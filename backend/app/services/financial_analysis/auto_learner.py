"""상담 로그 자동 학습 — helpful 피드백 대화에서 고품질 Q&A 추출

Gemini를 사용하여 만족도 높은 상담 대화에서
실무 지식(FAQ, 인사이트)을 자동 추출하여 knowledge_base에 축적한다.
시간이 지날수록 AI가 점점 더 정확해지는 자기 강화 루프.
"""

import json
import os
import traceback

import google.generativeai as genai


def extract_quality_knowledge(
    announcement_id: int,
    category: str,
    title: str,
    messages: list,
    conclusion: str,
    db_conn,
) -> int:
    """helpful 피드백 받은 상담에서 고품질 지식 추출 → knowledge_base 저장

    Returns:
        int: 저장된 지식 건수
    """
    if not messages or len(messages) < 4:
        return 0  # 최소 2턴(4메시지) 이상만

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return 0

    # 대화 텍스트 구성
    conversation = []
    for m in messages:
        role = "사용자" if m.get("role") == "user" else "AI"
        conversation.append(f"{role}: {m.get('text', '')[:500]}")
    conv_text = "\n".join(conversation)

    prompt = f"""아래는 정부 지원사업 상담에서 사용자가 "도움이 됐다"고 평가한 고품질 대화입니다.
이 대화에서 다른 사용자에게도 재사용 가능한 지식을 추출하세요.

공고: {title}
카테고리: {category}
결론: {conclusion}

[대화 내용]
{conv_text[:6000]}

[추출 요청]
아래 JSON 배열 형식으로 추출하세요. 최소 1개, 최대 3개:

[
  {{
    "type": "faq",
    "question": "다른 사용자도 물을 만한 일반적인 질문",
    "answer": "이 대화에서 AI가 잘 답변한 내용 요약 (200자 이내)",
    "confidence": 0.7~0.9
  }},
  {{
    "type": "insight",
    "insight": "이 대화에서 발견된 실무적 인사이트 (예: A자금 신청 시 B서류가 핵심)",
    "confidence": 0.6~0.8
  }}
]

규칙:
1. 해당 공고에만 해당하는 너무 구체적인 내용은 제외 (일반화 가능한 것만)
2. 질문은 다른 사용자가 검색할 만한 자연어로
3. 답변은 핵심만 간결하게 (구체적 수치 포함)
4. 순수 JSON 배열만 반환

순수 JSON만 반환하세요."""

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            "models/gemini-2.0-flash",
            generation_config={"max_output_tokens": 2048, "temperature": 0.2}
        )
        response = model.generate_content(prompt)
        raw = response.text.strip()

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        items = json.loads(raw)
        if not isinstance(items, list):
            return 0

        cur = db_conn.cursor()
        saved = 0

        for item in items[:3]:
            item_type = item.get("type", "faq")
            confidence = min(max(float(item.get("confidence", 0.7)), 0.3), 0.95)

            if item_type == "faq" and item.get("question") and item.get("answer"):
                content = {
                    "question": item["question"],
                    "answer": item["answer"],
                    "context": f"자동학습: {title[:30]} 상담에서 추출",
                    "source_announcement_id": announcement_id,
                }
            elif item_type == "insight" and item.get("insight"):
                content = {
                    "related_ids": [announcement_id],
                    "relationship": item["insight"],
                }
            else:
                continue

            try:
                cur.execute("""
                    INSERT INTO knowledge_base (source, knowledge_type, category, announcement_id, content, confidence)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                """, ("auto_learn", item_type, category, announcement_id,
                      json.dumps(content, ensure_ascii=False), confidence))
                saved += 1
            except Exception as e:
                print(f"[AutoLearner] Insert error: {e}")

        db_conn.commit()
        return saved

    except Exception as e:
        print(f"[AutoLearner] Error: {e}")
        traceback.print_exc()
        return 0


def process_helpful_feedback(
    consult_log_id: int,
    db_conn,
) -> int:
    """helpful 피드백이 달린 상담 로그를 학습 처리

    feedback 엔드포인트에서 호출.
    """
    try:
        cur = db_conn.cursor()
        cur.execute("""
            SELECT cl.announcement_id, cl.messages, cl.conclusion,
                   a.title, a.category
            FROM ai_consult_logs cl
            JOIN announcements a ON cl.announcement_id = a.announcement_id
            WHERE cl.id = %s
        """, (consult_log_id,))
        row = cur.fetchone()
        if not row:
            return 0

        messages = row["messages"]
        if isinstance(messages, str):
            messages = json.loads(messages)

        return extract_quality_knowledge(
            announcement_id=row["announcement_id"],
            category=row["category"] or "기타",
            title=row["title"] or "",
            messages=messages,
            conclusion=row["conclusion"] or "",
            db_conn=db_conn,
        )
    except Exception as e:
        print(f"[AutoLearner] process_helpful error: {e}")
        return 0
