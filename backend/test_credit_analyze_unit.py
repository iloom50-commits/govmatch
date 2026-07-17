# -*- coding: utf-8 -*-
"""G2-3: 공고문 분석(GET /api/pro/announcements/{id}/analyze) 50크레딧 차감 단위 테스트.

돈 경로 원칙 검증:
- 분석 성공 → 50 차감
- 분석 실패(예외) → 무차감
- 잔액부족 → 402
- 면제 계정(서비스토큰) → 무차감 통과

DB 접근은 get_db_connection()을 FakeConn/FakeCursor로 모킹(GovMatch 기존 관행,
test_credit_gate_unit.py 참고). get_db_connection은 endpoint 본문과 _charge_credits
양쪽에서 각각 호출되므로, 매 호출마다 새 FakeConn을 반환하되 users 딕셔너리는 공유한다.

실행: cd backend && python test_credit_analyze_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

from fastapi import HTTPException

import app.main as main


class FakeCursor:
    """announcements 조회 + users.credits/credit_transactions 를 in-memory로 시뮬레이션."""

    def __init__(self, ann_row, users):
        self._ann_row = ann_row
        self._users = users
        self._result = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        params = params or ()

        if s.startswith("SELECT a.*, aa.parsed_sections"):
            self._result = dict(self._ann_row) if self._ann_row else None

        elif s.startswith("SELECT credits FROM users"):
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


def _make_db_factory(monkeypatch, ann_row, users):
    """get_db_connection 호출마다 같은 users 딕셔너리를 공유하는 새 FakeConn을 반환."""

    def _factory():
        cur = FakeCursor(ann_row, users)
        return FakeConn(cur)

    monkeypatch.setattr(main, "get_db_connection", _factory)


ANN_ROW_ANALYZED = {
    "announcement_id": 1,
    "title": "테스트 공고",
    "organization": "테스트기관",
    "support_amount": "1000만원",
    "deadline_date": None,
    "url": "https://example.com",
    "parsed_sections": {"eligibility": "누구나"},
    "deep_analysis": {"target_summary": "요약"},
}


# ─────────────────────────────────────────────────────────────
# 분석 성공 → 50 차감
# ─────────────────────────────────────────────────────────────
def test_analyze_success_charges_50(monkeypatch):
    users = {1: {"credits": 100}}
    _make_db_factory(monkeypatch, ANN_ROW_ANALYZED, users)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    result = main.api_pro_announcement_analyze(1, current_user)

    assert result["status"] == "SUCCESS"
    assert users[1]["credits"] == 50, "분석 성공 후 50크레딧이 차감되어야 함"


# ─────────────────────────────────────────────────────────────
# 공고 없음(404) → 차감 전에 실패하므로 무차감
# ─────────────────────────────────────────────────────────────
def test_analyze_not_found_no_charge(monkeypatch):
    users = {1: {"credits": 100}}
    _make_db_factory(monkeypatch, None, users)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    try:
        main.api_pro_announcement_analyze(999, current_user)
        assert False, "404가 발생해야 함"
    except HTTPException as e:
        assert e.status_code == 404

    assert users[1]["credits"] == 100, "분석 실패(404) 시 차감되면 안 됨"


# ─────────────────────────────────────────────────────────────
# 잔액부족 → 402 (분석 자체는 성공했지만 차감 단계에서 402)
# ─────────────────────────────────────────────────────────────
def test_analyze_insufficient_credits_402(monkeypatch):
    users = {1: {"credits": 10}}
    _make_db_factory(monkeypatch, ANN_ROW_ANALYZED, users)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    try:
        main.api_pro_announcement_analyze(1, current_user)
        assert False, "402가 발생해야 함"
    except HTTPException as e:
        assert e.status_code == 402

    assert users[1]["credits"] == 10, "잔액부족 시 차감되면 안 됨"


# ─────────────────────────────────────────────────────────────
# 면제 계정(서비스토큰) → 무차감 통과
# ─────────────────────────────────────────────────────────────
def test_analyze_service_token_no_charge(monkeypatch):
    users = {}
    _make_db_factory(monkeypatch, ANN_ROW_ANALYZED, users)
    current_user = {"bn": "svc", "sub": "smartdoc-service", "_service": True}

    result = main.api_pro_announcement_analyze(1, current_user)

    assert result["status"] == "SUCCESS"
    # 서비스 계정은 users 딕셔너리에 없어도(크레딧 조회 자체가 스킵) 예외 없이 통과해야 함


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
