# -*- coding: utf-8 -*-
"""아산시기업지원(asan_biz) 스크래퍼 — JSON 파서 단위 테스트.

구 asan.go.kr/giup .../tbl_notice(2021 死板) → biz.asancef.or.kr로 이전.
목록은 정적 JSON(data/bbs_list_<pm>.json), b_id 앞 8자리=게시일(YYYYMMDD).

실행: cd backend && python test_asan_biz_unit.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

_ROWS = [
    {"b_id": "20260709156568414", "b_subj": "2026년 창업기업 판로지원사업 참여기업 모집 공고", "ca_id": "6"},
    {"b_id": "20260701100000000", "b_subj": "직원 채용 공고", "ca_id": "1"},
    {"b_id": "20210311091153742", "b_subj": "2021년 종료된 사업 공고", "ca_id": "0"},
    {"b_id": "", "b_subj": "빈 아이디", "ca_id": "0"},
]


def _p(cutoff="20260401"):
    from app.services.scrapers.tier1.local_biz_scrapers import AsanBizScraper
    return AsanBizScraper()._parse_asan(_ROWS, 2, cutoff)


def test_parse_includes_recent():
    out = _p()
    hit = next(o for o in out if "판로지원" in o["title"])
    assert hit["origin_url"] == "http://biz.asancef.or.kr/main/index.php?m_cd=2&b_id=20260709156568414"
    assert hit["region"] == "아산시"


def test_parse_skips_old_before_cutoff():
    assert all("2021년" not in o["title"] for o in _p())


def test_parse_skips_recruitment():
    assert all("채용" not in o["title"] for o in _p())


def test_parse_skips_empty_bid():
    assert all(o["title"] != "빈 아이디" for o in _p())


def test_parse_deadline_none():
    # 목록엔 마감일 없음 → None(만료 오탐 방지)
    assert all(o.get("deadline_date") is None for o in _p())


def test_parse_count():
    assert len(_p()) == 1  # 최근·비채용·유효 1건


if __name__ == "__main__":
    import traceback
    _fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    _p2 = _f = 0
    for _fn in _fns:
        try:
            _fn(); print("PASS  " + _fn.__name__); _p2 += 1
        except Exception as _e:
            print("FAIL  " + _fn.__name__ + ": " + repr(_e)); traceback.print_exc(); _f += 1
    print("\n%d passed, %d failed" % (_p2, _f)); sys.exit(1 if _f else 0)
