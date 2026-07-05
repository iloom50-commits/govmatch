# -*- coding: utf-8 -*-
"""데이터 품질 모니터링(문제2·3 근본개선 추적) — 단위 테스트.

AI COO 일일 보고에 오분류 의심·both 잔존·미분류·마감NULL율을 실어 매일 추이 확인.
(reporter._build_dq_text 렌더링 + health_collector data_quality 수집)

실행: cd backend && python test_data_quality_monitor_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def test_dq_text_renders_all_metrics():
    from app.services.orchestrator.reporter import _build_dq_text
    health = {"data_quality": {
        "misclass_suspect": 20, "both_count": 219, "unclassified": 100,
        "null_deadline": 6565, "null_deadline_rate": 52.0,
    }}
    txt = _build_dq_text(health)
    for token in ("20", "219", "100", "6565", "52"):
        assert token in txt, f"지표 {token} 누락"
    assert "데이터 품질" in txt


def test_dq_text_empty_on_error_or_missing():
    from app.services.orchestrator.reporter import _build_dq_text
    assert _build_dq_text({"data_quality": {"error": "x"}}) == ""
    assert _build_dq_text({}) == ""
    assert _build_dq_text(None) == ""


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
