"""공공기관 스크래퍼 — 기업마당 + KOCCA.

bizinfo.go.kr : 중소벤처기업부 지원사업 공고 포털 (1,200건+, 86페이지)
kocca.kr      : 한국콘텐츠진흥원 지원공고 (콘텐츠·미디어 분야)
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
_EXCLUDE_KW = re.compile(r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품")


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


def _extract_bracket_region(title: str) -> str | None:
    """제목 앞 [지역] 패턴에서 지역 추출."""
    m = re.match(r"^\[([가-힣]{1,6})\]", title)
    return m.group(1) if m else None


# ─────────────────────────────────────────────────────────────
# 1. 기업마당 (bizinfo.go.kr) — 중소벤처기업부 지원사업 공고 포털
# ─────────────────────────────────────────────────────────────
_BIZINFO_BASE = "https://www.bizinfo.go.kr"
_BIZINFO_LIST = (
    f"{_BIZINFO_BASE}/web/lay1/bbs/S1T122C128/AS/74/list.do"
    "?cpage={page}"  # pageIndex는 무시됨, cpage가 실제 페이지 파라미터
)
_BIZINFO_RE = re.compile(
    r"""href\s*=\s*['"]([^'"]*pblancId=(PBLN_\d+)[^'"]*)['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class BizinfoScraper(BaseScraper):
    name = "bizinfo"
    display_name = "기업마당(중소벤처기업부)"
    origin_url_prefix = f"{_BIZINFO_BASE}/sii/siia/selectSIIA200Detail.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_BIZINFO_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _BIZINFO_RE.finditer(html):
                pblanc_id = m.group(2)
                if pblanc_id in seen:
                    continue
                seen.add(pblanc_id)
                found_new = True

                title = _clean(m.group(3))
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                region = _extract_bracket_region(title) or "전국"
                ctx = html[max(0, m.start() - 400): m.end() + 400]

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_BIZINFO_BASE}/sii/siia/selectSIIA200Detail.do"
                        f"?pblancId={pblanc_id}"
                    ),
                    "region": region,
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(BizinfoScraper())


# ─────────────────────────────────────────────────────────────
# 2. 한국콘텐츠진흥원 (kocca.kr) — 지원공고 (콘텐츠/미디어 분야)
# ─────────────────────────────────────────────────────────────
_KOCCA_BASE = "https://www.kocca.kr"
_KOCCA_LIST = (
    f"{_KOCCA_BASE}/kocca/pims/list.do"
    "?menuNo=204104&pageIndex={page}"
)
_KOCCA_RE = re.compile(
    r"""href=['"]([^'"]*intcNo=([A-Z0-9]+)[^'"]*)['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KoccaScraper(BaseScraper):
    name = "kocca"
    display_name = "한국콘텐츠진흥원"
    origin_url_prefix = f"{_KOCCA_BASE}/kocca/pims/view.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KOCCA_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KOCCA_RE.finditer(html):
                intc_no = m.group(2)
                if intc_no in seen:
                    continue
                seen.add(intc_no)
                found_new = True

                title = _clean(m.group(3))
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                ctx = html[max(0, m.start() - 400): m.end() + 400]

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_KOCCA_BASE}/kocca/pims/view.do"
                        f"?intcNo={intc_no}&menuNo=204104"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "콘텐츠",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KoccaScraper())


# ─────────────────────────────────────────────────────────────
# 3. 소상공인시장진흥공단 (ols.semas.or.kr) — 자금공고 POST API
#    구 sbiz24.kr HTML 스크래핑 방식 → OLS API 방식으로 교체
# ─────────────────────────────────────────────────────────────
_SEMAS_API = "https://ols.semas.or.kr/ols/man/SMAN051M/search.do"
_SEMAS_DETAIL = "https://ols.semas.or.kr/ols/man/SMAN052M/page.do"
_SEMAS_API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://ols.semas.or.kr/ols/man/SMAN051M/page.do",
}
_SEMAS_EXCLUDE = re.compile(r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품|청소|경비|보안")


class SemasScraper(BaseScraper):
    name = "semas"
    display_name = "소상공인시장진흥공단(SEMAS)"
    origin_url_prefix = _SEMAS_DETAIL

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                resp = requests.post(
                    _SEMAS_API,
                    headers=_SEMAS_API_HEADERS,
                    data={"pageNo": str(page), "pageSize": "20"},
                    timeout=20,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                break

            result = data.get("result", [])
            if not result:
                break

            found_new = False
            for item in result:
                seq = str(item.get("bltwtrSeq", ""))
                if not seq or seq in seen:
                    continue
                seen.add(seq)
                found_new = True

                raw_title = item.get("bltwtrTitNm", "").strip()
                loan_type = item.get("loanSeCdNm", "").strip()
                category_nm = item.get("bltwtrClcd", "").strip()

                if not raw_title or len(raw_title) < 5:
                    continue
                if _SEMAS_EXCLUDE.search(raw_title):
                    continue

                # 대출 구분을 제목에 포함해 검색 품질 향상
                title = raw_title
                if loan_type and loan_type not in title:
                    title = f"[{loan_type}] {title}"

                reg_date = item.get("frstRegDt", "")

                items.append({
                    "title": title[:400],
                    "origin_url": f"{_SEMAS_DETAIL}?bltwtrSeq={seq}",
                    "region": "전국",
                    "target_type": "individual",
                    "category": category_nm or "소상공인",
                    "summary_text": None,
                    "deadline_date": None,
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(SemasScraper())
