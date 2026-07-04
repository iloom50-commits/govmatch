# -*- coding: utf-8 -*-
"""LITE 자금상담 개선 — 순수 함수 단위 테스트 (DB/LLM 불필요).

실행(스크립트 스타일, pytest 불필요):
    cd backend && python test_lite_fund_unit.py
pytest가 있으면 pytest로도 실행 가능.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# ─────────────────────────────────────────────────────────────
# T-1: 검색 강제 완화 — 세션 첫 사용자 턴에만 강제
# ─────────────────────────────────────────────────────────────
def test_should_force_search_first_turn():
    from app.services.ai_consultant import _should_force_search
    assert _should_force_search([{"role": "user", "text": "운전자금"}]) is True


def test_should_not_force_search_on_followup():
    from app.services.ai_consultant import _should_force_search
    msgs = [
        {"role": "user", "text": "운전자금"},
        {"role": "assistant", "text": "안내드립니다"},
        {"role": "user", "text": "나 취준생인데"},
    ]
    assert _should_force_search(msgs) is False


def test_should_force_search_when_greeting_precedes():
    """인사말(assistant)이 앞에 있어도 첫 사용자 턴이면 강제."""
    from app.services.ai_consultant import _should_force_search
    msgs = [
        {"role": "assistant", "text": "안녕하세요, 정책자금 상담사입니다"},
        {"role": "user", "text": "운전자금 알아보고 싶어요"},
    ]
    assert _should_force_search(msgs) is True


def test_should_not_force_search_empty():
    from app.services.ai_consultant import _should_force_search
    assert _should_force_search([]) is False


# ─────────────────────────────────────────────────────────────
# T-2: check_eligibility 프로필 키 정규화 (구간→수치, 인증→리스트)
# ─────────────────────────────────────────────────────────────
def test_normalize_revenue_bracket_korean():
    from app.services.ai_consultant import _normalize_profile_for_eligibility
    out = _normalize_profile_for_eligibility({"revenue_bracket": "1억~5억"})
    assert out["revenue_won"] == 100_000_000


def test_normalize_revenue_bracket_code():
    from app.services.ai_consultant import _normalize_profile_for_eligibility
    out = _normalize_profile_for_eligibility({"revenue_bracket": "REV_10_50"})
    assert out["revenue_won"] == 1_000_000_000


def test_normalize_employee_bracket_korean():
    from app.services.ai_consultant import _normalize_profile_for_eligibility
    out = _normalize_profile_for_eligibility({"employee_count_bracket": "10인~30인"})
    assert out["employees"] == 10


def test_normalize_certifications_split():
    from app.services.ai_consultant import _normalize_profile_for_eligibility
    out = _normalize_profile_for_eligibility({"certifications": "벤처기업,이노비즈"})
    assert "벤처기업" in out["certs"] and "이노비즈" in out["certs"]


def test_normalize_certifications_none_excluded():
    from app.services.ai_consultant import _normalize_profile_for_eligibility
    out = _normalize_profile_for_eligibility({"certifications": "없음"})
    assert "certs" not in out


def test_normalize_business_years_from_est_date():
    from app.services.ai_consultant import _normalize_profile_for_eligibility
    out = _normalize_profile_for_eligibility({"establishment_date": "2020-01-01"})
    assert out["business_years"] >= 5


def test_normalize_unknown_bracket_skipped():
    from app.services.ai_consultant import _normalize_profile_for_eligibility
    out = _normalize_profile_for_eligibility({"revenue_bracket": "몰라요값"})
    assert "revenue_won" not in out


def test_normalize_preserves_existing_revenue_won():
    from app.services.ai_consultant import _normalize_profile_for_eligibility
    out = _normalize_profile_for_eligibility({"revenue_won": 999, "revenue_bracket": "1억~5억"})
    assert out["revenue_won"] == 999


# ─────────────────────────────────────────────────────────────
# T-4: 환각 공고ID 제거 (도구 미반환 ID 인용 차단)
# ─────────────────────────────────────────────────────────────
def test_strip_unverified_removes_hallucinated():
    from app.services.ai_consultant import _strip_unverified_ann_ids
    out = _strip_unverified_ann_ids("A [공고ID: 12345] B [공고ID: 37580] C", {37580})
    assert "12345" not in out and "37580" in out


def test_strip_unverified_keeps_all_valid():
    from app.services.ai_consultant import _strip_unverified_ann_ids
    out = _strip_unverified_ann_ids("[공고ID: 100][ANN:200]", {100, 200})
    assert "100" in out and "200" in out


def test_strip_unverified_handles_ann_format():
    from app.services.ai_consultant import _strip_unverified_ann_ids
    out = _strip_unverified_ann_ids("X [ANN:999] Y", {1, 2})
    assert "999" not in out


def test_strip_unverified_empty_reply():
    from app.services.ai_consultant import _strip_unverified_ann_ids
    assert _strip_unverified_ann_ids("", {1}) == ""


def test_strip_unverified_valid_ids_as_strings():
    from app.services.ai_consultant import _strip_unverified_ann_ids
    out = _strip_unverified_ann_ids("[공고ID: 55]", {"55"})
    assert "55" in out


# ─────────────────────────────────────────────────────────────
# T-5a: 상담 검색 제외절 강화 (재도전/재창업 전용 + summary 검사)
# ─────────────────────────────────────────────────────────────
def test_exclusion_clause_blocks_restart_for_normal_user():
    from app.services.ai_consultant import _profile_exclusion_clause
    where, _ = _profile_exclusion_clause({"establishment_date": "2020-01-01"})
    assert "재도전" in where and "재창업" in where


def test_exclusion_clause_checks_summary_text():
    from app.services.ai_consultant import _profile_exclusion_clause
    where, _ = _profile_exclusion_clause({"establishment_date": "2020-01-01"})
    assert "summary_text" in where


def test_exclusion_clause_allows_restart_when_cert():
    from app.services.ai_consultant import _profile_exclusion_clause
    where, _ = _profile_exclusion_clause({"certifications": "재창업", "establishment_date": "2020-01-01"})
    assert "채무조정" not in where


# ─────────────────────────────────────────────────────────────
# T-6: 이미 추천한 공고 ID 추출 (검색 중복 차단용)
# ─────────────────────────────────────────────────────────────
def test_extract_mentioned_ids_both_formats():
    from app.services.ai_consultant import _extract_mentioned_ids
    msgs = [{"role": "assistant", "text": "### 1. A [공고ID: 100]\n### 2. B [ANN:200]"}]
    assert _extract_mentioned_ids(msgs) == {100, 200}


def test_extract_mentioned_ids_ignores_user_messages():
    from app.services.ai_consultant import _extract_mentioned_ids
    msgs = [
        {"role": "user", "text": "[공고ID: 999] 이거 뭐예요?"},
        {"role": "assistant", "text": "안내드립니다 [공고ID: 100]"},
    ]
    assert _extract_mentioned_ids(msgs) == {100}


def test_extract_mentioned_ids_empty():
    from app.services.ai_consultant import _extract_mentioned_ids
    assert _extract_mentioned_ids([]) == set()


# ─────────────────────────────────────────────────────────────
# T-9: Gemini 폴백 히스토리 구성 (user/model 턴 보존)
# ─────────────────────────────────────────────────────────────
def test_build_gemini_history_roles():
    from app.services.ai_consultant import _build_gemini_history
    h = _build_gemini_history([
        {"role": "user", "text": "a"},
        {"role": "assistant", "text": "b"},
        {"role": "user", "text": "c"},
    ])
    # 마지막 메시지는 send_message로 보내므로 history에서 제외
    assert h == [
        {"role": "user", "parts": ["a"]},
        {"role": "model", "parts": ["b"]},
    ]


def test_build_gemini_history_empty_and_single():
    from app.services.ai_consultant import _build_gemini_history
    assert _build_gemini_history([]) == []
    assert _build_gemini_history([{"role": "user", "text": "only"}]) == []


# ─────────────────────────────────────────────────────────────
# T-11a: 지역 검색 토큰 정규화 (DB region 축약형 대응 — V-2 검증)
# ─────────────────────────────────────────────────────────────
def test_region_token_metropolitan():
    from app.services.ai_consultant import _region_search_token
    assert _region_search_token("부산광역시") == "부산"
    assert _region_search_token("서울특별시") == "서울"


def test_region_token_province():
    from app.services.ai_consultant import _region_search_token
    assert _region_search_token("전라남도") == "전남"
    assert _region_search_token("전북특별자치도") == "전북"
    assert _region_search_token("경기도") == "경기"
    assert _region_search_token("강원특별자치도") == "강원"


def test_region_token_already_short():
    from app.services.ai_consultant import _region_search_token
    assert _region_search_token("부산") == "부산"


def test_region_token_full_address():
    from app.services.ai_consultant import _region_search_token
    assert _region_search_token("부산광역시 해운대구 우동") == "부산"


def test_region_token_empty():
    from app.services.ai_consultant import _region_search_token
    assert _region_search_token("") == ""
    assert _region_search_token(None) == ""


# ─────────────────────────────────────────────────────────────
# T-7: 인용 파서 겸용 패턴 ([공고ID: N] + [ANN:N])
# ─────────────────────────────────────────────────────────────
def test_ann_split_pattern_accepts_both_formats():
    import re
    from app.services.ai_consultant import _ANN_SPLIT_PATTERN
    blocks = re.split(_ANN_SPLIT_PATTERN, "intro [공고ID: 31524] 이유A [ANN:99] 이유B")
    assert blocks[1] == "31524" and blocks[3] == "99"


# ─────────────────────────────────────────────────────────────
# 섹션2: 프롬프트 정합성 (재설계 회귀 방지)
# ─────────────────────────────────────────────────────────────
def test_prompt_no_legacy_ann_tag():
    from app.services.prompts.lite_fund_tool import (
        PROMPT_LITE_FUND_BIZ_TOOL, PROMPT_LITE_FUND_INDIV_TOOL)
    assert "[ANN:" not in PROMPT_LITE_FUND_BIZ_TOOL
    assert "[ANN:" not in PROMPT_LITE_FUND_INDIV_TOOL
    assert "[공고ID: N]" in PROMPT_LITE_FUND_BIZ_TOOL
    assert "[공고ID: N]" in PROMPT_LITE_FUND_INDIV_TOOL


def test_prompt_persona_is_fund_expert():
    from app.services.prompts.lite_fund_tool import (
        PROMPT_LITE_FUND_BIZ_TOOL, PROMPT_LITE_FUND_INDIV_TOOL)
    assert "융자" in PROMPT_LITE_FUND_BIZ_TOOL[:200]
    assert "대출" in PROMPT_LITE_FUND_INDIV_TOOL[:200]


def test_prompt_has_domain_knowledge():
    from app.services.prompts.lite_fund_tool import PROMPT_LITE_FUND_BIZ_TOOL
    for kw in ["신용보증기금", "기술보증기금", "소진공", "중진공", "대리대출"]:
        assert kw in PROMPT_LITE_FUND_BIZ_TOOL, kw


def test_prompt_backend_compat():
    """---choices--- 마커 + 도구명 4종 유지 (백엔드 파서/라우팅 호환)."""
    from app.services.prompts.lite_fund_tool import (
        PROMPT_LITE_FUND_BIZ_TOOL, PROMPT_LITE_FUND_INDIV_TOOL)
    for p in (PROMPT_LITE_FUND_BIZ_TOOL, PROMPT_LITE_FUND_INDIV_TOOL):
        assert "---choices---" in p
        for tool in ("search_fund_announcements", "get_announcement_detail",
                     "search_knowledge_base", "check_eligibility"):
            assert tool in p, tool


def test_prompt_no_hardcoded_rates():
    """금리·한도 수치 하드코딩 금지 원칙 (환각·구정보 방지)."""
    import re
    from app.services.prompts.lite_fund_tool import (
        PROMPT_LITE_FUND_BIZ_TOOL, PROMPT_LITE_FUND_INDIV_TOOL)
    for p in (PROMPT_LITE_FUND_BIZ_TOOL, PROMPT_LITE_FUND_INDIV_TOOL):
        assert not re.search(r"연\s*\d+(\.\d+)?%", p)  # "연 3.5%" 류
        assert not re.search(r"최대\s*\d+억", p)       # "최대 2억원" 류


# ─────────────────────────────────────────────────────────────
# 엔진 우선순위: Gemini 1차 / OpenAI 폴백 (2026-07-04 교체)
# — gpt-4o-mini가 프롬프트 규칙(인용·선질문·이관)을 준수하지 못해
#   품질 검증된 gemini-2.5-flash를 1차로 승격. 실제 API 호출 없이 가짜 객체로 검증.
# ─────────────────────────────────────────────────────────────
class _FakeGeminiChat:
    def __init__(self, reply="제미니 응답입니다"):
        self._reply = reply
        self.history = []

    def send_message(self, _msg):
        class _R:
            pass
        r = _R()
        r.text = self._reply
        return r


class _FakeGeminiModel:
    fail = False  # 클래스 플래그 — 실패 시뮬레이션

    def __init__(self, *a, **kw):
        if _FakeGeminiModel.fail:
            raise RuntimeError("simulated gemini failure")

    def start_chat(self, **kw):
        return _FakeGeminiChat()


class _FakeOpenAIClient:
    called = []  # 호출 기록 (클래스 공유)
    fail = False

    def __init__(self, api_key=None):
        class _Msg:
            tool_calls = None
            content = "오픈AI 응답입니다"

        class _Resp:
            pass

        class _Completions:
            def create(_self, **kw):
                _FakeOpenAIClient.called.append(kw.get("model"))
                if _FakeOpenAIClient.fail:
                    raise RuntimeError("simulated openai failure")
                r = _Resp()
                choice = type("C", (), {"message": _Msg()})()
                r.choices = [choice]
                return r

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def _run_lite_with_fakes(gemini_fail=False, openai_fail=False):
    """양 엔진을 가짜로 바꿔 chat_lite_fund_expert 1회 호출 (DB·실 API 없음)."""
    import openai as _oai_mod  # 미리 임포트 — sys.modules 조회 실패로 실 API가 호출되는 것 방지
    from app.services import ai_consultant as ac

    os.environ.setdefault("GEMINI_API_KEY", "test-key")
    os.environ.setdefault("OPENAI_API_KEY", "test-key")

    _FakeGeminiModel.fail = gemini_fail
    _FakeOpenAIClient.fail = openai_fail
    _FakeOpenAIClient.called = []

    _orig_configure = ac.genai.configure
    _orig_model = ac.genai.GenerativeModel
    _orig_openai_cls = _oai_mod.OpenAI
    try:
        ac.genai.configure = lambda **kw: None
        ac.genai.GenerativeModel = _FakeGeminiModel
        _oai_mod.OpenAI = _FakeOpenAIClient
        return ac.chat_lite_fund_expert(
            messages=[{"role": "user", "text": "운전자금 문의"}],
            db_conn=None,
            user_profile={"business_type": "제조업"},
            mode="business_fund",
        )
    finally:
        ac.genai.configure = _orig_configure
        ac.genai.GenerativeModel = _orig_model
        _oai_mod.OpenAI = _orig_openai_cls


def test_engine_order_gemini_first():
    """양 엔진 정상 시 Gemini가 답하고 OpenAI는 아예 호출되지 않아야 한다."""
    result = _run_lite_with_fakes()
    assert result["engine"] == "gemini", result
    assert _FakeOpenAIClient.called == [], _FakeOpenAIClient.called


def test_engine_fallback_to_openai():
    """Gemini 실패 시 OpenAI 폴백으로 응답해야 한다."""
    result = _run_lite_with_fakes(gemini_fail=True)
    assert result["engine"] == "openai", result
    assert "오픈AI" in result["reply"]


def test_engine_both_fail_returns_retry():
    """양 엔진 모두 실패 시 재시도 안내를 반환해야 한다."""
    result = _run_lite_with_fakes(gemini_fail=True, openai_fail=True)
    assert "일시적으로" in result["reply"], result
    assert result["choices"] == ["✏️ 다시 시도"]


# ─────────────────────────────────────────────────────────────
# 스크립트 러너 (pytest 없이 실행)
# ─────────────────────────────────────────────────────────────
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
            traceback.print_exc()
            _failed += 1
    print("\n%d passed, %d failed" % (_passed, _failed))
    sys.exit(1 if _failed else 0)
