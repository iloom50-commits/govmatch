"""시군구 기업지원 전담기관 스크래퍼 (11개)

성남산업진흥원, 평택산업진흥원, 시흥산업진흥원,
창원산업진흥원, 김해의생명산업진흥원, 구미전자정보기술원,
천안과학산업진흥원, 충청북도기업진흥원,
남동구기업지원포털, 양산시기업지원, 아산시기업지원
"""
from __future__ import annotations
import re
import warnings
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any

from .base import BaseScraper, register

warnings.filterwarnings("ignore", message="Unverified HTTPS")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}
_EXCLUDE_KW = re.compile(
    r"채용|입찰|구매|계약|임원|인재|면접|합격자|공사|용역|물품|청소|경비|보안|퇴직|고용공고|입사"
)
_DATE_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
_DATE_SHORT = re.compile(r"(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})")  # YY.MM.DD
_DATE_MMDD = re.compile(r"(\d{1,2})-(\d{1,2})")                      # MM-DD only


def _get(url: str, verify: bool = True, **kw) -> BeautifulSoup:
    r = requests.get(url, headers=_HEADERS, timeout=20, verify=verify, **kw)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return BeautifulSoup(r.text, "html.parser")


def _post(url: str, data: dict, verify: bool = True) -> BeautifulSoup:
    r = requests.post(url, headers=_HEADERS, data=data, timeout=20, verify=verify)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return BeautifulSoup(r.text, "html.parser")


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def _parse_date(text: str) -> str | None:
    m = _DATE_RE.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    m2 = _DATE_SHORT.search(text or "")
    if m2:
        return f"20{m2.group(1)}-{m2.group(2).zfill(2)}-{m2.group(3).zfill(2)}"
    return None


def _item(title: str, url: str, date: str | None = None,
          summary: str | None = None, region: str = "전국") -> Dict[str, Any]:
    return {
        "title": title[:500],
        "origin_url": url,
        "deadline_date": date,
        "support_amount": None,
        "summary_text": summary,
        "region": region,
        "category": "창업지원",
        "target_type": None,
    }


# ─────────────────────────────────────────────────────────────
# 1. 성남산업진흥원
# ─────────────────────────────────────────────────────────────
@register
class SnipScraper(BaseScraper):
    name = "snip"
    display_name = "성남산업진흥원"
    origin_url_prefix = "https://www.snip.or.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        base = "https://www.snip.or.kr/SNIP/contents/Business1.do"
        results = []
        for page in range(1, 6):
            soup = _get(f"{base}?page={page}")
            rows = soup.select("table tbody tr")
            if not rows:
                break
            found = False
            for tr in rows:
                a = tr.select_one("td.subject a, td.list_subject a")
                if not a:
                    continue
                title = _clean(a.get_text())
                if not title or _EXCLUDE_KW.search(title):
                    continue
                href = a.get("href", "")
                url = href if href.startswith("http") else f"https://www.snip.or.kr{href}"
                date_td = tr.select_one("td.data, td.date")
                date = _parse_date(date_td.get_text() if date_td else "")
                results.append(_item(title, url, date, region="성남시"))
                found = True
            if not found:
                break
        return results


# ─────────────────────────────────────────────────────────────
# 2. 평택산업진흥원
# ─────────────────────────────────────────────────────────────
@register
class PipabizScraper(BaseScraper):
    name = "pipabiz"
    display_name = "평택산업진흥원"
    origin_url_prefix = "https://www.pipabiz.or.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        base = "https://www.pipabiz.or.kr/web/contents/notice.do"
        results = []
        for page in range(1, 6):
            soup = _get(f"{base}?page={page}")
            rows = soup.select("table tbody tr")
            if not rows:
                break
            found = False
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 2:
                    continue
                a = tds[1].find("a")
                if not a:
                    continue
                title = _clean(a.get_text())
                if not title or _EXCLUDE_KW.search(title):
                    continue
                href = a.get("href", "")
                url = href if href.startswith("http") else f"https://www.pipabiz.or.kr{href}"
                date = _parse_date(tds[3].get_text() if len(tds) > 3 else "")
                results.append(_item(title, url, date, region="평택시"))
                found = True
            if not found:
                break
        return results


# ─────────────────────────────────────────────────────────────
# 3. 시흥산업진흥원
# ─────────────────────────────────────────────────────────────
@register
class SidaScraper(BaseScraper):
    name = "sida"
    display_name = "시흥산업진흥원"
    origin_url_prefix = "https://www.sida.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        base = "https://www.sida.kr/notification/notice.html"
        results = []
        for page in range(1, 6):
            soup = _get(f"{base}?cpage={page}&spage=1")
            rows = soup.select("table tbody tr")
            if not rows:
                break
            found = False
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 2:
                    continue
                a = tds[1].find("a") if len(tds) > 1 else None
                if not a:
                    continue
                title = _clean(a.get_text())
                if not title or _EXCLUDE_KW.search(title):
                    continue
                href = a.get("href", "")
                if href.startswith("."):
                    href = "/notification/" + href.lstrip("./")
                url = f"https://www.sida.kr{href}" if not href.startswith("http") else href
                date = _parse_date(tds[-1].get_text() if tds else "")
                results.append(_item(title, url, date, region="시흥시"))
                found = True
            if not found:
                break
        return results


# ─────────────────────────────────────────────────────────────
# 그누보드 공통 스크래퍼 (창원, 김해)
# ─────────────────────────────────────────────────────────────
def _gnuboard_fetch(base_url: str, table: str, region: str,
                    verify: bool = True, max_pages: int = 5) -> List[Dict[str, Any]]:
    import datetime
    results = []
    for page in range(1, max_pages + 1):
        url = f"{base_url}/bbs/board.php?bo_table={table}&page={page}"
        soup = _get(url, verify=verify)
        # 그누보드는 div.bo_tit > a 또는 td.list_subject > a 둘 중 하나
        links = soup.select(
            "div.bo_tit a[href*='wr_id'], "
            "td.list_subject a[href*='wr_id'], "
            "td.td_subject a[href*='wr_id']"
        )
        if not links:
            break
        found = False
        for a in links:
            title = _clean(a.get_text())
            if not title or _EXCLUDE_KW.search(title):
                continue
            href = a.get("href", "")
            item_url = href if href.startswith("http") else f"{base_url}{href}"
            # 날짜: 같은 tr → td.list_date 또는 마지막 td
            tr = a.find_parent("tr")
            if tr:
                date_td = tr.select_one("td.list_date, td.td_datetime")
                if not date_td:
                    tds = tr.find_all("td")
                    date_td = tds[-1] if tds else None
                raw_date = date_td.get_text().strip() if date_td else ""
                if _DATE_MMDD.match(raw_date) and not _DATE_RE.search(raw_date):
                    raw_date = f"{datetime.date.today().year}-{raw_date}"
                date = _parse_date(raw_date)
            else:
                date = None
            results.append(_item(title, item_url, date, region=region))
            found = True
        if not found:
            break
    return results


@register
class CwipScraper(BaseScraper):
    name = "cwip"
    display_name = "창원산업진흥원"
    origin_url_prefix = "https://www.cwip.or.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        return _gnuboard_fetch("https://www.cwip.or.kr", "b0504", "창원시", verify=False)


@register
class GbiaScraper(BaseScraper):
    name = "gbia"
    display_name = "김해의생명산업진흥원"
    origin_url_prefix = "https://gbia.or.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        return _gnuboard_fetch("https://gbia.or.kr", "business", "김해시")


# ─────────────────────────────────────────────────────────────
# 6. 구미전자정보기술원 (ASP)
# ─────────────────────────────────────────────────────────────
@register
class GeriScraper(BaseScraper):
    name = "geri"
    display_name = "구미전자정보기술원"
    origin_url_prefix = "https://geri.re.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        base = "https://geri.re.kr"
        results = []
        for page in range(1, 6):
            soup = _get(f"{base}/html/board_list.asp?board_id=business&page={page}")
            links = soup.select("a[href*='board_content.asp']")
            if not links:
                break
            found = False
            for a in links:
                title = _clean(a.get_text())
                if not title or _EXCLUDE_KW.search(title):
                    continue
                href = a.get("href", "")
                url = f"{base}{href}" if href.startswith("/") else href
                tr = a.find_parent("tr")
                tds = tr.find_all("td") if tr else []
                date = _parse_date(tds[-1].get_text() if tds else "")
                results.append(_item(title, url, date, region="구미시"))
                found = True
            if not found:
                break
        return results


# ─────────────────────────────────────────────────────────────
# 7. 천안과학산업진흥원
# ─────────────────────────────────────────────────────────────
@register
class CistepScraper(BaseScraper):
    name = "cistep"
    display_name = "천안과학산업진흥원"
    origin_url_prefix = "https://www.cistep.re.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        base = "https://www.cistep.re.kr/gnb01/lnb01/list.do"
        results = []
        for page in range(1, 6):
            soup = _get(f"{base}?pageIndex={page}")
            links = soup.select("a[href*='read.do']")
            if not links:
                break
            found = False
            for a in links:
                title = _clean(a.get_text())
                if not title or _EXCLUDE_KW.search(title):
                    continue
                href = a.get("href", "")
                url = f"https://www.cistep.re.kr{href}" if href.startswith("/") else href
                tr = a.find_parent("tr")
                tds = tr.find_all("td") if tr else []
                date = _parse_date(" ".join(td.get_text() for td in tds))
                results.append(_item(title, url, date, region="천안시"))
                found = True
            if not found:
                break
        return results


# ─────────────────────────────────────────────────────────────
# 8. 충청북도기업진흥원
# ─────────────────────────────────────────────────────────────
@register
class CbaScraper(BaseScraper):
    name = "cba_bizinfo"
    display_name = "충청북도기업진흥원"
    origin_url_prefix = "https://www.cba.ne.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        base = "https://www.cba.ne.kr/home/sub.php"
        results = []
        for page in range(1, 6):
            soup = _get(f"{base}?menukey=172&mod=&page={page}&scode=00000004")
            links = soup.select("a[href*='mod=view']")
            if not links:
                break
            found = False
            for a in links:
                title = _clean(a.get_text())
                if not title or _EXCLUDE_KW.search(title):
                    continue
                href = a.get("href", "")
                url = f"https://www.cba.ne.kr/home/{href}" if not href.startswith("http") else href
                tr = a.find_parent("tr")
                tds = tr.find_all("td") if tr else []
                date = _parse_date(" ".join(td.get_text() for td in tds))
                results.append(_item(title, url, date, region="청주시"))
                found = True
            if not found:
                break
        return results


# ─────────────────────────────────────────────────────────────
# 9. 남동구 기업지원포털
# ─────────────────────────────────────────────────────────────
@register
class NamdongBizScraper(BaseScraper):
    name = "namdong_biz"
    display_name = "남동구기업지원포털"
    origin_url_prefix = "https://biz.namdong.go.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        base = "https://biz.namdong.go.kr/bizNotice/bizNoticeList.do"
        results = []
        for page in range(1, 6):
            soup = _get(f"{base}?pgno={page}", verify=False)
            items = soup.select("p.tit a, .list_wrap a")
            if not items:
                break
            found = False
            for a in items:
                title = _clean(a.get_text())
                if not title or _EXCLUDE_KW.search(title):
                    continue
                href = a.get("href", "")
                url = f"https://biz.namdong.go.kr{href}" if href.startswith("/") else href
                parent = a.find_parent("li") or a.find_parent("div")
                raw = parent.get_text() if parent else ""
                date = _parse_date(raw)
                results.append(_item(title, url, date, region="남동구"))
                found = True
            if not found:
                break
        return results


# ─────────────────────────────────────────────────────────────
# 10. 양산시 기업지원 (POST 페이지네이션)
# ─────────────────────────────────────────────────────────────
_YANGSAN_BIZ_KW = re.compile(
    r"지원|보조|융자|기업|창업|소상공인|벤처|중소|수출|R&D|기술|일자리|취업|모집|공모|신청|사업"
)

@register
class YangsanBizScraper(BaseScraper):
    name = "yangsan_biz"
    display_name = "양산시기업지원"
    origin_url_prefix = "https://www.yangsan.go.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        url = "https://www.yangsan.go.kr/portal/saeol/gosi/list.do?mid=0102010000"
        results = []
        for page in range(1, 6):
            soup = _post(url, data={"page": page, "pageUnit": 10,
                                    "searchCnd": 0, "searchWrd": ""})
            rows = soup.select("table tbody tr")
            if not rows:
                break
            found = False
            for tr in rows:
                a = tr.find("a", attrs={"data-action": True})
                if not a:
                    continue
                title = _clean(a.get_text())
                if not title or _EXCLUDE_KW.search(title):
                    continue
                if not _YANGSAN_BIZ_KW.search(title):
                    continue  # 기업지원 무관 공고 제외
                action = a.get("data-action", "")
                item_url = f"https://www.yangsan.go.kr{action}" if action.startswith("/") else action
                tds = tr.find_all("td")
                date = _parse_date(tds[4].get_text() if len(tds) > 4 else "")
                results.append(_item(title, item_url, date, region="양산시"))
                found = True
            if not found:
                break
        return results


# ─────────────────────────────────────────────────────────────
# 11. 아산시 기업지원
# ─────────────────────────────────────────────────────────────
@register
class AsanBizScraper(BaseScraper):
    name = "asan_biz"
    display_name = "아산시기업지원"
    origin_url_prefix = "https://www.asan.go.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        base = "https://www.asan.go.kr/giup/developer/m_board/m_board.php"
        results = []
        for page in range(1, 4):
            soup = _get(f"{base}?tb_nm=tbl_notice&m_mode=list&PageNo={page}")
            rows = soup.select("table tbody tr")
            if not rows:
                break
            found = False
            for tr in rows:
                a = tr.find("a")
                if not a:
                    continue
                title = _clean(a.get_text())
                if not title or _EXCLUDE_KW.search(title):
                    continue
                href = a.get("href", "")
                url = href if href.startswith("http") else f"{base.rsplit('/', 1)[0]}/{href.lstrip('/')}"
                tds = tr.find_all("td")
                date = _parse_date(tds[2].get_text() if len(tds) > 2 else "")
                results.append(_item(title, url, date, region="아산시"))
                found = True
            if not found:
                break
        return results
