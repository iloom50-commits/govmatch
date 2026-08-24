"""분석 실패 재시도 — analysis_failures 큐에서 next_retry_at <= now 항목 처리"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def recover_failed_analyses(db_conn, max_retries: int = 50) -> Dict[str, Any]:
    """재시도 가능한 분석 실패 항목 처리

    Returns: {attempted, recovered, still_failed, by_error_type}
    """
    from app.services.doc_analysis_service import analyze_and_store

    cur = db_conn.cursor()

    # extract_empty(본문 추출 불가 = PDF 파싱실패/빈 페이지)는 재시도해도 소용없다.
    # 임계 2로 조기소진: 초기+2회 재시도 후 '분석 불가' 확정 마킹 → 백로그·재시도에서 영구 제외.
    # (전엔 retry>=5까지 헛되이 재시도해 500+건이 복구 슬롯을 점유 → gemini_empty 회복을 지연시킴.
    #  일시장애 대비 2회 재시도는 남기되, 그 이상 반복은 낭비이므로 조기 정리)
    resolved_unanalyzable = 0
    try:
        cur.execute("""
            UPDATE analysis_failures SET resolved_at = CURRENT_TIMESTAMP
            WHERE resolved_at IS NULL AND retry_count >= 2 AND error_type = 'extract_empty'
        """)
        resolved_unanalyzable = cur.rowcount
        db_conn.commit()
    except Exception:
        try:
            db_conn.rollback()
        except Exception:
            pass

    # 재시도 대상: next_retry_at <= NOW + resolved_at IS NULL + retry_count < 5
    cur.execute("""
        SELECT af.id, af.announcement_id, af.error_type, af.retry_count,
               a.title, a.origin_url, a.summary_text
        FROM analysis_failures af
        JOIN announcements a ON a.announcement_id = af.announcement_id
        WHERE af.resolved_at IS NULL
          AND af.retry_count < 5
          AND (af.next_retry_at IS NULL OR af.next_retry_at <= CURRENT_TIMESTAMP)
          -- 마감이 지난 공고는 분석해도 쓸 데가 없다. 실측(2026-08-24): 최근 7일 분석
          -- 388건 중 54건(14%)이 이미 마감된 공고였다. 그만큼 슬롯과 토큰을 버렸다.
          AND (a.deadline_date IS NULL OR a.deadline_date >= CURRENT_DATE)
        -- 마감이 임박한 것부터. 마감일이 없는 것은 그다음(원문을 열어야 마감을 알 수 있다).
        ORDER BY (a.deadline_date IS NULL), a.deadline_date ASC, af.next_retry_at NULLS FIRST
        LIMIT %s
    """, (max_retries,))
    rows = cur.fetchall()

    attempted = 0
    recovered = 0
    still_failed = 0
    by_error_type: Dict[str, int] = {}

    for row in rows:
        aid = row["announcement_id"]
        error_type = row["error_type"]
        by_error_type[error_type] = by_error_type.get(error_type, 0) + 1
        attempted += 1

        try:
            # 별도 connection으로 분석 (rollback 영향 격리)
            from app.main import get_db_connection
            sub_conn = get_db_connection()
            try:
                result = analyze_and_store(
                    announcement_id=aid,
                    origin_url=row["origin_url"] or "",
                    title=row["title"] or "",
                    db_conn=sub_conn,
                    summary_text=row.get("summary_text") or "",
                )
                if result.get("success"):
                    recovered += 1
                    logger.info(f"[Patrol Recovery] ✓ #{aid} recovered")
                else:
                    still_failed += 1
                    logger.info(f"[Patrol Recovery] ✗ #{aid} still failed: {result.get('error')}")
            finally:
                sub_conn.close()
        except Exception as e:
            still_failed += 1
            logger.error(f"[Patrol Recovery] error #{aid}: {e}")

    return {
        "attempted": attempted,
        "recovered": recovered,
        "still_failed": still_failed,
        "resolved_unanalyzable": resolved_unanalyzable,
        "by_error_type": by_error_type,
    }


PRIORITY_CATEGORIES = ["소상공인", "수출지원", "금융"]


def preanalyze_priority_categories(
    db_conn,
    categories: list = None,
    min_days_left: int = 5,
    limit: int = 50,
) -> Dict[str, Any]:
    """마감 N일 이상 남은 우선 카테고리 미분석 공고를 즉시 분석.

    discover_unanalyzed()는 큐에만 넣지만, 이 함수는 analyze_and_store()를 직접 호출해
    사용자가 '나도 받을 수 있나?'를 클릭할 때 캐시 히트가 되도록 미리 채워둔다.
    """
    from app.services.doc_analysis_service import analyze_and_store
    from app.main import get_db_connection

    if categories is None:
        categories = PRIORITY_CATEGORIES

    cur = db_conn.cursor()
    cur.execute("""
        SELECT a.announcement_id, a.title, a.origin_url, a.summary_text, a.category,
               a.deadline_date
        FROM announcements a
        LEFT JOIN announcement_analysis aa ON aa.announcement_id = a.announcement_id
        WHERE aa.announcement_id IS NULL
          AND a.is_archived = FALSE
          AND a.category = ANY(%s)
          AND a.deadline_date >= CURRENT_DATE + INTERVAL '1 day' * %s
          AND a.origin_url IS NOT NULL AND a.origin_url != ''
        ORDER BY a.deadline_date ASC
        LIMIT %s
    """, (categories, min_days_left, limit))
    candidates = cur.fetchall()

    attempted = 0
    succeeded = 0
    failed = 0

    for row in candidates:
        aid = row["announcement_id"]
        attempted += 1
        try:
            sub_conn = get_db_connection()
            try:
                result = analyze_and_store(
                    announcement_id=aid,
                    origin_url=row["origin_url"] or "",
                    title=row["title"] or "",
                    db_conn=sub_conn,
                    summary_text=row.get("summary_text") or "",
                )
                if result.get("success"):
                    succeeded += 1
                    logger.info(f"[PriorityAnalysis] ✓ #{aid} ({row['category']}) analyzed")
                else:
                    failed += 1
                    logger.warning(f"[PriorityAnalysis] ✗ #{aid} failed: {result.get('error')}")
            finally:
                sub_conn.close()
        except Exception as e:
            failed += 1
            logger.error(f"[PriorityAnalysis] error #{aid}: {e}")

    logger.info(
        f"[PriorityAnalysis] categories={categories} attempted={attempted} "
        f"succeeded={succeeded} failed={failed}"
    )
    return {
        "categories": categories,
        "candidates": len(candidates),
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
    }


def discover_unanalyzed(db_conn, limit: int = 100) -> Dict[str, Any]:
    """분석되지 않은 공고를 자동 등록.
    아직 analysis_failures에도 없고 announcement_analysis에도 없는 항목을 큐에 추가.
    origin_url이 있는 공고를 대상으로, 마감 미상(deadline_date NULL)을 우선 처리
    (원문 확보→enricher가 마감 채움. 문제2 근본, P1-3).
    """
    cur = db_conn.cursor()

    cur.execute("""
        SELECT a.announcement_id, a.title
        FROM announcements a
        LEFT JOIN announcement_analysis aa ON aa.announcement_id = a.announcement_id
        LEFT JOIN analysis_failures af ON af.announcement_id = a.announcement_id AND af.resolved_at IS NULL
        WHERE aa.announcement_id IS NULL
          AND af.id IS NULL
          AND a.origin_url IS NOT NULL AND a.origin_url != ''
          AND (a.deadline_date IS NULL OR a.deadline_date >= CURRENT_DATE)
        -- 마감 임박한 것을 먼저 넣는다.
        -- 전에는 마감일 없는 것을 우선했다(원문 확보 → enricher 가 마감을 채우는 흐름).
        -- 그런데 마감일 없는 공고가 5,379건이라 우선순위를 계속 먹었고, 마감 90일 이내
        -- 841건(그중 7일 이내 492건)이 분석되지 못한 채 남았다(2026-08-24 실측).
        -- 마감을 채우는 목적은 살리되(마감일 없음이 두 번째), 임박한 것이 밀리지 않게 한다.
        ORDER BY (a.deadline_date IS NULL), a.deadline_date ASC, a.created_at DESC
        LIMIT %s
    """, (limit,))
    candidates = cur.fetchall()

    discovered = 0
    for row in candidates:
        try:
            cur.execute("""
                INSERT INTO analysis_failures
                    (announcement_id, error_type, error_message, retry_count, next_retry_at)
                VALUES (%s, 'pending_first_analysis', 'Discovered by patrol', 0, CURRENT_TIMESTAMP)
                ON CONFLICT (announcement_id, error_type) DO NOTHING
            """, (row["announcement_id"],))
            discovered += 1
        except Exception:
            db_conn.rollback()
    db_conn.commit()
    return {"candidates_found": len(candidates), "queued_for_analysis": discovered}
