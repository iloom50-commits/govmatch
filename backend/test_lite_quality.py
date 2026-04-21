#!/usr/bin/env python
"""[LITE 품질 테스트] 4 까다로운 페르소나 × Gemini + OpenAI 교차 평가.

출력: test_lite_quality_report_YYYYMMDD_HHMM.md

실행 전 .env 확인:
  - GEMINI_API_KEY (Gemini 2.5-flash)
  - OPENAI_API_KEY (gpt-4o-mini)
"""

import os
import sys
import json
import time
import datetime
from typing import List, Dict, Callable, Any


def with_retry(fn: Callable, max_attempts: int = 4, initial_wait: float = 10.0, label: str = "") -> Any:
    """429 등 일시적 오류에 대해 exponential backoff 재시도."""
    wait = initial_wait
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            msg = str(e)
            is_429 = ("429" in msg) or ("Resource exhausted" in msg) or ("rate" in msg.lower())
            if attempt < max_attempts and is_429:
                print(f"  [retry {label}] {attempt}회 실패 (429), {wait:.0f}초 대기 후 재시도", flush=True)
                time.sleep(wait)
                wait *= 1.8
                continue
            # 429 아닌 다른 에러면 즉시 중단
            if not is_429:
                raise
            break
    raise RuntimeError(f"Max retries exceeded ({label}): {last_err}")

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
import psycopg2.extras
from app.config import DATABASE_URL


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 페르소나 정의
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PERSONAS = [
    {
        "id": 1,
        "name": "60세 은퇴자 카페 창업 준비",
        "difficulty": "사용자 이해도 낮음",
        "profile": {
            "user_type": "individual",
            "age_range": "60대 이상",
            "income_level": "해당없음",
            "family_type": "일반",
            "employment_status": "구직자",
            "address_city": "부산광역시",
            "interests": "카페창업, 소상공인지원",
            "email": "test_persona1@example.com",
        },
        "mode": "individual_fund",
        "seed_question": "은퇴하고 카페 차리려는데, 정부에서 지원 받을 수 있는 게 있어요? IT 잘 몰라서 쉽게 설명해주세요.",
        "persona_prompt": """당신은 60세 은퇴자입니다. IT에 익숙하지 않고 정부 지원 제도도 잘 모릅니다.
부산에서 카페 창업을 준비하고 있습니다.
AI 상담에 대해 "어려운 말로 하지 말고 쉽게" 반복 요청하고,
이해 못한 부분은 "그게 무슨 뜻이에요?"라고 다시 물어보세요.""",
    },
    {
        "id": 2,
        "name": "25세 취준생 막무가내 탐색",
        "difficulty": "오타·줄임말·흐릿한 요청",
        "profile": {
            "user_type": "individual",
            "age_range": "20대",
            "income_level": "해당없음",
            "family_type": "1인가구",
            "employment_status": "구직자",
            "address_city": "서울특별시",
            "interests": "청년, 취업, 창업",
            "email": "test_persona2@example.com",
        },
        "mode": "individual_fund",
        "seed_question": "나 25살 서울사는데 청년 지원금 뭐 잇나영? ㅋㅋ 아무거나 다 받고싶음",
        "persona_prompt": """당신은 25세 서울 취준생입니다. 오타와 줄임말을 많이 씁니다(예: "잇나영", "ㅋㅋ", "짱 좋아").
구체적 목적 없이 "아무거나 받고 싶다"는 태도입니다.
AI가 질문하면 "몰라요", "대충 설명해주세요", "진짜요? 확실해요?" 같이 반응하세요.""",
    },
    {
        "id": 3,
        "name": "사회적기업 전환 준비 CEO",
        "difficulty": "특수 제도·전환 과정",
        "profile": {
            "user_type": "business",
            "company_name": "테스트그린(주)",
            "establishment_date": "2020-03-15",
            "industry_code": "94",  # 협회 및 단체, 수리 및 기타 개인 서비스업
            "revenue_bracket": "10억~30억",
            "employee_count_bracket": "10~29명",
            "address_city": "경기도",
            "interests": "사회적기업, ESG, 전환지원",
            "email": "test_persona3@example.com",
        },
        "mode": "business_fund",
        "seed_question": "일반 중소기업인데 사회적기업으로 전환 준비 중입니다. 예비 사회적기업 인증 받기 전·후에 받을 수 있는 지원금이 다른가요? 구체적 제도와 차이점을 알려주세요.",
        "persona_prompt": """당신은 5년차 중소기업 대표이며 사회적기업 전환을 준비 중입니다.
예비 사회적기업 vs 인증 사회적기업의 차이, 각 단계에서 신청 가능한 지원금,
고용노동부/행정안전부/산자부 등 주무부처별 제도 차이를 상세히 알고 싶어합니다.
AI 답변이 피상적이면 "그건 이미 알고 있고, 더 구체적으로 알려주세요"라고 요구하세요.""",
    },
    {
        "id": 4,
        "name": "폐업 후 재창업 + 주제 교란",
        "difficulty": "업력 계산 경계 + 컨텍스트 추적",
        "profile": {
            "user_type": "business",
            "company_name": "리스타트테크",
            "establishment_date": "2025-06-01",  # 재창업 후 6개월
            "industry_code": "62",  # 컴퓨터 프로그래밍
            "revenue_bracket": "1억~5억",
            "employee_count_bracket": "5~9명",
            "address_city": "대전광역시",
            "interests": "재창업, IT, R&D",
            "email": "test_persona4@example.com",
        },
        "mode": "business_fund",
        "seed_question": "3년 전에 첫 회사 폐업하고 작년 6월에 새 회사 차렸어요. 업력 7년차 사업자인지 1년차 사업자인지 정부 기준으로 알려주세요.",
        "persona_prompt": """당신은 재창업자입니다. 첫 회사(2018~2023 폐업) 후 2025년 6월에 재창업했습니다.
대화 중 갑자기 주제를 바꿉니다 (예: 자금 → 인력채용 → R&D → 다시 자금).
3턴마다 "아 그것 말고"라며 새 주제로 전환하세요.
AI가 이전 대화를 기억하는지(컨텍스트 유지) 테스트하세요.""",
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI 호출 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def simulate_user_turn(persona: dict, conversation: List[Dict]) -> str:
    """Gemini로 페르소나 역할의 다음 질문 생성."""
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("models/gemini-2.5-flash",
                                   generation_config={"max_output_tokens": 256, "temperature": 0.8})

    conv_text = "\n".join([f"[{m['role']}] {m.get('text', '')[:300]}" for m in conversation])
    prompt = f"""당신은 아래 페르소나로 정부 지원금 AI 상담을 이용 중입니다.
{persona['persona_prompt']}

지금까지 대화:
{conv_text}

페르소나 성격에 맞게 다음 질문이나 반응을 1~2문장으로만 생성하세요.
오직 사용자의 다음 발화만 출력 (JSON 아님, 따옴표 없이).
AI가 잘 답변했으면 더 깊은 질문, 애매하면 재질문, 만족하면 "감사합니다 종료"라고 답하세요."""

    try:
        resp = with_retry(lambda: model.generate_content(prompt), label="simulate_user")
        text = (resp.text or "").strip()
        # 앞뒤 따옴표·불필요 기호 제거
        for q in ['"', "'", "`"]:
            if text.startswith(q) and text.endswith(q):
                text = text[1:-1].strip()
        return text or "더 자세히 알려주세요."
    except Exception as e:
        print(f"  [simulate_user] error: {e}")
        return "더 자세히 설명해주세요."


def call_lite_chat(messages: List[Dict], profile: dict, mode: str, db_conn) -> Dict:
    """LITE /api/ai/chat 실제 호출 (직접 함수 호출) — 429 재시도 포함."""
    from app.services.ai_consultant import chat_lite_fund_expert
    try:
        return with_retry(
            lambda: chat_lite_fund_expert(messages, db_conn=db_conn, user_profile=profile, mode=mode),
            label="lite_chat",
        )
    except Exception as e:
        return {"reply": f"[호출 실패] {str(e)[:200]}", "choices": [], "announcements": []}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 평가 함수 (Gemini + OpenAI 교차)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EVAL_PROMPT_TMPL = """당신은 정부 지원금 AI 상담 품질 감사관입니다.
아래 대화를 세 영역(UI/UX/답변 품질)으로 나눠 정밀 평가하세요.

[페르소나]
{persona_desc}

[대화 전문]
{conversation}

[평가 기준 — 각 항목 0~10점]
A. UI 품질
   - ui_format: 마크다운·문단·리스트 가독성
   - ui_choices: 선택지·후속 질문 제공 적절성

B. UX 품질
   - ux_context: 대화 컨텍스트 유지 (이전 맥락 참조)
   - ux_comprehension: 사용자 이해 수준 감지·조정
   - ux_clarification: 불명확 질문의 구체화 유도

C. 답변 품질
   - quality_accuracy: 정확성(근거 기반, 환각 없음)
   - quality_completeness: 완결성(질문에 충분히 답함)
   - quality_usefulness: 실제 도움 수준
   - quality_recommendation: 공고 추천 적절성

[취약점 추출 — 구체적 문제점]
- ui_issues: UI 문제 리스트 (각 문제 간결 1문장)
- ux_issues: UX 문제 리스트
- quality_issues: 답변 품질 문제 리스트
- improvements: 개선 제안 리스트 (우선순위 high/mid/low 포함)

JSON만 응답 (Markdown 코드블록 없이):
{{
  "ui_format": 0, "ui_choices": 0,
  "ux_context": 0, "ux_comprehension": 0, "ux_clarification": 0,
  "quality_accuracy": 0, "quality_completeness": 0, "quality_usefulness": 0, "quality_recommendation": 0,
  "overall_avg": 0,
  "ui_issues": ["..."],
  "ux_issues": ["..."],
  "quality_issues": ["..."],
  "improvements": [{{"priority": "high|mid|low", "area": "ui|ux|quality", "suggestion": "..."}}]
}}"""


def evaluate_with_gemini(persona: dict, conversation: List[Dict]) -> dict:
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("models/gemini-2.5-flash",
                                   generation_config={"max_output_tokens": 4096, "temperature": 0.2,
                                                       "response_mime_type": "application/json"})
    conv_text = "\n\n".join([
        f"[{m['role'].upper()}] {m.get('text', '')}"
        for m in conversation
    ])
    prompt = EVAL_PROMPT_TMPL.format(
        persona_desc=f"{persona['name']} — {persona['difficulty']}\n{persona['persona_prompt']}",
        conversation=conv_text[:8000],
    )
    try:
        resp = with_retry(lambda: model.generate_content(prompt), label="eval_gemini")
        return json.loads(resp.text)
    except Exception as e:
        print(f"  [eval-gemini] error: {e}")
        return {"_error": str(e)}


def evaluate_with_openai(persona: dict, conversation: List[Dict]) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"_error": "OPENAI_API_KEY 미설정"}
    import httpx
    conv_text = "\n\n".join([
        f"[{m['role'].upper()}] {m.get('text', '')}"
        for m in conversation
    ])
    prompt = EVAL_PROMPT_TMPL.format(
        persona_desc=f"{persona['name']} — {persona['difficulty']}\n{persona['persona_prompt']}",
        conversation=conv_text[:8000],
    )
    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "max_tokens": 4096,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            return {"_error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        data = resp.json()
        return json.loads(data["choices"][0]["message"]["content"])
    except Exception as e:
        return {"_error": str(e)}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_conversation(persona: dict, db_conn, max_turns: int = 6) -> List[Dict]:
    """페르소나별 자동 대화 실행. seed 질문으로 시작, 이후 Gemini 시뮬레이션."""
    print(f"\n=== 페르소나 {persona['id']}: {persona['name']} ===")
    conv = [{"role": "user", "text": persona["seed_question"]}]
    print(f"[USER T1] {persona['seed_question'][:100]}...")

    for turn in range(1, max_turns + 1):
        # 1) LITE 상담 호출
        result = call_lite_chat(conv, persona["profile"], persona["mode"], db_conn)
        reply = result.get("reply", "")
        choices = result.get("choices", [])
        anns = result.get("announcements", [])
        assistant_entry = {"role": "assistant", "text": reply, "choices": choices, "announcements": anns}
        conv.append(assistant_entry)
        print(f"[AI T{turn}] {reply[:150]}..." if len(reply) > 150 else f"[AI T{turn}] {reply}")

        # 2) 종료 조건
        if turn >= max_turns:
            break
        if "종료" in reply or result.get("done"):
            break

        # 3) 페르소나 역할 다음 질문 생성
        next_q = simulate_user_turn(persona, conv)
        if "종료" in next_q or len(next_q) < 3:
            break
        conv.append({"role": "user", "text": next_q})
        print(f"[USER T{turn+1}] {next_q[:100]}..." if len(next_q) > 100 else f"[USER T{turn+1}] {next_q}")

    return conv


def generate_report(all_results: List[Dict]) -> str:
    """페르소나별 결과 + 종합 분석 Markdown 보고서 생성."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# LITE 상담 품질 평가 보고서",
        f"",
        f"**생성일시**: {ts}",
        f"**평가자**: Gemini 2.5-flash + OpenAI gpt-4o-mini (교차 평가)",
        f"**테스트 페르소나**: {len(all_results)}명",
        f"",
        "---",
        "",
    ]

    # 페르소나별 상세
    all_scores = {"gemini": [], "openai": []}
    all_issues = {"ui": [], "ux": [], "quality": []}
    all_improvements = []

    for res in all_results:
        p = res["persona"]
        conv = res["conversation"]
        ge = res["eval_gemini"]
        oa = res["eval_openai"]

        lines.append(f"## 페르소나 {p['id']}: {p['name']}")
        lines.append(f"**까다로움**: {p['difficulty']}")
        lines.append("")

        # 대화 전문
        lines.append("### 대화 기록")
        lines.append("```")
        for i, m in enumerate(conv, 1):
            role = "👤" if m["role"] == "user" else "🤖"
            lines.append(f"{role} T{i}: {m.get('text', '')[:500]}")
            if m.get("choices"):
                lines.append(f"   선택지: {m['choices']}")
            if m.get("announcements"):
                lines.append(f"   추천 공고: {len(m['announcements'])}건")
        lines.append("```")
        lines.append("")

        # 평가 점수표
        lines.append("### 평가 점수")
        cats = [
            ("ui_format",               "UI 포맷"),
            ("ui_choices",              "UI 선택지"),
            ("ux_context",              "UX 컨텍스트"),
            ("ux_comprehension",        "UX 이해도"),
            ("ux_clarification",        "UX 구체화"),
            ("quality_accuracy",        "품질 정확성"),
            ("quality_completeness",    "품질 완결성"),
            ("quality_usefulness",      "품질 유용성"),
            ("quality_recommendation",  "품질 추천"),
        ]
        lines.append("| 항목 | Gemini | OpenAI | 평균 |")
        lines.append("|---|---|---|---|")
        for key, label in cats:
            g = ge.get(key, "-")
            o = oa.get(key, "-")
            avg = None
            try:
                avg = round((float(g) + float(o)) / 2, 1)
            except Exception:
                avg = "-"
            lines.append(f"| {label} | {g} | {o} | {avg} |")
        lines.append("")

        # 종합 점수
        go = ge.get("overall_avg", "-")
        oo = oa.get("overall_avg", "-")
        lines.append(f"**Gemini 종합**: {go} / 10  ·  **OpenAI 종합**: {oo} / 10")
        all_scores["gemini"].append(ge.get("overall_avg", 0) or 0)
        all_scores["openai"].append(oa.get("overall_avg", 0) or 0)
        lines.append("")

        # 취약점
        for area, emoji, key in [("UI", "🎨", "ui_issues"), ("UX", "✨", "ux_issues"), ("답변 품질", "🎯", "quality_issues")]:
            lines.append(f"### {emoji} {area} 취약점")
            issues = list(ge.get(key, [])) + list(oa.get(key, []))
            if not issues:
                lines.append("- 특이사항 없음")
            else:
                seen = set()
                for issue in issues:
                    if issue and issue not in seen:
                        seen.add(issue)
                        lines.append(f"- {issue}")
                        all_issues[key.split("_")[0]].append(issue)
            lines.append("")

        # 개선 제안
        lines.append("### 개선 제안")
        imps = list(ge.get("improvements", [])) + list(oa.get("improvements", []))
        if not imps:
            lines.append("- 특이사항 없음")
        else:
            for imp in imps:
                if isinstance(imp, dict):
                    pr = imp.get("priority", "mid").upper()
                    area = imp.get("area", "general")
                    sug = imp.get("suggestion", "")
                    lines.append(f"- **[{pr}]** `{area}` {sug}")
                    all_improvements.append(imp)
        lines.append("")
        lines.append("---")
        lines.append("")

    # 종합 분석
    lines.append("## 🔎 종합 분석")
    lines.append("")
    ga = sum(all_scores["gemini"]) / max(1, len(all_scores["gemini"]))
    oa2 = sum(all_scores["openai"]) / max(1, len(all_scores["openai"]))
    lines.append(f"**전체 평균**: Gemini **{ga:.1f}/10**, OpenAI **{oa2:.1f}/10**")
    lines.append("")

    # 빈도 높은 취약점
    from collections import Counter
    for area, emoji in [("ui", "🎨 UI"), ("ux", "✨ UX"), ("quality", "🎯 답변 품질")]:
        cnt = Counter(all_issues[area])
        top = cnt.most_common(5)
        lines.append(f"### {emoji} 공통 취약점 (상위 5개)")
        if not top:
            lines.append("- 특이사항 없음")
        else:
            for issue, n in top:
                lines.append(f"- ({n}회) {issue}")
        lines.append("")

    # 우선순위별 개선 제안
    pri_bucket = {"HIGH": [], "MID": [], "LOW": []}
    for imp in all_improvements:
        if isinstance(imp, dict):
            pr = imp.get("priority", "mid").upper()
            pri_bucket.setdefault(pr, []).append(imp)
    lines.append("## 🔧 개선 우선순위")
    lines.append("")
    for pr in ["HIGH", "MID", "LOW"]:
        lines.append(f"### [{pr}]")
        imps = pri_bucket.get(pr, [])
        if not imps:
            lines.append("- 없음")
        else:
            seen = set()
            for imp in imps:
                key = f"{imp.get('area')}:{imp.get('suggestion')[:50]}"
                if key in seen: continue
                seen.add(key)
                lines.append(f"- `{imp.get('area')}` {imp.get('suggestion')}")
        lines.append("")

    return "\n".join(lines)


def main():
    # 환경 체크
    if not os.environ.get("GEMINI_API_KEY"):
        print("[ERROR] GEMINI_API_KEY 미설정")
        return 1

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    all_results = []

    for persona in PERSONAS:
        try:
            conv = run_conversation(persona, conn, max_turns=5)
            print("  평가 중... (Gemini)", end=" ", flush=True)
            eg = evaluate_with_gemini(persona, conv)
            print("Gemini OK", end=" ", flush=True)
            print("(OpenAI)", end=" ", flush=True)
            eo = evaluate_with_openai(persona, conv)
            print("OpenAI OK")
            all_results.append({"persona": persona, "conversation": conv, "eval_gemini": eg, "eval_openai": eo})
        except Exception as e:
            print(f"  [페르소나 {persona['id']}] 에러: {e}")
            import traceback; traceback.print_exc()

    conn.close()

    # 보고서 생성
    report_md = generate_report(all_results)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    report_path = f"test_lite_quality_report_{ts}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"\n[완료] 보고서: {report_path}")

    # 원자료도 json으로 저장
    raw_path = f"test_lite_quality_raw_{ts}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"[완료] 원자료: {raw_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
