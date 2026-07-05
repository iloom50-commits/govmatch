# -*- coding: utf-8 -*-
"""enricher 재스캔 마킹 + 분석큐 마감 우선(FABLE 근본설계 2026-07-05, 문제2 P1-3) - 단위 테스트.

문제2의 남은 절반(마감 NULL 54.7%)의 두 병목:
1) enricher가 'unknown'(파싱 실패) 결과일 때 행을 전혀 안 건드려 매 실행마다 같은
   원문을 재스캔(낭비) + ORDER BY created_at DESC(최신순)라 오래된 NULL은 영원히 기아.
   -> deadline_checked_at 마킹(모든 브랜치) + 7일 재검사 창 + 미검사·오래된 것 우선.
2) discover_unanalyzed가 마감 미상을 우선 분석하지 않아 원문 부재 NULL이 계속 쌓임.
   -> (deadline_date IS NULL) 우선 정렬로 마감 미상부터 원문 확보.

실행: cd backend && python test_deadline_marking_priority_unit.py
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

import app.services.deadline_enricher as de
import app.services.patrol.analysis_recovery as ar


def test_enricher_marks_checked_at_all_branches():
    src = inspect.getsource(de.enrich_pending_deadlines)
    # fixed/ongoing/unknown 세 브랜치 모두 checked 마킹(unknown도 마킹해야 재스캔 낭비·기아 차단)
    n = src.count("deadline_checked_at=CURRENT_TIMESTAMP")
    assert n >= 3, "checked_at 마킹 부족: %d곳(fixed/ongoing/unknown 3브랜치 기대)" % n


def test_enricher_skips_recently_checked():
    src = inspect.getsource(de.enrich_pending_deadlines)
    assert "deadline_checked_at IS NULL" in src, "재스캔 스킵 조건(미검사) 없음"
    assert "INTERVAL '7 days'" in src, "재검사 주기(stale window) 없음"


def test_enricher_no_newest_first_starvation():
    src = inspect.getsource(de.enrich_pending_deadlines)
    assert "ORDER BY a.created_at DESC" not in src, "최신순(기아) 정렬 잔존"
    assert "deadline_checked_at ASC NULLS FIRST" in src, "미검사·오래된 것 우선 정렬 아님"


def test_discover_prioritizes_null_deadline():
    src = inspect.getsource(ar.discover_unanalyzed)
    assert "(a.deadline_date IS NULL) DESC" in src, "마감 미상 우선 정렬 없음(원문 부재 NULL 계속 적체)"


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
