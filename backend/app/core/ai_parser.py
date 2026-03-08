import json

AI_SYSTEM_PROMPT = """
너는 정부 지원사업 공고 분석 전문가다. 주어진 공고문 텍스트를 읽고 아래 JSON 형식으로만 응답해라.

- title: 공고 명칭
- region: 전국/서울/부산 중 해당 지역
- industry: 대상 업종 코드 또는 명칭
- limit_year: 설립 몇 년 미만 지원 가능인지 (숫자만 추출, 없으면 99)
- summary: 기업 대표가 읽었을 때 10초 안에 이해되는 핵심 요약 (3줄 이내)

[주의사항]
1. 확실하지 않은 정보는 'NULL'로 표시해라.
2. 숫자는 정수로만 추출해라 (예: '1억원' -> 100000000).
3. JSON 외의 다른 말은 일절 하지 마라.
"""

def get_parser_prompt():
    return AI_SYSTEM_PROMPT

def parse_ai_response(response_text):
    """
    Parses the JSON response from the AI agent.
    """
    try:
        # Simple cleanup in case of markdown blocks
        clean_text = response_text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_text)
    except Exception as e:
        return {"error": "Failed to parse AI response", "raw": response_text}

if __name__ == "__main__":
    print("AI System Prompt Loaded:")
    print(AI_SYSTEM_PROMPT)
