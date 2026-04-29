#!/usr/bin/env python
"""
PRO 상담 품질 평가 - 까칠한 사용자 페르소나 x Gemini 자동 채점 -> HTML 보고서

5가지 까칠한 페르소나:
  P1. 정보거부형   -- 아무것도 안 알려주고 "그냥 알아서 해줘"
  P2. 모호질문형   -- 초고수준 모호 질문 + 이해 안 됐다고 짜증
  P3. 전문가딴죽형 -- 중소벤처부 정책 전문가라며 AI 답변에 딴죽 걸기
  P4. 불가능조건형 -- 어제 창업, 매출 0, 신용불량인데 100억 지원 요구
  P5. 연속질문형   -- 5번 연속 질문하며 점점 구체화, 최후에 "이게 최선이야?"

실행:
  cd backend
  python test_pro_quality.py --email PRO계정 --password 비밀번호

출력:
  test_pro_quality_report_YYYYMMDD_HHMM.html
  test_pro_quality_raw_YYYYMMDD_HHMM.json
"""
import os, sys, json, time, datetime, argparse, re
sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# -----------------------------------------------------------------
# 5개 까칠한 페르소나
# -----------------------------------------------------------------
PERSONAS = [
    {
        "id": "P1",
        "name": "정보거부형 김갑순",
        "desc": "개인정보 노출 극도로 꺼림. 업종도 나이도 지역도 안 알려줌. 그냥 알아서 해줘.",
        "type": "개인",
        "profile": {
            "client_name": "김갑순", "client_type": "individual",
            "address_city": None, "interests": None, "memo": None,
        },
        "action": "match", "mode": None,
        "turns": [
            "그냥 나한테 맞는 지원금 알려줘.",
            "그런 건 왜 알아야 돼? 그냥 다 알려줘.",
            "복잡하게 설명하지 말고 한 줄로만 답해.",
        ],
    },
    {
        "id": "P2",
        "name": "모호질문형 박애매",
        "desc": "매우 모호한 질문 + 답변 이해 못 했다고 짜증내며 재질문.",
        "type": "기업",
        "profile": {
            "client_name": "박애매상사", "client_type": "business",
            "industry_name": "제조업", "address_city": "인천광역시",
            "revenue_bracket": "10억~50억", "employee_count_bracket": "10~29명",
            "interests": "자금조달", "memo": None,
        },
        "action": "fund_consult", "mode": "business_fund",
        "turns": [
            "돈 필요해요.",
            "그게 무슨 말이에요? 더 쉽게 설명해줘요.",
            "그래서 얼마나 받을 수 있다는 거예요? 숫자로만 답해요.",
        ],
    },
    {
        "id": "P3",
        "name": "전문가딴죽형 최까칠",
        "desc": "중소벤처부 정책연구원 출신이라며 AI 답변 세부 조항에 딴죽.",
        "type": "기업",
        "profile": {
            "client_name": "딴죽기술(주)", "client_type": "business",
            "establishment_date": "2019-03-15",
            "industry_name": "소프트웨어개발", "address_city": "서울특별시",
            "revenue_bracket": "5억~10억", "employee_count_bracket": "5~9명",
            "interests": "R&D, 기술개발, 수출", "memo": "정책연구원 출신 대표",
        },
        "action": "match", "mode": None,
        "turns": [
            "중소기업 R&D 지원사업 최신 현황 알려주세요.",
            "방금 말한 그 사업 지원 한도 틀렸어요. 중기부 고시 기준으로는 다르게 나와 있는데요?",
            "그러면 실제 신청에서 가장 많이 탈락하는 이유가 뭔지 설명해봐요.",
        ],
    },
    {
        "id": "P4",
        "name": "불가능조건형 이억울",
        "desc": "어제 창업, 매출 0, 신용불량인데 100억 이상 지원 요구.",
        "type": "기업",
        "profile": {
            "client_name": "이억울창업", "client_type": "business",
            "establishment_date": str(datetime.date.today()),
            "industry_name": "AI플랫폼", "address_city": "부산광역시",
            "revenue_bracket": "없음(0)", "employee_count_bracket": "1명(대표만)",
            "interests": "대규모 투자유치, 정부지원",
            "memo": "신용불량, 창업 1일차",
        },
        "action": "match", "mode": None,
        "turns": [
            "어제 창업했는데 100억 지원받을 수 있는 사업 알려주세요.",
            "왜 없어요? 정부가 스타트업 지원 안 한다는 거예요?",
            "그러면 지금 당장 받을 수 있는 거 중에 제일 금액 큰 게 뭐예요?",
        ],
    },
    {
        "id": "P5",
        "name": "연속질문형 정집요",
        "desc": "5번 연속 점점 구체화하는 질문, 마지막에 이게 최선이야?로 압박.",
        "type": "개인",
        "profile": {
            "client_name": "정집요", "client_type": "individual",
            "address_city": "경기도", "interests": "취업, 청년, 주거, 교육",
            "memo": "고졸, 취준 2년차, 경기도 거주",
        },
        "action": "match", "mode": None,
        "turns": [
            "청년 지원금 알려주세요.",
            "경기도 거주 고졸 취준생인데 받을 수 있는 것만요.",
            "그 중에서 신청 기간이 아직 안 지난 것만 필터해주세요.",
            "각 사업별로 얼마씩 받을 수 있는지 표로 정리해줘요.",
            "이게 정말 최선이에요? 더 좋은 사업 없어요?",
        ],
    },
]


# -----------------------------------------------------------------
# DB / API
# -----------------------------------------------------------------
def get_db_conn():
    import psycopg2
    from app.config import DATABASE_URL
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def login_get_user(email, password, conn):
    import bcrypt
    cur = conn.cursor()
    cur.execute("SELECT user_id, business_number, email, password_hash, plan FROM users WHERE email=%s", (email,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"사용자 없음: {email}")
    uid, bn, em, pw_hash, plan = row
    if pw_hash and not bcrypt.checkpw(password.encode(), pw_hash.encode()):
        raise ValueError("비밀번호 오류")
    return {"user_id": uid, "bn": bn, "email": em, "plan": plan}


def create_client(profile, expert_bn, conn):
    cur = conn.cursor()
    p = profile
    cur.execute(
        """INSERT INTO client_profiles
           (owner_business_number, client_name, client_type, establishment_date,
            industry_code, industry_name, revenue_bracket, employee_count_bracket,
            address_city, interests, memo, status, is_active)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'new',TRUE) RETURNING id""",
        (expert_bn, p["client_name"], p["client_type"], p.get("establishment_date"),
         p.get("industry_code"), p.get("industry_name"), p.get("revenue_bracket"),
         p.get("employee_count_bracket"), p.get("address_city"),
         p.get("interests"), p.get("memo", ""))
    )
    cid = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return cid


def delete_client(cid, conn):
    cur = conn.cursor()
    cur.execute("DELETE FROM client_profiles WHERE id=%s", (cid,))
    conn.commit()
    cur.close()


def call_pro(messages, action, mode, client_id, expert_user):
    from app.main import AiConsultantChatRequest, _api_pro_consultant_chat_impl
    req = AiConsultantChatRequest(
        messages=messages, action=action, mode=mode,
        client_id=client_id, session_id=None,
        announcement_id=None, is_announcement_start=False,
    )
    cu = {k: expert_user[k] for k in ("user_id", "bn", "email", "plan")}
    try:
        return _api_pro_consultant_chat_impl(req, cu)
    except Exception as e:
        return {"reply": f"[오류] {str(e)[:300]}", "choices": [], "matched_announcements": []}


# -----------------------------------------------------------------
# Gemini 자동 채점
# -----------------------------------------------------------------
def _get_gemini_model():
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    genai.configure(api_key=api_key)
    try:
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                return genai.GenerativeModel(m.name)
    except Exception:
        pass
    try:
        return genai.GenerativeModel("gemini-pro")
    except Exception:
        return None


SCORE_PROMPT = (
    "너는 AI 상담 품질 평가 전문가다.\n"
    "아래 [페르소나 정보]와 [대화 내역]을 보고, AI 상담사(어시스턴트)의 응답 품질을 평가하라.\n\n"
    "[페르소나 정보]\n{persona_desc}\n\n"
    "[대화 내역]\n{conversation}\n\n"
    "아래 5가지 기준 각각 0~10점으로 채점하고, 반드시 아래 JSON 형식으로만 답변하라 (JSON만, 설명 없음):\n"
    '{{\n'
    '  "정확성": <0-10 정수>,\n'
    '  "맞춤도": <0-10 정수>,\n'
    '  "전문성": <0-10 정수>,\n'
    '  "실행가능성": <0-10 정수>,\n'
    '  "명확성": <0-10 정수>,\n'
    '  "총평": "<2~3문장으로 핵심 문제점과 개선 방향>",\n'
    '  "주요_문제": ["<문제1>", "<문제2>"],\n'
    '  "개선_제안": ["<개선1>", "<개선2>"]\n'
    "}}\n\n"
    "채점 기준:\n"
    "- 정확성(0-10): 사실 오류 없음, 정책/법령 정보 신뢰도\n"
    "- 맞춤도(0-10): 페르소나 특성(조건, 성격, 요구)을 얼마나 반영했는지\n"
    "- 전문성(0-10): 전문 용어 적절 활용, 체계적 구조, 깊이\n"
    "- 실행가능성(0-10): 구체적인 다음 행동(신청방법, 기관, 기한 등) 안내\n"
    "- 명확성(0-10): 이해하기 쉬운 언어, 핵심 먼저, 불필요한 반복 없음\n"
)


def gemini_score(persona, conversation_text):
    model = _get_gemini_model()
    if not model:
        return None
    prompt = SCORE_PROMPT.format(
        persona_desc=f"{persona['name']}: {persona['desc']}",
        conversation=conversation_text,
    )
    try:
        resp = model.generate_content(prompt)
        raw = resp.text.strip()
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            return json.loads(m.group())
    except Exception as e:
        print(f"  [Gemini 채점 오류] {e}", flush=True)
    return None


# -----------------------------------------------------------------
# 페르소나 1개 실행
# -----------------------------------------------------------------
def run_persona(persona, expert_user, conn):
    pid = persona["id"]
    print(f"\n{'--'*28}", flush=True)
    print(f"[{pid}] {persona['name']}", flush=True)
    print(f"  {persona['desc']}", flush=True)

    cid = create_client(persona["profile"], expert_user["bn"], conn)
    conversation = []
    action = persona["action"]
    mode   = persona["mode"]
    matched_count = 0

    for i, user_msg in enumerate(persona["turns"], 1):
        conversation.append({"role": "user", "text": user_msg})
        print(f"  > 턴 {i} -- 사용자: {user_msg[:60]}", flush=True)

        result = call_pro(conversation, action, mode, cid, expert_user)
        reply  = result.get("reply", "[응답 없음]")
        matched = result.get("matched_announcements") or []
        matched_count = max(matched_count, len(matched))

        # match 페르소나는 후속 턴도 action="match" 유지 (대화 히스토리 포함 재매칭)

        conversation.append({"role": "assistant", "text": reply})
        print(f"  AI ({i}): {reply[:80]}{'...' if len(reply) > 80 else ''}", flush=True)
        time.sleep(3)

    delete_client(cid, conn)

    conv_text = "\n".join(
        ("[사용자] " if m["role"] == "user" else "[AI 상담사] ") + m["text"]
        for m in conversation
    )

    print(f"  Gemini 채점 중...", flush=True)
    scores = gemini_score(persona, conv_text)
    if scores:
        total = sum(scores.get(k, 0) for k in ["정확성","맞춤도","전문성","실행가능성","명확성"])
        print(f"  채점 완료 -- 총점: {total}/50", flush=True)
    else:
        total = None
        print(f"  채점 실패 (Gemini 미응답)", flush=True)

    return {
        "id": pid,
        "name": persona["name"],
        "desc": persona["desc"],
        "type": persona["type"],
        "turns_count": len(persona["turns"]),
        "matched_count": matched_count,
        "conversation": conversation,
        "scores": scores,
        "total_score": total,
    }


# -----------------------------------------------------------------
# HTML
# -----------------------------------------------------------------
HTML_CSS = """
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:'Malgun Gothic','맑은 고딕',sans-serif; font-size:11pt; color:#1a1a2e; background:#fff; padding:24px; }
h1 { font-size:22pt; color:#4f46e5; margin-bottom:6px; }
h2 { font-size:14pt; color:#1e1b4b; margin:32px 0 12px; border-bottom:2px solid #e0e7ff; padding-bottom:5px; }
.meta { font-size:9pt; color:#6b7280; margin-bottom:24px; }
table { width:100%; border-collapse:collapse; font-size:10pt; margin-bottom:18px; }
th { background:#4f46e5; color:white; padding:8px 10px; text-align:center; }
td { border:1px solid #e5e7eb; padding:8px 10px; vertical-align:top; }
tr:nth-child(even) td { background:#f5f3ff; }
.persona-card { border:1px solid #c7d2fe; border-radius:10px; padding:20px; margin-bottom:28px; page-break-inside:avoid; }
.persona-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px; }
.persona-id { font-size:15pt; font-weight:bold; color:#4f46e5; }
.persona-name { font-size:13pt; font-weight:bold; color:#1e1b4b; margin-bottom:4px; }
.persona-desc { font-size:9pt; color:#6b7280; font-style:italic; }
.score-badge { text-align:right; }
.total-score { font-size:26pt; font-weight:bold; color:#dc2626; }
.total-label { font-size:8pt; color:#9ca3af; }
.score-bar-wrap { margin:14px 0; }
.score-row { display:flex; align-items:center; gap:8px; margin-bottom:6px; font-size:9pt; }
.score-label { width:80px; color:#374151; font-weight:bold; }
.score-bar-bg { flex:1; background:#e5e7eb; border-radius:4px; height:14px; }
.score-bar { height:14px; border-radius:4px; }
.score-num { width:32px; text-align:right; font-weight:bold; color:#4f46e5; }
.chat { margin-top:14px; }
.msg { margin-bottom:9px; padding:9px 14px; border-radius:8px; font-size:10pt; line-height:1.65; }
.msg-user { background:#ede9fe; text-align:right; margin-left:25%; }
.msg-ai { background:#f9fafb; border:1px solid #e5e7eb; margin-right:25%; }
.msg-label { font-size:8pt; font-weight:bold; margin-bottom:3px; color:#6b7280; }
.verdict-box { background:#fef3c7; border-left:4px solid #f59e0b; padding:12px 16px; border-radius:0 8px 8px 0; margin-top:14px; }
.verdict-title { font-size:9pt; font-weight:bold; color:#92400e; margin-bottom:5px; }
.verdict-text { font-size:10pt; color:#78350f; line-height:1.6; }
.issue-list,.suggest-list { list-style:none; margin-top:8px; }
.issue-list li::before { content:"!  "; }
.suggest-list li::before { content:"-> "; }
.issue-list li { font-size:9pt; color:#92400e; padding:2px 0; }
.suggest-list li { font-size:9pt; color:#065f46; padding:2px 0; }
.no-score { font-size:9pt; color:#9ca3af; font-style:italic; padding:8px 0; }
.footer { margin-top:48px; font-size:9pt; color:#9ca3af; text-align:center; border-top:1px solid #e5e7eb; padding-top:14px; }
@media print { .persona-card { page-break-inside:avoid; } }
"""

SCORE_KEYS = ["정확성","맞춤도","전문성","실행가능성","명확성"]
SCORE_COLORS = {
    "정확성":    "#6366f1",
    "맞춤도":    "#8b5cf6",
    "전문성":    "#0891b2",
    "실행가능성": "#059669",
    "명확성":    "#d97706",
}


def _score_bar(label, val):
    color = SCORE_COLORS.get(label, "#6366f1")
    pct = max(0, min(100, int((val or 0) / 10 * 100)))
    v = val if val is not None else "-"
    return (
        f'<div class="score-row"><span class="score-label">{label}</span>'
        f'<div class="score-bar-bg"><div class="score-bar" style="width:{pct}%;background:{color}"></div></div>'
        f'<span class="score-num">{v}</span></div>'
    )


def _color_total(total):
    if total is None: return "-"
    if total < 25: return f'<span style="color:#dc2626;font-weight:bold">{total}</span>'
    if total < 38: return f'<span style="color:#d97706;font-weight:bold">{total}</span>'
    return f'<span style="color:#059669;font-weight:bold">{total}</span>'


def build_html(results, ts):
    lines = []
    lines.append(f'<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><title>PRO 상담 품질 평가</title><style>{HTML_CSS}</style></head><body>')
    lines.append(f'<h1>PRO 상담 품질 평가 - 까칠한 사용자 페르소나</h1>')
    lines.append(f'<p class="meta">실행일시: {ts} | 페르소나 {len(results)}개 | Gemini 자동 채점 (5개 항목 x 10점)</p>')

    # 요약 테이블
    lines.append('<h2>1. 채점 요약</h2><table>')
    lines.append('<tr><th style="width:20%">페르소나</th><th>정확성</th><th>맞춤도</th><th>전문성</th><th>실행가능성</th><th>명확성</th><th>총점/50</th><th>핵심 문제</th></tr>')
    for r in results:
        s = r.get("scores") or {}
        cells = "".join(f'<td style="text-align:center">{s.get(k,"-")}</td>' for k in SCORE_KEYS)
        issues = " / ".join((s.get("주요_문제") or [])[:2]) or "-"
        lines.append(f'<tr><td><strong>[{r["id"]}]</strong> {r["name"]}</td>{cells}<td>{_color_total(r.get("total_score"))}</td><td style="font-size:9pt">{issues}</td></tr>')
    scored = [r for r in results if r.get("total_score") is not None]
    if scored:
        avg_t = round(sum(r["total_score"] for r in scored) / len(scored), 1)
        avg_cells = "".join(
            f'<td style="text-align:center;font-weight:bold">{round(sum(r["scores"].get(k,0) for r in scored if r.get("scores"))/len(scored),1)}</td>'
            for k in SCORE_KEYS
        )
        lines.append(f'<tr style="background:#e0e7ff"><td><strong>전체 평균</strong></td>{avg_cells}<td style="text-align:center;font-weight:bold">{avg_t}</td><td></td></tr>')
    lines.append("</table>")

    # 페르소나별 상세
    lines.append("<h2>2. 페르소나별 상세 평가</h2>")
    for r in results:
        s = r.get("scores") or {}
        total = r.get("total_score")
        td = f"{total}/50" if total is not None else "채점불가"
        lines.append(
            f'<div class="persona-card"><div class="persona-header"><div>'
            f'<div class="persona-id">[{r["id"]}]</div>'
            f'<div class="persona-name">{r["name"]}</div>'
            f'<div class="persona-desc">{r["desc"]}</div></div>'
            f'<div class="score-badge"><div class="total-score">{td}</div>'
            f'<div class="total-label">Gemini 채점</div></div></div>'
        )
        if s:
            lines.append('<div class="score-bar-wrap">')
            for k in SCORE_KEYS:
                lines.append(_score_bar(k, s.get(k)))
            lines.append('</div>')
        else:
            lines.append('<div class="no-score">Gemini 채점 결과 없음 (API 오류 또는 미설정)</div>')
        lines.append('<div class="chat">')
        for msg in r["conversation"]:
            txt = msg.get("text","").replace("<","&lt;").replace(">","&gt;").replace("\n","<br>")
            if msg["role"] == "user":
                lines.append(f'<div class="msg msg-user"><div class="msg-label">사용자 ({r["name"]})</div>{txt}</div>')
            else:
                lines.append(f'<div class="msg msg-ai"><div class="msg-label">AI 상담사</div>{txt}</div>')
        lines.append('</div>')
        if s:
            issues_html = "".join(f'<li>{i}</li>' for i in (s.get("주요_문제") or []))
            suggest_html = "".join(f'<li>{sg}</li>' for sg in (s.get("개선_제안") or []))
            lines.append(
                f'<div class="verdict-box"><div class="verdict-title">Gemini 총평</div>'
                f'<div class="verdict-text">{s.get("총평","")}</div>'
                f'<ul class="issue-list">{issues_html}</ul>'
                f'<ul class="suggest-list">{suggest_html}</ul></div>'
            )
        lines.append(f'<p style="font-size:9pt;color:#9ca3af;margin-top:10px">대화 턴: {r["turns_count"]}회 | 매칭 공고: {r["matched_count"]}건 | 유형: {r["type"]}</p></div>')

    # 종합 개선 과제
    lines.append("<h2>3. 종합 개선 과제</h2><table><tr><th style='width:5%'>#</th><th>개선 제안</th><th style='width:25%'>출처 페르소나</th></tr>")
    idx = 1
    seen = set()
    for r in results:
        for sg in ((r.get("scores") or {}).get("개선_제안") or []):
            if sg not in seen:
                seen.add(sg)
                lines.append(f'<tr><td style="text-align:center">{idx}</td><td>{sg}</td><td>{r["name"]}</td></tr>')
                idx += 1
    if idx == 1:
        lines.append('<tr><td colspan="3" style="text-align:center;color:#9ca3af">채점 결과 없음</td></tr>')
    lines.append("</table>")

    lines.append(f'<div class="footer">Auto_Gov_Macting PRO 상담 품질 평가 - 까칠한 페르소나 x Gemini 채점 | 생성: {ts}</div>')
    lines.append("</body></html>")
    return "\n".join(lines)


# -----------------------------------------------------------------
# 메인
# -----------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email",    required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--personas", default="P1,P2,P3,P4,P5",
                        help="실행할 페르소나 ID (쉼표 구분)")
    args = parser.parse_args()

    run_ids = [x.strip().upper() for x in args.personas.split(",")]
    selected = [p for p in PERSONAS if p["id"] in run_ids]
    if not selected:
        print("실행할 페르소나가 없습니다."); return

    print(f"[PRO 품질 평가] 페르소나 {len(selected)}개 실행", flush=True)
    print(f"  계정: {args.email}", flush=True)

    conn = get_db_conn()
    try:
        expert_user = login_get_user(args.email, args.password, conn)
        print(f"  로그인: user_id={expert_user['user_id']} plan={expert_user['plan']}", flush=True)
        if expert_user["plan"] != "pro":
            print("  WARNING: plan이 pro가 아닙니다. PRO 기능이 제한될 수 있습니다.", flush=True)
    except Exception as e:
        print(f"  ERROR: 로그인 실패: {e}")
        conn.close()
        return

    results = []
    for persona in selected:
        try:
            r = run_persona(persona, expert_user, conn)
            results.append(r)
            time.sleep(5)
        except Exception as e:
            print(f"  ERROR: [{persona['id']}] 실패: {e}", flush=True)
            import traceback; traceback.print_exc()

    conn.close()

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    base = os.path.dirname(os.path.abspath(__file__))

    raw_path = os.path.join(base, f"test_pro_quality_raw_{ts}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n[raw] {raw_path}", flush=True)

    html = build_html(results, ts)
    html_path = os.path.join(base, f"test_pro_quality_report_{ts}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[report] {html_path}", flush=True)
    print(f"\n브라우저에서 열고 Ctrl+P -> PDF 저장하세요.", flush=True)
    print(f"\n{'='*55}", flush=True)
    print(f"완료: {len(results)}/{len(selected)} 페르소나", flush=True)


if __name__ == "__main__":
    main()
