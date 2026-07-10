# -*- coding: utf-8 -*-
"""소스 진단자 — 순수함수 단위 테스트. 실행: cd backend && python test_source_diagnoser_unit.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass


def _t(http, links, body):
    from app.services.orchestrator.source_diagnoser import classify_diagnosis
    return classify_diagnosis(http, links, body)["diag_type"]


def test_unreachable_on_none_status():
    assert _t(None, 0, 0) == "unreachable"

def test_unreachable_on_4xx_5xx():
    assert _t(404, 10, 5000) == "unreachable"
    assert _t(500, 10, 5000) == "unreachable"

def test_extract_fail_when_many_links():
    # 200 + 링크 5개 이상 → 추출 실패(링크는 있는데 못 뽑음)
    assert _t(200, 5, 5000) == "extract_fail"
    assert _t(200, 4, 5000) != "extract_fail"

def test_js_only_when_no_links_and_short_body():
    assert _t(200, 0, 799) == "js_only"
    assert _t(200, 4, 799) == "js_only"

def test_wrong_or_empty_when_no_links_and_normal_body():
    assert _t(200, 0, 800) == "wrong_or_empty"
    assert _t(200, 4, 5000) == "wrong_or_empty"

def test_returns_suggested_action():
    from app.services.orchestrator.source_diagnoser import classify_diagnosis
    r = classify_diagnosis(200, 0, 800)
    assert r["diag_type"] == "wrong_or_empty"
    assert isinstance(r["suggested_action"], str) and len(r["suggested_action"]) > 3


from bs4 import BeautifulSoup

_FIX_MANY = """<table><tbody>
  <tr><td><a href="/board/view.do?no=1&idx=10">지원사업 A 모집</a></td></tr>
  <tr><td><a href="/board/view.do?no=1&idx=11">지원사업 B 공고</a></td></tr>
  <tr><td><a href="/board/view.do?no=1&idx=12">지원사업 C 모집</a></td></tr>
  <tr><td><a href="/board/view.do?no=1&idx=13">지원사업 D 공고</a></td></tr>
  <tr><td><a href="/board/view.do?no=1&idx=14">지원사업 E 모집</a></td></tr>
  <tr><td><a href="/about">기관소개</a></td></tr>
</tbody></table>"""

_FIX_NONE = """<div><a href="/about">기관소개</a><a href="/login">로그인</a></div>"""

def test_count_article_links_counts_only_detail_links():
    from app.services.orchestrator.source_diagnoser import count_article_links
    assert count_article_links(BeautifulSoup(_FIX_MANY, "html.parser")) == 5
    assert count_article_links(BeautifulSoup(_FIX_NONE, "html.parser")) == 0

def test_visible_text_len_excludes_scripts():
    from app.services.orchestrator.source_diagnoser import visible_text_len
    html = "<html><script>var x=123456789012345;</script><body>짧은본문</body></html>"
    n = visible_text_len(BeautifulSoup(html, "html.parser"))
    assert n == len("짧은본문")


def test_search_keys_extracts_institution_names():
    from app.services.orchestrator.source_diagnoser import _search_keys
    assert _search_keys("admin-manual:부산경제진흥원(BEPA)") == ["부산경제진흥원", "BEPA"]
    assert _search_keys("admin-manual:안양시 기업지원") == ["안양시"]
    assert _search_keys("admin-manual:고용24(고용노동부)") == ["고용24", "고용노동부"]
    # 접두 scraper: 도 벗김
    assert _search_keys("scraper:jejutp") == ["jejutp"]


if __name__ == "__main__":
    import traceback
    _fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    _p = _f = 0
    for _fn in _fns:
        try:
            _fn(); print("PASS  " + _fn.__name__); _p += 1
        except Exception as _e:
            print("FAIL  " + _fn.__name__ + ": " + repr(_e)); traceback.print_exc(); _f += 1
    print("\n%d passed, %d failed" % (_p, _f)); sys.exit(1 if _f else 0)
