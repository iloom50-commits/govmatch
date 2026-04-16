import re
import psycopg2
import psycopg2.extras
import datetime
import json
from app.services.rule_engine import rule_engine, _normalize_region
from app.config import DATABASE_URL

def get_db_connection(database_url=DATABASE_URL):
    conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# 관심 분야 태그 → 매칭 키워드 확장 맵
INTEREST_KEYWORD_MAP = {
    "창업지원":   ["창업", "스타트업", "벤처", "예비창업", "창업패키지", "초기기업"],
    "기술개발":   ["R&D", "연구개발", "기술개발", "기술혁신", "연구", "기술", "AI", "인공지능", "혁신기술"],
    "수출마케팅": ["수출", "해외", "글로벌", "무역", "수출마케팅", "해외판로", "해외진출", "수출지원", "해외마케팅", "KOTRA"],
    "고용지원":   ["고용", "채용", "일자리", "인력", "청년", "근로자", "고용지원", "인재", "취업", "고용안정", "고용장려", "인건비", "장려금"],
    "시설개선":   ["시설", "설비", "인테리어", "리모델링", "환경개선", "공간", "장비"],
    "정책자금":   ["정책자금", "융자", "대출", "보증", "자금", "금융", "지원금", "보조금"],
    "디지털전환": ["디지털", "스마트", "IT", "정보화", "비대면", "플랫폼", "소프트웨어", "AI", "인공지능", "DX", "ICT"],
    "판로개척":   ["판로", "마케팅", "홍보", "온라인", "판매", "유통", "쇼핑몰", "B2B", "B2C"],
    "교육훈련":   ["교육", "훈련", "컨설팅", "멘토링", "역량", "강의", "아카데미"],
    "에너지환경": ["에너지", "환경", "친환경", "탄소", "녹색", "ESG", "수소", "태양광", "신재생"],
    "소상공인":   ["소상공인", "자영업", "골목상권", "전통시장", "소규모"],
    "R&D":        ["R&D", "연구개발", "기술개발", "혁신", "연구", "AI", "인공지능"],
}

# 지원 대상 기업 유형 분류
EXCLUSIVE_BIZ_TYPES = {"소상공인", "예비창업자", "사회적기업", "예비사회적기업", "마을기업", "자활기업", "수출기업"}

# 특정 대상 제한 키워드 — 제목에 포함 시 해당 대상이 아니면 제외
RESTRICTED_TARGET_KEYWORDS = {
    "여성": ["여성", "여성기업", "여성창업"],
    "장애인": ["장애인", "장애인기업"],
    "군인/보훈": ["보훈", "제대군인", "군인"],
    "농업": ["농업인", "농업법인", "영농"],
    "어업": ["어업인", "수산업"],
    "사회적경제": ["사회적기업", "마을기업", "자활기업", "협동조합"],
}

# 카테고리 정규화 (AI가 영어/한글 혼재로 추출)
CATEGORY_NORMALIZE = {
    # 영어
    "Tech": "기술", "Global": "수출", "Entrepreneurship": "창업",
    "Employment": "인력", "Loan": "금융", "Investment": "금융",
    "Marketing": "경영", "General Business Support": "경영",
    "Small Business/Startup": "창업", "SME Support": "경영",
    "R&D": "기술", "R&D/Digital": "기술", "Food Industry": "경영",
    "General": "경영", "Tourism": "수출",
    # 멀티값 (쉼표 구분)
    "Tech, Global, 바우처": "기술", "Tech, Global, R&D": "기술",
    "Tech, Global, Entrepreneurship": "기술", "Tech, Global": "기술",
    "Global, Tech": "수출", "Global, Culture, Animation, Production": "수출",
    "Entrepreneurship, Tech, Consulting": "창업",
    # 비표준 한글
    "판로": "경영", "판로지원": "경영", "고용": "인력", "일자리": "인력",
    "환경안전": "기술", "환경개선": "경영", "컨설팅": "경영",
    "문화/예술": "경영", "농림축산": "경영", "사회적기업": "창업",
    "기업지원": "경영", "경영/승계": "경영", "지원사업": "경영",
    "지역경제": "경영", "재기": "창업", "산업/기술": "기술",
    "패션": "경영", "수상": "경영",
    # 정보 카테고리 — 제목 기반으로 재분류 (title에서 매칭)
    "정보": "정보",
    "복지": "복지", "주거": "주거", "교육": "교육",
    "청년": "청년", "보건의료": "복지",
}

# 관심분야 → 카테고리 매핑 (관심분야가 있는 카테고리 공고를 부스트)
INTEREST_CATEGORY_MAP = {
    "기술개발":   ["기술", "R&D"],
    "창업지원":   ["창업", "경영"],
    "수출마케팅": ["수출"],
    "고용지원":   ["인력", "고용"],
    "청년고용":   ["인력", "고용"],
    "정책자금":   ["금융", "경영"],
    "디지털전환": ["기술", "경영", "정보"],
    "판로개척":   ["내수", "수출", "경영"],
    "교육훈련":   ["인력", "경영"],
    "에너지환경": ["기술", "경영"],
    "소상공인":   ["경영", "내수", "소상공인"],
    "R&D":        ["기술", "R&D"],
    "시설개선":   ["경영"],
}

# 단어 단위 유의어 확장 맵 (커스텀 입력 키워드 → 유사 표현)
# 태그 단위가 아닌 개별 키워드 단위로 확장하여 정밀도 유지
SYNONYM_MAP = {
    "컨설팅":   ["컨설팅", "자문", "경영지도", "경영컨설팅", "진단"],
    "전문가":   ["전문가", "멘토", "전문인력", "자문위원", "코치"],
    "수행기관": ["수행기관", "용역", "위탁", "대행", "수탁기관"],
    "용역기관": ["용역기관", "용역", "수행기관", "위탁", "대행"],
    "인증":     ["인증", "인증서", "ISO", "품질인증", "기술인증", "인정"],
    "특허":     ["특허", "지식재산", "IP", "실용신안", "지재권"],
    "바우처":   ["바우처", "쿠폰", "이용권", "지원권"],
    "사업화":   ["사업화", "상용화", "제품화", "양산", "시제품"],
    "입주":     ["입주", "센터입주", "보육", "인큐베이팅", "창업공간"],
    "해외":     ["해외", "수출", "글로벌", "해외진출", "해외시장"],
    "디자인":   ["디자인", "브랜딩", "패키지디자인", "BI", "CI"],
    "홍보":     ["홍보", "마케팅", "광고", "프로모션", "SNS마케팅"],
    "네트워킹": ["네트워킹", "네트워크", "교류", "매칭", "협업"],
}

# 카테고리별 결과 최대 건수 (다양성 보장)
CATEGORY_CAP = 8


def _is_soho(user_profile: dict) -> bool:
    """매출·인원 기준으로 소상공인 여부 판별"""
    rev_bracket = user_profile.get("revenue_bracket") or user_profile.get("revenue", "")
    emp_bracket = user_profile.get("employee_count_bracket") or user_profile.get("employees", "")
    small_rev = rev_bracket in ("1억 미만", "1억~5억", "UNDER_1B", "1B_TO_5B")
    small_emp = emp_bracket in ("5인 미만", "5인~10인", "UNDER_5", "5_TO_10")
    return small_rev and small_emp


def _get_biz_types(eligibility_logic: dict) -> list:
    """eligibility_logic에서 business_type 목록 추출"""
    bt = eligibility_logic.get("business_type", [])
    if isinstance(bt, list):
        return bt
    if isinstance(bt, str) and bt:
        return [bt]
    return []


def get_matches_for_user(user_profile):
    conn = get_db_connection()
    cursor = conn.cursor()

    # 업력 계산
    est_date_str = user_profile.get("establishment_date", "2020-01-01")
    try:
        if isinstance(est_date_str, (datetime.date, datetime.datetime)):
            est_date = datetime.datetime(est_date_str.year, est_date_str.month, est_date_str.day)
        else:
            est_date = datetime.datetime.strptime(str(est_date_str), "%Y-%m-%d")
    except (ValueError, AttributeError):
        est_date = datetime.datetime(2020, 1, 1)
    today = datetime.date.today()
    company_age = today.year - est_date.year - ((today.month, today.day) < (est_date.month, est_date.day))

    # 매출/인원 브래킷 → 수치 변환
    revenue_map = {
        "UNDER_1B": 100000000, "1B_TO_5B": 500000000, "5B_TO_10B": 1000000000, "OVER_10B": 10000000000,
        "1억 미만": 100000000, "1억~5억": 500000000, "5억~10억": 1000000000,
        "10억~50억": 5000000000, "50억 이상": 10000000000,
    }
    employee_map = {
        "UNDER_5": 5, "5_TO_10": 10, "10_TO_50": 50, "OVER_50": 100,
        "5인 미만": 5, "5인~10인": 10, "10인~30인": 30, "30인~50인": 50, "50인 이상": 100,
    }
    user_rev = revenue_map.get(user_profile.get("revenue_bracket") or user_profile.get("revenue"), 0)
    user_emp = employee_map.get(user_profile.get("employee_count_bracket") or user_profile.get("employees"), 0)

    # SQL 1차 필터: 마감 공고 제외 + deadline 없는 공고는 최근 60일 이내만
    # target_type 필터: business 매칭은 business/both만, individual은 individual/both만
    query = """
    SELECT announcement_id, title, region, category, department,
           support_amount, deadline_date, origin_source, created_at,
           COALESCE(target_type, 'business') AS target_type,
           origin_url, summary_text, eligibility_logic,
           established_years_limit, revenue_limit, employee_limit
    FROM announcements
    WHERE (established_years_limit IS NULL OR established_years_limit >= %s)
    AND (revenue_limit IS NULL OR revenue_limit >= %s)
    AND (employee_limit IS NULL OR employee_limit >= %s)
    AND (COALESCE(target_type, 'business') IN ('business', 'both'))
    AND (
        (deadline_date IS NOT NULL AND deadline_date >= CURRENT_DATE)
        OR (deadline_date IS NULL AND created_at >= CURRENT_DATE - INTERVAL '60 days')
    )
    """
    cursor.execute(query, (company_age, user_rev, user_emp))
    candidates = []
    for row in cursor.fetchall():
        d = dict(row)
        candidates.append(d)
    conn.close()

    if not candidates:
        return []

    # 사용자 정보 준비
    user_interests_raw = user_profile.get("interests") or ""
    user_interest_tags = [t.strip() for t in user_interests_raw.split(",") if t.strip()]

    # 관심분야 → 확장 키워드
    interest_keywords = []
    for tag in user_interest_tags:
        if tag in INTEREST_KEYWORD_MAP:
            # 프리셋 태그 → 해당 태그의 키워드 전체 확장
            interest_keywords.extend(INTEREST_KEYWORD_MAP[tag])
        elif tag in SYNONYM_MAP:
            # 커스텀 입력이 유의어맵에 있으면 → 유의어로 확장
            interest_keywords.extend(SYNONYM_MAP[tag])
        else:
            # 완전 커스텀 입력 → 그대로 키워드로 사용
            interest_keywords.append(tag)

    # 맞춤 키워드 추가 (custom_keywords)
    custom_kw_raw = user_profile.get("custom_keywords") or ""
    custom_kw_list = [k.strip() for k in custom_kw_raw.split(",") if k.strip()]
    interest_keywords.extend(custom_kw_list)

    is_soho = _is_soho(user_profile)

    # 사용자 보유 인증/자격 (certifications) — 복수, 콤마 구분 문자열
    user_certs_raw = user_profile.get("certifications") or ""
    user_certs = [c.strip() for c in user_certs_raw.split(",") if c.strip() and c.strip() != "없음"]
    has_female = any("여성" in c for c in user_certs)
    has_disabled = any("장애" in c for c in user_certs)
    has_social = any(("사회적" in c) or ("협동조합" in c) or ("마을기업" in c) for c in user_certs)
    has_venture = any("벤처" in c for c in user_certs)
    has_innobiz = any(("이노비즈" in c) or ("메인비즈" in c) for c in user_certs)

    # 업종 대분류 (KSIC 앞 2자리)
    user_ind_code = (user_profile.get("industry_code") or "")[:2]
    # 1차 산업/식품/문화 등 특수 업종 판별
    is_farmer = user_ind_code in ("01", "02", "03")  # 농업/임업/어업
    is_fishery = user_ind_code == "03"
    is_food_mfg = user_ind_code in ("10", "11")       # 식품제조
    is_culture = user_ind_code in ("58", "59", "60", "90", "91")  # 출판/영상/문화

    # 소재지 (1개, 자격 필터용) — address_city에서 첫 번째 실제 지역
    raw_city = user_profile.get("address_city", "")
    user_cities = [_normalize_region(c.strip()) for c in raw_city.split(",") if c.strip()] if raw_city else []
    # 소재지: 전국 제외한 첫 번째 지역
    home_city = next((c for c in user_cities if c not in ("전국", "")), "")

    # 관심 지역 (복수, 보너스용) — interest_regions 필드
    raw_interest_regions = user_profile.get("interest_regions", "")
    interest_regions = [_normalize_region(c.strip()) for c in raw_interest_regions.split(",") if c.strip() and c.strip() != "전국"] if raw_interest_regions else []

    # 소재지가 없으면 전국 취급 (모든 지역 공고 통과)
    has_home = bool(home_city)
    # bonus_cities = 소재지 + 관심지역 (보너스 점수용)
    bonus_cities = []
    if home_city:
        bonus_cities.append(home_city)
    bonus_cities.extend([r for r in interest_regions if r not in bonus_cities])

    results = []
    ineligible_results = []  # 자격 미달 — 후순위로 노출

    def _mark_ineligible(ad_obj, reason):
        """자격 미달 공고를 후순위 리스트에 추가하고 기본 필드 채움"""
        ad_obj["match_score"] = 0
        ad_obj["eligibility_status"] = "ineligible"
        ad_obj["ineligible_reason"] = reason
        ad_obj["recommendation_reason"] = reason
        ad_obj.pop("_category", None)
        ineligible_results.append(ad_obj)

    for ad in candidates:
        # eligibility_logic 파싱
        eligibility_logic = {}
        if ad.get("eligibility_logic"):
            try:
                eligibility_logic = json.loads(ad["eligibility_logic"])
            except (json.JSONDecodeError, TypeError):
                pass

        # RuleEngine 자격 검증 (업력/지역/인원/매출 하드 필터)
        rule_result = rule_engine.evaluate(user_profile, eligibility_logic)
        if not rule_result["is_eligible"]:
            _mark_ineligible(ad, "기본 자격 미달")
            continue

        title = ad.get("title", "")

        # 만료 공고 필터 — 제목에 작년 이전 연도가 있고 마감일이 없거나 지났으면 제외
        # (예: "2025년 ..." 공고가 2026년 4월에 노출되는 문제 차단)
        current_year = today.year
        title_year_match = re.search(r'(\d{4})년', title)
        if title_year_match:
            title_year = int(title_year_match.group(1))
            if title_year < current_year:
                # 마감일 명시가 있고 미래면 통과, 그 외 모두 제외
                dl = ad.get("deadline_date")
                if not dl:
                    continue
                try:
                    if isinstance(dl, (datetime.date, datetime.datetime)):
                        dl_date = dl if isinstance(dl, datetime.date) else dl.date()
                    else:
                        dl_date = datetime.datetime.strptime(str(dl), "%Y-%m-%d").date()
                    if dl_date < today:
                        continue
                except (ValueError, TypeError):
                    continue

        # 지역 필터: 관심지역이 아닌 곳의 지역 전용 공고만 제외
        # 지역 미표기/전국 공고는 항상 포함
        ad_region = _normalize_region(ad.get("region") or "")

        # 지역 필터: 소재지 기반 자격 필터
        # - 전국 공고(region=전국/빈값)는 항상 통과
        # - 지역 전용 공고는 소재지(home_city)가 일치해야 통과
        # - 관심지역(interest_regions)은 필터 안 함 (보너스만)
        if ad_region and ad_region not in ("전국", "", "All"):
            if has_home:
                # 소재지가 있으면: 소재지 일치만 통과
                if ad_region != home_city:
                    _mark_ineligible(ad, f"{ad_region} 지역 전용 (소재지 불일치)")
                    continue
            # 소재지 없으면 전국 취급 → 모든 지역 통과

        # 제목의 [도시명] 패턴으로 지역 특화 공고 판별
        bracket_city_match = re.search(
            r'\[(서울|경기|인천|부산|대구|대전|광주|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)\]',
            title
        )
        if bracket_city_match:
            title_city = bracket_city_match.group(1)
            if has_home and title_city != home_city:
                _mark_ineligible(ad, f"{title_city} 지역 전용 (소재지 불일치)")
                continue

        # business_type 하드 필터: 배타적 대상 유형이 지정된 경우
        ad_biz_types = _get_biz_types(eligibility_logic)
        biz_skipped = False
        if ad_biz_types:
            exclusive_types = [bt for bt in ad_biz_types if bt in EXCLUSIVE_BIZ_TYPES]
            if exclusive_types:
                # 소상공인 전용 → 비소상공인 제외
                if "소상공인" in exclusive_types and not is_soho:
                    if not any(bt in ad_biz_types for bt in ["중소기업", "스타트업", "기업"]):
                        _mark_ineligible(ad, "소상공인 전용 (사용자 비해당)")
                        biz_skipped = True
                # 수출기업 전용 → 수출 관심 없는 기업 제외
                if not biz_skipped and "수출기업" in exclusive_types and len(exclusive_types) == 1:
                    if "수출마케팅" not in user_interest_tags and "수출" not in user_interests_raw:
                        _mark_ineligible(ad, "수출기업 전용")
                        biz_skipped = True
                # 예비창업자 전용 → 기존 창업자 제외
                if not biz_skipped and "예비창업자" in exclusive_types and not any(bt in ad_biz_types for bt in ["중소기업", "스타트업"]):
                    if company_age > 0:
                        _mark_ineligible(ad, "예비창업자 전용")
                        biz_skipped = True
                # 사회적경제기업 전용 → 사회적기업/협동조합/마을기업 자격 없으면 제외
                if not biz_skipped:
                    social_types = [bt for bt in exclusive_types if bt in ("사회적기업", "예비사회적기업", "마을기업", "자활기업")]
                    if social_types and not has_social:
                        _mark_ineligible(ad, f"{social_types[0]} 전용 자격")
                        biz_skipped = True
        if biz_skipped:
            continue

        # 정보/안내 페이지 필터 — 실제 공고가 아닌 기관 소개 등 제외
        _info_page_keywords = ["소개", "안내 페이지", "지원시책", "지원 관련 기관", "상담 예약 현황"]
        if any(kw in title for kw in _info_page_keywords) and not any(kw in title for kw in ["모집", "공고", "신청", "접수"]):
            continue

        # 특정 대상 제한 필터 — 제목/본문의 대상 키워드와 사용자 certifications/업종 대조
        # 제목에 여성/장애인/농업/사회적경제 등 전용 키워드가 있는데 사용자 자격이 안 맞으면 후순위
        _el_kw_list = eligibility_logic.get("target_keywords", []) or []
        _el_ind_list = eligibility_logic.get("target_industries", []) or []
        _el_kw_text = " ".join(_el_kw_list) if isinstance(_el_kw_list, list) else str(_el_kw_list)
        _el_ind_text = " ".join(_el_ind_list) if isinstance(_el_ind_list, list) else str(_el_ind_list)
        _target_text = f"{title} {_el_kw_text} {_el_ind_text}"

        restricted_reason = None
        # 여성 전용 (기업 대상)
        if any(kw in _target_text for kw in ["여성기업", "여성창업", "여성경제인"]) and not has_female:
            restricted_reason = "여성기업 전용 자격"
        # 장애인 전용
        elif any(kw in _target_text for kw in ["장애인기업", "장애인창업", "장애인고용"]) and not has_disabled:
            restricted_reason = "장애인기업 전용 자격"
        # 보훈/제대군인 전용
        elif any(kw in _target_text for kw in ["보훈", "제대군인", "국가유공자"]):
            restricted_reason = "보훈/제대군인 전용 자격"
        # 농업/영농 전용 (제목 또는 AI 추출 업종에 농업이 있는 경우)
        elif (any(kw in title for kw in ["농업인", "농업법인", "영농", "농촌", "농가"]) or
              any("농업" in x for x in _el_ind_list if isinstance(x, str))) and not is_farmer:
            restricted_reason = "농업인/영농 전용"
        # 어업/수산 전용
        elif (any(kw in title for kw in ["어업인", "수산업", "수산가공"]) or
              any(("수산" in x) or ("어업" in x) for x in _el_ind_list if isinstance(x, str))) and not is_fishery:
            restricted_reason = "어업/수산업 전용"
        # 식품진흥/식품업 전용 (제조업 코드 C10/C11이 아니면 제외)
        elif (any(kw in title for kw in ["식품진흥", "식품산업진흥", "식품위생업"]) or
              any(("식품위생" in x) or ("식품산업" in x) for x in _el_ind_list if isinstance(x, str))) and not is_food_mfg:
            restricted_reason = "식품업 전용"
        # 사회적경제기업 전용 (제목 기반)
        elif any(kw in title for kw in ["사회적경제기업", "사회적기업", "마을기업", "자활기업", "협동조합"]) and not has_social:
            restricted_reason = "사회적경제기업 전용 자격"

        if restricted_reason:
            _mark_ineligible(ad, restricted_reason)
            continue

        # 검색 텍스트 구성
        raw_summary = ad.get("summary_text") or ""
        clean_summary = _strip_html(raw_summary)
        _kw = eligibility_logic.get("target_keywords", [])
        el_keywords = " ".join(_kw) if isinstance(_kw, list) else str(_kw or "")
        _ind = eligibility_logic.get("target_industries", [])
        el_industries = " ".join(_ind) if isinstance(_ind, list) else str(_ind or "")
        el_business_types = " ".join(ad_biz_types)
        search_text = f"{title} {clean_summary} {el_keywords} {el_industries} {el_business_types}".lower()

        # 카테고리 정규화 — "정보" 카테고리는 제목 기반 재분류
        raw_category = ad.get("category") or ""
        ad_category = CATEGORY_NORMALIZE.get(raw_category, raw_category)
        if ad_category in ("정보", ""):
            title_lower = title.lower()
            if any(kw in title_lower for kw in ["r&d", "연구개발", "기술개발", "기술혁신"]):
                ad_category = "기술"
            elif any(kw in title_lower for kw in ["창업", "예비창업", "스타트업"]):
                ad_category = "창업"
            elif any(kw in title_lower for kw in ["고용", "채용", "일자리", "인력"]):
                ad_category = "인력"
            elif any(kw in title_lower for kw in ["융자", "정책자금", "보증", "대출"]):
                ad_category = "금융"
            elif any(kw in title_lower for kw in ["수출", "바우처", "해외"]):
                ad_category = "수출"

        score = 0.0
        reasons = []

        # A. 기본 자격 (30점)
        score += 30.0

        # A-1. 지역 매칭 보너스
        # 소재지 일치: +20점 / 관심지역 일치: +8점
        ad_city_for_match = (bracket_city_match.group(1) if bracket_city_match else None) or \
                            (ad_region if ad_region and ad_region not in ("전국", "", "All") else None)
        if ad_city_for_match:
            if ad_city_for_match == home_city:
                score += 35.0
                reasons.append(f"{home_city} 소재지 지원사업")
            elif ad_city_for_match in interest_regions:
                score += 15.0
                reasons.append(f"{ad_city_for_match} 관심지역 지원사업")

        # B. 소상공인 매칭 (최대 20점)
        soho_keywords = ["소상공인", "자영업", "골목상권", "전통시장", "소규모"]
        ad_targets_soho = any(kw in search_text for kw in soho_keywords) or "소상공인" in ad_biz_types
        ad_targets_large = any(kw in search_text for kw in ["해외지사", "수출기업", "코스닥", "상장", "대기업"])

        if is_soho and ad_targets_soho:
            score += 20.0
            reasons.append("소상공인 전용 지원사업")
        elif is_soho and ad_targets_large:
            score -= 15.0
        elif not is_soho and ad_targets_soho:
            score -= 5.0

        # C. 관심분야 키워드 매칭 (최대 35점)
        if interest_keywords:
            matched_interests = [kw for kw in interest_keywords if kw.lower() in search_text]
            if matched_interests:
                interest_score = min(35.0, len(set(matched_interests)) * 6.0)
                score += interest_score
                for tag in user_interest_tags:
                    tag_kws = INTEREST_KEYWORD_MAP.get(tag, [tag])
                    if any(kw.lower() in search_text for kw in tag_kws):
                        reasons.append(f'"{tag}" 관심분야 부합')
                        break

        # C-2. 구체적 키워드 직접 매칭 부스트 (최대 30점)
        # custom_keywords(스마트공장, 바이오 등)가 제목에 직접 포함되면 최우선
        if custom_kw_list:
            title_lower = title.lower()
            direct_match = [kw for kw in custom_kw_list if kw.lower() in title_lower]
            if direct_match:
                score += min(30.0, len(direct_match) * 15.0)
                reasons.append(f'"{direct_match[0]}" 키워드 직접 매칭')

        # D. business_type 보너스 매칭 (최대 10점)
        if ad_biz_types and not ad_targets_soho:
            if "중소기업" in ad_biz_types and not is_soho:
                score += 5.0
            if "스타트업" in ad_biz_types and company_age <= 7:
                score += 5.0
                if not any("창업" in r for r in reasons):
                    reasons.append("스타트업 대상 지원사업")
            if "벤처기업" in ad_biz_types:
                score += 3.0

        # G. 카테고리-관심분야 매칭 보너스 (최대 20점)
        if ad_category:
            for tag in user_interest_tags:
                if ad_category in INTEREST_CATEGORY_MAP.get(tag, []):
                    score += 20.0
                    if not any(ad_category in r for r in reasons):
                        reasons.append(f"{ad_category} 분야 지원사업")
                    break

        # E-2. 업종 연관성 매칭 (최대 20점)
        user_ind = user_profile.get("industry_code") or ""
        if user_ind:
            # 업종코드 대분류 (앞 2자리)
            user_ind_major = user_ind[:2]
            # 공고 텍스트에서 업종 연관 키워드 검색
            INDUSTRY_KEYWORDS = {
                "62": ["소프트웨어", "IT", "정보통신", "디지털", "AI", "인공지능", "ICT", "플랫폼", "앱"],
                "56": ["음식", "외식", "요식", "식당", "프랜차이즈", "식품"],
                "10": ["식품", "제조", "가공식품", "식품제조"],
                "25": ["금속", "기계", "부품", "가공", "제조"],
                "26": ["전자", "반도체", "디스플레이", "전자부품"],
                "29": ["자동차", "차량", "모빌리티"],
                "21": ["바이오", "의약", "제약", "생명과학", "헬스케어"],
                "41": ["건설", "건축", "시공"],
                "47": ["소매", "유통", "판매", "쇼핑"],
                "49": ["물류", "운송", "배송", "택배"],
                "70": ["컨설팅", "전문서비스", "경영"],
                "85": ["교육", "학원", "훈련", "에듀"],
                "72": ["연구", "R&D", "연구개발", "바이오"],
                "74": ["디자인", "광고", "마케팅"],
            }
            ind_keywords = INDUSTRY_KEYWORDS.get(user_ind_major, [])
            if ind_keywords:
                ind_match_count = sum(1 for kw in ind_keywords if kw.lower() in search_text)
                if ind_match_count >= 2:
                    score += 20.0
                    reasons.append("업종 연관성 높음")
                elif ind_match_count == 1:
                    score += 10.0

        # F. 마감일 가중치 (최대 10점)
        if ad.get("deadline_date"):
            try:
                deadline_val = ad["deadline_date"]
                if isinstance(deadline_val, (datetime.date, datetime.datetime)):
                    deadline = deadline_val if isinstance(deadline_val, datetime.date) else deadline_val.date()
                else:
                    deadline = datetime.datetime.strptime(str(deadline_val), "%Y-%m-%d").date()
                days_left = (deadline - today).days
                if days_left < 0:
                    continue  # 만료 공고 제외
                # 마감일이 있는 공고 자체에 기본 보너스 (+3점)
                score += 3.0
                if days_left <= 7:
                    score += 7.0
                    reasons.append("마감 임박 (7일 이내)")
                elif days_left <= 14:
                    score += 4.0
                    reasons.append(f"마감 D-{days_left}")
                elif days_left <= 30:
                    score += 2.0
            except (ValueError, TypeError):
                pass

        # G. 사업 규모/유형 가산점 — 정책자금/R&D 등 인기 카테고리 우선
        title_lower = (ad.get("title") or "").lower()
        cat_lower = (ad.get("category") or "").lower()
        amount_str = (ad.get("support_amount") or "")

        # 정책자금/융자/보증: +12점 (인기 + 큰 금액)
        if any(k in title_lower for k in ["정책자금", "융자", "보증", "보증료"]) or "정책자금" in cat_lower or "보증" in cat_lower:
            score += 12.0
            if "정책자금" in title_lower or "정책자금" in cat_lower:
                reasons.append("정책자금")
            elif "보증" in title_lower or "보증" in cat_lower:
                reasons.append("보증")
            else:
                reasons.append("융자")
        # R&D: +8점
        elif "r&d" in title_lower or "연구개발" in title_lower or "기술개발" in title_lower:
            score += 8.0
            reasons.append("R&D")

        # 금액 기반 가산점 (큰 금액 우선)
        try:
            import re as _re
            num = 0
            if "억" in amount_str:
                m = _re.search(r'(\d+(?:\.\d+)?)\s*억', amount_str)
                if m:
                    num = float(m.group(1)) * 100000000
            elif "천만" in amount_str:
                m = _re.search(r'(\d+(?:\.\d+)?)\s*천만', amount_str)
                if m:
                    num = float(m.group(1)) * 10000000
            if num >= 1000000000:  # 10억+
                score += 8.0
            elif num >= 100000000:  # 1억+
                score += 4.0
            elif num >= 10000000:  # 1천만+
                score += 2.0
        except Exception:
            pass

        # 점수 100 캡 — 사용자 신뢰도 위해 0~100 정규화
        score = min(score, 100.0)
        ad["match_score"] = round(score, 1)
        ad["eligibility_status"] = "eligible"
        # recommendation_reason: "기본 자격" 제외하고 실제 매칭 이유만 표시
        meaningful_reasons = [r for r in reasons if "기본 지원 자격" not in r]
        ad["recommendation_reason"] = " / ".join(meaningful_reasons[:2]) if meaningful_reasons else "지원 자격 충족"
        ad["_category"] = ad_category  # 다양성 처리용 임시 필드
        results.append(ad)

    # 중복 공고 제거 (같은 제목) — eligible / ineligible 각각
    def _dedupe(lst):
        seen = set()
        out = []
        for r in lst:
            norm = re.sub(r'\s+', '', r.get("title", ""))
            if norm not in seen:
                seen.add(norm)
                out.append(r)
        return out
    results = _dedupe(results)
    ineligible_results = _dedupe(ineligible_results)

    # eligible에서 같은 제목이 나온 건 ineligible에서 제거 (중복 노출 방지)
    eligible_titles = {re.sub(r'\s+', '', r.get("title", "")) for r in results}
    ineligible_results = [r for r in ineligible_results if re.sub(r'\s+', '', r.get("title", "")) not in eligible_titles]

    # 노이즈 컷오프 — 60점 미만은 eligible에서만 제외
    results = [r for r in results if r.get("match_score", 0) >= 60]

    # 점수 순 정렬 (eligible)
    results.sort(key=lambda x: x["match_score"], reverse=True)

    # 임시 필드 제거
    for r in results:
        r.pop("_category", None)
    for r in ineligible_results:
        r.pop("_category", None)

    # eligible 먼저, ineligible 후순위로 합쳐서 반환
    return results + ineligible_results


# ───────────────────────────────────────────────────────────
# 개인 매칭 엔진
# ───────────────────────────────────────────────────────────

# 연령대 → 매칭 키워드 맵
AGE_KEYWORD_MAP = {
    "20대": ["청년", "20대", "만 19세", "만 18세", "만 34세", "만 39세", "19세~", "18세~", "대학생", "청소년"],
    "30대": ["청년", "30대", "만 34세", "만 39세", "중장년", "장년"],
    "40대": ["중장년", "40대", "중년", "장년"],
    "50대": ["중장년", "50대", "중년", "장년", "노인", "신중년", "5060"],
    "60대 이상": ["노인", "어르신", "60대", "65세", "고령자", "장년", "시니어", "5060", "경로"],
}

# 소득수준 → 매칭 키워드 맵 (우선순위: 기초생활 > 차상위 > 중위50%)
INCOME_KEYWORD_MAP = {
    "기초생활": ["기초생활", "기초수급", "수급자", "국민기초", "생활보장", "저소득"],
    "차상위": ["차상위", "저소득", "기초생활", "수급자"],
    "중위50%이하": ["저소득", "중위소득", "중위 50%", "기준중위소득"],
    "중위75%이하": ["중위소득", "중위 75%", "기준중위소득"],
    "중위100%이하": ["중위소득", "기준중위소득"],
    "해당없음": [],
}

# 가구유형 → 매칭 키워드 맵
FAMILY_KEYWORD_MAP = {
    "1인가구": ["1인가구", "1인 가구", "단독가구", "독거"],
    "다자녀": ["다자녀", "다둥이", "셋째", "3자녀", "2자녀", "다자녀가구"],
    "한부모": ["한부모", "한부모가정", "한부모가족", "모자가정", "부자가정"],
    "신혼부부": ["신혼", "신혼부부", "결혼", "혼인"],
    "다문화": ["다문화", "다문화가정", "다문화가족", "이주민", "외국인"],
    "일반": [],
    "해당없음": [],
}

# 취업상태 → 매칭 키워드 맵
EMPLOYMENT_KEYWORD_MAP = {
    "재직자": ["재직자", "재직", "근로자", "직장인", "피보험자", "고용보험"],
    "구직자": ["구직자", "구직", "실업", "미취업", "취업준비", "취업지원", "실직", "취업활동"],
    "자영업": ["자영업", "소상공인", "자영업자", "사업자", "소규모사업"],
    "프리랜서": ["프리랜서", "특수고용", "플랫폼노동", "특수형태", "긱워커"],
    "학생": ["학생", "대학생", "대학원생", "재학", "휴학"],
    "해당없음": [],
}

# 연령대 → 생애주기(life_stage) 매핑
AGE_LIFE_STAGE_MAP = {
    "20대": ["청년", "영유아", "아동·청소년"],
    "30대": ["청년", "중장년"],
    "40대": ["중장년"],
    "50대": ["중장년", "노년"],
    "60대 이상": ["노년"],
}

# 개인 카테고리별 결과 최대 건수
INDIVIDUAL_CATEGORY_CAP = 6


def get_individual_matches_for_user(user_profile: dict) -> list:
    """개인 사용자 프로필 기반 복지/지원서비스 매칭"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # SQL: 개인 대상 서비스만 조회 (individual + both), 마감 전 또는 상시모집
    query = """
    SELECT announcement_id, title, region, category, department,
           support_amount, deadline_date, origin_source, created_at,
           COALESCE(target_type, 'individual') AS target_type,
           origin_url, summary_text, eligibility_logic,
           established_years_limit, revenue_limit, employee_limit
    FROM announcements
    WHERE target_type IN ('individual', 'both')
    AND (
        (deadline_date IS NOT NULL AND deadline_date >= CURRENT_DATE)
        OR (deadline_date IS NULL AND created_at >= CURRENT_DATE - INTERVAL '90 days')
    )
    ORDER BY
        CASE WHEN support_amount IS NOT NULL AND support_amount != '' THEN 0 ELSE 1 END,
        deadline_date ASC NULLS LAST,
        created_at DESC
    LIMIT 2000
    """
    cursor.execute(query)
    candidates = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not candidates:
        return []

    # 사용자 프로필 추출
    user_age = user_profile.get("age_range") or "해당없음"
    user_income = user_profile.get("income_level") or "해당없음"
    user_family = user_profile.get("family_type") or "해당없음"
    user_employment = user_profile.get("employment_status") or "해당없음"
    raw_city = user_profile.get("address_city") or ""
    user_cities = [_normalize_region(c.strip()) for c in raw_city.split(",") if c.strip()] if raw_city else []
    home_city = next((c for c in user_cities if c not in ("전국", "")), "")
    has_home = bool(home_city)
    raw_interest_regions = user_profile.get("interest_regions", "")
    interest_regions = [_normalize_region(c.strip()) for c in raw_interest_regions.split(",") if c.strip() and c.strip() != "전국"] if raw_interest_regions else []
    bonus_cities = [home_city] if home_city else []
    bonus_cities.extend([r for r in interest_regions if r not in bonus_cities])
    user_interests_raw = user_profile.get("interests") or ""
    user_interest_tags = [t.strip() for t in user_interests_raw.split(",") if t.strip()]

    # 맞춤 키워드
    custom_kw_raw = user_profile.get("custom_keywords") or ""
    custom_kw_list = [k.strip() for k in custom_kw_raw.split(",") if k.strip()]

    # 키워드 리스트 준비
    age_keywords = AGE_KEYWORD_MAP.get(user_age, [])
    income_keywords = INCOME_KEYWORD_MAP.get(user_income, [])
    family_keywords = FAMILY_KEYWORD_MAP.get(user_family, [])
    employment_keywords = EMPLOYMENT_KEYWORD_MAP.get(user_employment, [])
    age_life_stages = AGE_LIFE_STAGE_MAP.get(user_age, [])

    today = datetime.date.today()
    results = []

    for ad in candidates:
        # eligibility_logic 파싱
        eligibility = {}
        if ad.get("eligibility_logic"):
            try:
                eligibility = json.loads(ad["eligibility_logic"])
            except (json.JSONDecodeError, TypeError):
                pass

        target_desc = (eligibility.get("target_description") or "").lower()
        life_stage = (eligibility.get("life_stage") or "").lower()
        theme = (eligibility.get("theme") or "").lower()
        sel_criteria = (eligibility.get("selection_criteria") or "").lower()
        raw_title = ad.get("title") or ""
        title = raw_title.lower()
        raw_summary = ad.get("summary_text") or ""
        clean_summary = _strip_html(raw_summary).lower()

        # 만료 공고 필터 — 작년 이전 연도가 제목에 있고 마감일이 과거/없으면 제외
        title_year_match = re.search(r'(\d{4})년', raw_title)
        if title_year_match:
            title_year = int(title_year_match.group(1))
            if title_year < today.year:
                dl = ad.get("deadline_date")
                if not dl:
                    continue
                try:
                    if isinstance(dl, (datetime.date, datetime.datetime)):
                        dl_date = dl if isinstance(dl, datetime.date) else dl.date()
                    else:
                        dl_date = datetime.datetime.strptime(str(dl), "%Y-%m-%d").date()
                    if dl_date < today:
                        continue
                except (ValueError, TypeError):
                    continue

        # 통합 검색 텍스트
        search_text = f"{title} {target_desc} {clean_summary} {sel_criteria}"

        # 지역 필터 — 소재지 기반
        ad_region = _normalize_region(ad.get("region") or "")
        if ad_region and ad_region not in ("전국", "", "All"):
            if has_home and ad_region != home_city:
                continue

        score = 0.0
        reasons = []

        # A. 기본 자격 (20점)
        score += 20.0

        # B. 연령대 매칭 (최대 20점)
        if age_keywords and target_desc:
            age_matched = [kw for kw in age_keywords if kw in search_text]
            if age_matched:
                score += 20.0
                reasons.append(f"{user_age} 대상")
            elif not target_desc or "누구나" in target_desc or "전 국민" in target_desc or "제한없음" in target_desc:
                score += 5.0  # 대상 제한 없는 서비스

        # B-2. 연령대 역필터: 명시적으로 다른 연령대 전용인 경우 감점
        if target_desc:
            age_exclusive_penalty = False
            if user_age in ("50대", "60대 이상"):
                if any(kw in target_desc for kw in ["청년", "20대", "대학생"]) and not any(kw in target_desc for kw in ["중장년", "노인", "어르신", "시니어"]):
                    age_exclusive_penalty = True
            elif user_age in ("20대", "30대"):
                if any(kw in target_desc for kw in ["노인", "어르신", "65세 이상", "고령자"]) and not any(kw in target_desc for kw in ["청년", "청소년"]):
                    age_exclusive_penalty = True
            if age_exclusive_penalty:
                score -= 30.0  # 자격 미달 수준으로 감점

        # C. 소득수준 매칭 (최대 20점)
        if income_keywords and user_income != "해당없음":
            income_matched = [kw for kw in income_keywords if kw in search_text]
            if income_matched:
                # 기초생활/차상위는 더 높은 점수 (전용 프로그램이 많음)
                if user_income in ("기초생활", "차상위"):
                    score += 20.0
                    reasons.append(f"{user_income} 대상 지원")
                else:
                    score += 15.0
                    reasons.append("소득기준 충족")

        # D. 가구유형 매칭 (최대 15점)
        if family_keywords and user_family not in ("일반", "해당없음"):
            family_matched = [kw for kw in family_keywords if kw in search_text]
            if family_matched:
                score += 15.0
                reasons.append(f"{user_family} 대상")

        # E. 취업상태 매칭 (최대 15점)
        if employment_keywords and user_employment != "해당없음":
            emp_matched = [kw for kw in employment_keywords if kw in search_text]
            if emp_matched:
                score += 15.0
                reasons.append(f"{user_employment} 대상")

        # F. 지역 매칭 보너스 — 소재지 +10, 관심지역 +5
        if ad_region and ad_region not in ("전국", "", "All"):
            if ad_region == home_city:
                score += 10.0
                reasons.append(f"{home_city} 거주지역 서비스")
            elif ad_region in interest_regions:
                score += 5.0
                reasons.append(f"{ad_region} 관심지역 서비스")

        # G. 생애주기(life_stage) 매칭 (최대 5점)
        if life_stage and age_life_stages:
            if any(ls.lower() in life_stage for ls in age_life_stages):
                score += 5.0

        # H. 관심주제(theme) 매칭 (최대 5점)
        if theme and user_interest_tags:
            for tag in user_interest_tags:
                if tag.lower() in theme:
                    score += 5.0
                    break

        # H-2. 맞춤 키워드 매칭 (최대 15점)
        if custom_kw_list:
            kw_matched = [kw for kw in custom_kw_list if kw.lower() in search_text]
            if kw_matched:
                kw_score = min(15.0, len(set(kw_matched)) * 5.0)
                score += kw_score
                reasons.append(f'"{kw_matched[0]}" 키워드 매칭')

        # I. 마감일 가중치 (최대 5점) — 상시모집이 대부분이므로 마감 있는 건 부스트
        if ad.get("deadline_date"):
            try:
                deadline_val = ad["deadline_date"]
                if isinstance(deadline_val, (datetime.date, datetime.datetime)):
                    deadline = deadline_val if isinstance(deadline_val, datetime.date) else deadline_val.date()
                else:
                    deadline = datetime.datetime.strptime(str(deadline_val), "%Y-%m-%d").date()
                days_left = (deadline - today).days
                if days_left < 0:
                    continue  # 만료 제외
                if days_left <= 14:
                    score += 5.0
                    reasons.append(f"마감 D-{days_left}")
                elif days_left <= 30:
                    score += 3.0
            except (ValueError, TypeError):
                pass

        # 점수 100 캡
        score = min(score, 100.0)
        ad["match_score"] = round(score, 1)
        meaningful_reasons = reasons[:3]
        ad["recommendation_reason"] = " / ".join(meaningful_reasons) if meaningful_reasons else "지원 자격 충족"

        # 카테고리 (다양성 보장용)
        ad["_category"] = ad.get("category") or ""
        results.append(ad)

    # 노이즈 컷오프 — 60점 미만 제외
    results = [r for r in results if r.get("match_score", 0) >= 60]

    # 점수 순 정렬
    results.sort(key=lambda x: x["match_score"], reverse=True)

    # 카테고리 정리
    for r in results:
        r.pop("_category", None)
    return results


# ── 임베딩 기반 매칭 (Feature Flag로 제어, 기본 OFF) ──
def _profile_to_text(user_profile: dict) -> str:
    """사용자 프로파일을 임베딩용 자연어로 변환."""
    parts = []
    if user_profile.get("company_name"):
        parts.append(f"기업명: {user_profile['company_name']}")
    if user_profile.get("industry_code"):
        parts.append(f"업종코드: {user_profile['industry_code']}")
    if user_profile.get("industry_name"):
        parts.append(f"업종명: {user_profile['industry_name']}")
    if user_profile.get("address_city"):
        parts.append(f"지역: {user_profile['address_city']}")
    if user_profile.get("revenue_bracket"):
        parts.append(f"매출규모: {user_profile['revenue_bracket']}")
    if user_profile.get("employee_count_bracket"):
        parts.append(f"직원수: {user_profile['employee_count_bracket']}")
    if user_profile.get("establishment_date"):
        parts.append(f"설립일: {user_profile['establishment_date']}")
    if user_profile.get("interests"):
        parts.append(f"관심분야: {user_profile['interests']}")
    # 개인용 필드
    if user_profile.get("age_range"):
        parts.append(f"연령대: {user_profile['age_range']}")
    if user_profile.get("income_level"):
        parts.append(f"소득수준: {user_profile['income_level']}")
    if user_profile.get("family_type"):
        parts.append(f"가구형태: {user_profile['family_type']}")
    if user_profile.get("employment_status"):
        parts.append(f"고용상태: {user_profile['employment_status']}")
    if user_profile.get("housing_status"):
        parts.append(f"주거형태: {user_profile['housing_status']}")
    if user_profile.get("special_conditions"):
        parts.append(f"특수자격: {user_profile['special_conditions']}")
    return "\n".join(parts) if parts else "일반 지원사업"


def get_matches_by_embedding(user_profile: dict, top_k: int = 50, target_type_filter: str = None) -> list:
    """임베딩 유사도 기반 상위 K개 공고 추출.
    실패 시 빈 리스트 반환 (호출자가 fallback 처리).
    """
    import os as _os
    try:
        import google.generativeai as _genai
    except ImportError:
        return []

    api_key = _os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return []

    try:
        _genai.configure(api_key=api_key)
        profile_text = _profile_to_text(user_profile)
        res = _genai.embed_content(
            model="models/gemini-embedding-001",
            content=profile_text,
            task_type="retrieval_query",
            output_dimensionality=768,
        )
        vec = res.get("embedding") if isinstance(res, dict) else res["embedding"]
        if not vec:
            return []
        vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    except Exception as e:
        print(f"[EmbMatch] embed error: {str(e)[:150]}")
        return []

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # target_type 필터
        tt_filter = ""
        params: list = [vec_str]
        if target_type_filter in ("business", "individual"):
            tt_filter = " AND COALESCE(a.target_type, 'business') IN (%s, 'both')"
            params.append(target_type_filter)
        params.append(top_k)
        sql = f"""
            SELECT a.announcement_id, a.title, a.department, a.category,
                   a.support_amount, a.deadline_date, a.region, a.origin_url,
                   a.summary_text, a.eligibility_logic, a.target_type,
                   1 - (e.embedding <=> %s::vector) AS similarity
            FROM announcement_embeddings e
            JOIN announcements a ON e.announcement_id = a.announcement_id
            WHERE (a.deadline_date IS NULL OR a.deadline_date >= CURRENT_DATE){tt_filter}
            ORDER BY e.embedding <=> %s::vector
            LIMIT %s
        """
        # ORDER BY에도 vec_str 필요
        params.insert(-1, vec_str)
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    except Exception as e:
        print(f"[EmbMatch] query error: {str(e)[:200]}")
        return []
    finally:
        try: conn.close()
        except: pass


# ───────────────────────────────────────────────────────────
# 버킷 분류 + 로테이션 + 2차 정렬
# ───────────────────────────────────────────────────────────

_BUCKET_ORDER_BASE = ["interest", "region", "national_fund", "deadline", "fresh"]


def _is_fund_related(title: str, category: str) -> bool:
    t = f"{title or ''} {category or ''}".lower()
    return any(k in t for k in ["정책자금", "융자", "보증", "대출", "자금", "r&d", "연구개발", "기술개발", "창업자금"])


def _amount_value(amount_str: str) -> int:
    """지원금액 텍스트 → 대략적 원화 정수 (큰 숫자 먼저 정렬용)."""
    if not amount_str:
        return 0
    try:
        if "억" in amount_str:
            m = re.search(r"(\d+(?:\.\d+)?)\s*억", amount_str)
            if m:
                return int(float(m.group(1)) * 100_000_000)
        if "천만" in amount_str:
            m = re.search(r"(\d+(?:\.\d+)?)\s*천만", amount_str)
            if m:
                return int(float(m.group(1)) * 10_000_000)
        if "만" in amount_str:
            m = re.search(r"(\d+(?:\.\d+)?)\s*만", amount_str)
            if m:
                return int(float(m.group(1)) * 10_000)
    except Exception:
        pass
    return 0


def _is_deadline_valid(deadline_date) -> bool:
    """마감 유효 (미래이거나 상시모집)."""
    if deadline_date is None:
        return True
    try:
        if isinstance(deadline_date, (datetime.date, datetime.datetime)):
            d = deadline_date if isinstance(deadline_date, datetime.date) else deadline_date.date()
        else:
            d = datetime.datetime.strptime(str(deadline_date)[:10], "%Y-%m-%d").date()
        return d >= datetime.date.today()
    except Exception:
        return True


def _days_left(deadline_date) -> int:
    if deadline_date is None:
        return 9999
    try:
        if isinstance(deadline_date, (datetime.date, datetime.datetime)):
            d = deadline_date if isinstance(deadline_date, datetime.date) else deadline_date.date()
        else:
            d = datetime.datetime.strptime(str(deadline_date)[:10], "%Y-%m-%d").date()
        return (d - datetime.date.today()).days
    except Exception:
        return 9999


def _classify_bucket(match_item: dict, user_profile: dict) -> str:
    """공고를 버킷에 배정 — interest/region/deadline/fresh 중 하나."""
    title = match_item.get("title") or ""
    category = match_item.get("category") or ""
    region = match_item.get("region") or ""
    search_text = f"{title} {category} {match_item.get('summary_text') or ''}".lower()

    # 1) interest 우선 — 사용자 관심 키워드와 매칭되면 interest 버킷
    user_interests = (user_profile.get("interests") or "").split(",") if user_profile.get("interests") else []
    user_kws = (user_profile.get("custom_keywords") or "").split(",") if user_profile.get("custom_keywords") else []
    for tag in user_interests + user_kws:
        tag = (tag or "").strip()
        if not tag:
            continue
        if tag.lower() in search_text:
            return "interest"
        # INTEREST_KEYWORD_MAP 확장된 키워드도 체크
        expanded = INTEREST_KEYWORD_MAP.get(tag, [])
        if any(kw.lower() in search_text for kw in expanded):
            return "interest"

    # 2) region — 사용자 소재지/관심지역과 매칭
    addr_raw = (user_profile.get("address_city") or "")
    user_cities = [c.strip() for c in addr_raw.split(",") if c.strip() and c.strip() != "전국"]
    if region and region not in ("전국", "All", "") and any(uc in region or region in uc for uc in user_cities):
        return "region"

    # 3) national_fund — 전국 범위의 자금 관련 공고 (전국 공고가 region 버킷에서 배제되는 문제 보완)
    if (not region or region in ("전국", "All", "")) and _is_fund_related(title, category):
        return "national_fund"

    # 4) deadline — 30일 이내 마감
    dleft = _days_left(match_item.get("deadline_date"))
    if 0 <= dleft <= 30:
        return "deadline"

    # 5) fresh — 최근 등록 (기본 버킷)
    return "fresh"


def _rotate_buckets(user_profile: dict) -> list:
    """접속일·사용자 해시로 상위 3개 버킷만 로테이션. 마감·최신은 항상 뒤쪽 고정.
    - 상위 슬롯(1·2·3): interest / region / national_fund 로테이션
    - 하위 슬롯(4·5): deadline → fresh 고정
    """
    import hashlib
    seed_parts = [
        str(user_profile.get("business_number", "")),
        str(user_profile.get("email", "")),
        datetime.date.today().isoformat(),
    ]
    seed = "|".join(seed_parts)
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    top_buckets = ["interest", "region", "national_fund"]
    rotated_top: list = []
    remaining = top_buckets[:]
    for i in range(len(top_buckets)):
        if not remaining:
            break
        idx = (h + i * 7) % len(remaining)
        rotated_top.append(remaining.pop(idx))
    # 하위는 고정
    return rotated_top + ["deadline", "fresh"]


_BUCKET_LABELS = {
    "interest": "🎯 내 관심분야",
    "region": "📍 내 지역 맞춤",
    "national_fund": "🌏 전국 자금 공고",
    "deadline": "⏰ 마감 임박",
    "fresh": "✨ 최근 등록",
}


def _apply_bucket_layer(results: list, user_profile: dict) -> list:
    """매칭 결과에 버킷 분류 + 2차 정렬 + 합성 score 부여.

    기존 match_score 정렬과 호환되도록 합성 점수는 버킷 우선순위를 보존.
    - 1등 버킷: 95~99
    - 2등: 87~94
    - 3등: 80~86
    - 4등: 75~79
    버킷 내부 정렬: 자금관련(+) → 마감 유효(+) → 금액 큰 순.
    """
    if not results:
        return results

    bucket_order = _rotate_buckets(user_profile)
    bucket_to_rank = {b: i for i, b in enumerate(bucket_order)}

    # 1) 각 아이템에 버킷 부여
    for r in results:
        b = _classify_bucket(r, user_profile)
        r["bucket"] = b
        r["bucket_label"] = _BUCKET_LABELS.get(b, b)

    # 2) 버킷 내부 2차 정렬 키
    #    1순위: 실제 금액 명시 (support_amount에 숫자+원/억/만 포함 — 프론트 빨간 뱃지 조건과 동일)
    #    2순위: 자금 키워드 매칭 (fallback)
    #    3순위: 마감 유효
    #    4순위: 금액 크기 desc
    def _sort_key(r):
        amt_str = str(r.get("support_amount") or "")
        has_real_amount = 0 if (any(c.isdigit() for c in amt_str) and any(k in amt_str for k in ("원", "억", "만"))) else 1
        fund = 0 if _is_fund_related(r.get("title", ""), r.get("category", "")) else 1
        deadline_ok = 0 if _is_deadline_valid(r.get("deadline_date")) else 1
        amount = -_amount_value(amt_str)
        return (has_real_amount, fund, deadline_ok, amount)

    # 버킷별 그룹
    grouped: dict = {b: [] for b in bucket_order}
    for r in results:
        b = r.get("bucket") or "fresh"
        grouped.setdefault(b, []).append(r)

    # 3) 버킷별 내부 정렬 + 합성 점수 부여
    final: list = []
    ranges = [(95, 99), (88, 94), (82, 87), (76, 81), (70, 75)]
    for idx, b in enumerate(bucket_order):
        items = grouped.get(b, [])
        items.sort(key=_sort_key)
        lo, hi = ranges[idx] if idx < len(ranges) else (75, 79)
        span = max(1, len(items))
        for i, r in enumerate(items):
            # 합성 점수 — 순위가 높을수록 hi 가까움
            synth = hi - int((hi - lo) * (i / span))
            r["match_score"] = synth
            # reasons 배열 (프론트 뱃지용) — 기존 recommendation_reason 유지하면서 신규 필드 추가
            reasons_arr = []
            if r.get("bucket") == "interest":
                reasons_arr.append({"icon": "🎯", "label": "관심분야"})
            elif r.get("bucket") == "region":
                reasons_arr.append({"icon": "📍", "label": "내 지역"})
            elif r.get("bucket") == "national_fund":
                reasons_arr.append({"icon": "🌏", "label": "전국 자금"})
            if _is_fund_related(r.get("title", ""), r.get("category", "")):
                reasons_arr.append({"icon": "💰", "label": "자금"})
            dl = _days_left(r.get("deadline_date"))
            if 0 <= dl <= 7:
                reasons_arr.append({"icon": "⏰", "label": f"D-{dl}"})
            r["reasons"] = reasons_arr
            final.append(r)

    return final


def get_matches_hybrid(user_profile: dict, is_individual: bool = False) -> list:
    """하이브리드 매칭 — USE_EMBEDDING_MATCHING 환경변수 ON일 때만 임베딩 사용.
    OFF 또는 실패 시 기존 rule-based 함수로 자동 fallback.
    결과에 버킷 분류·합성 점수·reasons 추가.
    """
    import os as _os
    use_emb = _os.environ.get("USE_EMBEDDING_MATCHING", "false").lower() == "true"

    # 기본: rule-based 사용
    if not use_emb:
        results = get_individual_matches_for_user(user_profile) if is_individual else get_matches_for_user(user_profile)
    else:
        # 임베딩 검색으로 상위 50개 후보 추출
        tt = "individual" if is_individual else "business"
        candidates = get_matches_by_embedding(user_profile, top_k=50, target_type_filter=tt)
        if not candidates:
            print("[MatchHybrid] embedding returned empty, fallback to rule-based")
            results = get_individual_matches_for_user(user_profile) if is_individual else get_matches_for_user(user_profile)
        else:
            for c in candidates:
                sim = c.pop("similarity", 0.0) or 0.0
                c["match_score"] = round(max(0, min(100, sim * 100)))
                c["match_reason"] = "의미 유사도 기반 매칭"
            results = candidates

    # 버킷 분류 + 2차 정렬 + 합성 점수 후처리
    try:
        results = _apply_bucket_layer(results, user_profile)
    except Exception as e:
        print(f"[MatchHybrid] bucket layer error (fallback raw): {e}")
    return results
