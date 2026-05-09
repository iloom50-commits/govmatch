"""공공기관 스크래퍼 배치 2 — NIPA, KEIT, KIBO, GBSA.

nipa.kr     : 정보통신산업진흥원 (ICT/SW 분야, curPage 페이지네이션)
keit.re.kr  : 한국산업기술평가관리원 (제조/소재/부품 R&D, nPage 페이지네이션)
kibo.or.kr  : 기술보증기금 (기술·창업 보증 지원, offset 페이지네이션)
gbsa.or.kr  : 경기도경제과학진흥원 (경기도 기업 지원, pageIndex 페이지네이션)
"""
from __future__ import annotations
import re
import requests
from typing import List, Dict, Any

from .base import BaseScraper, SCRAPER_REGISTRY

_DATE_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_EXCLUDE_KW = re.compile(r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품|청소|경비|보안")


def _get(url: str, **kwargs) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=20, **kwargs)
    resp.raise_for_status()
    return resp.text


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _clean(raw: str) -> str:
    return re.sub(r"\s+", " ", _strip_tags(raw)).strip()


def _parse_deadline(text: str) -> str | None:
    dates = _DATE_RE.findall(text or "")
    if len(dates) >= 2:
        y, m, d = dates[1]
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    if dates:
        y, m, d = dates[0]
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return None


# ─────────────────────────────────────────────────────────────
# 1. 정보통신산업진흥원 (nipa.kr) — ICT/SW 지원사업 공고
# ─────────────────────────────────────────────────────────────
_NIPA_BASE = "https://www.nipa.kr"
_NIPA_LIST = f"{_NIPA_BASE}/home/2-2?curPage={{page}}"
_NIPA_RE = re.compile(
    r"""href=['"](?:/home/2-2/|https://www\.nipa\.kr/home/2-2/)(\d+)['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class NipaScraper(BaseScraper):
    name = "nipa"
    display_name = "정보통신산업진흥원(NIPA)"
    origin_url_prefix = f"{_NIPA_BASE}/home/2-2/"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_NIPA_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _NIPA_RE.finditer(html):
                post_id = m.group(1)
                if post_id in seen:
                    continue
                seen.add(post_id)
                found_new = True

                title = _clean(m.group(2))
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                ctx = html[max(0, m.start() - 400): m.end() + 400]

                items.append({
                    "title": title[:400],
                    "origin_url": f"{_NIPA_BASE}/home/2-2/{post_id}",
                    "region": "전국",
                    "target_type": "business",
                    "category": "ICT",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(NipaScraper())


# ─────────────────────────────────────────────────────────────
# 2. 한국산업기술평가관리원 (keit.re.kr) — R&D 사업 공고
# ─────────────────────────────────────────────────────────────
_KEIT_BASE = "https://www.keit.re.kr"
_KEIT_LIST = (
    f"{_KEIT_BASE}/board.es"
    "?mid=a10301010000&bid=0009&nPage={page}"
)
_KEIT_RE = re.compile(
    r"""href=['"][^'"]*list_no=(\d+)[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KeitScraper(BaseScraper):
    name = "keit"
    display_name = "한국산업기술평가관리원(KEIT)"
    origin_url_prefix = f"{_KEIT_BASE}/board.es"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KEIT_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KEIT_RE.finditer(html):
                list_no = m.group(1)
                if list_no in seen:
                    continue
                seen.add(list_no)
                found_new = True

                title = _clean(m.group(2))
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                ctx = html[max(0, m.start() - 400): m.end() + 400]

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_KEIT_BASE}/board.es"
                        f"?mid=a10301010000&bid=0009&act=view&list_no={list_no}&nPage={page}"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "R&D",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KeitScraper())


# ─────────────────────────────────────────────────────────────
# 3. 기술보증기금 (kibo.or.kr) — 지원공고 (보증/기술평가)
# ─────────────────────────────────────────────────────────────
_KIBO_BASE = "https://www.kibo.or.kr"
_KIBO_LIST = (
    f"{_KIBO_BASE}/main/board/boardType01.do"
    "?article.offset={offset}&articleLimit=10"
)
_KIBO_RE = re.compile(
    r"""href=['"][^'"]*articleNo=(\d+)[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KiboScraper(BaseScraper):
    name = "kibo"
    display_name = "기술보증기금(KIBO)"
    origin_url_prefix = f"{_KIBO_BASE}/main/board/boardType01.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(0, 10):  # offset = page * 10
            offset = page * 10
            try:
                html = _get(_KIBO_LIST.format(offset=offset))
            except Exception:
                break

            found_new = False
            for m in _KIBO_RE.finditer(html):
                article_no = m.group(1)
                if article_no in seen:
                    continue
                seen.add(article_no)
                found_new = True

                title = _clean(m.group(2))
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                ctx = html[max(0, m.start() - 400): m.end() + 400]

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_KIBO_BASE}/main/board/boardType01.do"
                        f"?mode=view&articleNo={article_no}&article.offset={offset}&articleLimit=10"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "금융",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KiboScraper())


# ─────────────────────────────────────────────────────────────
# 4. 경기도경제과학진흥원 (gbsa.or.kr) — 공지사항/지원사업
# ─────────────────────────────────────────────────────────────
_GBSA_BASE = "https://www.gbsa.or.kr"
_GBSA_LIST = f"{_GBSA_BASE}/board/notice.do?pageIndex={{page}}"
_GBSA_RE = re.compile(
    r"""href=['"][^'"]*nttId=(\d+)[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class GbsaScraper(BaseScraper):
    name = "gbsa"
    display_name = "경기도경제과학진흥원(GBSA)"
    origin_url_prefix = f"{_GBSA_BASE}/board/notice.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_GBSA_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _GBSA_RE.finditer(html):
                ntt_id = m.group(1)
                if ntt_id in seen:
                    continue
                seen.add(ntt_id)
                found_new = True

                title = _clean(m.group(2))
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                ctx = html[max(0, m.start() - 400): m.end() + 400]

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_GBSA_BASE}/board/notice.do"
                        f"?nttId={ntt_id}&pageIndex={page}"
                    ),
                    "region": "경기",
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(GbsaScraper())
