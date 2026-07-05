# -*- coding: utf-8 -*-
"""Hot이슈 RSS 소스 교체(FABLE 설계 2026-07-05, 기능 3) — 단위 테스트.

죽은 정부 RSS 5개 → 실측 검증된 6개 교체에 수반되는 새 로직:
- _resolve_rss_url: {ENV_KEY} 치환 + 필수 키 없으면 None(skip)  (기업마당 BIZINFO_PORTAL_KEY)
- _count_by_source: 소스별 수집 건수 집계 (5개월 무성과 방치 재발 방지 관측)
- PRESS_SOURCES 불변식: 키는 placeholder(하드코딩 금지), 필수 필드 존재
- _collect_press_releases: 키 미설정 소스 skip, 나머지 계속

네트워크는 유일한 외부 경계라 _fetch_rss_titles만 모킹(치환/skip 로직 자체는 실코드).
실행: cd backend && python test_issue_monitor_rss_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from app.services import issue_monitor as im


# ─────────────────────────────────────────────────────────────
# _resolve_rss_url — 키 치환 + 필수 키 없으면 skip
# ─────────────────────────────────────────────────────────────
def test_resolve_rss_url_no_placeholder_returns_unchanged():
    url = "https://www.mss.go.kr/rss/smba/board/86.do"
    assert im._resolve_rss_url(url) == url


def test_resolve_rss_url_substitutes_env_key():
    os.environ["TEST_RSS_KEY"] = "ABC123"
    try:
        out = im._resolve_rss_url("https://x.go.kr/api?crtfcKey={TEST_RSS_KEY}&searchCnt=20")
        assert out == "https://x.go.kr/api?crtfcKey=ABC123&searchCnt=20"
    finally:
        os.environ.pop("TEST_RSS_KEY", None)


def test_resolve_rss_url_returns_none_when_key_missing():
    os.environ.pop("TEST_RSS_KEY", None)
    assert im._resolve_rss_url("https://x.go.kr/api?crtfcKey={TEST_RSS_KEY}") is None


# ─────────────────────────────────────────────────────────────
# _count_by_source — 소스별 수집 건수 집계 (관측성)
# ─────────────────────────────────────────────────────────────
def test_count_by_source_aggregates():
    items = [
        {"source_name": "중기부", "title": "a"},
        {"source_name": "중기부", "title": "b"},
        {"source_name": "고용부", "title": "c"},
    ]
    assert im._count_by_source(items) == {"중기부": 2, "고용부": 1}


def test_count_by_source_empty():
    assert im._count_by_source([]) == {}


# ─────────────────────────────────────────────────────────────
# PRESS_SOURCES 불변식 — 키 하드코딩 금지, 필수 필드
# ─────────────────────────────────────────────────────────────
def test_press_sources_bizinfo_uses_key_placeholder_not_hardcoded():
    biz = [s for s in im.PRESS_SOURCES if "bizinfo.go.kr" in (s.get("rss") or "")]
    assert biz, "기업마당(bizinfo) 소스가 PRESS_SOURCES에 없음"
    assert "{BIZINFO_PORTAL_KEY}" in biz[0]["rss"], "API 키가 placeholder가 아니라 하드코딩됨"


def test_press_sources_all_have_required_fields():
    assert len(im.PRESS_SOURCES) >= 5
    for s in im.PRESS_SOURCES:
        assert s.get("name"), f"name 누락: {s}"
        assert s.get("rss"), f"rss 누락: {s}"
        assert s.get("category"), f"category 누락: {s}"


def test_press_sources_no_dead_legacy_feeds():
    dead = ("moef.go.kr/rss/moefRss", "smba/rss/smbaRss", "moel.go.kr/rss/rssMain",
            "molit.go.kr/portal/rss", "mohw.go.kr/react/al/rss")
    for s in im.PRESS_SOURCES:
        rss = s.get("rss") or ""
        assert not any(d in rss for d in dead), f"죽은 레거시 피드 잔존: {rss}"


# ─────────────────────────────────────────────────────────────
# _collect_press_releases — 키 없는 소스 skip, 나머지 fetch
# ─────────────────────────────────────────────────────────────
def test_collect_skips_source_when_key_missing():
    orig_key = os.environ.get("BIZINFO_PORTAL_KEY")
    orig_fetch = im._fetch_rss_titles
    orig_sleep = im.time.sleep
    fetched_urls = []

    def fake_fetch(url, max_items=8):
        fetched_urls.append(url)
        return [{"title": "테스트제목입니다", "link": "http://x", "desc": ""}]

    os.environ["BIZINFO_PORTAL_KEY"] = ""  # 키 비움 → bizinfo skip 되어야 함
    im._fetch_rss_titles = fake_fetch
    im.time.sleep = lambda *a, **k: None
    try:
        im._collect_press_releases()
        assert not any("bizinfo.go.kr" in u for u in fetched_urls), \
            "키 미설정인데 bizinfo를 fetch함(skip 실패)"
        assert any("mss.go.kr" in u for u in fetched_urls), \
            "키 불필요 소스(mss)는 fetch되어야 함"
    finally:
        im._fetch_rss_titles = orig_fetch
        im.time.sleep = orig_sleep
        if orig_key is None:
            os.environ.pop("BIZINFO_PORTAL_KEY", None)
        else:
            os.environ["BIZINFO_PORTAL_KEY"] = orig_key


def test_collect_fetches_bizinfo_when_key_present():
    orig_key = os.environ.get("BIZINFO_PORTAL_KEY")
    orig_fetch = im._fetch_rss_titles
    orig_sleep = im.time.sleep
    fetched_urls = []

    def fake_fetch(url, max_items=8):
        fetched_urls.append(url)
        return []

    os.environ["BIZINFO_PORTAL_KEY"] = "DUMMYKEY"
    im._fetch_rss_titles = fake_fetch
    im.time.sleep = lambda *a, **k: None
    try:
        im._collect_press_releases()
        biz = [u for u in fetched_urls if "bizinfo.go.kr" in u]
        assert biz, "키가 있는데 bizinfo를 fetch 안 함"
        assert "DUMMYKEY" in biz[0], "키가 URL에 치환되지 않음"
        assert "{BIZINFO_PORTAL_KEY}" not in biz[0], "placeholder가 그대로 남음"
    finally:
        im._fetch_rss_titles = orig_fetch
        im.time.sleep = orig_sleep
        if orig_key is None:
            os.environ.pop("BIZINFO_PORTAL_KEY", None)
        else:
            os.environ["BIZINFO_PORTAL_KEY"] = orig_key


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
