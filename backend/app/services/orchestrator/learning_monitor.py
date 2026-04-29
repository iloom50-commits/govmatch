"""
learning_monitor.py — knowledge_base 학습 상태 감시
일일 증감, 에이전트별 기여, 임베딩 누락 등 체크
"""
import json


def check_learning(db_conn) -> dict:
    """
    knowledge_base 현황 수집.
    반환: {
        "total": int,
        "today_added": int,
        "by_source_agent": {...},
        "by_category": {...},
        "no_embedding_count": int,
        "consult_log_today": int,
    }
    """
    result = {}
    cur = db_conn.cursor()

    # 1. 전체 지식 건수
    try:
        cur.execute("SELECT COUNT(*) AS cnt FROM knowledge_base")
        row = cur.fetchone()
        result["total"] = row["cnt"] if row else 0
    except Exception as e:
        result["total"] = -1
        print(f"[Orchestrator/learning] total 조회 오류: {e}")

    # 2. 오늘 추가된 지식
    try:
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM knowledge_base
            WHERE created_at >= CURRENT_DATE
        """)
        row = cur.fetchone()
        result["today_added"] = row["cnt"] if row else 0
    except Exception:
        result["today_added"] = 0

    # 3. source_agent별 분포
    try:
        cur.execute("""
            SELECT source_agent, COUNT(*) AS cnt
            FROM knowledge_base
            GROUP BY source_agent
            ORDER BY cnt DESC
        """)
        result["by_source_agent"] = {
            r["source_agent"] or "unknown": r["cnt"]
            for r in cur.fetchall()
        }
    except Exception:
        result["by_source_agent"] = {}

    # 4. category별 분포 (상위 10개)
    try:
        cur.execute("""
            SELECT category, COUNT(*) AS cnt
            FROM knowledge_base
            GROUP BY category
            ORDER BY cnt DESC
            LIMIT 10
        """)
        result["by_category"] = {
            r["category"] or "미분류": r["cnt"]
            for r in cur.fetchall()
        }
    except Exception:
        result["by_category"] = {}

    # 5. 임베딩 누락 건수
    try:
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM knowledge_base
            WHERE embedding IS NULL
        """)
        row = cur.fetchone()
        result["no_embedding_count"] = row["cnt"] if row else 0
    except Exception:
        result["no_embedding_count"] = -1

    # 6. 오늘 상담 로그 건수
    try:
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM ai_consult_logs
            WHERE updated_at >= CURRENT_DATE
        """)
        row = cur.fetchone()
        result["consult_log_today"] = row["cnt"] if row else 0
    except Exception:
        result["consult_log_today"] = 0

    # 7. 최근 7일 일별 지식 추가 추이
    try:
        cur.execute("""
            SELECT DATE(created_at) AS day, COUNT(*) AS cnt
            FROM knowledge_base
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY day
        """)
        result["weekly_trend"] = [
            {"day": str(r["day"]), "count": r["cnt"]}
            for r in cur.fetchall()
        ]
    except Exception:
        result["weekly_trend"] = []

    return result
