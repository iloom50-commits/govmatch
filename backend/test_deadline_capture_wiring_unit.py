# -*- coding: utf-8 -*-
"""P2-2 수집단 마감정보 손실 근본해결 — 배선(정적) 테스트.

FABLE 근본설계(scratchpad/p2_2_collection_design.md) 2026-07-05.
수집단에 '마감 원문' 개념이 없어 파서가 실패하면 원문을 버린 채 NULL 저장하던 것을,
중앙 헬퍼 parse_deadline + 저장 관문 일원화 + 원문/기록자 보존으로 근본 차단.

이 파일은 단계별로 확장된다(P2-2a..f). 각 단계 구현 전 해당 assert가 RED여야 한다.

실행: cd backend && python test_deadline_capture_wiring_unit.py
"""
import os
import sys
import inspect
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import app.main as m


# ── P2-2a: 컬럼 2개 추가 (ADD-only) ──
def test_migration_adds_raw_text_and_source_columns():
    src = inspect.getsource(m.init_database)
    assert "ADD COLUMN IF NOT EXISTS deadline_raw_text VARCHAR(200)" in src, \
        "deadline_raw_text 컬럼 마이그레이션 없음(원문 보존 불가)"
    assert "ADD COLUMN IF NOT EXISTS deadline_source VARCHAR(20)" in src, \
        "deadline_source 컬럼 마이그레이션 없음(기록자 귀속 불가)"


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
