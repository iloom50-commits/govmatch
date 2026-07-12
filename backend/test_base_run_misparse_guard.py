# -*- coding: utf-8 -*-
"""base.run() 배치 안전망 — 등록일→마감일 오인 시 영구 드롭 방지 (근본개선).

핵심 원칙: list-scrape는 자기가 추측한 마감일로 공고를 영구 드롭할 수 없다.
"found>0인데 저장 0 + 거의 전량 만료" = 마감 오인 신호 → 드롭 대신 마감미상(None)
으로 저장하여 enricher가 실제 마감을 보강하게 한다.

실행: cd backend && python test_base_run_misparse_guard.py
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.scrapers.tier1.base import BaseScraper


class _FakeCursor:
    def execute(self, sql, params=None):
        self._last = sql
    def fetchone(self):
        # scraper_runs INSERT ... RETURNING id
        return {"id": 1}
    def close(self):
        pass


class _FakeConn:
    def cursor(self, *a, **k):
        return _FakeCursor()
    def commit(self):
        pass
    def rollback(self):
        pass


class _FakeScraper(BaseScraper):
    """_save_item을 인메모리 기록으로 대체 — 실제 DB 없이 run() 흐름만 검증."""
    name = "fake_test"

    def __init__(self, items):
        self._items = items
        self.saved = []

    def fetch_items(self):
        return self._items

    def _save_item(self, item, db_conn):
        self.saved.append(dict(item))
        return True


def _past():
    return (datetime.date.today() - datetime.timedelta(days=90)).isoformat()


def _future():
    return (datetime.date.today() + datetime.timedelta(days=30)).isoformat()


def _item(i, deadline):
    return {"title": f"공고{i}", "origin_url": f"https://x.test/{i}", "deadline_date": deadline}


def test_all_expired_batch_is_rescued_with_null_deadline():
    # 5건 전부 과거 마감(=등록일 오인 의심) → 드롭이 아니라 마감미상으로 전량 저장돼야 한다.
    items = [_item(i, _past()) for i in range(5)]
    s = _FakeScraper(items)
    res = s.run(_FakeConn())
    assert res["items_saved"] == 5, res
    assert res["items_expired"] == 0, res
    assert len(s.saved) == 5, s.saved
    assert all(x["deadline_date"] is None for x in s.saved), \
        [x["deadline_date"] for x in s.saved]


def test_normal_batch_still_drops_genuinely_expired():
    # 신선건 8 + 진짜 만료 2 → 만료 2건은 그대로 드롭(과잉발동 없음), 신선건은 마감 유지.
    items = [_item(i, _future()) for i in range(8)] + [_item(8, _past()), _item(9, _past())]
    s = _FakeScraper(items)
    res = s.run(_FakeConn())
    assert res["items_saved"] == 8, res
    assert res["items_expired"] == 2, res
    assert all(x["deadline_date"] is not None for x in s.saved), s.saved


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
