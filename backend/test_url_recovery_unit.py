# -*- coding: utf-8 -*-
"""URL 자동복구 run_batch 배선(FABLE 설계 2026-07-05, 기능 1) — 단위 테스트.

run_all에만 있던 _try_recover_url 복구를 일일 경로(run_batch)에 이관.
테스트 가능성을 위해 결정 로직을 추출:
- _select_recovery_targets(순수): 도메인 중복 제거 + 7일 rate-limit + 상한(MAX_URL_RECOVERY)
- AdminScraper._run_recovery_pass(async, 의존성 주입): 선별→UPDATE(last_recovery_attempt)→_try_recover_url→성공집계, 예외격리

Playwright/실DB는 주입으로 대체(불가피 경계). _try_recover_url은 가짜 async로 교체.
실행: cd backend && python test_url_recovery_unit.py
"""
import os
import sys
import asyncio
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import app.services.admin_scraper as asm


def _cand(cid, url, lra=None, fail=3):
    return {"id": cid, "url": url, "source_name": f"src{cid}",
            "fail_count": fail, "last_recovery_attempt": lra}


# ─────────────────────────────────────────────────────────────
# _select_recovery_targets — 순수 선별 로직
# ─────────────────────────────────────────────────────────────
def test_select_dedups_same_domain():
    c = [_cand(1, "https://a.kr/x"), _cand(2, "https://a.kr/y"), _cand(3, "https://b.kr/z")]
    sel = asm._select_recovery_targets(c, max_rec=5, now=datetime.now())
    assert [x["id"] for x in sel] == [1, 3], "같은 도메인 중복 시도 미제거"


def test_select_respects_max():
    c = [_cand(i, f"https://d{i}.kr/x") for i in range(1, 6)]
    sel = asm._select_recovery_targets(c, max_rec=3, now=datetime.now())
    assert len(sel) == 3, "MAX_URL_RECOVERY 상한 미적용"


def test_select_skips_recent_attempt():
    now = datetime(2026, 7, 5, 12, 0, 0)
    c = [_cand(1, "https://a.kr/x", lra=now - timedelta(days=3)),   # 최근 → skip
         _cand(2, "https://b.kr/y", lra=now - timedelta(days=8))]   # 8일 전 → 시도
    sel = asm._select_recovery_targets(c, max_rec=5, now=now)
    assert [x["id"] for x in sel] == [2], "7일 rate-limit 미적용"


def test_select_includes_when_no_prior_attempt():
    c = [_cand(1, "https://a.kr/x", lra=None)]
    sel = asm._select_recovery_targets(c, max_rec=5, now=datetime.now())
    assert len(sel) == 1, "이력 없는 URL이 선별 안 됨"


def test_select_empty():
    assert asm._select_recovery_targets([], 3, datetime.now()) == []


# ─────────────────────────────────────────────────────────────
# 가짜 DB (복구 패스의 UPDATE/commit/rollback 경계)
# ─────────────────────────────────────────────────────────────
class _FakeCur:
    def __init__(self):
        self.updated_ids = []

    def execute(self, sql, params=None):
        if sql.strip().upper().startswith("UPDATE") and params:
            self.updated_ids.append(params[-1])

    def fetchone(self):
        return None


class _FakeConn:
    def __init__(self, cur):
        self._cur = cur
        self.rolled_back = False
        self.committed = 0

    def cursor(self):
        return self._cur

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


# ─────────────────────────────────────────────────────────────
# _run_recovery_pass — 선별→UPDATE→복구호출→집계, 예외격리
# ─────────────────────────────────────────────────────────────
def test_recovery_pass_counts_successes_and_updates_attempt():
    scraper = asm.AdminScraper()

    async def fake_recover(target, browser, cursor, conn):
        return target["id"] == 1   # id1만 복구 성공

    scraper._try_recover_url = fake_recover
    cur = _FakeCur()
    conn = _FakeConn(cur)
    cands = [_cand(1, "https://a.kr/x"), _cand(2, "https://b.kr/y")]
    r = asyncio.run(scraper._run_recovery_pass(cands, None, cur, conn, 5, datetime.now()))
    assert r["attempted"] == 2, f"시도 수 오류: {r}"
    assert r["recovered"] == 1, f"복구 성공 집계 오류: {r}"
    assert cur.updated_ids == [1, 2], f"last_recovery_attempt UPDATE 누락: {cur.updated_ids}"


def test_recovery_pass_isolates_exception():
    scraper = asm.AdminScraper()

    async def boom(target, browser, cursor, conn):
        if target["id"] == 1:
            raise RuntimeError("복구 중 예외")
        return True

    scraper._try_recover_url = boom
    cur = _FakeCur()
    conn = _FakeConn(cur)
    cands = [_cand(1, "https://a.kr/x"), _cand(2, "https://b.kr/y")]
    r = asyncio.run(scraper._run_recovery_pass(cands, None, cur, conn, 5, datetime.now()))
    assert r["recovered"] == 1, "예외 뒤 다음 후보가 계속되지 않음"
    assert conn.rolled_back, "예외 시 rollback 미수행"


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
