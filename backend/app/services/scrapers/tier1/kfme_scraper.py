"""한국소공인진흥협회(kfme) 스크래퍼 — 공지 게시판.

kfme.or.kr/kr/board/notice.php. 소공인 스마트공방·경영환경개선 등 소공인 지원사업 공고가
기업마당(bizinfo)에 교차게시되지 않는 kfme 전용 채널이라 그동안 누락됐다. 행 구조:
  <div class="column bbs-title">
    <a href="/kr/board/notice.php?bgu=view&idx={idx}&cate=1">
      ...<strong class="bbs-subject-txt"><span class="notice-tit">공지</span> 제목</strong>

목록에 마감일 컬럼이 없다 → deadline_date는 None(하류 deadline_enricher가 본문에서 보강).
등록일을 마감일로 저장하면 진행중 공고가 전량 소실된다(2026-07 BEPA 사고 클래스).
"""
from __future__ import annotations
import re
import requests
from typing import List, Dict, Any

from .base import BaseScraper, SCRAPER_REGISTRY

_KFME_BASE = "https://www.kfme.or.kr"
# startPage는 행 오프셋(0,10,20…) — 상단 공지행은 매 페이지 공통 노출
_KFME_LIST = f"{_KFME_BASE}/kr/board/notice.php?cate=1&startPage={{offset}}"
_KFME_RE = re.compile(
    r'href="/kr/board/notice\.php\?bgu=view&(?:amp;)?idx=(\d+)&(?:amp;)?cate=\d+"'
    r'.*?<strong class="bbs-subject-txt">(.*?)</strong>',
    re.DOTALL,
)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _clean_title(inner_html: str) -> str:
    # 공지 배지 span은 내용('공지'/'공지사항')까지 통째 제거 — 잔재가 제목 앞에 붙지 않도록
    t = re.sub(r'<span class="notice-tit">.*?</span>', " ", inner_html, flags=re.DOTALL)
    t = re.sub(r"<[^>]+>", " ", t)               # 나머지 태그 제거
    t = re.sub(r"\s+", " ", t).strip()
    return t


class KfmeScraper(BaseScraper):
    name = "kfme"
    display_name = "한국소공인진흥협회"
    origin_url_prefix = f"{_KFME_BASE}/kr/board"

    def _parse_list(self, html: str, seen: set) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for m in _KFME_RE.finditer(html):
            idx = m.group(1)
            if idx in seen:
                continue
            seen.add(idx)

            title = _clean_title(m.group(2))
            if not title or len(title) < 5:
                continue

            items.append({
                "title": title[:400],
                "origin_url": f"{_KFME_BASE}/kr/board/notice.php?bgu=view&idx={idx}&cate=1",
                "region": None,
                "target_type": None,   # NULL → AI 분류가 사업자/개인 판정
                "category": None,
                "summary_text": None,
                "deadline_date": None,  # 목록에 마감일 없음 → None (등록일 오인 금지)
                "support_amount": None,
            })
        return items

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()
        for offset in (0, 10, 20, 30):
            try:
                resp = requests.get(_KFME_LIST.format(offset=offset), headers=_HEADERS, timeout=20)
                resp.raise_for_status()
            except Exception:
                break
            page_items = self._parse_list(resp.text, seen)
            if not page_items:
                break
            items.extend(page_items)
        return items


SCRAPER_REGISTRY.append(KfmeScraper())
