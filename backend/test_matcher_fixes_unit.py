# -*- coding: utf-8 -*-
"""PRO 매칭 결함 수정(2026-07-04 검증테스트 발견) — 단위 테스트.

D1: 임베딩 경로가 하드필터(지역 등)를 건너뜀 → 부산 고객에 경남 공고 "신청 가능"
D2: 신형 eligibility_logic 필드(target_industries/required_certifications/region_restriction) 미적용
D3: 구식 빈 elig({"min_revenue":"","max_revenue":""})가 무제약으로 해석

실행: cd backend && python test_matcher_fixes_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# 부산 제조업 고객 (검증테스트와 동일 프로필)
P = {
    "industry_name": "제조업(금속가공)",
    "industry_code": "25999",
    "address_city": "부산광역시",
    "certifications": "",
    "revenue_bracket": "1억~5억",
    "employee_count_bracket": "5인 미만",
}


# ─────────────────────────────────────────────────────────────
# D3: is_blank_eligibility — 구식/빈 elig 판별
# ─────────────────────────────────────────────────────────────
def test_blank_none_empty():
    from app.core.matcher import is_blank_eligibility
    for v in (None, "", "{}", "null", {}):
        assert is_blank_eligibility(v) is True, v


def test_blank_legacy_all_empty_values():
    from app.core.matcher import is_blank_eligibility
    assert is_blank_eligibility('{"min_revenue": "", "max_revenue": ""}') is True
    assert is_blank_eligibility({"min_revenue": "", "max_revenue": ""}) is True
    assert is_blank_eligibility({"min_revenue": None, "max_revenue": ""}) is True


def test_blank_invalid_json_treated_blank():
    from app.core.matcher import is_blank_eligibility
    assert is_blank_eligibility("not-a-json{") is True


def test_not_blank_when_any_value():
    from app.core.matcher import is_blank_eligibility
    assert is_blank_eligibility('{"max_revenue": "50억"}') is False
    assert is_blank_eligibility({"target_industries": ["어업"]}) is False
    assert is_blank_eligibility({"min_founding_years": 0}) is False


# ─────────────────────────────────────────────────────────────
# D2: judge_eligibility_fields — 신형 elig 필드 판정
# ─────────────────────────────────────────────────────────────
def test_judge_industry_mismatch_ineligible():
    from app.core.matcher import judge_eligibility_fields
    status, reason = judge_eligibility_fields({"target_industries": ["어업"]}, P)
    assert status == "ineligible", (status, reason)
    assert "어업" in (reason or "")


def test_judge_industry_match_eligible():
    from app.core.matcher import judge_eligibility_fields
    status, _ = judge_eligibility_fields({"target_industries": ["제조업"]}, P)
    assert status == "eligible"
    status, _ = judge_eligibility_fields({"target_industries": ["어업", "제조"]}, P)
    assert status == "eligible"


def test_judge_industry_generic_pass():
    from app.core.matcher import judge_eligibility_fields
    for generic in (["전업종"], ["제한없음"], [], None):
        status, _ = judge_eligibility_fields({"target_industries": generic}, P)
        assert status == "eligible", generic


def test_judge_industry_unknown_user_conditional():
    """고객 업종을 모르면 배제하지 않고 확인 필요."""
    from app.core.matcher import judge_eligibility_fields
    p2 = dict(P, industry_name="", industry_code="")
    status, _ = judge_eligibility_fields({"target_industries": ["어업"]}, p2)
    assert status == "conditional"


def test_judge_region_other_province_ineligible():
    from app.core.matcher import judge_eligibility_fields
    status, reason = judge_eligibility_fields({"region_restriction": "경남"}, P)
    assert status == "ineligible", (status, reason)


def test_judge_region_same_city_eligible():
    from app.core.matcher import judge_eligibility_fields
    status, _ = judge_eligibility_fields({"region_restriction": "부산"}, P)
    assert status == "eligible"
    status, _ = judge_eligibility_fields({"region_restriction": "전국"}, P)
    assert status == "eligible"


def test_judge_region_district_conditional():
    """같은 시도지만 구·군 단위 제한 — 프로필은 시 단위라 확인 필요."""
    from app.core.matcher import judge_eligibility_fields
    status, reason = judge_eligibility_fields({"region_restriction": "부산 영도구"}, P)
    assert status == "conditional", (status, reason)


def test_judge_required_cert_missing_conditional():
    from app.core.matcher import judge_eligibility_fields
    status, reason = judge_eligibility_fields({"required_certifications": ["어업경영체 등록"]}, P)
    assert status == "conditional", (status, reason)


def test_judge_required_cert_held_eligible():
    from app.core.matcher import judge_eligibility_fields
    p2 = dict(P, certifications="벤처기업 인증,이노비즈")
    status, _ = judge_eligibility_fields({"required_certifications": ["벤처기업"]}, p2)
    assert status == "eligible"


def test_judge_worst_status_wins():
    from app.core.matcher import judge_eligibility_fields
    status, _ = judge_eligibility_fields({
        "target_industries": ["어업"],
        "required_certifications": ["어업경영체 등록"],
    }, P)
    assert status == "ineligible"


def test_judge_blank_elig_eligible():
    """빈 elig는 판정 재료 없음 — 상위(확인 필요 처리)에 맡기고 eligible 반환."""
    from app.core.matcher import judge_eligibility_fields
    status, _ = judge_eligibility_fields({}, P)
    assert status == "eligible"
    status, _ = judge_eligibility_fields(None, P)
    assert status == "eligible"


def test_judge_real_case_51167():
    """검증테스트 실사례: 영도구 어업활동지원 → 제조업 고객에게 불가."""
    from app.core.matcher import judge_eligibility_fields
    elig = {
        "min_founding_years": None, "max_founding_years": None,
        "region_restriction": "부산 영도구",
        "target_industries": ["어업"],
        "required_certifications": ["어업경영체 등록"],
        "business_type": ["소상공인", "어업인"],
    }
    status, reason = judge_eligibility_fields(elig, P)
    assert status == "ineligible", (status, reason)


# ─────────────────────────────────────────────────────────────
# D1a: 지역 하드필터 회귀 (기존 함수 — 검증테스트 실사례)
# ─────────────────────────────────────────────────────────────
def _cands():
    return [
        {"announcement_id": 1, "title": "[경남] 2026년 소상공인 정책자금 운용계획 공고", "region": "경남", "summary_text": ""},
        {"announcement_id": 2, "title": "부산 소상공인 특별지원", "region": "부산", "summary_text": ""},
        {"announcement_id": 3, "title": "중소기업 전국 지원사업", "region": "전국", "summary_text": ""},
        {"announcement_id": 4, "title": "양산시 소상공인 육성자금 특별보증", "region": "경남", "summary_text": ""},
    ]


def test_hard_filter_excludes_other_region():
    from app.core.matcher import _hard_filter_business
    passed, excluded = _hard_filter_business(_cands(), P, None)
    ids = {c["announcement_id"] for c in passed}
    assert ids == {2, 3}, ids


# ─────────────────────────────────────────────────────────────
# G: 개인 공고 성별 전용 판정 (2026-07-05 — '경력단절여성'→남성 발송 실증 건)
# ─────────────────────────────────────────────────────────────
def test_gender_male_excluded_from_female_only():
    from app.core.matcher import _check_gender_exclusion
    excl, reason = _check_gender_exclusion("남성", "경력단절여성 등 취업지원")
    assert excl is True and "여성" in (reason or "")
    assert _check_gender_exclusion("남성", "임산부 교통비 지원")[0] is True
    assert _check_gender_exclusion("남성", "여성농업인 농작업 편의장비 지원사업")[0] is True


def test_gender_female_passes_female_only():
    from app.core.matcher import _check_gender_exclusion
    assert _check_gender_exclusion("여성", "경력단절여성 등 취업지원")[0] is False


def test_gender_unknown_never_excluded():
    from app.core.matcher import _check_gender_exclusion
    for g in ("", None, "해당없음"):
        assert _check_gender_exclusion(g, "경력단절여성 취업지원")[0] is False, g


def test_gender_department_name_guard():
    """'여성가족부' 등 기관명은 전용 신호가 아님 — 과차단 방지."""
    from app.core.matcher import _check_gender_exclusion
    assert _check_gender_exclusion("남성", "[여성가족부] 청소년 프로그램 지원")[0] is False
    assert _check_gender_exclusion("남성", "남녀 임금격차 개선 컨설팅")[0] is False


def test_gender_english_value_normalized():
    from app.core.matcher import _check_gender_exclusion
    assert _check_gender_exclusion("male", "여대생 커리어 캠프")[0] is True


def test_gender_female_excluded_from_male_only():
    from app.core.matcher import _check_gender_exclusion
    assert _check_gender_exclusion("여성", "남성 육아휴직 장려금")[0] is True


def test_hard_filter_individual_applies_gender():
    from app.core.matcher import _hard_filter_individual
    p = dict(P, user_type="individual", gender="남성", industry_code="", industry_name="")
    cands = [
        {"announcement_id": 1, "title": "경력단절여성 등 취업지원", "region": "부산", "summary_text": ""},
        {"announcement_id": 2, "title": "청년 월세 지원", "region": "부산", "summary_text": ""},
    ]
    passed, excluded = _hard_filter_individual(cands, p, None)
    assert {c["announcement_id"] for c in passed} == {2}, passed


# ─────────────────────────────────────────────────────────────
# D1: 임베딩 경로도 하드필터 적용
# ─────────────────────────────────────────────────────────────
def test_hybrid_embedding_applies_hard_filter():
    from app.core import matcher as m
    os.environ["USE_EMBEDDING_MATCHING"] = "true"
    orig_emb = m.get_matches_by_embedding
    orig_conn = m.get_db_connection
    try:
        m.get_matches_by_embedding = lambda profile, top_k=50, target_type_filter=None: [
            {"announcement_id": 1, "title": "[경남] 소상공인 정책자금", "region": "경남", "summary_text": "", "similarity": 0.9},
            {"announcement_id": 2, "title": "부산 소상공인 지원", "region": "부산", "summary_text": "", "similarity": 0.8},
        ]
        def _no_db(*a, **k):
            raise RuntimeError("no db in unit test")
        m.get_db_connection = _no_db
        res = m.get_matches_hybrid(P, is_individual=False, skip_bucket=True)
        ids = {r["announcement_id"] for r in res}
        assert ids == {2}, res
    finally:
        m.get_matches_by_embedding = orig_emb
        m.get_db_connection = orig_conn
        os.environ["USE_EMBEDDING_MATCHING"] = "false"


# ─────────────────────────────────────────────────────────────
# 스크립트 러너
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
