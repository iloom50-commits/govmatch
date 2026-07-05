# -*- coding: utf-8 -*-
"""L2 주간 표본감사(FABLE 근본설계, 문제3 P2-1) — 단위 테스트.

분류된 공고를 출처강제 없이 Gemini로 재판정(_call_gemini_classify 재사용)해 저장값과
비교, classification_events(method='audit')에 기록. keyword 휴리스틱(misclass_suspect)의
상한치가 아닌 '정탐 제외 실제 오분류율'을 표본으로 측정.

- 측정 전용: target_type을 변경하지 않는다(출처강제 90.7% 담당을 단일 Gemini로 뒤집지 않음).
- 주 1회 게이팅: 최근 6일 내 감사 있으면 스킵(매일 중복 실행·비용 방지).

실행: cd backend && python test_l2_audit_unit.py
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


def test_audit_function_exists_and_reuses_gemini():
    assert hasattr(tc, "weekly_classification_audit"), "L2 감사 함수 없음"
    src = inspect.getsource(tc.weekly_classification_audit)
    assert "_call_gemini_classify" in src, "출처강제 없는 Gemini 재판정 미사용(출처강제 검증 불가)"
    assert "classification_events" in src, "감사 이력 테이블 미기록"
    assert "'audit'" in src, "method='audit' 미기록(다른 method와 구분 불가)"


def test_audit_is_measurement_only():
    src = inspect.getsource(tc.weekly_classification_audit)
    assert "UPDATE announcements SET target_type" not in src, \
        "감사가 target_type을 변경(측정 전용이어야 — 단일 Gemini로 출처강제 뒤집기 금지)"


def test_audit_weekly_gated():
    src = inspect.getsource(tc.weekly_classification_audit)
    assert "INTERVAL '6 days'" in src, "주간 게이팅(6일) 없음 — 매일 중복 실행·비용 위험"


def test_reporter_renders_l2_audit_rate():
    import app.services.orchestrator.reporter as rep
    health = {"data_quality": {
        "misclass_suspect": 0, "both_count": 0, "unclassified": 0,
        "null_deadline": 0, "null_deadline_rate": 0.0,
        "l2_audit": {"conclusive": 48, "mismatch": 3, "mismatch_rate": 6.2}}}
    txt = rep._build_dq_text(health)
    assert "L2 표본감사 오분류율: 6.2%" in txt, "리포트 텍스트에 L2 오분류율 미노출"
    src = inspect.getsource(rep)
    assert "l2_audit" in src and "L2 표본감사 오분류율" in src, "HTML L2 측정 노출 배선 없음"


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
            _failed += 1
    print("\n%d passed, %d failed" % (_passed, _failed))
    sys.exit(1 if _failed else 0)
