# -*- coding: utf-8 -*-
"""소스 커버리지 회귀감지 — 순수함수 단위 테스트 (Phase 1 A).

announcements.origin_source 기반 자기교정 임계값 판정(classify_source_row),
접두→tier 매핑(_tier_from_prefix), scraper_monitor 흡수 조기경보
(_early_warnings_from_rows), 뮤트/집계(_assemble_coverage)를 검증한다.

실행: cd backend && python test_coverage_regression_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _c(aw, dq, total=50):
    """classify 헬퍼 — active_weeks/days_quiet/total로 status만 뽑음."""
    from app.services.coverage_checker import classify_source_row
    row = {"origin_source": "scraper:x", "last_seen": "2026-01-01",
           "total_items": total, "active_weeks_90d": aw, "days_quiet": dq}
    return classify_source_row(row)["status"]


# ── 정규 소스 (aw>=4): 자기교정 임계값 경계 ──
def test_weekly_source_green_within_gap():
    # aw=13 → gap=7, yellow 경계=10.5. dq=6.9 → 하한 미만이라 green
    assert _c(13, 6.9) == "green"


def test_weekly_source_yellow_boundary():
    # 1.5×7 = 10.5 경계
    assert _c(13, 10.5) == "yellow"
    assert _c(13, 10.4) == "green"


def test_weekly_source_red_boundary():
    # 3×7 = 21 경계
    assert _c(13, 21.0) == "red"
    assert _c(13, 20.9) == "yellow"


def test_red_threshold_scales_with_gap():
    # aw=9 → gap=ceil(90/9)=10, red 경계=max(30,14)=30
    assert _c(9, 30.0) == "red"
    assert _c(9, 29.9) == "yellow"


def test_monthly_source_not_flagged_at_20d():
    # aw=4 → gap=ceil(90/4)=23, yellow 경계=34.5. dq=20 → green
    # (고정 임계값이었다면 오탐 RED였을 케이스 — 자기교정의 핵심)
    assert _c(4, 20.0) == "green"


def test_monthly_source_red_at_69d():
    # aw=4 → gap=23, red 경계=3×23=69
    assert _c(4, 69.0) == "red"
    assert _c(4, 68.9) == "yellow"


# ── 불규칙 소스 (aw<4) ──
def test_irregular_source_na():
    # aw=2, dq=30 (<60) → 판정보류
    assert _c(2, 30, total=10) == "na"


def test_dormant_source_yellow_bepa_case():
    # BEPA 실측 재현: admin-manual 4건, 110일 침묵 → 휴면 YELLOW
    from app.services.coverage_checker import classify_source_row
    row = {"origin_source": "admin-manual:부산경제진흥원(BEPA)",
           "last_seen": "2026-03-22", "total_items": 4,
           "active_weeks_90d": 1, "days_quiet": 110}
    assert classify_source_row(row)["status"] == "yellow"


def test_dormant_needs_min_items():
    # total=2 (<3) → 테스트/일회성 가능성 → na
    assert _c(1, 200, total=2) == "na"


# ── 접두 → tier ──
def test_tier_from_prefix():
    from app.services.coverage_checker import _tier_from_prefix
    assert _tier_from_prefix("scraper:busan_bepa") == 1
    assert _tier_from_prefix("admin-manual:부산경제진흥원(BEPA)") == 2
    assert _tier_from_prefix("smes24-api") == 3
    assert _tier_from_prefix("weird_value") == 0


# ── scraper_monitor 흡수 조기경보 ──
def test_early_warnings_error_surge():
    from app.services.coverage_checker import _early_warnings_from_rows
    rows = [{"source": "s1", "runs": 4, "ok": 1, "err": 3, "saved_24h": 0}]
    alerts = _early_warnings_from_rows(rows)
    assert any(a["level"] == "critical" and a["source"] == "s1" for a in alerts)
    # err=2 → 경보 없음
    rows2 = [{"source": "s2", "runs": 4, "ok": 2, "err": 2, "saved_24h": 0}]
    assert _early_warnings_from_rows(rows2) == []


def test_early_warnings_zero_saved_is_not_an_alert():
    # items_saved=0(신규 없음)은 정상 — 에러 아니면 경보하지 않는다(오탐 폭주 방지).
    # 소스 침묵은 announcements 기반 회귀감지가 담당.
    from app.services.coverage_checker import _early_warnings_from_rows
    rows = [{"source": "s1", "runs": 3, "ok": 3, "err": 0, "saved_24h": 0}]
    assert _early_warnings_from_rows(rows) == []


def test_early_warnings_all_expired_skip_signature():
    # BEPA류 재발 탐지: 24h 내 found>0인데 saved=0이고 expired가 found를 거의 다 차지
    # → 등록일을 마감일로 오인해 진행중 공고를 전부 '마감'으로 스킵했을 가능성.
    from app.services.coverage_checker import _early_warnings_from_rows
    rows = [{"source": "bepa", "runs": 1, "ok": 1, "err": 0,
             "saved_24h": 0, "found_24h": 8, "expired_24h": 8}]
    alerts = _early_warnings_from_rows(rows)
    assert len(alerts) == 1
    assert alerts[0]["source"] == "bepa"
    assert "마감" in alerts[0]["msg"]


def test_early_warnings_normal_no_new_not_flagged():
    # 정상 '신규 없음': found>0이나 expired 낮음(대부분 이미 DB에 존재) → 경보 없음.
    from app.services.coverage_checker import _early_warnings_from_rows
    rows = [{"source": "monthly", "runs": 1, "ok": 1, "err": 0,
             "saved_24h": 0, "found_24h": 10, "expired_24h": 1}]
    assert _early_warnings_from_rows(rows) == []


def test_early_warnings_expired_but_some_saved_not_flagged():
    # 일부라도 저장됐으면(saved>0) 스크래퍼가 정상 동작 중 → 경보 없음.
    from app.services.coverage_checker import _early_warnings_from_rows
    rows = [{"source": "ok_src", "runs": 1, "ok": 1, "err": 0,
             "saved_24h": 3, "found_24h": 10, "expired_24h": 7}]
    assert _early_warnings_from_rows(rows) == []


# ── 뮤트 / 집계 ──
def test_muted_source_excluded_from_lists():
    from app.services.coverage_checker import _assemble_coverage
    classified = [
        {"origin_source": "scraper:dead", "status": "red", "days_quiet": 40,
         "expected_gap_days": 7, "last_seen": "2026-05-01", "reason": "회귀"},
        {"origin_source": "scraper:live", "status": "green", "days_quiet": 1,
         "expected_gap_days": 7, "last_seen": "2026-07-09", "reason": ""},
    ]
    # 뮤트 없음 → red_list 1건
    r0 = _assemble_coverage(classified, set())
    assert r0["red"] == 1 and len(r0["red_list"]) == 1
    # dead를 뮤트 → red_list 비고 muted=1
    r1 = _assemble_coverage(classified, {"scraper:dead"})
    assert r1["red"] == 0 and r1["red_list"] == [] and r1["muted"] == 1


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
