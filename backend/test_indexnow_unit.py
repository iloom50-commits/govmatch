# -*- coding: utf-8 -*-
"""IndexNow 제출 페이로드 — 단위 테스트 (TDD, HTTP 없이 순수 로직).

새 공고 저장 시 네이버·빙 등에 자동 색인 요청(IndexNow). 수동 수집요청 부담 제거.
실행: cd backend && python test_indexnow_unit.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.indexnow import prepare_urls, build_payload, INDEXNOW_KEY, HOST


def test_prepare_dedup_preserves_order():
    urls = ["https://www.govmatch.kr/announcements/2",
            "https://www.govmatch.kr/announcements/1",
            "https://www.govmatch.kr/announcements/2"]
    assert prepare_urls(urls) == [
        "https://www.govmatch.kr/announcements/2",
        "https://www.govmatch.kr/announcements/1",
    ]


def test_prepare_drops_empty_and_none():
    assert prepare_urls(["", None, "https://www.govmatch.kr/announcements/9", "  "]) == \
        ["https://www.govmatch.kr/announcements/9"]


def test_prepare_caps_at_10000():
    urls = [f"https://www.govmatch.kr/announcements/{i}" for i in range(10050)]
    assert len(prepare_urls(urls)) == 10000


def test_build_payload_required_fields():
    urls = ["https://www.govmatch.kr/announcements/1"]
    p = build_payload(urls)
    assert p["host"] == HOST == "www.govmatch.kr"
    assert p["key"] == INDEXNOW_KEY
    assert p["keyLocation"] == f"https://www.govmatch.kr/{INDEXNOW_KEY}.txt"
    assert p["urlList"] == urls


def test_build_payload_key_is_valid_indexnow_key():
    # 8~128자, 영숫자·대시만
    import re
    assert 8 <= len(INDEXNOW_KEY) <= 128
    assert re.fullmatch(r"[a-zA-Z0-9-]+", INDEXNOW_KEY)


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p = f = 0
    for fn in fns:
        try:
            fn(); print("PASS  " + fn.__name__); p += 1
        except Exception as e:
            print("FAIL  " + fn.__name__ + ": " + repr(e)); traceback.print_exc(); f += 1
    print("\n%d passed, %d failed" % (p, f))
    sys.exit(1 if f else 0)
