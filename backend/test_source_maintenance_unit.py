# -*- coding: utf-8 -*-
"""소스 정비 파이프라인 편입(FABLE 설계 2026-07-05, 기능 2) — 단위 테스트.

구 _daily_sync_loop(죽은 코드)에 방치된 _deactivate_dead_urls/_discover_new_sources를
run_daily_pipeline에 편입하며 수반되는 변경:
- 두 함수가 처리 건수(int) 반환 (기존 None → _log_step 건수 기록용)
- _discover 재등록 버그 수정: 기등록 도메인 조회에서 is_active=1 필터 제거
  (비활성화된 죽은 도메인이 "미등록"으로 보여 다른 URL로 재등록되던 버그)
- step_2c_source_maintenance: 비활성화는 매일 / 발견은 주1회(월요일)

DB 접근(get_db_connection)은 DI가 아니라 내부 호출이라 모킹이 불가피(유일 외부 경계).
실행: cd backend && python test_source_maintenance_unit.py
"""
import os
import sys
import inspect
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import app.main as m


# ─────────────────────────────────────────────────────────────
# 가짜 DB (get_db_connection 대체 — 유일한 외부 경계)
# ─────────────────────────────────────────────────────────────
class FakeCursor:
    def __init__(self, registered=None, announcements=None, deactivated=None):
        self._registered = registered or []
        self._announcements = announcements or []
        self._deactivated = deactivated or []
        self._result = []
        self.rowcount = 0
        self.inserts = []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SELECT url FROM admin_urls"):
            self._result = self._registered
        elif "FROM announcements" in s:
            self._result = self._announcements
        elif s.startswith("UPDATE admin_urls"):
            self._result = self._deactivated
        elif s.startswith("INSERT INTO admin_urls"):
            self.inserts.append(params)
            self.rowcount = 1
        else:
            self._result = []

    def fetchall(self):
        return self._result


class FakeConn:
    def __init__(self, cur):
        self._cur = cur

    def cursor(self):
        return self._cur

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _with_fake_db(fake_cursor, fn):
    orig = m.get_db_connection
    m.get_db_connection = lambda: FakeConn(fake_cursor)
    try:
        return fn()
    finally:
        m.get_db_connection = orig


# ─────────────────────────────────────────────────────────────
# 반환값 — 기존 None → 처리 건수(int)
# ─────────────────────────────────────────────────────────────
def test_deactivate_returns_count_of_rows():
    fake = FakeCursor(deactivated=[
        {"id": 1, "source_name": "a", "url": "u1", "fail_count": 6},
        {"id": 2, "source_name": "b", "url": "u2", "fail_count": 8},
    ])
    assert _with_fake_db(fake, m._deactivate_dead_urls) == 2


def test_deactivate_returns_zero_when_none_dead():
    fake = FakeCursor(deactivated=[])
    assert _with_fake_db(fake, m._deactivate_dead_urls) == 0


def test_discover_returns_count_of_registered():
    fake = FakeCursor(
        registered=[],
        announcements=[{"origin_url": "https://www.newbiz.kr/notice", "cnt": 5}],
    )
    n = _with_fake_db(fake, m._discover_new_sources)
    assert n == 1, f"신규 등록 건수 반환 실패: {n}"
    assert fake.inserts, "INSERT가 발생하지 않음"


# ─────────────────────────────────────────────────────────────
# 재등록 버그 — 기등록 도메인 조회가 비활성도 포함해야 함
# ─────────────────────────────────────────────────────────────
def test_discover_registered_query_includes_inactive_domains():
    src = inspect.getsource(m._discover_new_sources)
    assert "SELECT url FROM admin_urls WHERE is_active = 1" not in src, \
        "기등록 도메인 조회가 활성만 봐서 비활성 죽은 도메인을 재등록함(버그 잔존)"
    assert "SELECT url FROM admin_urls" in src, "기등록 도메인 조회 자체가 사라짐"


# ─────────────────────────────────────────────────────────────
# step_2c_source_maintenance — 비활성화 매일 / 발견 주1(월)
# ─────────────────────────────────────────────────────────────
def _patch_maint(deact_ret, disc_ret, disc_calls):
    orig_de, orig_di = m._deactivate_dead_urls, m._discover_new_sources
    m._deactivate_dead_urls = lambda: deact_ret
    m._discover_new_sources = lambda: (disc_calls.append(1) or disc_ret)
    return orig_de, orig_di


def test_step_2c_skips_discover_on_non_monday():
    from app.services.patrol.daily_pipeline import step_2c_source_maintenance
    disc_calls = []
    orig_de, orig_di = _patch_maint(3, 9, disc_calls)
    try:
        r = step_2c_source_maintenance(today=datetime.date(2024, 1, 2))  # 화요일
        assert r["deactivated"] == 3
        assert not disc_calls, "비월요일에 discover가 실행됨"
        assert "skip" in str(r.get("discover", "")), "discover skip 표기 없음"
    finally:
        m._deactivate_dead_urls, m._discover_new_sources = orig_de, orig_di


def test_step_2c_runs_discover_on_monday():
    from app.services.patrol.daily_pipeline import step_2c_source_maintenance
    disc_calls = []
    orig_de, orig_di = _patch_maint(0, 9, disc_calls)
    try:
        r = step_2c_source_maintenance(today=datetime.date(2024, 1, 1))  # 월요일
        assert r["deactivated"] == 0
        assert r.get("discovered") == 9, "월요일에 discover 미실행"
        assert len(disc_calls) == 1
    finally:
        m._deactivate_dead_urls, m._discover_new_sources = orig_de, orig_di


# ─────────────────────────────────────────────────────────────
# 스크립트 러너
# ─────────────────────────────────────────────────────────────
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
