# -*- coding: utf-8 -*-
"""크레딧 차감 게이트(_is_credit_exempt / _charge_credits) 단위 테스트.

G2-1: 성공 이후에만 차감, 잔액부족 402, 면제(서비스토큰/CREDIT_EXEMPT_BNS 허용목록)
무차감 통과를 검증한다.

★ 면제는 plan(구독)과 완전히 분리되어 있다 — G2의 목적이 구독 폐지이므로,
plan='pro'/'biz'라는 이유만으로는 면제되지 않는다(리뷰 반영: plan 기반 면제는
"무한 무료 이용권" 구멍이 됨). 면제는 오직 ①SmartDoc 서비스토큰(_service=True)
②CREDIT_EXEMPT_BNS 환경변수 허용목록 두 가지뿐이다.

DB 접근은 app.main._charge_credits가 get_db_connection()으로 커넥션을 얻는 구조라
get_db_connection을 FakeConn/FakeCursor로 모킹한다(GovMatch 기존 관행,
test_wallet_unit.py 참고).

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
    """users.credits / credit_transactions 를 in-memory로 시뮬레이션."""

    def __init__(self, users=None):
        # user_id -> {"credits": int}
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
            raise AssertionError("예상치 못한 SQL: " + s + " — _is_credit_exempt는 이제 DB를 조회하면 안 됨")

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


import app.main as main


# ─────────────────────────────────────────────────────────────
# _charge_credits — 정상 차감
# ─────────────────────────────────────────────────────────────
def test_charge_credits_deducts_and_returns_balance(monkeypatch):
    users = {1: {"credits": 100}}
    conn, cur = _patch_db(monkeypatch, main, users)
    monkeypatch.setattr(main, "CREDIT_EXEMPT_BNS", set())
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    main._charge_credits(current_user, 50, "deduct", ref="test")

    assert users[1]["credits"] == 50
    assert conn.committed is True
    assert len(cur.tx_log) == 1
    assert cur.tx_log[0]["amount"] == -50


# ─────────────────────────────────────────────────────────────
# _charge_credits — 잔액부족 402
# ─────────────────────────────────────────────────────────────
def test_charge_credits_insufficient_raises_402(monkeypatch):
    users = {1: {"credits": 10}}
    _patch_db(monkeypatch, main, users)
    monkeypatch.setattr(main, "CREDIT_EXEMPT_BNS", set())
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    try:
        main._charge_credits(current_user, 50, "deduct", ref="test")
        assert False, "402가 발생해야 함"
    except HTTPException as e:
        assert e.status_code == 402
        assert e.detail["required"] == 50
        assert e.detail["balance"] == 10

    assert users[1]["credits"] == 10, "잔액부족 시 차감되면 안 됨"


# ─────────────────────────────────────────────────────────────
# plan은 면제 근거가 아니다 (리뷰 반영 — 구독 폐지가 목적이므로 plan='pro'/'biz'
# 여도 허용목록에 없으면 반드시 과금되어야 한다)
# ─────────────────────────────────────────────────────────────
def test_charge_credits_pro_plan_not_in_allowlist_still_charged(monkeypatch):
    """plan='pro'인데 CREDIT_EXEMPT_BNS에 없으면 정상 과금되어야 한다."""
    users = {2: {"credits": 1000}}
    conn, cur = _patch_db(monkeypatch, main, users)
    monkeypatch.setattr(main, "CREDIT_EXEMPT_BNS", set())
    # current_user에 plan='pro'가 실려 있어도 무시되어야 함
    current_user = {"user_id": 2, "bn": "222-22-22222", "plan": "pro"}

    main._charge_credits(current_user, 500, "deduct", ref="test")

    assert users[2]["credits"] == 500, "plan='pro'라도 허용목록에 없으면 과금되어야 함"
    assert len(cur.tx_log) == 1


def test_is_credit_exempt_pro_plan_without_allowlist_is_false(monkeypatch):
    monkeypatch.setattr(main, "CREDIT_EXEMPT_BNS", set())
    assert main._is_credit_exempt({"user_id": 5, "bn": "biz-bn", "plan": "biz"}) is False
    assert main._is_credit_exempt({"user_id": 6, "bn": "pro-bn", "plan": "pro"}) is False


# ─────────────────────────────────────────────────────────────
# 면제 ① SmartDoc 서비스 토큰
# ─────────────────────────────────────────────────────────────
def test_charge_credits_service_token_skips_deduction(monkeypatch):
    """SmartDoc 서비스 토큰(_service=True, user_id 없음) — DB 조회 없이 즉시 통과해야 함."""

    def _boom():
        raise AssertionError("서비스 토큰은 DB를 조회하면 안 됨")

    monkeypatch.setattr(main, "get_db_connection", _boom)
    current_user = {"bn": "333-33-33333", "sub": "smartdoc-service", "_service": True}

    main._charge_credits(current_user, 500, "deduct", ref="test")  # 예외 없이 통과해야 함


def test_is_credit_exempt_service_token_true(monkeypatch):
    assert main._is_credit_exempt({"bn": "x", "_service": True}) is True


# ─────────────────────────────────────────────────────────────
# 면제 ② CREDIT_EXEMPT_BNS 허용목록
# ─────────────────────────────────────────────────────────────
def test_charge_credits_allowlisted_bn_skips_deduction(monkeypatch):
    def _boom():
        raise AssertionError("허용목록 대상은 DB를 조회하면 안 됨(면제 판정에 한해)")

    monkeypatch.setattr(main, "get_db_connection", _boom)
    monkeypatch.setattr(main, "CREDIT_EXEMPT_BNS", {"999-99-99999"})
    current_user = {"user_id": 9, "bn": "999-99-99999"}

    main._charge_credits(current_user, 500, "deduct", ref="test")  # 예외 없이 통과해야 함


def test_is_credit_exempt_bn_not_in_allowlist_false(monkeypatch):
    monkeypatch.setattr(main, "CREDIT_EXEMPT_BNS", {"999-99-99999"})
    assert main._is_credit_exempt({"user_id": 1, "bn": "111-11-11111"}) is False


def test_is_credit_exempt_empty_bn_false(monkeypatch):
    monkeypatch.setattr(main, "CREDIT_EXEMPT_BNS", {""})
    assert main._is_credit_exempt({"user_id": 1, "bn": ""}) is False
    assert main._is_credit_exempt({"user_id": 1}) is False


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
