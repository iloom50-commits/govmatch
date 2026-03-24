from typing import Dict, Any, List
from datetime import datetime, date

# 지역명 정규화: AI가 다양한 형태로 추출하는 지역명을 표준화
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

def _normalize_region(region: str) -> str:
    if not region:
        return ""
    return REGION_NORMALIZE.get(region.strip(), region.strip())


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
