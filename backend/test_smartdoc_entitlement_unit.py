# -*- coding: utf-8 -*-
"""entitlement 통과 정책: 결제는 SmartDoc 전담 → 유효 사용자면 has_access=true.

실행: cd backend && python test_smartdoc_entitlement_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_entitlement_passthrough_for_valid_user():
    from app.main import _entitlement_response
    out = _entitlement_response(row={"smartdoc_plan": None, "smartdoc_expires_at": None})
    assert out["has_access"] is True, out
    assert out["billed_by"] == "smartdoc", out
    assert out["purchase_url"] is None, out


def test_entitlement_passthrough_none_row():
    from app.main import _entitlement_response
    out = _entitlement_response(row=None)
    assert out["has_access"] is True, out


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
