# -*- coding: utf-8 -*-
"""부산경제진흥원(BEPA) 스크래퍼 — 순수 파서 단위 테스트 (Phase 1 C).

_parse_board(soup, board, seen) 검증. 픽스처는 실측된 bepa.kr 게시판 뷰
링크 구조(view.do?no=<board>&idx=<idx>&view=view&state=<ing|end|stay>)를 반영.

실행: cd backend && python test_bepa_scraper_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from bs4 import BeautifulSoup

# 실측 구조 기반 픽스처 — 진행중(ing) 2 · 마감(end) 1 · 예정(stay) 1 · 채용(exclude) 1
_FIX_1502 = """
<table><tbody>
  <tr><td><a href="/kor/view.do?no=1502&idx=19289&view=view&state=ing">2026년 소상공인 경영지원 사업 공고</a></td><td>2026.12.11</td></tr>
  <tr><td><a href="/kor/view.do?no=1502&idx=19285&view=view&state=ing">부산 창업기업 성장지원 모집</a></td><td>2026.11.30</td></tr>
  <tr><td><a href="/kor/view.do?no=1502&idx=19245&view=view&state=end">마감된 지원사업 공고</a></td><td>2025.11.13</td></tr>
  <tr><td><a href="/kor/view.do?no=1502&idx=19000&view=view&state=ing">경영지원단 직원 채용 공고</a></td><td>2026.10.01</td></tr>
</tbody></table>
"""

# 1505 게시판 — idx 19289는 1502와 중복(게시판 간 dedup 확인용) + 신규 stay 1
_FIX_1505 = """
<table><tbody>
  <tr><td><a href="/kor/view.do?no=1505&idx=19289&view=view&state=ing">2026년 소상공인 경영지원 사업 공고</a></td><td>2026.12.11</td></tr>
  <tr><td><a href="/kor/view.do?no=1505&idx=19284&view=view&state=stay">중소기업 자금지원 접수예정</a></td><td>2026.12.20</td></tr>
</tbody></table>
"""


def _scraper():
    from app.services.scrapers.tier1.sido_scrapers import BepaScraper
    return BepaScraper()


def test_parse_extracts_idx_and_title():
    s = _scraper()
    out = s._parse_board(BeautifulSoup(_FIX_1502, "html.parser"), 1502, set())
    titles = [o["title"] for o in out]
    assert "2026년 소상공인 경영지원 사업 공고" in titles
    # origin_url 정규형: state 파라미터 미포함
    hit = next(o for o in out if o["title"].startswith("2026년 소상공인"))
    assert hit["origin_url"] == "https://www.bepa.kr/kor/view.do?no=1502&idx=19289&view=view"
    assert "state=" not in hit["origin_url"]
    assert hit["region"] == "부산"


def test_parse_skips_state_end():
    s = _scraper()
    out = s._parse_board(BeautifulSoup(_FIX_1502, "html.parser"), 1502, set())
    assert all("마감된" not in o["title"] for o in out)


def test_parse_keeps_state_stay():
    s = _scraper()
    out = s._parse_board(BeautifulSoup(_FIX_1505, "html.parser"), 1505, set())
    assert any("접수예정" in o["title"] for o in out)


def test_parse_skips_exclude_keywords():
    s = _scraper()
    out = s._parse_board(BeautifulSoup(_FIX_1502, "html.parser"), 1502, set())
    assert all("채용" not in o["title"] for o in out)


def test_parse_dedups_idx_across_boards():
    s = _scraper()
    seen = set()
    out1 = s._parse_board(BeautifulSoup(_FIX_1502, "html.parser"), 1502, seen)
    out2 = s._parse_board(BeautifulSoup(_FIX_1505, "html.parser"), 1505, seen)
    # idx 19289는 1502에서 잡혔으므로 1505에선 제외
    assert not any("19289" in o["origin_url"] for o in out2)
    # ing 2건(19289,19285) 중 채용·마감 제외 → 1502에서 2건
    assert len(out1) == 2


def test_parse_extracts_deadline():
    s = _scraper()
    out = s._parse_board(BeautifulSoup(_FIX_1502, "html.parser"), 1502, set())
    hit = next(o for o in out if o["title"].startswith("2026년 소상공인"))
    assert hit["deadline_date"] == "2026-12-11"


def test_fetch_stops_on_repeated_page(monkeypatch=None):
    # 같은 HTML 반복 반환 → 페이지 루프가 무한 수집하지 않음
    import app.services.scrapers.tier1.sido_scrapers as mod
    orig = mod._get
    mod._get = lambda url, verify=True, **kw: BeautifulSoup(_FIX_1502, "html.parser")
    try:
        items = mod.BepaScraper().fetch_items()
    finally:
        mod._get = orig
    # 중복 idx는 seen으로 제거 → 유한 건수(채용·마감 제외한 2건 수준)
    assert 0 < len(items) <= 4


def test_registry_contains_busan_bepa_and_keeps_busan_city():
    import app.services.scrapers.tier1._load_all  # noqa: F401 (레지스트리 적재)
    from app.services.scrapers.tier1.base import SCRAPER_REGISTRY
    names = {s.name for s in SCRAPER_REGISTRY}
    assert "busan_bepa" in names          # 신규 활성화
    assert "busan_city" in names          # 부산시청 스크래퍼 비파괴


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
