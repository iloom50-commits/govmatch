"""공공기관 스크래퍼 배치 7 — 정부출연연구기관 6개.

kicet.re.kr  : 한국세라믹기술원 (idx 파라미터)
kims.re.kr   : 한국재료연구원 (wr_id 파라미터, Gnuboard 계열)
etri.re.kr   : 한국전자통신연구원 (b_idx 파라미터)
kitech.re.kr : 한국생산기술연구원 (id 파라미터)
kriss.re.kr  : 한국표준과학연구원 (list_no 파라미터)
kimm.re.kr   : 한국기계연구원 (RESTful /notice/view/id/)
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
# 1. 한국세라믹기술원 (kicet.re.kr)
# ─────────────────────────────────────────────────────────────
_KICET_BASE = "https://www.kicet.re.kr"
_KICET_LIST = f"{_KICET_BASE}/00020/00117/00120.web?page={{page}}"
_KICET_RE = re.compile(
    r"""href=['"]\?gcode=1015(?:&amp;|&)idx=(\d+)(?:&amp;|&)amode=view[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KicetScraper(BaseScraper):
    name = "kicet"
    display_name = "한국세라믹기술원(KICET)"
    origin_url_prefix = f"{_KICET_BASE}/00020/00117/00120.web"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KICET_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KICET_RE.finditer(html):
                idx = m.group(1)
                if idx in seen:
                    continue
                seen.add(idx)
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
                        f"{_KICET_BASE}/00020/00117/00120.web"
                        f"?gcode=1015&idx={idx}&amode=view"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "R&D",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KicetScraper())


# ─────────────────────────────────────────────────────────────
# 2. 한국재료연구원 (kims.re.kr) — Gnuboard 계열 wr_id
# ─────────────────────────────────────────────────────────────
_KIMS_BASE = "https://www.kims.re.kr"
_KIMS_LIST = f"{_KIMS_BASE}/v17/bbx/board.php?bx_table=05_02&page={{page}}"
_KIMS_RE = re.compile(
    r"""href=['"]https://www\.kims\.re\.kr/v17/bbx/board\.php\?bx_table=05_02(?:&amp;|&)wr_id=(\d+)[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KimsScraper(BaseScraper):
    name = "kims"
    display_name = "한국재료연구원(KIMS)"
    origin_url_prefix = f"{_KIMS_BASE}/v17/bbx/board.php"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KIMS_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KIMS_RE.finditer(html):
                wr_id = m.group(1)
                if wr_id in seen:
                    continue
                seen.add(wr_id)
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
                        f"{_KIMS_BASE}/v17/bbx/board.php"
                        f"?bx_table=05_02&wr_id={wr_id}"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "R&D",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KimsScraper())


# ─────────────────────────────────────────────────────────────
# 3. 한국전자통신연구원 (etri.re.kr) — b_idx 파라미터
# ─────────────────────────────────────────────────────────────
_ETRI_BASE = "https://www.etri.re.kr"
_ETRI_LIST = f"{_ETRI_BASE}/kor/bbs/list.etri?b_board_id=ETRI01&nPage={{page}}"
_ETRI_RE = re.compile(
    r"""href=['"]/kor/bbs/view\.etri[^'"]*b_idx=(\d+)[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class EtriScraper(BaseScraper):
    name = "etri"
    display_name = "한국전자통신연구원(ETRI)"
    origin_url_prefix = f"{_ETRI_BASE}/kor/bbs/view.etri"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_ETRI_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _ETRI_RE.finditer(html):
                b_idx = m.group(1)
                if b_idx in seen:
                    continue
                seen.add(b_idx)
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
                        f"{_ETRI_BASE}/kor/bbs/view.etri"
                        f"?b_board_id=ETRI01&b_idx={b_idx}"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "ICT",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(EtriScraper())


# ─────────────────────────────────────────────────────────────
# 4. 한국생산기술연구원 (kitech.re.kr) — id 파라미터
# ─────────────────────────────────────────────────────────────
_KITECH_BASE = "https://www.kitech.re.kr"
_KITECH_LIST = f"{_KITECH_BASE}/pages/19?page={{page}}"
_KITECH_RE = re.compile(
    r"""href=['"]/pages/19\?id=(\d+)(?:&amp;|&)menuMode=READ[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KitechScraper(BaseScraper):
    name = "kitech"
    display_name = "한국생산기술연구원(KITECH)"
    origin_url_prefix = f"{_KITECH_BASE}/pages/19"
    # 목록이 최신순 아님(만료·기존이 상단, 신규가 하단) → 연속 기존건 조기종료 시
    # 신규를 놓침. 전체 순회 필요.
    skip_consecutive_break = True

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KITECH_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KITECH_RE.finditer(html):
                post_id = m.group(1)
                if post_id in seen:
                    continue
                seen.add(post_id)
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
                        f"{_KITECH_BASE}/pages/19"
                        f"?id={post_id}&menuMode=READ"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "R&D",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KitechScraper())


# ─────────────────────────────────────────────────────────────
# 5. 한국표준과학연구원 (kriss.re.kr) — list_no 파라미터
# ─────────────────────────────────────────────────────────────
_KRISS_BASE = "https://www.kriss.re.kr"
_KRISS_LIST = (
    f"{_KRISS_BASE}/board.es"
    "?mid=a10503000000&bid=0002&nPage={page}"
)
_KRISS_RE = re.compile(
    r"""href=['"]/board\.es[^'"]*list_no=(\d+)[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KrissScraper(BaseScraper):
    name = "kriss"
    display_name = "한국표준과학연구원(KRISS)"
    origin_url_prefix = f"{_KRISS_BASE}/board.es"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KRISS_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KRISS_RE.finditer(html):
                list_no = m.group(1)
                if list_no in seen:
                    continue
                seen.add(list_no)
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
                        f"{_KRISS_BASE}/board.es"
                        f"?mid=a10503000000&bid=0002&act=view&list_no={list_no}&nPage={page}"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "R&D",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KrissScraper())


# ─────────────────────────────────────────────────────────────
# 6. 한국기계연구원 (kimm.re.kr) — RESTful /notice/view/id/
# ─────────────────────────────────────────────────────────────
_KIMM_BASE = "https://www.kimm.re.kr"
_KIMM_LIST = f"{_KIMM_BASE}/notice?page={{page}}"
_KIMM_RE = re.compile(
    r"""href=['"]/notice/view/id/(\d+)['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KimmScraper(BaseScraper):
    name = "kimm"
    display_name = "한국기계연구원(KIMM)"
    origin_url_prefix = f"{_KIMM_BASE}/notice/view/id/"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KIMM_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KIMM_RE.finditer(html):
                post_id = m.group(1)
                if post_id in seen:
                    continue
                seen.add(post_id)
                found_new = True

                title = _clean(m.group(2))
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                ctx = html[max(0, m.start() - 400): m.end() + 400]

                items.append({
                    "title": title[:400],
                    "origin_url": f"{_KIMM_BASE}/notice/view/id/{post_id}",
                    "region": "전국",
                    "target_type": "business",
                    "category": "R&D",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KimmScraper())
