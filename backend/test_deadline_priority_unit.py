# -*- coding: utf-8 -*-
"""마감 판정 우선순위 역전(FABLE 진단 2026-07-05, 문제2 근본) — 단위 테스트.

버그: _detect_deadline_from_analysis가 본문에 '상시/수시/예산소진' 단어만 있으면
날짜 추출을 시도하지도 않고 ongoing 확정(doc_analysis_service.py:1220-1221).
'상시 문의' 같은 부수적 단어에 실제 접수마감일이 덮여 ongoing+과거날짜 누수 유발.

수정: 날짜 추출을 먼저, 상시 키워드는 '날짜가 전혀 없을 때만' ongoing 판정.
추가: _update_analysis_status가 기존 deadline_date 있는 행을 ongoing으로 덮지 않도록 가드.

실행: cd backend && python test_deadline_priority_unit.py
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

from app.services.doc_analysis_service import _detect_deadline_from_analysis
import app.services.doc_analysis_service as doc


def test_detect_deadline_date_wins_over_ongoing_keyword():
    """본문에 '상시' 부수단어가 있어도 실제 접수마감일이 있으면 fixed 우선."""
    fy = datetime.date.today().year + 1  # 항상 미래
    text = f"상시 문의 가능합니다. 신청기간: {fy}년 8월 1일 ~ 8월 31일까지 접수."
    result = _detect_deadline_from_analysis({}, text)
    assert result == ("fixed", f"{fy}-08-31"), \
        f"날짜가 상시 키워드에 밀림(ongoing으로 뒤집힘): {result}"


def test_detect_ongoing_only_when_no_date():
    """날짜가 전혀 없고 상시 키워드만 있으면 ongoing."""
    text = "예산 소진 시까지 상시 모집합니다. 관심 있는 분은 문의 바랍니다."
    result = _detect_deadline_from_analysis({}, text)
    assert result == ("ongoing", None), f"상시 판정 실패: {result}"


def test_detect_unknown_when_no_date_no_ongoing():
    """날짜도 상시 키워드도 없으면 unknown."""
    text = "지원 대상은 중소기업입니다. 자세한 내용은 첨부파일을 참조하세요."
    result = _detect_deadline_from_analysis({}, text)
    assert result == ("unknown", None), f"unknown 판정 실패: {result}"


def test_update_status_guards_ongoing_overwrite():
    """_update_analysis_status가 기존 deadline_date 있는 행을 ongoing으로 덮지 않아야 함."""
    src = inspect.getsource(doc._update_analysis_status)
    assert "deadline_date IS NOT NULL THEN deadline_type" in src, \
        "ongoing이 기존 마감일 행의 type을 덮는 것을 막는 가드 없음"


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
