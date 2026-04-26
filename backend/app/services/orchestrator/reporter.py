"""보고서 생성 + 발송 — Gemini 요약 → 이메일/카카오."""

import os
import json
import logging
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

OWNER_EMAIL = os.getenv("OWNER_EMAIL", "iloom50@gmail.com")


def generate_and_send_report(
    db_conn,
    metrics: Dict,
    alerts: list,
    quality: Dict,
    learning: Dict,
    actions: list,
    url_health: Dict = None,
) -> bool:
    """Gemini로 보고서 생성 후 이메일 발송. 반환: 발송 성공 여부."""

    # ── 1. Gemini로 보고서 생성 ──
    report_text = _generate_report_with_gemini(metrics, alerts, quality, learning, actions, url_health=url_health)
    if not report_text:
        report_text = _generate_fallback_report(metrics, alerts, quality, learning, actions, url_health=url_health)

    # ── 2. 이메일 발송 ──
    sent = _send_email_report(report_text)

    # ── 2-2. 카카오 발송 (사장님 나에게 보내기) ──
    try:
        kakao_ok = _send_kakao_report(db_conn, report_text)
        if kakao_ok:
            logger.info("[Reporter] Kakao report sent to owner")
    except Exception as e:
        logger.warning(f"[Reporter] Kakao send skipped: {e}")

    # ── 3. DB에 보고서 저장 ──
    try:
        cur = db_conn.cursor()
        cur.execute("""
            INSERT INTO system_logs (action, category, detail, result)
            VALUES ('coo_report', 'orchestrator', %s, %s)
        """, (report_text[:500], json.dumps({
            "metrics": {k: v for k, v in metrics.items() if not isinstance(v, dict)},
            "alerts_count": len(alerts),
            "quality_summary": quality.get("summary", ""),
            "actions": actions,
        }, ensure_ascii=False, default=str)))
        db_conn.commit()
    except Exception as e:
        logger.warning(f"[Reporter] DB save error: {e}")
        try:
            db_conn.rollback()
        except Exception:
            pass

    return sent


def _generate_report_with_gemini(
    metrics: Dict, alerts: list, quality: Dict, learning: Dict, actions: list,
    url_health: Dict = None,
) -> str:
    """Gemini로 자연어 보고서 생성."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return ""

    today = datetime.now().strftime("%Y-%m-%d")
    url_health = url_health or {}

    # URL 의심 기관 요약 (최대 5개)
    suspects = url_health.get("suspects", [])[:5]
    suspect_summary = [
        f"{s['source_name']}: {', '.join(s['reasons'])}" for s in suspects
    ]

    data_block = json.dumps({
        "date": today,
        "consults_today": metrics.get("total_consults_today", 0),
        "pro_sessions": metrics.get("pro_sessions_today", 0),
        "agents": metrics.get("agents", {}),
        "kb_total": metrics.get("kb_total", 0),
        "kb_new_today": metrics.get("kb_new_today", 0),
        "kb_unused_ratio": f"{metrics.get('kb_unused', 0)}/{metrics.get('kb_total', 1)}",
        "announcements_total": metrics.get("announcements_total", 0),
        "analysis_rate": f"{metrics.get('analysis_rate', 0)}%",
        "analysis_queue": metrics.get("analysis_queue", 0),
        "new_announcements": metrics.get("new_announcements_today", 0),
        "new_users": metrics.get("new_users_today", 0),
        "plan_distribution": metrics.get("plan_distribution", {}),
        "expired_ratio": f"{metrics.get('expired_ratio', 0)}%",
        "quality_scores": quality.get("agent_scores", {}),
        "quality_summary": quality.get("summary", ""),
        "low_quality_count": len(quality.get("low_quality_samples", [])),
        "learning_growth_7d": learning.get("kb_growth_7d", 0),
        "learning_lite_active": learning.get("lite_learning_active", False),
        "learning_embed_coverage": f"{learning.get('embedding_coverage', 0)*100:.0f}%",
        "alerts": [a[1] for a in alerts],
        "auto_actions": actions,
        "url_health": {
            "total_active": url_health.get("total_active", 0),
            "suspect_count": url_health.get("suspect_count", 0),
            "suspect_list": suspect_summary,
        },
    }, ensure_ascii=False, indent=2)

    prompt = f"""당신은 지원금AI(govmatch.kr) 서비스의 AI COO입니다.
아래 운영 데이터를 바탕으로 사장님에게 일일 보고서를 작성하세요.

[운영 데이터]
{data_block}

[보고서 형식]
📊 지원금AI 일일 보고 ({today})

■ 핵심 요약 (3줄)
■ AI 에이전트 성적표
■ 학습 파이프라인
■ 공고 분석 현황
■ 수집 URL 점검 (의심 기관 목록 포함, 없으면 생략)
■ 이상 감지 및 자동 조치
■ 사장님께 제안

한국어, 간결하고 핵심만. 이모지 적절히 사용. 500자 이내."""

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-2.5-flash",
                                       generation_config={"max_output_tokens": 1024, "temperature": 0.3})
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception as e:
        logger.warning(f"[Reporter] Gemini error: {e}")
        return ""


def _generate_fallback_report(
    metrics: Dict, alerts: list, quality: Dict, learning: Dict, actions: list,
    url_health: Dict = None,
) -> str:
    """Gemini 실패 시 단순 텍스트 보고서."""
    today = datetime.now().strftime("%Y-%m-%d")
    url_health = url_health or {}
    lines = [
        f"📊 지원금AI 일일 보고 ({today})",
        "",
        f"■ 상담: {metrics.get('total_consults_today', 0)}건 (PRO {metrics.get('pro_sessions_today', 0)}건)",
        f"■ 지식: {metrics.get('kb_total', 0)}건 (+{metrics.get('kb_new_today', 0)})",
        f"■ 공고 분석: {metrics.get('analysis_rate', 0)}% ({metrics.get('analysis_queue', 0)}건 대기)",
        f"■ 품질: {quality.get('summary', 'N/A')}",
        f"■ 신규 가입: {metrics.get('new_users_today', 0)}명",
    ]
    if alerts:
        lines.append("")
        lines.append("■ 이상 감지:")
        for sev, msg in alerts[:5]:
            icon = "🚨" if sev == "warning" else "ℹ️"
            lines.append(f"  {icon} {msg}")
    if actions:
        lines.append("")
        lines.append("■ 자동 조치:")
        for a in actions[:3]:
            lines.append(f"  ✅ {a}")
    suspects = url_health.get("suspects", [])
    if suspects:
        lines.append("")
        lines.append(f"■ 수집 URL 점검 ({url_health.get('suspect_count', 0)}개 의심):")
        for s in suspects[:5]:
            lines.append(f"  🔍 {s['source_name']}: {', '.join(s['reasons'])}")
    return "\n".join(lines)


def _send_email_report(report_text: str) -> bool:
    """SMTP로 보고서 이메일 전송."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_password:
        logger.info("[Reporter] SMTP 미설정 — 이메일 발송 건너뜀")
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[지원금AI COO] 일일 보고 {today}"
    msg["From"] = smtp_user
    msg["To"] = OWNER_EMAIL

    # 텍스트를 HTML로 변환 (줄바꿈 → <br>)
    html_body = f"""<html><body style="font-family: 'Apple SD Gothic Neo', sans-serif; padding: 20px; max-width: 600px;">
<pre style="white-space: pre-wrap; font-size: 14px; line-height: 1.6;">{report_text}</pre>
<hr style="margin-top: 20px; border: none; border-top: 1px solid #eee;">
<p style="color: #999; font-size: 11px;">이 보고서는 AI COO가 자동 생성했습니다. govmatch.kr</p>
</body></html>"""

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        logger.info(f"[Reporter] COO report sent to {OWNER_EMAIL}")
        return True
    except Exception as e:
        logger.error(f"[Reporter] Email send error: {e}")
        return False


def _send_kakao_report(db_conn, report_text: str) -> bool:
    """사장님 카카오 '나에게 보내기'로 보고서 요약 발송.

    - OWNER_EMAIL로 users에서 business_number + kakao_refresh_token 조회
    - 텍스트 템플릿(최대 200자) + 이메일 상세 안내 버튼
    """
    kakao_client_id = os.getenv("KAKAO_CLIENT_ID", "")
    if not kakao_client_id:
        return False

    # OWNER 계정의 refresh_token 찾기 (email 기준)
    try:
        cur = db_conn.cursor()
        cur.execute("""
            SELECT business_number, kakao_refresh_token
            FROM users
            WHERE email = %s AND kakao_refresh_token IS NOT NULL AND kakao_refresh_token != ''
            LIMIT 1
        """, (OWNER_EMAIL,))
        row = cur.fetchone()
        if not row or not row.get("kakao_refresh_token"):
            logger.info("[Reporter] OWNER kakao_refresh_token 없음 — 카카오 발송 건너뜀")
            return False
        refresh_token = row["kakao_refresh_token"]
        owner_bn = row["business_number"]
    except Exception as e:
        logger.warning(f"[Reporter] Owner lookup error: {e}")
        try: db_conn.rollback()
        except Exception: pass
        return False

    # 메시지 요약 (200자 제한 — text 템플릿은 description 200자)
    today = datetime.now().strftime("%m/%d")
    # 보고서에서 첫 5줄 또는 180자 추출
    summary_lines = report_text.split("\n")[:8]
    summary = "\n".join(summary_lines)[:180]

    kakao_client_secret = os.getenv("KAKAO_CLIENT_SECRET", "")
    app_url = os.getenv("FRONTEND_URL", "https://govmatch.kr")

    async def _do_send():
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. refresh_token → access_token
            token_res = await client.post("https://kauth.kakao.com/oauth/token", data={
                "grant_type": "refresh_token",
                "client_id": kakao_client_id,
                "client_secret": kakao_client_secret,
                "refresh_token": refresh_token,
            })
            token_data = token_res.json()
            access_token = token_data.get("access_token")
            if not access_token:
                logger.warning(f"[Reporter] Kakao token refresh 실패: {token_data}")
                return False

            # refresh_token 갱신 저장
            new_refresh = token_data.get("refresh_token")
            if new_refresh and owner_bn:
                try:
                    cur2 = db_conn.cursor()
                    cur2.execute("UPDATE users SET kakao_refresh_token = %s WHERE business_number = %s",
                                 (new_refresh, owner_bn))
                    db_conn.commit()
                except Exception:
                    try: db_conn.rollback()
                    except Exception: pass

            # 2. 나에게 보내기 (text 템플릿)
            msg_res = await client.post(
                "https://kapi.kakao.com/v2/api/talk/memo/default/send",
                headers={"Authorization": f"Bearer {access_token}"},
                data={"template_object": json.dumps({
                    "object_type": "text",
                    "text": f"[COO {today}]\n{summary}",
                    "link": {"web_url": app_url, "mobile_web_url": app_url},
                    "button_title": "전체 보고서 보기",
                }, ensure_ascii=False)},
            )
            result = msg_res.json()
            return result.get("result_code") == 0

    try:
        # sync 컨텍스트에서 async 호출
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 이미 event loop 안이면 새 loop 생성
                new_loop = asyncio.new_event_loop()
                try:
                    return new_loop.run_until_complete(_do_send())
                finally:
                    new_loop.close()
            return loop.run_until_complete(_do_send())
        except RuntimeError:
            return asyncio.run(_do_send())
    except Exception as e:
        logger.warning(f"[Reporter] Kakao send error: {e}")
        return False
