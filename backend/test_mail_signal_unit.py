# -*- coding: utf-8 -*-
"""메일 신호(인프라 알림) 분류·저장·수집분석 단위 테스트 — mail_signal_collector.

실행: cd backend && python test_mail_signal_unit.py
FakeConn/FakeCursor 모킹(실 DB 없음). LLM·Gmail 의존 없음.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass
from app.services.orchestrator.mail_signal_collector import (
    classify_service,
    estimate_severity,
    action_hint,
    store_mail_signal,
    validate_mail_signal,
    collect_mail_signals,
)


class _FakeCur:
    def __init__(self, rows=None, fetchone_val=None):
        self.sql = []               # [(normalized_sql, params)]
        self.rows = rows or []
        self._fetchone_val = fetchone_val
    def execute(self, sql, params=None):
        self.sql.append((" ".join(sql.split()), params))
    def fetchone(self):
        return self._fetchone_val
    def fetchall(self):
        return self.rows


class _FakeConn:
    def __init__(self, rows=None, fetchone_val=None):
        self._cur = _FakeCur(rows, fetchone_val)
        self.committed = False
    def cursor(self):
        return self._cur
    def commit(self):
        self.committed = True


def test_classify_service():
    assert classify_service("noreply@railway.app") == "railway"
    assert classify_service("team@railway.com") == "railway"
    assert classify_service("notifications@vercel.com") == "vercel"
    assert classify_service("alerts@supabase.io") == "supabase"
    assert classify_service("billing@supabase.com") == "supabase"
    assert classify_service("hello@example.com") == "other"


def test_estimate_severity():
    assert estimate_severity("Deployment failed", "build error") == "high"
    assert estimate_severity("Your project", "exceeded your quota") == "high"
    assert estimate_severity("Weekly summary", "all good") == "info"


def test_store_uses_on_conflict_and_classifies():
    conn = _FakeConn(fetchone_val={"id": 1})
    payload = {
        "msg_id": "abc123",
        "from": "noreply@railway.app",
        "subject": "Deployment failed",
        "snippet": "build error",
    }
    created = store_mail_signal(conn, payload)
    assert created is True, "신규 저장이 True를 반환해야 함"
    assert len(conn._cur.sql) == 1
    sql, params = conn._cur.sql[0]
    assert "ON CONFLICT" in sql, "멱등 저장(ON CONFLICT) 누락"
    assert "gmail_msg_id" in sql, "gmail_msg_id 컬럼 누락"
    assert "railway" in params, "service 분류(railway) 미반영"
    assert "high" in params, "severity(high) 미반영"
    assert "abc123" in params, "msg_id 미반영"
    assert conn.committed is True, "commit 미호출"


def test_validate_secret_and_fields():
    secret = "s3cr3t"
    # wrong secret
    ok, code, err = validate_mail_signal("wrong", {"msg_id": "a", "from": "b"}, secret)
    assert ok is False and code == 401
    # missing fields (only date)
    ok, code, err = validate_mail_signal(secret, {"date": "2026-07-26"}, secret)
    assert ok is False and code == 400
    # full valid
    ok, code, err = validate_mail_signal(secret, {"msg_id": "a", "from": "b"}, secret)
    assert ok is True and code == 200


def test_collect_zero_returns_ok_no_analysis():
    conn = _FakeConn(rows=[])
    res = collect_mail_signals(conn)
    assert res == {"count": 0, "high": [], "by_service": {}}, res
    # 0건이면 UPDATE 없음
    updates = [s for s, _ in conn._cur.sql if s.upper().startswith("UPDATE")]
    assert updates == [], "0건인데 UPDATE 발생"


def test_collect_surfaces_high_and_marks_analyzed():
    rows = [
        {"id": 1, "service": "railway", "severity": "high",
         "subject": "Deployment failed", "snippet": "x", "received_at": None},
        {"id": 2, "service": "vercel", "severity": "info",
         "subject": "summary", "snippet": "y", "received_at": None},
    ]
    conn = _FakeConn(rows=rows)
    res = collect_mail_signals(conn)
    assert res["count"] == 2, res
    assert len(res["high"]) == 1, res
    assert res["high"][0]["service"] == "railway", res
    assert "action" in res["high"][0], "action 힌트 누락"
    assert res["by_service"].get("railway") == 1 and res["by_service"].get("vercel") == 1, res
    updates = [s for s, _ in conn._cur.sql if "analyzed_at" in s and s.upper().startswith("UPDATE")]
    assert updates, "analyzed_at 마킹 UPDATE 누락"


if __name__ == "__main__":
    import traceback
    _fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    _p = _f = 0
    for fn in _fns:
        try:
            fn(); print("PASS  " + fn.__name__); _p += 1
        except Exception as e:
            print("FAIL  " + fn.__name__ + ": " + repr(e)); traceback.print_exc(); _f += 1
    print("\n%d passed, %d failed" % (_p, _f))
    sys.exit(1 if _f else 0)
