# -*- coding: utf-8 -*-
"""관심분야 우선 정렬 SQL 조각 — 단위 테스트 (TDD, DB 불필요 순수 함수).

메인 공개목록에서 로그인+필터 시 마감순으로 떨어지던 것을, 관심 매칭 공고 우선으로
정렬하기 위한 ORDER BY 조각 생성기. 관심 없으면 빈 조각(비로그인·미설정 무영향).
실행: cd backend && python test_list_ordering_unit.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.list_ordering import interest_priority_order


def test_empty_interests_returns_empty():
    assert interest_priority_order([]) == ("", [])
    assert interest_priority_order(None) == ("", [])


def test_whitespace_only_ignored():
    assert interest_priority_order(["", "   "]) == ("", [])


def test_single_interest_builds_case_ending_with_comma():
    frag, params = interest_priority_order(["창업"])
    assert "CASE WHEN" in frag
    assert "THEN 0 ELSE 1 END" in frag
    assert frag.rstrip().endswith(","), frag  # ORDER BY 조각은 콤마로 끝남
    assert params == ["%창업%", "%창업%"]  # title, category 각각


def test_multiple_interests_order_and_params():
    frag, params = interest_priority_order(["창업", "수출"])
    assert frag.count("ILIKE") == 4  # 2개 관심 × (title, category)
    assert params == ["%창업%", "%창업%", "%수출%", "%수출%"]


def test_strips_and_filters_blanks_among_valid():
    frag, params = interest_priority_order(["  육아 ", "", "돌봄"])
    assert params == ["%육아%", "%육아%", "%돌봄%", "%돌봄%"]


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p = f = 0
    for fn in fns:
        try:
            fn(); print("PASS  " + fn.__name__); p += 1
        except Exception as e:
            print("FAIL  " + fn.__name__ + ": " + repr(e)); traceback.print_exc(); f += 1
    print("\n%d passed, %d failed" % (p, f))
    sys.exit(1 if f else 0)
