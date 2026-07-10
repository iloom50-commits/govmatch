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
