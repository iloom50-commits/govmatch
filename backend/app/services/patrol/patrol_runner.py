"""AI 패트롤 메인 실행자

매일 새벽 3시 실행:
1. URL 헬스체크 + 자동 수정
2. 분석 실패 재시도
3. 인기 카테고리 미분석 발굴
4. 결과를 patrol_history에 저장
"""
import logging
import json
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def run_patrol(triggered_by: str = "scheduler") -> Dict[str, Any]:
    """전체 패트롤 실행

    Returns: 실행 결과 요약 dict
    """
    from app.main import get_db_connection
    from .url_health import scan_and_fix_urls
    from .analysis_recovery import recover_failed_analyses, discover_unanalyzed

    summary: Dict[str, Any] = {
        "triggered_by": triggered_by,
        "started_at": time.time(),
        "url_health": None,
        "recovery": None,
        "discovery": None,
        "elapsed_seconds": 0,
        "errors": [],
    }

    history_id: Optional[int] = None
    conn = get_db_connection()

    # patrol_history INSERT (running 상태)
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO patrol_history (status, summary)
            VALUES ('running', %s::jsonb)
            RETURNING id
        """, (json.dumps({"triggered_by": triggered_by}),))
        row = cur.fetchone()
        history_id = row["id"] if row else None
        conn.commit()
    except Exception as e:
        logger.error(f"[Patrol] history insert failed: {e}")
        try: conn.rollback()
        except: pass

    # ── 1. URL 헬스체크 ──
    try:
        logger.info("[Patrol] Starting URL health check...")
        result = scan_and_fix_urls(conn)
        summary["url_health"] = result
        logger.info(f"[Patrol] URL: scanned={result['scanned']}, fixed={result['fixed']}")
    except Exception as e:
        msg = f"url_health failed: {e}"
        logger.error(f"[Patrol] {msg}")
        summary["errors"].append(msg)

    # ── 2. 인기 카테고리 미분석 발굴 (재시도 큐 추가) ──
    try:
        logger.info("[Patrol] Discovering unanalyzed popular announcements...")
        result = discover_unanalyzed(conn, limit=100)
        summary["discovery"] = result
        logger.info(f"[Patrol] Discovery: queued={result['queued_for_analysis']}")
    except Exception as e:
        msg = f"discovery failed: {e}"
        logger.error(f"[Patrol] {msg}")
        summary["errors"].append(msg)

    # ── 3. 오늘의 인기 공고 업데이트 ──
    try:
        logger.info("[Patrol] Updating trending announcements...")
        from .trending import run_trending_update
        result = run_trending_update(conn)
        summary["trending"] = result
        logger.info(f"[Patrol] Trending: {result['saved']} announcements selected")
    except Exception as e:
        msg = f"trending failed: {e}"
        logger.error(f"[Patrol] {msg}")
        summary["errors"].append(msg)

    # ── 4. 최종 URL 수집 (경유지 → 원본 URL) ──
    try:
        logger.info("[Patrol] Resolving final URLs for priority announcements...")
        from .final_url_resolver import resolve_priority_announcements
        result = resolve_priority_announcements(conn, limit=30)
        summary["final_url"] = result
        logger.info(f"[Patrol] FinalURL: resolved={result['resolved']}/{result['total']}")
    except Exception as e:
        msg = f"final_url failed: {e}"
        logger.error(f"[Patrol] {msg}")
        summary["errors"].append(msg)

    # ── 4. 분석 실패 재시도 (실제 분석 실행) ──
    try:
        logger.info("[Patrol] Recovering failed analyses...")
        result = recover_failed_analyses(conn, max_retries=100)
        summary["recovery"] = result
        logger.info(f"[Patrol] Recovery: attempted={result['attempted']}, recovered={result['recovered']}")
    except Exception as e:
        msg = f"recovery failed: {e}"
        logger.error(f"[Patrol] {msg}")
        summary["errors"].append(msg)

    # 종료
    summary["elapsed_seconds"] = round(time.time() - summary["started_at"], 1)
    summary["completed_at"] = time.time()

    # patrol_history UPDATE
    if history_id:
        try:
            cur = conn.cursor()
            status = "failed" if summary["errors"] else "success"
            cur.execute("""
                UPDATE patrol_history
                SET completed_at = CURRENT_TIMESTAMP,
                    status = %s,
                    summary = %s::jsonb,
                    error = %s
                WHERE id = %s
            """, (
                status,
                json.dumps(summary, ensure_ascii=False, default=str),
                "; ".join(summary["errors"])[:500] if summary["errors"] else None,
                history_id,
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"[Patrol] history update failed: {e}")

    try: conn.close()
    except: pass

    logger.info(f"[Patrol] Done in {summary['elapsed_seconds']}s | errors={len(summary['errors'])}")
    return summary


def get_latest_report(db_conn, limit: int = 10) -> Dict[str, Any]:
    """최근 패트롤 실행 이력 조회"""
    cur = db_conn.cursor()
    cur.execute("""
        SELECT id, started_at, completed_at, status, summary, error
        FROM patrol_history
        ORDER BY started_at DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    history = []
    for r in rows:
        item = dict(r)
        # JSONB 처리
        s = item.get("summary")
        if isinstance(s, str):
            try: item["summary"] = json.loads(s)
            except: pass
        # 시간 직렬화
        for k in ("started_at", "completed_at"):
            if item.get(k):
                item[k] = str(item[k])
        history.append(item)
    return {"history": history, "count": len(history)}
