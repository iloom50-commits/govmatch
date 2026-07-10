# -*- coding: utf-8 -*-
"""울산테크노파크 스크래퍼(신 플랫폼 platform.utp.or.kr) — 순수 파서 단위 테스트.

기존 board.php(sub0203_02)가 2024년 死板되어 platform.utp.or.kr/com/biz_gonggo_all.php로
이전됨. 공고는 <a onclick="goViewGonggo('<id>')">공고명</a> 구조.

실행: cd backend && python test_ulsan_tp_unit.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

# 실측 구조 기반 픽스처 (id 1438 중복 1개, 채용 1개 포함)
_FIX = """
<div>울산산업기술단지 거점기능강화사업 <br/>
  <a href="#gonggoView" onclick="goViewGonggo('1438')" style="color:blue;">2026년 기술투자촉진사업 지원기업 모집 공고</a>
</div>
<div><a href="#gonggoView" onclick="goViewGonggo('1439')" style="color:blue;">2026년 대중소상생협력 WPS인증지원사업 모집공고</a></div>
<div><a href="#gonggoView" onclick="goViewGonggo('1438')" style="color:blue;">2026년 기술투자촉진사업 지원기업 모집 공고</a></div>
<div><a href="#gonggoView" onclick="goViewGonggo('1400')" style="color:blue;">울산테크노파크 직원 채용 공고</a></div>
"""


def _scraper():
    from app.services.scrapers.tier1.tp_scrapers import UtpScraper
    return UtpScraper()


def test_parse_extracts_id_and_title():
    out = _scraper()._parse_list(_FIX, set())
    hit = next(o for o in out if "기술투자촉진" in o["title"])
    assert hit["origin_url"] == "https://platform.utp.or.kr/com/biz_gonggo_detail.php?rq_gonggopgrm=1438&cmd=detail"
    assert hit["region"] == "울산"
    assert hit["title"].startswith("[울산]")


def test_parse_dedups_by_id():
    out = _scraper()._parse_list(_FIX, set())
    ids = [o["origin_url"] for o in out]
    assert ids.count("https://platform.utp.or.kr/com/biz_gonggo_detail.php?rq_gonggopgrm=1438&cmd=detail") == 1


def test_parse_skips_recruitment():
    out = _scraper()._parse_list(_FIX, set())
    assert all("채용" not in o["title"] for o in out)


def test_parse_count():
    # 1438, 1439 = 2건 (1438 중복 제거, 1400 채용 제외)
    assert len(_scraper()._parse_list(_FIX, set())) == 2


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
