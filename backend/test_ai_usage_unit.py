# -*- coding: utf-8 -*-
"""ai_usage.extract_usage — 구·신 SDK usage_metadata 추출 단위 테스트.
실행: cd backend && python test_ai_usage_unit.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass
from app.services.ai_usage import extract_usage


class _UM:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _Resp:
    def __init__(self, um):
        self.usage_metadata = um


def test_extract_new_sdk_with_thoughts():
    r = _Resp(_UM(prompt_token_count=100, candidates_token_count=500, thoughts_token_count=2000, total_token_count=2600))
    assert extract_usage(r) == (100, 500, 2000, 2600)


def test_extract_old_sdk_no_thoughts():
    # 구 SDK는 thoughts 필드 없음 → 0
    r = _Resp(_UM(prompt_token_count=100, candidates_token_count=500, total_token_count=600))
    assert extract_usage(r) == (100, 500, 0, 600)


def test_extract_none_when_no_metadata():
    class _R:
        pass
    assert extract_usage(_R()) is None


if __name__ == "__main__":
    import traceback
    _fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    _p = _f = 0
    for fn in _fns:
        try:
            fn(); print("PASS  " + fn.__name__); _p += 1
        except Exception as e:
            print("FAIL  " + fn.__name__ + ": " + repr(e)); traceback.print_exc(); _f += 1
    print("\n%d passed, %d failed" % (_p, _f)); sys.exit(1 if _f else 0)
