"""정책자금/융자/보증 상담 시 금융 분석 데이터를 프롬프트에 주입하는 헬퍼"""

import json


def build_financial_context(financial_details: dict | None) -> str:
    """financial_details를 상담 프롬프트용 텍스트로 변환

    AI가 "명시되지 않았지만..." 대신 정확한 수치를 답할 수 있도록
    구조화된 금융 데이터를 주입한다.
    """
    if not financial_details:
        return ""

    sections = []

    # 1. 융자 조건
    loan = financial_details.get("loan_conditions") or {}
    if any(loan.values()):
        lines = ["[금융 공고 정밀 분석 — 융자 조건] ★ 아래 데이터가 있으면 반드시 활용하세요"]
        _add_line(lines, "금리 유형", loan.get("interest_rate_type"))
        _add_line(lines, "금리 범위", loan.get("interest_rate_range"))
        _add_line(lines, "우대금리", loan.get("preferential_rate"))
        _add_line(lines, "개인사업자 한도", loan.get("loan_limit_individual"))
        _add_line(lines, "중소기업 한도", loan.get("loan_limit_sme"))
        _add_line(lines, "최대 한도", loan.get("loan_limit_max"))
        _add_line(lines, "시설자금 상환", loan.get("repayment_period_facility"))
        _add_line(lines, "운전자금 상환", loan.get("repayment_period_operating"))
        _add_line(lines, "상환방식", loan.get("repayment_method"))
        _add_line(lines, "자부담 비율", loan.get("self_funding_ratio"))
        sections.append("\n".join(lines))

    # 2. 담보/보증
    coll = financial_details.get("collateral_guarantee") or {}
    if any(coll.values()):
        lines = ["[담보/보증 조건]"]
        _add_line(lines, "담보 종류", coll.get("collateral_types"))
        _add_line(lines, "보증기관", coll.get("guarantee_agencies"))
        _add_line(lines, "보증비율", coll.get("guarantee_ratio"))
        _add_line(lines, "보증료율", coll.get("guarantee_fee_rate"))
        _add_line(lines, "신용등급 기준", coll.get("credit_grade_requirement"))
        sections.append("\n".join(lines))

    # 3. 금융 신청 자격
    elig = financial_details.get("eligibility_financial") or {}
    if any(elig.values()):
        lines = ["[금융 신청 자격 — 상세]"]
        _add_line(lines, "대상 기업", elig.get("target_business_types"))
        _add_line(lines, "설립 연수", elig.get("founding_year_requirement"))
        _add_line(lines, "매출 기준", elig.get("revenue_requirement"))
        _add_line(lines, "직원 수", elig.get("employee_requirement"))
        _add_line(lines, "지역 제한", elig.get("region_restriction"))
        _add_line(lines, "신용등급 제한", elig.get("credit_restriction"))
        _add_line(lines, "재무제표 요건", elig.get("financial_statement_requirement"))
        _add_line(lines, "세금 체납", elig.get("tax_delinquency_restriction"))
        _add_line(lines, "기존 융자 잔액", elig.get("existing_loan_restriction"))
        _add_line(lines, "제외 대상", elig.get("excluded_businesses"))
        sections.append("\n".join(lines))

    # 4. 신청 절차
    proc = financial_details.get("application_process") or {}
    if any(proc.values()):
        lines = ["[신청 절차]"]
        _add_line(lines, "신청 방법", proc.get("application_method"))
        _add_line(lines, "온라인 신청", proc.get("application_url"))
        _add_line(lines, "제출 서류", proc.get("required_documents"))
        _add_line(lines, "심사 기간", proc.get("review_period"))
        _add_line(lines, "심사 기준", proc.get("review_criteria"))
        _add_line(lines, "자금 지급", proc.get("disbursement_timeline"))
        sections.append("\n".join(lines))

    # 5. 특이사항
    notes = financial_details.get("special_notes") or {}
    if any(notes.values()):
        lines = ["[특이사항/주의]"]
        _add_line(lines, "조기상환 수수료", notes.get("early_repayment_penalty"))
        _add_line(lines, "연체이율", notes.get("late_payment_penalty"))
        _add_line(lines, "용도 제한", notes.get("usage_restrictions"))
        _add_line(lines, "사후관리", notes.get("monitoring_requirements"))
        _add_line(lines, "연장/재신청", notes.get("renewal_conditions"))
        sections.append("\n".join(lines))

    if not sections:
        return ""

    return "\n\n".join(sections)


def _add_line(lines: list, label: str, value) -> None:
    """null/빈 값이 아닌 경우에만 라인 추가"""
    if value and str(value).strip() and str(value).lower() != "null":
        lines.append(f"- {label}: {value}")
