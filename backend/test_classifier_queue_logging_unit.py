# -*- coding: utf-8 -*-
"""분류 큐 재설계 + 결정 로깅(FABLE 근본설계 2026-07-05, 문제3 P1-1) — 단위 테스트.

- 큐 기아 해소: created_at DESC(오래된 NULL 영원히 미처리) → ASC + 시도 3회 상한
- 30일 business 재분류(낭비) 폐지 → 주간 표본감사(L2)가 대체
- 결정 로깅: tt_method/confidence/attempts + classification_events (오분류 감사·정밀지표)
- 프롬프트 'both 권장' 제거(NULL 폴백과 모순)

실행: cd backend && python test_classifier_queue_logging_unit.py
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

import app.services.patrol.target_type_classifier as tc


def test_queue_oldest_first_no_starvation():
    src = inspect.getsource(tc.ai_classify_pending)
    assert "ORDER BY created_at ASC" in src, "큐가 오래된 것 우선이 아님(기아 지속)"
    assert "created_at DESC" not in src, "옛 최신순(기아) 정렬 잔존"


def test_queue_attempt_cap():
    src = inspect.getsource(tc.ai_classify_pending)
    assert "tt_attempts" in src, "시도 횟수 상한 없음(무한 재시도 위험)"


def test_queue_drops_30day_business_reclassify():
    src = inspect.getsource(tc.ai_classify_pending)
    assert "INTERVAL '30 days'" not in src, "30일 business 블랭킷 재분류(낭비) 잔존"


def test_classify_records_method_and_event():
    src = inspect.getsource(tc._classify_and_update)
    assert "tt_method" in src, "결정 method 미기록"
    assert "classification_events" in src, "분류 이력 테이블 미기록"
    assert "tt_attempts = COALESCE(tt_attempts, 0) + 1" in src, "시도 횟수 미증가"


def test_prompt_no_both_recommendation():
    src = inspect.getsource(tc)
    assert '"both" 권장' not in src, "프롬프트가 여전히 both 권장(NULL 폴백과 모순)"


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
