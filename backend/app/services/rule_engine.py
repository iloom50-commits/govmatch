from typing import Dict, Any, List, Optional
from datetime import datetime, date

# 광역시/도 장문명 → 표준 단문명
REGION_NORMALIZE = {
    "경상남도": "경남", "경상북도": "경북",
    "전라남도": "전남", "전라북도": "전북",
    "전북특별자치도": "전북", "전남특별자치도": "전남",
    "충청남도": "충남", "충청북도": "충북",
    "강원특별자치도": "강원", "강원도": "강원",
    "제주특별자치도": "제주", "제주도": "제주",
    "인천광역시": "인천", "부산광역시": "부산",
    "대구광역시": "대구", "광주광역시": "광주",
    "대전광역시": "대전", "울산광역시": "울산",
    "서울특별시": "서울", "세종특별자치시": "세종",
    "경기도": "경기",
}

# 도 prefix 없이 단독으로 오는 시/군 → 광역시도
_CITY_TO_SIDO = {
    "구미시": "경북", "구미": "경북",
    "포항시": "경북", "포항": "경북",
    "경주시": "경북", "경주": "경북",
    "안동시": "경북", "안동": "경북",
    "창원시": "경남", "창원": "경남",
    "진주시": "경남", "진주": "경남",
    "통영시": "경남", "통영": "경남",
    "아산시": "충남", "아산": "충남",
    "천안시": "충남", "천안": "충남",
    "공주시": "충남", "공주": "충남",
    "청주시": "충북", "청주": "충북",
    "충주시": "충북", "충주": "충북",
    "전주시": "전북", "전주": "전북",
    "군산시": "전북", "군산": "전북",
    "익산시": "전북", "익산": "전북",
    "목포시": "전남", "목포": "전남",
    "여수시": "전남", "여수": "전남",
    "순천시": "전남", "순천": "전남",
    "평창군": "강원", "평창": "강원",
    "춘천시": "강원", "춘천": "강원",
    "원주시": "강원", "원주": "강원",
    "강릉시": "강원", "강릉": "강원",
    "과천시": "경기", "과천": "경기",
    "수원시": "경기", "수원": "경기",
    "성남시": "경기", "성남": "경기",
    "고양시": "경기", "고양": "경기",
    "용인시": "경기", "용인": "경기",
    "부천시": "경기", "부천": "경기",
    "안산시": "경기", "안산": "경기",
    "안양시": "경기", "안양": "경기",
    "화성시": "경기", "화성": "경기",
    "평택시": "경기", "평택": "경기",
    # 창조경제혁신센터 형태 (primary city 기준)
    "광주전라제주센터": "광주",
    "대구경북센터": "대구",
    "서울인천센터": "서울",
    "세종대전충청센터": "세종",
    "서울ㆍ경기ㆍ인천": "수도권",
    "서울·경기·인천": "수도권",
}

_STANDARD_REGIONS = {
    "전국", "서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
    "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
    "수도권", "All", "온라인", "해외", "기타",
}


def _normalize_region(region) -> str:
    """rule_engine 내부 사용 — 매칭 로직에서 호출."""
    if not region:
        return ""
    if isinstance(region, list):
        region = region[0] if region else ""
    if not region:
        return ""
    r = str(region).strip()
    if r in REGION_NORMALIZE:
        return REGION_NORMALIZE[r]
    parts = r.replace("  ", " ").split()
    if len(parts) >= 2:
        sido = REGION_NORMALIZE.get(parts[0], parts[0])
        if sido in ("서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"):
            return sido
    for full, short in REGION_NORMALIZE.items():
        if r.startswith(full) or r.startswith(short):
            return short
    return r


def normalize_region_for_save(region) -> Optional[str]:
    """스크래퍼 저장 시 region 정규화. 비표준 시/군명도 광역시도로 변환."""
    if not region:
        return None
    r = str(region).strip()
    if not r:
        return None
    # 1. 이미 표준값
    if r in _STANDARD_REGIONS:
        return r
    # 2. 광역시/도 장문명
    if r in REGION_NORMALIZE:
        return REGION_NORMALIZE[r]
    # 3. 시/군 단독 매핑
    if r in _CITY_TO_SIDO:
        return _CITY_TO_SIDO[r]
    # 4. "경기도 시흥시" 형태 → 첫 번째 부분이 광역시도이면 추출
    parts = r.replace("  ", " ").split()
    if len(parts) >= 2:
        sido = REGION_NORMALIZE.get(parts[0], _CITY_TO_SIDO.get(parts[0], parts[0]))
        if sido in _STANDARD_REGIONS:
            return sido
    # 5. 접두사 매핑
    for full, short in REGION_NORMALIZE.items():
        if r.startswith(full):
            return short
    for city, sido in _CITY_TO_SIDO.items():
        if r.startswith(city):
            return sido
    return r  # 알 수 없는 값은 원본 유지


# ─── category 정규화 ────────────────────────────────────────────

VALID_CATEGORIES = {
    "복지", "자금·지원", "교육", "의료", "출산", "인력·교육", "기술·개발",
    "기타", "주거", "창업·스케일업", "정보", "금융", "수출·판로", "경영·법률",
    "창업지원", "직업훈련", "장애", "R&D",
}

_CATEGORY_NORMALIZE = {
    "Entrepreneurship": "창업지원",
    "entrepreneurship": "창업지원",
    "고용·창업": "창업지원",
    "사회적기업": "창업지원",
    "저소득": "복지",
    "취업": "인력·교육",
    "환경": "기술·개발",
    "에너지": "기술·개발",
    "농업": "기타",
    "콘텐츠기업지원센터": "기타",
    "문화콘텐츠센터": "기타",
}

# (키워드 리스트, 카테고리) — 앞쪽일수록 우선순위 높음
_CATEGORY_KEYWORDS = [
    (["R&D", "연구개발", "기술개발", "연구·개발"], "R&D"),
    (["수출", "해외진출", "글로벌진출", "수출바우처", "무역", "판로"], "수출·판로"),
    (["훈련", "직업훈련", "직업교육", "국가기술자격", "기능장", "기능사", "명장"], "직업훈련"),
    (["창업", "스타트업", "예비창업"], "창업지원"),
    (["기술", "디지털전환", "스마트공장", "ICT", "AI", "SW개발", "소프트웨어"], "기술·개발"),
    # 출산이 의료보다 앞: "임산부 의료비" → 임산부(출산) 우선
    (["출산", "임신", "임산부", "산모", "육아", "보육", "어린이집"], "출산"),
    (["의료비", "진료비", "건강검진", "의약품"], "의료"),
    (["주거급여", "전세대출", "임대주택", "월세지원", "주거지원"], "주거"),
    (["장애수당", "장애급여", "활동지원", "장애인"], "장애"),
    (["복지", "생계급여", "기초생활", "차상위", "한부모", "긴급복지"], "복지"),
    (["자금지원", "보조금", "보조사업", "지원금", "융자"], "자금·지원"),
    (["보증", "투자유치", "펀드", "금융지원"], "금융"),
    (["인력채용", "고용지원", "일자리창출", "취업연계"], "인력·교육"),
    (["경영지원", "법률자문", "특허", "지식재산"], "경영·법률"),
    (["교육", "역량강화", "컨설팅", "멘토링"], "교육"),
]


def normalize_category(category) -> Optional[str]:
    """비표준 category 값을 표준 VALID_CATEGORIES 중 하나로 변환."""
    if not category:
        return None
    c = str(category).strip()
    if not c:
        return None
    if c in VALID_CATEGORIES:
        return c
    if c in _CATEGORY_NORMALIZE:
        return _CATEGORY_NORMALIZE[c]
    return c  # 알 수 없는 값은 원본 유지 (AI가 추후 보강)


def infer_category_from_title(title: str) -> Optional[str]:
    """공고 제목 키워드 기반 category 추론. 매칭 없으면 None."""
    if not title:
        return None
    for keywords, cat in _CATEGORY_KEYWORDS:
        if any(kw in title for kw in keywords):
            return cat
    return None


class RuleEngine:
    """정부지원사업 적합성 판별을 위한 규칙 엔진"""

    def evaluate(self, profile: Dict[str, Any], eligibility: Dict[str, Any]) -> Dict[str, Any]:
        reasons = []
        is_eligible = True

        if not eligibility:
            return {"is_eligible": True, "reasons": ["세부 자격 요건 분석 중 (기본 요건 검토 완료)"]}

        # 업력 계산 (공통)
        company_years = None
        if profile.get("establishment_date"):
            try:
                est_val = profile["establishment_date"]
                if isinstance(est_val, (date, datetime)):
                    est_date = datetime(est_val.year, est_val.month, est_val.day)
                else:
                    est_date = datetime.strptime(str(est_val), "%Y-%m-%d")
                company_years = (datetime.now() - est_date).days / 365.25
            except (ValueError, TypeError):
                pass

        # 1. 최대 업력 제한 (예: 창업 7년 이하만 지원)
        if eligibility.get("max_founding_years") is not None and company_years is not None:
            if company_years > eligibility["max_founding_years"]:
                is_eligible = False
                reasons.append(f"업력 초과 (제한 {eligibility['max_founding_years']}년, 현재 {company_years:.1f}년)")

        # 2. 최소 업력 제한 (예: 창업 1년 이상만 지원)
        if eligibility.get("min_founding_years") is not None and company_years is not None:
            if company_years < eligibility["min_founding_years"]:
                is_eligible = False
                reasons.append(f"업력 부족 (최소 {eligibility['min_founding_years']}년, 현재 {company_years:.1f}년)")

        # 3. 지역 제한 체크 (정규화 포함)
        region_restriction = _normalize_region(eligibility.get("region_restriction") or "전국")
        user_city = _normalize_region(profile.get("address_city") or "")
        if region_restriction and region_restriction != "전국" and user_city:
            if region_restriction not in user_city and user_city not in region_restriction:
                is_eligible = False
                reasons.append(f"지역 불일치 (제한: {region_restriction})")

        # 인원/매출 매핑
        emp_map = {
            "5인 미만": 0, "5인~10인": 5, "10인~30인": 10, "30인~50인": 30, "50인 이상": 50,
            "UNDER_5": 0, "5_TO_10": 5, "10_TO_50": 10, "OVER_50": 50,
        }
        rev_map = {
            "1억 미만": 0, "1억~5억": 1e8, "5억~10억": 5e8, "10억~50억": 10e8, "50억 이상": 50e8,
            "UNDER_1B": 0, "1B_TO_5B": 1e8, "5B_TO_10B": 5e8, "OVER_10B": 50e8,
        }
        company_emp = emp_map.get(profile.get("employee_count_bracket") or profile.get("employees"), -1)
        company_rev = rev_map.get(profile.get("revenue_bracket") or profile.get("revenue"), -1)

        # 4. 최소 인원 (min_employee_count)
        min_emp = eligibility.get("min_employee_count")
        try:
            min_emp = float(min_emp) if min_emp is not None else None
        except (ValueError, TypeError):
            min_emp = None
        if min_emp and company_emp >= 0 and company_emp < min_emp:
            is_eligible = False
            reasons.append(f"인력 부족 (최소 {int(min_emp)}인)")

        # 5. 최대 인원 (max_employee_count) — 중소기업 기준 초과 여부
        max_emp = eligibility.get("max_employee_count")
        try:
            max_emp = float(max_emp) if max_emp is not None else None
        except (ValueError, TypeError):
            max_emp = None
        if max_emp and company_emp >= 0 and company_emp > max_emp:
            is_eligible = False
            reasons.append(f"인원 초과 (최대 {int(max_emp)}인)")

        # 6. 최대 매출 (max_revenue) — 지원 대상 규모 상한
        max_rev = eligibility.get("max_revenue")
        try:
            max_rev = float(max_rev) if max_rev is not None else None
        except (ValueError, TypeError):
            max_rev = None
        if max_rev and company_rev >= 0 and company_rev > max_rev:
            is_eligible = False
            reasons.append(f"매출 초과 (최대 {max_rev/1e8:.0f}억)")

        return {
            "is_eligible": is_eligible,
            "reasons": reasons if reasons else ["모든 기본 자격 조건 충족"],
        }


rule_engine = RuleEngine()
