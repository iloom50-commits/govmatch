# -*- coding: utf-8 -*-
"""하드코딩 유효성 필터 치환(FABLE 근본설계 2026-07-05, 문제2 P1-2) - 단위 테스트.

누수의 근본: 사용자 대면 엔드포인트가 valid_announcement_where() 대신 제각각의
하드코딩 필터를 써서, 마감 지난 'ongoing' 공고가 통과(만료 상시 누수)하고
KST 기준도 아님. 특히 /api/trending 주 JOIN 쿼리는 유효성 필터가 아예 없음.

치환 대상(사용자 대면):
- /api/public/match-teaser: _valid 하드코딩 -> valid_announcement_where()
- /api/trending: 주 JOIN + 폴백 3곳 -> valid_announcement_where()

실행: cd backend && python test_hardcoded_filter_replacement_unit.py
"""
import os
import sys
import inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import app.main as m


def test_match_teaser_uses_helper():
    src = inspect.getsource(m.api_public_match_teaser)
    assert "valid_announcement_where(" in src, "match-teaser가 공용 유효필터 헬퍼 미사용"
    assert "deadline_date >= CURRENT_DATE OR deadline_type='ongoing'" not in src, \
        "match-teaser에 무가드 ongoing 리터럴 잔존(마감 지난 상시 누수)"


def test_trending_uses_helper_everywhere():
    src = inspect.getsource(m.api_trending)
    n = src.count("valid_announcement_where(")
    assert n >= 4, "trending 유효필터 치환 부족: %d곳(주 JOIN + 폴백3 = 4 기대)" % n
    assert "deadline_type = 'ongoing' OR (deadline_type = 'fixed'" not in src, \
        "trending에 무가드 ongoing 리터럴 잔존(마감 지난 상시 누수)"


def test_helper_guards_expired_ongoing():
    """치환의 핵심 속성: 헬퍼가 ongoing + 과거날짜를 배제한다(누수 차단)."""
    sql = m.valid_announcement_where()
    assert "deadline_type = 'ongoing' AND (" in sql, "ongoing 분기에 날짜 가드 없음"
    # ongoing은 날짜 NULL이거나 미래(>= 오늘)만 통과 - 과거 상시 누수 차단
    assert "deadline_date IS NULL OR" in sql, "ongoing NULL/미래 가드 없음"


def test_no_hardcoded_valid_filter_in_admin_batches():
    """관리자 배치 8곳 포함 — main.py 전체에 무가드 ongoing 유효필터가 없어야(P1-2-admin)."""
    src = inspect.getsource(m)
    # alias 'a.' 버전(관리자 분석 배치)의 무가드 리터럴 잔존 금지
    assert "deadline_type = 'ongoing' OR (a.deadline_type = 'fixed'" not in src, \
        "관리자 배치에 무가드 ongoing 유효필터 잔존(만료 상시 분석 낭비·누수)"


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
