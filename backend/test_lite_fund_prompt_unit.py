# -*- coding: utf-8 -*-
"""LITE 자금상담 프롬프트 — 중진공 정책자금 상주 지식 (FABLE 설계 2026-07-08) 정적 테스트.

- 필수 자금 지식 존재(버튼 4종 + 재도약 + 핵심 사실)
- 금리·한도 수치 하드코딩 0건(요건 수치 7년/39세/10명은 허용)
- 환각 방지 가드 존재
- 청년나이 버그 수정(만 34세 단정 제거)
- 호환 계약 유지(도구명·choices 마커)

실행: cd backend && python test_lite_fund_prompt_unit.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from app.services.prompts.lite_fund_tool import (
    FUND_DOMAIN_KNOWLEDGE_BIZ, PROMPT_LITE_FUND_BIZ_TOOL,
    PROMPT_LITE_FUND_INDIV_TOOL, COMMON_QUALITY_RULES,
)


def test_no_rate_or_limit_numbers():
    assert not re.search(r"\d+(\.\d+)?\s*%", FUND_DOMAIN_KNOWLEDGE_BIZ), "금리 % 수치 하드코딩(구식화·환각 원인)"
    assert not re.search(r"\d+\s*억", FUND_DOMAIN_KNOWLEDGE_BIZ), "한도 억원 수치 하드코딩"
    assert not re.search(r"\d+\s*만원", FUND_DOMAIN_KNOWLEDGE_BIZ), "한도 만원 수치 하드코딩"


def test_required_fund_knowledge_present():
    for kw in ["신성장기반자금", "창업기반지원자금", "긴급경영안정자금", "신시장진출지원자금",
               "재도약지원자금", "시설자금 중심", "전체 소상공인", "재해중소기업 확인증", "성실경영평가"]:
        assert kw in FUND_DOMAIN_KNOWLEDGE_BIZ, "필수 지식 누락: %s" % kw


def test_hallucination_guards_present():
    assert "1811-3655" in PROMPT_LITE_FUND_BIZ_TOOL, "금리·한도 확인경로(1811-3655) 가드 누락"
    assert "단순 영업부진" in PROMPT_LITE_FUND_BIZ_TOOL, "긴급경영안정 오안내 가드 누락"
    assert PROMPT_LITE_FUND_BIZ_TOOL.count("단정") >= 3, "단정 금지 가드 부족"


def test_young_fund_age_bug_fixed():
    assert "만 34세 이하" not in COMMON_QUALITY_RULES, "청년나이 버그(만 34세 단정) 잔존 — 실제 청년전용창업 만 39세"


def test_compat_contract_unchanged():
    assert "---choices---" in PROMPT_LITE_FUND_BIZ_TOOL and "---choices---" in PROMPT_LITE_FUND_INDIV_TOOL
    for tool in ["search_fund_announcements", "get_announcement_detail", "check_eligibility", "search_knowledge_base"]:
        assert tool in PROMPT_LITE_FUND_BIZ_TOOL, "도구명 누락: %s" % tool


if __name__ == "__main__":
    import traceback
    _fns = [v for k, v in sorted(globals().items())
            if k.startswith("test_") and callable(v)]
    _passed = _failed = 0
    for _fn in _fns:
        try:
            _fn()
            print("PASS  " + _fn.__name__)
            _passed += 1
        except Exception as _e:
            print("FAIL  " + _fn.__name__ + ": " + repr(_e))
            _failed += 1
    print("\n%d passed, %d failed" % (_passed, _failed))
    sys.exit(1 if _failed else 0)
