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
    "고용지원":   ["고용", "채용", "일자리", "인력", "청년", "근로자", "고용지원", "인재", "취업"],
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
}

# 관심분야 → 카테고리 매핑 (관심분야가 있는 카테고리 공고를 부스트)
INTEREST_CATEGORY_MAP = {
    "기술개발":   ["기술"],
    "창업지원":   ["창업"],
    "수출마케팅": ["수출"],
    "고용지원":   ["인력"],
    "정책자금":   ["금융"],
    "디지털전환": ["기술", "경영"],
    "판로개척":   ["내수", "수출", "경영"],
    "교육훈련":   ["인력", "경영"],
    "에너지환경": ["기술", "경영"],
    "소상공인":   ["경영", "내수"],
    "R&D":        ["기술"],
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
    # 관심지역: 쉼표 구분 문자열 → 정규화된 리스트
    raw_city = user_profile.get("address_city", "")
    user_cities = [_normalize_region(c.strip()) for c in raw_city.split(",") if c.strip()] if raw_city else []
    user_city = user_cities[0] if user_cities else ""
    is_nationwide = not user_cities or "전국" in user_cities

    results = []

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
            continue

        # 지역 필터: 관심지역이 아닌 곳의 지역 전용 공고만 제외
        # 지역 미표기/전국 공고는 항상 포함
        title = ad.get("title", "")
        ad_region = _normalize_region(ad.get("region") or "")

        # DB region 필드 기반 지역 전용 공고 필터
        if ad_region and ad_region not in ("전국", "", "All") and not is_nationwide:
            if ad_region not in user_cities:
                continue

        # 제목의 [도시명] 패턴으로 지역 특화 공고 판별
        bracket_city_match = re.search(
            r'\[(서울|경기|인천|부산|대구|대전|광주|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)\]',
            title
        )
        if bracket_city_match and not is_nationwide:
            title_city = bracket_city_match.group(1)
            if title_city not in user_cities:
                continue

        # business_type 하드 필터: 배타적 대상 유형이 지정된 경우
        ad_biz_types = _get_biz_types(eligibility_logic)
        if ad_biz_types:
            exclusive_types = [bt for bt in ad_biz_types if bt in EXCLUSIVE_BIZ_TYPES]
            if exclusive_types:
                # 소상공인 전용 → 비소상공인 제외
                if "소상공인" in exclusive_types and not is_soho:
                    if not any(bt in ad_biz_types for bt in ["중소기업", "스타트업", "기업"]):
                        continue
                # 수출기업 전용 → 수출 관심 없는 기업 제외
                if "수출기업" in exclusive_types and len(exclusive_types) == 1:
                    if "수출마케팅" not in user_interest_tags and "수출" not in user_interests_raw:
                        continue
                # 예비창업자 전용 → 기존 창업자 제외
                if "예비창업자" in exclusive_types and not any(bt in ad_biz_types for bt in ["중소기업", "스타트업"]):
                    if company_age > 0:
                        continue

        # 특정 대상 제한 필터 — 제목에 여성/장애인/보훈 등 키워드가 있으면 해당 대상만 통과
        title_lower = title.lower()
        skip_restricted = False
        for target_group, keywords in RESTRICTED_TARGET_KEYWORDS.items():
            if any(kw in title for kw in keywords):
                # 사용자의 관심분야나 검색어에 해당 키워드가 없으면 제외
                if not any(kw in user_interests_raw for kw in keywords):
                    skip_restricted = True
                    break
        if skip_restricted:
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

        # 카테고리 정규화
        raw_category = ad.get("category") or ""
        ad_category = CATEGORY_NORMALIZE.get(raw_category, raw_category)

        score = 0.0
        reasons = []

        # A. 기본 자격 (30점)
        score += 30.0

        # A-1. 지역 매칭 보너스 (최대 25점)
        matched_city = None
        if bracket_city_match and not is_nationwide:
            matched_city = bracket_city_match.group(1)
        elif ad_region and ad_region not in ("전국", "", "All") and not is_nationwide and ad_region in user_cities:
            matched_city = ad_region
        if matched_city:
            score += 25.0
            reasons.append(f"{matched_city} 지역 특화 지원사업")

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

        # C. 관심분야 키워드 매칭 (최대 25점)
        if interest_keywords:
            matched_interests = [kw for kw in interest_keywords if kw.lower() in search_text]
            if matched_interests:
                interest_score = min(25.0, len(set(matched_interests)) * 4.0)
                score += interest_score
                for tag in user_interest_tags:
                    tag_kws = INTEREST_KEYWORD_MAP.get(tag, [tag])
                    if any(kw.lower() in search_text for kw in tag_kws):
                        reasons.append(f'"{tag}" 관심분야 부합')
                        break

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

        # G. 카테고리-관심분야 매칭 보너스 (최대 10점)
        if ad_category:
            for tag in user_interest_tags:
                if ad_category in INTEREST_CATEGORY_MAP.get(tag, []):
                    score += 10.0
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

        ad["match_score"] = round(score, 1)
        # recommendation_reason: "기본 자격" 제외하고 실제 매칭 이유만 표시
        meaningful_reasons = [r for r in reasons if "기본 지원 자격" not in r]
        ad["recommendation_reason"] = " / ".join(meaningful_reasons[:2]) if meaningful_reasons else "지원 자격 충족"
        ad["_category"] = ad_category  # 다양성 처리용 임시 필드
        results.append(ad)

    # 중복 공고 제거 (같은 제목)
    seen_titles = set()
    unique_results = []
    for r in results:
        norm = re.sub(r'\s+', '', r.get("title", ""))
        if norm not in seen_titles:
            seen_titles.add(norm)
            unique_results.append(r)
    results = unique_results

    # 점수 순 정렬
    results.sort(key=lambda x: x["match_score"], reverse=True)

    # 임시 필드 제거 후 반환
    for r in results:
        r.pop("_category", None)
    return results


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
        OR deadline_date IS NULL
    )
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
    is_nationwide = not user_cities or "전국" in user_cities
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
        title = (ad.get("title") or "").lower()
        raw_summary = ad.get("summary_text") or ""
        clean_summary = _strip_html(raw_summary).lower()

        # 통합 검색 텍스트
        search_text = f"{title} {target_desc} {clean_summary} {sel_criteria}"

        # 지역 필터
        ad_region = _normalize_region(ad.get("region") or "")
        if ad_region and ad_region not in ("전국", "", "All") and not is_nationwide:
            if ad_region not in user_cities:
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

        # F. 지역 매칭 보너스 (최대 10점)
        if ad_region and ad_region not in ("전국", "", "All") and not is_nationwide and ad_region in user_cities:
            score += 10.0
            reasons.append(f"{ad_region} 지역 서비스")

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

        ad["match_score"] = round(score, 1)
        meaningful_reasons = reasons[:3]
        ad["recommendation_reason"] = " / ".join(meaningful_reasons) if meaningful_reasons else "지원 자격 충족"

        # 카테고리 (다양성 보장용)
        ad["_category"] = ad.get("category") or ""
        results.append(ad)

    # 점수 순 정렬
    results.sort(key=lambda x: x["match_score"], reverse=True)

    # 카테고리 정리
    for r in results:
        r.pop("_category", None)
    return results
