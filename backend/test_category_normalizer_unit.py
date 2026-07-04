# -*- coding: utf-8 -*-
"""구 카테고리 → 칩 분류 정규화 — 단위 테스트.

원칙: 확실한 구분류만 결정적 매핑, 애매한 값('소상공인','정보','기타',센터명 등)과
NULL은 건드리지 않음(None 반환 = 변경 없음).

실행: cd backend && python test_category_normalizer_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _n(cat, tt="business"):
    from app.services.category_normalizer import normalize_category
    return normalize_category(cat, tt)


# ── 기업 계열 ──
def test_biz_startup():
    assert _n("창업지원") == "창업·스케일업"
    assert _n("창업") == "창업·스케일업"
    assert _n("Entrepreneurship") == "창업·스케일업"


def test_biz_tech():
    for c in ("기술", "기술개발", "R&D", "Tech", "ICT", "디지털전환"):
        assert _n(c) == "기술·개발", c


def test_biz_export():
    for c in ("수출", "수출마케팅", "Global", "내수", "판로개척"):
        assert _n(c) == "수출·판로", c


def test_biz_fund():
    for c in ("정책자금", "금융", "대출정보", "자금", "융자"):
        assert _n(c) == "자금·지원", c


def test_biz_mgmt():
    for c in ("경영", "Business Support", "SME Support", "Small Business Support"):
        assert _n(c) == "경영·법률", c


def test_biz_hr():
    for c in ("인력", "직업훈련", "고용지원", "교육훈련", "Education"):
        assert _n(c) == "인력·교육", c


def test_null_target_treated_as_business():
    assert _n("창업지원", None) == "창업·스케일업"
    assert _n("수출", "") == "수출·판로"


def test_both_uses_business_map():
    assert _n("창업지원", "both") == "창업·스케일업"


# ── 개인 계열 ──
def test_ind_fund():
    assert _n("금융", "individual") == "자금·지원"
    assert _n("정책자금", "individual") == "자금·지원"


def test_ind_welfare():
    for c in ("장애", "노인", "저소득", "생활안정"):
        assert _n(c, "individual") == "복지", c


def test_ind_childcare():
    assert _n("육아", "individual") == "출산"
    assert _n("보육", "individual") == "출산"


def test_ind_education():
    assert _n("장학금", "individual") == "교육"
    assert _n("직업훈련", "individual") == "교육"


def test_ind_map_not_applied_to_business():
    """'장애'는 개인에선 복지지만 기업 공고(장애인기업 지원)에선 유지."""
    assert _n("장애", "business") is None


# ── 보수 원칙: 애매하면 유지 ──
def test_ambiguous_kept():
    for c, t in (("소상공인", "business"), ("정보", "business"), ("기타", "business"),
                 ("디지털기술융합센터", "business"), ("청년", "individual"),
                 ("고용", "individual"), ("Agriculture", "business")):
        assert _n(c, t) is None, (c, t)


def test_null_and_chip_values_unchanged():
    assert _n(None) is None
    assert _n("") is None
    assert _n("자금·지원") is None          # 이미 신분류
    assert _n("복지", "individual") is None


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
