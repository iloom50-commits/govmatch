# -*- coding: utf-8 -*-
"""즉시 첫 청구 정책(2026-07-04 확정) — 단위 테스트.

구조: 체험 3회(사용량) = 무료체험 → 결제(빌링키 등록) 시 즉시 첫 청구 → 성공 시 30일 이용권.
기존 버그: subscribe 응답의 trial_days NameError / '결제 후 30일 무료' 정책 / 문구 7일 불일치.

실행: cd backend && python test_billing_policy_unit.py
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# ─────────────────────────────────────────────────────────────
# _plan_price — 서버 기준 단일 가격 소스
# ─────────────────────────────────────────────────────────────
def test_price_pro():
    from app.main import _plan_price
    assert _plan_price("pro") == 49000
    assert _plan_price("pro", "individual") == 49000  # PRO는 유형 무관


def test_price_lite_business():
    from app.main import _plan_price
    assert _plan_price("lite") == 4900
    assert _plan_price("lite", "business") == 4900
    assert _plan_price("lite", "both") == 4900


def test_price_lite_individual():
    from app.main import _plan_price
    assert _plan_price("lite", "individual") == 2900


# ─────────────────────────────────────────────────────────────
# _charge_billing_key — V1/V2 겸용 즉시 청구
# ─────────────────────────────────────────────────────────────
def _fake_httpx(status_code):
    mod = types.ModuleType("httpx")
    calls = {}

    def post(url, headers=None, json=None, timeout=None):
        calls["url"] = url
        calls["json"] = json
        r = types.SimpleNamespace(status_code=status_code)
        return r

    mod.post = post
    mod._calls = calls
    return mod


def test_charge_v2_success():
    import app.main as m
    orig_httpx = sys.modules.get("httpx")
    orig_secret = m.PORTONE_API_SECRET
    try:
        fake = _fake_httpx(200)
        sys.modules["httpx"] = fake
        m.PORTONE_API_SECRET = "secret"
        ok = m._charge_billing_key("billing-key-abc123", "first-999-20260704", 49000, "지원금길잡이 PRO 월 구독")
        assert ok is True
        assert fake._calls["json"]["amount"]["total"] == 49000
        assert fake._calls["json"]["billingKey"] == "billing-key-abc123"
        assert "first-999-20260704" in fake._calls["url"]
    finally:
        if orig_httpx is not None:
            sys.modules["httpx"] = orig_httpx
        m.PORTONE_API_SECRET = orig_secret


def test_charge_v2_declined():
    import app.main as m
    orig_httpx = sys.modules.get("httpx")
    orig_secret = m.PORTONE_API_SECRET
    try:
        sys.modules["httpx"] = _fake_httpx(400)
        m.PORTONE_API_SECRET = "secret"
        assert m._charge_billing_key("billing-key-x", "p1", 49000, "o") is False
    finally:
        if orig_httpx is not None:
            sys.modules["httpx"] = orig_httpx
        m.PORTONE_API_SECRET = orig_secret


def test_charge_v2_no_secret_fails():
    import app.main as m
    orig_secret = m.PORTONE_API_SECRET
    try:
        m.PORTONE_API_SECRET = ""
        assert m._charge_billing_key("billing-key-x", "p1", 49000, "o") is False
    finally:
        m.PORTONE_API_SECRET = orig_secret


def test_charge_v1_routes_to_charge_v1():
    import app.main as m
    orig_v1 = m._charge_v1
    orig_k, orig_s = m.PORTONE_V1_API_KEY, m.PORTONE_V1_API_SECRET
    called = {}
    try:
        m.PORTONE_V1_API_KEY, m.PORTONE_V1_API_SECRET = "k", "s"

        def fake_v1(customer_uid, merchant_uid, amount, order_name):
            called.update(uid=customer_uid, amount=amount)
            return True

        m._charge_v1 = fake_v1
        ok = m._charge_billing_key("cust_abc123456", "p1", 4900, "o")
        assert ok is True and called["uid"] == "cust_abc123456" and called["amount"] == 4900
    finally:
        m._charge_v1 = orig_v1
        m.PORTONE_V1_API_KEY, m.PORTONE_V1_API_SECRET = orig_k, orig_s


def test_charge_v1_no_keys_fails():
    import app.main as m
    orig_k, orig_s = m.PORTONE_V1_API_KEY, m.PORTONE_V1_API_SECRET
    try:
        m.PORTONE_V1_API_KEY, m.PORTONE_V1_API_SECRET = "", ""
        assert m._charge_billing_key("cust_abc123456", "p1", 4900, "o") is False
    finally:
        m.PORTONE_V1_API_KEY, m.PORTONE_V1_API_SECRET = orig_k, orig_s


# ─────────────────────────────────────────────────────────────
# 회귀 — subscribe 소스에 trial_days 미정의 참조가 없어야 함
# ─────────────────────────────────────────────────────────────
def test_subscribe_no_undefined_trial_days():
    import inspect
    import app.main as m
    src = inspect.getsource(m.api_plan_subscribe)
    assert "trial_days" not in src, "subscribe에 trial_days 참조 잔존 (NameError 버그)"
    assert "무료 체험이 시작" not in src, "'무료 체험 시작' 메시지 잔존 (즉시 청구 정책 위반)"


def test_subscribe_charges_immediately():
    import inspect
    import app.main as m
    src = inspect.getsource(m.api_plan_subscribe)
    assert "_charge_billing_key" in src, "subscribe가 즉시 청구를 호출하지 않음"


# ─────────────────────────────────────────────────────────────
# 환불 정책 (_refund_amount_policy) — /refund 페이지 공개 정책 그대로
#   7일 이내·미사용: 전액 / 7일 이내·사용: 일할 공제 / 7일 경과: 불가
# ─────────────────────────────────────────────────────────────
def test_refund_full_within_7days_unused():
    import datetime
    from app.main import _refund_amount_policy
    started = datetime.datetime(2026, 7, 1)
    now = datetime.datetime(2026, 7, 4)
    ok, amount, _ = _refund_amount_policy(49000, started, now, used=False)
    assert ok is True and amount == 49000


def test_refund_prorated_within_7days_used():
    import datetime
    from app.main import _refund_amount_policy
    started = datetime.datetime(2026, 7, 1)
    now = datetime.datetime(2026, 7, 4)  # 이용 4일차 (당일 포함)
    ok, amount, _ = _refund_amount_policy(49000, started, now, used=True)
    assert ok is True
    assert amount == round(49000 * (30 - 4) / 30), amount  # 잔여 26일분


def test_refund_denied_after_7days():
    import datetime
    from app.main import _refund_amount_policy
    started = datetime.datetime(2026, 7, 1)
    now = datetime.datetime(2026, 7, 9)
    ok, amount, reason = _refund_amount_policy(49000, started, now, used=False)
    assert ok is False and amount == 0
    assert "7일" in reason


def test_refund_same_day_used_counts_one_day():
    import datetime
    from app.main import _refund_amount_policy
    started = datetime.datetime(2026, 7, 4, 9, 0)
    now = datetime.datetime(2026, 7, 4, 15, 0)
    ok, amount, _ = _refund_amount_policy(30000, started, now, used=True)
    assert ok is True
    assert amount == round(30000 * 29 / 30), amount  # 이용 1일 공제


# ─────────────────────────────────────────────────────────────
# _cancel_payment — V1/V2 겸용 결제 취소(부분 취소 포함)
# ─────────────────────────────────────────────────────────────
def test_cancel_v2_success():
    import app.main as m
    orig_httpx = sys.modules.get("httpx")
    orig_secret = m.PORTONE_API_SECRET
    try:
        fake = _fake_httpx(200)
        sys.modules["httpx"] = fake
        m.PORTONE_API_SECRET = "secret"
        ok = m._cancel_payment("first-999-20260704", 49000, "billing-key-abc")
        assert ok is True
        assert "first-999-20260704/cancel" in fake._calls["url"]
        assert fake._calls["json"]["amount"] == 49000
    finally:
        if orig_httpx is not None:
            sys.modules["httpx"] = orig_httpx
        m.PORTONE_API_SECRET = orig_secret


def test_cancel_v2_failure():
    import app.main as m
    orig_httpx = sys.modules.get("httpx")
    orig_secret = m.PORTONE_API_SECRET
    try:
        sys.modules["httpx"] = _fake_httpx(400)
        m.PORTONE_API_SECRET = "secret"
        assert m._cancel_payment("p1", 1000, "billing-key-abc") is False
    finally:
        if orig_httpx is not None:
            sys.modules["httpx"] = orig_httpx
        m.PORTONE_API_SECRET = orig_secret


def test_refund_endpoint_uses_real_cancel():
    """환불 API가 실제 취소 호출 없이 성공 메시지만 반환하던 결함 회귀 방지."""
    import inspect
    import app.main as m
    src = inspect.getsource(m.api_plan_refund)
    assert "_cancel_payment" in src, "환불 API가 실제 취소를 호출하지 않음"
    assert "환불이 처리되었습니다" not in src or "_cancel_payment" in src


def test_subscribe_no_pg_fails_loud():
    """PG 미설정 시 무료 구독으로 조용히 넘어가지 않고 명시적 오류."""
    import inspect
    import app.main as m
    src = inspect.getsource(m.api_plan_subscribe)
    assert "첫 청구 생략" not in src, "PG 미설정 시 무과금 구독 경로 잔존"


# ─────────────────────────────────────────────────────────────
# 스크립트 러너
# ─────────────────────────────────────────────────────────────
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
