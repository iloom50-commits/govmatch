"""공공기관 스크래퍼 배치 3 — KETEP, aT, K-SURE, KIPA.

ketep.re.kr   : 한국에너지기술평가원 (에너지 R&D 공고, pageNum 페이지네이션)
at.or.kr      : 한국농수산식품유통공사 (농식품 지원사업, pageIndex 페이지네이션)
ksure.or.kr   : 한국무역보험공사 (무역보증 지원, data-ntt-sn 추출)
kipa.org      : 한국발명진흥회 (발명·특허 지원, pager.offset 페이지네이션)
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
# 1. 한국에너지기술평가원 (ketep.re.kr) — 에너지 R&D 공고
# ─────────────────────────────────────────────────────────────
_KETEP_BASE = "https://www.ketep.re.kr"
_KETEP_LIST = (
    f"{_KETEP_BASE}/businessAcment"
    "?menuId=MENU002080200000000&pageNum={page}&rowCnt=10"
)
_KETEP_RE = re.compile(
    r"""href=['"][^'"]*uni_ancm_id=([A-Z0-9]+)[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KetepScraper(BaseScraper):
    name = "ketep"
    display_name = "한국에너지기술평가원(KETEP)"
    origin_url_prefix = f"{_KETEP_BASE}/businessAcment/view"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KETEP_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KETEP_RE.finditer(html):
                ancm_id = m.group(1)
                if ancm_id in seen:
                    continue
                seen.add(ancm_id)
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
                        f"{_KETEP_BASE}/businessAcment/view"
                        f"?menuId=MENU002080200000000&uni_ancm_id={ancm_id}"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "에너지",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KetepScraper())


# ─────────────────────────────────────────────────────────────
# 2. 한국농수산식품유통공사 (at.or.kr) — 농식품 지원사업
# ─────────────────────────────────────────────────────────────
_AT_BASE = "https://www.at.or.kr"
_AT_LIST = f"{_AT_BASE}/article/apko364000/list.action?pageIndex={{page}}"
_AT_RE = re.compile(
    r"""href=['"][^'"]*articleId=(\d+)[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class AtScraper(BaseScraper):
    name = "at_corporation"
    display_name = "한국농수산식품유통공사(aT)"
    origin_url_prefix = f"{_AT_BASE}/article/apko364000/view.action"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_AT_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _AT_RE.finditer(html):
                article_id = m.group(1)
                if article_id in seen:
                    continue
                seen.add(article_id)
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
                        f"{_AT_BASE}/article/apko364000/view.action"
                        f"?articleId={article_id}"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "농식품",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(AtScraper())


# ─────────────────────────────────────────────────────────────
# 3. 한국무역보험공사 (ksure.or.kr) — 지원공고 (data-ntt-sn 추출)
# ─────────────────────────────────────────────────────────────
_KSURE_BASE = "https://www.ksure.or.kr"
_KSURE_LIST = (
    f"{_KSURE_BASE}/rh-kr/bbs/i-412/list.do"
    "?pageIndex={page}&searchCondition=&pageItm=10"
)
# href="javascript:void(0)" data-ntt-sn="625064" ...>제목</a>
_KSURE_RE = re.compile(
    r"""data-ntt-sn=['"](\d+)['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KsureScraper(BaseScraper):
    name = "ksure"
    display_name = "한국무역보험공사(K-SURE)"
    origin_url_prefix = f"{_KSURE_BASE}/rh-kr/bbs/i-412/detail.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KSURE_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KSURE_RE.finditer(html):
                ntt_sn = m.group(1)
                if ntt_sn in seen:
                    continue
                seen.add(ntt_sn)
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
                        f"{_KSURE_BASE}/rh-kr/bbs/i-412/detail.do"
                        f"?ntt_sn={ntt_sn}"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "수출",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KsureScraper())


# ─────────────────────────────────────────────────────────────
# 4. 한국발명진흥회 (kipa.org) — 발명·특허 지원사업 공고
# ─────────────────────────────────────────────────────────────
_KIPA_BASE = "https://www.kipa.org"
_KIPA_LIST = (
    f"{_KIPA_BASE}/kipa/notice/kw_0403_01.jsp"
    "?pager.offset={offset}&board_no=28"
)
_KIPA_PAGE_SIZE = 10
_KIPA_RE = re.compile(
    r"""href=['"][^'"]*article_no=(\d+)[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KipaScraper(BaseScraper):
    name = "kipa"
    display_name = "한국발명진흥회(KIPA)"
    origin_url_prefix = f"{_KIPA_BASE}/kipa/notice/kw_0403_01.jsp"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(0, 10):  # offset = page * 10
            offset = page * _KIPA_PAGE_SIZE
            try:
                html = _get(_KIPA_LIST.format(offset=offset))
            except Exception:
                break

            found_new = False
            for m in _KIPA_RE.finditer(html):
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
                        f"{_KIPA_BASE}/kipa/notice/kw_0403_01.jsp"
                        f"?mode=view&article_no={article_no}&board_no=28"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KipaScraper())
