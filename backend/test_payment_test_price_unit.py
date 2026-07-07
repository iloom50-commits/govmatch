# -*- coding: utf-8 -*-
"""실결제 테스트용 가격 오버라이드(bn-게이트) — 단위 테스트.

카카오페이(V2) 실청구 테스트를 소액(예 1000원)으로 하기 위한 임시 오버라이드.
- env SUBSCRIPTION_TEST_PRICE 없으면 정상가(무해, 기본 OFF).
- SUBSCRIPTION_TEST_BN 설정 시 그 사업자번호에만 적용(타 유저 자동갱신 보호).
- 구독·자동갱신·환불이 모두 _plan_price를 쓰므로 청구·환불 동일가 일관.

실행: cd backend && python test_payment_test_price_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import app.main as m


def _clear():
    os.environ.pop("SUBSCRIPTION_TEST_PRICE", None)
    os.environ.pop("SUBSCRIPTION_TEST_BN", None)


def test_no_override_when_env_unset():
    _clear()
    assert m._plan_price("pro") == 49000, "env 없을 때 PRO 정상가 아님"
    assert m._plan_price("lite") == 4900, "env 없을 때 LITE(사업자) 정상가 아님"
    assert m._plan_price("lite", "individual") == 2900, "env 없을 때 LITE(개인) 정상가 아님"


def test_override_applies_only_to_matching_bn():
    os.environ["SUBSCRIPTION_TEST_PRICE"] = "1000"
    os.environ["SUBSCRIPTION_TEST_BN"] = "111-22-33333"
    try:
        assert m._plan_price("pro", bn="111-22-33333") == 1000, "매칭 bn에 테스트가 미적용"
        assert m._plan_price("pro", bn="999-99-99999") == 49000, "미매칭 bn인데 테스트가 적용(타 유저 오염)"
        assert m._plan_price("pro") == 49000, "bn 미전달 경로가 테스트가로 오염(보호 실패)"
    finally:
        _clear()


def test_override_global_when_no_bn_filter():
    os.environ["SUBSCRIPTION_TEST_PRICE"] = "1000"
    os.environ.pop("SUBSCRIPTION_TEST_BN", None)
    try:
        assert m._plan_price("pro", bn="anybn") == 1000, "BN 필터 없을 때 전역 적용 실패"
    finally:
        _clear()


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
