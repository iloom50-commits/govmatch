# -*- coding: utf-8 -*-
"""표창/포상 공고 비지원사업 필터 — 단위 테스트.

'유공 포상 후보자 모집' 류는 지원금이 아닌 정부 표창 후보 모집인데 '모집'이 있어
기존 필터를 통과함. '모집'보다 먼저 표창 키워드를 hard-제외해야 함.

실행: cd backend && python test_award_filter_unit.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _f(title):
    from app.services.scrapers.tier1.base import _is_non_support_title
    return _is_non_support_title(title)


def test_award_recruitment_excluded_despite_모집():
    # 표창 후보 모집 — '모집'이 있어도 제외(True)
    assert _f("2026년 중소기업 융합 촉진 유공 포상 후보자 모집 연장 공고") is True
    assert _f("2026년 중소기업 지역혁신 유공 포상 후보자 모집 공고") is True


def test_award_plan_excluded():
    assert _f("소프트웨어 산업발전 유공자 포상계획 공고") is True


def test_real_support_still_allowed():
    # 진짜 지원사업은 계속 허용(False)
    assert _f("2026년 창업기업 판로지원사업 참여기업 모집 공고") is False
    assert _f("청년 창업 지원사업 참가기업 모집") is False
    assert _f("소상공인 정책자금 융자 지원 공고") is False


if __name__ == "__main__":
    import traceback
    _fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    _p = _ff = 0
    for _fn in _fns:
        try:
            _fn(); print("PASS  " + _fn.__name__); _p += 1
        except Exception as _e:
            print("FAIL  " + _fn.__name__ + ": " + repr(_e)); traceback.print_exc(); _ff += 1
    print("\n%d passed, %d failed" % (_p, _ff)); sys.exit(1 if _ff else 0)
