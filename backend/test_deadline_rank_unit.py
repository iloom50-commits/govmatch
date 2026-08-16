# -*- coding: utf-8 -*-
"""작업4: 마감일 정렬 3단계 — 마감일 있음 > 미상 > 지남.

결함: matcher.py의 _is_deadline_valid(None)=True. 마감일 NULL을 전부 '유효'(최상위)로 취급.
그런데 NULL은 진짜 상시(deadline_type='ongoing', 3880건)일 수도, 파싱실패 미상('unknown', 4067건)일
수도 있다. 미상까지 미래·상시와 동급 최상위로 올라가 신뢰도 낮은 공고가 상단을 차지.

수정: deadline_type으로 3단계 — 0=마감일 유효(미래)/진짜 상시, 1=미상, 2=마감 지남.
진짜 상시는 후순위로 밀지 않고, 미상만 중간으로 내린다.

실행: cd backend && python -m pytest test_deadline_rank_unit.py -q --no-header
"""
import os
import sys
import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_deadline_sort_rank_three_tiers():
    from app.core.matcher import _deadline_sort_rank
    today = datetime.date.today()
    future = today + datetime.timedelta(days=10)
    past = today - datetime.timedelta(days=10)
    assert _deadline_sort_rank(future, "fixed") == 0, "미래 마감일 = 최상(0)"
    assert _deadline_sort_rank(None, "ongoing") == 0, "진짜 상시(ongoing) = 최상(0), 밀지 않음"
    assert _deadline_sort_rank(None, "unknown") == 1, "미상(unknown) = 중간(1)"
    assert _deadline_sort_rank(past, "fixed") == 2, "마감 지남 = 최하(2)"


def test_unknown_between_ongoing_and_past():
    """핵심 불변식: 미상은 상시/미래보다 뒤, 마감 지남보다 앞."""
    from app.core.matcher import _deadline_sort_rank
    today = datetime.date.today()
    r_ongoing = _deadline_sort_rank(None, "ongoing")
    r_unknown = _deadline_sort_rank(None, "unknown")
    r_past = _deadline_sort_rank(today - datetime.timedelta(days=1), "fixed")
    assert r_ongoing < r_unknown < r_past, (
        f"정렬 위계 위반: 상시({r_ongoing}) < 미상({r_unknown}) < 지남({r_past})이어야 함"
    )


def test_ongoing_not_penalized_vs_unknown():
    """진짜 상시가 미상보다 뒤로 밀리지 않는다(마감일 NULL 두 종류를 구분)."""
    from app.core.matcher import _deadline_sort_rank
    assert _deadline_sort_rank(None, "ongoing") < _deadline_sort_rank(None, "unknown")
