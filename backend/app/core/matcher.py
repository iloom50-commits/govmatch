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

# 관심 분야 태그 → 매칭 키워드 확장 맵 (확장판)
INTEREST_KEYWORD_MAP = {
    "창업지원":   ["창업", "스타트업", "벤처", "예비창업", "창업패키지", "초기기업", "팁스", "TIPS", "창업육성", "창업도약", "창업성공", "창업기업"],
    "기술개발":   ["R&D", "연구개발", "기술개발", "기술혁신", "연구", "기술", "AI", "인공지능", "혁신기술", "R%26D", "기술사업화", "특허", "지식재산", "IP"],
    "수출마케팅": ["수출", "해외", "글로벌", "무역", "수출마케팅", "해외판로", "해외진출", "수출지원", "해외마케팅", "KOTRA", "수출바우처", "해외전시", "CES", "IFA", "바이어"],
    "고용지원":   ["고용", "채용", "일자리", "인력", "청년", "근로자", "고용지원", "인재", "취업", "고용안정", "고용장려", "인건비", "장려금", "청년내일", "두루누리", "육아휴직", "청년일자리"],
    "시설개선":   ["시설", "설비", "인테리어", "리모델링", "환경개선", "공간", "장비", "스마트공장", "자동화", "장비구입", "기기구입", "공정개선", "작업환경"],
    "정책자금":   ["정책자금", "융자", "대출", "보증", "자금", "금융", "지원금", "보조금", "특례보증", "신용보증", "운전자금", "경영안정자금", "성장지원", "특례자금"],
    "디지털전환": ["디지털", "스마트", "IT", "정보화", "비대면", "플랫폼", "소프트웨어", "AI", "인공지능", "DX", "ICT", "데이터", "클라우드", "SaaS", "O2O", "디지털혁신", "딥테크"],
    "판로개척":   ["판로", "마케팅", "홍보", "온라인", "판매", "유통", "쇼핑몰", "B2B", "B2C", "전시회", "박람회", "플랫폼입점", "라이브커머스", "인플루언서", "브랜드마케팅", "라이브방송"],
    "교육훈련":   ["교육", "훈련", "컨설팅", "멘토링", "역량", "강의", "아카데미", "HRD", "직업훈련", "전문교육", "리스킬링", "업스킬링"],
    "에너지환경": ["에너지", "환경", "친환경", "탄소", "녹색", "ESG", "수소", "태양광", "신재생", "그린뉴딜", "저탄소", "순환경제", "재활용"],
    "소상공인":   ["소상공인", "자영업", "골목상권", "전통시장", "소규모", "골목", "중소유통", "상점가", "상권활성화", "생활밀착"],
    "R&D":        ["R&D", "연구개발", "기술개발", "혁신", "연구", "AI", "인공지능", "기술사업화", "원천기술", "산학협력", "융합기술", "응용연구"],
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


# ════════════════════════════════════════════════════════════════
# 0단계: 하드 필터 (자격 미달 즉시 제외)
# ════════════════════════════════════════════════════════════════

# 사용자 업종 코드(KSIC 대분류 2자리) → 제외 키워드 매핑
# 공고의 exclusion_rules/제목/요약에 이 키워드가 있으면 해당 업종 사용자 제외
INDUSTRY_EXCLUSION_KEYWORDS = {
    "41": ["건설업", "건설기업", "토목", "건축"],
    "42": ["건설업", "건설기업", "토목"],
    "43": ["건설업", "건설기업"],
    "46": [],  # 도매업 (일반적으로 제외 안 됨)
    "47": [],  # 소매업
    "55": ["숙박업", "숙박·음식", "숙박/음식"],
    "56": ["음식점", "음식·숙박", "음식/숙박", "주점", "외식업", "유흥"],
    "62": [],  # 정보통신 — IT는 거의 제외되지 않음
    "63": [],  # 정보서비스
    "64": ["금융업", "금융기관"],
    "65": ["보험업", "보험기관"],
    "66": ["금융", "보험"],
    "68": ["부동산업", "부동산임대", "부동산 임대", "임대업"],
    "91": ["사행성", "도박", "카지노", "경마", "복권"],
    "92": ["유흥", "사행성", "도박"],
}

# 보편적 제외 키워드 (어떤 사용자든 해당 업종이면 제외)
COMMON_EXCLUSION_PATTERNS = [
    ("부동산임대업", "68"),
    ("부동산 임대", "68"),
    ("부동산업", "68"),
    ("사행성", "91"),
    ("유흥업", "92"),
    ("도박", "91"),
    ("숙박·음식점업", "55"),
    ("주점업", "56"),
]


# 사용자 업종 대분류 → "타 분야 전용" 공고 제목 키워드
# 해당 키워드가 제목에 있으면 이 사용자에게는 부적합 (특정 분야 지정 공고)
# 정부사업 중 일부는 "OO분야 지원사업" 식으로 특정 업종만 대상
INDUSTRY_DOMAIN_EXCLUSIONS = {
    # IT/소프트웨어/정보서비스 (62, 63) — 이런 분야 지정 공고는 IT 유저에게 부적합
    "62": [
        # 관광·여행·숙박·음식
        "관광진흥", "관광산업", "관광업", "관광기업", "여행업", "여행사",
        "숙박업", "외식업", "음식업", "주점",
        # 스포츠·체육·문화
        "국민체육진흥", "체육산업", "스포츠산업", "스포츠기업",
        "영화산업", "영화제작", "방송산업", "방송영상",
        "애니메이션", "출판산업", "공연예술", "공예산업", "문화콘텐츠",
        # 에너지·환경
        "에너지기술", "에너지산업", "수소산업", "태양광", "신재생에너지", "풍력", "지열",
        "오염방지", "탄소중립", "환경산업", "미래환경산업", "녹색산업",
        # 농림수산
        "축산", "농업인", "농업법인", "영농", "귀농", "어업인", "어선", "수산업", "임업", "산림",
        # 건설·토목·광업
        "건설업", "건설기술", "건설기업", "토목", "플랜트",
        "광업", "광물", "제련",
        # 바이오·의료·식품
        "의약품산업", "제약산업", "바이오산업",  # R&D는 IT도 가능하므로 '산업' 키워드로 좁힘
        "의료기기산업", "헬스케어산업",
        "식품산업", "식품제조", "외식산업",
        # 물류·해운·운송
        "해운", "항만", "물류산업", "운송업", "철도산업",
        "섬유산업", "의류제조", "패션산업",
        # 특수 대상
        "폐자원", "재활용산업",
    ],
    "63": [
        # 관광·여행·숙박·음식
        "관광진흥", "관광산업", "여행업", "숙박업", "외식업",
        # 스포츠·체육·문화
        "국민체육진흥", "체육산업", "스포츠산업",
        "영화산업", "방송산업", "애니메이션", "공연예술",
        # 에너지·환경
        "에너지기술", "수소", "태양광", "오염방지", "환경산업",
        # 농림수산
        "축산", "농업인", "영농", "어업인", "수산업", "임업", "산림",
        # 건설·광업
        "건설업", "광업", "제약산업", "바이오산업",
        # 물류
        "해운", "항만", "물류산업", "철도산업",
    ],
    # 제조업 (10~33)
    "10": ["관광", "여행", "IT전용", "소프트웨어전용", "영화·영상산업", "공연예술"],
    # 도·소매 (46, 47)
    "46": ["관광진흥", "농업", "어업", "건설업", "광업", "환경산업",
           "IT전용", "R&D전용", "기술개발전용"],
    "47": ["관광진흥", "농업", "어업", "건설업", "환경산업", "IT전용", "R&D전용"],
    # 농업(01) — 반대로 농업 외 분야 제외
    "01": ["IT", "소프트웨어", "관광", "제조업전용", "건설"],
    # 건설(41,42) — 건설 외 분야 제외
    "41": ["관광", "농업", "어업", "IT", "소프트웨어", "환경산업"],
}


def _extract_exclusion_text(exclusion_rules) -> str:
    """deep_analysis.exclusion_rules(list of dict) → 검색용 텍스트로 병합."""
    if not exclusion_rules:
        return ""
    if isinstance(exclusion_rules, str):
        try:
            exclusion_rules = json.loads(exclusion_rules)
        except Exception:
            return exclusion_rules
    if not isinstance(exclusion_rules, list):
        return ""
    parts = []
    for rule in exclusion_rules:
        if isinstance(rule, dict):
            parts.append(rule.get("rule") or "")
            parts.append(rule.get("detail") or "")
        elif isinstance(rule, str):
            parts.append(rule)
    return " ".join(parts)


def _check_industry_exclusion(user_industry_code: str, exclusion_text: str, title: str, summary: str) -> tuple:
    """사용자 업종이 공고 exclusion_rules에 해당하면 제외 (명시적 배제만).

    B안 전환: 타 분야 지정 공고(관광/체육/에너지 등)는 관심분야 버킷이
    자연스럽게 분리하므로 여기서는 명시적 exclusion_rules만 체크.

    예: 공고가 "부동산임대업 제외"를 명시 + 사용자 업종=부동산임대업 → 제외.
    Returns: (excluded: bool, reason: str or None)
    """
    if not user_industry_code:
        return False, None
    major = str(user_industry_code)[:2]
    search_text = f"{exclusion_text} {title} {summary}".lower()

    # 사용자 업종이 공고 exclusion_rules/본문에서 명시적으로 배제되는지
    user_excl_kws = INDUSTRY_EXCLUSION_KEYWORDS.get(major, [])
    for kw in user_excl_kws:
        if kw.lower() in search_text:
            return True, f"{kw} 제외 대상"
    return False, None


def _check_region_exclusion(user_city_normalized: str, ann_region: str, ann_title: str) -> tuple:
    """공고가 특정 지역 전용인데 사용자 지역과 다르면 제외.

    검사 순서:
      1. 제목에 [전국] 있으면 통과
      2. 제목에 [시·도명] 있으면 그 지역과 사용자 지역 비교
      3. ann.region 필드 검사
    """
    title = ann_title or ""
    # 1. [전국] 패턴이면 통과
    if "[전국]" in title:
        return False, None
    if not user_city_normalized:
        return False, None  # 사용자 지역 모르면 통과

    # 2. 제목에 [지역명] 패턴이 있으면 우선 체크 (region 필드보다 신뢰도 높음)
    import re as _re
    bracket_match = _re.search(
        r'\[(서울|경기|인천|부산|대구|대전|광주|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)\]',
        title
    )
    if bracket_match:
        title_region = bracket_match.group(1)
        title_region_norm = _normalize_region(title_region)
        if (title_region_norm == user_city_normalized
            or user_city_normalized in title_region_norm
            or title_region_norm in user_city_normalized):
            return False, None  # 사용자 지역과 일치 → 통과
        return True, f"[{title_region}] 지역 전용"  # 다른 지역 전용 → 제외

    # 3. ann.region 필드 체크
    if not ann_region or ann_region in ("전국", "All", "전국단위", ""):
        return False, None
    normalized_ann = _normalize_region(ann_region)
    if not normalized_ann or normalized_ann in ("전국", "All"):
        return False, None
    if (normalized_ann == user_city_normalized
        or user_city_normalized in normalized_ann
        or normalized_ann in user_city_normalized):
        return False, None
    return True, f"{ann_region} 지역 전용"


def _load_exclusion_rules_bulk(db_conn, announcement_ids: list) -> dict:
    """공고 ID 리스트 → {announcement_id: exclusion_text} 일괄 조회."""
    if not announcement_ids or not db_conn:
        return {}
    try:
        cur = db_conn.cursor()
        cur.execute("""
            SELECT announcement_id, deep_analysis->'exclusion_rules' AS rules
            FROM announcement_analysis
            WHERE announcement_id = ANY(%s)
              AND deep_analysis IS NOT NULL
        """, (announcement_ids,))
        result = {}
        for row in cur.fetchall():
            rules = row.get("rules") if hasattr(row, "get") else row[1]
            ann_id = row.get("announcement_id") if hasattr(row, "get") else row[0]
            if rules:
                result[ann_id] = _extract_exclusion_text(rules)
        return result
    except Exception as e:
        print(f"[hard_filter] exclusion_rules bulk load failed: {e}")
        return {}


def _hard_filter_business(candidates: list, user_profile: dict, db_conn=None) -> tuple:
    """기업 사용자 0단계 하드 필터.
    SQL로 이미 걸러진 업력/매출/직원 외에:
    - 지역 전용 공고 제외
    - AI 추출 exclusion_rules 기반 업종 제외
    - 제목/요약의 보편적 제외 키워드
    Returns: (passed: list, excluded: list of {ad, reasons})
    """
    user_industry = user_profile.get("industry_code") or ""
    raw_city = user_profile.get("address_city") or ""
    user_city_norm = ""
    if raw_city:
        first_city = raw_city.split(",")[0].strip()
        user_city_norm = _normalize_region(first_city)
    # 일괄 exclusion_rules 조회
    ann_ids = [c.get("announcement_id") for c in candidates if c.get("announcement_id")]
    exclusion_map = _load_exclusion_rules_bulk(db_conn, ann_ids)

    passed = []
    excluded = []
    for ad in candidates:
        ann_id = ad.get("announcement_id")
        title = ad.get("title") or ""
        summary = _strip_html(ad.get("summary_text") or "")[:500]
        region = ad.get("region") or ""
        reasons = []

        # 1. 지역 전용 제외
        region_excl, region_reason = _check_region_exclusion(user_city_norm, region, title)
        if region_excl:
            reasons.append(region_reason)

        # 2. 업종 제외 (exclusion_rules + 제목/요약)
        excl_text = exclusion_map.get(ann_id, "")
        ind_excl, ind_reason = _check_industry_exclusion(user_industry, excl_text, title, summary)
        if ind_excl:
            reasons.append(ind_reason)

        if reasons:
            excluded.append({"ad": ad, "reasons": reasons})
        else:
            passed.append(ad)
    return passed, excluded


def _hard_filter_individual(candidates: list, user_profile: dict, db_conn=None) -> tuple:
    """개인 사용자 0단계 하드 필터.
    - 지역 전용 공고 제외
    - 연령 제한: eligibility_logic에 max_age/min_age 있으면 확인
    - exclusion_rules 기반 제외 (개인 대상 사업도 제외 조건 있음)
    """
    raw_city = user_profile.get("address_city") or ""
    user_city_norm = ""
    if raw_city:
        first_city = raw_city.split(",")[0].strip()
        user_city_norm = _normalize_region(first_city)

    passed = []
    excluded = []
    for ad in candidates:
        title = ad.get("title") or ""
        region = ad.get("region") or ""
        reasons = []

        # 지역 전용 제외
        region_excl, region_reason = _check_region_exclusion(user_city_norm, region, title)
        if region_excl:
            reasons.append(region_reason)

        if reasons:
            excluded.append({"ad": ad, "reasons": reasons})
        else:
            passed.append(ad)
    return passed, excluded


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

    # ═══════════════════════════════════════════════════════════
    # 0단계: 하드 필터 — 자격 미달 공고 즉시 제외
    # (업력/매출/직원은 SQL에서 이미 필터링됨. 여기서는 지역·업종·제외규칙)
    # ═══════════════════════════════════════════════════════════
    candidates, _hard_excluded = _hard_filter_business(candidates, user_profile, conn)
    conn.close()

    if _hard_excluded:
        print(f"[hard_filter_biz] passed={len(candidates)}, excluded={len(_hard_excluded)}")

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

        # 정보/안내 페이지 필터 — 실제 공고가 아닌 기관 소개·행사 등 제외
        _info_page_keywords = ["소개", "안내 페이지", "지원시책", "지원 관련 기관", "상담 예약 현황",
                               "발대식", "개최", "개소식", "행사 안내", "설명회 안내", "상담 예약",
                               "만족도 조사", "조사 안내", "페스티벌", "페스티발", "축제",
                               "예약 현황", "원스톱", "상담 현황"]
        if any(kw in title for kw in _info_page_keywords) and not any(kw in title for kw in ["모집 공고", "참여기업 모집", "참여 기업 모집", "대상자 모집"]):
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

        # C. 관심분야 키워드 매칭 (관심 일치 여부 플래그 + 최대 35점)
        ad["interest_matched"] = False  # 기본값
        ad["matched_interests"] = []
        if interest_keywords:
            matched_interests = [kw for kw in interest_keywords if kw.lower() in search_text]
            if matched_interests:
                ad["interest_matched"] = True
                # 어떤 관심분야가 일치했는지 저장 (프론트 뱃지용)
                for tag in user_interest_tags:
                    tag_kws = INTEREST_KEYWORD_MAP.get(tag, [tag])
                    if any(kw.lower() in search_text for kw in tag_kws):
                        ad["matched_interests"].append(tag)
                interest_score = min(35.0, len(set(matched_interests)) * 6.0)
                score += interest_score
                if ad["matched_interests"]:
                    reasons.append(f'"{ad["matched_interests"][0]}" 관심분야 부합')

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
    """개인 사용자 프로필 기반 복지/지원서비스 매칭.

    설계 철학 (기업 매칭과 완전히 다름):
    - 개인 공고 대부분이 '전 국민' 대상 → 점수화·컷오프 하지 않음
    - 오직 '역 조건 배제'만 적용:
      ① 연령 전용 공고(예: "65세 이상만")인데 사용자 연령대가 다름 → 제외
      ② 가구형태 전용(예: "한부모 가구만")인데 다름 → 제외
      ③ 소득 전용(예: "기초생활수급자만")인데 다름 → 제외
      ④ 지역 전용(예: "[부산] 전용")인데 다름 → 제외 (이미 _hard_filter_individual에서 처리)
      ⑤ 마감 지남 → 제외
    - 관심 키워드 매칭 시 interest_matched=True (버킷 레이어에서 🎯 그룹)
    - 나머지는 모두 통과 → ✅ 참고 버킷으로
    """
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

    # ═══════════════════════════════════════════════════════════
    # 0단계: 하드 필터 — 자격 미달 공고 즉시 제외 (개인)
    # ═══════════════════════════════════════════════════════════
    candidates, _hard_excluded = _hard_filter_individual(candidates, user_profile, conn)
    conn.close()

    if _hard_excluded:
        print(f"[hard_filter_indiv] passed={len(candidates)}, excluded={len(_hard_excluded)}")

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

    # 관심분야 → 키워드 확장 (기업 매칭과 동일 구조)
    interest_keywords = []
    for tag in user_interest_tags:
        if tag in INTEREST_KEYWORD_MAP:
            interest_keywords.extend(INTEREST_KEYWORD_MAP[tag])
        elif tag in SYNONYM_MAP:
            interest_keywords.extend(SYNONYM_MAP[tag])
        else:
            interest_keywords.append(tag)
    # custom_keywords 합치기
    interest_keywords.extend(custom_kw_list)

    today = datetime.date.today()
    results = []

    # 역조건(명시 전용) 그룹 — 사용자가 그 유형이 아니면 제외
    AGE_EXCLUSIVE_MAP = {
        "20대": ["노인", "어르신", "65세 이상", "고령자", "시니어"],
        "30대": ["노인", "어르신", "65세 이상", "고령자", "시니어"],
        "40대": ["노인 전용", "어르신 전용", "65세 이상 전용", "대학생 전용"],
        "50대": ["대학생", "청소년", "만 18세 이하"],
        "60대 이상": ["청년", "청소년", "대학생"],
    }
    FAMILY_EXCLUSIVE_MAP = {
        "1인가구": ["한부모 전용", "다자녀 전용", "신혼부부 전용"],
        "한부모가족": [],  # 한부모 전용 공고는 통과해야 함
        "다자녀가족": [],
        "신혼부부": [],
        "일반": ["한부모 전용", "다자녀 전용"],
    }

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

        # 만료 연도 필터
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

        # 정보/안내 페이지 필터
        _info_kws = ["소개", "안내 페이지", "지원시책", "지원 관련 기관", "상담 예약 현황",
                     "발대식", "개최", "개소식", "행사 안내", "설명회 안내", "상담 예약",
                     "만족도 조사", "조사 안내", "페스티벌", "페스티발", "축제",
                     "예약 현황", "원스톱", "상담 현황"]
        if any(kw in raw_title for kw in _info_kws) and not any(kw in raw_title for kw in ["모집 공고", "참여기업 모집", "참여 기업 모집", "대상자 모집"]):
            continue

        search_text = f"{title} {target_desc} {clean_summary} {sel_criteria}"

        # 지역 필터 — 소재지 기반
        ad_region = _normalize_region(ad.get("region") or "")
        if ad_region and ad_region not in ("전국", "", "All"):
            if has_home and ad_region != home_city:
                continue

        # 마감 지남 제외
        if ad.get("deadline_date"):
            try:
                deadline_val = ad["deadline_date"]
                if isinstance(deadline_val, (datetime.date, datetime.datetime)):
                    deadline = deadline_val if isinstance(deadline_val, datetime.date) else deadline_val.date()
                else:
                    deadline = datetime.datetime.strptime(str(deadline_val), "%Y-%m-%d").date()
                if (deadline - today).days < 0:
                    continue
            except (ValueError, TypeError):
                pass

        # ═══ 역조건 배제 (명시적으로 다른 대상 전용인 경우만) ═══
        exclude = False
        # 1. 연령 역조건
        age_ex_kws = AGE_EXCLUSIVE_MAP.get(user_age, [])
        if age_ex_kws and target_desc:
            # '전용' 표기된 경우 제외. target_desc에 본인 연령대 키워드가 없고 상대 연령대만 있으면 제외.
            self_age_present = any(kw in target_desc for kw in age_keywords)
            other_age_present = any(kw in target_desc for kw in age_ex_kws)
            if other_age_present and not self_age_present:
                exclude = True

        # 2. 가구형태 역조건
        family_ex_kws = FAMILY_EXCLUSIVE_MAP.get(user_family, [])
        if not exclude and family_ex_kws and target_desc:
            if any(kw in target_desc for kw in family_ex_kws):
                exclude = True

        # 3. 한부모/다자녀 전용 공고인데 사용자가 그 유형이 아님
        if not exclude and target_desc:
            if "한부모 전용" in target_desc and user_family != "한부모가족":
                exclude = True
            elif "다자녀 전용" in target_desc and user_family != "다자녀가족":
                exclude = True

        # 4. 기초생활수급자 전용인데 사용자가 다름
        if not exclude and user_income not in ("저소득", "기초생활", "차상위") and target_desc:
            if "기초생활수급자 전용" in target_desc or "수급자만" in target_desc:
                exclude = True

        if exclude:
            continue

        # ═══ 관심 일치 플래그 설정 (🎯 버킷 분류용) ═══
        matched_interests = []
        interest_matched = False
        if interest_keywords:
            hits = [kw for kw in interest_keywords if kw.lower() in search_text]
            if hits:
                interest_matched = True
                for tag in user_interest_tags:
                    tag_kws = INTEREST_KEYWORD_MAP.get(tag, [tag])
                    if any(kw.lower() in search_text for kw in tag_kws):
                        matched_interests.append(tag)

        ad["interest_matched"] = interest_matched
        ad["matched_interests"] = matched_interests

        # 추천 사유 (UI 표시용)
        reasons = []
        if interest_matched and matched_interests:
            reasons.append(f'"{matched_interests[0]}" 관심분야')
        if ad_region == home_city and home_city:
            reasons.append(f"{home_city} 거주지역")
        elif not ad_region or ad_region in ("전국", "All"):
            reasons.append("전국 대상")
        ad["recommendation_reason"] = " / ".join(reasons[:2]) if reasons else "지원 가능"

        # match_score는 제거. 버킷 레이어에서 rank만 부여
        results.append(ad)

    # 점수화·컷오프 없음 → 제외되지 않은 모든 공고 반환
    # 정렬: 관심 일치 → 마감 유효 → 최신 순
    def _indiv_sort_key(r):
        interest_rank = 0 if r.get("interest_matched") else 1
        amt = str(r.get("support_amount") or "")
        has_amt = 0 if (any(c.isdigit() for c in amt) and any(k in amt for k in ("원", "억", "만"))) else 1
        dl_ok = 0 if _is_deadline_valid(r.get("deadline_date")) else 1
        return (interest_rank, has_amt, dl_ok)

    results.sort(key=_indiv_sort_key)
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


def _classify_bucket(match_item: dict, user_profile: dict, bucket_order: list = None) -> str:
    """공고를 버킷에 배정.
    bucket_order의 상위 3개(로테이션 결과) 순서대로 분류를 시도.
    이렇게 하면 오늘 1위 버킷이 분류에서도 우선권을 가져
    좋은 공고를 독점하지 않고 고르게 분배됨.
    """
    title = match_item.get("title") or ""
    category = match_item.get("category") or ""
    region = match_item.get("region") or ""
    search_text = f"{title} {category} {match_item.get('summary_text') or ''}".lower()

    # 각 버킷 매칭 여부를 미리 계산
    # interest 매칭
    is_interest = False
    user_interests = (user_profile.get("interests") or "").split(",") if user_profile.get("interests") else []
    user_kws = (user_profile.get("custom_keywords") or "").split(",") if user_profile.get("custom_keywords") else []
    for tag in user_interests + user_kws:
        tag = (tag or "").strip()
        if not tag:
            continue
        if tag.lower() in search_text:
            is_interest = True
            break
        expanded = INTEREST_KEYWORD_MAP.get(tag, [])
        if any(kw.lower() in search_text for kw in expanded):
            is_interest = True
            break

    # region 매칭 — DB region 필드 + 제목 [도시명] 패턴 모두 체크
    is_region = False
    addr_raw = (user_profile.get("address_city") or "")
    user_cities = [c.strip() for c in addr_raw.split(",") if c.strip() and c.strip() != "전국"]
    if user_cities:
        if region and region not in ("전국", "All", "") and any(uc in region or region in uc for uc in user_cities):
            is_region = True
        if not is_region:
            import re as _re
            _bracket = _re.search(r'\[(서울|경기|인천|부산|대구|대전|광주|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)\]', title)
            if _bracket and _bracket.group(1) in user_cities:
                is_region = True

    # national_fund 매칭 — 전국 범위(region 비어있거나 전국)이면서 자금 관련
    is_national_fund = False
    effective_region = region
    if not effective_region or effective_region in ("전국", "All", ""):
        import re as _re2
        _br2 = _re2.search(r'\[(서울|경기|인천|부산|대구|대전|광주|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)\]', title)
        if _br2:
            effective_region = _br2.group(1)
    if (not effective_region or effective_region in ("전국", "All", "")) and _is_fund_related(title, category):
        is_national_fund = True

    # 로테이션 순서대로 분류 (상위 3버킷)
    bucket_checks = {
        "interest": is_interest,
        "region": is_region,
        "national_fund": is_national_fund,
    }
    top_3 = (bucket_order or _BUCKET_ORDER_BASE)[:3]
    for b in top_3:
        if bucket_checks.get(b, False):
            return b

    # 하위 버킷 (고정 순서)
    dleft = _days_left(match_item.get("deadline_date"))
    if 0 <= dleft <= 30:
        return "deadline"

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

# 새 버킷 라벨 (B안 — 관심 일치 + 참고 2단)
_BUCKET_LABELS_V2 = {
    "interest_match": "🎯 관심 분야 일치",
    "qualified_other": "✅ 자격 통과 (참고)",
    "deadline_urgent": "⏰ 마감 임박 (놓치면 아쉬운)",
}


# 사용자 업종 대분류 → 공고 관련 키워드 (제목/요약에 있으면 "업종 근접" 가산)
# 관심 기반 우선순위 + 업종 근접도 2차 정렬로 품질 향상
INDUSTRY_AFFINITY_KEYWORDS = {
    "62": ["소프트웨어", "IT", "ICT", "AI", "인공지능", "디지털", "SaaS", "플랫폼", "앱", "딥테크", "기술창업", "R&D", "스타트업"],
    "63": ["정보서비스", "데이터", "플랫폼", "IT", "디지털", "콘텐츠"],
    "10": ["제조", "생산", "품질", "공장", "스마트공장", "자동화", "설비"],
    "26": ["전자", "반도체", "부품", "전기전자", "스마트"],
    "28": ["기계", "제조", "스마트공장", "자동화", "설비"],
    "46": ["도매", "유통", "판로", "수출", "B2B"],
    "47": ["소매", "소상공인", "골목", "유통", "판로"],
    "41": ["건설", "건축", "토목", "시공", "인프라"],
    "01": ["농업", "영농", "작물", "축산", "시설농업", "스마트팜"],
    "03": ["어업", "수산", "양식"],
    "20": ["화학", "소재", "신소재"],
    "21": ["제약", "바이오", "의약품"],
    "86": ["의료", "헬스케어", "병원", "진료"],
    "58": ["출판", "콘텐츠", "교육"],
    "72": ["연구", "R&D", "기술개발"],
}


def _industry_affinity_score(r: dict, user_major: str) -> int:
    """공고 제목·요약에서 사용자 업종 관련 키워드 매치 개수 반환 (높을수록 근접)."""
    if not user_major:
        return 0
    kws = INDUSTRY_AFFINITY_KEYWORDS.get(user_major, [])
    if not kws:
        return 0
    search = ((r.get("title") or "") + " " + (r.get("summary_text") or ""))[:800].lower()
    count = 0
    for kw in kws:
        if kw.lower() in search:
            count += 1
    return count


def _apply_bucket_layer_v2(results: list, user_profile: dict) -> list:
    """B안 — 관심 일치 + 참고 2단 버킷 (사용자 의도 우선).

    버킷:
    - 🎯 interest_match: 관심분야 일치 (사용자가 선택한 키워드 매칭)
    - ⏰ deadline_urgent: 마감 D-7 이내 (관심 여부 무관, 놓치면 아쉬움)
    - ✅ qualified_other: 자격 통과지만 관심분야 외 (참고)

    각 버킷 내부 정렬:
      1순위: 사용자 업종 근접도 (제목/요약 키워드 매치 수) ← NEW
      2순위: 실제 금액 명시
      3순위: 마감 유효
      4순위: 금액 큰 순
    """
    if not results:
        return results

    # 자격 미달(지역 불일치/소상공인 아닌데 소상공인 전용 등) 완전 제외
    pre_count = len(results)
    results = [r for r in results if r.get("eligibility_status") != "ineligible"]
    if pre_count != len(results):
        print(f"[bucket_v2] ineligible 제외: {pre_count - len(results)}건")

    user_major = str(user_profile.get("industry_code") or "")[:2]

    def _bucket_of(r):
        # 마감 임박 우선 체크 (관심과 무관하게 놓치면 아쉬운 공고)
        dl = _days_left(r.get("deadline_date"))
        if dl is not None and 0 <= dl <= 7:
            return "deadline_urgent"
        if r.get("interest_matched"):
            return "interest_match"
        return "qualified_other"

    for r in results:
        b = _bucket_of(r)
        r["bucket"] = b
        r["bucket_label"] = _BUCKET_LABELS_V2.get(b, b)
        # 업종 근접도 계산 (저장해서 정렬·UI에 활용 가능)
        r["industry_affinity"] = _industry_affinity_score(r, user_major)

    def _sort_key(r):
        # 업종 근접도가 높을수록 앞 (desc → 음수)
        affinity = -(r.get("industry_affinity") or 0)
        amt_str = str(r.get("support_amount") or "")
        has_real_amount = 0 if (any(c.isdigit() for c in amt_str) and any(k in amt_str for k in ("원", "억", "만"))) else 1
        deadline_ok = 0 if _is_deadline_valid(r.get("deadline_date")) else 1
        amount = -_amount_value(amt_str)
        return (affinity, has_real_amount, deadline_ok, amount)

    # 버킷별 그룹 (정해진 순서)
    bucket_order = ["interest_match", "deadline_urgent", "qualified_other"]
    grouped = {b: [] for b in bucket_order}
    for r in results:
        grouped.get(r.get("bucket"), grouped["qualified_other"]).append(r)

    final = []
    for b in bucket_order:
        items = grouped[b]
        items.sort(key=_sort_key)
        for r in items:
            # 뱃지 재구성
            reasons_arr = []
            if b == "interest_match":
                tags = r.get("matched_interests") or []
                if tags:
                    reasons_arr.append({"icon": "🎯", "label": tags[0]})
                else:
                    reasons_arr.append({"icon": "🎯", "label": "관심일치"})
            elif b == "deadline_urgent":
                dl = _days_left(r.get("deadline_date"))
                if dl is not None:
                    reasons_arr.append({"icon": "⏰", "label": f"D-{dl}"})
            if _is_fund_related(r.get("title", ""), r.get("category", "")):
                reasons_arr.append({"icon": "💰", "label": "자금"})
            r["reasons"] = reasons_arr
            final.append(r)

    # 순위 부여 (match_score 제거 합의에 따라 rank만)
    for idx, r in enumerate(final):
        r["rank"] = idx + 1
        r.pop("match_score", None)
    return final


def _apply_bucket_layer(results: list, user_profile: dict) -> list:
    """매칭 결과에 버킷 분류 + 2차 정렬 + 합성 score 부여.

    로테이션 순서를 분류 우선순위에도 적용하여 3개 버킷이 진정 동등.
    점수 범위: 1등 95~99 / 2등 88~94 / 3등 82~87 / 4등 76~81 / 5등 70~75
    버킷 내부: 실제금액(+) → 자금키워드(+) → 마감유효(+) → 금액 큰 순.
    """
    if not results:
        return results

    bucket_order = _rotate_buckets(user_profile)
    bucket_to_rank = {b: i for i, b in enumerate(bucket_order)}

    # 1) 각 아이템에 버킷 부여 (로테이션 순서를 분류 우선순위로도 사용)
    for r in results:
        b = _classify_bucket(r, user_profile, bucket_order)
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

    # 3) 버킷 순서대로 내부 정렬 후 연결 — 순위=순서 (점수화 없음)
    final: list = []
    for b in bucket_order:
        items = grouped.get(b, [])
        items.sort(key=_sort_key)
        for r in items:
            # reasons 배열 (프론트 뱃지용)
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

    # 순위만 유지 (점수화 제거 합의에 따라 match_score 필드 제거)
    # 프론트는 rank 또는 배열 순서로 정렬하므로 점수 불필요
    for idx, r in enumerate(final):
        r["rank"] = idx + 1  # 1등부터 순위
        # match_score 완전 제거 (기존 점수 계산값도 삭제)
        r.pop("match_score", None)

    return final


def get_matches_hybrid(user_profile: dict, is_individual: bool = False, skip_bucket: bool = False) -> list:
    """하이브리드 매칭 — USE_EMBEDDING_MATCHING 환경변수 ON일 때만 임베딩 사용.
    OFF 또는 실패 시 기존 rule-based 함수로 자동 fallback.
    skip_bucket=True면 버킷 레이어를 건너뜀 (both 모드에서 합산 후 1회 적용 용도).
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

    if skip_bucket:
        return results

    # 버킷 분류 + 순서 정렬 후처리 (B안 — 관심 우선 + 참고 2단)
    try:
        results = _apply_bucket_layer_v2(results, user_profile)
    except Exception as e:
        print(f"[MatchHybrid] bucket_v2 layer error (fallback raw): {e}")
        # 구버전 폴백
        try:
            results = _apply_bucket_layer(results, user_profile)
        except Exception:
            pass
    return results
