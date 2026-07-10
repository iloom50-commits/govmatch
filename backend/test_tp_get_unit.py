# -*- coding: utf-8 -*-
"""tp_scrapers._get — SSL 실패 시 verify=False 폴백 단위 테스트.

gwangju/jeonbuk TP가 프로덕션에서만 fetch 0건 → SSL 체인 거부 가설. _get이
SSLError 시 verify=False로 재시도하도록.

실행: cd backend && python test_tp_get_unit.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass


def test_get_retries_without_verify_on_sslerror():
    import app.services.scrapers.tier1.tp_scrapers as mod
    import requests

    calls = {"n": 0, "verify_used": []}

    class _Resp:
        text = "<html>ok</html>"
        def raise_for_status(self): pass

    def fake_get(url, **kwargs):
        calls["n"] += 1
        calls["verify_used"].append(kwargs.get("verify", True))
        if calls["n"] == 1:
            raise requests.exceptions.SSLError("cert verify failed")
        return _Resp()

    orig = requests.get
    requests.get = fake_get
    try:
        html = mod._get("https://example.gov/list")
    finally:
        requests.get = orig
    assert html == "<html>ok</html>"
    assert calls["n"] == 2                       # 1차 실패 → 2차 재시도
    assert calls["verify_used"][1] is False      # 2차는 verify=False


def test_get_normal_no_retry():
    import app.services.scrapers.tier1.tp_scrapers as mod
    import requests

    class _Resp:
        text = "<html>ok</html>"
        def raise_for_status(self): pass

    calls = {"n": 0}
    def fake_get(url, **kwargs):
        calls["n"] += 1
        return _Resp()

    orig = requests.get
    requests.get = fake_get
    try:
        mod._get("https://example.gov/list")
    finally:
        requests.get = orig
    assert calls["n"] == 1  # 정상이면 재시도 없음


if __name__ == "__main__":
    import traceback
    _fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    _p = _f = 0
    for _fn in _fns:
        try:
            _fn(); print("PASS  " + _fn.__name__); _p += 1
        except Exception as _e:
            print("FAIL  " + _fn.__name__ + ": " + repr(_e)); traceback.print_exc(); _f += 1
    print("\n%d passed, %d failed" % (_p, _f)); sys.exit(1 if _f else 0)
