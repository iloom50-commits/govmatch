# -*- coding: utf-8 -*-
"""한국표준협회(KSA) 스크래퍼 — 순수 파서 단위 테스트.

KSA 공고 게시판은 Jflow CMS(ksa.or.kr/bbs/ksa_kr/1021/artclList.do). 행 구조:
  <td class="_artclTdTitle">
    <a href="/bbs/ksa_kr/1021/{articleNo}/artclView.do"
       onclick="jf_viewArtcl('ksa_kr','1021','{articleNo}')">제목<span>new</span></a>

기존 admin-manual:한국표준협회(KSA) 시드는 엉뚱한 페이지(subview.do)라 extract_fail.
실제 보드(1021)는 파싱 가능 — 지원기업 모집 공고 등 실공고 존재. 프로덕션에서 200(지오차단 아님).

실행: cd backend && python test_ksa_scraper_unit.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

# 실측 구조 기반 픽스처: new 배지 1개, 중복 1개(1590515), 채용 1개 포함
_FIX = """
<tr class="">
  <td class="_artclTdNum">55</td>
  <td class="_artclTdTitle">
    <a href="/bbs/ksa_kr/1021/1590594/artclView.do" onclick="jf_viewArtcl('ksa_kr', '1021', '1590594')" class="artclLinkView">
      <strong class="artclInfo">2026 무역기술장벽(TBT) 실무교육 2차 안내</strong><span class="newArtcl">new</span>
    </a>
  </td>
</tr>
<tr>
  <td class="_artclTdNum">52</td>
  <td class="_artclTdTitle">
    <a href="/bbs/ksa_kr/1021/1590515/artclView.do" onclick="jf_viewArtcl('ksa_kr', '1021', '1590515')" class="artclLinkView">2026년 「첨단산업 분야 표준화 멘토링」 지원기업 모집 공고</a>
  </td>
</tr>
<tr>
  <td class="_artclTdTitle">
    <a href="/bbs/ksa_kr/1021/1590515/artclView.do" class="artclLinkView">2026년 「첨단산업 분야 표준화 멘토링」 지원기업 모집 공고</a>
  </td>
</tr>
<tr>
  <td class="_artclTdTitle">
    <a href="/bbs/ksa_kr/1021/1590300/artclView.do" class="artclLinkView">한국표준협회 직원 채용 공고</a>
  </td>
</tr>
"""


def _scraper():
    from app.services.scrapers.tier1.ksa_scraper import KsaScraper
    return KsaScraper()


def test_parse_extracts_id_and_title():
    out = _scraper()._parse_list(_FIX, set())
    hit = next(o for o in out if "표준화 멘토링" in o["title"])
    assert hit["origin_url"] == "https://ksa.or.kr/bbs/ksa_kr/1021/1590515/artclView.do"
    assert hit["title"].startswith("[표준]")
    assert hit["target_type"] == "business"


def test_parse_dedups_by_id():
    out = _scraper()._parse_list(_FIX, set())
    urls = [o["origin_url"] for o in out]
    assert urls.count("https://ksa.or.kr/bbs/ksa_kr/1021/1590515/artclView.do") == 1


def test_parse_skips_recruitment():
    out = _scraper()._parse_list(_FIX, set())
    assert all("채용" not in o["title"] for o in out)


def test_parse_strips_new_badge():
    out = _scraper()._parse_list(_FIX, set())
    tbt = next(o for o in out if "무역기술장벽" in o["title"])
    assert tbt["title"].rstrip().endswith("안내"), f"new 배지 미제거: {tbt['title']!r}"


def test_parse_count():
    # 1590594, 1590515 = 2건 (1590515 중복 제거, 1590300 채용 제외)
    assert len(_scraper()._parse_list(_FIX, set())) == 2


def test_seen_carries_across_pages():
    seen = set()
    _scraper()._parse_list(_FIX, seen)
    # 같은 seen으로 재파싱하면 이미 본 id라 0건
    assert len(_scraper()._parse_list(_FIX, seen)) == 0


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
