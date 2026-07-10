"""테크노파크 스크래퍼 — 6개 기관.

부산TP / 광주TP / 전남TP / 전북TP / 충남TP / 울산TP
각 사이트 고유 URL 구조로 개별 구현.
"""
from __future__ import annotations
import logging
import re
import requests
from typing import List, Dict, Any

from .base import BaseScraper, SCRAPER_REGISTRY

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
# 일부 정부사이트 WAF가 최소 UA를 차단 → 실제 브라우저 UA(프로덕션 fetch 성공률 개선 시도)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _get(url: str, **kwargs) -> str:
    kwargs.setdefault("timeout", 20)
    try:
        resp = requests.get(url, headers=_HEADERS, **kwargs)
    except requests.exceptions.SSLError:
        # 일부 정부사이트 SSL 체인이 특정 환경(예: Railway)에서 거부됨 → verify=False 재시도
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            kwargs["verify"] = False
            resp = requests.get(url, headers=_HEADERS, **kwargs)
    resp.raise_for_status()
    return resp.text


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _clean_title(raw: str) -> str:
    return re.sub(r"\s+", " ", _strip_tags(raw)).strip()


def _parse_deadline(text: str) -> str | None:
    """두 번째 날짜를 마감일로 사용, 없으면 첫 번째."""
    dates = _DATE_RE.findall(text or "")
    if len(dates) >= 2:
        y, m, d = dates[1]
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    if dates:
        y, m, d = dates[0]
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return None


def _extract_rows(html: str, link_re: re.Pattern, key_group: int,
                  base_url: str, region: str, url_builder) -> List[Dict[str, Any]]:
    """공통 행 추출 헬퍼: link_re로 (href_full, key, title_raw) 추출."""
    results = []
    for m in link_re.finditer(html):
        key = m.group(key_group)
        title_raw = m.group(m.lastindex)  # 마지막 그룹 = 제목 raw HTML
        title = _clean_title(title_raw)
        if not title or len(title) < 5:
            continue
        # 제목 앞뒤 TR 컨텍스트에서 날짜 추출 시도
        start = max(0, m.start() - 400)
        ctx = html[start: m.end() + 400]
        deadline = _parse_deadline(ctx)
        if not title.startswith("["):
            title = f"[{region}] {title}"
        results.append({
            "title": title[:400],
            "origin_url": url_builder(key),
            "region": region,
            "target_type": "business",
            "category": None,
            "summary_text": None,
            "deadline_date": deadline,
            "support_amount": None,
        })
    return results


# ─────────────────────────────────────────────────
# 1. 부산테크노파크 (btp.or.kr)
# ─────────────────────────────────────────────────
_BTP_BASE = "https://www.btp.or.kr"
_BTP_LIST = f"{_BTP_BASE}/kor/CMS/Board/Board.do?mCode=MN013&page={{page}}"
# <a href='...board_seq=N...'><span class="titleHover">제목</span><span class="subjectWr">제목(중복)</span></a>
# → 첫 번째 span만 추출
_BTP_RE = re.compile(
    r"""href=['"]([^'"]*board_seq=(\d+)[^'"]*)['"]\s*[^>]*>.*?<span[^>]*>(.*?)</span>""",
    re.DOTALL,
)


class BtpScraper(BaseScraper):
    name = "busan_tp"
    display_name = "부산테크노파크"
    origin_url_prefix = f"{_BTP_BASE}/kor/CMS/Board/"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()
        for page in range(1, 11):
            try:
                html = _get(_BTP_LIST.format(page=page))
            except Exception:
                break
            found_new = False
            for m in _BTP_RE.finditer(html):
                seq = m.group(2)
                if seq in seen:
                    continue
                seen.add(seq)
                found_new = True
                title = _clean_title(m.group(3))
                if not title or len(title) < 5:
                    continue
                ctx = html[max(0, m.start()-300): m.end()+300]
                if not title.startswith("["):
                    title = f"[부산] {title}"
                items.append({
                    "title": title[:400],
                    "origin_url": f"{_BTP_BASE}/kor/CMS/Board/Board.do?mCode=MN013&mode=view&mgr_seq=16&board_seq={seq}",
                    "region": "부산",
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })
            if not found_new:
                break
        return items


SCRAPER_REGISTRY.append(BtpScraper())


# ─────────────────────────────────────────────────
# 2. 광주테크노파크 (gjtp.or.kr)
# ─────────────────────────────────────────────────
_GJTP_BASE = "https://www.gjtp.or.kr"
_GJTP_LIST = f"{_GJTP_BASE}/home/business.cs?pageIndex={{page}}"
_GJTP_RE = re.compile(
    r"""href=['"]([^'"]*bsnssId=(\d+)[^'"]*)['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class GjtpScraper(BaseScraper):
    name = "gwangju_tp"
    display_name = "광주테크노파크"
    origin_url_prefix = f"{_GJTP_BASE}/home/business.cs"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()
        for page in range(1, 11):
            try:
                html = _get(_GJTP_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[gwangju_tp] 페이지{page} 요청 실패: {type(e).__name__}: {e}")
                break
            found_new = False
            for m in _GJTP_RE.finditer(html):
                bid = m.group(2)
                if bid in seen:
                    continue
                seen.add(bid)
                found_new = True
                title = _clean_title(m.group(3))
                if not title or len(title) < 5:
                    continue
                ctx = html[max(0, m.start()-300): m.end()+300]
                if not title.startswith("["):
                    title = f"[광주] {title}"
                items.append({
                    "title": title[:400],
                    "origin_url": f"{_GJTP_BASE}/home/business.cs?act=view&bsnssId={bid}",
                    "region": "광주",
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })
            if not found_new:
                break
        return items


SCRAPER_REGISTRY.append(GjtpScraper())


# ─────────────────────────────────────────────────
# 3. 전남테크노파크 (jntp.or.kr)
# ─────────────────────────────────────────────────
_JNTP_BASE = "https://www.jntp.or.kr"
# 정부사업공고(boardManagementNo=13) + JNTP사업공고(11) 두 게시판 수집
_JNTP_BOARDS = [
    (13, 46, "정부사업공고"),
    (11, 44, "JNTP사업공고"),
]
_JNTP_RE = re.compile(
    r"""href=['"]([^'"]*boardNo=(\d+)[^'"]*)['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class JntpScraper(BaseScraper):
    name = "jeonnam_tp"
    display_name = "전남테크노파크"
    origin_url_prefix = f"{_JNTP_BASE}/base/board/read"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()
        for board_no, menu_no, _ in _JNTP_BOARDS:
            for page in range(1, 11):
                try:
                    url = (
                        f"{_JNTP_BASE}/base/board/list"
                        f"?boardManagementNo={board_no}&menuLevel=2&menuNo={menu_no}&page={page}"
                    )
                    html = _get(url)
                except Exception as e:
                    logger.warning(f"[jeonnam_tp] board{board_no} 페이지{page} 요청 실패: {type(e).__name__}: {e}")
                    break
                found_new = False
                for m in _JNTP_RE.finditer(html):
                    bn = m.group(2)
                    if bn in seen:
                        continue
                    seen.add(bn)
                    found_new = True
                    title = _clean_title(m.group(3))
                    if not title or len(title) < 5:
                        continue
                    ctx = html[max(0, m.start()-300): m.end()+300]
                    if not title.startswith("["):
                        title = f"[전남] {title}"
                    items.append({
                        "title": title[:400],
                        "origin_url": (
                            f"{_JNTP_BASE}/base/board/read"
                            f"?boardManagementNo={board_no}&boardNo={bn}&menuLevel=2&menuNo={menu_no}"
                        ),
                        "region": "전남",
                        "target_type": "business",
                        "category": None,
                        "summary_text": None,
                        "deadline_date": _parse_deadline(ctx),
                        "support_amount": None,
                    })
                if not found_new:
                    break
        return items


SCRAPER_REGISTRY.append(JntpScraper())


# ─────────────────────────────────────────────────
# 4. 전북테크노파크 (jbtp.or.kr)
# ─────────────────────────────────────────────────
_JBTP_BASE = "https://www.jbtp.or.kr"
_JBTP_LIST = (
    f"{_JBTP_BASE}/board/list.jbtp"
    "?boardId=BBS_0000006&menuCd=DOM_000000102001000000&pageNo={page}"
)
_JBTP_RE = re.compile(
    r"""href=['"]([^'"]*dataSid=(\d+)[^'"]*)['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class JbtpScraper(BaseScraper):
    name = "jeonbuk_tp"
    display_name = "전북테크노파크"
    origin_url_prefix = f"{_JBTP_BASE}/board/view.jbtp"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()
        for page in range(1, 11):
            try:
                html = _get(_JBTP_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[jeonbuk_tp] 페이지{page} 요청 실패: {type(e).__name__}: {e}")
                break
            found_new = False
            for m in _JBTP_RE.finditer(html):
                sid = m.group(2)
                if sid in seen:
                    continue
                seen.add(sid)
                found_new = True
                title = _clean_title(m.group(3))
                if not title or len(title) < 5:
                    continue
                ctx = html[max(0, m.start()-300): m.end()+300]
                if not title.startswith("["):
                    title = f"[전북] {title}"
                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_JBTP_BASE}/board/view.jbtp"
                        f"?menuCd=DOM_000000102001000000&boardId=BBS_0000006&dataSid={sid}"
                    ),
                    "region": "전북",
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })
            if not found_new:
                break
        return items


SCRAPER_REGISTRY.append(JbtpScraper())


# ─────────────────────────────────────────────────
# 5. 충남테크노파크 (ctp.or.kr)
# ─────────────────────────────────────────────────
_CTP_BASE = "https://www.ctp.or.kr"
_CTP_LIST = f"{_CTP_BASE}/business/data.do?pn={{page}}"
_CTP_RE = re.compile(
    r"""href=['"]([^'"]*datadetail\.do\?seq=(\d+)[^'"]*)['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class CtpScraper(BaseScraper):
    name = "chungnam_tp"
    display_name = "충남테크노파크"
    origin_url_prefix = f"{_CTP_BASE}/business/datadetail.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()
        for page in range(1, 11):
            try:
                html = _get(_CTP_LIST.format(page=page))
            except Exception:
                break
            found_new = False
            for m in _CTP_RE.finditer(html):
                seq = m.group(2)
                if seq in seen:
                    continue
                seen.add(seq)
                found_new = True
                title = _clean_title(m.group(3))
                if not title or len(title) < 5:
                    continue
                ctx = html[max(0, m.start()-300): m.end()+300]
                if not title.startswith("["):
                    title = f"[충남] {title}"
                items.append({
                    "title": title[:400],
                    "origin_url": f"{_CTP_BASE}/business/datadetail.do?seq={seq}",
                    "region": "충남",
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })
            if not found_new:
                break
        return items


SCRAPER_REGISTRY.append(CtpScraper())


# ─────────────────────────────────────────────────
# 6. 울산테크노파크 — 신 플랫폼 platform.utp.or.kr (기업지원사업 관리시스템)
#    구 board.php(sub0203_02)는 2024년 死板 → 공고가 이 시스템으로 이전.
#    공고: <a onclick="goViewGonggo('<id>')">공고명</a>, 상세는 biz_gonggo_detail.php.
# ─────────────────────────────────────────────────
_UTP_BASE = "https://platform.utp.or.kr"
_UTP_LIST = f"{_UTP_BASE}/com/biz_gonggo_all.php?page={{page}}"
_UTP_RE = re.compile(r"goViewGonggo\('(\d+)'\)[^>]*>(.*?)</a>", re.DOTALL)
_UTP_EXCLUDE = re.compile(r"채용|입찰|구매|계약|낙찰|사칭")


class UtpScraper(BaseScraper):
    name = "ulsan_tp"
    display_name = "울산테크노파크"
    origin_url_prefix = f"{_UTP_BASE}/com/biz_gonggo_detail.php"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()
        for page in range(1, 6):
            try:
                html = _get(_UTP_LIST.format(page=page), verify=False)
            except Exception:
                break
            new = self._parse_list(html, seen)
            if not new:
                break
            items.extend(new)
        return items

    def _parse_list(self, html: str, seen: set) -> List[Dict[str, Any]]:
        """목록 HTML에서 공고(goViewGonggo id) 추출 — 픽스처 단위테스트 대상 순수 파서."""
        out: List[Dict[str, Any]] = []
        for m in _UTP_RE.finditer(html):
            gid = m.group(1)
            if gid in seen:
                continue
            title = _clean_title(m.group(2))
            if not title or len(title) < 5 or _UTP_EXCLUDE.search(title):
                continue
            seen.add(gid)
            if not title.startswith("["):
                title = f"[울산] {title}"
            out.append({
                "title": title[:400],
                "origin_url": f"{_UTP_BASE}/com/biz_gonggo_detail.php?rq_gonggopgrm={gid}&cmd=detail",
                "region": "울산",
                "target_type": "business",
                "category": None,
                "summary_text": None,
                "deadline_date": None,  # 목록은 대부분 상시 — 마감 미상(None)으로 저장, enricher가 보강
                "support_amount": None,
            })
        return out


SCRAPER_REGISTRY.append(UtpScraper())


# ─────────────────────────────────────────────────
# 7. 대전테크노파크 (djtp.or.kr)
# 목록: /pbanc?mid=a20101000000&nPage=N
# 상세: pms.dips.or.kr/sso/business.jsp?gubun=pbancView&pbanc_no=XXXX
# ─────────────────────────────────────────────────
_DJTP_BASE = "https://djtp.or.kr"
_DJTP_LIST = f"{_DJTP_BASE}/pbanc?mid=a20101000000&nPage={{page}}"
_DJTP_PBANC_RE = re.compile(r"pbanc_no=([\d\-]+)")
_DJTP_PDF_TITLE_RE = re.compile(
    r'href=["\'][^"\']*pdfviewer[^"\']*["\'][^>]*>\s*(.*?)\s*</a>',
    re.DOTALL | re.IGNORECASE,
)


class DjtpScraper(BaseScraper):
    name = "daejeon_tp"
    display_name = "대전테크노파크"
    origin_url_prefix = "https://pms.dips.or.kr/sso/business.jsp"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()
        for page in range(1, 11):
            try:
                html = _get(_DJTP_LIST.format(page=page))
            except Exception as e:
                logger.warning(f"[daejeon_tp] 페이지{page} 요청 실패: {type(e).__name__}: {e}")
                break
            found_new = False
            rows = re.split(r"<tr[\s>]", html, flags=re.IGNORECASE)
            for row in rows:
                pbanc_m = _DJTP_PBANC_RE.search(row)
                if not pbanc_m:
                    continue
                pbanc_no = pbanc_m.group(1)
                if pbanc_no in seen:
                    continue
                seen.add(pbanc_no)
                found_new = True
                title_m = _DJTP_PDF_TITLE_RE.search(row)
                if title_m:
                    raw = _clean_title(title_m.group(1))
                    # "YYYY-NN-NNNN" 형식 pbanc_no 접두어 제거 (구분자: " - " 또는 공백)
                    raw = re.sub(r"^\d{4}-\d{2}-\d{4}\s*[-–]?\s*", "", raw).strip()
                else:
                    raw = ""
                if not raw or len(raw) < 5:
                    continue
                title = f"[대전] {raw}" if not raw.startswith("[") else raw
                # pbanc_no 문자열("2026-01-0078")이 날짜로 오인되지 않도록 제거 후 파싱
                row_for_date = _DJTP_PBANC_RE.sub("", row)
                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"https://pms.dips.or.kr/sso/business.jsp"
                        f"?gubun=pbancView&pbanc_no={pbanc_no}"
                    ),
                    "region": "대전",
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_deadline(row_for_date),
                    "support_amount": None,
                })
            if not found_new:
                break
        return items


SCRAPER_REGISTRY.append(DjtpScraper())
