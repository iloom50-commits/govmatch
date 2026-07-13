# -*- coding: utf-8 -*-
"""entitlement 정책(순수 건별): AI 신청서 작성 = 로그인 사용자면 누구나 통과(구독 게이트 없음).
실제 문서 과금은 SmartDoc(건별 9,900원).

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


def test_entitlement_pro_has_access():
    from app.main import _entitlement_response
    assert _entitlement_response("pro")["has_access"] is True


def test_entitlement_free_has_access_no_purchase_url():
    # 순수 건별: FREE도 통과, 업그레이드 유도(purchase_url) 없음
    from app.main import _entitlement_response
    out = _entitlement_response("free")
    assert out["has_access"] is True, out
    assert out["purchase_url"] is None, out


def test_entitlement_none_has_access():
    # plan 없음(비구독)도 통과 — 로그인 사용자면 누구나
    from app.main import _entitlement_response
    out = _entitlement_response(None)
    assert out["has_access"] is True, out
    assert out["purchase_url"] is None, out


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
