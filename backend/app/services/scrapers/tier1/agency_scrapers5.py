"""공공기관 스크래퍼 배치 5 — KCA, KOFIC, KBIZ, KVIC.

kca.kr                  : 한국방송통신전파진흥원 (방송/ICT 지원, 직접 href)
kofic.or.kr             : 영화진흥위원회 (콘텐츠 지원, onclick seq 추출)
kbiz.or.kr              : 중소기업중앙회 (중소기업 지원, onclick seq 추출)
kvic.or.kr              : 한국벤처투자 (벤처 투자/육성 지원, onclick id 추출)
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
# 1. 한국방송통신전파진흥원 (kca.kr) — 방송/통신/ICT 지원공고
# ─────────────────────────────────────────────────────────────
_KCA_BASE = "https://www.kca.kr"
_KCA_LIST = (
    f"{_KCA_BASE}/boardList.do"
    "?boardId=NOTICE&pageId=www47&movePage={page}"
)
_KCA_RE = re.compile(
    r"""href=['"]/boardView\.do\?pageId=www47&boardId=NOTICE&seq=(\d+)[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KcaScraper(BaseScraper):
    name = "kca"
    display_name = "한국방송통신전파진흥원(KCA)"
    origin_url_prefix = f"{_KCA_BASE}/boardView.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KCA_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KCA_RE.finditer(html):
                seq = m.group(1)
                if seq in seen:
                    continue
                seen.add(seq)
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
                        f"{_KCA_BASE}/boardView.do"
                        f"?pageId=www47&boardId=NOTICE&seq={seq}&movePage={page}"
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


SCRAPER_REGISTRY.append(KcaScraper())


# ─────────────────────────────────────────────────────────────
# 2. 영화진흥위원회 (kofic.or.kr) — 콘텐츠/영화 지원공고
#    onclick="fn_goDetailPage(seq, ...)" 에서 seq 추출
# ─────────────────────────────────────────────────────────────
_KOFIC_BASE = "https://www.kofic.or.kr"
_KOFIC_LIST = (
    f"{_KOFIC_BASE}/kofic/business/board/selectBoardList.do"
    "?boardNumber=4&pageIndex={page}"
)
# 제목이 onclick 링크 내 텍스트로 포함됨
_KOFIC_RE = re.compile(
    r"""fn_goDetailPage\((\d+)[^)]*\)[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KoficScraper(BaseScraper):
    name = "kofic"
    display_name = "영화진흥위원회(KOFIC)"
    origin_url_prefix = f"{_KOFIC_BASE}/kofic/business/board/selectBoardView.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KOFIC_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KOFIC_RE.finditer(html):
                seq = m.group(1)
                if seq in seen:
                    continue
                seen.add(seq)
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
                        f"{_KOFIC_BASE}/kofic/business/board/selectBoardView.do"
                        f"?boardNumber=4&seq={seq}"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "콘텐츠",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KoficScraper())


# ─────────────────────────────────────────────────────────────
# 3. 중소기업중앙회 (kbiz.or.kr) — 중소기업 지원사업 공고
#    onclick="goView(seq, ...)" 에서 seq 추출
# ─────────────────────────────────────────────────────────────
_KBIZ_BASE = "https://www.kbiz.or.kr"
_KBIZ_LIST = (
    f"{_KBIZ_BASE}/ko/contents/bbs/list.do"
    "?mnSeq=211&pageIndex={page}"
)
_KBIZ_RE = re.compile(
    r"""goView\((\d+)[^)]*\)[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KbizScraper(BaseScraper):
    name = "kbiz"
    display_name = "중소기업중앙회(KBIZ)"
    origin_url_prefix = f"{_KBIZ_BASE}/ko/contents/bbs/view.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KBIZ_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KBIZ_RE.finditer(html):
                seq = m.group(1)
                if seq in seen:
                    continue
                seen.add(seq)
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
                        f"{_KBIZ_BASE}/ko/contents/bbs/view.do"
                        f"?seq={seq}&mnSeq=211"
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


SCRAPER_REGISTRY.append(KbizScraper())


# ─────────────────────────────────────────────────────────────
# 4. 한국벤처투자 (kvic.or.kr) — 투자·육성 지원공고
#    onclick="board_view(id)" 에서 id 추출 (Mozilla UA 필수)
# ─────────────────────────────────────────────────────────────
_KVIC_BASE = "https://www.kvic.or.kr"
_KVIC_LIST = (
    f"{_KVIC_BASE}/notice/kvic-notice/investment-business-notice"
    "?page={page}"
)
_KVIC_RE = re.compile(
    r"""board_view\((\d+)\)[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class KvicScraper(BaseScraper):
    name = "kvic"
    display_name = "한국벤처투자(KVIC)"
    origin_url_prefix = f"{_KVIC_BASE}/notice/kvic-notice/investment-business-notice"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_KVIC_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _KVIC_RE.finditer(html):
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
                        f"{_KVIC_BASE}/notice/kvic-notice/investment-business-notice"
                        f"?id={post_id}"
                    ),
                    "region": "전국",
                    "target_type": "business",
                    "category": "투자",
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(KvicScraper())
