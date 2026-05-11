"""
reporter.py — GovMatch 일일 현황 보고서 생성 + 이메일/카카오 발송
"""
import json
import os
from datetime import datetime, timedelta


# ── 텍스트 보고서 ──────────────────────────────────────────────
def _build_report_text(metrics: dict, learning: dict) -> str:
    now   = datetime.now()
    today = now.strftime("%Y-%m-%d")
    yest  = (now - timedelta(days=1)).strftime("%m-%d")

    u_total = metrics.get("users_total", "N/A")
    u_pro   = metrics.get("users_pro",   "N/A")
    u_lite  = metrics.get("users_lite",  "N/A")
    u_new   = metrics.get("new_users_yesterday", "N/A")
    u_biz   = metrics.get("new_users_yesterday_business",   0)
    u_ind   = metrics.get("new_users_yesterday_individual", 0)
    conv_rt = metrics.get("pro_conversion_rate", "N/A")

    dau        = metrics.get("dau_yesterday", "N/A")
    ai_cnt     = metrics.get("ai_consults_yesterday", "N/A")
    pro_cnt    = metrics.get("pro_consults_yesterday", "N/A")
    match_cnt  = metrics.get("matching_yesterday", "N/A")

    total_consults = metrics.get("total_real_consults", "N/A")
    total_pro      = metrics.get("total_pro_sessions",  "N/A")
    total_match    = metrics.get("total_match_history", "N/A")

    kb_total = learning.get("total", "N/A")
    kb_today = learning.get("today_added", 0)

    # 주간 DAU 막대
    weekly = metrics.get("weekly_dau", [])
    weekly_lines = ""
    if weekly:
        max_dau = max((w["dau"] for w in weekly), default=1) or 1
        for w in weekly:
            bar = "■" * max(1, round(w["dau"] / max_dau * 10))
            weekly_lines += f"  {w['date'][5:]}  {bar} {w['dau']}명\n"
    else:
        weekly_lines = "  데이터 없음\n"

    return f"""[GovMatch 일일 현황] {today}
{'─' * 38}

▌ 회원 현황
  누적: {u_total}명 (lite {u_lite} / pro {u_pro})
  유료 전환율: {conv_rt}%
  어제({yest}) 신규: {u_new}명 (기업 {u_biz} / 개인 {u_ind})

▌ 어제({yest}) 활동
  로그인(DAU): {dau}명
  AI 상담: {ai_cnt}건  |  PRO 상담: {pro_cnt}건
  매칭 실행: {match_cnt}건

▌ 주간 DAU 추이
{weekly_lines}
▌ 누적 현황
  실질 상담: {total_consults}건
  PRO 세션: {total_pro}건
  매칭 이력: {total_match}건
  지식베이스: {kb_total}건 (오늘 +{kb_today})

{'─' * 38}
GovMatch | govmatch.kr"""


# ── HTML 보고서 ───────────────────────────────────────────────
def _build_report_html(metrics: dict, learning: dict) -> str:
    now   = datetime.now()
    today = now.strftime("%Y-%m-%d")
    yest  = (now - timedelta(days=1)).strftime("%m-%d")

    u_total = metrics.get("users_total", "N/A")
    u_pro   = metrics.get("users_pro",   "N/A")
    u_lite  = metrics.get("users_lite",  "N/A")
    u_new   = metrics.get("new_users_yesterday", "N/A")
    u_biz   = metrics.get("new_users_yesterday_business",   0)
    u_ind   = metrics.get("new_users_yesterday_individual", 0)
    conv_rt = metrics.get("pro_conversion_rate", "N/A")

    dau       = metrics.get("dau_yesterday", "N/A")
    ai_cnt    = metrics.get("ai_consults_yesterday", "N/A")
    pro_cnt   = metrics.get("pro_consults_yesterday", "N/A")
    match_cnt = metrics.get("matching_yesterday", "N/A")

    total_consults = metrics.get("total_real_consults", "N/A")
    total_pro      = metrics.get("total_pro_sessions",  "N/A")
    total_match    = metrics.get("total_match_history", "N/A")

    kb_total = learning.get("total", "N/A")
    kb_today = learning.get("today_added", 0)

    # 주간 DAU 막대 HTML
    weekly = metrics.get("weekly_dau", [])
    max_dau = max((w["dau"] for w in weekly), default=1) or 1
    weekly_html = ""
    for w in weekly:
        pct = max(4, round(w["dau"] / max_dau * 100))
        weekly_html += f"""
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:13px">
          <span style="width:36px;color:#6b7280">{w['date'][5:]}</span>
          <div style="flex:1;background:#e5e7eb;border-radius:4px;height:16px">
            <div style="background:#6d28d9;width:{pct}%;height:16px;border-radius:4px"></div>
          </div>
          <span style="width:28px;text-align:right">{w['dau']}</span>
        </div>"""
    if not weekly_html:
        weekly_html = '<p style="color:#9ca3af;font-size:13px">데이터 없음</p>'

    def stat_row(label, value):
        return f'<tr><td style="padding:5px 0;color:#6b7280;font-size:13px">{label}</td><td style="font-weight:bold;font-size:13px">{value}</td></tr>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;max-width:560px;margin:auto;padding:24px;color:#111">

  <h2 style="color:#6d28d9;margin-bottom:4px">GovMatch 일일 현황</h2>
  <p style="color:#6b7280;font-size:13px;margin-top:0">{today} 보고</p>
  <hr style="border-color:#e5e7eb">

  <h3 style="color:#111;font-size:15px">&#128101; 회원</h3>
  <table style="width:100%;border-collapse:collapse">
    {stat_row("누적 회원", f"{u_total}명")}
    {stat_row("&nbsp;&nbsp;├ lite", f"{u_lite}명")}
    {stat_row("&nbsp;&nbsp;└ pro", f'<span style="color:#6d28d9">{u_pro}명</span>')}
    {stat_row("유료 전환율", f'<span style="color:#6d28d9">{conv_rt}%</span>')}
    {stat_row(f"어제({yest}) 신규", f'{u_new}명 &nbsp;<span style="color:#6b7280;font-weight:normal;font-size:12px">(기업 {u_biz} / 개인 {u_ind})</span>')}
  </table>

  <h3 style="color:#111;font-size:15px;margin-top:20px">&#9889; 어제({yest}) 활동</h3>
  <table style="width:100%;border-collapse:collapse">
    {stat_row("로그인(DAU)", f"{dau}명")}
    {stat_row("AI 상담", f"{ai_cnt}건")}
    {stat_row("PRO 상담", f"{pro_cnt}건")}
    {stat_row("매칭 실행", f"{match_cnt}건")}
  </table>

  <h3 style="color:#111;font-size:15px;margin-top:20px">&#128200; 주간 DAU 추이</h3>
  {weekly_html}

  <h3 style="color:#111;font-size:15px;margin-top:20px">&#128202; 누적 현황</h3>
  <table style="width:100%;border-collapse:collapse">
    {stat_row("실질 AI 상담", f"{total_consults}건")}
    {stat_row("PRO 세션", f"{total_pro}건")}
    {stat_row("매칭 이력", f"{total_match}건")}
    {stat_row("지식베이스", f"{kb_total}건 <span style='color:#6b7280;font-weight:normal;font-size:12px'>(오늘 +{kb_today})</span>")}
  </table>

  <hr style="border-color:#e5e7eb;margin-top:24px">
  <p style="color:#9ca3af;font-size:12px">GovMatch | <a href="https://govmatch.kr" style="color:#9ca3af">govmatch.kr</a></p>
</body></html>"""


# ── 발송 ──────────────────────────────────────────────────────
def send_report(metrics: dict, learning: dict) -> dict:
    report_text = _build_report_text(metrics, learning)
    report_html = _build_report_html(metrics, learning)
    result = {"text": report_text, "email_sent": False, "kakao_sent": False}

    # ── 이메일 ──
    owner_email    = os.environ.get("OWNER_EMAIL") or os.environ.get("REPORT_EMAIL")
    resend_api_key = os.environ.get("RESEND_API_KEY")
    resend_from    = os.environ.get("RESEND_FROM", "info@govmatch.kr")

    if owner_email and resend_api_key:
        try:
            import requests
            today_str = datetime.now().strftime("%Y-%m-%d")
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": resend_from,
                    "to": [owner_email],
                    "subject": f"[GovMatch] 일일 현황 {today_str}",
                    "html": report_html,
                    "text": report_text,
                },
                timeout=15,
            )
            result["email_sent"] = resp.status_code in (200, 202)
            if result["email_sent"]:
                print(f"[reporter] 이메일 발송 완료 → {owner_email}")
            else:
                print(f"[reporter] 이메일 발송 실패: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            print(f"[reporter] 이메일 오류: {e}")
    else:
        print("[reporter] OWNER_EMAIL 또는 RESEND_API_KEY 미설정 — 이메일 스킵")

    # ── 카카오 ──
    kakao_client_id = os.environ.get("KAKAO_CLIENT_ID")
    if owner_email and kakao_client_id:
        try:
            import psycopg2, psycopg2.extras
            conn = psycopg2.connect(
                os.environ.get("DATABASE_URL", ""),
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
            cur = conn.cursor()
            cur.execute(
                "SELECT kakao_refresh_token FROM users WHERE email = %s",
                (owner_email,),
            )
            row = cur.fetchone()
            conn.close()

            if row and row.get("kakao_refresh_token"):
                import asyncio, httpx

                async def _send():
                    async with httpx.AsyncClient() as client:
                        token_res = await client.post(
                            "https://kauth.kakao.com/oauth/token",
                            data={
                                "grant_type": "refresh_token",
                                "client_id": kakao_client_id,
                                "client_secret": os.environ.get("KAKAO_CLIENT_SECRET", ""),
                                "refresh_token": row["kakao_refresh_token"],
                            },
                        )
                        access_token = token_res.json().get("access_token")
                        if not access_token:
                            return False

                        today_str  = datetime.now().strftime("%Y-%m-%d")
                        yest_short = (datetime.now() - timedelta(days=1)).strftime("%m-%d")
                        kakao_text = (
                            f"[GovMatch] {today_str}\n"
                            f"누적 회원 {metrics.get('users_total')}명 (PRO {metrics.get('users_pro')})\n"
                            f"어제({yest_short}) 신규 {metrics.get('new_users_yesterday')}명 | DAU {metrics.get('dau_yesterday')}명\n"
                            f"AI상담 {metrics.get('ai_consults_yesterday')}건 | 매칭 {metrics.get('matching_yesterday')}건\n"
                            f"govmatch.kr"
                        )
                        msg_res = await client.post(
                            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
                            headers={"Authorization": f"Bearer {access_token}"},
                            data={"template_object": json.dumps({
                                "object_type": "text",
                                "text": kakao_text,
                                "link": {
                                    "web_url": "https://govmatch.kr",
                                    "mobile_web_url": "https://govmatch.kr",
                                },
                            }, ensure_ascii=False)},
                        )
                        return msg_res.json().get("result_code") == 0

                loop = asyncio.new_event_loop()
                result["kakao_sent"] = loop.run_until_complete(_send())
                loop.close()
                if result["kakao_sent"]:
                    print("[reporter] 카카오 발송 완료")
        except Exception as e:
            print(f"[reporter] 카카오 오류: {e}")
    else:
        print("[reporter] OWNER_EMAIL 또는 KAKAO_CLIENT_ID 미설정 — 카카오 스킵")

    return result
