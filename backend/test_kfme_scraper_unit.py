# -*- coding: utf-8 -*-
"""kfme(한국소공인진흥협회) 스크래퍼 파서 단위 테스트.

배경: 소공인 스마트공방 코디네이터 양성과정 등 kfme.or.kr 전용 공고가 기업마당에
교차게시되지 않아 우리 앱에 안 나옴. kfme 공지 게시판을 새 수집처로 추가.

핵심 규칙(CLAUDE.md): 목록에 마감일 컬럼이 없다 → deadline_date는 반드시 None
(등록일을 마감일로 저장하면 진행중 공고가 전량 소실 — BEPA 사고 클래스).

실행: cd backend && python -m pytest test_kfme_scraper_unit.py -q --no-header
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# kfme.or.kr/kr/board/notice.php 목록의 실제 행 구조(공지행 + 일반행)
_FIXTURE = """
<div class="bbs-list-tbody">
  <div class="bbs-list-row notice-row">
    <div class="column bbs-notice-category"><span class="notice-tit">공지</span></div>
    <div class="column bbs-title">
      <a href="/kr/board/notice.php?bgu=view&idx=5267&cate=1">
        <div class="bbs-subject-con">
          <strong class="bbs-subject-txt"><span class="notice-tit">공지사항</span> 2026 소상공인 경영환경개선 지원사업 2차 모집 공고</strong>
        </div>
      </a>
    </div>
  </div>
  <div class="bbs-list-row">
    <div class="column bbs-title">
      <a href="/kr/board/notice.php?bgu=view&idx=5244&cate=1">
        <div class="bbs-subject-con">
          <strong class="bbs-subject-txt">2026년 소공인 스마트제조지원 (스마트공방) 사업 코디네이터 양성과정 안내</strong>
        </div>
      </a>
    </div>
  </div>
</div>
"""


def _parse():
    from app.services.scrapers.tier1.kfme_scraper import KfmeScraper
    return KfmeScraper()._parse_list(_FIXTURE, set())


def test_target_announcement_extracted():
    """대상 공고(idx=5244 코디네이터 양성과정)가 정확히 추출된다."""
    items = _parse()
    target = [it for it in items if "idx=5244" in it["origin_url"]]
    assert len(target) == 1, f"idx=5244 공고를 못 뽑음 (items={len(items)})"
    it = target[0]
    assert "코디네이터 양성과정" in it["title"], f"제목 이상: {it['title']!r}"
    assert it["origin_url"] == "https://www.kfme.or.kr/kr/board/notice.php?bgu=view&idx=5244&cate=1"


def test_deadline_is_none():
    """마감일 컬럼이 없으므로 deadline_date는 None이어야 한다(등록일 오인 방지)."""
    for it in _parse():
        assert it.get("deadline_date") is None, f"마감일을 채우면 안 됨: {it}"


def test_notice_badge_stripped():
    """공지행의 '공지' 배지가 제목에 섞이지 않는다."""
    items = _parse()
    pinned = [it for it in items if "idx=5267" in it["origin_url"]]
    assert len(pinned) == 1
    # 배지('공지'/'공지사항')와 그 잔재('사항')가 제목 앞에 남지 않아야 한다
    assert pinned[0]["title"].startswith("2026 소상공인 경영환경개선"), f"배지 잔재: {pinned[0]['title']!r}"
