# -*- coding: utf-8 -*-
"""크레딧 차감 게이트(_is_credit_exempt / _charge_credits) 단위 테스트.

G2-1: 성공 이후에만 차감, 잔액부족 402, 서비스계정/관리자(plan=pro·biz 무기한 또는
_service 토큰) 무차감 통과를 검증한다.

DB 접근은 app.main._charge_credits가 get_db_connection()으로 커넥션을 얻는 구조라
get_db_connection을 FakeConn/FakeCursor로 모킹한다(GovMatch 기존 관행,
test_wallet_unit.py 참고). is_credit_exempt의 DB plan 조회도 같은 FakeCursor로 모킹.

실행: cd backend && python test_credit_gate_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

from fastapi import HTTPException

from app.services import wallet


class FakeCursor:
    """users(credits, plan, plan_expires_at) / credit_transactions 를 in-memory로 시뮬레이션."""

    def __init__(self, users=None):
        # user_id -> {"credits": int, "plan": str, "plan_expires_at": str|None}
        self._users = users or {}
        self.tx_log = []
        self._result = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        params = params or ()

        if s.startswith("SELECT credits FROM users"):
            user_id = params[0]
            row = self._users.get(user_id)
            if row is None:
                self._result = None
                self.rowcount = 0
            else:
                self._result = {"credits": row["credits"]}
                self.rowcount = 1

        elif s.startswith("SELECT plan, plan_expires_at FROM users WHERE user_id"):
            user_id = params[0]
            row = self._users.get(user_id)
            if row is None:
                self._result = None
                self.rowcount = 0
            else:
                self._result = {"plan": row.get("plan"), "plan_expires_at": row.get("plan_expires_at")}
                self.rowcount = 1

        elif s.startswith("UPDATE users SET credits = credits - %s"):
            amount, user_id, min_amount = params
            row = self._users.get(user_id)
            current = row["credits"] if row else 0
            if row is not None and current >= min_amount:
                row["credits"] -= amount
                self._result = {"credits": row["credits"]}
                self.rowcount = 1
            else:
                self._result = None
                self.rowcount = 0

        elif s.startswith("INSERT INTO credit_transactions"):
            user_id, tx_type, amount, balance_after, ref = params
            self.tx_log.append({
                "user_id": user_id, "type": tx_type, "amount": amount,
                "balance_after": balance_after, "ref": ref,
            })
            self.rowcount = 1

        else:
            raise AssertionError("예상치 못한 SQL: " + s)

    def fetchone(self):
        return self._result


class FakeConn:
    def __init__(self, cur):
        self._cur = cur
        self.committed = False
        self.closed = False

    def cursor(self):
        return self._cur

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def _patch_db(monkeypatch, main_mod, users):
    cur = FakeCursor(users=users)
    conn = FakeConn(cur)
    monkeypatch.setattr(main_mod, "get_db_connection", lambda: conn)
    return conn, cur


def _import_main(monkeypatch=None):
    import importlib
    import app.main as main_mod
    importlib.reload(main_mod) if False else None
    return main_mod


import app.main as main


# ─────────────────────────────────────────────────────────────
# _charge_credits — 정상 차감
# ─────────────────────────────────────────────────────────────
def test_charge_credits_deducts_and_returns_balance(monkeypatch):
    users = {1: {"credits": 100, "plan": "free", "plan_expires_at": None}}
    conn, cur = _patch_db(monkeypatch, main, users)
    current_user = {"user_id": 1, "bn": "111-11-11111", "plan": "free"}

    main._charge_credits(current_user, 50, "deduct", ref="test")

    assert users[1]["credits"] == 50
    assert conn.committed is True
    assert len(cur.tx_log) == 1
    assert cur.tx_log[0]["amount"] == -50


# ─────────────────────────────────────────────────────────────
# _charge_credits — 잔액부족 402
# ─────────────────────────────────────────────────────────────
def test_charge_credits_insufficient_raises_402(monkeypatch):
    users = {1: {"credits": 10, "plan": "free", "plan_expires_at": None}}
    _patch_db(monkeypatch, main, users)
    current_user = {"user_id": 1, "bn": "111-11-11111", "plan": "free"}

    try:
        main._charge_credits(current_user, 50, "deduct", ref="test")
        assert False, "402가 발생해야 함"
    except HTTPException as e:
        assert e.status_code == 402
        assert e.detail["required"] == 50
        assert e.detail["balance"] == 10

    assert users[1]["credits"] == 10, "잔액부족 시 차감되면 안 됨"


# ─────────────────────────────────────────────────────────────
# _is_credit_exempt / _charge_credits — 면제(관리자·서비스계정) 무차감 통과
# ─────────────────────────────────────────────────────────────
def test_charge_credits_pro_plan_account_skips_deduction(monkeypatch):
    """plan='pro'(무기한, plan_expires_at NULL) 계정 — 서비스계정/대표 우회 관행."""
    users = {2: {"credits": 0, "plan": "pro", "plan_expires_at": None}}
    conn, cur = _patch_db(monkeypatch, main, users)
    current_user = {"user_id": 2, "bn": "222-22-22222", "plan": "free"}  # JWT plan은 신뢰 안 함

    main._charge_credits(current_user, 500, "deduct", ref="test")

    assert users[2]["credits"] == 0, "면제 대상은 차감되면 안 됨"
    assert cur.tx_log == []


def test_charge_credits_service_token_skips_deduction(monkeypatch):
    """SmartDoc 서비스 토큰(_service=True, user_id 없음) — DB 조회 없이 즉시 통과해야 함."""

    def _boom():
        raise AssertionError("서비스 토큰은 DB를 조회하면 안 됨")

    monkeypatch.setattr(main, "get_db_connection", _boom)
    current_user = {"bn": "333-33-33333", "sub": "smartdoc-service", "_service": True}

    main._charge_credits(current_user, 500, "deduct", ref="test")  # 예외 없이 통과해야 함


def test_is_credit_exempt_biz_plan_true(monkeypatch):
    users = {5: {"credits": 0, "plan": "biz", "plan_expires_at": None}}
    _patch_db(monkeypatch, main, users)
    assert main._is_credit_exempt({"user_id": 5, "bn": "x", "plan": "free"}) is True


def test_is_credit_exempt_expired_pro_false(monkeypatch):
    users = {6: {"credits": 0, "plan": "pro", "plan_expires_at": "2020-01-01T00:00:00"}}
    _patch_db(monkeypatch, main, users)
    assert main._is_credit_exempt({"user_id": 6, "bn": "x", "plan": "free"}) is False


def test_is_credit_exempt_free_plan_false(monkeypatch):
    users = {7: {"credits": 0, "plan": "free", "plan_expires_at": None}}
    _patch_db(monkeypatch, main, users)
    assert main._is_credit_exempt({"user_id": 7, "bn": "x", "plan": "free"}) is False


if __name__ == "__main__":
    import traceback
    import types

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
            _fn(mp)
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
