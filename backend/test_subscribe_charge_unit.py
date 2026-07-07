# -*- coding: utf-8 -*-
"""구독 청구액 — LITE→PRO 업그레이드 시 LITE 월정가만큼 단순 차감 (2026-07-08) 단위 테스트.

정책: PRO 청구 = PRO 전액 − LITE 월정가(사용자 타입별). 일수 무관(단순).
free→PRO는 차감 없음(낸 게 없음).

실행: cd backend && python test_subscribe_charge_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from app.main import _subscribe_charge


# (current_plan, target, user_type) → (기대 청구액, 기대 크레딧)
CASES = [
    ("lite", "pro", "business", 44100, 4900),   # 49000 - 4900
    ("lite", "pro", "individual", 46100, 2900),  # 49000 - 2900
    ("basic", "pro", "business", 44100, 4900),   # basic도 lite 취급
    ("free", "pro", "business", 49000, 0),       # free→pro: 차감 없음
    ("lite", "lite", "business", 4900, 0),        # 업그레이드 아님(동일플랜) → 차감 없음
]


def test_subscribe_charge():
    for cur_plan, target, utype, exp_charge, exp_credit in CASES:
        charge, credit = _subscribe_charge(cur_plan, target, utype)
        assert (charge, credit) == (exp_charge, exp_credit), \
            "(%s→%s, %s) → (%d,%d) 기대이나 (%d,%d)" % (
                cur_plan, target, utype, exp_charge, exp_credit, charge, credit)


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
