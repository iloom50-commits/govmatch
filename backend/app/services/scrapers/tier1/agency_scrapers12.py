"""공공기관 스크래퍼 배치 12 — HRD Korea, KWBIZ, KOSA

HRD Korea : 한국산업인력공단 — 공지사항/훈련 공고 (HTML table, Java 타임스탬프)
KWBIZ     : 한국여성경제인협회 — 지원사업 공고 (HTML table, goDetail JS URL 재구성)
KOSA      : 한국소프트웨어산업협회 — 공지·행사 게시판 (eGovFrame CMS, BS4)
"""
from __future__ import annotations
import re
import time
import logging
import datetime
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
_DATE_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def _get(url: str, **kwargs) -> BeautifulSoup:
    resp = requests.get(url, headers=_HEADERS, timeout=20, **kwargs)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return BeautifulSoup(resp.text, "html.parser")


def _parse_date(text: str) -> str | None:
    dates = _DATE_RE.findall(text or "")
    if not dates:
        return None
    y, m, d = dates[-1]
    return f"{y}-{m.zfill(2)}-{d.zfill(2)}"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


# ─────────────────────────────────────────────────────────────
# 1. HRD Korea (한국산업인력공단) — 공지사항
#    https://www.hrdkorea.or.kr/3/1/1?pageNo={page}
#    컬럼: 번호 | 제목(링크, ?k=ID) | Java 타임스탬프
# ─────────────────────────────────────────────────────────────
_HRD_BASE = "https://www.hrdkorea.or.kr"
_HRD_LIST = f"{_HRD_BASE}/3/1/1?pageNo={{page}}&searchType=&searchText="
_HRD_K_RE = re.compile(r"[?&]k=(\d+)")

# Java 타임스탬프: "Fri Mar 27 13:50:04 KST 2026"
_HRD_TS_RE = re.compile(
    r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"(\d{1,2})\s+[\d:]+\s+KST\s+(\d{4})"
)
_MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def _hrd_parse_date(text: str) -> str | None:
    m = _HRD_TS_RE.search(text or "")
    if m:
        _, mon_s, day, year = m.groups()
        try:
            return f"{year}-{_MONTH_MAP[mon_s]:02d}-{int(day):02d}"
        except (KeyError, ValueError):
            pass
    return _parse_date(text)


class HRDKoreaScraper(BaseScraper):
    """한국산업인력공단 — 공지사항/훈련·자격 공고"""

    name = "hrd_korea"
    display_name = "한국산업인력공단(HRD Korea)"
    origin_url_prefix = _HRD_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 8):
            try:
                soup = _get(_HRD_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[hrd_korea] page {page} 실패: {e}")
                break

            rows = soup.select("table tbody tr")
            if not rows:
                break

            found_new = False
            for row in rows:
                link = row.select_one("a[href*='k=']")
                if not link:
                    continue
                href = link.get("href", "")
                k_m = _HRD_K_RE.search(href)
                if not k_m:
                    continue
                k = k_m.group(1)
                if k in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                # 날짜: 세 번째 td (Java timestamp)
                cells = row.select("td")
                date_text = cells[-1].get_text(" ") if cells else ""
                posted = _hrd_parse_date(date_text)

                detail_url = (
                    _HRD_BASE + href if href.startswith("/") else href
                )

                seen.add(k)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {posted}" if posted else None,
                        "region": "전국",
                        "category": "직업훈련",
                        "target_type": None,
                        "department": "한국산업인력공단",
                    }
                )

            if not found_new:
                break
            time.sleep(0.4)

        logger.info(f"[hrd_korea] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(HRDKoreaScraper())


# ─────────────────────────────────────────────────────────────
# 2. KWBIZ (한국여성경제인협회) — 공지사항/지원사업
#    https://www.kwbiz.or.kr/notice?page={page}
#    링크: javascript:goDetail('BOARD_XXXXXXXXX')
#    → 상세 URL: /notice/BOARD_XXXXXXXXX
# ─────────────────────────────────────────────────────────────
_KWBIZ_BASE = "https://www.kwbiz.or.kr"
_KWBIZ_LIST = f"{_KWBIZ_BASE}/notice?page={{page}}"
_KWBIZ_ID_RE = re.compile(r"goDetail\(['\"]?(BOARD_\w+)['\"]?\)")


class KWBIZScraper(BaseScraper):
    """한국여성경제인협회 — 공지사항/여성기업 지원사업"""

    name = "kwbiz"
    display_name = "한국여성경제인협회(KWBIZ)"
    origin_url_prefix = _KWBIZ_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_KWBIZ_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[kwbiz] page {page} 실패: {e}")
                break

            rows = soup.select("table tbody tr, tr")
            found_new = False
            for row in rows:
                # goDetail JS 링크에서 BOARD ID 추출
                subj_td = row.select_one("td.td_sub, td[class*='sub']")
                if not subj_td:
                    continue
                link = subj_td.select_one("a")
                if not link:
                    continue

                onclick = link.get("href", "") + " " + link.get("onclick", "")
                id_m = _KWBIZ_ID_RE.search(onclick)
                if not id_m:
                    continue
                board_id = id_m.group(1)
                if board_id in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                # 날짜: td.td_date (YYYY/MM/DD)
                date_td = row.select_one("td.td_date")
                posted = _parse_date(date_td.get_text() if date_td else "")

                seen.add(board_id)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": f"{_KWBIZ_BASE}/notice/{board_id}",
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {posted}" if posted else None,
                        "region": "전국",
                        "category": "창업지원",
                        "target_type": None,
                        "department": "한국여성경제인협회",
                    }
                )

            if not found_new:
                break
            time.sleep(0.4)

        logger.info(f"[kwbiz] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(KWBIZScraper())


# ─────────────────────────────────────────────────────────────
# 3. KOSA (한국소프트웨어산업협회) — 공지·행사 게시판
#    eGovFrame CMS (KEITI와 동일 패턴)
#    cbIdx=292 (행사·전시) + cbIdx=379 (뉴스·공지)
# ─────────────────────────────────────────────────────────────
_KOSA_BASE = "https://www.sw.or.kr"

_KOSA_BOARDS = [
    (292, "행사·전시"),
    (379, "뉴스·공지"),
]

_KOSA_HEADERS = {
    **_HEADERS,
    "Referer": f"{_KOSA_BASE}/",
}


def _get_kosa(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=_KOSA_HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return BeautifulSoup(resp.text, "html.parser")


def _scrape_kosa_board(cbIdx: int, board_label: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen: set = set()

    for page in range(1, 5):
        url = (
            f"{_KOSA_BASE}/site/sw/ex/board/List.do"
            f"?cbIdx={cbIdx}&pageIndex={page}"
        )
        try:
            soup = _get_kosa(url)
        except Exception as e:
            logger.warning(f"[kosa] cbIdx={cbIdx} page {page} 실패: {e}")
            break

        links = soup.select(
            f"a.bbsSubjectLink[href*='cbIdx={cbIdx}'], "
            f"a[href*='board/View.do?cbIdx={cbIdx}']"
        )
        if not links:
            break

        found_new = False
        for link in links:
            href = link.get("href", "")
            bc_m = re.search(r"bcIdx=(\d+)", href)
            if not bc_m:
                continue
            bcIdx = bc_m.group(1)
            if bcIdx in seen:
                continue

            title = _clean(link.get("title", "") or link.get_text())
            # 글번호 제거 ("NNNN번글")
            title = re.sub(r"^\d+번글$", "", title).strip()
            if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                continue

            # 날짜: 링크 부모 tr에서 span.date 또는 마지막 td
            parent = link.find_parent("tr") or link.find_parent("li")
            date_text = ""
            if parent:
                date_span = parent.select_one("span.date")
                date_text = date_span.get_text() if date_span else parent.get_text(" ")
            posted = _parse_date(date_text)

            detail_url = (
                _KOSA_BASE + href if href.startswith("/") else href
            )

            seen.add(bcIdx)
            found_new = True
            items.append(
                {
                    "title": title[:400],
                    "origin_url": detail_url,
                    "deadline_date": None,
                    "support_amount": None,
                    "summary_text": f"[{board_label}] 등록일: {posted}" if posted else f"[{board_label}]",
                    "region": "전국",
                    "category": "ICT",
                    "target_type": "business",
                    "department": "한국소프트웨어산업협회",
                }
            )

        if not found_new:
            break
        time.sleep(0.4)

    return items


class KOSAScraper(BaseScraper):
    """한국소프트웨어산업협회 — 공지·행사 게시판"""

    name = "kosa"
    display_name = "한국소프트웨어산업협회(KOSA)"
    origin_url_prefix = f"{_KOSA_BASE}/site/sw/ex/board"

    def fetch_items(self) -> List[Dict[str, Any]]:
        all_items: List[Dict[str, Any]] = []
        seen_urls: set = set()

        for cbIdx, label in _KOSA_BOARDS:
            for it in _scrape_kosa_board(cbIdx, label):
                if it["origin_url"] not in seen_urls:
                    seen_urls.add(it["origin_url"])
                    all_items.append(it)

        logger.info(f"[kosa] 수집: {len(all_items)}건")
        return all_items


SCRAPER_REGISTRY.append(KOSAScraper())
