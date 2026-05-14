"""공공기관 스크래퍼 배치 11 — KITA, INNOPOLIS, KCCI, KICOX

KITA      : 한국무역협회 — 진행 중 지원사업 (li.list-type 카드 파싱)
INNOPOLIS : 연구개발특구진흥재단 — 공지사항·사업공고 (table + li 파싱)
KCCI      : 대한상공회의소 — 공지사항 (SSL bypass, HTML table)
KICOX     : 한국산업단지공단 — 사업공고 (HTML table, JS 링크 재구성)
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
    "Referer": "https://www.google.com",
}
_EXCLUDE_KW = re.compile(
    r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품|청소|경비|보안|퇴직|임원|낙찰|유찰"
)
_DATE_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
_RANGE_TAIL_RE = re.compile(r"~\s*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})")


def _get(url: str, verify: bool = True, **kwargs) -> BeautifulSoup:
    resp = requests.get(url, headers=_HEADERS, timeout=20, verify=verify, **kwargs)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return BeautifulSoup(resp.text, "html.parser")


def _parse_date(text: str) -> str | None:
    dates = _DATE_RE.findall(text or "")
    if not dates:
        return None
    y, m, d = dates[-1]
    return f"{y}-{m.zfill(2)}-{d.zfill(2)}"


def _deadline_from_range(text: str) -> str | None:
    """'시작 ~ 마감' 패턴에서 마감일 추출."""
    m = _RANGE_TAIL_RE.search(text or "")
    if m:
        return _parse_date(m.group(1))
    return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


# ─────────────────────────────────────────────────────────────
# 1. KITA (한국무역협회) — 진행 중 지원사업 목록
#    https://www.kita.net/cmmrcInfo/cmmrcNews/cmmrcNews/list.do
#    카드 구조: ul.list-type.line-st > li > p.subject > a[onclick]
# ─────────────────────────────────────────────────────────────
_KITA_BASE = "https://www.kita.net"
_KITA_LIST = f"{_KITA_BASE}/cmmrcInfo/cmmrcNews/cmmrcNews/list.do?curPage={{page}}"
_KITA_GOPAGE_RE = re.compile(r"global\.goPage\(['\"]([^'\"]+)['\"]")


class KITAScraper(BaseScraper):
    """한국무역협회 — 지원사업/교육/포럼 공고"""

    name = "kita"
    display_name = "한국무역협회(KITA)"
    origin_url_prefix = _KITA_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_KITA_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[kita] page {page} 실패: {e}")
                break

            card_list = soup.select("ul.list-type li, ul.list-type-line li")
            if not card_list:
                # 대안 셀렉터
                card_list = soup.select("li.swiper-slide") or soup.select("li")

            found_new = False
            for li in card_list:
                subj_a = li.select_one("p.subject a, .subject a")
                if not subj_a:
                    continue

                title = _clean(
                    subj_a.get("title", "") or subj_a.get_text()
                )
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                # URL: onclick에서 경로 추출
                onclick = subj_a.get("onclick", "")
                path_m = _KITA_GOPAGE_RE.search(onclick)
                if not path_m:
                    href = subj_a.get("href", "")
                    if not href or href.startswith("javascript"):
                        continue
                    detail_url = _KITA_BASE + href if href.startswith("/") else href
                else:
                    path = path_m.group(1)
                    detail_url = _KITA_BASE + path if path.startswith("/") else path

                if detail_url in seen:
                    continue

                # 마감일: dateinfo span에서 "~ YYYY.MM.DD" 패턴
                deadline = None
                for info in li.select("p.dateinfo span.font-numbers"):
                    t = info.get_text()
                    dl = _deadline_from_range(t) or _parse_date(t)
                    if dl:
                        deadline = dl
                        break

                seen.add(detail_url)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": deadline,
                        "support_amount": None,
                        "summary_text": None,
                        "region": "전국",
                        "category": "수출",
                        "target_type": "business",
                        "department": "한국무역협회",
                    }
                )

            if not found_new:
                break
            time.sleep(0.5)

        logger.info(f"[kita] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(KITAScraper())


# ─────────────────────────────────────────────────────────────
# 2. INNOPOLIS (연구개발특구진흥재단) — 공지사항 + 사업공고
#    공지: /board?menuId=MENU00318  (table tbody tr)
#    사업: /newBusiness?menuId=MENU01028 (ul li)
# ─────────────────────────────────────────────────────────────
_INNO_BASE = "https://www.innopolis.or.kr"
_INNO_NOTICE = (
    f"{_INNO_BASE}/board"
    "?menuId=MENU00318&siteId=null&pageNum={{page}}&rowCnt=10"
)
_INNO_BIZ = f"{_INNO_BASE}/newBusiness?menuId=MENU01028"
_INNO_VIEW_RE = re.compile(r"no1=(\d+).*?linkId=(\d+)", re.DOTALL)


def _inno_notice_items() -> List[Dict[str, Any]]:
    """INNOPOLIS 공지사항 게시판 수집 (table)."""
    items: List[Dict[str, Any]] = []
    seen: set = set()

    for page in range(1, 6):
        try:
            soup = _get(_INNO_NOTICE.format(page=page))
        except Exception as e:
            logger.warning(f"[innopolis] notice page {page} 실패: {e}")
            break

        rows = soup.select("table tbody tr")
        if not rows:
            break

        found_new = False
        for row in rows:
            link = row.select_one("a[href]")
            if not link:
                continue
            href = link.get("href", "")
            if not href or href == "#" or "javascript" in href:
                continue

            title = _clean(link.get_text())
            if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                continue

            detail_url = _INNO_BASE + href if href.startswith("/") else href
            if detail_url in seen:
                continue

            cells = row.select("td")
            # 컬럼: 번호 | 제목(link) | 작성자 | 등록일 | 조회수 | 첨부
            date_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            deadline = _parse_date(date_text)

            seen.add(detail_url)
            found_new = True
            items.append(
                {
                    "title": title[:400],
                    "origin_url": detail_url,
                    "deadline_date": None,
                    "support_amount": None,
                    "summary_text": f"등록일: {deadline}" if deadline else None,
                    "region": "전국",
                    "category": "R&D",
                    "target_type": None,
                    "department": "연구개발특구진흥재단",
                }
            )

        if not found_new:
            break
        time.sleep(0.4)

    return items


def _inno_biz_items() -> List[Dict[str, Any]]:
    """INNOPOLIS 사업공고 li 목록 수집."""
    items: List[Dict[str, Any]] = []
    seen: set = set()

    try:
        soup = _get(_INNO_BIZ)
    except Exception as e:
        logger.warning(f"[innopolis] 사업공고 실패: {e}")
        return []

    for li in soup.select("li a[href*='board/view']"):
        href = li.get("href", "")
        if not href:
            continue
        detail_url = _INNO_BASE + href if href.startswith("/") else href
        if detail_url in seen:
            continue

        strong = li.select_one("strong")
        title = _clean(strong.get_text() if strong else li.get_text())
        if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
            continue

        # 날짜: li 텍스트에 "YYYY-MM-DD~YYYY-MM-DD" 포함
        full_text = li.get_text(" ")
        deadline = _deadline_from_range(full_text) or _parse_date(full_text)

        seen.add(detail_url)
        items.append(
            {
                "title": title[:400],
                "origin_url": detail_url,
                "deadline_date": deadline,
                "support_amount": None,
                "summary_text": None,
                "region": "전국",
                "category": "R&D",
                "target_type": "business",
                "department": "연구개발특구진흥재단",
            }
        )

    return items


class InnopolisScraper(BaseScraper):
    """연구개발특구진흥재단 — 공지사항 + 사업공고"""

    name = "innopolis"
    display_name = "연구개발특구진흥재단(INNOPOLIS)"
    origin_url_prefix = _INNO_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        notice = _inno_notice_items()
        biz = _inno_biz_items()

        seen_urls: set = set()
        all_items: List[Dict[str, Any]] = []
        for it in biz + notice:
            if it["origin_url"] not in seen_urls:
                seen_urls.add(it["origin_url"])
                all_items.append(it)

        logger.info(f"[innopolis] 수집: {len(all_items)}건 (공지{len(notice)} + 사업{len(biz)})")
        return all_items


SCRAPER_REGISTRY.append(InnopolisScraper())


# ─────────────────────────────────────────────────────────────
# 3. KCCI (대한상공회의소) — 공지사항
#    SSL 인증서 문제로 verify=False 필요
#    https://www.kcci.or.kr/front/news/notice/noticeList.do
# ─────────────────────────────────────────────────────────────
_KCCI_BASE = "https://www.kcci.or.kr"
_KCCI_LIST = f"{_KCCI_BASE}/front/news/notice/noticeList.do?pageIndex={{page}}"
_KCCI_SEQ_RE = re.compile(r"(?:nttSn|noticeNo|seq)=(\d+)", re.IGNORECASE)


class KCCIScraper(BaseScraper):
    """대한상공회의소 — 공지사항 (SSL bypass)"""

    name = "kcci"
    display_name = "대한상공회의소(KCCI)"
    origin_url_prefix = _KCCI_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        import warnings as _w
        import urllib3 as _u3
        _u3.disable_warnings(_u3.exceptions.InsecureRequestWarning)

        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_KCCI_LIST.format(page=page), verify=False)
            except Exception as e:
                logger.warning(f"[kcci] page {page} 실패: {e}")
                break

            rows = soup.select("table tbody tr")
            if not rows:
                break

            found_new = False
            for row in rows:
                link = row.select_one("a[href]")
                if not link:
                    continue
                href = link.get("href", "")
                if not href or "javascript" in href:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                detail_url = _KCCI_BASE + href if href.startswith("/") else href
                if detail_url in seen:
                    continue

                row_text = row.get_text(" ")
                deadline = _parse_date(row_text)

                seen.add(detail_url)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {deadline}" if deadline else None,
                        "region": "전국",
                        "category": None,
                        "target_type": "business",
                        "department": "대한상공회의소",
                    }
                )

            if not found_new:
                break
            time.sleep(0.4)

        if not items:
            logger.info("[kcci] SSL/구조 문제로 수집 0건 (URL 재확인 필요)")
        else:
            logger.info(f"[kcci] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(KCCIScraper())


# ─────────────────────────────────────────────────────────────
# 4. KICOX (한국산업단지공단) — 사업공고
#    https://www.kicox.or.kr/boardList/1016
#    링크: href="#none" (JS 렌더링) → 제목+날짜만 추출, URL은 패턴 추정
# ─────────────────────────────────────────────────────────────
_KICOX_BASE = "https://www.kicox.or.kr"
_KICOX_LIST = f"{_KICOX_BASE}/boardList/1016?page={{page}}"
_KICOX_NO_RE = re.compile(r"data-no=['\"]?(\d+)['\"]?|/(\d+)$", re.IGNORECASE)


class KICOXScraper(BaseScraper):
    """한국산업단지공단 — 사업공고 (제목+날짜 수집, 상세 URL 패턴 추정)"""

    name = "kicox"
    display_name = "한국산업단지공단(KICOX)"
    origin_url_prefix = _KICOX_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_KICOX_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[kicox] page {page} 실패: {e}")
                break

            rows = soup.select("table tbody tr")
            if not rows:
                break

            found_new = False
            for idx, row in enumerate(rows):
                # 링크 셀 (제목): href="#none" 또는 실제 href
                link = row.select_one("a")
                if not link:
                    continue

                title = _clean(link.get("title", "") or link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                # 실제 href 우선, 없으면 data-no 또는 row index 기반 URL 생성
                href = link.get("href", "")
                if href and href != "#" and "javascript" not in href:
                    detail_url = _KICOX_BASE + href if href.startswith("/") else href
                else:
                    # data-no 속성 또는 row의 onclick에서 ID 추출 시도
                    no_m = _KICOX_NO_RE.search(str(row))
                    if no_m:
                        no = no_m.group(1) or no_m.group(2)
                        detail_url = f"{_KICOX_BASE}/boardDetail/1016/{no}"
                    else:
                        # fallback: 리스트 URL + 제목 해시 (유일성 보장용)
                        import hashlib
                        title_hash = hashlib.md5(title.encode()).hexdigest()[:8]
                        detail_url = f"{_KICOX_BASE}/boardList/1016#{title_hash}"

                if detail_url in seen:
                    continue

                cells = row.select("td")
                date_text = " ".join(c.get_text(" ") for c in cells)
                deadline = _parse_date(date_text)

                seen.add(detail_url)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {deadline}" if deadline else None,
                        "region": "전국",
                        "category": "산업단지",
                        "target_type": "business",
                        "department": "한국산업단지공단",
                    }
                )

            if not found_new:
                break
            time.sleep(0.4)

        if not items:
            logger.info("[kicox] 수집 0건 (JS 렌더링 또는 URL 변경)")
        else:
            logger.info(f"[kicox] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(KICOXScraper())
