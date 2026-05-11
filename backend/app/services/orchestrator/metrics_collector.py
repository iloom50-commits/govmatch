"""
metrics_collector.py — 일일 비즈니스 지표 수집

collect_business_metrics(db_conn) → dict 반환:
  users:    누적/어제 신규/plan 분포/user_type 분포
  activity: 어제 DAU, 어제 AI상담(실질), 어제 PRO상담, 어제 매칭
  weekly:   최근 7일 DAU 추이
  totals:   누적 상담/PRO세션/매칭이력
"""
from __future__ import annotations


def collect_business_metrics(db_conn) -> dict:
    cur = db_conn.cursor()
    result: dict = {}

    # ── 1. 회원 누적 현황 ──────────────────────────────────────
    # public.users 테이블: created_at 없음 → 단순 COUNT
    try:
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE plan = 'pro')  AS pro,
                COUNT(*) FILTER (WHERE plan = 'lite') AS lite,
                COUNT(*) FILTER (WHERE plan = 'free') AS free
            FROM users
        """)
        r = cur.fetchone()
        result["users_total"] = int(r["total"] or 0)
        result["users_pro"]   = int(r["pro"]   or 0)
        result["users_lite"]  = int(r["lite"]  or 0)
        result["users_free"]  = int(r["free"]  or 0)
    except Exception as e:
        result["users_total"] = result["users_pro"] = result["users_lite"] = "N/A"
        print(f"[metrics] 회원 누적 오류: {e}")

    # ── 2. 어제 신규 가입 ──────────────────────────────────────
    # user_events.event_type='signup' 기준 (created_at은 UTC 저장)
    try:
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE u.user_type = 'business')   AS business,
                COUNT(*) FILTER (WHERE u.user_type = 'individual') AS individual,
                COUNT(*) FILTER (WHERE u.user_type = 'both')       AS both
            FROM user_events ue
            LEFT JOIN users u ON ue.business_number = u.business_number
            WHERE ue.event_type IN ('signup', 'social_login')
              AND ue.created_at >= CURRENT_DATE - INTERVAL '1 day'
              AND ue.created_at <  CURRENT_DATE
        """)
        r = cur.fetchone()
        result["new_users_yesterday"]            = int(r["total"]      or 0)
        result["new_users_yesterday_business"]   = int(r["business"]   or 0)
        result["new_users_yesterday_individual"] = int(r["individual"] or 0)
        result["new_users_yesterday_both"]       = int(r["both"]       or 0)
    except Exception as e:
        result["new_users_yesterday"] = "N/A"
        print(f"[metrics] 신규 가입 오류: {e}")

    # ── 3. 어제 DAU (로그인 이벤트 기준) ──────────────────────
    # user_events.created_at은 timestamp without tz (UTC 저장 가정)
    try:
        cur.execute("""
            SELECT COUNT(DISTINCT business_number) AS dau
            FROM user_events
            WHERE event_type IN ('login', 'social_login')
              AND created_at >= CURRENT_DATE - INTERVAL '1 day'
              AND created_at <  CURRENT_DATE
        """)
        r = cur.fetchone()
        result["dau_yesterday"] = int(r["dau"] or 0)
    except Exception as e:
        result["dau_yesterday"] = "N/A"
        print(f"[metrics] DAU 오류: {e}")

    # ── 4. 어제 AI 상담 (실질 상담 = 4턴 이상) ────────────────
    try:
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM ai_consult_logs
            WHERE jsonb_array_length(messages) >= 4
              AND created_at >= CURRENT_DATE - INTERVAL '1 day'
              AND created_at <  CURRENT_DATE
        """)
        r = cur.fetchone()
        result["ai_consults_yesterday"] = int(r["cnt"] or 0)
    except Exception as e:
        result["ai_consults_yesterday"] = "N/A"
        print(f"[metrics] AI 상담 오류: {e}")

    # ── 5. 어제 PRO 상담 ──────────────────────────────────────
    try:
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM pro_consult_sessions
            WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
              AND created_at <  CURRENT_DATE
        """)
        r = cur.fetchone()
        result["pro_consults_yesterday"] = int(r["cnt"] or 0)
    except Exception as e:
        result["pro_consults_yesterday"] = "N/A"
        print(f"[metrics] PRO 상담 오류: {e}")

    # ── 6. 어제 매칭 실행 ──────────────────────────────────────
    try:
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM user_events
            WHERE event_type = 'matching'
              AND created_at >= CURRENT_DATE - INTERVAL '1 day'
              AND created_at <  CURRENT_DATE
        """)
        r = cur.fetchone()
        result["matching_yesterday"] = int(r["cnt"] or 0)
    except Exception as e:
        result["matching_yesterday"] = "N/A"
        print(f"[metrics] 매칭 오류: {e}")

    # ── 7. 주간 DAU 추이 (최근 7일) ───────────────────────────
    try:
        cur.execute("""
            SELECT DATE(created_at) AS d, COUNT(DISTINCT business_number) AS dau
            FROM user_events
            WHERE event_type IN ('login', 'social_login')
              AND created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY d
        """)
        rows = cur.fetchall()
        result["weekly_dau"] = [
            {"date": str(r["d"]), "dau": int(r["dau"] or 0)}
            for r in rows
        ]
    except Exception as e:
        result["weekly_dau"] = []
        print(f"[metrics] 주간 DAU 오류: {e}")

    # ── 8. 누적 통계 ──────────────────────────────────────────
    try:
        cur.execute("SELECT COUNT(*) AS cnt FROM ai_consult_logs WHERE jsonb_array_length(messages) >= 4")
        r = cur.fetchone()
        result["total_real_consults"] = int(r["cnt"] or 0)
    except Exception:
        result["total_real_consults"] = "N/A"

    try:
        cur.execute("SELECT COUNT(*) AS cnt FROM pro_consult_sessions")
        r = cur.fetchone()
        result["total_pro_sessions"] = int(r["cnt"] or 0)
    except Exception:
        result["total_pro_sessions"] = "N/A"

    try:
        cur.execute("SELECT COUNT(*) AS cnt FROM match_history")
        r = cur.fetchone()
        result["total_match_history"] = int(r["cnt"] or 0)
    except Exception:
        result["total_match_history"] = "N/A"

    # ── 9. 유료 전환율 ────────────────────────────────────────
    try:
        total = result.get("users_total", 0)
        pro   = result.get("users_pro", 0)
        if isinstance(total, int) and isinstance(pro, int) and total > 0:
            result["pro_conversion_rate"] = round(pro / total * 100, 1)
        else:
            result["pro_conversion_rate"] = "N/A"
    except Exception:
        result["pro_conversion_rate"] = "N/A"

    return result
