# -*- coding: utf-8 -*-
"""ongoing 재검사 보강 — enrich_pending_deadlines가 'ongoing'도 재검사해
full_text에 명시적 접수마감일이 있으면 fixed(날짜)로 업그레이드하는지 단위 테스트.

버그: 배치 WHERE가 (deadline_type IS NULL OR 'unknown')만 처리 → 'ongoing'은 영영
재검사 안 됨. 초기 상시 오분류(원문에 접수기간 있는데 상시로 잡힌 것)가 고착.
수정: WHERE에 'ongoing' 포함 + 접수마감 발견 시 fixed 업그레이드(기존 루프 그대로).

실행: cd backend && python test_deadline_ongoing_recheck_unit.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass
from app.services.deadline_enricher import enrich_pending_deadlines


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.selected_sql = None
        self.updates = []          # (sql, params)
    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.strip().upper().startswith("SELECT"):
            self.selected_sql = s
        else:
            self.updates.append((s, params))
    def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, rows):
        self._cur = FakeCursor(rows)
        self.committed = False
    def cursor(self):
        return self._cur
    def commit(self):
        self.committed = True


_LEGIT_SANGSI = "연중 상시 모집합니다. " * 10  # >120자, 접수마감 없음


def test_select_includes_ongoing():
    """배치 SELECT의 deadline_type 필터가 'ongoing'을 포함해야 함."""
    conn = FakeConn([])
    enrich_pending_deadlines(conn)
    sql = conn._cur.selected_sql or ""
    assert "ongoing" in sql, "enrich 배치가 'ongoing'을 재검사 대상에 포함하지 않음"


def test_ongoing_with_deadline_upgraded_to_fixed():
    """ongoing인데 full_text에 접수기간 마감일이 있으면 fixed(날짜)로 UPDATE."""
    rows = [{"id": 111, "ft": "○ 접수기간 : 2026.2.19 ~ 2026.2.26 접수 바랍니다. " * 5}]
    conn = FakeConn(rows)
    res = enrich_pending_deadlines(conn)
    assert res["fixed"] == 1, f"fixed 업그레이드 안 됨: {res}"
    # UPDATE에 fixed + 종료일(2026-02-26)이 들어갔는지
    joined = " | ".join(f"{s} {p}" for s, p in conn._cur.updates)
    assert "deadline_type='fixed'" in joined.replace(" ", "").replace("'fixed'", "'fixed'") or "fixed" in joined
    assert "2026-02-26" in joined, f"종료일 미반영: {joined}"


def test_legit_sangsi_stays_ongoing():
    """접수마감 없는 진짜 상시는 fixed로 바뀌면 안 됨(유지)."""
    rows = [{"id": 222, "ft": _LEGIT_SANGSI}]
    conn = FakeConn(rows)
    res = enrich_pending_deadlines(conn)
    assert res["fixed"] == 0, f"진짜 상시가 잘못 fixed 전환됨: {res}"
    assert res["ongoing"] == 1, f"상시 유지 실패: {res}"


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
