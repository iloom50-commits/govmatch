# -*- coding: utf-8 -*-
"""G2-2: /api/ai/consultant/match(매칭) 무료화 검증.

free 플랜 + 이번 달 사용량이 옛 한도(3회)를 이미 넘긴 사용자도 429 없이 매칭이
성공해야 한다(사용량 게이트 제거 확인). get_matches_hybrid는 매칭엔진 자체이므로
모킹해 이 테스트를 매칭 게이트 로직에만 집중시킨다.

실행: cd backend && python test_match_free_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

import app.main as main


class FakeCursor:
    def __init__(self, user_row):
        self._user_row = user_row
        self._result = None

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SELECT * FROM users WHERE business_number"):
            self._result = dict(self._user_row)
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


def test_free_plan_over_old_limit_gets_200_no_429():
    # free 플랜, 옛 PLAN_LIMITS["free"]=3을 이미 초과한 사용량 → 예전엔 429였음
    user_row = {
        "plan": "free",
        "plan_expires_at": None,
        "ai_usage_month": 999,
        "ai_usage_reset_at": None,
    }
    cur = FakeCursor(user_row)
    conn = FakeConn(cur)
    monkeypatch = _MonkeyPatch()
    monkeypatch.setattr(main, "get_db_connection", lambda: conn)
    monkeypatch.setattr(main, "get_matches_hybrid", lambda profile, is_individual: [{"id": 1, "title": "테스트공고"}])

    req = main.ConsultantMatchRequest(profile={"company_name": "테스트", "industry_code": "01"})
    current_user = {"user_id": 1, "bn": "111-11-11111", "plan": "free"}

    try:
        result = main.api_ai_consultant_match(req, current_user)
    finally:
        monkeypatch.undo()

    assert result["status"] == "SUCCESS"
    assert result["matches"] == [{"id": 1, "title": "테스트공고"}]
    assert "ai_limit" not in result, "무제한 무료화 후 ai_limit 필드는 없어야 함"


def test_zero_credits_user_still_gets_200():
    """크레딧 0인 사용자도 매칭은 무료이므로 402 없이 통과해야 함(크레딧은 조회조차 안 함)."""
    user_row = {
        "plan": "free",
        "plan_expires_at": None,
        "ai_usage_month": 0,
        "ai_usage_reset_at": None,
    }
    cur = FakeCursor(user_row)
    conn = FakeConn(cur)
    monkeypatch = _MonkeyPatch()
    monkeypatch.setattr(main, "get_db_connection", lambda: conn)
    monkeypatch.setattr(main, "get_matches_hybrid", lambda profile, is_individual: [])

    req = main.ConsultantMatchRequest(profile={"age_range": "20대"})  # industry_code 없음 → 개인
    current_user = {"user_id": 2, "bn": "222-22-22222", "plan": "free"}

    try:
        result = main.api_ai_consultant_match(req, current_user)
    finally:
        monkeypatch.undo()

    assert result["status"] == "SUCCESS"


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
