"""정책자금/융자/보증 공고 전용 분석 스키마"""

# 금융 공고 감지 키워드
FINANCIAL_KEYWORDS = [
    "정책자금", "융자", "대출", "보증", "금융", "자금지원",
    "운전자금", "시설자금", "사업전환자금", "긴급경영안정",
    "신용보증", "기술보증", "보증수수료", "이차보전",
    "창업자금", "성장자금", "재도전자금",
]

# 카테고리 기반 감지
FINANCIAL_CATEGORIES = ["금융", "보증", "융자"]


def is_financial_announcement(title: str, category: str, support_details: str = "") -> bool:
    """공고가 정책자금/융자/보증 유형인지 판별"""
    text = f"{title} {category} {support_details}".lower()
    return any(kw in text for kw in FINANCIAL_KEYWORDS) or category in FINANCIAL_CATEGORIES


# Gemini에게 추출 요청할 금융 특화 필드
FINANCIAL_EXTRACTION_SCHEMA = {
    "loan_conditions": {
        "description": "융자/대출 조건",
        "fields": {
            "interest_rate_type": "고정/변동/혼합",
            "interest_rate_range": "금리 범위 (예: 연 2.0~3.5%)",
            "preferential_rate": "우대금리 조건 및 감면폭",
            "loan_limit_individual": "개인사업자 한도",
            "loan_limit_sme": "중소기업 한도",
            "loan_limit_max": "최대 한도",
            "repayment_period_facility": "시설자금 상환기간 (거치기간 포함)",
            "repayment_period_operating": "운전자금 상환기간 (거치기간 포함)",
            "repayment_method": "상환방식 (원리금균등/원금균등/만기일시 등)",
            "self_funding_ratio": "자부담 비율",
        }
    },
    "collateral_guarantee": {
        "description": "담보/보증 조건",
        "fields": {
            "collateral_types": "필요 담보 종류 (부동산/보증서/예금 등)",
            "guarantee_agencies": "보증기관 (신보/기보/지역신보재단 등)",
            "guarantee_ratio": "보증비율",
            "guarantee_fee_rate": "보증료율",
            "credit_grade_requirement": "신용등급 기준",
        }
    },
    "eligibility_financial": {
        "description": "금융 관련 신청 자격",
        "fields": {
            "target_business_types": "대상 기업 유형 (제조/서비스/전업종 등)",
            "founding_year_requirement": "설립 연수 기준",
            "revenue_requirement": "매출 기준",
            "employee_requirement": "직원 수 기준",
            "region_restriction": "지역 제한",
            "credit_restriction": "신용등급 제한 (예: BB 이상)",
            "financial_statement_requirement": "재무제표 요건",
            "tax_delinquency_restriction": "세금 체납 제한",
            "existing_loan_restriction": "기존 융자 잔액 제한",
            "excluded_businesses": "제외 대상 업종/기업",
        }
    },
    "application_process": {
        "description": "신청 절차",
        "fields": {
            "application_method": "신청 방법 (온라인/방문/우편 등)",
            "application_url": "온라인 신청 URL",
            "required_documents": "제출 서류 목록",
            "review_period": "심사 소요 기간",
            "review_criteria": "심사 기준 및 배점",
            "disbursement_timeline": "자금 지급 시기",
        }
    },
    "special_notes": {
        "description": "특이사항",
        "fields": {
            "early_repayment_penalty": "조기상환 수수료 여부",
            "late_payment_penalty": "연체이율/불이익",
            "usage_restrictions": "자금 용도 제한",
            "monitoring_requirements": "사후관리/모니터링 조건",
            "renewal_conditions": "연장/재신청 조건",
        }
    }
}
