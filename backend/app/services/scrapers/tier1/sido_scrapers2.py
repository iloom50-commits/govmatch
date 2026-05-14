"""광역시도청 스크래퍼 배치 2 — 대구, 경기도, 경상북도

대구광역시청 : 공지사항 (JS 렌더링 가능성 높음 — 0건 graceful fallback)
경기도청     : 공지사항 (JS 렌더링 가능성 높음 — 0건 graceful fallback)
경상북도청   : 고시공고 게시판 (HTML table, &Start= 페이지네이션, B_NUM ID)
"""
from __future__ import annotations
import re
import time
import logging
import requests
from typing import List, Dict, Any
from bs4 import BeautifulSoup

from .base import BaseScraper, SCRAPER_REGISTRY

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}
_EXCLUDE_KW = re.compile(
    r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품|청소|경비|보안|퇴직|임원|낙찰|유찰"
)
_DATE_RE = re.compile(r"(\d{4})[.\-/년](\d{1,2})[.\-/월](\d{1,2})")
_DATE_SHORT_RE = re.compile(r"(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def _get(url: str, **kwargs) -> BeautifulSoup:
    resp = requests.get(url, headers=_HEADERS, timeout=20, **kwargs)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return BeautifulSoup(resp.text, "html.parser")


def _parse_date(text: str) -> str | None:
    # 4자리 연도 우선
    dates = _DATE_RE.findall(text or "")
    if dates:
        y, m, d = dates[-1]
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    # 2자리 연도 (YY-MM-DD → 20YY)
    shorts = _DATE_SHORT_RE.findall(text or "")
    if shorts:
        yy, m, d = shorts[-1]
        return f"20{yy}-{m.zfill(2)}-{d.zfill(2)}"
    return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


# ─────────────────────────────────────────────────────────────
# 1. 대구광역시청 — 공지사항
#    https://www.daegu.go.kr/index.do?menu_id=00000854&pageNo={page}
#    JS 렌더링 가능성 높음 → 0건 시 로그만
# ─────────────────────────────────────────────────────────────
_DAEGU_BASE = "https://www.daegu.go.kr"
_DAEGU_LIST = f"{_DAEGU_BASE}/index.do?menu_id=00000854&pageNo={{page}}"


class DaeguScraper(BaseScraper):
    """대구광역시청 — 공지사항/고시공고"""

    name = "daegu_sido"
    display_name = "대구광역시청"
    origin_url_prefix = _DAEGU_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_DAEGU_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[daegu_sido] page {page} 실패: {e}")
                break

            rows = soup.select("table tbody tr")
            for row in rows:
                link = row.select_one("a[href]")
                if not link:
                    continue
                href = link.get("href", "")
                if not href or "javascript" in href.lower():
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                detail_url = (
                    _DAEGU_BASE + href if href.startswith("/") else href
                )
                if detail_url in seen:
                    continue

                date_text = " ".join(td.get_text(" ") for td in row.select("td"))
                posted = _parse_date(date_text)

                seen.add(detail_url)
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {posted}" if posted else None,
                        "region": "대구",
                        "category": None,
                        "target_type": None,
                        "department": "대구광역시청",
                    }
                )

            if items:
                break
            time.sleep(0.4)

        if not items:
            logger.info(
                "[daegu_sido] 정적 HTML 수집 0건 "
                "(JS 렌더링 가능성 — Playwright 전환 후 재구현 예정)"
            )
        else:
            logger.info(f"[daegu_sido] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(DaeguScraper())


# ─────────────────────────────────────────────────────────────
# 2. 경기도청 — 공지사항
#    https://www.gg.go.kr/bbs/board.do?bsIdx=570&menuId=1590&pageIndex={page}
#    JS 렌더링 가능성 높음 → 0건 시 로그만
# ─────────────────────────────────────────────────────────────
_GG_BASE = "https://www.gg.go.kr"
_GG_LIST = f"{_GG_BASE}/bbs/board.do?bsIdx=570&menuId=1590&pageIndex={{page}}"
_GG_SEQ_RE = re.compile(r"bbsIdx=(\d+)|seq=(\d+)|no=(\d+)", re.IGNORECASE)


class GyeonggiScraper(BaseScraper):
    """경기도청 — 공지사항/도정소식"""

    name = "gyeonggi_sido"
    display_name = "경기도청"
    origin_url_prefix = _GG_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_GG_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[gyeonggi_sido] page {page} 실패: {e}")
                break

            rows = soup.select("table tbody tr, ul.board-list li, div.list-wrap li")
            for row in rows:
                link = row.select_one("a[href]")
                if not link:
                    continue
                href = link.get("href", "")
                if not href or "javascript" in href.lower():
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                detail_url = (
                    _GG_BASE + href if href.startswith("/") else href
                )
                if detail_url in seen:
                    continue

                date_text = row.get_text(" ")
                posted = _parse_date(date_text)

                seen.add(detail_url)
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {posted}" if posted else None,
                        "region": "경기",
                        "category": None,
                        "target_type": None,
                        "department": "경기도청",
                    }
                )

            if items:
                break
            time.sleep(0.4)

        if not items:
            logger.info(
                "[gyeonggi_sido] 정적 HTML 수집 0건 "
                "(JS 렌더링 가능성 — Playwright 전환 후 재구현 예정)"
            )
        else:
            logger.info(f"[gyeonggi_sido] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(GyeonggiScraper())


# ─────────────────────────────────────────────────────────────
# 3. 경상북도청 — 고시공고 게시판
#    https://www.gb.go.kr/Main/page.do?mnu_uid=6786&BD_CODE=bbs_gongji&Start={start}
#    Start=0, 10, 20 … (10개 단위)
#    컬럼: 번호 | 제목(링크) | 파일 | 작성자 | 조회 | 작성일(YY-MM-DD)
#    B_NUM 파라미터로 detail URL 구성
# ─────────────────────────────────────────────────────────────
_GB_BASE = "https://www.gb.go.kr"
_GB_LIST = (
    f"{_GB_BASE}/Main/page.do"
    "?mnu_uid=6786&BD_CODE=bbs_gongji&Start={{start}}"
)
_GB_BNUM_RE = re.compile(r"B_NUM=(\d+)")


class GyeongbukScraper(BaseScraper):
    """경상북도청 — 고시공고 게시판"""

    name = "gyeongbuk_sido"
    display_name = "경상북도청"
    origin_url_prefix = f"{_GB_BASE}/Main/page.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(8):  # Start=0,10,...,70 (8페이지)
            start = page * 10
            try:
                soup = _get(_GB_LIST.format(start=start))
            except Exception as e:
                logger.warning(f"[gyeongbuk_sido] Start={start} 실패: {e}")
                break

            rows = soup.select("table tbody tr")
            if not rows:
                break

            found_new = False
            for row in rows:
                link = row.select_one("a[href*='B_NUM']")
                if not link:
                    continue
                href = link.get("href", "")
                bnum_m = _GB_BNUM_RE.search(href)
                if not bnum_m:
                    continue
                bnum = bnum_m.group(1)
                if bnum in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                # 날짜: 마지막 td (YY-MM-DD 형식)
                cells = row.select("td")
                date_text = cells[-1].get_text(strip=True) if cells else ""
                posted = _parse_date(date_text)

                detail_url = (
                    _GB_BASE + "/Main/" + href.lstrip("./")
                    if href.startswith("./")
                    else _GB_BASE + href if href.startswith("/")
                    else href
                )

                seen.add(bnum)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {posted}" if posted else None,
                        "region": "경북",
                        "category": None,
                        "target_type": None,
                        "department": "경상북도청",
                    }
                )

            if not found_new:
                break
            time.sleep(0.4)

        logger.info(f"[gyeongbuk_sido] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(GyeongbukScraper())
