"""
reporter.py — GovMatch 일일 현황 보고서 생성 + 이메일/카카오 발송
"""
import json
import os
from datetime import datetime, timedelta


# ── 텍스트 보고서 ──────────────────────────────────────────────
def _build_seo_text(seo: dict) -> str:
    if not seo or seo.get("skipped") or seo.get("error"):
        return "  데이터 없음\n"
    t = seo.get("total", {})
    lines = (
        f"  클릭: {t.get('clicks',0)}회  |  노출: {t.get('impressions',0)}회\n"
        f"  CTR: {t.get('ctr',0)}%  |  평균순위: {t.get('position',0)}위\n"
    )
    queries = seo.get("top_queries", [])[:3]
    if queries:
        lines += "  상위 검색어:\n"
        for q in queries:
            lines += f"    · {q['query']} ({q['clicks']}클릭, {q['position']}위)\n"
    opps = seo.get("opportunities", [])
    if opps:
        lines += f"  CTR 개선 기회: {len(opps)}개 페이지\n"
    suggestions = seo.get("ai_suggestions", "")
    if suggestions:
        lines += "  AI 개선 제안:\n"
        for line in suggestions.split("\n")[:4]:
            if line.strip():
                lines += f"    {line.strip()}\n"
    return lines


def _build_alert_text(health: dict) -> str:
    """🚦 시스템 경보 (텍스트). health 없으면 빈 문자열."""
    if not health:
        return ""
    alerts = health.get("alerts", [])
    lines = "▌ 🚦 시스템 경보\n"
    if alerts:
        for a in alerts:
            lines += f"  {a}\n"
    else:
        lines += "  ✅ 이상 없음 (파이프라인·수집·재분석·API 정상)\n"
    pl = health.get("pipeline", {}) or {}
    co = health.get("collection", {}) or {}
    ra = health.get("reanalyze", {}) or {}
    api = health.get("api", {}) or {}
    lines += (
        f"  · 파이프라인 {pl.get('age_days','?')}일전 | "
        f"공고 {co.get('age_days','?')}일전(어제 +{co.get('new_1d','?')}) | "
        f"재분석 {ra.get('age_days','?')}일전(백로그 {ra.get('backlog','?')})\n"
    )
    admin = health.get("admin_scraper", {}) or {}
    dig = health.get("digest", {}) or {}
    bl = health.get("analysis_backlog", {}) or {}
    lines += (
        f"  · 기관수집 {admin.get('age_days','?')}일전 | "
        f"이메일 {dig.get('age_days','?')}일전 | 분석실패 {bl.get('real_fail', bl.get('open','?'))}\n"
    )
    if api:
        parts = []
        for k in ("Gemini", "OpenAI"):
            if k in api:
                v = api[k]
                parts.append(f"{k}={'정상' if v is True else '이상' if v is False else '미설정'}")
        if parts:
            lines += "  · API: " + "  ".join(parts) + "\n"
    return lines


def _build_sales_text(health: dict) -> str:
    """💰 매출/전환 (텍스트)."""
    s = (health or {}).get("sales", {}) or {}
    if not s or s.get("error"):
        return ""
    return (
        "▌ 💰 매출/전환\n"
        f"  유료 PRO(결제): {s.get('pro_paying',0)}명  |  프로모·체험 PRO: {s.get('pro_promo_trial',0)}명\n"
        f"  어제 신규 PRO 전환: {s.get('new_pro_yesterday',0)}명  |  전환율: {s.get('conversion_rate',0)}%\n"
    )


def _build_dq_text(health: dict) -> str:
    """📊 데이터 품질 (텍스트) — 오분류·마감 파싱 추이 실측(근본개선 검증용)."""
    d = (health or {}).get("data_quality", {}) or {}
    if not d or d.get("error"):
        return ""
    ni = d.get("new_intake") or {}
    intake_line = ""
    if ni.get("n_new"):
        intake_line = (
            f"  신규 마감 확보율: {ni.get('capture_rate')}% "
            f"(날짜 {ni.get('n_date',0)} + 상시 {ni.get('n_ongoing',0)} / 신규 {ni.get('n_new',0)}) "
            f"| 원문만 {ni.get('n_raw_only',0)} | 부재 {ni.get('n_absent',0)}\n"
        )
    l2 = d.get("l2_audit") or {}
    l2_line = ""
    if l2.get("conclusive"):
        l2_line = (
            f"  L2 표본감사 오분류율: {l2.get('mismatch_rate')}% "
            f"({l2.get('mismatch',0)}/{l2.get('conclusive',0)} 표본, 무출처 Gemini 재판정)\n"
        )
    return (
        "▌ 📊 데이터 품질 (근본개선 추적)\n"
        f"  개인탭 오분류 의심: {d.get('misclass_suspect',0)}건 (individual인데 사업자 제목)\n"
        f"  both 잔존: {d.get('both_count',0)}건  |  미분류(NULL): {d.get('unclassified',0)}건\n"
        f"  마감일 미상(NULL): {d.get('null_deadline',0)}건 ({d.get('null_deadline_rate',0)}%)\n"
        + intake_line
        + l2_line
    )


def _build_report_text(metrics: dict, learning: dict, quality: dict, seo: dict = None, health: dict = None) -> str:
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

    # 에이전트 품질
    quality_lines = ""
    agents = quality.get("agents", {})
    if agents:
        for key, info in agents.items():
            score = info.get("avg_score")
            status = info.get("status", "no_data")
            flag = "⚠️" if status == "warning" else ("✅" if score is not None else "–")
            score_str = f"{score}점" if score is not None else "데이터 없음"
            quality_lines += f"  {flag} {info['label']}: {score_str}\n"
        low = quality.get("total_low_quality", 0)
        if low:
            quality_lines += f"  ⚠️ 점검 필요 {low}건\n"
            # 이슈 목록
            for info in agents.values():
                for iss in info.get("issues", []):
                    quality_lines += f"    · {iss}\n"
    else:
        quality_lines = "  데이터 없음\n"

    seo_lines = _build_seo_text(seo or {})
    alert_block = _build_alert_text(health)
    sales_block = _build_sales_text(health)
    dq_block = _build_dq_text(health)

    return f"""[GovMatch 일일 현황] {today}
{'─' * 38}

{alert_block}
▌ 구글 검색 유입
{seo_lines}
▌ 회원 현황
  누적: {u_total}명 (lite {u_lite} / pro {u_pro})
  유료 전환율: {conv_rt}%
  어제({yest}) 신규: {u_new}명 (기업 {u_biz} / 개인 {u_ind})

{sales_block}
{dq_block}
▌ 어제({yest}) 활동
  로그인(DAU): {dau}명
  AI 상담: {ai_cnt}건  |  PRO 상담: {pro_cnt}건
  매칭 실행: {match_cnt}건

▌ 주간 DAU 추이
{weekly_lines}
▌ 에이전트 역할 점검
{quality_lines}
▌ 누적 현황
  실질 상담: {total_consults}건
  PRO 세션: {total_pro}건
  매칭 이력: {total_match}건
  지식베이스: {kb_total}건 (오늘 +{kb_today})

{'─' * 38}
GovMatch | govmatch.kr"""


# ── HTML 보고서 ───────────────────────────────────────────────
def _build_alert_html(health: dict) -> str:
    """🚦 시스템 경보 박스 (HTML). 경보 있으면 빨강, 없으면 초록."""
    if not health:
        return ""
    alerts = health.get("alerts", [])
    if alerts:
        items = "".join(f'<li style="margin-bottom:4px">{a}</li>' for a in alerts)
        box = (
            '<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px 16px;margin:12px 0">'
            f'<div style="font-weight:bold;color:#dc2626;font-size:15px;margin-bottom:6px">&#128678; 시스템 경보 {len(alerts)}건</div>'
            f'<ul style="margin:0;padding-left:18px;color:#b91c1c;font-size:13px">{items}</ul></div>'
        )
    else:
        box = (
            '<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px 16px;margin:12px 0">'
            '<span style="font-weight:bold;color:#16a34a;font-size:14px">&#9989; 시스템 정상</span> '
            '<span style="color:#15803d;font-size:13px">— 파이프라인·수집·재분석·API 이상 없음</span></div>'
        )
    pl = health.get("pipeline", {}) or {}
    co = health.get("collection", {}) or {}
    ra = health.get("reanalyze", {}) or {}
    api = health.get("api", {}) or {}
    api_str = "  ".join(
        f"{k} {'✅' if api.get(k) is True else '🚨' if api.get(k) is False else '–'}"
        for k in ("Gemini", "OpenAI") if k in api
    )
    admin = health.get("admin_scraper", {}) or {}
    dig = health.get("digest", {}) or {}
    bl = health.get("analysis_backlog", {}) or {}
    box += (
        '<p style="color:#6b7280;font-size:12px;margin:4px 0 0">'
        f'파이프라인 {pl.get("age_days","?")}일전 · 공고 {co.get("age_days","?")}일전(+{co.get("new_1d","?")}) · '
        f'재분석 {ra.get("age_days","?")}일전(백로그 {ra.get("backlog","?")})'
        f'{" · " + api_str if api_str else ""}</p>'
        '<p style="color:#6b7280;font-size:12px;margin:2px 0 0">'
        f'기관수집 {admin.get("age_days","?")}일전 · 이메일 {dig.get("age_days","?")}일전 · '
        f'분석실패 {bl.get("real_fail", bl.get("open","?"))}</p>'
    )
    return box


def _build_report_html(metrics: dict, learning: dict, quality: dict, seo: dict = None, health: dict = None) -> str:
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

    # 에이전트 품질 HTML
    agents = quality.get("agents", {})
    quality_html = ""
    if agents:
        for key, info in agents.items():
            score = info.get("avg_score")
            status = info.get("status", "no_data")
            flag = "⚠️" if status == "warning" else ("✅" if score is not None else "–")
            score_str = f"{score}점" if score is not None else "–"
            color = "#dc2626" if status == "warning" else "#16a34a" if score is not None else "#6b7280"
            quality_html += f"""
            <tr>
              <td style="padding:5px 0;font-size:13px">{flag} {info['label']}</td>
              <td style="font-weight:bold;font-size:13px;color:{color}">{score_str}</td>
            </tr>"""
        for info in agents.values():
            for iss in info.get("issues", []):
                quality_html += f"""
            <tr>
              <td colspan="2" style="padding:2px 0 2px 16px;font-size:12px;color:#dc2626">· {iss}</td>
            </tr>"""
    else:
        quality_html = '<tr><td colspan="2" style="color:#9ca3af;font-size:13px">데이터 없음</td></tr>'

    def stat_row(label, value):
        return f'<tr><td style="padding:5px 0;color:#6b7280;font-size:13px">{label}</td><td style="font-weight:bold;font-size:13px">{value}</td></tr>'

    # 🚦 경보 + 💰 매출 HTML
    alert_html = _build_alert_html(health)
    _s = (health or {}).get("sales", {}) or {}
    sales_html = ""
    if _s and not _s.get("error"):
        sales_html = (
            '<h3 style="color:#111;font-size:15px;margin-top:20px">&#128176; 매출/전환</h3>'
            '<table style="width:100%;border-collapse:collapse">'
            + stat_row("유료 PRO (결제)", f'<span style="color:#6d28d9">{_s.get("pro_paying",0)}명</span>')
            + stat_row("프로모·체험 PRO", f'{_s.get("pro_promo_trial",0)}명')
            + stat_row("어제 신규 PRO 전환", f'<span style="color:#6d28d9">{_s.get("new_pro_yesterday",0)}명</span>')
            + stat_row("유료 전환율", f'{_s.get("conversion_rate",0)}%')
            + '</table>'
        )

    _dq = (health or {}).get("data_quality", {}) or {}
    dq_html = ""
    if _dq and not _dq.get("error"):
        _ni = _dq.get("new_intake") or {}
        _intake_row = ""
        if _ni.get("n_new"):
            _intake_row = stat_row(
                "신규 마감 확보율",
                f'<span style="color:#6d28d9">{_ni.get("capture_rate")}%</span> '
                f'<span style="color:#6b7280;font-weight:normal;font-size:12px">'
                f'(날짜 {_ni.get("n_date",0)}+상시 {_ni.get("n_ongoing",0)}/신규 {_ni.get("n_new",0)} '
                f'| 원문만 {_ni.get("n_raw_only",0)} | 부재 {_ni.get("n_absent",0)})</span>')
        _l2 = _dq.get("l2_audit") or {}
        _l2_row = ""
        if _l2.get("conclusive"):
            _l2_row = stat_row(
                "L2 표본감사 오분류율",
                f'<span style="color:#6d28d9">{_l2.get("mismatch_rate")}%</span> '
                f'<span style="color:#6b7280;font-weight:normal;font-size:12px">'
                f'({_l2.get("mismatch",0)}/{_l2.get("conclusive",0)} 표본, 무출처 Gemini 재판정)</span>')
        dq_html = (
            '<h3 style="color:#111;font-size:15px;margin-top:20px">&#128202; 데이터 품질 (근본개선 추적)</h3>'
            '<table style="width:100%;border-collapse:collapse">'
            + stat_row("개인탭 오분류 의심", f'{_dq.get("misclass_suspect",0)}건')
            + stat_row("both 잔존", f'{_dq.get("both_count",0)}건')
            + stat_row("미분류(NULL)", f'{_dq.get("unclassified",0)}건')
            + stat_row("마감일 미상(NULL)", f'{_dq.get("null_deadline",0)}건 ({_dq.get("null_deadline_rate",0)}%)')
            + _intake_row
            + _l2_row
            + '</table>'
        )

    # SEO HTML 섹션
    seo = seo or {}
    seo_t = seo.get("total", {})
    seo_html = ""
    if seo and not seo.get("skipped") and not seo.get("error"):
        queries_html = "".join(
            f'<tr><td style="padding:4px 0;font-size:13px">{q["query"]}</td>'
            f'<td style="font-size:13px">{q["clicks"]}클릭</td>'
            f'<td style="font-size:13px;color:#6b7280">{q["position"]}위</td></tr>'
            for q in seo.get("top_queries", [])[:3]
        )
        suggestions_html = ""
        for line in (seo.get("ai_suggestions") or "").split("\n")[:4]:
            if line.strip():
                suggestions_html += f'<li style="font-size:12px;margin-bottom:4px">{line.strip()}</li>'

        seo_html = f"""
  <h3 style="color:#111;font-size:15px;margin-top:20px">&#128269; 구글 검색 유입</h3>
  <table style="width:100%;border-collapse:collapse">
    {stat_row("클릭수", f"{seo_t.get('clicks',0)}회")}
    {stat_row("노출수", f"{seo_t.get('impressions',0)}회")}
    {stat_row("CTR", f'<span style="color:#6d28d9">{seo_t.get("ctr",0)}%</span>')}
    {stat_row("평균순위", f"{seo_t.get('position',0)}위")}
  </table>
  <p style="font-size:13px;font-weight:bold;margin:12px 0 4px">상위 검색어</p>
  <table style="width:100%;border-collapse:collapse">{queries_html}</table>
  {"<p style='font-size:13px;font-weight:bold;margin:12px 0 4px'>AI 개선 제안</p><ul style='margin:0;padding-left:16px'>" + suggestions_html + "</ul>" if suggestions_html else ""}"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;max-width:560px;margin:auto;padding:24px;color:#111">

  <h2 style="color:#6d28d9;margin-bottom:4px">GovMatch 일일 현황</h2>
  <p style="color:#6b7280;font-size:13px;margin-top:0">{today} 보고</p>
  <hr style="border-color:#e5e7eb">
  {alert_html}
  {seo_html}

  <h3 style="color:#111;font-size:15px">&#128101; 회원</h3>
  <table style="width:100%;border-collapse:collapse">
    {stat_row("누적 회원", f"{u_total}명")}
    {stat_row("&nbsp;&nbsp;├ lite", f"{u_lite}명")}
    {stat_row("&nbsp;&nbsp;└ pro", f'<span style="color:#6d28d9">{u_pro}명</span>')}
    {stat_row("유료 전환율", f'<span style="color:#6d28d9">{conv_rt}%</span>')}
    {stat_row(f"어제({yest}) 신규", f'{u_new}명 &nbsp;<span style="color:#6b7280;font-weight:normal;font-size:12px">(기업 {u_biz} / 개인 {u_ind})</span>')}
  </table>
  {sales_html}
  {dq_html}

  <h3 style="color:#111;font-size:15px;margin-top:20px">&#9889; 어제({yest}) 활동</h3>
  <table style="width:100%;border-collapse:collapse">
    {stat_row("로그인(DAU)", f"{dau}명")}
    {stat_row("AI 상담", f"{ai_cnt}건")}
    {stat_row("PRO 상담", f"{pro_cnt}건")}
    {stat_row("매칭 실행", f"{match_cnt}건")}
  </table>

  <h3 style="color:#111;font-size:15px;margin-top:20px">&#128200; 주간 DAU 추이</h3>
  {weekly_html}

  <h3 style="color:#111;font-size:15px;margin-top:20px">&#129302; 에이전트 역할 점검</h3>
  <table style="width:100%;border-collapse:collapse">
    {quality_html}
  </table>

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


# ── 카카오 발송 (동기 requests 버전) ──────────────────────────
def _send_kakao(metrics: dict) -> bool:
    """카카오 나에게 보내기 — 동기 requests 사용 (asyncio 충돌 방지)."""
    import requests as _req
    import psycopg2, psycopg2.extras

    kakao_client_id     = os.environ.get("KAKAO_CLIENT_ID", "")
    kakao_client_secret = os.environ.get("KAKAO_CLIENT_SECRET", "")
    owner_email         = os.environ.get("OWNER_EMAIL") or os.environ.get("REPORT_EMAIL")
    db_url              = os.environ.get("DATABASE_URL", "")

    if not kakao_client_id or not owner_email or not db_url:
        print("[reporter] 카카오 필수 환경변수 미설정 (KAKAO_CLIENT_ID/OWNER_EMAIL) — 스킵")
        return False

    # refresh_token 조회 — email 또는 kakao_id 기준
    try:
        conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            "SELECT business_number, kakao_refresh_token FROM users WHERE email = %s",
            (owner_email,),
        )
        row = cur.fetchone()
        conn.close()
    except Exception as e:
        print(f"[reporter] 카카오 DB 조회 오류: {e}")
        return False

    if not row or not row.get("kakao_refresh_token"):
        print(f"[reporter] 카카오 refresh_token 없음 (email={owner_email})")
        return False

    refresh_token = row["kakao_refresh_token"]
    bn = row.get("business_number")

    # 1. refresh_token → access_token
    try:
        token_res = _req.post(
            "https://kauth.kakao.com/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": kakao_client_id,
                "client_secret": kakao_client_secret,
                "refresh_token": refresh_token,
            },
            timeout=10,
        )
        token_data = token_res.json()
        access_token = token_data.get("access_token")
        if not access_token:
            print(f"[reporter] 카카오 access_token 발급 실패: {token_data}")
            return False

        # refresh_token 갱신 시 DB 업데이트
        new_refresh = token_data.get("refresh_token")
        if new_refresh and bn:
            try:
                conn2 = psycopg2.connect(db_url)
                cur2 = conn2.cursor()
                cur2.execute(
                    "UPDATE users SET kakao_refresh_token = %s WHERE business_number = %s",
                    (new_refresh, bn),
                )
                conn2.commit()
                conn2.close()
            except Exception as upd_err:
                print(f"[reporter] refresh_token 갱신 저장 실패: {upd_err}")
    except Exception as e:
        print(f"[reporter] 카카오 토큰 갱신 오류: {e}")
        return False

    # 2. 나에게 보내기
    now = datetime.now()
    yest = (now - timedelta(days=1)).strftime("%m-%d")
    kakao_text = (
        f"[GovMatch] {now.strftime('%Y-%m-%d')}\n"
        f"누적 회원 {metrics.get('users_total')}명 (PRO {metrics.get('users_pro')})\n"
        f"어제({yest}) 신규 {metrics.get('new_users_yesterday')}명 | DAU {metrics.get('dau_yesterday')}명\n"
        f"AI상담 {metrics.get('ai_consults_yesterday')}건 | 매칭 {metrics.get('matching_yesterday')}건\n"
        f"govmatch.kr"
    )
    try:
        msg_res = _req.post(
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
            timeout=10,
        )
        result = msg_res.json()
        success = result.get("result_code") == 0
        if success:
            print("[reporter] 카카오 발송 완료")
        else:
            print(f"[reporter] 카카오 발송 실패: {result}")
        return success
    except Exception as e:
        print(f"[reporter] 카카오 메시지 전송 오류: {e}")
        return False


# ── 발송 ──────────────────────────────────────────────────────
def send_report(metrics: dict, learning: dict, quality: dict = None, seo: dict = None, health: dict = None) -> dict:
    if quality is None:
        quality = {}
    if seo is None:
        seo = {}
    if health is None:
        health = {}
    report_text = _build_report_text(metrics, learning, quality, seo, health)
    report_html = _build_report_html(metrics, learning, quality, seo, health)
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

    # ── 카카오 (동기 방식으로 교체) ──
    result["kakao_sent"] = _send_kakao(metrics)

    return result
