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

# KSIC 대분류 → 매칭 키워드 맵
KSIC_KEYWORD_MAP = {
    "58": ["IT", "정보통신", "소프트웨어", "디지털", "콘텐츠", "ICT", "AI"],
    "61": ["IT", "정보통신", "소프트웨어", "디지털", "통신", "ICT"],
    "62": ["IT", "정보통신", "소프트웨어", "디지털", "프로그래밍", "AI", "인공지능", "ICT", "SW"],
    "63": ["IT", "정보통신", "소프트웨어", "디지털", "데이터", "ICT", "AI"],
    "10": ["제조", "식품", "식품제조", "가공"],
    "20": ["제조", "화학", "화장품"],
    "26": ["제조", "반도체", "전자"],
    "29": ["제조", "자동차", "부품"],
    "33": ["제조", "가구", "인테리어"],
    "34": ["제조", "공장", "설비", "기계"],
    "25": ["제조", "금속", "부품", "가공"],
    "70": ["서비스", "컨설팅", "전문", "회계"],
    "71": ["서비스", "컨설팅", "광고", "마케팅", "디자인"],
    "72": ["연구", "연구개발", "R&D"],
    "74": ["디자인", "전문서비스"],
    "56": ["음식", "외식", "식당", "요식", "배달", "소상공인", "자영업"],
    "47": ["소매", "판매", "상점", "유통", "소상공인", "자영업"],
    "46": ["도매", "유통", "무역"],
    "55": ["숙박", "호텔", "관광", "펜션", "소상공인", "여행", "관광업"],
    "96": ["미용", "뷰티", "세탁", "생활서비스", "소상공인", "자영업"],
    "95": ["수리", "정비", "AS"],
    "85": ["교육", "학원", "강의", "훈련", "직업훈련"],
    "68": ["부동산", "임대", "중개"],
    "45": ["자동차", "차량", "정비", "세차", "소상공인"],
    "49": ["운송", "물류", "택배", "화물"],
    "52": ["창고", "물류", "보관"],
    "41": ["건설", "건축", "시공"],
    "42": ["토목", "건설"],
    "75": ["수의", "동물병원"],
    "86": ["의료", "병원", "치과", "한의원"],
    "91": ["스포츠", "체육", "헬스", "레저"],
    "90": ["공연", "문화", "예술"],
    "81": ["청소", "방역", "시설관리"],
}

# KSIC 대분류 → 업종 한글명 (target_industries 매칭용)
KSIC_INDUSTRY_NAMES = {
    "58": ["IT", "소프트웨어", "콘텐츠", "정보통신", "ICT", "AI"],
    "61": ["통신", "IT", "ICT", "정보통신"],
    "62": ["소프트웨어", "IT", "SW", "ICT", "AI", "인공지능", "컴퓨터 프로그래밍"],
    "63": ["IT", "데이터", "정보서비스", "데이터처리", "ICT", "AI"],
    "10": ["식품", "식품제조", "식품가공", "제조"],
    "20": ["화학", "화장품", "뷰티", "제조"],
    "26": ["전자", "반도체", "전기전자", "제조"],
    "29": ["자동차", "운송장비", "제조"],
    "33": ["가구", "제조"],
    "34": ["기계", "설비", "제조"],
    "25": ["금속", "금속가공", "제조"],
    "70": ["전문서비스", "컨설팅"],
    "71": ["마케팅", "광고", "디자인", "전문서비스"],
    "72": ["연구개발", "R&D"],
    "74": ["디자인", "전문서비스"],
    "56": ["음식", "외식", "요식"],
    "47": ["소매", "유통", "전자상거래"],
    "46": ["도매", "무역", "유통"],
    "55": ["숙박", "관광", "호텔"],
    "96": ["미용", "뷰티", "생활서비스"],
    "85": ["교육", "훈련"],
    "86": ["의료", "헬스케어"],
    "41": ["건설", "건축"],
    "45": ["자동차", "차량관리"],
    "49": ["물류", "운송"],
    "81": ["시설관리", "청소"],
}

# 소상공인 해당 KSIC 대분류 코드
SOHO_KSIC_PREFIXES = {"56", "47", "55", "96", "95", "45", "68", "46", "85", "90", "91", "81"}

# 지원 대상 기업 유형 분류
EXCLUSIVE_BIZ_TYPES = {"소상공인", "예비창업자", "사회적기업", "예비사회적기업", "마을기업", "자활기업", "수출기업"}

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

# 카테고리별 결과 최대 건수 (다양성 보장)
CATEGORY_CAP = 8


def _is_soho(user_profile: dict) -> bool:
    rev_bracket = user_profile.get("revenue_bracket") or user_profile.get("revenue", "")
    emp_bracket = user_profile.get("employee_count_bracket") or user_profile.get("employees", "")
    small_rev = rev_bracket in ("1억 미만", "1억~5억", "UNDER_1B", "1B_TO_5B")
    small_emp = emp_bracket in ("5인 미만", "5인~10인", "UNDER_5", "5_TO_10")
    if not (small_rev and small_emp):
        return False
    ksic = str(user_profile.get("industry_code", "")).strip()
    prefix = ksic[:2] if ksic else ""
    non_soho_prefixes = {"58", "61", "62", "63", "72", "26", "29", "10", "20", "25", "34", "41", "42"}
    if prefix in non_soho_prefixes:
        return False
    return True


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
    query = """
    SELECT * FROM announcements
    WHERE (region = '전국' OR region = 'All' OR region LIKE %s)
    AND (established_years_limit IS NULL OR established_years_limit >= %s)
    AND (revenue_limit IS NULL OR revenue_limit >= %s)
    AND (employee_limit IS NULL OR employee_limit >= %s)
    AND (
        (deadline_date IS NOT NULL AND deadline_date >= CURRENT_DATE)
        OR (deadline_date IS NULL AND created_at >= CURRENT_DATE - INTERVAL '60 days')
    )
    """
    cursor.execute(query, (f'%{user_profile.get("address_city", "")}%', company_age, user_rev, user_emp))
    candidates = []
    for row in cursor.fetchall():
        d = dict(row)
        candidates.append(d)
    conn.close()

    if not candidates:
        return []

    # 사용자 정보 준비
    user_ksic = str(user_profile.get("industry_code", "")).strip()
    user_interests_raw = user_profile.get("interests") or ""
    user_interest_tags = [t.strip() for t in user_interests_raw.split(",") if t.strip()]
    ksic_prefix = user_ksic[:2] if user_ksic else ""
    ksic_keywords = KSIC_KEYWORD_MAP.get(ksic_prefix, [])
    ksic_industry_names = KSIC_INDUSTRY_NAMES.get(ksic_prefix, [])

    # 관심분야 → 확장 키워드
    interest_keywords = []
    for tag in user_interest_tags:
        interest_keywords.extend(INTEREST_KEYWORD_MAP.get(tag, [tag]))

    is_soho = _is_soho(user_profile)
    user_city = _normalize_region(user_profile.get("address_city", ""))

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

        # 지역 필터: 제목의 [도시명] 패턴으로 지역 특화 공고 판별
        title = ad.get("title", "")
        bracket_city_match = re.search(
            r'\[(서울|경기|인천|부산|대구|대전|광주|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)\]',
            title
        )
        if bracket_city_match:
            title_city = bracket_city_match.group(1)
            if user_city and user_city not in ("전국", "") and title_city != user_city:
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

        # 검색 텍스트 구성
        raw_summary = ad.get("summary_text") or ""
        clean_summary = _strip_html(raw_summary)
        el_keywords = " ".join(eligibility_logic.get("target_keywords", []))
        el_industries = " ".join(eligibility_logic.get("target_industries", []))
        el_business_types = " ".join(ad_biz_types)
        search_text = f"{title} {clean_summary} {el_keywords} {el_industries} {el_business_types}".lower()

        # 카테고리 정규화
        raw_category = ad.get("category") or ""
        ad_category = CATEGORY_NORMALIZE.get(raw_category, raw_category)

        score = 0.0
        reasons = []

        # A. 기본 자격 (30점)
        score += 30.0

        # A-1. 지역 매칭 보너스 (최대 15점)
        if bracket_city_match and user_city and user_city not in ("전국", ""):
            score += 15.0
            reasons.append(f"{user_city} 지역 특화 지원사업")

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

        # D. KSIC 업종 매칭 (최대 20점)
        if user_ksic and user_ksic != "00000":
            # D-1. target_industries 직접 매칭 (최대 20점, 가장 정확)
            ad_target_industries = [i.lower() for i in eligibility_logic.get("target_industries", [])]
            def _ind_match(ind: str, ad_ind: str) -> bool:
                # 3자 이하 단어는 단어 경계 매칭만 허용 (부분 매칭 오탐 방지)
                if len(ind) <= 3:
                    return bool(re.search(r'(?<![가-힣a-zA-Z])' + re.escape(ind) + r'(?![가-힣a-zA-Z])', ad_ind))
                return ind in ad_ind or ad_ind in ind

            ad_target_industries = [i.lower() for i in eligibility_logic.get("target_industries", [])]
            industry_match = False
            if ad_target_industries and ksic_industry_names:
                industry_match = any(
                    _ind_match(ind, ad_ind)
                    for ind in [n.lower() for n in ksic_industry_names]
                    for ad_ind in ad_target_industries
                )
            # D-1. target_industries 직접 매칭 (최대 20점)
            if industry_match:
                score += 20.0
                reasons.append("업종 직접 매칭")
            # D-2. KSIC 키워드 기반 매칭 (최대 15점) — D-1 실패해도 독립적으로 실행
            elif ksic_prefix in SOHO_KSIC_PREFIXES and ad_targets_soho:
                score += 10.0
                if not any("소상공인" in r for r in reasons):
                    reasons.append("업종 기반 소상공인 매칭")
            elif ksic_keywords:
                matched_ksic = [kw for kw in ksic_keywords if kw.lower() in search_text]
                if matched_ksic:
                    score += 15.0
                    reasons.append(f"업종({ksic_prefix}계열) 부합")

        # E. business_type 보너스 매칭 (최대 10점)
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

        # F. 마감일 가중치 (최대 5점)
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
                if days_left <= 7:
                    score += 5.0
                    reasons.append("마감 임박 (7일 이내)")
                elif days_left <= 14:
                    score += 2.0
            except (ValueError, TypeError):
                pass

        # 최소 점수 미달 → 제외 (기본 30점만 받은 경우 노출 안 함)
        if score <= 30.0:
            continue

        ad["match_score"] = round(score, 1)
        # recommendation_reason: "기본 자격" 제외하고 실제 매칭 이유만 표시
        meaningful_reasons = [r for r in reasons if "기본 지원 자격" not in r]
        ad["recommendation_reason"] = " / ".join(meaningful_reasons[:2]) if meaningful_reasons else "지원 자격 충족"
        ad["_category"] = ad_category  # 다양성 처리용 임시 필드
        results.append(ad)

    # 점수 순 정렬
    results.sort(key=lambda x: x["match_score"], reverse=True)

    # 카테고리 다양성 보장: 카테고리별 최대 CATEGORY_CAP건, 전체 상위 20건
    final = []
    cat_counts: dict = {}
    # 1차: 고득점 순으로 카테고리 캡 적용
    for r in results:
        cat = r.get("_category", "")
        if cat_counts.get(cat, 0) < CATEGORY_CAP:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            final.append(r)
        if len(final) >= 20:
            break

    # 2차: 금융·경영 카테고리 최소 1건 보장 (유용한 지원을 놓치지 않도록)
    for must_cat in ["금융", "경영"]:
        if not any(r.get("_category") == must_cat for r in final):
            candidate = next((r for r in results if r.get("_category") == must_cat and r not in final), None)
            if candidate:
                final[-1] = candidate  # 가장 낮은 점수 결과와 교체

    # 임시 필드 제거 후 반환
    for r in final:
        r.pop("_category", None)
    return final
