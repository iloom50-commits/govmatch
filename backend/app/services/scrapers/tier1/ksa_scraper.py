"""한국표준협회(KSA) 스크래퍼 — 공고 게시판(Jflow CMS).

ksa.or.kr/bbs/ksa_kr/1021/artclList.do. 행 구조:
  <td class="_artclTdTitle">
    <a href="/bbs/ksa_kr/1021/{articleNo}/artclView.do"
       onclick="jf_viewArtcl('ksa_kr','1021','{articleNo}')">제목<span>new</span></a>

구 admin-manual 시드는 엉뚱한 페이지(subview.do)라 extract_fail였음. 실제 보드(1021)는
지원기업 모집 공고 등 실공고 존재. 프로덕션에서 200(지오차단 아님) → 전용 스크래퍼로 대체.
마감일은 리스트에 없음 → None(하류 deadline_enricher가 본문에서 보강).
"""
from __future__ import annotations
import re
import requests
from typing import List, Dict, Any

from .base import BaseScraper, SCRAPER_REGISTRY

_KSA_BASE = "https://ksa.or.kr"
_KSA_LIST = f"{_KSA_BASE}/bbs/ksa_kr/1021/artclList.do?page={{page}}"
_KSA_RE = re.compile(
    r'<a\s+href="/bbs/ksa_kr/1021/(\d+)/artclView\.do"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_EXCLUDE_KW = re.compile(r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품|청소|경비|보안")
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _clean_title(inner_html: str) -> str:
    t = re.sub(r"<[^>]+>", " ", inner_html)
    t = re.sub(r"\s+", " ", t).strip()
    # 목록 'new' 배지가 텍스트로 딸려옴 → 말미의 단독 new 제거
    t = re.sub(r"\s*\bnew\b\s*$", "", t, flags=re.IGNORECASE).strip()
    return t


class KsaScraper(BaseScraper):
    name = "ksa"
    display_name = "한국표준협회(KSA)"
    origin_url_prefix = f"{_KSA_BASE}/bbs/ksa_kr/1021"

    def _parse_list(self, html: str, seen: set) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for m in _KSA_RE.finditer(html):
            art_no = m.group(1)
            if art_no in seen:
                continue
            seen.add(art_no)

            title = _clean_title(m.group(2))
            if not title or len(title) < 5:
                continue
            if _EXCLUDE_KW.search(title):
                continue
            if not title.startswith("["):
                title = f"[표준] {title}"

            items.append({
                "title": title[:400],
                "origin_url": f"{_KSA_BASE}/bbs/ksa_kr/1021/{art_no}/artclView.do",
                "region": None,
                "target_type": "business",
                "category": None,
                "summary_text": None,
                "deadline_date": None,
                "support_amount": None,
            })
        return items

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()
        for page in range(1, 6):
            try:
                resp = requests.get(_KSA_LIST.format(page=page), headers=_HEADERS, timeout=20)
                resp.raise_for_status()
            except Exception:
                break
            page_items = self._parse_list(resp.text, seen)
            if not page_items:
                break
            items.extend(page_items)
        return items


SCRAPER_REGISTRY.append(KsaScraper())
