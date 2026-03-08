import sqlite3
import datetime
import json
from app.services.ai_service import ai_service
from app.services.rule_engine import rule_engine

def get_db_connection(db_path="gov_matching.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_matches_for_user(user_profile):
    """
    고도화된 매칭 엔진: 하드 필터링 + 시맨틱 검색 + AI 심층 분석
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 1차 필터링: 지역 및 기본적인 업력 체크 (SQL)
    est_date_str = user_profile.get("establishment_date", "2020-01-01")
    est_date = datetime.datetime.strptime(est_date_str, "%Y-%m-%d")
    today = datetime.date.today()
    company_age = today.year - est_date.year - ((today.month, today.day) < (est_date.month, est_date.day))
    
    # 매출 및 인원 브래킷 변환 (하이브리드 필터링용)
    revenue_map = {"UNDER_1B": 100000000, "1B_TO_5B": 500000000, "5B_TO_10B": 1000000000, "OVER_10B": 10000000000, "1억 미만": 100000000, "1억~5억": 500000000, "5억~10억": 1000000000, "10억~50억": 5000000000, "50억 이상": 10000000000}
    employee_map = {"UNDER_5": 5, "5_TO_10": 10, "10_TO_50": 50, "OVER_50": 100, "5인 미만": 5, "5인~10인": 10, "10인~30인": 30, "30인~50인": 50, "50인 이상": 100}
    
    user_rev = revenue_map.get(user_profile.get("revenue_bracket") or user_profile.get("revenue"), 0)
    user_emp = employee_map.get(user_profile.get("employee_count_bracket") or user_profile.get("employees"), 0)

    query = """
    SELECT * FROM announcements 
    WHERE (region = '전국' OR region = 'All' OR region LIKE ?)
    AND (established_years_limit IS NULL OR established_years_limit >= ?)
    AND (revenue_limit IS NULL OR revenue_limit >= ?)
    AND (employee_limit IS NULL OR employee_limit >= ?)
    """
    cursor.execute(query, (f'%{user_profile["address_city"]}%', company_age, user_rev, user_emp))
    candidates = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if not candidates:
        return []

    results = []
    
    # 2. 2차 상세 분석: RuleEngine & AI Scoring
    for ad in candidates:
        # AI가 추출한 구조화된 로직 파싱
        eligibility_logic = {}
        if ad.get("eligibility_logic"):
            try:
                eligibility_logic = json.loads(ad["eligibility_logic"])
            except (json.JSONDecodeError, TypeError):
                pass
        
        # 규칙 기반 검증
        rule_result = rule_engine.evaluate(user_profile, eligibility_logic)
        
        # 3. 점수 계산 로직 (v8: Eligibility > Industry > Deadline)
        score = 0.0
        reasons = []

        # A. 자격 요건 (기본 60점, 부적합 시 페널티)
        if rule_result["is_eligible"]:
            score += 60.0
            reasons.append("기본 지원 자격 충족")
        else:
            # Hard Filter: 자격 미달 시 결과에서 즉시 제외
            continue

        # B. 업종 코드 매칭 (최대 30점)
        user_ksic = str(user_profile.get("industry_code", "")).strip()
        target_ksics = str(ad.get("target_industry_codes", "")).strip()
        
        if user_ksic and target_ksics:
            industry_bonus = 0.0
            targets = [t.strip().lower() for t in target_ksics.split(",") if t.strip()]
            
            # 1. "전업종" (All industries) check
            if any("전업종" in t for t in targets) or any("none" in t for t in targets):
                industry_bonus = 15.0 # Basic bonus for universal applicability
                reasons.append("전업종 대상 사업")

            # 2. Key Category Mapping (for legacy data compatibility)
            # Mapping common KSIC categories to keywords
            category_keywords = []
            if user_ksic.startswith("58") or user_ksic.startswith("61") or user_ksic.startswith("62") or user_ksic.startswith("63"):
                category_keywords.extend(["it", "정보통신", "소프트웨어", "디지털"])
            if user_ksic.startswith("10") or user_ksic.startswith("34") or "c" in user_ksic.lower():
                category_keywords.extend(["제조", "공장", "설비", "기계"])
            if user_ksic.startswith("70") or user_ksic.startswith("71"):
                category_keywords.extend(["서비스", "컨설팅", "전문"])

            # Exact match (5 digits)
            if any(user_ksic == t for t in targets):
                industry_bonus = 30.0
                reasons.append("주업종 완벽 일치")
            # Keyword match (if user's industry category matches target keyword)
            elif any(kw in t for kw in category_keywords for t in targets):
                industry_bonus = 25.0
                reasons.append("산업 분야 부합")
            # Group match (3 digits)
            elif any(user_ksic[:3] == t[:3] for t in targets if t.isdigit()):
                industry_bonus = 15.0
                reasons.append("유사 업종군 포함")
            
            score += industry_bonus

        # C. 마감일 가중치 및 필터 (최대 10점)
        if ad.get("deadline_date"):
            try:
                deadline = datetime.datetime.strptime(ad["deadline_date"], "%Y-%m-%d").date()
                days_left = (deadline - today).days
                
                # Hard Filter: Expired announcements
                if days_left < 0:
                    continue
                    
                if 0 <= days_left <= 7:
                    score += 10.0
                    reasons.append("마감 임박 (7일 이내)")
                elif 0 <= days_left <= 14:
                    score += 5.0
                    reasons.append("신청 권장 (14일 이내)")
            except (ValueError, TypeError):
                pass

        # D. 지역 키워드 쉴드 (Region Keyword Shield)
        # 제목에 특정 도시명이 포함되어 있는데 사용자의 도시와 다르면 제외
        # 단, DB 상 region 이 '전국'이나 'All'인 경우에는 고의적인 지역 한정 공고가 아닐 가능성이 높으므로 통과
        city_keywords = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
        user_city = user_profile.get("address_city", "")
        title = ad.get("title", "")
        db_region = ad.get("region", "")
        
        if db_region not in ["전국", "All"]:
            found_city = None
            for city in city_keywords:
                if city in title:
                    found_city = city
                    break
            
            if found_city and user_city and found_city not in user_city:
                continue

        # E. 업종 미지정 유저를 위한 최소 점수 보정 (v9)
        if not reasons or ("기본 지원 자격 충족" in reasons and len(reasons) == 1):
             if not user_ksic or user_ksic == "00000":
                 score += 15.0
                 reasons.append("전업종 범용 지원사업")

        ad["match_score"] = score
        # 앞의 2가지 주요 사유만 노출
        ad["recommendation_reason"] = " / ".join(reasons[:2])
        results.append(ad)
    
    # 점수 순 정렬
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:20]
