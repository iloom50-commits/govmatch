"""Schema 강제 Gemini 추출기 — 자연어 응답 → 구조화 정보.

Function Calling과 병행 사용하기 위한 2단계 파이프라인의 두 번째 단계.

원칙:
- 첫 번째 Gemini 호출은 Function Calling으로 자연어 답변 생성 (기존 방식)
- 이 추출기는 별도 짧은 호출로 Schema 강제하여 구조화 정보만 추출
- 정규식 extractor(extract_profile_info)와 함께 이중 안전망 구성
"""

import os
import json
import logging
from typing import Dict, Optional

from .schemas import EXTRACTED_INFO_SCHEMA  # noqa: F401 (reference)

# Schema 강제용 간소화 버전 — description 제거, 필수 필드 없음 (모두 optional)
# Gemini response_schema는 한글 description에 토큰 많이 먹고 복잡할수록 실패율 ↑
_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "address_city": {"type": "string"},
        "establishment_date": {"type": "string"},
        "revenue_bracket": {"type": "string"},
        "employee_count_bracket": {"type": "string"},
        "age_range": {"type": "string"},
        "income_level": {"type": "string"},
        "family_type": {"type": "string"},
        "employment_status": {"type": "string"},
        "housing_status": {"type": "string"},
        "industry_code": {"type": "string"},
        "company_name": {"type": "string"},
        "interests": {"type": "array", "items": {"type": "string"}},
    },
}

logger = logging.getLogger(__name__)


_EXTRACT_PROMPT = """다음 대화에서 사용자 프로필 정보를 추출하여 JSON으로 반환.

[사용자 메시지]
{user_msg}

[AI 답변 (참고용)]
{ai_reply}

[추출 규칙]
- 명시적 언급만 추출. 추측 금지.
- address_city: 17개 시도 중 하나 (예: '서울', '경기')
- establishment_date: YYYY-MM-DD (연도만 알면 YYYY-01-01)
- revenue_bracket: '1억 미만' / '1억~5억' / '5억~10억' / '10억~50억' / '50억~100억' / '100억 이상'
- employee_count_bracket: '5인 미만' / '5~10인' / '10~30인' / '30~50인' / '50~100인' / '100인 이상'
- age_range: '20대' / '30대' / '40대' / '50대' / '60대 이상'
- income_level: '기초생활' / '차상위' / '중위50%이하' / '중위75%이하' / '중위100%이하' / '해당없음'
- family_type: '1인가구' / '다자녀' / '한부모' / '신혼부부' / '다문화' / '일반' / '해당없음'
- employment_status: '재직자' / '구직자' / '자영업' / '프리랜서' / '학생' / '해당없음'
- housing_status: '자가' / '전세' / '월세' / '임대' / '해당없음'
- interests: 대화에서 언급된 관심 분야 배열 (예: ['정책자금', 'R&D'])
- industry_code: 한국표준산업분류 2자리 코드 (명시된 경우만)
- company_name: 회사명 (명시된 경우만)

없는 정보는 해당 필드를 완전히 생략. 빈 문자열 대신 필드 자체를 빼는 것.
"""


def schema_extract_profile(user_msg: str, ai_reply: str, api_key: Optional[str] = None) -> Dict:
    """Gemini에게 Schema 강제로 프로필 정보 추출 요청.

    Args:
        user_msg: 사용자 마지막 메시지
        ai_reply: AI 답변 (맥락 참고용)
        api_key: GEMINI_API_KEY (None이면 환경변수)

    Returns:
        EXTRACTED_INFO_SCHEMA에 맞는 dict (빈 dict일 수 있음)
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        return {}

    try:
        import google.generativeai as genai
    except ImportError:
        return {}

    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel(
            "models/gemini-2.5-flash",
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": _EXTRACT_SCHEMA,
                "temperature": 0.1,
                "max_output_tokens": 2048,
            },
        )

        prompt = _EXTRACT_PROMPT.format(
            user_msg=(user_msg or "")[:500],
            ai_reply=(ai_reply or "")[:800],
        )
        response = model.generate_content(prompt)
        text = response.text or "{}"
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"[schema_extract] error: {e}")
        return {}
