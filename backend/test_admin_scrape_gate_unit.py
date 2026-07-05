# -*- coding: utf-8 -*-
"""admin 이중배선 제거(FABLE 설계 2026-07-05, 기능 1-B) — 단위 테스트.

sync_all(step ①)의 run_all(전체 스캔)과 run_batch(step ②-1)가 매일 admin_urls를
이중 수집 → run_all은 중도 사망·85분 낭비. run_batch를 단일 경로로 만들고
run_all은 ADMIN_FULL_SCAN=true 게이트 뒤로(수동 전체 스캔용, 되돌리기 가능).
헬스 알림(get_health_report)은 DB만 읽으므로 유지.

sync_all은 다수 외부 API를 호출하는 대형 async 메서드라 정적 소스 검증으로 확인
(repo 관례: test_digest_fixes_unit.py의 inspect.getsource 패턴).
실행: cd backend && python test_admin_scrape_gate_unit.py
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

from app.services import sync_service


def test_run_all_gated_behind_admin_full_scan():
    src = inspect.getsource(sync_service.SyncService.sync_all)
    assert "ADMIN_FULL_SCAN" in src, \
        "run_all이 ADMIN_FULL_SCAN 게이트 없이 무조건 호출됨(이중배선 미제거)"
    assert "run_all()" in src, \
        "run_all 호출이 완전히 사라짐 — 게이트 뒤 유지 의도와 불일치"
    assert src.index("ADMIN_FULL_SCAN") < src.index("run_all()"), \
        "게이트(ADMIN_FULL_SCAN)가 run_all() 호출보다 뒤에 있음"


def test_health_alert_block_retained():
    src = inspect.getsource(sync_service.SyncService.sync_all)
    assert "get_health_report()" in src, \
        "헬스 알림(get_health_report) 블록이 제거됨 — DB만 읽으므로 유지해야 함"


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
