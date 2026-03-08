from typing import Dict, Any, List
from datetime import datetime

class RuleEngine:
    """정부지원사업 적합성 판별을 위한 규칙 엔진"""
    
    def evaluate(self, profile: Dict[str, Any], eligibility: Dict[str, Any]) -> Dict[str, Any]:
        """
        기업 프로필과 공고의 자격 요건을 비교하여 적합성 판별
        
        Args:
            profile: 기업 프로필 (founding_date, revenue, employees, city, business_type)
            eligibility: AI가 추출한 구조화된 자격 요건
            
        Returns:
            {"is_eligible": bool, "reasons": List[str]}
        """
        reasons = []
        is_eligible = True
        
        if not eligibility:
            # AI 분석 데이터가 없을 경우 기본적으로 통과시키되, 
            # matcher에서 수행한 1차 SQL 필터링에 의존함.
            return {"is_eligible": True, "reasons": ["세부 자격 요건 분석 중 (기본 요건 검토 완료)"]}

        # 1. 창업 공력 (업력) 체크
        if eligibility.get("max_founding_years") is not None and profile.get("establishment_date"):
            try:
                est_date = datetime.strptime(profile["establishment_date"], "%Y-%m-%d")
                years = (datetime.now() - est_date).days / 365.25
                if years > eligibility["max_founding_years"]:
                    is_eligible = False
                    reasons.append(f"업력 초과 (제한 {eligibility['max_founding_years']}년)")
            except (ValueError, TypeError):
                pass

        # 2. 지역 제한 체크
        region_restriction = eligibility.get("region_restriction") or "전국"
        user_city = profile.get("address_city") or ""
        if isinstance(region_restriction, str) and region_restriction != "전국" and user_city:
            if region_restriction not in user_city:
                is_eligible = False
                reasons.append(f"지역 불일치 (제한: {region_restriction})")

        # 3. 매출액 체크 (간단한 매핑 기반)
        if eligibility.get("min_revenue") and (profile.get("revenue_bracket") or profile.get("revenue")):
            # "1억 미만" -> 0, "1억~5억" -> 1e8, etc.
            rev_map = {
                "1억 미만": 0, "1억~5억": 1e8, "5억~10억": 5e8, "10억~50억": 10e8, "50억 이상": 50e8,
                "UNDER_1B": 0, "1B_TO_5B": 1e8, "5B_TO_10B": 5e8, "OVER_10B": 10e8
            }
            company_rev = rev_map.get(profile.get("revenue_bracket") or profile.get("revenue"), 0)
            if company_rev < eligibility["min_revenue"]:
                is_eligible = False
                reasons.append(f"매출액 부족 (최소 {eligibility['min_revenue']/1e8:.1f}억)")

        # 4. 근로자 수 체크
        if eligibility.get("min_employees") and (profile.get("employee_count_bracket") or profile.get("employees")):
            emp_map = {
                "5인 미만": 0, "5인~10인": 5, "10인~30인": 10, "30인~50인": 30, "50인 이상": 50,
                "UNDER_5": 0, "5_TO_10": 5, "10_TO_50": 10, "OVER_50": 50
            }
            company_emp = emp_map.get(profile.get("employee_count_bracket") or profile.get("employees"), 0)
            if company_emp < eligibility["min_employees"]:
                is_eligible = False
                reasons.append(f"인력 부족 (최소 {eligibility['min_employees']}인)")

        return {
            "is_eligible": is_eligible,
            "reasons": reasons if reasons else ["모든 기본 자격 조건 충족"]
        }

rule_engine = RuleEngine()
