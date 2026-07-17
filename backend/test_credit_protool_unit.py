# -*- coding: utf-8 -*-
"""G2-5: 전문가도구 500크레딧(가치 액션만) 단위 테스트.

돈 경로 원칙 검증(대표 엔드포인트로 검증):
- 가치 액션(files/analyze) 성공 → 500 차감
- 실패(분석할 텍스트 부족 — 실제 분석 미실행) → 무차감
- 잔액부족 → 402
- 면제 계정(서비스토큰) → 무차감 통과
- 무료 엔드포인트(clients 목록 조회)는 _require_pro 제거 후에도 크레딧 테이블을
  전혀 건드리지 않고 로그인만으로 동작해야 함(과금 없음 확인).

실행: cd backend && python test_credit_protool_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("GEMINI_API_KEY", "")  # 실제 네트워크 호출 방지(빈 키 → 조기 반환 분기)

from fastapi import HTTPException

import app.main as main


class CreditsCursor:
    """users.credits / credit_transactions 만 다루는 최소 FakeCursor (_charge_credits용)."""

    def __init__(self, users):
        self._users = users
        self._result = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        params = params or ()

        if s.startswith("SELECT credits FROM users"):
            user_id = params[0]
            row = self._users.get(user_id)
            self._result = {"credits": row["credits"]} if row else None

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
            self.rowcount = 1

        else:
            raise AssertionError("예상치 못한 SQL(CreditsCursor): " + s)

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


def _patch_credits_db(monkeypatch, users):
    """get_db_connection 호출마다 같은 users 딕셔너리를 공유하는 새 FakeConn을 반환.
    files/analyze는 DB를 credits 목적으로만 사용(다른 테이블 접근 없음)."""

    def _factory():
        return FakeConn(CreditsCursor(users))

    monkeypatch.setattr(main, "get_db_connection", _factory)


# ─────────────────────────────────────────────────────────────
# 가치 액션 성공 → 500 차감 (files/analyze)
# ─────────────────────────────────────────────────────────────
def test_files_analyze_success_charges_500(monkeypatch):
    users = {1: {"credits": 1000}}
    _patch_credits_db(monkeypatch, users)
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    req = main.FileAnalyzeRequest(text="이것은 충분히 긴 분석 대상 텍스트입니다. " * 3)

    result = main.api_pro_file_analyze(req, current_user)

    assert result["status"] == "SUCCESS"
    assert users[1]["credits"] == 500, "분석 성공 후 500크레딧이 차감되어야 함"


# ─────────────────────────────────────────────────────────────
# 실패(텍스트 부족 — 분석 미실행) → 무차감
# ─────────────────────────────────────────────────────────────
def test_files_analyze_too_short_no_charge(monkeypatch):
    users = {1: {"credits": 1000}}
    _patch_credits_db(monkeypatch, users)
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    req = main.FileAnalyzeRequest(text="짧음")

    result = main.api_pro_file_analyze(req, current_user)

    assert result["status"] == "SUCCESS"
    assert users[1]["credits"] == 1000, "분석을 실행하지 않았으므로 차감되면 안 됨"


# ─────────────────────────────────────────────────────────────
# 잔액부족 → 402 (분석 자체는 성공했지만 차감 단계에서 402)
# ─────────────────────────────────────────────────────────────
def test_files_analyze_insufficient_credits_402(monkeypatch):
    users = {1: {"credits": 100}}
    _patch_credits_db(monkeypatch, users)
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    req = main.FileAnalyzeRequest(text="이것은 충분히 긴 분석 대상 텍스트입니다. " * 3)

    try:
        main.api_pro_file_analyze(req, current_user)
        assert False, "402가 발생해야 함"
    except HTTPException as e:
        assert e.status_code == 402

    assert users[1]["credits"] == 100, "잔액부족 시 차감되면 안 됨"


# ─────────────────────────────────────────────────────────────
# 면제 계정(서비스토큰) → 무차감 통과
# ─────────────────────────────────────────────────────────────
def test_files_analyze_service_token_no_charge(monkeypatch):
    def _boom():
        raise AssertionError("서비스 토큰은 DB를 조회하면 안 됨")

    monkeypatch.setattr(main, "get_db_connection", _boom)
    current_user = {"bn": "svc", "sub": "smartdoc-service", "_service": True}
    req = main.FileAnalyzeRequest(text="이것은 충분히 긴 분석 대상 텍스트입니다. " * 3)

    result = main.api_pro_file_analyze(req, current_user)

    assert result["status"] == "SUCCESS"


# ─────────────────────────────────────────────────────────────
# 무료 엔드포인트(clients 목록) — _require_pro 제거 확인:
# plan 조회 없이, 로그인만으로 동작하고 크레딧 테이블을 건드리지 않음
# ─────────────────────────────────────────────────────────────
class ClientsListCursor:
    def __init__(self):
        self.rowcount = 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SELECT id, client_name"):
            self._rows = []
        else:
            raise AssertionError(
                "무료 엔드포인트가 예상 밖의 SQL을 실행함(plan 조회나 크레딧 차감이 남아있을 가능성): "
                + s
            )

    def fetchall(self):
        return self._rows


def test_pro_clients_list_is_free_no_plan_check_no_charge(monkeypatch):
    cur = ClientsListCursor()
    conn = FakeConn(cur)
    monkeypatch.setattr(main, "get_db_connection", lambda: conn)
    # plan 필드가 아예 없어도(무료 사용자) 동작해야 함 — _require_pro가 완전히 제거됐는지 확인
    current_user = {"bn": "222-22-22222"}

    result = main.api_pro_clients(None, current_user)

    assert result["status"] == "SUCCESS"
    assert result["clients"] == []


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
