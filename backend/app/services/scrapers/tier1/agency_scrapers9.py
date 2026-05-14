"""공공기관 스크래퍼 배치 9 — KEITI, TIPA, KIDP, IITP, KOTRA

KEITI  : 한국환경산업기술원 공지/공모 (HTML ul.list.col5)
TIPA   : 중소기업기술정보진흥원 기정원소식/공고 (HTML table.basic_table)
KIDP   : 한국디자인진흥원 지원사업/사업소식 (HTML, JS submitForm URL 재구성)
IITP   : 정보통신기획평가원 공지사항 (Vue.js AJAX 시도)
KOTRA  : 한국무역투자진흥공사 공지사항 (HTML 시도)
"""
from __future__ import annotations
import html as _html
import json
import re
import time
import logging
import requests
from typing import List, Dict, Any

from .base import BaseScraper, SCRAPER_REGISTRY

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}
_EXCLUDE_KW = re.compile(
    r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품|청소|경비|보안|퇴직|임원|낙찰|유찰|재공고"
)
_DATE_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def _get(url: str, **kwargs) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=20, **kwargs)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _clean(raw: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw or "")).strip()


def _parse_date(text: str) -> str | None:
    m = _DATE_RE.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return None


# ─────────────────────────────────────────────────────────────
# 1. KEITI (한국환경산업기술원) — 공지사항/공모 게시판
#    https://www.keiti.re.kr/site/keiti/ex/board/List.do?cbIdx=277
# ─────────────────────────────────────────────────────────────
_KEITI_BASE = "https://www.keiti.re.kr"
_KEITI_LIST = (
    f"{_KEITI_BASE}/site/keiti/ex/board/List.do?cbIdx=277&pageIndex={{page}}"
)
# 입찰·채용·공사·공시송달 제외 (cateName 기준)
_KEITI_EXCL_CAT = re.compile(r"입찰|채용|공사|용역|구매|낙찰|유찰|공시송달")
_KEITI_HREF_RE = re.compile(
    r'href="(/site/keiti/ex/board/View\.do\?cbIdx=277&bcIdx=(\d+))"'
)
_KEITI_CAT_RE = re.compile(r'<span class="cateName">([^<]+)</span>')
_KEITI_DATE_RE = re.compile(r'<span class="date">(\d{4}-\d{2}-\d{2})</span>')
_KEITI_SUBJ_RE = re.compile(r'<span class="subject">([^<]+)</span>')
_KEITI_TEXT_RE = re.compile(r'<span class="text">(.*?)</span>', re.DOTALL)


class KEITIScraper(BaseScraper):
    """한국환경산업기술원 — 공지/공모 게시판"""

    name = "keiti"
    display_name = "한국환경산업기술원(KEITI)"
    origin_url_prefix = f"{_KEITI_BASE}/site/keiti/ex/board"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 8):
            try:
                html = _get(_KEITI_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[keiti] page {page} 실패: {e}")
                break

            # 각 항목은 bcIdx 고유 href로 구분
            blocks = re.split(
                r'(?=href="/site/keiti/ex/board/View\.do\?cbIdx=277&bcIdx=)',
                html,
            )
            found_new = False
            for block in blocks[1:]:
                href_m = _KEITI_HREF_RE.search(block[:200])
                if not href_m:
                    continue
                href, bcIdx = href_m.group(1), href_m.group(2)
                if bcIdx in seen:
                    continue

                ctx = block[:1200]

                # 카테고리 필터
                cat_m = _KEITI_CAT_RE.search(ctx)
                cat_label = _clean(cat_m.group(1)) if cat_m else ""
                if _KEITI_EXCL_CAT.search(cat_label):
                    continue

                subj_m = _KEITI_SUBJ_RE.search(ctx)
                if not subj_m:
                    continue
                title = _html.unescape(_clean(subj_m.group(1)))
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                date_m = _KEITI_DATE_RE.search(ctx)
                text_m = _KEITI_TEXT_RE.search(ctx)
                summary = _html.unescape(_clean(text_m.group(1))) if text_m else None

                seen.add(bcIdx)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": _KEITI_BASE + href,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": (summary or "")[:1000] or None,
                        "region": "전국",
                        "category": "환경",
                        "target_type": None,
                        "department": "한국환경산업기술원",
                    }
                )

            if not found_new:
                break
            time.sleep(0.5)

        logger.info(f"[keiti] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(KEITIScraper())


# ─────────────────────────────────────────────────────────────
# 2. TIPA (중소기업기술정보진흥원) — 기정원소식 (공고·행사·보도자료)
#    https://www.tipa.or.kr/s040101
# ─────────────────────────────────────────────────────────────
_TIPA_BASE = "https://www.tipa.or.kr"
_TIPA_LIST = f"{_TIPA_BASE}/s040101/index/page/{{page}}"
_TIPA_LINK_RE = re.compile(
    r"""href='/s040101/view/id/(\d+)'\s+title="([^"]+)"""
)
_TIPA_DATE_RE = re.compile(r"(\d{4}\.\d{2}\.\d{2})")


class TIPAScraper(BaseScraper):
    """중소기업기술정보진흥원 — 기정원소식"""

    name = "tipa"
    display_name = "중소기업기술정보진흥원(TIPA)"
    origin_url_prefix = f"{_TIPA_BASE}/s040101"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 8):
            try:
                html = _get(_TIPA_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[tipa] page {page} 실패: {e}")
                break

            found_new = False
            for m in _TIPA_LINK_RE.finditer(html):
                art_id = m.group(1)
                title = _html.unescape(m.group(2).strip())

                if art_id in seen:
                    continue
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                # 등록일: 매치 이후 500자 내 최초 날짜
                ctx = html[m.end(): m.end() + 600]
                date_m = _TIPA_DATE_RE.search(ctx)
                posted = _parse_date(date_m.group(1)) if date_m else None

                seen.add(art_id)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": f"{_TIPA_BASE}/s040101/view/id/{art_id}",
                        "deadline_date": None,   # 등록일 ≠ 마감일
                        "support_amount": None,
                        "summary_text": f"등록일: {posted}" if posted else None,
                        "region": "전국",
                        "category": "기술개발",
                        "target_type": "business",
                        "department": "중소기업기술정보진흥원",
                    }
                )

            if not found_new:
                break
            time.sleep(0.5)

        logger.info(f"[tipa] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(TIPAScraper())


# ─────────────────────────────────────────────────────────────
# 3. KIDP (한국디자인진흥원) — 지원사업 공고 / 사업소식
#    JavaScript submitForm() 방식 → seq ID로 URL 재구성
# ─────────────────────────────────────────────────────────────
_KIDP_BASE = "https://www.kidp.or.kr"

# (menuno, board_label, category, target_type)
_KIDP_BOARDS = [
    (1487, "디자인금융지원", "디자인", "business"),
    (1202, "사업소식",     "디자인", None),
]
_KIDP_ITEM_RE = re.compile(
    r"""onclick="return\s+submitForm\(this,'view',(\d+)\);"\s+title="([^"]+)"""
)
_KIDP_DATE_ROW_RE = re.compile(r"<td[^>]*>\s*(20\d{2}-\d{2}-\d{2})\s*</td>")


class KIDPScraper(BaseScraper):
    """한국디자인진흥원 — 지원사업/사업소식"""

    name = "kidp"
    display_name = "한국디자인진흥원(KIDP)"
    origin_url_prefix = _KIDP_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for menuno, board_label, category, target_type in _KIDP_BOARDS:
            for page in range(1, 6):
                # KIDP 페이지네이션: ?menuno=N&page=P (일반 board 패턴)
                url = f"{_KIDP_BASE}/?menuno={menuno}&page={page}"
                try:
                    html = _get(url)
                except Exception as e:
                    logger.warning(f"[kidp] menuno={menuno} page={page} 실패: {e}")
                    break

                found_new = False
                for m in _KIDP_ITEM_RE.finditer(html):
                    seq = m.group(1)
                    title = _html.unescape(m.group(2).strip())

                    uid = f"{menuno}_{seq}"
                    if uid in seen:
                        continue
                    if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                        continue

                    # 날짜: 매치 이후 400자 내 YYYY-MM-DD 셀
                    ctx_after = html[m.end(): m.end() + 500]
                    date_m = _KIDP_DATE_ROW_RE.search(ctx_after)
                    if not date_m:
                        # 매치 이전 300자에서도 시도
                        ctx_before = html[max(0, m.start() - 400): m.start()]
                        date_m = _KIDP_DATE_ROW_RE.search(ctx_before)
                    posted = date_m.group(1) if date_m else None

                    seen.add(uid)
                    found_new = True
                    # 상세 URL: 한국 CMS 공통 패턴 (?menuno=N&no=SEQ)
                    detail_url = f"{_KIDP_BASE}/?menuno={menuno}&no={seq}"
                    items.append(
                        {
                            "title": title[:400],
                            "origin_url": detail_url,
                            "deadline_date": None,
                            "support_amount": None,
                            "summary_text": f"[{board_label}] 등록일: {posted}" if posted else f"[{board_label}]",
                            "region": "전국",
                            "category": category,
                            "target_type": target_type,
                            "department": "한국디자인진흥원",
                        }
                    )

                if not found_new:
                    break
                time.sleep(0.5)

        logger.info(f"[kidp] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(KIDPScraper())


# ─────────────────────────────────────────────────────────────
# 4. IITP (정보통신기획평가원) — 공지사항
#    Vue.js 기반 SPA — AJAX JSON endpoint 시도
#    Board path: /web/lay1/bbs/S1T12C37/A/7/list.do
# ─────────────────────────────────────────────────────────────
_IITP_BASE = "https://www.iitp.kr"
_IITP_LIST_URL = f"{_IITP_BASE}/web/lay1/bbs/S1T12C37/A/7/list.do"
_IITP_VIEW_URL = f"{_IITP_BASE}/web/lay1/bbs/S1T12C37/A/7/view.do"

# 정적 HTML fallback: article_seq 직접 추출
_IITP_SEQ_RE = re.compile(r'article_seq["\s:=\']+(\d+)')
_IITP_TITLE_RE = re.compile(r'"title"\s*:\s*"([^"]+)"')
_IITP_DATE_RE = re.compile(r'"reg_dt"\s*:\s*"(\d{4}-\d{2}-\d{2})"')


def _iitp_ajax(page: int) -> List[Dict[str, Any]]:
    """Vue.js AJAX 엔드포인트 POST 시도. 실패 시 빈 리스트."""
    try:
        headers = {**_HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                   "X-Requested-With": "XMLHttpRequest",
                   "Referer": _IITP_LIST_URL}
        resp = requests.post(
            _IITP_LIST_URL,
            headers=headers,
            data={"cpage": page, "rows": 10, "sort": ""},
            timeout=20,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        row_list = data.get("list") or data.get("data") or data.get("items") or []
        results = []
        for row in row_list:
            seq = str(row.get("article_seq") or row.get("seq") or "")
            title = str(row.get("title") or row.get("sj") or "")
            if not seq or not title or _EXCLUDE_KW.search(title):
                continue
            reg_dt = str(row.get("reg_dt") or row.get("regDt") or "")
            results.append(
                {
                    "title": _html.unescape(title)[:400],
                    "origin_url": f"{_IITP_VIEW_URL}?article_seq={seq}",
                    "deadline_date": None,
                    "support_amount": None,
                    "summary_text": f"등록일: {reg_dt}" if reg_dt else None,
                    "region": "전국",
                    "category": "ICT",
                    "target_type": None,
                    "department": "정보통신기획평가원",
                }
            )
        return results
    except Exception:
        return []


class IITPScraper(BaseScraper):
    """정보통신기획평가원 — 공지사항 (Vue.js AJAX)"""

    name = "iitp"
    display_name = "정보통신기획평가원(IITP)"
    origin_url_prefix = _IITP_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 6):
            rows = _iitp_ajax(page)
            if not rows:
                break
            found_new = False
            for row in rows:
                key = row["origin_url"]
                if key in seen:
                    continue
                seen.add(key)
                found_new = True
                items.append(row)
            if not found_new:
                break
            time.sleep(0.5)

        if not items:
            logger.info("[iitp] AJAX 엔드포인트 미확인 — 수집 0건 (Playwright 도입 후 재구현 예정)")
        else:
            logger.info(f"[iitp] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(IITPScraper())


# ─────────────────────────────────────────────────────────────
# 5. KOTRA (한국무역투자진흥공사) — 공지사항
#    subList SPA 페이지 → 정적 HTML 파싱 시도
#    Vue.js 렌더링 경우 수집 0건 (향후 API 엔드포인트 확인 필요)
# ─────────────────────────────────────────────────────────────
_KOTRA_BASE = "https://www.kotra.or.kr"
_KOTRA_LIST = f"{_KOTRA_BASE}/subList/41000022001"

# 정적 렌더 시 존재 가능한 패턴
_KOTRA_TITLE_RE = re.compile(
    r'class="[^"]*(?:title|subject|tit)[^"]*"[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_KOTRA_DATE_RE = re.compile(r"(\d{4}[.\-]\d{2}[.\-]\d{2})")

# 비즈니스 지원사업 API 엔드포인트 (JSON 응답 기대)
_KOTRA_BIZ_API = (
    f"{_KOTRA_BASE}/subList/20000020753/subhome/bizAply/selectBizMntInfoList.do"
)
_KOTRA_BIZ_DETAIL = (
    f"{_KOTRA_BASE}/subList/20000020753/subhome/bizAply/selectBizMntInfoDetail.do"
    "?dtlBizMntNo={{no}}&cpbizYn=N"
)


def _kotra_biz_api() -> List[Dict[str, Any]]:
    """KOTRA 비즈니스 지원사업 JSON API 시도."""
    try:
        headers = {**_HEADERS,
                   "Content-Type": "application/json",
                   "X-Requested-With": "XMLHttpRequest",
                   "Referer": f"{_KOTRA_BASE}/subList/20000020753"}
        resp = requests.post(
            _KOTRA_BIZ_API,
            headers=headers,
            json={"pageNo": 1, "pageSize": 30, "bizMntSeCd": ""},
            timeout=20,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        row_list = (
            data.get("list") or data.get("data") or
            data.get("bizMntList") or data.get("items") or []
        )
        results = []
        for row in row_list:
            no = str(row.get("dtlBizMntNo") or row.get("no") or "")
            title = str(row.get("bizSj") or row.get("title") or row.get("TITLE") or "")
            if not no or not title or _EXCLUDE_KW.search(title):
                continue
            results.append(
                {
                    "title": _html.unescape(title)[:400],
                    "origin_url": _KOTRA_BIZ_DETAIL.format(no=no),
                    "deadline_date": None,
                    "support_amount": None,
                    "summary_text": None,
                    "region": "전국",
                    "category": "수출",
                    "target_type": "business",
                    "department": "한국무역투자진흥공사",
                }
            )
        return results
    except Exception:
        return []


class KOTRAScraper(BaseScraper):
    """한국무역투자진흥공사 — 지원사업 공고"""

    name = "kotra"
    display_name = "한국무역투자진흥공사(KOTRA)"
    origin_url_prefix = _KOTRA_BASE

    def fetch_items(self) -> List[Dict[str, Any]]:
        items = _kotra_biz_api()
        if not items:
            logger.info(
                "[kotra] API 응답 없음 — Vue.js SPA 구조로 수집 0건 "
                "(브라우저 DevTools에서 API 엔드포인트 확인 후 재구현 예정)"
            )
        else:
            logger.info(f"[kotra] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(KOTRAScraper())
