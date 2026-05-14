"""공공기관 스크래퍼 배치 13 — KOEF, KEA EEP, KoreaBio

KOEF     : 한국청년기업가정신재단 — 공지사항 (PHP board, ARTICLE_SEQ 파라미터)
KEA EEP  : 한국에너지공단 효율제도실 — 공지사항 (ASP.NET, ./view.aspx?cate=&no=)
KoreaBio : 한국바이오협회 — 공지사항 (그누보드 스타일, bo_table=orgnotice)
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
# 1. KOEF (한국청년기업가정신재단) — 공지사항
#    https://www.koef.or.kr/board/notice_list.php?BOARD_ID=1&page={page}
#    <a href="notice_view.php?ARTICLE_SEQ=5462&page=1">제목</a>
#    날짜: 5번째 td (index 4), YYYY-MM-DD
# ─────────────────────────────────────────────────────────────
_KOEF_BASE = "https://www.koef.or.kr"
_KOEF_LIST = f"{_KOEF_BASE}/board/notice_list.php?BOARD_ID=1&page={{page}}"
_KOEF_SEQ_RE = re.compile(r"ARTICLE_SEQ=(\d+)")


class KOEFScraper(BaseScraper):
    """한국청년기업가정신재단 — 공지사항/창업 지원사업 공고"""

    name = "koef"
    display_name = "한국청년기업가정신재단(KOEF)"
    origin_url_prefix = f"{_KOEF_BASE}/board"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_KOEF_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[koef] page {page} 실패: {e}")
                break

            rows = soup.select("table tbody tr")
            if not rows:
                break

            found_new = False
            for row in rows:
                link = row.select_one("a[href*='notice_view.php']")
                if not link:
                    continue
                href = link.get("href", "")
                seq_m = _KOEF_SEQ_RE.search(href)
                if not seq_m:
                    continue
                seq = seq_m.group(1)
                if seq in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                cells = row.select("td")
                date_text = cells[4].get_text() if len(cells) > 4 else ""
                posted = _parse_date(date_text)

                detail_url = f"{_KOEF_BASE}/board/notice_view.php?ARTICLE_SEQ={seq}&page=1"

                seen.add(seq)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {posted}" if posted else None,
                        "region": "전국",
                        "category": "창업지원",
                        "target_type": "business",
                        "department": "한국청년기업가정신재단",
                    }
                )

            if not found_new:
                break
            time.sleep(0.4)

        logger.info(f"[koef] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(KOEFScraper())


# ─────────────────────────────────────────────────────────────
# 2. KEA EEP (한국에너지공단 효율제도실) — 공지사항
#    https://eep.energy.or.kr/notice/list.aspx?page={page}
#    <a href="./view.aspx?cate=2&no=318">제목</a>
#    날짜: 4번째 td (index 3), YYYY-MM-DD
# ─────────────────────────────────────────────────────────────
_EEP_BASE = "https://eep.energy.or.kr"
_EEP_LIST = f"{_EEP_BASE}/notice/list.aspx?page={{page}}"
_EEP_HREF_RE = re.compile(r"view\.aspx\?cate=(\d+)&no=(\d+)")


class KEAEEPScraper(BaseScraper):
    """한국에너지공단 효율제도실 — 에너지효율 관련 공지·공고"""

    name = "kea_eep"
    display_name = "한국에너지공단 효율제도실(KEA EEP)"
    origin_url_prefix = f"{_EEP_BASE}/notice"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_EEP_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[kea_eep] page {page} 실패: {e}")
                break

            rows = soup.select("table tbody tr")
            if not rows:
                break

            found_new = False
            for row in rows:
                link = row.select_one("a[href*='view.aspx']")
                if not link:
                    continue
                href = link.get("href", "")
                m = _EEP_HREF_RE.search(href)
                if not m:
                    continue
                cate, no = m.group(1), m.group(2)
                uid = f"{cate}_{no}"
                if uid in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                cells = row.select("td")
                date_text = cells[3].get_text() if len(cells) > 3 else ""
                posted = _parse_date(date_text)

                detail_url = f"{_EEP_BASE}/notice/view.aspx?cate={cate}&no={no}"

                seen.add(uid)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {posted}" if posted else None,
                        "region": "전국",
                        "category": "에너지",
                        "target_type": None,
                        "department": "한국에너지공단",
                    }
                )

            if not found_new:
                break
            time.sleep(0.4)

        logger.info(f"[kea_eep] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(KEAEEPScraper())


# ─────────────────────────────────────────────────────────────
# 3. KoreaBio (한국바이오협회) — 공지사항
#    https://www.koreabio.org/board/board.php?bo_table=orgnotice&page={page}
#    <li><a href="...?bo_table=orgnotice&idx=650">제목</a><span>날짜</span></li>
# ─────────────────────────────────────────────────────────────
_KBIO_BASE = "https://www.koreabio.org"
_KBIO_LIST = f"{_KBIO_BASE}/board/board.php?bo_table=orgnotice&page={{page}}"
_KBIO_IDX_RE = re.compile(r"idx=(\d+)")


class KoreaBioScraper(BaseScraper):
    """한국바이오협회 — 공지사항/바이오·의약 지원사업 공고"""

    name = "koreabio"
    display_name = "한국바이오협회(KoreaBio)"
    origin_url_prefix = f"{_KBIO_BASE}/board"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_KBIO_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[koreabio] page {page} 실패: {e}")
                break

            links = soup.select("a[href*='bo_table=orgnotice'][href*='idx=']")
            if not links:
                break

            found_new = False
            for link in links:
                href = link.get("href", "")
                idx_m = _KBIO_IDX_RE.search(href)
                if not idx_m:
                    continue
                idx = idx_m.group(1)
                if idx in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                # 날짜: 링크 부모 li 내 span
                parent = link.find_parent("li") or link.find_parent("tr")
                date_text = ""
                if parent:
                    span = parent.select_one("span")
                    date_text = span.get_text() if span else parent.get_text(" ")
                posted = _parse_date(date_text)

                detail_url = (
                    _KBIO_BASE + href if href.startswith("/") else
                    href if href.startswith("http") else
                    f"{_KBIO_BASE}/board/{href.lstrip('./')}"
                )

                seen.add(idx)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {posted}" if posted else None,
                        "region": "전국",
                        "category": "바이오·의약",
                        "target_type": "business",
                        "department": "한국바이오협회",
                    }
                )

            if not found_new:
                break
            time.sleep(0.4)

        logger.info(f"[koreabio] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(KoreaBioScraper())
