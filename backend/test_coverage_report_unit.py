# -*- coding: utf-8 -*-
"""AI COO 메일 커버리지 섹션 — 순수함수 단위 테스트 (Phase 1 B).

_build_coverage_text / _build_coverage_html 렌더링 + send_report 빌더의
하위호환(coverage 인자 없이도 기존과 동일 동작)을 검증한다.

실행: cd backend && python test_coverage_report_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


_RED_COVERAGE = {
    "total_sources": 30, "green": 27, "yellow": 2, "red": 1, "na": 0, "muted": 0,
    "red_list": [{"source": "scraper:busan_bepa", "days_quiet": 40,
                  "expected_gap_days": 7, "last_seen": "2026-05-01",
                  "reason": "평시 7일 주기 3배 초과"}],
    "yellow_list": [], "scraper_alerts": [],
}


def test_coverage_text_red_lists_source_and_days():
    from app.services.orchestrator.reporter import _build_coverage_text
    txt = _build_coverage_text(_RED_COVERAGE)
    assert "수집 소스 커버리지" in txt
    assert "scraper:busan_bepa" in txt
    assert "40" in txt          # 40일째
    assert "7" in txt           # 평시 주기


def test_coverage_text_all_green():
    from app.services.orchestrator.reporter import _build_coverage_text
    cov = {"total_sources": 30, "green": 30, "yellow": 0, "red": 0, "na": 0,
           "muted": 0, "red_list": [], "yellow_list": [], "scraper_alerts": []}
    txt = _build_coverage_text(cov)
    assert "회귀 없음" in txt


def test_coverage_text_empty_on_none_or_error():
    from app.services.orchestrator.reporter import _build_coverage_text
    assert _build_coverage_text({}) == ""
    assert _build_coverage_text({"error": "x"}) == ""
    assert _build_coverage_text(None) == ""


def test_coverage_html_box_color():
    from app.services.orchestrator.reporter import _build_coverage_html
    # red → 빨강 박스
    assert "#fef2f2" in _build_coverage_html(_RED_COVERAGE)
    # yellow만 → 호박 박스
    yellow_only = {"total_sources": 30, "green": 28, "yellow": 2, "red": 0,
                   "na": 0, "muted": 0, "red_list": [],
                   "yellow_list": [{"source": "s", "days_quiet": 12,
                                    "expected_gap_days": 7, "reason": "주의"}],
                   "scraper_alerts": []}
    assert "#fffbeb" in _build_coverage_html(yellow_only)
    # 전부 정상 → 초록 박스
    all_green = {"total_sources": 30, "green": 30, "yellow": 0, "red": 0,
                 "na": 0, "muted": 0, "red_list": [], "yellow_list": [],
                 "scraper_alerts": []}
    assert "#f0fdf4" in _build_coverage_html(all_green)


def test_coverage_html_empty_on_none_or_error():
    from app.services.orchestrator.reporter import _build_coverage_html
    assert _build_coverage_html({}) == ""
    assert _build_coverage_html({"error": "x"}) == ""
    assert _build_coverage_html(None) == ""


# ── 하위호환: coverage 인자 없이 호출 ──
def test_report_text_backward_compat():
    from app.services.orchestrator.reporter import _build_report_text
    m = {"users_total": 10}
    # coverage 인자 없이 (기존 호출부와 동일) — 예외 없이 렌더
    txt = _build_report_text(m, {}, {}, {}, {})
    assert "GovMatch 일일 현황" in txt


def test_report_html_backward_compat():
    from app.services.orchestrator.reporter import _build_report_html
    html = _build_report_html({"users_total": 10}, {}, {}, {}, {})
    assert "GovMatch 일일 현황" in html


def test_report_text_includes_coverage_after_alert():
    from app.services.orchestrator.reporter import _build_report_text
    txt = _build_report_text({"users_total": 10}, {}, {}, {}, {}, _RED_COVERAGE)
    assert "수집 소스 커버리지" in txt
    # 시스템 경보 섹션보다 뒤, 구글 검색 유입보다 앞
    assert txt.index("수집 소스 커버리지") < txt.index("구글 검색 유입")


_REPAIR_COV = {
    "total_sources": 30, "green": 27, "yellow": 3, "red": 0, "na": 0, "muted": 0,
    "red_list": [], "yellow_list": [], "scraper_alerts": [],
    "repair_list": [
        {"source": "admin-manual:부산경제진흥원(BEPA)", "diag_type": "wrong_or_empty",
         "suggested_action": "엉뚱한 URL/빈 게시판 — 올바른 게시판 URL 확인", "diag_at": "2026-07-13"},
    ],
}

def test_coverage_text_shows_repair():
    from app.services.orchestrator.reporter import _build_coverage_text
    txt = _build_coverage_text(_REPAIR_COV)
    assert "수리 필요" in txt
    assert "부산경제진흥원" in txt
    assert "올바른 게시판" in txt

def test_coverage_html_shows_repair():
    from app.services.orchestrator.reporter import _build_coverage_html
    html = _build_coverage_html(_REPAIR_COV)
    assert "수리 필요" in html and "부산경제진흥원" in html

_REDUNDANT_COV = {
    "total_sources": 30, "green": 27, "yellow": 0, "red": 0, "na": 0, "muted": 0,
    "red_list": [], "yellow_list": [], "scraper_alerts": [], "repair_list": [],
    "redundant_list": [
        {"source": "admin-manual:제주테크노파크", "covered_by": ["scraper:jejutp"]},
    ],
}

def test_coverage_text_shows_redundant_mute_candidates():
    from app.services.orchestrator.reporter import _build_coverage_text
    txt = _build_coverage_text(_REDUNDANT_COV)
    assert "뮤트 후보" in txt
    assert "제주테크노파크" in txt and "scraper:jejutp" in txt

def test_coverage_html_shows_redundant():
    from app.services.orchestrator.reporter import _build_coverage_html
    html = _build_coverage_html(_REDUNDANT_COV)
    assert "뮤트 후보" in html and "제주테크노파크" in html


def test_coverage_text_no_repair_key_ok():
    # repair_list 없어도 기존 동작(회귀 없음) 유지
    from app.services.orchestrator.reporter import _build_coverage_text
    cov = {"total_sources": 10, "green": 10, "yellow": 0, "red": 0, "na": 0,
           "muted": 0, "red_list": [], "yellow_list": [], "scraper_alerts": []}
    assert "회귀 없음" in _build_coverage_text(cov)


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
