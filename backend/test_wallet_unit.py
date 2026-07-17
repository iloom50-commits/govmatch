# -*- coding: utf-8 -*-
"""크레딧 지갑 코어(wallet_balance/wallet_add/wallet_deduct/wallet_record_charge) 단위 테스트.

G1-2: 원자적 차감(잔액부족 시 미차감·원장미기록), 멱등 충전(중복 portone_id 미적립)을 검증.
DB 접근은 함수가 cur를 인자로 받는 구조(DI)라 FakeCursor로 in-memory 시뮬레이션.
(GovMatch 기존 관행: get_db_connection 내부 호출 함수는 FakeConn/FakeCursor로 모킹 — 로컬 DB 불필요)

실행: cd backend && python test_wallet_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.wallet import (
    wallet_balance,
    wallet_add,
    wallet_deduct,
    wallet_record_charge,
)


class FakeCursor:
    """users.credits / credit_transactions / payments 를 in-memory로 시뮬레이션."""

    def __init__(self, users=None):
        self._users = users or {}  # user_id -> credits
        self.tx_log = []  # credit_transactions 기록
        self.payments = {}  # portone_id -> row
        self._result = None
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

        elif s.startswith("UPDATE users SET credits = credits - %s"):
            amount, user_id, min_amount = params
            current = self._users.get(user_id, 0)
            if current >= min_amount:
                self._users[user_id] -= amount
                self._result = {"credits": self._users[user_id]}
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

        else:
            raise AssertionError("예상치 못한 SQL: " + s)

    def fetchone(self):
        return self._result


# ─────────────────────────────────────────────────────────────
# wallet_balance
# ─────────────────────────────────────────────────────────────
def test_wallet_balance_returns_current_credits():
    cur = FakeCursor(users={1: 500})
    assert wallet_balance(cur, 1) == 500


def test_wallet_balance_missing_user_is_zero():
    cur = FakeCursor(users={})
    assert wallet_balance(cur, 999) == 0


# ─────────────────────────────────────────────────────────────
# wallet_add
# ─────────────────────────────────────────────────────────────
def test_wallet_add_increments_and_logs():
    cur = FakeCursor(users={1: 100})
    new_balance = wallet_add(cur, 1, 50, "charge", ref="test-ref")
    assert new_balance == 150
    assert cur._users[1] == 150
    assert len(cur.tx_log) == 1
    tx = cur.tx_log[0]
    assert tx["amount"] == 50
    assert tx["balance_after"] == 150
    assert tx["type"] == "charge"
    assert tx["ref"] == "test-ref"


# ─────────────────────────────────────────────────────────────
# wallet_deduct
# ─────────────────────────────────────────────────────────────
def test_wallet_deduct_insufficient_balance_fails_and_no_log():
    cur = FakeCursor(users={1: 10})
    ok = wallet_deduct(cur, 1, 50, "consume", ref="ann-1")
    assert ok is False
    assert cur._users[1] == 10, "잔액이 변하면 안 됨"
    assert cur.tx_log == [], "원장에 기록되면 안 됨"


def test_wallet_deduct_success_updates_balance_and_logs_negative():
    cur = FakeCursor(users={1: 100})
    ok = wallet_deduct(cur, 1, 30, "consume", ref="ann-2")
    assert ok is True
    assert cur._users[1] == 70
    assert len(cur.tx_log) == 1
    tx = cur.tx_log[0]
    assert tx["amount"] == -30, "차감 원장은 음수여야 함"
    assert tx["balance_after"] == 70
    assert tx["ref"] == "ann-2"


def test_wallet_deduct_exact_balance_succeeds():
    cur = FakeCursor(users={1: 30})
    ok = wallet_deduct(cur, 1, 30, "consume")
    assert ok is True
    assert cur._users[1] == 0


# ─────────────────────────────────────────────────────────────
# wallet_record_charge — 멱등성
# ─────────────────────────────────────────────────────────────
def test_wallet_record_charge_adds_credits_first_time():
    cur = FakeCursor(users={1: 0})
    new_balance = wallet_record_charge(cur, 1, 9900, 100, "portone-abc")
    assert new_balance == 100
    assert cur._users[1] == 100
    assert len(cur.tx_log) == 1


def test_wallet_record_charge_duplicate_portone_id_is_noop():
    cur = FakeCursor(users={1: 0})
    first = wallet_record_charge(cur, 1, 9900, 100, "portone-dup")
    assert first == 100
    second = wallet_record_charge(cur, 1, 9900, 100, "portone-dup")
    assert second is None, "중복 portone_id는 None(멱등) 반환해야 함"
    assert cur._users[1] == 100, "잔액이 2배가 되면 안 됨(중복 적립 차단)"
    assert len(cur.tx_log) == 1, "중복 시 원장도 추가되면 안 됨"


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
