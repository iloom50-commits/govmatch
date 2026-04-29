#!/usr/bin/env python
"""
PRO 상담 품질 DOE (Design of Experiments) 테스트
L8 직교배열 (4인자 × 2수준)

인자:
  A. 고객 유형       : 기업(사업자) / 개인
  B. 상담 유형       : 지원사업 매칭 / 자금상담
  C. 프로필 완성도   : 충분 (업종+매출+지역) / 최소 (이름만)
  D. 질문 방식       : 구체적 / 모호한

실행:
  cd backend
  python test_pro_doe.py --email PRO계정 --password 비밀번호

출력:
  test_doe_report_YYYYMMDD_HHMM.html  (브라우저에서 Ctrl+P → PDF 저장)
  test_doe_raw_YYYYMMDD_HHMM.json
"""
import os, sys, json, time, datetime, argparse
sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─────────────────────────────────────────────────────────────
# L8 직교배열 설계
# ─────────────────────────────────────────────────────────────
# A=고객유형(기업1/개인2)  B=상담유형(매칭1/자금2)
# C=프로필(충분1/최소2)    D=질문(구체1/모호2)
DOE_MATRIX = [
    # Run  A  B  C  D
    (1,    1, 1, 1, 1),
    (2,    1, 1, 2, 2),
    (3,    1, 2, 1, 2),
    (4,    1, 2, 2, 1),
    (5,    2, 1, 1, 2),
    (6,    2, 1, 2, 1),
    (7,    2, 2, 1, 1),
    (8,    2, 2, 2, 2),
]

# ─────────────────────────────────────────────────────────────
# 프로필 풀 (충분 / 최소)
# ─────────────────────────────────────────────────────────────
BIZ_FULL = {
    "client_name": "스마트팜코리아(주)", "client_type": "business",
    "establishment_date": "2021-04-01", "industry_code": "01",
    "industry_name": "농업", "revenue_bracket": "1억~5억",
    "employee_count_bracket": "5~9명", "address_city": "경기도",
    "interests": "스마트팜, 농업기술, 디지털전환", "memo": "스마트팜 솔루션 스타트업",
}
BIZ_MIN = {
    "client_name": "테스트기업", "client_type": "business",
    "establishment_date": None, "industry_code": None, "industry_name": None,
    "revenue_bracket": None, "employee_count_bracket": None,
    "address_city": None, "interests": None, "memo": None,
}
IND_FULL = {
    "client_name": "김지수", "client_type": "individual",
    "establishment_date": None, "industry_code": None, "industry_name": None,
    "revenue_bracket": None, "employee_count_bracket": None,
    "address_city": "서울특별시", "interests": "취업, 청년, 주거",
    "memo": "30대 초반 취업준비생, 전세대출 고민",
    "age_range": "30대", "income_level": "차상위", "employment_status": "구직자",
}
IND_MIN = {
    "client_name": "테스트개인", "client_type": "individual",
    "establishment_date": None, "industry_code": None, "industry_name": None,
    "revenue_bracket": None, "employee_count_bracket": None,
    "address_city": None, "interests": None, "memo": None,
}

# ─────────────────────────────────────────────────────────────
# 질문 세트
# ─────────────────────────────────────────────────────────────
QUESTIONS = {
    ("biz",   "match", "specific"): "경기도 농업 스타트업 업력 3년, 매출 3억인데 스마트팜 관련 지원사업 어떤 게 있나요?",
    ("biz",   "match", "vague"):    "지원금 뭐가 있어요?",
    ("biz",   "fund",  "specific"): "업력 3년 농업 스타트업인데 시설자금 2억 정도 받을 수 있는 정책자금 알려주세요.",
    ("biz",   "fund",  "vague"):    "돈 빌릴 수 있는 데 없나요?",
    ("indiv", "match", "specific"): "서울 거주 30대 구직자인데 취업 지원금이나 청년 혜택 찾고 있어요.",
    ("indiv", "match", "vague"):    "저 받을 수 있는 지원금 있나요?",
    ("indiv", "fund",  "specific"): "청년 전세자금 대출 조건이랑 신청방법 알려주세요.",
    ("indiv", "fund",  "vague"):    "집 관련해서 뭔가 지원 받을 수 있나요?",
}


def build_test_cases():
    cases = []
    for run, a, b, c, d in DOE_MATRIX:
        cust  = "biz"   if a == 1 else "indiv"
        cons  = "match" if b == 1 else "fund"
        prof  = "full"  if c == 1 else "min"
        qtype = "specific" if d == 1 else "vague"

        if cust == "biz":
            profile = BIZ_FULL.copy() if prof == "full" else BIZ_MIN.copy()
            action  = cons
            mode    = "business_fund" if cons == "fund" else None
        else:
            profile = IND_FULL.copy() if prof == "full" else IND_MIN.copy()
            action  = cons
            mode    = "individual_fund" if cons == "fund" else None

        question = QUESTIONS[(cust, cons, qtype)]

        cases.append({
            "run": run,
            "factors": {"A": a, "B": b, "C": c, "D": d},
            "labels": {
                "A": "기업" if a == 1 else "개인",
                "B": "지원사업 매칭" if b == 1 else "자금상담",
                "C": "충분" if c == 1 else "최소",
                "D": "구체적" if d == 1 else "모호한",
            },
            "profile": profile,
            "action": action,
            "mode": mode,
            "question": question,
        })
    return cases


# ─────────────────────────────────────────────────────────────
# DB / API 호출
# ─────────────────────────────────────────────────────────────
def get_db_conn():
    import psycopg2, psycopg2.extras
    from app.config import DATABASE_URL
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def login_get_user(email, password, conn):
    import bcrypt
    cur = conn.cursor()
    cur.execute("SELECT user_id, business_number, email, password_hash, plan FROM users WHERE email=%s", (email,))
    row = cur.fetchone()
    if not row: raise ValueError(f"사용자 없음: {email}")
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
         p.get("employee_count_bracket"), p.get("address_city"), p.get("interests"), p.get("memo",""))
    )
    cid = cur.fetchone()[0]; conn.commit(); cur.close()
    return cid


def delete_client(cid, conn):
    cur = conn.cursor()
    cur.execute("DELETE FROM client_profiles WHERE id=%s", (cid,))
    conn.commit(); cur.close()


def call_pro(messages, action, mode, client_id, expert_user):
    from app.main import AiConsultantChatRequest, _api_pro_consultant_chat_impl
    req = AiConsultantChatRequest(
        messages=messages, action=action, mode=mode,
        client_id=client_id, session_id=None,
        announcement_id=None, is_announcement_start=False,
    )
    cu = {k: expert_user[k] for k in ("user_id","bn","email","plan")}
    try:
        return _api_pro_consultant_chat_impl(req, cu)
    except Exception as e:
        return {"reply": f"[오류] {str(e)[:200]}", "choices": [], "matched_announcements": []}


# ─────────────────────────────────────────────────────────────
# 1개 케이스 실행 (3턴)
# ─────────────────────────────────────────────────────────────
MAX_TURNS = 3

def run_case(case, expert_user, conn):
    run = case["run"]
    print(f"\n{'─'*55}", flush=True)
    print(f"[Run {run}] A={case['labels']['A']}  B={case['labels']['B']}  C={case['labels']['C']}  D={case['labels']['D']}", flush=True)
    print(f"  질문: {case['question'][:70]}", flush=True)

    cid = create_client(case["profile"], expert_user["bn"], conn)
    conversation = [{"role": "user", "text": case["question"]}]
    action = case["action"]
    mode   = case["mode"]
    matched_count = 0

    for turn in range(1, MAX_TURNS + 1):
        print(f"  ▶ AI 응답 (turn {turn})...", flush=True)
        result = call_pro(conversation, action, mode, cid, expert_user)
        reply  = result.get("reply", "[응답 없음]")
        matched = result.get("matched_announcements") or []
        matched_count = max(matched_count, len(matched))

        if action == "match" and matched:
            action = "consult"

        conversation.append({"role": "assistant", "text": reply})
        print(f"  AI({turn}): {reply[:100]}{'...' if len(reply)>100 else ''}", flush=True)

        if result.get("done") or turn == MAX_TURNS:
            break

        # 간단한 후속 질문 (하드코딩)
        followups = {
            "specific": "이 중에서 가장 빨리 신청할 수 있는 것은 어떤 건가요?",
            "vague":    "좀 더 자세히 알려주세요.",
        }
        fq = followups["specific" if case["factors"]["D"]==1 else "vague"]
        conversation.append({"role": "user", "text": fq})
        print(f"  사용자({turn+1}): {fq}", flush=True)
        time.sleep(2)

    delete_client(cid, conn)

    return {
        "run": run,
        "factors": case["factors"],
        "labels": case["labels"],
        "question": case["question"],
        "profile_name": case["profile"]["client_name"],
        "profile_type": "충분" if case["factors"]["C"]==1 else "최소",
        "turns": len([m for m in conversation if m["role"]=="user"]),
        "matched_count": matched_count,
        "conversation": conversation,
        "ai_reply_length": len(conversation[1]["text"]) if len(conversation)>1 else 0,
    }


# ─────────────────────────────────────────────────────────────
# HTML 보고서 생성
# ─────────────────────────────────────────────────────────────
HTML_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; font-size: 11pt; color: #1a1a2e; background: #fff; padding: 20px; }
h1 { font-size: 20pt; color: #4f46e5; margin-bottom: 4px; }
h2 { font-size: 14pt; color: #1e1b4b; margin: 28px 0 10px; border-bottom: 2px solid #e0e7ff; padding-bottom: 4px; }
h3 { font-size: 12pt; color: #312e81; margin: 18px 0 8px; }
.meta { font-size: 9pt; color: #6b7280; margin-bottom: 20px; }
table { width: 100%; border-collapse: collapse; font-size: 10pt; margin-bottom: 16px; }
th { background: #4f46e5; color: white; padding: 7px 10px; text-align: center; }
td { border: 1px solid #e5e7eb; padding: 7px 10px; vertical-align: top; }
tr:nth-child(even) td { background: #f5f3ff; }
.run-card { border: 1px solid #c7d2fe; border-radius: 8px; padding: 16px; margin-bottom: 20px; page-break-inside: avoid; }
.run-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.run-num { font-size: 13pt; font-weight: bold; color: #4f46e5; }
.factor-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.tag { font-size: 8pt; padding: 2px 8px; border-radius: 12px; font-weight: bold; }
.tag-biz  { background:#dbeafe; color:#1d4ed8; }
.tag-ind  { background:#fce7f3; color:#9d174d; }
.tag-match { background:#d1fae5; color:#065f46; }
.tag-fund  { background:#fef3c7; color:#92400e; }
.tag-full  { background:#e0e7ff; color:#3730a3; }
.tag-min   { background:#fee2e2; color:#991b1b; }
.tag-spec  { background:#f0fdf4; color:#166534; border:1px solid #86efac; }
.tag-vague { background:#fef9c3; color:#854d0e; border:1px solid #fde047; }
.q-box { background: #f5f3ff; border-left: 4px solid #6366f1; padding: 8px 12px; margin: 8px 0; border-radius: 0 6px 6px 0; font-style: italic; font-size: 10pt; }
.chat { margin-top: 10px; }
.msg { margin-bottom: 8px; padding: 8px 12px; border-radius: 6px; font-size: 10pt; line-height: 1.6; }
.msg-user { background: #ede9fe; text-align: right; margin-left: 20%; }
.msg-ai   { background: #f9fafb; border: 1px solid #e5e7eb; margin-right: 20%; }
.msg-label { font-size: 8pt; font-weight: bold; margin-bottom: 3px; color: #6b7280; }
.eval-table td { text-align: center; }
.eval-table td:first-child { text-align: left; }
.score-cell { width: 60px; min-height: 28px; }
.comment-cell { min-height: 40px; }
.footer { margin-top: 40px; font-size: 9pt; color: #9ca3af; text-align: center; border-top: 1px solid #e5e7eb; padding-top: 12px; }
@media print {
  .run-card { page-break-inside: avoid; }
  h2 { page-break-before: auto; }
}
"""

def build_html(results, ts):
    lines = []
    lines.append(f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<title>PRO 상담 DOE 품질 평가 보고서</title>
<style>{HTML_CSS}</style></head><body>""")

    # 헤더
    lines.append(f"""
<h1>PRO 상담 품질 — DOE 평가 보고서</h1>
<p class="meta">실행일시: {ts} &nbsp;|&nbsp; L8 직교배열 (4인자 × 2수준) &nbsp;|&nbsp; 총 {len(results)}케이스</p>
""")

    # DOE 설계 행렬
    lines.append("""<h2>1. DOE 설계 행렬</h2>
<table>
<tr><th>Run</th><th>A. 고객유형</th><th>B. 상담유형</th><th>C. 프로필</th><th>D. 질문방식</th><th>질문 요약</th></tr>""")
    for r in results:
        lbl = r["labels"]
        q_short = r["question"][:35] + ("…" if len(r["question"])>35 else "")
        lines.append(f"""<tr>
<td style="text-align:center;font-weight:bold">{r['run']}</td>
<td style="text-align:center">{lbl['A']}</td>
<td style="text-align:center">{lbl['B']}</td>
<td style="text-align:center">{lbl['C']}</td>
<td style="text-align:center">{lbl['D']}</td>
<td>{q_short}</td>
</tr>""")
    lines.append("</table>")

    # 케이스별 상세
    lines.append("<h2>2. 케이스별 상담 내용</h2>")
    for r in results:
        lbl = r["labels"]
        tag_a = "tag-biz" if r["factors"]["A"]==1 else "tag-ind"
        tag_b = "tag-match" if r["factors"]["B"]==1 else "tag-fund"
        tag_c = "tag-full" if r["factors"]["C"]==1 else "tag-min"
        tag_d = "tag-spec" if r["factors"]["D"]==1 else "tag-vague"

        lines.append(f"""<div class="run-card">
<div class="run-header">
  <span class="run-num">Run {r['run']}</span>
  <div class="factor-tags">
    <span class="tag {tag_a}">{lbl['A']}</span>
    <span class="tag {tag_b}">{lbl['B']}</span>
    <span class="tag {tag_c}">프로필:{lbl['C']}</span>
    <span class="tag {tag_d}">질문:{lbl['D']}</span>
  </div>
</div>
<div class="q-box">❓ {r['question']}</div>
<div class="chat">""")

        for msg in r["conversation"]:
            role = msg["role"]
            text = msg.get("text","").replace("<","&lt;").replace(">","&gt;").replace("\n","<br>")
            if role == "user":
                lines.append(f'<div class="msg msg-user"><div class="msg-label">사용자</div>{text}</div>')
            else:
                lines.append(f'<div class="msg msg-ai"><div class="msg-label">AI 상담사</div>{text}</div>')

        lines.append(f"""</div>
<p style="font-size:9pt;color:#6b7280;margin-top:8px">
  대화 턴수: {r['turns']}회 &nbsp;|&nbsp; 매칭 공고: {r['matched_count']}건 &nbsp;|&nbsp; AI 응답 길이: {r['ai_reply_length']}자
</p>
</div>""")

    # 품질 평가표 (사장님 작성용)
    lines.append("""<h2>3. 품질 평가표 (직접 작성)</h2>
<p style="font-size:10pt;color:#6b7280;margin-bottom:12px">
각 항목을 0~10점으로 평가하고 의견을 기재해주세요.
</p>
<table class="eval-table">
<tr>
  <th style="width:22%">Run / 조건</th>
  <th style="width:8%">정확성<br><span style="font-weight:normal;font-size:8pt">정보 오류 없음</span></th>
  <th style="width:8%">맞춤도<br><span style="font-weight:normal;font-size:8pt">프로필 반영</span></th>
  <th style="width:8%">전문성<br><span style="font-weight:normal;font-size:8pt">깊이·구조</span></th>
  <th style="width:8%">실행성<br><span style="font-weight:normal;font-size:8pt">다음단계 안내</span></th>
  <th style="width:8%">합계<br><span style="font-weight:normal;font-size:8pt">/40</span></th>
  <th>특이사항 / 개선 의견</th>
</tr>""")

    for r in results:
        lbl = r["labels"]
        lines.append(f"""<tr>
<td><strong>Run {r['run']}</strong><br>
<span style="font-size:9pt;color:#6b7280">{lbl['A']} | {lbl['B']}<br>{lbl['C']} | {lbl['D']}</span></td>
<td class="score-cell"></td>
<td class="score-cell"></td>
<td class="score-cell"></td>
<td class="score-cell"></td>
<td class="score-cell"></td>
<td class="comment-cell"></td>
</tr>""")

    lines.append("""<tr style="background:#f5f3ff">
<td><strong>합계 / 평균</strong></td>
<td></td><td></td><td></td><td></td><td></td>
<td></td>
</tr>
</table>""")

    # DOE 인자 효과 분석표 (작성 후)
    lines.append("""<h2>4. 인자 효과 분석 (평가 후 작성)</h2>
<p style="font-size:10pt;color:#6b7280;margin-bottom:12px">
평가 완료 후, 각 인자의 수준별 평균 점수를 계산해 어떤 조건이 품질에 영향을 주는지 확인합니다.
</p>
<table>
<tr><th>인자</th><th>수준 1 (기준)</th><th>수준 2</th><th>차이 (효과 크기)</th><th>해석</th></tr>
<tr>
  <td><strong>A. 고객유형</strong></td>
  <td>기업 평균 (Run 1~4)</td>
  <td>개인 평균 (Run 5~8)</td>
  <td class="score-cell"></td>
  <td class="comment-cell"></td>
</tr>
<tr>
  <td><strong>B. 상담유형</strong></td>
  <td>매칭 평균 (Run 1,2,5,6)</td>
  <td>자금 평균 (Run 3,4,7,8)</td>
  <td class="score-cell"></td>
  <td class="comment-cell"></td>
</tr>
<tr>
  <td><strong>C. 프로필</strong></td>
  <td>충분 평균 (Run 1,3,5,7)</td>
  <td>최소 평균 (Run 2,4,6,8)</td>
  <td class="score-cell"></td>
  <td class="comment-cell"></td>
</tr>
<tr>
  <td><strong>D. 질문방식</strong></td>
  <td>구체적 평균 (Run 1,4,6,7)</td>
  <td>모호한 평균 (Run 2,3,5,8)</td>
  <td class="score-cell"></td>
  <td class="comment-cell"></td>
</tr>
</table>
<p style="font-size:9pt;color:#9ca3af">
* 차이가 큰 인자일수록 품질에 미치는 영향이 크며, 개선 우선순위가 됩니다.
</p>""")

    lines.append(f'<div class="footer">Auto_Gov_Macting PRO 상담 DOE 품질 평가 | 생성: {ts}</div>')
    lines.append("</body></html>")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email",    required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--runs",     default="1,2,3,4,5,6,7,8",
                        help="실행할 Run 번호 (쉼표 구분, 기본: 전체)")
    args = parser.parse_args()

    run_ids = [int(x) for x in args.runs.split(",") if x.strip().isdigit()]
    cases = [c for c in build_test_cases() if c["run"] in run_ids]

    print(f"[DOE 테스트] 총 {len(cases)}개 케이스 실행", flush=True)
    print(f"  계정: {args.email}", flush=True)

    conn = get_db_conn()
    try:
        expert_user = login_get_user(args.email, args.password, conn)
        print(f"  로그인: user_id={expert_user['user_id']} plan={expert_user['plan']}", flush=True)
        if expert_user["plan"] != "pro":
            print("  ⚠ plan이 pro가 아닙니다. PRO 기능이 제한될 수 있습니다.", flush=True)
    except Exception as e:
        print(f"  ❌ 로그인 실패: {e}"); conn.close(); return

    results = []
    for case in cases:
        try:
            r = run_case(case, expert_user, conn)
            results.append(r)
            time.sleep(4)
        except Exception as e:
            print(f"  ❌ Run {case['run']} 실패: {e}", flush=True)
            import traceback; traceback.print_exc()

    conn.close()

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    base = os.path.dirname(os.path.abspath(__file__))

    # RAW JSON
    raw_path = os.path.join(base, f"test_doe_raw_{ts}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[raw] {raw_path}", flush=True)

    # HTML 보고서
    html = build_html(results, ts)
    html_path = os.path.join(base, f"test_doe_report_{ts}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[report] {html_path}", flush=True)
    print(f"\n브라우저에서 열고 Ctrl+P → PDF 저장 하세요.", flush=True)

    print(f"\n{'='*55}", flush=True)
    print(f"완료: {len(results)}/{len(cases)}케이스", flush=True)


if __name__ == "__main__":
    main()
