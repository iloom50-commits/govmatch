"""광역시도청 사업공고 스크래퍼 — requests 기반

정상 수집 (9개):
  대전시청  daejeon.go.kr        소상공인 지원 게시판
  울산시청  ulsan.go.kr          고시공고
  강원도청  state.gwd.go.kr      공고/고시 (onclick goPage)
  충북도청  ebizcb.chungbuk.go.kr 창업·기업 지원사업
  충남도청  cnsp.or.kr           지원사업 공고
  전북도청  jeonbuk.go.kr        공고/고시
  전남도청  jeonnam.go.kr        기업지원 자금지원
  경남도청  gyeongnam.go.kr      고시공고
  서울시청  seoulboard.seoul.go.kr RSS feed (bbsNo=277)
  부산경제진흥원 bepa.kr          사업공고(no=1502)·중소기업공고(no=1505), verify=False

Playwright 필요 (로컬 전용 — 향후 agency_scrapers_pw.py에 추가):
  대구시청  JS 렌더링
  경기도청  JS 렌더링
  경북도청  JS 렌더링
  인천시청  bizok.incheon.go.kr  JS 렌더링 (rows=0)
  세종시청  sejong.go.kr         JS 링크 (nttId HTML 미포함)
  광주시청  gwangju.go.kr        JS 렌더링 (테이블 없음, requests 불가)
"""
from __future__ import annotations
import re
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from typing import List, Dict, Any
import warnings

from .base import BaseScraper, SCRAPER_REGISTRY

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_EXCLUDE_KW = re.compile(
    r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품|청소|경비|보안|퇴직|임원|고용공고"
)
_DATE_RE = re.compile(r"(\d{4})[.\-/년](\d{1,2})[.\-/월](\d{1,2})")


def _get(url: str, verify: bool = True, **kwargs) -> BeautifulSoup:
    resp = requests.get(url, headers=_HEADERS, timeout=20, verify=verify, **kwargs)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def _parse_date(text: str) -> str | None:
    """텍스트에서 날짜 추출 — 범위이면 마지막 날짜(마감일) 반환."""
    dates = _DATE_RE.findall(text or "")
    if not dates:
        return None
    y, m, d = dates[-1]
    return f"{y}-{m.zfill(2)}-{d.zfill(2)}"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_rows(soup: BeautifulSoup) -> list:
    """table tbody tr 패턴으로 행 추출."""
    tbody = soup.select_one("table tbody")
    if tbody:
        return tbody.select("tr")
    return soup.select("table tr")


# ─────────────────────────────────────────────────────────────
# 1. 인천광역시 — BizOK 기업지원 신청 포털
# ─────────────────────────────────────────────────────────────
_INCHEON_BASE = "https://bizok.incheon.go.kr"
_INCHEON_LIST = f"{_INCHEON_BASE}/open_content/support.do?act=list&pgno={{page}}"
_INCHEON_ID_RE = re.compile(r"policyno=(\d+)")


class IncheonScraper(BaseScraper):
    name = "incheon_sido"
    display_name = "인천광역시청(BizOK)"
    origin_url_prefix = f"{_INCHEON_BASE}/open_content/support.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_INCHEON_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for row in _extract_rows(soup):
                link = row.select_one("a[href*='policyno']")
                if not link:
                    continue
                m = _INCHEON_ID_RE.search(link.get("href", ""))
                if not m:
                    continue
                pid = m.group(1)
                if pid in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                seen.add(pid)
                found_new = True
                row_text = row.get_text(" ")

                items.append({
                    "title": title[:400],
                    "origin_url": f"{_INCHEON_BASE}/open_content/support.do?act=detail&policyno={pid}",
                    "region": "인천",
                    "target_type": None,
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_date(row_text),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


# IncheonScraper: JS 렌더링 필요 → 현재 비활성 (Playwright 전환 시 활성화)
# SCRAPER_REGISTRY.append(IncheonScraper())


# ─────────────────────────────────────────────────────────────
# 2. 대전광역시 — 소상공인 지원 게시판
# ─────────────────────────────────────────────────────────────
_DAEJEON_BASE = "https://www.daejeon.go.kr"
_DAEJEON_LIST = (
    f"{_DAEJEON_BASE}/drh/board/boardNormalList.do"
    "?boardId=normal_0189&menuSeq=1632&pageIndex={page}&recordCountPerPage=10"
)
_DAEJEON_ID_RE = re.compile(r"ntatcSeq=(\d+)")


class DaejeonScraper(BaseScraper):
    name = "daejeon_sido"
    display_name = "대전광역시청"
    origin_url_prefix = f"{_DAEJEON_BASE}/drh/board/boardNormalView.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_DAEJEON_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for row in _extract_rows(soup):
                link = row.select_one("a[href*='ntatcSeq']")
                if not link:
                    continue
                m = _DAEJEON_ID_RE.search(link.get("href", ""))
                if not m:
                    continue
                nid = m.group(1)
                if nid in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                seen.add(nid)
                found_new = True
                row_text = row.get_text(" ")

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_DAEJEON_BASE}/drh/board/boardNormalView.do"
                        f"?boardId=normal_0189&menuSeq=1632&pageIndex={page}&ntatcSeq={nid}"
                    ),
                    "region": "대전",
                    "target_type": None,
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_date(row_text),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(DaejeonScraper())


# ─────────────────────────────────────────────────────────────
# 3. 울산광역시 — 고시공고 게시판
# ─────────────────────────────────────────────────────────────
_ULSAN_BASE = "https://www.ulsan.go.kr"
_ULSAN_LIST = (
    f"{_ULSAN_BASE}/u/rep/contents.ulsan"
    "?mId=001004002000000000&curPage={page}"
)
_ULSAN_ID_RE = re.compile(r"(\d+)\.ulsan")


class UlsanScraper(BaseScraper):
    name = "ulsan_sido"
    display_name = "울산광역시청"
    origin_url_prefix = f"{_ULSAN_BASE}/u/rep/"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_ULSAN_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for row in _extract_rows(soup):
                link = row.select_one("a[href]")
                if not link:
                    continue
                href = link.get("href", "")
                m = _ULSAN_ID_RE.search(href)
                if not m:
                    continue
                uid = m.group(1)
                if uid in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                seen.add(uid)
                found_new = True
                row_text = row.get_text(" ")

                detail_url = (
                    f"{_ULSAN_BASE}/u/rep/{uid}.ulsan?mId=001004002000000000"
                    if not href.startswith("http")
                    else href
                )

                items.append({
                    "title": title[:400],
                    "origin_url": detail_url,
                    "region": "울산",
                    "target_type": None,
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_date(row_text),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(UlsanScraper())


# ─────────────────────────────────────────────────────────────
# 4. 세종특별자치시 — 공지사항 게시판
# ─────────────────────────────────────────────────────────────
_SEJONG_BASE = "https://www.sejong.go.kr"
_SEJONG_LIST = f"{_SEJONG_BASE}/bbs/R0071/list.do?pageIndex={{page}}"
_SEJONG_ID_RE = re.compile(r"nttId=(\d+)")


class SejongScraper(BaseScraper):
    name = "sejong_sido"
    display_name = "세종특별자치시청"
    origin_url_prefix = f"{_SEJONG_BASE}/bbs/R0071/view.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_SEJONG_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for row in _extract_rows(soup):
                link = row.select_one("a[href*='nttId']")
                if not link:
                    continue
                m = _SEJONG_ID_RE.search(link.get("href", ""))
                if not m:
                    continue
                nid = m.group(1)
                if nid in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                seen.add(nid)
                found_new = True
                row_text = row.get_text(" ")

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_SEJONG_BASE}/bbs/R0071/view.do"
                        f"?nttId={nid}&mno=sub02_01&pageIndex={page}"
                    ),
                    "region": "세종",
                    "target_type": None,
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_date(row_text),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


# SejongScraper: 링크가 javascript:void(0), nttId HTML에 없음 → 비활성
# SCRAPER_REGISTRY.append(SejongScraper())


# ─────────────────────────────────────────────────────────────
# 5. 강원특별자치도 — 공고/고시 게시판
# ─────────────────────────────────────────────────────────────
_GANGWON_BASE = "https://state.gwd.go.kr"
_GANGWON_LIST = f"{_GANGWON_BASE}/portal/bulletin/notification?page={{page}}"
_GANGWON_ONCLICK_RE = re.compile(r"goPage\((\d+)\)")


class GangwonScraper(BaseScraper):
    name = "gangwon_sido"
    display_name = "강원특별자치도청"
    origin_url_prefix = f"{_GANGWON_BASE}/portal/bulletin/notification/"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_GANGWON_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for row in _extract_rows(soup):
                link = row.select_one("a")
                if not link:
                    continue
                # href="#nolink" + onclick="goPage(ID)" 방식
                onclick = link.get("onclick", "") or row.get("onclick", "")
                m = _GANGWON_ONCLICK_RE.search(onclick)
                if not m:
                    # fallback: href에 숫자 ID 있는 경우
                    href = link.get("href", "")
                    m2 = re.search(r"/notification/(\d+)", href)
                    if not m2:
                        continue
                    aid = m2.group(1)
                else:
                    aid = m.group(1)

                if aid in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                seen.add(aid)
                found_new = True
                row_text = row.get_text(" ")

                items.append({
                    "title": title[:400],
                    "origin_url": f"{_GANGWON_BASE}/portal/bulletin/notification/{aid}",
                    "region": "강원",
                    "target_type": None,
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_date(row_text),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(GangwonScraper())


# ─────────────────────────────────────────────────────────────
# 6. 충청북도 — e기업사랑센터 지원사업 공고
# ─────────────────────────────────────────────────────────────
_CHUNGBUK_BASE = "https://ebizcb.chungbuk.go.kr"
_CHUNGBUK_LIST = (
    f"{_CHUNGBUK_BASE}/plc/selectPolicyInf.do"
    "?menuId=MNU_0000000000000081&grpCode=PLCG_FOUND&pageIndex={page}"
)
_CHUNGBUK_ID_RE = re.compile(r"plcInfId=([\w\-]+)")


class ChungbukScraper(BaseScraper):
    name = "chungbuk_sido"
    display_name = "충청북도청(e기업사랑센터)"
    origin_url_prefix = f"{_CHUNGBUK_BASE}/plc/selectPolicyInf.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()
        session = requests.Session()
        session.headers.update(_HEADERS)

        for page in range(1, 6):
            try:
                resp = session.get(_CHUNGBUK_LIST.format(page=page), timeout=20)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
            except Exception:
                break

            found_new = False
            for row in _extract_rows(soup):
                link = row.select_one("a[href*='plcInfId']")
                if not link:
                    continue
                m = _CHUNGBUK_ID_RE.search(link.get("href", ""))
                if not m:
                    continue
                pid = m.group(1)
                if pid in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                seen.add(pid)
                found_new = True
                row_text = row.get_text(" ")

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_CHUNGBUK_BASE}/plc/selectPolicyInf.do"
                        f"?menuId=MNU_0000000000000081&grpCode=PLCG_FOUND"
                        f"&pageIndex={page}&plcInfId={pid}"
                    ),
                    "region": "충북",
                    "target_type": None,
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_date(row_text),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(ChungbukScraper())


# ─────────────────────────────────────────────────────────────
# 7. 충청남도 — 충남 지원사업 통합관리시스템 (cnsp.or.kr)
# ─────────────────────────────────────────────────────────────
_CHUNGNAM_BASE = "https://www.cnsp.or.kr"
_CHUNGNAM_LIST = f"{_CHUNGNAM_BASE}/project/list.do?pn={{page}}"
_CHUNGNAM_ID_RE = re.compile(r"seq=(\d+)")


class ChungnamScraper(BaseScraper):
    name = "chungnam_sido"
    display_name = "충청남도청(CNSP)"
    origin_url_prefix = f"{_CHUNGNAM_BASE}/project/view.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_CHUNGNAM_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for row in _extract_rows(soup):
                link = row.select_one("a[href*='seq']") or row.select_one("a[href*='view']")
                if not link:
                    continue
                href = link.get("href", "")
                m = _CHUNGNAM_ID_RE.search(href)
                if not m:
                    continue
                sid = m.group(1)
                if sid in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                seen.add(sid)
                found_new = True
                row_text = row.get_text(" ")

                items.append({
                    "title": title[:400],
                    "origin_url": f"{_CHUNGNAM_BASE}/project/view.do?seq={sid}&pn={page}",
                    "region": "충남",
                    "target_type": None,
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_date(row_text),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(ChungnamScraper())


# ─────────────────────────────────────────────────────────────
# 8. 전북특별자치도 — 공고/고시 게시판
# ─────────────────────────────────────────────────────────────
_JEONBUK_BASE = "https://www.jeonbuk.go.kr"
_JEONBUK_LIST = (
    f"{_JEONBUK_BASE}/board/list.jeonbuk"
    "?boardId=BBS_0000129&menuCd=DOM_000000102002005000&paging=ok&startPage={page}&listRow=10"
)
_JEONBUK_ID_RE = re.compile(r"dataSid=(\d+)")


class JeonbukScraper(BaseScraper):
    name = "jeonbuk_sido"
    display_name = "전북특별자치도청"
    origin_url_prefix = f"{_JEONBUK_BASE}/board/view.jeonbuk"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_JEONBUK_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for row in _extract_rows(soup):
                link = row.select_one("a[href*='dataSid']")
                if not link:
                    continue
                m = _JEONBUK_ID_RE.search(link.get("href", ""))
                if not m:
                    continue
                did = m.group(1)
                if did in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                seen.add(did)
                found_new = True
                row_text = row.get_text(" ")

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_JEONBUK_BASE}/board/view.jeonbuk"
                        f"?boardId=BBS_0000129&menuCd=DOM_000000102002005000"
                        f"&dataSid={did}&paging=ok&startPage={page}"
                    ),
                    "region": "전북",
                    "target_type": None,
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_date(row_text),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(JeonbukScraper())


# ─────────────────────────────────────────────────────────────
# 9. 전라남도 — 기업지원 자금지원 게시판
# ─────────────────────────────────────────────────────────────
_JEONNAM_BASE = "https://www.jeonnam.go.kr"
_JEONNAM_LIST = (
    f"{_JEONNAM_BASE}/M5918/boardList.do"
    "?menuId=jeonnam0501030100&pageIndex={page}"
)
_JEONNAM_ID_RE = re.compile(r"seq=(\d+)")


class JeonnamScraper(BaseScraper):
    name = "jeonnam_sido"
    display_name = "전라남도청"
    origin_url_prefix = f"{_JEONNAM_BASE}/M5918/boardView.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_JEONNAM_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for row in _extract_rows(soup):
                link = row.select_one("a[href*='seq']") or row.select_one("a[href*='boardView']")
                if not link:
                    continue
                href = link.get("href", "")
                m = _JEONNAM_ID_RE.search(href)
                if not m:
                    continue
                sid = m.group(1)
                if sid in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                seen.add(sid)
                found_new = True
                row_text = row.get_text(" ")

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_JEONNAM_BASE}/M5918/boardView.do"
                        f"?seq={sid}&menuId=jeonnam0501030100&pageIndex={page}"
                    ),
                    "region": "전남",
                    "target_type": None,
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_date(row_text),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(JeonnamScraper())


# ─────────────────────────────────────────────────────────────
# 10. 경상남도 — 고시공고 게시판
# ─────────────────────────────────────────────────────────────
_GYEONGNAM_BASE = "https://www.gyeongnam.go.kr"
_GYEONGNAM_LIST = (
    "https://www.gyeongnam.go.kr/index.gyeong"
    "?menuCd=DOM_000000135003009001&page={page}&pageLine=10&gosiGbn=A"
)
_GYEONGNAM_ID_RE = re.compile(r"sno=(\d+)")


class GyeongnamScraper(BaseScraper):
    name = "gyeongnam_sido"
    display_name = "경상남도청"
    origin_url_prefix = f"{_GYEONGNAM_BASE}/index.gyeong?menuCd=DOM_000000135003009001&mode=view"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_GYEONGNAM_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for row in _extract_rows(soup):
                link = row.select_one("a[href*='sno']")
                if not link:
                    continue
                m = _GYEONGNAM_ID_RE.search(link.get("href", ""))
                if not m:
                    continue
                sno = m.group(1)
                if sno in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                seen.add(sno)
                found_new = True
                row_text = row.get_text(" ")

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_GYEONGNAM_BASE}/index.gyeong"
                        f"?menuCd=DOM_000000135003009001&mode=view&sno={sno}&gosiGbn=A"
                    ),
                    "region": "경남",
                    "target_type": None,
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_date(row_text),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(GyeongnamScraper())


# ─────────────────────────────────────────────────────────────
# 11. 부산경제진흥원(BEPA) — 사업공고(no=1502)·중소기업 공고(no=1505)
#     SSL 인증서 불완전 → verify=False. 글 고유ID는 idx(no는 게시판ID),
#     state=end(마감) 제외. origin_url은 가변 state 파라미터를 빼 정규화(재저장 방지).
#     ※ 부산'시청'(busan_city, agency_scrapers10.py)과는 별개 기관 — 혼동 금지.
# ─────────────────────────────────────────────────────────────
_BEPA_BASE = "https://www.bepa.kr"
_BEPA_BOARDS = (1502, 1505)
_BEPA_LIST = f"{_BEPA_BASE}/kor/view.do?no={{board}}&pageIndex={{page}}"
_BEPA_IDX_RE = re.compile(r"[?&]idx=(\d+)")
_BEPA_STATE_RE = re.compile(r"[?&]state=(\w+)")


class BepaScraper(BaseScraper):
    name = "busan_bepa"
    display_name = "부산경제진흥원(BEPA)"
    origin_url_prefix = f"{_BEPA_BASE}/kor/view.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()  # 게시판 간 idx 공유 dedup
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # InsecureRequestWarning 억제
            for board in _BEPA_BOARDS:
                for page in range(1, 4):
                    try:
                        soup = _get(_BEPA_LIST.format(board=board, page=page), verify=False)
                    except Exception:
                        break
                    new_items = self._parse_board(soup, board, seen)
                    if not new_items:
                        break  # 페이지네이션 미지원/끝 — 반복 시 자동 종료
                    items.extend(new_items)
        return items

    def _parse_board(self, soup, board: int, seen: set) -> List[Dict[str, Any]]:
        """게시판 뷰 HTML에서 글 링크(idx) 추출 — 순수 파서(픽스처 단위테스트 대상)."""
        out: List[Dict[str, Any]] = []
        for link in soup.select("a[href*='idx=']"):
            href = link.get("href", "")
            m = _BEPA_IDX_RE.search(href)
            if not m:
                continue
            idx = m.group(1)
            if idx in seen:
                continue
            sm = _BEPA_STATE_RE.search(href)
            if sm and sm.group(1) == "end":
                continue  # 마감 공고 제외
            title = _clean(link.get_text())
            if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                continue
            seen.add(idx)
            # 목록에는 마감일 컬럼이 없음(날짜열은 '등록일'). 개폐는 state로 판정하고
            # 마감일은 미상(None)으로 둔다 — 등록일을 마감일로 저장하면 base.run()이
            # 진행중 공고를 '마감 지남'으로 오판해 스킵함. 실제 마감일은 하위 파이프라인 보강.
            out.append({
                "title": title[:400],
                "origin_url": f"{_BEPA_BASE}/kor/view.do?no={board}&idx={idx}&view=view",
                "region": "부산",
                "target_type": None,
                "category": None,
                "summary_text": None,
                "deadline_date": None,
                "support_amount": None,
            })
        return out


SCRAPER_REGISTRY.append(BepaScraper())


# ─────────────────────────────────────────────────────────────
# 12. 광주광역시 — 공지사항 게시판 (BD_0000000022)
# ─────────────────────────────────────────────────────────────
_GWANGJU_BASE = "https://www.gwangju.go.kr"
_GWANGJU_LIST = (
    f"{_GWANGJU_BASE}/boardList.do"
    "?boardId=BD_0000000022&pageId=www788&movePage={page}&recordCnt=10"
)
_GWANGJU_ID_RE = re.compile(r"seq=(\d+)")


class GwangjuScraper(BaseScraper):
    name = "gwangju_sido"
    display_name = "광주광역시청"
    origin_url_prefix = f"{_GWANGJU_BASE}/boardView.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            try:
                soup = _get(_GWANGJU_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for row in _extract_rows(soup):
                link = row.select_one("a[href*='seq']") or row.select_one("a[href*='boardView']")
                if not link:
                    continue
                href = link.get("href", "")
                m = _GWANGJU_ID_RE.search(href)
                if not m:
                    continue
                sid = m.group(1)
                if sid in seen:
                    continue

                title = _clean(link.get_text())
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                seen.add(sid)
                found_new = True
                row_text = row.get_text(" ")

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_GWANGJU_BASE}/boardView.do"
                        f"?pageId=www788&boardId=BD_0000000022&seq={sid}"
                        f"&movePage={page}&recordCnt=10"
                    ),
                    "region": "광주",
                    "target_type": None,
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_date(row_text),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


# GwangjuScraper: JS 렌더링 필요 (테이블 0개) → 비활성
# SCRAPER_REGISTRY.append(GwangjuScraper())


# ─────────────────────────────────────────────────────────────
# 13. 서울특별시 — RSS 피드 (bbsNo=277, 기업지원 공고)
# ─────────────────────────────────────────────────────────────
_SEOUL_RSS_URL = "https://seoulboard.seoul.go.kr/rss/RSSGenerator?bbsNo=277"
_SEOUL_DATE_RE = re.compile(
    r"(\w{3}),\s+(\d{1,2})\s+(\w{3})\s+(\d{4})"
)
_MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}


def _parse_rss_date(pub_date: str) -> str | None:
    """'Mon, 12 May 2025 09:00:00 +0900' 형식 파싱 → 'YYYY-MM-DD'."""
    m = _SEOUL_DATE_RE.search(pub_date or "")
    if not m:
        return None
    _, day, mon, year = m.groups()
    month_num = _MONTH_MAP.get(mon)
    if not month_num:
        return None
    return f"{year}-{month_num}-{day.zfill(2)}"


class SeoulRssScraper(BaseScraper):
    name = "seoul_sido"
    display_name = "서울특별시청(RSS)"
    origin_url_prefix = "https://seoulboard.seoul.go.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        try:
            resp = requests.get(_SEOUL_RSS_URL, headers=_HEADERS, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception:
            return items

        ns = {}
        channel = root.find("channel")
        if channel is None:
            return items

        for item_el in channel.findall("item"):
            title_el = item_el.find("title")
            link_el = item_el.find("link")
            pub_el = item_el.find("pubDate")

            if title_el is None or link_el is None:
                continue

            title = _clean(title_el.text or "")
            link = (link_el.text or "").strip()

            if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                continue
            if link in seen:
                continue

            seen.add(link)
            pub_date = _parse_rss_date(pub_el.text if pub_el is not None else "")

            items.append({
                "title": title[:400],
                "origin_url": link,
                "region": "서울",
                "target_type": None,
                "category": None,
                "summary_text": None,
                "deadline_date": pub_date,
                "support_amount": None,
            })

        return items


SCRAPER_REGISTRY.append(SeoulRssScraper())
