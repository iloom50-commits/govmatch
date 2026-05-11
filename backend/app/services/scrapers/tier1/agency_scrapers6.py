"""공공기관 스크래퍼 배치 6 — KHIDI, MSS, K-Startup.

khidi.or.kr         : 한국보건산업진흥원 (보건의료 지원, 직접 href)
mss.go.kr           : 중소벤처기업부 (정책 공고, doBbsFView onclick bcIdx 추출)
k-startup.go.kr     : K-Startup (창업진흥원 포털, go_view onclick ID 추출)
"""
from __future__ import annotations
import html as html_lib
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
# 1. 한국보건산업진흥원 (khidi.or.kr) — 보건·의료·바이오 지원공고
# ─────────────────────────────────────────────────────────────
_KHIDI_BASE = "https://www.khidi.or.kr"
_KHIDI_LIST = f"{_KHIDI_BASE}/board?menuId=MENU01108&pageIndex={{page}}"
_KHIDI_RE = re.compile(
    r"""href=['"]/board/view\?[^'"]*linkId=(\d+)[^'"]*menuId=MENU01108[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KhidiScraper(BaseScraper):
    name = "khidi"
    display_name = "한국보건산업진흥원(KHIDI)"
    origin_url_prefix = f"{_KHIDI_BASE}/board/view"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KHIDI_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KHIDI_RE.finditer(html):
                link_id = m.group(1)
                if link_id in seen:
                    continue
                seen.add(link_id)
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
                        f"{_KHIDI_BASE}/board/view"
                        f"?linkId={link_id}&menuId=MENU01108"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "바이오",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KhidiScraper())


# ─────────────────────────────────────────────────────────────
# 2. 중소벤처기업부 (mss.go.kr) — 정책/공고
#    onclick="doBbsFView('310','bcIdx',...)" 에서 bcIdx 추출
# ─────────────────────────────────────────────────────────────
_MSS_BASE = "https://www.mss.go.kr"
_MSS_LIST = (
    f"{_MSS_BASE}/site/smba/ex/bbs/List.do"
    "?cbIdx=310&pageIndex={page}"
)
# doBbsFView('310', '1068080', '16010100', '1068080') → bcIdx = 두 번째 인자
_MSS_RE = re.compile(
    r"""doBbsFView\('[^']*','(\d+)'[^)]*\)[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class MssScraper(BaseScraper):
    name = "mss"
    display_name = "중소벤처기업부(MSS)"
    origin_url_prefix = f"{_MSS_BASE}/site/smba/ex/bbs/View.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_MSS_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _MSS_RE.finditer(html):
                bc_idx = m.group(1)
                if bc_idx in seen:
                    continue
                seen.add(bc_idx)
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
                        f"{_MSS_BASE}/site/smba/ex/bbs/View.do"
                        f"?cbIdx=310&bcIdx={bc_idx}"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(MssScraper())


# ─────────────────────────────────────────────────────────────
# 3. K-Startup (k-startup.go.kr) — 창업 지원사업 공고
#    onclick="go_view(ID)" 에서 ID 추출, <p class="tit"> 로 제목만 추출
# ─────────────────────────────────────────────────────────────
_KSTARTUP_BASE = "https://www.k-startup.go.kr"
_KSTARTUP_LIST = (
    f"{_KSTARTUP_BASE}/web/contents/bizpbanc-ongoing.do"
    "?schPageSize=10&page={page}"
)
# <a> 블록 전체 캡처 (ID + 내부 HTML)
_KSTARTUP_BLOCK_RE = re.compile(
    r"""go_view\((\d+)\).*?</a>""",
    re.DOTALL,
)
# <a> 블록 내에서 실제 제목만 추출
_KSTARTUP_TIT_RE = re.compile(
    r'<p[^>]+class="tit"[^>]*>(.*?)</p>',
    re.DOTALL,
)


class KstartupScraper(BaseScraper):
    name = "k_startup"
    display_name = "K-Startup(창업진흥원 포털)"
    origin_url_prefix = f"{_KSTARTUP_BASE}/web/contents/bizpbanc-read.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                page_html = _get(_KSTARTUP_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KSTARTUP_BLOCK_RE.finditer(page_html):
                pbanc_sn = m.group(1)
                if pbanc_sn in seen:
                    continue
                seen.add(pbanc_sn)
                found_new = True

                block = m.group(0)
                tit_m = _KSTARTUP_TIT_RE.search(block)
                if not tit_m:
                    continue

                # HTML 엔티티(&amp; 등) 디코딩 후 태그 제거
                title = html_lib.unescape(_clean(tit_m.group(1)))
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                ctx = page_html[max(0, m.start() - 400): m.end() + 400]

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_KSTARTUP_BASE}/web/contents/bizpbanc-read.do"
                        f"?pbancSn={pbanc_sn}"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "창업",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KstartupScraper())
