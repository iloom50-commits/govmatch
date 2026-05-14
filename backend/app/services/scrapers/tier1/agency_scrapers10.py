"""광역시도청·R&D기관 스크래퍼 배치 10

광주광역시청  : 경제정책 게시판 (HTML table, BS4)
제주특별자치도 : 입법·고시·공고 게시판 (HTML table, BS4)
KISTEP        : 한국과학기술기획평가원 사업공모 (HTML table, BS4)
부산광역시청   : 기업지원 공고 (HTML table, BS4 — JS 렌더링 시 0건)
NRF           : 한국연구재단 사업공고 (HTML 시도 — AJAX 불가 시 0건)
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


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


# ─────────────────────────────────────────────────────────────
# 1. 광주광역시청 — 경제정책 게시판
#    /economy/boardList.do?pageId=economy7&boardId=BD_0000001719
#    컬럼: 번호 | 분류 | 제목(링크) | 작성자 | 작성일 | 파일 | 조회
# ─────────────────────────────────────────────────────────────
_GWANGJU_BASE = "https://www.gwangju.go.kr"
_GWANGJU_LIST = (
    f"{_GWANGJU_BASE}/economy/boardList.do"
    "?pageId=economy7&boardId=BD_0000001719&movePage={{page}}&recordCnt=10"
)
_GWANGJU_SEQ_RE = re.compile(r"seq=(\d+)")


class GwangjuScraper(BaseScraper):
    """광주광역시청 — 경제정책 게시판"""

    name = "gwangju_econ"
    display_name = "광주광역시청(경제정책)"
    origin_url_prefix = f"{_GWANGJU_BASE}/economy/boardView.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 8):
            try:
                soup = _get(_GWANGJU_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[gwangju_econ] page {page} 실패: {e}")
                break

            rows = soup.select("table tbody tr")
            if not rows:
                break

            found_new = False
            for row in rows:
                link = row.select_one("a[href*='boardView']")
                if not link:
                    continue
                href = link.get("href", "")
                seq_m = _GWANGJU_SEQ_RE.search(href)
                if not seq_m:
                    continue
                seq = seq_m.group(1)
                if seq in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                # 날짜: 작성일 컬럼 (td 텍스트에 "작성일 YYYY-MM-DD" 포함)
                date_text = " ".join(td.get_text(" ") for td in row.select("td"))
                deadline = _parse_date(date_text)

                # 상세 URL: seq 파라미터 포함 href 사용
                detail_url = (
                    _GWANGJU_BASE + href
                    if href.startswith("/")
                    else href
                )

                seen.add(seq)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {deadline}" if deadline else None,
                        "region": "광주",
                        "category": None,
                        "target_type": None,
                        "department": "광주광역시청",
                    }
                )

            if not found_new:
                break
            time.sleep(0.5)

        logger.info(f"[gwangju_econ] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(GwangjuScraper())


# ─────────────────────────────────────────────────────────────
# 2. 제주특별자치도청 — 입법·고시·공고
#    /news/news/law.htm
#    컬럼: 번호 | 제목(링크) | 새글 | 댓글 | 작성부서 | 작성일 | 조회
# ─────────────────────────────────────────────────────────────
_JEJU_BASE = "https://www.jeju.go.kr"
_JEJU_LAW_LIST = f"{_JEJU_BASE}/news/news/law.htm?curPage={{page}}"
_JEJU_SEQ_RE = re.compile(r"seq=(\d+)")

# 제주 전체공고(새소식)도 함께 수집
_JEJU_NEWS_LIST = f"{_JEJU_BASE}/news/news/news.htm?curPage={{page}}"


def _scrape_jeju_board(base_list_url: str, detail_base: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen: set = set()

    for page in range(1, 8):
        try:
            soup = _get(base_list_url.format(page=page))
        except Exception as e:
            logger.warning(f"[jeju_sido] page {page} 실패: {e}")
            break

        rows = soup.select("table tbody tr")
        if not rows:
            break

        found_new = False
        for row in rows:
            link = row.select_one("a[href*='act=view']")
            if not link:
                continue
            href = link.get("href", "")
            seq_m = _JEJU_SEQ_RE.search(href)
            if not seq_m:
                continue
            seq = seq_m.group(1)
            if seq in seen:
                continue

            title_text = link.get("title", "") or _clean(link.get_text())
            title = _clean(title_text)
            if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                continue

            # 날짜: 마지막에서 두번째 td (작성일)
            cells = row.select("td")
            date_text = cells[-2].get_text(" ") if len(cells) >= 2 else ""
            deadline = _parse_date(date_text)

            detail_url = (
                _JEJU_BASE + href if href.startswith("/") else href
            )

            seen.add(seq)
            found_new = True
            items.append(
                {
                    "title": title[:400],
                    "origin_url": detail_url,
                    "deadline_date": None,
                    "support_amount": None,
                    "summary_text": f"등록일: {deadline}" if deadline else None,
                    "region": "제주",
                    "category": None,
                    "target_type": None,
                    "department": "제주특별자치도청",
                }
            )

        if not found_new:
            break
        time.sleep(0.4)

    return items


class JejuScraper(BaseScraper):
    """제주특별자치도청 — 입법·고시·공고 + 도정소식"""

    name = "jeju_sido"
    display_name = "제주특별자치도청"
    origin_url_prefix = f"{_JEJU_BASE}/news/news"

    def fetch_items(self) -> List[Dict[str, Any]]:
        # 고시·공고 (법령·행정)
        law_items = _scrape_jeju_board(_JEJU_LAW_LIST, "law.htm")
        # 도정소식 (일반 공고)
        news_items = _scrape_jeju_board(_JEJU_NEWS_LIST, "news.htm")

        # URL 기준 중복 제거 후 합산
        seen_urls: set = set()
        all_items: List[Dict[str, Any]] = []
        for it in law_items + news_items:
            if it["origin_url"] not in seen_urls:
                seen_urls.add(it["origin_url"])
                all_items.append(it)

        logger.info(f"[jeju_sido] 수집: {len(all_items)}건 (법령{len(law_items)} + 소식{len(news_items)})")
        return all_items


SCRAPER_REGISTRY.append(JejuScraper())


# ─────────────────────────────────────────────────────────────
# 3. KISTEP (한국과학기술기획평가원) — 사업공모 게시판 (bid=0028)
#    /board.es?mid=a10303000000&bid=0028
#    컬럼: 번호 | 제목(링크) | 등록자 | 등록일 | 첨부 | 조회수
# ─────────────────────────────────────────────────────────────
_KISTEP_BASE = "https://www.kistep.re.kr"
_KISTEP_LIST = (
    f"{_KISTEP_BASE}/board.es"
    "?mid=a10303000000&bid=0028&b_list=10&act=list&nPage={{page}}"
)
_KISTEP_NO_RE = re.compile(r"list_no=(\d+)")


class KISTEPScraper(BaseScraper):
    """한국과학기술기획평가원 — 사업공모"""

    name = "kistep"
    display_name = "한국과학기술기획평가원(KISTEP)"
    origin_url_prefix = f"{_KISTEP_BASE}/board.es"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 8):
            try:
                soup = _get(_KISTEP_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[kistep] page {page} 실패: {e}")
                break

            rows = soup.select("table tbody tr")
            if not rows:
                break

            found_new = False
            for row in rows:
                link = row.select_one("a[href*='act=view']")
                if not link:
                    continue
                href = link.get("href", "")
                no_m = _KISTEP_NO_RE.search(href)
                if not no_m:
                    continue
                list_no = no_m.group(1)
                if list_no in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                cells = row.select("td")
                # 컬럼: 번호|제목|등록자|등록일|첨부|조회수
                date_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                deadline = _parse_date(date_text)

                detail_url = (
                    _KISTEP_BASE + href if href.startswith("/") else href
                )

                seen.add(list_no)
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
                        "department": "한국과학기술기획평가원",
                    }
                )

            if not found_new:
                break
            time.sleep(0.5)

        logger.info(f"[kistep] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(KISTEPScraper())


# ─────────────────────────────────────────────────────────────
# 4. 부산광역시청 — 기업지원 공고
#    /biz/index — JS 렌더링 가능성 높음, 수집 0건 시 로그만 기록
# ─────────────────────────────────────────────────────────────
_BUSAN_BASE = "https://www.busan.go.kr"
_BUSAN_LIST = f"{_BUSAN_BASE}/biz/index"
# 부산은 JS SPA 가능성이 높아, 정적 HTML tbody tr을 우선 파싱
# 이후 nbnews(공고) 게시판도 시도


class BusanScraper(BaseScraper):
    """부산광역시청 — 기업지원/공고 (정적 HTML 파싱 시도)"""

    name = "busan_city"
    display_name = "부산광역시청(직접)"
    origin_url_prefix = _BUSAN_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        # 시도할 게시판 URL 목록
        candidates = [
            f"{_BUSAN_BASE}/biz/index",
            f"{_BUSAN_BASE}/nbnews",
            f"{_BUSAN_BASE}/main/bbs?bbsNo=4",
        ]

        for list_url in candidates:
            try:
                soup = _get(list_url)
            except Exception:
                continue

            rows = soup.select("table tbody tr")
            for row in rows:
                link = row.select_one("a[href]")
                if not link:
                    continue
                href = link.get("href", "")
                if not href or href.startswith("javascript"):
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                detail_url = (
                    _BUSAN_BASE + href if href.startswith("/") else href
                )
                if detail_url in seen:
                    continue

                date_text = " ".join(td.get_text(" ") for td in row.select("td"))
                deadline = _parse_date(date_text)

                seen.add(detail_url)
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": detail_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"등록일: {deadline}" if deadline else None,
                        "region": "부산",
                        "category": None,
                        "target_type": None,
                        "department": "부산광역시청",
                    }
                )

            if items:
                break  # 첫 번째로 성공한 URL에서 수집한 데이터 사용
            time.sleep(0.4)

        if not items:
            logger.info(
                "[busan_city] 정적 HTML 수집 0건 "
                "(JS 렌더링 가능성 — Playwright 전환 후 재구현 예정)"
            )
        else:
            logger.info(f"[busan_city] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(BusanScraper())


# ─────────────────────────────────────────────────────────────
# 5. NRF (한국연구재단) — 사업공고
#    /biz/info/notice/list — 검색 폼 기반, 정적 목록 파싱 시도
# ─────────────────────────────────────────────────────────────
_NRF_BASE = "https://www.nrf.re.kr"
_NRF_LIST = f"{_NRF_BASE}/biz/info/notice/list"
_NRF_SEQ_RE = re.compile(r"(?:seq|no|id)=(\d+)", re.IGNORECASE)


class NRFScraper(BaseScraper):
    """한국연구재단 — 사업공고 (정적 파싱 시도)"""

    name = "nrf"
    display_name = "한국연구재단(NRF)"
    origin_url_prefix = _NRF_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        # NRF는 AJAX/form 기반이라 정적 HTML에 실제 목록이 없을 수 있음
        # page 파라미터로 시도
        for page in range(1, 5):
            url = f"{_NRF_LIST}?page={page}"
            try:
                soup = _get(url)
            except Exception as e:
                logger.warning(f"[nrf] page {page} 실패: {e}")
                break

            rows = soup.select("table tbody tr, ul.list li, div.list-item")
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

                detail_url = (
                    _NRF_BASE + href if href.startswith("/") else href
                )
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
                        "category": "R&D",
                        "target_type": None,
                        "department": "한국연구재단",
                    }
                )

            if not found_new:
                break
            time.sleep(0.5)

        if not items:
            logger.info(
                "[nrf] 정적 HTML 수집 0건 "
                "(AJAX form 기반 — 브라우저 API 엔드포인트 확인 후 재구현 예정)"
            )
        else:
            logger.info(f"[nrf] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(NRFScraper())
