# -*- coding: utf-8 -*-
"""크레딧 지갑 API(G1-3~G1-5) 단위 테스트: 충전팩 조회·잔액/원장 조회 + PortOne 충전 검증 + 가입 보너스.

FastAPI 라우트 함수를 데코레이터 그대로 직접 호출한다(Depends 기본값은 무시하고
current_user를 명시적으로 전달) — GovMatch 기존 관행(FakeCursor in-memory 모킹).

실행: cd backend && python test_wallet_api.py
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


class FakeCursor:
    """users.credits / credit_transactions / payments 를 in-memory로 시뮬레이션."""

    def __init__(self, users=None, payments=None, tx_types=None):
        self._users = users or {}  # user_id -> credits
        self.tx_log = []  # {user_id, type, amount, balance_after, ref}
        self.payments = payments or {}  # portone_id -> row
        # user_id -> set(tx types already recorded) — signup_bonus 중복검사용 seed
        self._seed_tx_types = tx_types or {}
        self._result = None
        self._results = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        params = params or ()

        if s.startswith("SELECT credits FROM users"):
            user_id = params[0]
            if user_id in self._users:
                self._result = {"credits": self._users[user_id]}
                self.rowcount = 1
            else:
                self._result = None
                self.rowcount = 0

        elif s.startswith("UPDATE users SET credits = credits + %s"):
            amount, user_id = params
            if user_id not in self._users:
                self._result = None
                self.rowcount = 0
            else:
                self._users[user_id] += amount
                self._result = {"credits": self._users[user_id]}
                self.rowcount = 1

        elif s.startswith("INSERT INTO credit_transactions"):
            user_id, tx_type, amount, balance_after, ref = params
            self.tx_log.append({
                "user_id": user_id, "type": tx_type, "amount": amount,
                "balance_after": balance_after, "ref": ref,
            })
            self._seed_tx_types.setdefault(user_id, set()).add(tx_type)
            self.rowcount = 1

        elif s.startswith("INSERT INTO payments"):
            user_id, portone_id, amount_krw, credits = params
            if portone_id in self.payments:
                self._result = None
                self.rowcount = 0
            else:
                row = {
                    "id": len(self.payments) + 1, "user_id": user_id,
                    "portone_id": portone_id, "amount_krw": amount_krw,
                    "credits": credits,
                }
                self.payments[portone_id] = row
                self._result = {"id": row["id"]}
                self.rowcount = 1

        elif s.startswith("SELECT 1 FROM payments WHERE portone_id"):
            portone_id = params[0]
            self._result = {"?column?": 1} if portone_id in self.payments else None

        elif s.startswith("SELECT 1 FROM credit_transactions WHERE user_id") and "signup_bonus" in s:
            user_id = params[0]
            has = "signup_bonus" in self._seed_tx_types.get(user_id, set())
            self._result = {"?column?": 1} if has else None

        elif s.startswith("SELECT type, amount, balance_after, ref, created_at"):
            user_id = params[0]
            rows = [t for t in reversed(self.tx_log) if t["user_id"] == user_id]
            self._results = [
                {"type": t["type"], "amount": t["amount"], "balance_after": t["balance_after"],
                 "ref": t["ref"], "created_at": None}
                for t in rows[:50]
            ]

        elif "NOT IN" in s and s.startswith("SELECT user_id FROM users"):
            self._results = [
                {"user_id": uid} for uid in self._users
                if "signup_bonus" not in self._seed_tx_types.get(uid, set())
            ]

        else:
            raise AssertionError("예상치 못한 SQL: " + s)

    def fetchone(self):
        return self._result

    def fetchall(self):
        return self._results


class FakeConn:
    def __init__(self, cur):
        self._cur = cur
        self.committed = 0
        self.closed = False

    def cursor(self):
        return self._cur

    def commit(self):
        self.committed += 1

    def close(self):
        self.closed = True


_orig_get_db_connection = m.get_db_connection
_orig_verify_portone = m._verify_portone_payment


def _patch_db(cur):
    conn = FakeConn(cur)
    m.get_db_connection = lambda: conn
    return conn


def _restore():
    m.get_db_connection = _orig_get_db_connection
    m._verify_portone_payment = _orig_verify_portone


# ─────────────────────────────────────────────────────────────
# /api/wallet/packs
# ─────────────────────────────────────────────────────────────
def test_packs_returns_catalog():
    """팩 카탈로그를 그대로 노출한다(요금 개편에 깨지지 않도록 CREDIT_PACKS 기준으로 검증)."""
    result = m.api_wallet_packs()
    assert len(result["packs"]) == len(m.CREDIT_PACKS)
    assert result["packs"] == [{"krw": k, "credits": c} for k, c in m.CREDIT_PACKS]
    assert all(p["krw"] > 0 and p["credits"] > 0 for p in result["packs"])


# ─────────────────────────────────────────────────────────────
# /api/wallet
# ─────────────────────────────────────────────────────────────
def test_wallet_returns_balance_and_transactions():
    cur = FakeCursor(users={1: 500})
    cur.tx_log.append({"user_id": 1, "type": "signup_bonus", "amount": 500, "balance_after": 500, "ref": None})
    try:
        _patch_db(cur)
        result = m.api_wallet(current_user={"user_id": 1})
        assert result["credits"] == 500
        assert len(result["transactions"]) == 1
        assert result["transactions"][0]["type"] == "signup_bonus"
    finally:
        _restore()


# ─────────────────────────────────────────────────────────────
# /api/wallet/charge/verify
# ─────────────────────────────────────────────────────────────
def test_charge_verify_success_adds_credits():
    cur = FakeCursor(users={1: 0})
    try:
        _patch_db(cur)
        krw, credits = m.CREDIT_PACKS[0]   # 요금 개편에 깨지지 않도록 카탈로그 첫 팩 사용
        m._verify_portone_payment = lambda pid: {"status": "PAID", "amount": krw, "user_id": 1}
        req = m.WalletChargeVerifyRequest(payment_id="pay-1")
        result = m.api_wallet_charge_verify(req, current_user={"user_id": 1})
        assert result == {"ok": True, "credits": credits}
        assert cur._users[1] == credits
    finally:
        _restore()


def test_charge_verify_duplicate_payment_id_no_double_credit():
    cur = FakeCursor(users={1: 0})
    try:
        _patch_db(cur)
        krw, credits = m.CREDIT_PACKS[0]
        m._verify_portone_payment = lambda pid: {"status": "PAID", "amount": krw, "user_id": 1}
        req = m.WalletChargeVerifyRequest(payment_id="pay-dup")
        first = m.api_wallet_charge_verify(req, current_user={"user_id": 1})
        assert first["credits"] == credits
        second = m.api_wallet_charge_verify(req, current_user={"user_id": 1})
        assert second == {"ok": True, "credits": credits, "duplicate": True}
        assert cur._users[1] == credits, "잔액이 2배가 되면 안 됨"
    finally:
        _restore()


def test_charge_verify_invalid_amount_400():
    cur = FakeCursor(users={1: 0})
    try:
        _patch_db(cur)
        m._verify_portone_payment = lambda pid: {"status": "PAID", "amount": 12345, "user_id": 1}
        req = m.WalletChargeVerifyRequest(payment_id="pay-bad-amount")
        try:
            m.api_wallet_charge_verify(req, current_user={"user_id": 1})
            assert False, "400 예외가 발생해야 함"
        except m.HTTPException as e:
            assert e.status_code == 400
    finally:
        _restore()


def test_charge_verify_not_paid_400():
    cur = FakeCursor(users={1: 0})
    try:
        _patch_db(cur)
        m._verify_portone_payment = lambda pid: {"status": "READY", "amount": 19000, "user_id": 1}
        req = m.WalletChargeVerifyRequest(payment_id="pay-not-paid")
        try:
            m.api_wallet_charge_verify(req, current_user={"user_id": 1})
            assert False, "400 예외가 발생해야 함"
        except m.HTTPException as e:
            assert e.status_code == 400
    finally:
        _restore()


def test_charge_verify_owner_mismatch_403():
    cur = FakeCursor(users={1: 0, 2: 0})
    try:
        _patch_db(cur)
        m._verify_portone_payment = lambda pid: {"status": "PAID", "amount": 19000, "user_id": 2}
        req = m.WalletChargeVerifyRequest(payment_id="pay-mismatch")
        try:
            m.api_wallet_charge_verify(req, current_user={"user_id": 1})
            assert False, "403 예외가 발생해야 함"
        except m.HTTPException as e:
            assert e.status_code == 403
    finally:
        _restore()


def test_charge_verify_portone_lookup_failure_502():
    cur = FakeCursor(users={1: 0})
    try:
        _patch_db(cur)

        def _raise(pid):
            raise RuntimeError("network down")
        m._verify_portone_payment = _raise
        req = m.WalletChargeVerifyRequest(payment_id="pay-network-fail")
        try:
            m.api_wallet_charge_verify(req, current_user={"user_id": 1})
            assert False, "502 예외가 발생해야 함"
        except m.HTTPException as e:
            assert e.status_code == 502
    finally:
        _restore()


# ─────────────────────────────────────────────────────────────
# 가입 보너스
# ─────────────────────────────────────────────────────────────
def test_grant_signup_bonus_first_time():
    cur = FakeCursor(users={10: 0})
    m._grant_signup_bonus(cur, 10)
    assert cur._users[10] == 500
    assert len(cur.tx_log) == 1
    assert cur.tx_log[0]["type"] == "signup_bonus"


def test_grant_signup_bonus_already_granted_is_noop():
    cur = FakeCursor(users={10: 0})
    m._grant_signup_bonus(cur, 10)
    m._grant_signup_bonus(cur, 10)
    assert cur._users[10] == 500, "두 번째 호출에서 중복 지급되면 안 됨"
    assert len(cur.tx_log) == 1


def test_backfill_signup_bonus_batch_idempotent():
    # user 20: 이미 signup_bonus 있음(소급 대상 아님) / user 21: 없음(소급 대상)
    cur = FakeCursor(
        users={20: 500, 21: 0},
        tx_types={20: {"signup_bonus"}},
    )
    try:
        _patch_db(cur)
        result = m.api_admin_credit_backfill_signup_bonus()
        assert result == {"granted": 1}
        assert cur._users[21] == 500
        assert cur._users[20] == 500, "이미 지급된 회원은 변동 없어야 함"

        # 재실행 — 멱등(전원 이미 지급됨 → 0건)
        result2 = m.api_admin_credit_backfill_signup_bonus()
        assert result2 == {"granted": 0}
    finally:
        _restore()


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
