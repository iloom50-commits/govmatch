"""공공기관 스크래퍼 배치 4 — KOSEA, KOVWA.

socialenterprise.or.kr : 한국사회적기업진흥원 (사회적기업 지원공고, page 페이지네이션)
kovwa.or.kr            : 한국여성벤처협회 (여성벤처 지원공고, WordPress page 페이지네이션)
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
# 1. 한국사회적기업진흥원 (socialenterprise.or.kr)
# ─────────────────────────────────────────────────────────────
_KOSEA_BASE = "https://www.socialenterprise.or.kr"
_KOSEA_LIST = (
    f"{_KOSEA_BASE}/homepage/bbs/board.do"
    "?bsIdx=10002&menuId=822&page={page}"
)
# bsIdx=10002 고정 → 해당 게시판 공고만 매칭
_KOSEA_RE = re.compile(
    r"""href=['"][^'"]*bsIdx=10002[^'"]*bIdx=(\d+)[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KoseaScraper(BaseScraper):
    name = "kosea"
    display_name = "한국사회적기업진흥원(KOSEA)"
    origin_url_prefix = f"{_KOSEA_BASE}/homepage/bbs/boardView.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KOSEA_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KOSEA_RE.finditer(html):
                b_idx = m.group(1)
                if b_idx in seen:
                    continue
                seen.add(b_idx)
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
                        f"{_KOSEA_BASE}/homepage/bbs/boardView.do"
                        f"?bsIdx=10002&bIdx={b_idx}&page={page}&menuId=822"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "사회적기업",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KoseaScraper())


# ─────────────────────────────────────────────────────────────
# 2. 한국여성벤처협회 (kovwa.or.kr) — 여성벤처 지원공고
# ─────────────────────────────────────────────────────────────
_KOVWA_BASE = "https://www.kovwa.or.kr"
_KOVWA_LIST = f"{_KOVWA_BASE}/94/?page={{page}}"
# WordPress 계열: bmode=view&idx=171197608&t=board
_KOVWA_RE = re.compile(
    r"""href=['"][^'"]*bmode=view[^'"]*idx=(\d+)[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KovwaScraper(BaseScraper):
    name = "kovwa"
    display_name = "한국여성벤처협회(KOVWA)"
    origin_url_prefix = f"{_KOVWA_BASE}/94/"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KOVWA_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KOVWA_RE.finditer(html):
                idx = m.group(1)
                if idx in seen:
                    continue
                seen.add(idx)
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
                        f"{_KOVWA_BASE}/94/?bmode=view&idx={idx}&t=board"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "여성기업",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KovwaScraper())
