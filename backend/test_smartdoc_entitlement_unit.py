# -*- coding: utf-8 -*-
"""entitlement 정책(B안): AI 신청서 작성 = LITE+ 전용. 실제 문서 과금은 SmartDoc(건별).

실행: cd backend && python test_smartdoc_entitlement_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_entitlement_lite_has_access():
    from app.main import _entitlement_response
    out = _entitlement_response("lite")
    assert out["has_access"] is True, out
    assert out["billed_by"] == "smartdoc", out


def test_entitlement_lite_individual_has_access():
    from app.main import _entitlement_response
    assert _entitlement_response("lite_individual")["has_access"] is True


def test_entitlement_pro_has_access():
    from app.main import _entitlement_response
    assert _entitlement_response("pro")["has_access"] is True


def test_entitlement_free_blocked_with_purchase_url():
    from app.main import _entitlement_response
    out = _entitlement_response("free")
    assert out["has_access"] is False, out
    assert out["purchase_url"], out  # 업그레이드 유도


def test_entitlement_none_blocked():
    from app.main import _entitlement_response
    assert _entitlement_response(None)["has_access"] is False


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
