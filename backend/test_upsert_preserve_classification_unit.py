# -*- coding: utf-8 -*-
"""업서트 되돌림 차단(FABLE 근본설계 2026-07-05, 문제3 P0-1) — 단위 테스트.

버그: _save_to_db 업서트가 target_type = COALESCE(EXCLUDED, announcements)라,
복지피드(항상 individual 하드코딩) 재수집 때마다 분류기 결과를 individual로 재도장.
복지 전체동기화는 매주 월요일 실행 → business로 분류된 공고가 매주 되돌아감.

수정(단일 기록자): COALESCE(announcements, EXCLUDED)로 역전 — 기존 분류값 보존,
NULL일 때만 수집 하드코딩이 채움(신규 의미 유지).

실행: cd backend && python test_upsert_preserve_classification_unit.py
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


def test_upsert_preserves_classified_target_type():
    from app.services.sync_service import SyncService
    src = inspect.getsource(SyncService._save_to_db)
    assert "target_type = COALESCE(announcements.target_type, EXCLUDED.target_type)" in src, \
        "업서트가 기존 분류값을 보존 안 함 (복지 재수집이 매주 분류 결과를 되돌림)"
    assert "COALESCE(EXCLUDED.target_type, announcements.target_type)" not in src, \
        "옛 순서(수집이 분류를 덮음) 잔존"


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
