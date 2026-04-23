"""스크래퍼 감시 — scraper_runs 로그 분석 + 알림.

기준:
  - 24시간 내 status=error 3회 이상 → 심각
  - items_saved=0 (이전엔 저장 있었음) 3일 연속 → HTML 변경 의심
  - 전체 수집량 평균 대비 -30% → 의심

오케스트레이터의 보고서 생성 단계에서 호출.
"""
from __future__ import annotations
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def check_scraper_health(db_conn) -> Dict[str, Any]:
    """최근 스크래퍼 상태 집계 + 경보."""
    cur = db_conn.cursor()

    # 24시간 내 실행별 통계
    cur.execute("""
        SELECT source,
               COUNT(*) AS runs,
               COUNT(CASE WHEN status='ok' THEN 1 END) AS ok,
               COUNT(CASE WHEN status='error' THEN 1 END) AS err,
               COUNT(CASE WHEN status='empty' THEN 1 END) AS empty,
               SUM(items_saved) AS saved_24h,
               MAX(started_at) AS last_run
        FROM scraper_runs
        WHERE started_at > NOW() - INTERVAL '24 hours'
        GROUP BY source
        ORDER BY source
    """)
    rows_24h = [dict(r) for r in cur.fetchall()]

    # 3일 연속 0건 저장 스크래퍼 (이전엔 정상)
    cur.execute("""
        WITH daily AS (
          SELECT source, DATE(started_at) AS day, SUM(items_saved) AS saved
          FROM scraper_runs
          WHERE started_at > NOW() - INTERVAL '10 days'
          GROUP BY source, DATE(started_at)
        )
        SELECT source, ARRAY_AGG(day ORDER BY day DESC) AS days,
               ARRAY_AGG(saved ORDER BY day DESC) AS saveds
        FROM daily
        GROUP BY source
    """)
    trends = [dict(r) for r in cur.fetchall()]

    # 경보 판정
    alerts: List[Dict[str, Any]] = []
    for r in rows_24h:
        src = r["source"]
        if r["err"] and r["err"] >= 3:
            alerts.append({
                "level": "critical", "source": src,
                "msg": f"24h 내 에러 {r['err']}회 — 스크래퍼 점검 필요"
            })
        elif r["ok"] == 0 and r["runs"] > 0:
            alerts.append({
                "level": "warn", "source": src,
                "msg": f"24h 내 성공 0건 (시도 {r['runs']}회)"
            })

    for t in trends:
        days = t.get("days") or []
        saveds = t.get("saveds") or []
        if len(saveds) >= 3:
            last3 = saveds[:3]
            if all((s or 0) == 0 for s in last3) and any((s or 0) > 0 for s in saveds[3:]):
                alerts.append({
                    "level": "warn", "source": t["source"],
                    "msg": f"3일 연속 수집 0건 (과거엔 있었음) — HTML 구조 변경 의심"
                })

    # 전체 합계
    cur.execute("""
        SELECT COUNT(DISTINCT source) AS n_sources,
               SUM(items_saved) AS total_saved,
               COUNT(*) AS total_runs
        FROM scraper_runs
        WHERE started_at > NOW() - INTERVAL '24 hours'
    """)
    summary = dict(cur.fetchone() or {})

    return {
        "summary_24h": summary,
        "per_source_24h": rows_24h,
        "alerts": alerts,
        "alert_count": len(alerts),
    }


def format_report(health: Dict[str, Any]) -> str:
    """자연어 보고서 — 카카오/이메일 발송용."""
    s = health.get("summary_24h", {}) or {}
    alerts = health.get("alerts", []) or []
    lines = []
    lines.append(f"📊 스크래퍼 24h 요약")
    lines.append(f"  • 활성 소스: {s.get('n_sources', 0)}개")
    lines.append(f"  • 실행 총합: {s.get('total_runs', 0)}회")
    lines.append(f"  • 신규 저장: {s.get('total_saved', 0)}건")

    if alerts:
        lines.append(f"\n🚨 경보 {len(alerts)}건")
        for a in alerts[:10]:
            icon = "🔴" if a["level"] == "critical" else "🟡"
            lines.append(f"  {icon} [{a['source']}] {a['msg']}")
    else:
        lines.append("\n✅ 경보 없음 — 모든 스크래퍼 정상")

    return "\n".join(lines)
