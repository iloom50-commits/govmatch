"""health_collector.py — 시스템 건강/경보 + 매출 신호 수집.

전부 실제 DB/로그 조회 + API 카나리아 실호출 (지어내는 값 없음).
'조용한 고장'(파이프라인 멈춤·수집 정체·재분석 멈춤·크레딧 소진)을 감지하여
일일 리포트 최상단 경보로 노출한다.

나이(정체 일수)는 DB의 NOW() 기준으로 SQL에서 계산 — 서버/로컬 timezone 차이 무관.
"""
from __future__ import annotations
import os

STALE_DAYS = 2  # 이 일수 이상 정체 시 🚨 경보


def _api_canary() -> dict:
    """Gemini/OpenAI 초소형 실호출로 크레딧 생존 확인.
    True=정상 / False=이상(크레딧 소진 등) / None=키 미설정."""
    out: dict = {}
    # Gemini
    try:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            out["Gemini"] = None
        else:
            import google.generativeai as genai
            genai.configure(api_key=key)
            m = genai.GenerativeModel("models/gemini-2.5-flash")
            r = m.generate_content("ping", request_options={"timeout": 20})
            out["Gemini"] = bool(getattr(r, "text", ""))
    except Exception as e:
        out["Gemini"] = False
        out["Gemini_err"] = str(e)[:70]
    # OpenAI
    try:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            out["OpenAI"] = None
        else:
            from openai import OpenAI
            c = OpenAI(api_key=key)
            r = c.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1, timeout=20,
            )
            out["OpenAI"] = bool(r.choices)
    except Exception as e:
        out["OpenAI"] = False
        out["OpenAI_err"] = str(e)[:70]
    return out


def collect_health(db_conn, run_canary: bool = True) -> dict:
    """리포트 최상단 경보/매출 섹션용 데이터. alerts=[] 이면 건강."""
    cur = db_conn.cursor()
    alerts: list[str] = []
    h: dict = {"alerts": alerts}

    # 1. 파이프라인 마지막 실행
    try:
        cur.execute("""
            SELECT created_at, result,
                   EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400 AS age_days
            FROM system_logs WHERE action IN ('daily_pipeline', 'pipeline_run')
            ORDER BY created_at DESC LIMIT 1
        """)
        r = cur.fetchone()
        if not r:
            alerts.append("🚨 파이프라인 실행 기록 없음")
            h["pipeline"] = {"last": None}
        else:
            age = float(r["age_days"] or 0)
            h["pipeline"] = {"last": str(r["created_at"]), "age_days": round(age, 1), "result": r["result"]}
            if age > STALE_DAYS:
                alerts.append(f"🚨 파이프라인 {age:.0f}일째 미실행 (마지막 {r['created_at']:%m-%d %H:%M})")
            elif r["result"] and str(r["result"]) not in ("success", "ok"):
                alerts.append(f"🚨 파이프라인 마지막 실행 결과: {r['result']}")
    except Exception as e:
        alerts.append("⚠️ 파이프라인 상태 조회 실패")
        h["pipeline"] = {"error": str(e)[:80]}

    # 2. 공고 수집 신선도
    try:
        cur.execute("""
            SELECT MAX(created_at) AS mx,
                   EXTRACT(EPOCH FROM (NOW() - MAX(created_at))) / 86400 AS age_days,
                   COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 day') AS d1
            FROM announcements
        """)
        r = cur.fetchone()
        age = float(r["age_days"] or 0)
        h["collection"] = {"newest": str(r["mx"]), "age_days": round(age, 1), "new_1d": int(r["d1"] or 0)}
        if r["mx"] and age > STALE_DAYS:
            alerts.append(f"🚨 공고 수집 {age:.0f}일째 정체 (최신 {r['mx']:%m-%d})")
    except Exception as e:
        alerts.append("⚠️ 공고 수집 상태 조회 실패")
        h["collection"] = {"error": str(e)[:80]}

    # 3. 재분석 건강 — 2개월 방치 재발을 잡는 핵심 지표
    try:
        cur.execute("""
            SELECT MAX(ai_analyzed_at) AS mx,
                   EXTRACT(EPOCH FROM (NOW() - MAX(ai_analyzed_at))) / 86400 AS age_days
            FROM announcements
        """)
        r = cur.fetchone()
        age = float(r["age_days"] or 0)
        cur.execute("""
            SELECT COUNT(*) AS n FROM announcements
            WHERE (deadline_date IS NULL OR deadline_date >= CURRENT_DATE)
              AND (eligibility_logic IS NULL OR eligibility_logic = '' OR eligibility_logic = '{}')
              AND ai_analyzed_at IS NULL
        """)
        backlog = int(cur.fetchone()["n"] or 0)
        h["reanalyze"] = {"newest": str(r["mx"]), "age_days": round(age, 1), "backlog": backlog}
        if r["mx"] and age > STALE_DAYS:
            alerts.append(f"🚨 재분석 {age:.0f}일째 멈춤 — matcher 데이터 노후화 (미분석 {backlog}건)")
    except Exception as e:
        alerts.append("⚠️ 재분석 상태 조회 실패")
        h["reanalyze"] = {"error": str(e)[:80]}

    # 4. API 크레딧 카나리아 (초소형 실호출)
    if run_canary:
        api = _api_canary()
        h["api"] = api
        for name in ("Gemini", "OpenAI"):
            if api.get(name) is False:
                alerts.append(f"🚨 {name} API 이상 — 크레딧 소진 의심 ({api.get(name + '_err', '')})")
    else:
        h["api"] = {}

    # 4b. 기관 수집(admin_urls) 정지 감지 (A-4 — 99일 정지 사례를 잡는 신호)
    try:
        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE is_active = 1) AS active,
                   EXTRACT(EPOCH FROM (NOW() - MAX(last_scraped))) / 86400 AS age
            FROM admin_urls
        """)
        r = cur.fetchone()
        age = float(r["age"] or 0)
        h["admin_scraper"] = {"active": int(r["active"] or 0), "age_days": round(age, 1)}
        if r["active"] and age > STALE_DAYS:
            alerts.append(f"🚨 기관 수집(admin_urls {int(r['active'])}개) {age:.0f}일째 정지")
    except Exception as e:
        h["admin_scraper"] = {"error": str(e)[:80]}

    # 4c. 소스별 수집 신선도 — 7일+ 정체한 활성 소스 (A-8/B-2: 전체 MAX만 보면 못 잡음)
    try:
        cur.execute("""
            SELECT origin_source,
                   EXTRACT(EPOCH FROM (NOW() - MAX(created_at))) / 86400 AS age
            FROM announcements
            WHERE origin_source IS NOT NULL
            GROUP BY origin_source HAVING COUNT(*) >= 20
        """)
        stale = sorted(
            [(row["origin_source"], float(row["age"] or 0)) for row in cur.fetchall()
             if float(row["age"] or 0) > 7],
            key=lambda x: -x[1],
        )
        h["stale_sources"] = [f"{s}({a:.0f}d)" for s, a in stale[:8]]
        if len(stale) >= 5:
            alerts.append(f"🚨 수집 정체 소스 {len(stale)}개(7일+): {', '.join(s for s, _ in stale[:5])} 등")
    except Exception as e:
        h["stale_sources"] = {"error": str(e)[:80]}

    # 4d. 다이제스트/이메일 발송 (B-1)
    #   다이제스트는 평일(월~금, UTC)만 발송 → 주말(토·일)의 정체는 정상이므로 경보 제외.
    try:
        cur.execute("""
            SELECT EXTRACT(EPOCH FROM (NOW() - MAX(sent_at))) / 86400 AS age,
                   COUNT(*) FILTER (WHERE sent_at >= NOW() - INTERVAL '1 day') AS d1,
                   EXTRACT(ISODOW FROM NOW()) AS dow
            FROM notification_logs WHERE channel = 'email'
        """)
        r = cur.fetchone()
        age = float(r["age"]) if r and r["age"] is not None else 999
        is_weekend = int(r["dow"]) in (6, 7) if r and r["dow"] is not None else False  # 6=토,7=일
        h["digest"] = {"age_days": round(age, 1) if age < 999 else None, "sent_1d": int(r["d1"] or 0)}
        if age > STALE_DAYS and not is_weekend:
            alerts.append(f"🚨 이메일/다이제스트 {age:.0f}일째 미발송")
    except Exception as e:
        h["digest"] = {"error": str(e)[:80]}

    # 4d-2. 다이제스트 발송수 급감 감지 (6/25형 — 4명 vs 평소 중앙 67명)
    #   어제(직전 발송일)가 평소 중앙값의 30% 미만이면 경고. 주말(발송 없음)은 자동 제외.
    try:
        cur.execute("""
            WITH daily AS (
                SELECT DATE(sent_at) AS d, COUNT(*) AS c
                FROM notification_logs
                WHERE channel = 'email' AND sent_at >= NOW() - INTERVAL '12 days'
                GROUP BY DATE(sent_at)
            )
            SELECT
                (SELECT c FROM daily WHERE d = (NOW() - INTERVAL '1 day')::date) AS yest,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c) AS med
            FROM daily WHERE d < (NOW() - INTERVAL '1 day')::date
        """)
        r = cur.fetchone()
        yest = r["yest"] if r else None
        med = float(r["med"]) if r and r["med"] is not None else None
        if yest is not None and med and med >= 10 and yest < med * 0.3:
            alerts.append(f"⚠️ 다이제스트 발송 급감: 어제 {int(yest)}명 (평소 중앙 {med:.0f}명)")
    except Exception:
        pass

    # 4e. 결제 실패/강등 (A-6) — 최근 3일 auto_renew partial/error
    try:
        cur.execute("""
            SELECT detail, created_at FROM system_logs
            WHERE action = 'auto_renew' AND result IN ('partial', 'error')
              AND created_at >= NOW() - INTERVAL '3 days'
            ORDER BY created_at DESC LIMIT 1
        """)
        r = cur.fetchone()
        if r:
            h["billing"] = {"issue": r["detail"], "at": str(r["created_at"])}
            alerts.append(f"🚨 결제 이슈(최근3일): {r['detail']}")
    except Exception as e:
        h["billing"] = {"error": str(e)[:80]}

    # 4f. 분석 실패 백로그 (B-4)
    try:
        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE resolved_at IS NULL) AS open_n,
                   COUNT(*) FILTER (WHERE resolved_at IS NULL AND retry_count >= 5) AS exhausted
            FROM analysis_failures
        """)
        r = cur.fetchone()
        open_n = int(r["open_n"] or 0)
        h["analysis_backlog"] = {"open": open_n, "exhausted": int(r["exhausted"] or 0)}
        if open_n >= 5000:
            alerts.append(f"⚠️ 분석 실패 백로그 {open_n:,}건 누적 (재시도소진 {int(r['exhausted'] or 0)})")
    except Exception as e:
        h["analysis_backlog"] = {"error": str(e)[:80]}

    # 4g. Hot이슈 자동생성 정체 (A-5)
    try:
        cur.execute("""
            SELECT EXTRACT(EPOCH FROM (NOW() - MAX(created_at))) / 86400 AS age
            FROM hot_issues WHERE auto_generated = TRUE
        """)
        r = cur.fetchone()
        age = float(r["age"]) if r and r["age"] is not None else 999
        h["hot_issue"] = {"age_days": round(age, 1) if age < 999 else None}
        if age > 8:
            label = f"{age:.0f}일째" if age < 999 else "기록 없음"
            alerts.append(f"⚠️ Hot이슈 자동생성 {label} 정체")
    except Exception as e:
        h["hot_issue"] = {"error": str(e)[:80]}

    # 5. 매출/전환 신호 (users.plan / billing_key / plan_started_at)
    try:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE plan = 'pro') AS pro_total,
                COUNT(*) FILTER (WHERE plan = 'pro' AND billing_key IS NOT NULL AND billing_key <> '') AS pro_paying,
                COUNT(*) FILTER (WHERE plan = 'pro'
                                 AND plan_started_at >= CURRENT_DATE - INTERVAL '1 day'
                                 AND plan_started_at <  CURRENT_DATE) AS new_pro_yest,
                COUNT(*) AS users_total
            FROM users
        """)
        r = cur.fetchone()
        pro_total = int(r["pro_total"] or 0)
        pro_paying = int(r["pro_paying"] or 0)
        users_total = int(r["users_total"] or 0)
        h["sales"] = {
            "pro_total": pro_total,
            "pro_paying": pro_paying,
            "pro_promo_trial": pro_total - pro_paying,
            "new_pro_yesterday": int(r["new_pro_yest"] or 0),
            "conversion_rate": round(pro_total / users_total * 100, 1) if users_total else 0,
        }
    except Exception as e:
        h["sales"] = {"error": str(e)[:80]}

    h["ok"] = len(alerts) == 0
    return h
