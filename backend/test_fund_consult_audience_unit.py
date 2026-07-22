# -*- coding: utf-8 -*-
"""fund_consult 화법 audience 모드 단위 테스트.

build_pro_fund_biz_prompt(audience):
- 미지정/"consultant" → 원본(전문가↔고객사 3인칭) 그대로(하위호환).
- "applicant" → 사업주 본인 대면 2인칭. '고객사' 0건·'귀사' 포함·'3인칭 필수' 규칙 제거.

배경: SmartDoc 자금상담AI가 이 API의 순수 프록시라, 대화 상대가 곧 사업주 본인인데
원본 프롬프트가 "사장님/귀하 금지 → 반드시 고객사"를 강제해 3인칭으로 답했다. 프록시 측
steering으론 이 규칙을 못 이겨(비결정) 프롬프트 자체를 결정론 치환한다.

실행: cd backend && python test_fund_consult_audience_unit.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from app.services.prompts import build_pro_fund_biz_prompt, PROMPT_PRO_FUND_BIZ_TOOL


def test_default_is_original():
    assert build_pro_fund_biz_prompt() is PROMPT_PRO_FUND_BIZ_TOOL
    assert build_pro_fund_biz_prompt("consultant") is PROMPT_PRO_FUND_BIZ_TOOL
    assert build_pro_fund_biz_prompt("") is PROMPT_PRO_FUND_BIZ_TOOL


def test_applicant_is_second_person():
    ap = build_pro_fund_biz_prompt("applicant")
    assert ap.count("고객사") == 0, f"'고객사' 잔존 {ap.count('고객사')}건"
    assert "귀사" in ap
    assert "3인칭 필수" not in ap
    assert "화법 (2인칭" in ap
    assert "사업주" in ap


def test_original_not_mutated():
    # 빌더가 원본 상수를 오염시키지 않아야 한다(전문가용 3인칭 유지).
    build_pro_fund_biz_prompt("applicant")
    assert "3인칭 필수" in PROMPT_PRO_FUND_BIZ_TOOL
    assert PROMPT_PRO_FUND_BIZ_TOOL.count("고객사") > 0


if __name__ == "__main__":
    test_default_is_original()
    test_applicant_is_second_person()
    test_original_not_mutated()
    print("PASS: fund_consult audience 3 tests")
