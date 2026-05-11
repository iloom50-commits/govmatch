"""공공기관 스크래퍼 배치 8 — 고비즈코리아, 신용보증기금

gobizkorea.com    : 중기부 수출지원 공지 (HTML 파싱)
kodit.co.kr       : 신용보증기금 공고 (HTML 파싱)

※ 중소기업진흥공단(kosmes.or.kr), KIAT(kiat.or.kr)는
   순수 JS 렌더링이라 Playwright 도입 후 별도 구현 예정
"""
from __future__ import annotations
import html as html_lib
import re
import time
import requests
from typing import List, Dict, Any

from .base import BaseScraper, SCRAPER_REGISTRY

_DATE_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}
_EXCLUDE_KW = re.compile(r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품|청소|경비|보안|퇴직|임원")


def _get(url: str, **kwargs) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=20, **kwargs)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _post(url: str, data: dict, **kwargs) -> str:
    resp = requests.post(url, headers=_HEADERS, data=data, timeout=20, **kwargs)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _clean(raw: str) -> str:
    return re.sub(r"\s+", " ", _strip_tags(raw)).strip()


def _parse_date(text: str) -> str | None:
    m = _DATE_RE.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return None


# ─────────────────────────────────────────────────────────────
# 1. 고비즈코리아 (gobizkorea.com) — 중기부 수출지원 공지사항
# ─────────────────────────────────────────────────────────────
_GOBIZ_BASE = "https://kr.gobizkorea.com"
_GOBIZ_LIST = f"{_GOBIZ_BASE}/customer/board/cmList.do?bbs_id=smenotice&page={{page}}"
_GOBIZ_DETAIL_RE = re.compile(r"goDetail\('(\d+)'\)", re.IGNORECASE)
_GOBIZ_TITLE_RE = re.compile(
    r'class="tl"[^>]*>\s*<a[^>]+goDetail\(\'(\d+)\'\)[^>]*>(.*?)</a>',
    re.DOTALL,
)
_GOBIZ_DATE_RE = re.compile(r'<td[^>]*>(\d{4}-\d{2}-\d{2})</td>')


class GobizKoreaScraper(BaseScraper):
    name = "gobizkorea"
    display_name = "고비즈코리아(중기부 수출지원)"
    origin_url_prefix = f"{_GOBIZ_BASE}/customer/board"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                html = _get(_GOBIZ_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _GOBIZ_TITLE_RE.finditer(html):
                seq = m.group(1)
                if seq in seen:
                    continue
                seen.add(seq)
                found_new = True

                title = html_lib.unescape(_clean(m.group(2)))
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                ctx = html[max(0, m.start() - 200): m.end() + 400]
                dates = _GOBIZ_DATE_RE.findall(ctx)
                deadline = dates[-1] if dates else None

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_GOBIZ_BASE}/customer/board/cmView.do"
                        f"?bbs_id=smenotice&nos={seq}"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "수출",
                    "summary_text": None,
                    "deadline_date": deadline,
                    "support_amount": None,
                })

            if not found_new:
                break
            time.sleep(0.3)

        return items


SCRAPER_REGISTRY.append(GobizKoreaScraper())


# ─────────────────────────────────────────────────────────────
# 2. 신용보증기금 (kodit.co.kr) — 공지사항
# ─────────────────────────────────────────────────────────────
_KODIT_BASE = "https://www.kodit.co.kr"
_KODIT_LIST = (
    f"{_KODIT_BASE}/kodit/na/ntt/selectNttList.do"
    "?mi=2638&bbsId=148&currPage={page}"
)
_KODIT_TITLE_RE = re.compile(
    r'data-id="(\d+)"\s+class="nttInfoBtn">\s*(.*?)\s*</a>',
    re.DOTALL,
)
_KODIT_DATE_RE = re.compile(r'<td[^>]*>(\d{4}\.\d{2}\.\d{2})</td>')


class KoditScraper(BaseScraper):
    name = "kodit"
    display_name = "신용보증기금(KODIT)"
    origin_url_prefix = f"{_KODIT_BASE}/kodit/na/ntt"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                html = _get(_KODIT_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KODIT_TITLE_RE.finditer(html):
                ntt_id = m.group(1)
                if ntt_id in seen:
                    continue
                seen.add(ntt_id)
                found_new = True

                title = html_lib.unescape(_clean(m.group(2)))
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                ctx = html[max(0, m.start() - 100): m.end() + 400]
                dates = _KODIT_DATE_RE.findall(ctx)
                raw_dl = dates[-1] if dates else None
                deadline = _parse_date(raw_dl) if raw_dl else None

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_KODIT_BASE}/kodit/na/ntt/selectNttInfo.do"
                        f"?mi=2638&bbsId=148&nttSn={ntt_id}"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "금융",
                    "summary_text": None,
                    "deadline_date": deadline,
                    "support_amount": None,
                })

            if not found_new:
                break
            time.sleep(0.3)

        return items


SCRAPER_REGISTRY.append(KoditScraper())


# TODO: 중소기업진흥공단(kosmes.or.kr), 한국산업기술진흥원(kiat.or.kr)
#   → 순수 JS 렌더링 (Knockout.js AJAX). Playwright 도입 후 구현 예정.
