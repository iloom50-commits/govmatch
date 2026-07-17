# -*- coding: utf-8 -*-
"""G2-6: 구독 결제 엔드포인트 410 + walletStatus(credits) 단위 테스트.

- /api/plan/upgrade, /api/plan/subscribe, /api/plan/cancel, /api/plan/refund
  는 본문이 제거되고 410 Gone을 반환해야 한다(라우트 자체는 남아 404가 아님).
- _get_wallet_status(current_user)가 {"credits": N}을 반환해야 한다
  (auth/me 등 planStatus 응답에 credits로 노출되는 값의 근거).

DB 접근 없이 판단 가능한 부분(410)은 즉시 호출로, credits는
get_db_connection을 FakeConn/FakeCursor로 모킹해 검증한다
(GovMatch 기존 관행, test_credit_gate_unit.py 참고).

실행: cd backend && python test_subscription_removed_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

from fastapi import HTTPException

import app.main as main


# ─────────────────────────────────────────────────────────────
# 구독 엔드포인트 410
# ─────────────────────────────────────────────────────────────
def test_plan_upgrade_returns_410():
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    req = main.UpgradePlanRequest(target_plan="pro")
    try:
        main.api_plan_upgrade(req, current_user)
        assert False, "410이 발생해야 함"
    except HTTPException as e:
        assert e.status_code == 410


def test_plan_subscribe_returns_410():
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    req = main.SubscribeRequest(billing_key="billing_key_1234567890")
    try:
        main.api_plan_subscribe(req, current_user)
        assert False, "410이 발생해야 함"
    except HTTPException as e:
        assert e.status_code == 410


def test_plan_cancel_returns_410():
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    try:
        main.api_plan_cancel(current_user)
        assert False, "410이 발생해야 함"
    except HTTPException as e:
        assert e.status_code == 410


def test_plan_refund_returns_410():
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    try:
        main.api_plan_refund(current_user)
        assert False, "410이 발생해야 함"
    except HTTPException as e:
        assert e.status_code == 410


# ─────────────────────────────────────────────────────────────
# walletStatus(credits)
# ─────────────────────────────────────────────────────────────
class CreditsOnlyCursor:
    def __init__(self, credits):
        self._credits = credits

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SELECT credits FROM users"):
            self._result = {"credits": self._credits}
        else:
            raise AssertionError("예상치 못한 SQL: " + s)

    def fetchone(self):
        return self._result


class FakeConn:
    def __init__(self, cur):
        self._cur = cur
        self.closed = False

    def cursor(self):
        return self._cur

    def close(self):
        self.closed = True


def test_get_wallet_status_returns_credits(monkeypatch):
    cur = CreditsOnlyCursor(750)
    conn = FakeConn(cur)
    monkeypatch.setattr(main, "get_db_connection", lambda: conn)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    result = main._get_wallet_status(current_user)

    assert result == {"credits": 750}
    assert conn.closed is True


if __name__ == "__main__":
    import traceback

    class _MonkeyPatch:
        def __init__(self):
            self._undo = []

        def setattr(self, obj, name, value):
            old = getattr(obj, name, None)
            had = hasattr(obj, name)
            self._undo.append((obj, name, had, old))
            setattr(obj, name, value)

        def undo(self):
            for obj, name, had, old in reversed(self._undo):
                if had:
                    setattr(obj, name, old)
                else:
                    try:
                        delattr(obj, name)
                    except AttributeError:
                        pass
            self._undo.clear()

    _fns = [v for k, v in sorted(globals().items())
            if k.startswith("test_") and callable(v)]
    _passed = _failed = 0
    for _fn in _fns:
        mp = _MonkeyPatch()
        try:
            if _fn.__code__.co_argcount:
                _fn(mp)
            else:
                _fn()
            print("PASS  " + _fn.__name__)
            _passed += 1
        except Exception as _e:
            print("FAIL  " + _fn.__name__ + ": " + repr(_e))
            traceback.print_exc()
            _failed += 1
        finally:
            mp.undo()
    print("\n%d passed, %d failed" % (_passed, _failed))
    sys.exit(1 if _failed else 0)
