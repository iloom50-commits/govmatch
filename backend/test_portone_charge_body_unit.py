# -*- coding: utf-8 -*-
"""PortOne V2 빌링키 청구 요청 본문 — currency 위치 버그 회귀 테스트.

PortOne V2는 currency를 요청 최상위에 요구(amount 안이 아님). amount 안에 넣으면
400 INVALID_REQUEST "missing required field currency" → 모든 V2 청구 실패.
(실측 2026-07-07: 이 버그로 결제가 한 번도 성공 못 함)

실행: cd backend && python test_portone_charge_body_unit.py
"""
import os
import sys
import inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import app.main as m


def test_currency_not_inside_amount():
    for name, fn in [("_charge_billing_key", m._charge_billing_key),
                     ("_auto_renew_subscriptions", m._auto_renew_subscriptions)]:
        src = inspect.getsource(fn)
        assert '"total": price, "currency"' not in src, \
            "%s: currency가 amount 안에 있음 → PortOne 400" % name
        assert '"currency": "KRW"' in src, "%s: 최상위 currency 없음" % name


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
