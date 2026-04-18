"""학습 파이프라인 모니터 — 지식 추출/활용 상태 감시."""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def check_learning_health(db_conn) -> Dict[str, Any]:
    """학습 파이프라인 건강 상태 확인.

    Returns: {
        "extraction_today": int,        # 오늘 추출된 지식 수
        "kb_growth_7d": int,            # 7일간 knowledge_base 증가량
        "unused_ratio": float,          # 미활용 비율
        "by_source": {...},             # 소스별 현황
        "embedding_coverage": float,    # 임베딩 커버리지
        "lite_learning_active": bool,   # LITE 학습 동작 여부
        "alerts": [...]
    }
    """
    result: Dict[str, Any] = {"alerts": []}
    cur = db_conn.cursor()

    try:
        # 오늘 추출된 지식
        cur.execute("SELECT COUNT(*) as cnt FROM knowledge_base WHERE created_at >= CURRENT_DATE")
        result["extraction_today"] = cur.fetchone()["cnt"]

        # 7일 증가량
        cur.execute("""
            SELECT COUNT(*) as cnt FROM knowledge_base
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        """)
        result["kb_growth_7d"] = cur.fetchone()["cnt"]

        # 전체 / 미활용
        cur.execute("SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE use_count = 0) as unused FROM knowledge_base")
        r = cur.fetchone()
        total = r["total"] or 1
        result["kb_total"] = total
        result["unused_ratio"] = round(r["unused"] / total, 2)

        # 소스별 현황
        cur.execute("""
            SELECT source, COUNT(*) as cnt,
                   AVG(use_count) as avg_use,
                   COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days') as recent
            FROM knowledge_base
            GROUP BY source
            ORDER BY cnt DESC
        """)
        by_source = {}
        for r in cur.fetchall():
            by_source[r["source"]] = {
                "total": r["cnt"],
                "avg_use": round(float(r["avg_use"] or 0), 1),
                "recent_7d": r["recent"],
            }
        result["by_source"] = by_source

        # 임베딩 커버리지
        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embed,
                   COUNT(*) as total
            FROM knowledge_base
        """)
        r = cur.fetchone()
        result["embedding_coverage"] = round(r["with_embed"] / r["total"], 2) if r["total"] > 0 else 0

        # LITE 학습 동작 여부 (최근 7일 내 source='lite_consult' 있는지)
        cur.execute("""
            SELECT COUNT(*) as cnt FROM knowledge_base
            WHERE source = 'lite_consult' AND created_at >= CURRENT_DATE - INTERVAL '7 days'
        """)
        lite_recent = cur.fetchone()["cnt"]
        result["lite_learning_active"] = lite_recent > 0

        # ── 이상 감지 ──
        if result["extraction_today"] == 0:
            result["alerts"].append("오늘 지식 추출 0건")

        if result["kb_growth_7d"] == 0:
            result["alerts"].append("7일간 knowledge_base 성장 0건 — 학습 중단")

        if result["unused_ratio"] > 0.85:
            result["alerts"].append(f"미활용 지식 {result['unused_ratio']*100:.0f}% — 조회 로직 점검 필요")

        if result["embedding_coverage"] < 0.9:
            result["alerts"].append(f"임베딩 커버리지 {result['embedding_coverage']*100:.0f}% — 누락 보강 필요")

        if not result["lite_learning_active"]:
            result["alerts"].append("LITE 상담 학습이 7일간 미동작")

    except Exception as e:
        logger.error(f"[LearningMonitor] Error: {e}")
        result["error"] = str(e)

    return result
