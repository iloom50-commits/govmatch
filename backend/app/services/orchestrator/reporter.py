"""
reporter.py — 일일 감시 보고서 생성 + 이메일/카카오 발송
"""
import json
import os
from datetime import datetime


def _build_report_text(metrics: dict, quality: dict, learning: dict) -> str:
    """사람이 읽기 좋은 텍스트 보고서 생성"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    avg = quality.get("avg_scores", {})
    avg_total = quality.get("avg_total", 0)
    low = quality.get("low_quality_count", 0)
    sample_n = quality.get("sample_count", 0)

    score_lines = "\n".join(
        f"  - {k}: {v}/10" for k, v in avg.items()
    ) if avg else "  - 평가 데이터 없음"

    kb_total = learning.get("total", 0)
    kb_today = learning.get("today_added", 0)
    consult_today = learning.get("consult_log_today", 0)
    no_emb = learning.get("no_embedding_count", 0)

    agent_lines = "\n".join(
        f"  - {agent}: {cnt}건"
        for agent, cnt in (learning.get("by_source_agent") or {}).items()
    ) or "  - 데이터 없음"

    # 품질 경고 판단
    quality_alert = ""
    if avg_total > 0 and avg_total < 30:
        quality_alert = "⚠️ 평균 품질 점수 낮음 — 프롬프트 개선 검토 필요\n"
    elif low > 2:
        quality_alert = f"⚠️ 저품질 상담 {low}건 감지됨\n"

    report = f"""📊 [GovMatch AI COO 일일 보고서]
날짜: {now} KST
{'─' * 40}

🤖 상담 품질 체크 ({sample_n}건 샘플)
{quality_alert}평균 점수: {avg_total}/50점
{score_lines}

📚 학습 현황
  - 지식베이스 총: {kb_total}건
  - 오늘 추가: {kb_today}건
  - 오늘 상담 로그: {consult_today}건
  - 임베딩 누락: {no_emb}건

🧠 에이전트별 지식 기여
{agent_lines}

📈 상담 통계
  - 총 상담 건수: {metrics.get('total_consults', 'N/A')}건
  - 오늘: {metrics.get('today_consults', 'N/A')}건
  - PRO 세션: {metrics.get('pro_sessions', 'N/A')}건

---
GovMatch AI COO | govmatch.kr"""

    return report


def _build_report_html(metrics: dict, quality: dict, learning: dict, report_text: str) -> str:
    avg = quality.get("avg_scores", {})
    avg_total = quality.get("avg_total", 0)
    low = quality.get("low_quality_count", 0)
    kb_total = learning.get("total", 0)
    kb_today = learning.get("today_added", 0)
    consult_today = learning.get("consult_log_today", 0)

    score_bars = ""
    for k, v in avg.items():
        pct = int(v * 10)
        color = "#22c55e" if v >= 7 else "#f59e0b" if v >= 5 else "#ef4444"
        score_bars += f"""
        <div style="margin-bottom:8px">
          <div style="display:flex;justify-content:space-between;font-size:13px">
            <span>{k}</span><span style="font-weight:bold">{v}/10</span>
          </div>
          <div style="background:#e5e7eb;border-radius:4px;height:8px;margin-top:4px">
            <div style="background:{color};width:{pct}%;height:8px;border-radius:4px"></div>
          </div>
        </div>"""

    alert_html = ""
    if low > 0 or (avg_total > 0 and avg_total < 30):
        alert_html = f'<div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;padding:12px;margin-bottom:16px">⚠️ 품질 점검 필요: 저품질 {low}건, 평균 {avg_total}/50점</div>'

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;max-width:600px;margin:auto;padding:24px;color:#111">
  <h2 style="color:#6d28d9">📊 GovMatch AI COO 일일 보고서</h2>
  <p style="color:#6b7280;font-size:13px">{now} KST</p>
  <hr style="border-color:#e5e7eb">

  {alert_html}

  <h3>🤖 상담 품질</h3>
  <p>평균: <strong>{avg_total}/50점</strong> ({quality.get('sample_count',0)}건 샘플)</p>
  {score_bars}

  <h3>📚 학습 현황</h3>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <tr><td style="padding:6px 0;color:#6b7280">지식베이스 총</td><td style="font-weight:bold">{kb_total}건</td></tr>
    <tr><td style="padding:6px 0;color:#6b7280">오늘 추가</td><td style="font-weight:bold">{kb_today}건</td></tr>
    <tr><td style="padding:6px 0;color:#6b7280">오늘 상담 로그</td><td style="font-weight:bold">{consult_today}건</td></tr>
    <tr><td style="padding:6px 0;color:#6b7280">임베딩 누락</td><td style="font-weight:bold">{learning.get('no_embedding_count',0)}건</td></tr>
  </table>

  <h3>📈 상담 통계</h3>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <tr><td style="padding:6px 0;color:#6b7280">총 상담</td><td style="font-weight:bold">{metrics.get('total_consults','N/A')}건</td></tr>
    <tr><td style="padding:6px 0;color:#6b7280">오늘 상담</td><td style="font-weight:bold">{metrics.get('today_consults','N/A')}건</td></tr>
    <tr><td style="padding:6px 0;color:#6b7280">PRO 세션</td><td style="font-weight:bold">{metrics.get('pro_sessions','N/A')}건</td></tr>
  </table>

  <hr style="border-color:#e5e7eb;margin-top:24px">
  <p style="color:#9ca3af;font-size:12px">GovMatch AI COO | <a href="https://govmatch.kr">govmatch.kr</a></p>
</body></html>"""


def send_report(metrics: dict, quality: dict, learning: dict) -> dict:
    """보고서 생성 후 이메일 + 카카오 발송"""
    report_text = _build_report_text(metrics, quality, learning)
    report_html = _build_report_html(metrics, quality, learning, report_text)
    result = {"text": report_text, "email_sent": False, "kakao_sent": False}

    # ── 이메일 발송 ──
    owner_email = os.environ.get("OWNER_EMAIL") or os.environ.get("REPORT_EMAIL")
    resend_api_key = os.environ.get("RESEND_API_KEY")
    resend_from = os.environ.get("RESEND_FROM", "noreply@govmatch.kr")

    if owner_email and resend_api_key:
        try:
            import requests
            now_str = datetime.now().strftime("%Y-%m-%d")
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": resend_from,
                    "to": [owner_email],
                    "subject": f"[AI COO] GovMatch 일일 보고서 {now_str}",
                    "html": report_html,
                },
                timeout=15,
            )
            result["email_sent"] = resp.status_code in (200, 202)
            if result["email_sent"]:
                print(f"[Orchestrator/reporter] 이메일 발송 완료 → {owner_email}")
            else:
                print(f"[Orchestrator/reporter] 이메일 발송 실패: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            print(f"[Orchestrator/reporter] 이메일 오류: {e}")
    else:
        print("[Orchestrator/reporter] OWNER_EMAIL 또는 RESEND_API_KEY 미설정 — 이메일 스킵")

    # ── 카카오 발송 (사장님 계정) ──
    owner_email = os.environ.get("OWNER_EMAIL") or os.environ.get("REPORT_EMAIL")
    kakao_client_id = os.environ.get("KAKAO_CLIENT_ID")

    if owner_email and kakao_client_id:
        try:
            import asyncio
            import psycopg2
            import psycopg2.extras

            DATABASE_URL = os.environ.get("DATABASE_URL", "")
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            cur.execute("SELECT kakao_refresh_token FROM users WHERE email = %s", (owner_email,))
            row = cur.fetchone()
            conn.close()

            if row and row.get("kakao_refresh_token"):
                async def _send_kakao():
                    import httpx
                    async with httpx.AsyncClient() as client:
                        token_res = await client.post("https://kauth.kakao.com/oauth/token", data={
                            "grant_type": "refresh_token",
                            "client_id": kakao_client_id,
                            "client_secret": os.environ.get("KAKAO_CLIENT_SECRET", ""),
                            "refresh_token": row["kakao_refresh_token"],
                        })
                        access_token = token_res.json().get("access_token")
                        if not access_token:
                            return False

                        now_str = datetime.now().strftime("%Y-%m-%d")
                        avg_total = quality.get("avg_total", 0)
                        kb_today = learning.get("today_added", 0)
                        consult_today = learning.get("consult_log_today", 0)
                        kakao_text = (
                            f"[AI COO] {now_str} 보고\n"
                            f"품질: {avg_total}/50점\n"
                            f"오늘 상담: {consult_today}건\n"
                            f"신규 지식: {kb_today}건\n"
                            f"govmatch.kr"
                        )

                        msg_res = await client.post(
                            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
                            headers={"Authorization": f"Bearer {access_token}"},
                            data={"template_object": json.dumps({
                                "object_type": "text",
                                "text": kakao_text,
                                "link": {"web_url": "https://govmatch.kr", "mobile_web_url": "https://govmatch.kr"},
                            }, ensure_ascii=False)},
                        )
                        return msg_res.json().get("result_code") == 0

                try:
                    loop = asyncio.new_event_loop()
                    result["kakao_sent"] = loop.run_until_complete(_send_kakao())
                    loop.close()
                    if result["kakao_sent"]:
                        print("[Orchestrator/reporter] 카카오 발송 완료")
                except Exception as e:
                    print(f"[Orchestrator/reporter] 카카오 오류: {e}")
        except Exception as e:
            print(f"[Orchestrator/reporter] 카카오 DB 조회 오류: {e}")
    else:
        print("[Orchestrator/reporter] OWNER_EMAIL 또는 KAKAO_CLIENT_ID 미설정 — 카카오 스킵")

    return result
