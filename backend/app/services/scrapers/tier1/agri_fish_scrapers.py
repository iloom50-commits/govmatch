"""농·수산 기관 스크래퍼 — RDA, KRC, FIRA, MOF

RDA  : 농촌진흥청 — 공지사항 (HTML table, currPage 페이지네이션, dataNo ID)
KRC  : 한국농어촌공사 — 공지사항 (HTML table, page 페이지네이션, dataUid ID)
FIRA : 한국수산자원공단 — 공지사항 (HTML table, pager.offset 페이지네이션, article_no ID)
MOF  : 해양수산부 — 공지사항 (JS 렌더링 가능성 높음 — 0건 graceful fallback)
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
    r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품|청소|경비|보안|퇴직|임원|낙찰|유찰|보상|열람"
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
# 1. RDA (농촌진흥청) — 공지사항
#    https://www.rda.go.kr/board/board.do?mode=list&prgId=nei_ancmttEntry&currPage={page}
#    컬럼: 번호 | 제목(링크, dataNo파라미터) | 작성부서 | 담당자 | 등록일 | 조회
# ─────────────────────────────────────────────────────────────
_RDA_BASE = "https://www.rda.go.kr"
_RDA_LIST = (
    f"{_RDA_BASE}/board/board.do"
    "?mode=list&prgId=nei_ancmttEntry&currPage={{page}}"
)
_RDA_DATANO_RE = re.compile(r"dataNo=(\d+)")


class RDAScraper(BaseScraper):
    """농촌진흥원 — 공지사항/농업 지원사업 공모"""

    name = "rda"
    display_name = "농촌진흥청(RDA)"
    origin_url_prefix = f"{_RDA_BASE}/board/board.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 8):
            try:
                soup = _get(_RDA_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[rda] page {page} 실패: {e}")
                break

            rows = soup.select("table tbody tr")
            if not rows:
                break

            found_new = False
            for row in rows:
                link = row.select_one("a[href*='dataNo']")
                if not link:
                    continue
                href = link.get("href", "")
                dn_m = _RDA_DATANO_RE.search(href)
                if not dn_m:
                    continue
                data_no = dn_m.group(1)
                if data_no in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                cells = row.select("td")
                # 컬럼: 번호|제목|작성부서|담당자|등록일|조회
                date_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                posted = _parse_date(date_text)

                detail_url = (
                    _RDA_BASE + href if href.startswith("/") else
                    _RDA_BASE + "/" + href.lstrip("./") if href.startswith(".") else
                    href
                )

                seen.add(data_no)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {posted}" if posted else None,
                        "region": "전국",
                        "category": "농업",
                        "target_type": None,
                        "department": "농촌진흥청",
                    }
                )

            if not found_new:
                break
            time.sleep(0.4)

        logger.info(f"[rda] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(RDAScraper())


# ─────────────────────────────────────────────────────────────
# 2. KRC (한국농어촌공사) — 공지사항
#    https://www.ekr.or.kr/planweb/board/list.krc?boardUid=...&contentUid=...&page={page}
#    컬럼: 번호 | 제목(링크, dataUid파라미터) | 담당자 | 첨부 | 등록일 | 조회
# ─────────────────────────────────────────────────────────────
_KRC_BASE = "https://www.ekr.or.kr"
_KRC_BOARD_UID = "402880317cc0644a017cc5e8000f06b7"
_KRC_CONTENT_UID = "402880317cc0644a017cc0c9da9f0120"
_KRC_LIST = (
    f"{_KRC_BASE}/planweb/board/list.krc"
    f"?boardUid={_KRC_BOARD_UID}&contentUid={_KRC_CONTENT_UID}&page={{page}}"
)
_KRC_DATAUID_RE = re.compile(r"dataUid=([\w]+)")


class KRCScraper(BaseScraper):
    """한국농어촌공사 — 공지사항/농어촌 지원사업 공고"""

    name = "krc"
    display_name = "한국농어촌공사(KRC)"
    origin_url_prefix = f"{_KRC_BASE}/planweb/board"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 8):
            try:
                soup = _get(_KRC_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[krc] page {page} 실패: {e}")
                break

            rows = soup.select("table tbody tr")
            if not rows:
                break

            found_new = False
            for row in rows:
                link = row.select_one("a[href*='dataUid']")
                if not link:
                    continue
                href = link.get("href", "")
                uid_m = _KRC_DATAUID_RE.search(href)
                if not uid_m:
                    continue
                data_uid = uid_m.group(1)
                if data_uid in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                cells = row.select("td")
                # 컬럼: 번호|제목|담당자|첨부|등록일|조회
                date_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                posted = _parse_date(date_text)

                detail_url = (
                    f"{_KRC_BASE}/planweb/board/view.krc"
                    f"?dataUid={data_uid}"
                    f"&boardUid={_KRC_BOARD_UID}"
                    f"&contentUid={_KRC_CONTENT_UID}"
                )

                seen.add(data_uid)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {posted}" if posted else None,
                        "region": "전국",
                        "category": "농업",
                        "target_type": None,
                        "department": "한국농어촌공사",
                    }
                )

            if not found_new:
                break
            time.sleep(0.4)

        logger.info(f"[krc] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(KRCScraper())


# ─────────────────────────────────────────────────────────────
# 3. FIRA (한국수산자원공단) — 공지사항
#    http://www.fira.or.kr/newfira/web/news/news01_01.jsp?pager.offset={offset}
#    컬럼: 번호 | 제목(링크, article_no파라미터) | 작성자 | 등록일 | 첨부 | 조회
#    offset 단위: 10
# ─────────────────────────────────────────────────────────────
_FIRA_BASE = "http://www.fira.or.kr"
_FIRA_LIST_BASE = f"{_FIRA_BASE}/newfira/web/news/news01_01.jsp"
_FIRA_LIST = f"{_FIRA_LIST_BASE}?pager.offset={{offset}}"
_FIRA_ARTNO_RE = re.compile(r"article_no=(\d+)")


class FIRAScraper(BaseScraper):
    """한국수산자원공단 — 공지사항/수산 지원사업 공모"""

    name = "fira"
    display_name = "한국수산자원공단(FIRA)"
    origin_url_prefix = _FIRA_LIST_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(8):  # offset=0,10,...,70
            offset = page * 10
            try:
                soup = _get(_FIRA_LIST.format(offset=offset))
            except Exception as e:
                logger.warning(f"[fira] offset={offset} 실패: {e}")
                break

            rows = soup.select("table tbody tr")
            if not rows:
                break

            found_new = False
            for row in rows:
                link = row.select_one("a[href*='article_no']")
                if not link:
                    continue
                href = link.get("href", "")
                art_m = _FIRA_ARTNO_RE.search(href)
                if not art_m:
                    continue
                art_no = art_m.group(1)
                if art_no in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                cells = row.select("td")
                # 컬럼: 번호|제목|작성자|등록일|첨부|조회
                date_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                posted = _parse_date(date_text)

                detail_url = (
                    f"{_FIRA_LIST_BASE}?mode=view&article_no={art_no}&board_no=2"
                )

                seen.add(art_no)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {posted}" if posted else None,
                        "region": "전국",
                        "category": "수산",
                        "target_type": None,
                        "department": "한국수산자원공단",
                    }
                )

            if not found_new:
                break
            time.sleep(0.4)

        logger.info(f"[fira] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(FIRAScraper())


# ─────────────────────────────────────────────────────────────
# 4. MOF (해양수산부) — 공고
#    https://www.mof.go.kr/index.do?menuSeq=889
#    JS 렌더링 가능성 높음 → 0건 graceful fallback
# ─────────────────────────────────────────────────────────────
_MOF_BASE = "https://www.mof.go.kr"
_MOF_LIST = f"{_MOF_BASE}/index.do?menuSeq=889"


class MOFScraper(BaseScraper):
    """해양수산부 — 공고 (정적 HTML 파싱 시도)"""

    name = "mof"
    display_name = "해양수산부(MOF)"
    origin_url_prefix = _MOF_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        try:
            soup = _get(_MOF_LIST)
        except Exception as e:
            logger.warning(f"[mof] 접속 실패: {e}")
            return []

        rows = soup.select("table tbody tr, ul.board-list li")
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
                _MOF_BASE + href if href.startswith("/") else href
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
                    "region": "전국",
                    "category": "수산",
                    "target_type": None,
                    "department": "해양수산부",
                }
            )

        if not items:
            logger.info(
                "[mof] 정적 HTML 수집 0건 "
                "(JS 렌더링 가능성 — Playwright 전환 후 재구현 예정)"
            )
        else:
            logger.info(f"[mof] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(MOFScraper())
