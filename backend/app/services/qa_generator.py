"""
qa_generator.py — 자금상담 사전학습 Q&A 자동 생성
웹 검색으로 자주 묻는 질문 수집 → Gemini로 답변 생성 → qa_review_queue 저장
"""
import os
import json
import time
import psycopg2
import psycopg2.extras
import requests

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── 자주 묻는 질문 주제 (웹 검색 키워드) ──
SEARCH_TOPICS = [
    ("정책자금 자주묻는질문", "fund_biz"),
    ("소상공인 대출 자격요건", "fund_biz"),
    ("중소기업 정책자금 한도 금리", "fund_biz"),
    ("창업자금 신청 조건 FAQ", "fund_biz"),
    ("기업 보증 신용보증기금 이용방법", "fund_biz"),
    ("소상공인 경영개선자금 조건", "fund_biz"),
    ("중진공 정책자금 종류 비교", "fund_biz"),
    ("청년 창업자금 자주묻는질문", "fund_indiv"),
    ("청년 정부지원금 자격요건 FAQ", "fund_indiv"),
    ("개인사업자 운전자금 신청방법", "fund_indiv"),
    ("예비창업자 지원사업 자주묻는질문", "fund_indiv"),
    ("청년전용 창업자금 금리 한도", "fund_indiv"),
]

# ── 도메인별 시뮬레이션 질문 (검색 보완용 고정 질문셋) ──
SEED_QUESTIONS = {
    "fund_biz": [
        "소상공인 정책자금 신청 자격이 어떻게 되나요?",
        "중소기업 정책자금과 일반 은행대출의 차이점은 무엇인가요?",
        "신용보증기금과 기술보증기금의 차이는 무엇인가요?",
        "정책자금 신청 시 필요한 서류는 무엇인가요?",
        "창업한 지 얼마나 지나야 정책자금을 받을 수 있나요?",
        "정책자금 금리는 어떻게 결정되나요?",
        "운전자금과 시설자금의 차이점은 무엇인가요?",
        "정책자금 거절 사유에는 어떤 것들이 있나요?",
        "소진공 소상공인 자금과 중진공 중소기업 자금의 차이는?",
        "법인사업자와 개인사업자의 정책자금 차이점은?",
        "정책자금 대출 후 조기 상환 시 패널티가 있나요?",
        "매출이 없는 스타트업도 정책자금 신청이 가능한가요?",
        "폐업 후 재창업자도 정책자금을 받을 수 있나요?",
        "정책자금 신청 후 심사 기간은 얼마나 걸리나요?",
        "정책자금 한도는 어떻게 산정되나요?",
    ],
    "fund_indiv": [
        "청년 창업자금 신청 나이 제한이 어떻게 되나요?",
        "취업 중인 청년도 창업자금을 받을 수 있나요?",
        "청년전용창업자금과 일반 창업자금의 차이점은?",
        "개인사업자 운전자금 신청 시 신용점수 기준은?",
        "예비창업자 단계에서 받을 수 있는 자금 지원은?",
        "청년 창업자금 상환 조건은 어떻게 되나요?",
        "부업이나 투잡 상태에서 창업자금 신청 가능한가요?",
        "대학생도 창업자금 신청이 가능한가요?",
        "청년 창업자금 신청 후 사업 계획서는 어떻게 작성하나요?",
        "여성 창업자를 위한 별도 지원 자금이 있나요?",
        "신용불량자도 청년 창업자금을 받을 수 있나요?",
        "지역 청년창업 지원과 중앙 정부 지원의 차이는?",
        "소액 창업자금부터 시작하고 싶은데 최소 한도는?",
        "창업 아이템이 없어도 창업자금 신청이 가능한가요?",
        "청년 창업자금 거절 후 재신청 기간은 얼마나 되나요?",
    ],
}


def search_questions_via_gemini(topic: str, category: str, api_key: str) -> list[str]:
    """Gemini로 특정 주제에 대한 자주 묻는 질문 10개 생성"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-2.5-flash")

        prompt = f"""당신은 정부 자금상담 전문가입니다.
'{topic}' 주제로 실제 중소기업/소상공인/창업자들이 자주 묻는 어려운 질문 10개를 생성하세요.

조건:
- 단순한 질문이 아니라 구체적이고 판단이 필요한 질문
- 금리, 한도, 자격요건, 절차, 서류 등 실질적인 내용
- 각 줄에 질문 하나씩, 번호 없이

JSON 배열로 반환: ["질문1", "질문2", ...]"""

        response = model.generate_content(prompt)
        text = response.text.strip()
        # JSON 파싱
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        questions = json.loads(text)
        return [q for q in questions if isinstance(q, str) and len(q) > 10][:10]
    except Exception as e:
        print(f"  [qa_gen] 질문 생성 오류 ({topic}): {e}")
        return []


def generate_answer(question: str, category: str, api_key: str) -> str:
    """자금상담AI 역할로 질문에 답변 생성"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-2.5-flash")

        persona = "기업/소상공인 자금상담" if category == "fund_biz" else "청년/개인 창업자금 상담"

        prompt = f"""당신은 {persona} 전문 AI입니다.
아래 질문에 대해 정확하고 구체적인 답변을 작성하세요.

질문: {question}

답변 원칙:
- 정확한 정보 위주로 답변 (추측 금지)
- 구체적인 기관명, 금리범위, 한도 등 수치 포함
- 불확실한 부분은 "기관 확인 필요"로 명시
- 300자 이내로 간결하게
- 마크다운 사용 가능"""

        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"  [qa_gen] 답변 생성 오류: {e}")
        return ""


def generate_and_save_qa(batch_size: int = 5) -> dict:
    """
    Q&A 생성 후 qa_review_queue에 저장
    batch_size: 토픽당 생성할 질문 수 (API 비용 절약)
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return {"error": "GEMINI_API_KEY 미설정"}

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    # 이미 생성된 질문 목록 (중복 방지)
    cur.execute("SELECT question FROM qa_review_queue")
    existing = {r["question"] for r in cur.fetchall()}

    saved = 0
    errors = 0

    # ── 1. 고정 시드 질문 먼저 처리 ──
    for category, questions in SEED_QUESTIONS.items():
        for question in questions:
            if question in existing:
                continue
            answer = generate_answer(question, category, api_key)
            if not answer:
                errors += 1
                continue
            cur.execute(
                """INSERT INTO qa_review_queue (question, ai_answer, category, source_keywords)
                   VALUES (%s, %s, %s, %s)""",
                (question, answer, category, "seed")
            )
            conn.commit()
            existing.add(question)
            saved += 1
            print(f"  [seed] [{category}] {question[:40]}... → 저장")
            time.sleep(0.5)  # API 레이트 리밋 방지

    # ── 2. 토픽별 Gemini 질문 생성 ──
    for topic, category in SEARCH_TOPICS:
        print(f"\n[{topic}] 질문 생성 중...")
        questions = search_questions_via_gemini(topic, category, api_key)

        for question in questions[:batch_size]:
            if question in existing:
                continue
            answer = generate_answer(question, category, api_key)
            if not answer:
                errors += 1
                continue
            cur.execute(
                """INSERT INTO qa_review_queue (question, ai_answer, category, source_keywords)
                   VALUES (%s, %s, %s, %s)""",
                (question, answer, category, topic)
            )
            conn.commit()
            existing.add(question)
            saved += 1
            print(f"  [{category}] {question[:40]}... → 저장")
            time.sleep(0.5)

    conn.close()
    print(f"\n✅ Q&A 생성 완료: {saved}건 저장, {errors}건 오류")
    return {"saved": saved, "errors": errors}
