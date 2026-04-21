"""정규식/키워드 기반 엔티티 추출.

AI가 `extracted_info`에 채우지 못한 필드를 코드가 보완.
Schema 강제 + 이 extractor = 이중 안전망.
"""

import re
from typing import Dict, List


REGIONS = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
]

INTEREST_KEYWORDS = {
    "정책자금": ["정책자금", "융자", "대출", "운전자금", "시설자금"],
    "R&D": ["R&D", "연구개발", "기술개발", "신기술"],
    "수출": ["수출", "해외진출", "바우처", "FTA"],
    "창업": ["창업", "예비창업", "재창업", "스타트업"],
    "고용": ["고용", "채용", "인력", "일자리"],
    "스마트공장": ["스마트공장", "스마트팩토리", "제조혁신"],
    "ESG": ["ESG", "친환경", "탄소중립", "재생에너지"],
    "사회적기업": ["사회적기업", "예비사회적기업", "사회적가치"],
}

AGE_PATTERNS = {
    r"(\d{1,2})살|만\s*(\d{1,2})세": "from_age",
    r"20대": "20대",
    r"30대": "30대",
    r"40대": "40대",
    r"50대": "50대",
    r"60대|은퇴": "60대 이상",
}

REVENUE_PATTERNS = [
    (r"매출\s*1억\s*미만|영세", "1억 미만"),
    (r"매출\s*1~5억|매출\s*1-5억", "1억~5억"),
    (r"매출\s*5~10억|매출\s*5-10억", "5억~10억"),
    (r"매출\s*10~50억", "10억~50억"),
    (r"매출\s*50~100억", "50억~100억"),
    (r"매출\s*100억|중견|대기업", "100억 이상"),
]

EMPLOYEE_PATTERNS = [
    (r"(\d+)\s*인\s*미만|1인|혼자", None),  # 특별 처리
    (r"5인\s*미만", "5인 미만"),
    (r"10인\s*미만|5~10인", "5~10인"),
    (r"30인\s*미만|10~30인", "10~30인"),
    (r"50인\s*미만|30~50인", "30~50인"),
    (r"100인\s*미만|50~100인", "50~100인"),
    (r"100인\s*이상", "100인 이상"),
]


def extract_profile_info(user_text: str, ai_extracted: dict = None) -> Dict:
    """사용자 대화 텍스트 + AI 추출 결과를 병합.

    우선순위: AI 추출 > 정규식 추출 (AI가 놓친 것만 보완).
    """
    result = dict(ai_extracted or {})
    text = user_text or ""

    # 지역
    if not result.get("address_city"):
        for r in REGIONS:
            if r in text:
                result["address_city"] = r
                break

    # 설립일 (연도)
    if not result.get("establishment_date"):
        # "2019년", "2019년 설립", "작년", "올해"
        now_year = 2026
        if "작년" in text:
            result["establishment_date"] = f"{now_year - 1}-01-01"
        elif "올해" in text:
            result["establishment_date"] = f"{now_year}-01-01"
        else:
            m = re.search(r"(20\d{2})\s*년", text)
            if m:
                result["establishment_date"] = f"{m.group(1)}-01-01"

    # 매출
    if not result.get("revenue_bracket"):
        for pat, label in REVENUE_PATTERNS:
            if re.search(pat, text):
                result["revenue_bracket"] = label
                break

    # 직원수
    if not result.get("employee_count_bracket"):
        for pat, label in EMPLOYEE_PATTERNS:
            if re.search(pat, text):
                if label:
                    result["employee_count_bracket"] = label
                break

    # 연령
    if not result.get("age_range"):
        for pat, label in AGE_PATTERNS.items():
            m = re.search(pat, text)
            if m:
                if label == "from_age":
                    age = int(m.group(1) or m.group(2))
                    if age < 30: result["age_range"] = "20대"
                    elif age < 40: result["age_range"] = "30대"
                    elif age < 50: result["age_range"] = "40대"
                    elif age < 60: result["age_range"] = "50대"
                    else: result["age_range"] = "60대 이상"
                else:
                    result["age_range"] = label
                break

    # 관심 분야 (키워드 매칭, 여러 개 가능)
    if not result.get("interests"):
        found = []
        text_lower = text.lower()
        for tag, kws in INTEREST_KEYWORDS.items():
            if any(kw.lower() in text_lower for kw in kws):
                found.append(tag)
        if found:
            result["interests"] = found

    return result


def extract_mentioned_announcement_ids(messages: List[Dict]) -> List[int]:
    """AI 메시지에서 언급된 announcement_id 추출 (중복 방지용)."""
    ids = set()
    for m in messages:
        if m.get("role") != "assistant":
            continue
        text = m.get("text", "")
        # "[공고ID: 1234]" 패턴
        for hit in re.findall(r"공고ID\s*[:：]\s*(\d+)", text):
            try:
                ids.add(int(hit))
            except ValueError:
                pass
    return sorted(ids)
