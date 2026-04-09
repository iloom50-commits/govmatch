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

    # 재시도 대상: next_retry_at <= NOW + resolved_at IS NULL + retry_count < 5
    cur.execute("""
        SELECT af.id, af.announcement_id, af.error_type, af.retry_count,
               a.title, a.origin_url, a.summary_text
        FROM analysis_failures af
        JOIN announcements a ON a.announcement_id = af.announcement_id
        WHERE af.resolved_at IS NULL
          AND af.retry_count < 5
          AND (af.next_retry_at IS NULL OR af.next_retry_at <= CURRENT_TIMESTAMP)
        ORDER BY af.next_retry_at NULLS FIRST
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
        "by_error_type": by_error_type,
    }


def discover_unanalyzed(db_conn, limit: int = 30) -> Dict[str, Any]:
    """분석되지 않은 인기 카테고리 공고 자동 등록 (정책자금/보증/R&D 등)
    아직 analysis_failures에도 없고 announcement_analysis에도 없는 항목을 큐에 추가
    """
    cur = db_conn.cursor()

    # 인기 카테고리 + 분석 없음 + 실패 기록도 없음
    cur.execute("""
        SELECT a.announcement_id, a.title
        FROM announcements a
        LEFT JOIN announcement_analysis aa ON aa.announcement_id = a.announcement_id
        LEFT JOIN analysis_failures af ON af.announcement_id = a.announcement_id AND af.resolved_at IS NULL
        WHERE aa.announcement_id IS NULL
          AND af.id IS NULL
          AND (a.title ILIKE '%%정책자금%%' OR a.title ILIKE '%%보증%%'
               OR a.title ILIKE '%%R&D%%' OR a.title ILIKE '%%기술개발%%'
               OR a.title ILIKE '%%창업%%' OR a.title ILIKE '%%수출%%')
          AND a.deadline_date IS NULL OR a.deadline_date >= CURRENT_DATE
        ORDER BY a.created_at DESC
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
