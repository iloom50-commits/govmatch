"""지역 테크노파크 스크래퍼 — 경기TP / 경북TP / 충북TP / 강원TP.

gtp.or.kr   : 경기테크노파크 (pms.gtp.or.kr, GET + title attr)
gbtp.or.kr  : 경북테크노파크 (GET, fn_detail → nttNo)
cbtp.or.kr  : 충북테크노파크 (GET, no= 파라미터, Legacy SSL 필요)
gwtp.or.kr  : 강원테크노파크 (GET, bbs_data=base64 파라미터)
"""
from __future__ import annotations
import base64
import re
import ssl
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


def _get(url: str, session: requests.Session | None = None, **kwargs) -> str:
    s = session or requests
    resp = s.get(url, headers=_HEADERS, timeout=20, **kwargs)
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


def _legacy_ssl_session() -> requests.Session:
    """DH key too small SSL 오류 우회용 세션 (충북TP 등)."""
    try:
        from requests.adapters import HTTPAdapter
        from urllib3.util.ssl_ import create_urllib3_context

        class _LegacyAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                ctx = create_urllib3_context()
                ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                kwargs["ssl_context"] = ctx
                super().init_poolmanager(*args, **kwargs)

        sess = requests.Session()
        sess.mount("https://", _LegacyAdapter())
        return sess
    except Exception:
        return requests.Session()


# ─────────────────────────────────────────────────────────────
# 1. 경기테크노파크 (pms.gtp.or.kr)
#    GET 목록, onclick="fn_goView('b_idx')" + title="제목"
# ─────────────────────────────────────────────────────────────
_GTP_BASE = "https://pms.gtp.or.kr"
_GTP_LIST = f"{_GTP_BASE}/web/business/webBusinessList.do?page={{page}}"
_GTP_RE = re.compile(
    r"""onclick="fn_goView\('(\d+)'\)[^"]*"\s+title="([^"]+)""",
    re.DOTALL,
)


class GtpScraper(BaseScraper):
    name = "gyeonggi_tp"
    display_name = "경기테크노파크(GTP)"
    origin_url_prefix = f"{_GTP_BASE}/web/business/webBusinessView.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_GTP_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _GTP_RE.finditer(html):
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

                if not title.startswith("["):
                    title = f"[경기] {title}"

                items.append({
                    "title": title[:400],
                    "origin_url": f"{_GTP_BASE}/web/business/webBusinessView.do?b_idx={b_idx}",
                    "region": "경기",
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(GtpScraper())


# ─────────────────────────────────────────────────────────────
# 2. 경북테크노파크 (gbtp.or.kr)
#    GET 목록, onclick="fn_detail('nttNo','rnum')"
# ─────────────────────────────────────────────────────────────
_GBTP_BASE = "https://www.gbtp.or.kr"
_GBTP_LIST = (
    f"{_GBTP_BASE}/user/board.do"
    "?bbsId=BBSMSTR_000000000021&pageIndex={page}"
)
_GBTP_RE = re.compile(
    r"""fn_detail\('(\d+)','(\d+)'\)[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class GbtpScraper(BaseScraper):
    name = "gyeongbuk_tp"
    display_name = "경북테크노파크(GBTP)"
    origin_url_prefix = f"{_GBTP_BASE}/user/boardDetail.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_GBTP_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _GBTP_RE.finditer(html):
                ntt_no = m.group(1)
                if ntt_no in seen:
                    continue
                seen.add(ntt_no)
                found_new = True

                title = _clean(m.group(3))
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                ctx = html[max(0, m.start() - 400): m.end() + 400]

                if not title.startswith("["):
                    title = f"[경북] {title}"

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_GBTP_BASE}/user/boardDetail.do"
                        f"?nttNo={ntt_no}&bbsId=BBSMSTR_000000000021"
                    ),
                    "region": "경북",
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(GbtpScraper())


# ─────────────────────────────────────────────────────────────
# 3. 충북테크노파크 (cbtp.or.kr)
#    GET, no= 파라미터 (contact_XXXX 또는 숫자), Legacy SSL
# ─────────────────────────────────────────────────────────────
_CBTP_BASE = "https://www.cbtp.or.kr"
_CBTP_LIST = (
    f"{_CBTP_BASE}/index.php"
    "?control=bbs&board_id=saup_notice&lm_uid=387"
    "&page={page}&offset={offset}&task=list"
)
_CBTP_RE = re.compile(
    r"""href=['"]/index\.php\?control=bbs(?:&amp;|&)board_id=saup_notice(?:&amp;|&)mode=view(?:&amp;|&)no=([^&'"]+)[^'"]*['"]\s*[^>]*>(.*?)</a>""",
    re.DOTALL,
)


class CbtpScraper(BaseScraper):
    name = "chungbuk_tp"
    display_name = "충북테크노파크(CBTP)"
    origin_url_prefix = f"{_CBTP_BASE}/index.php"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()
        session = _legacy_ssl_session()

        for page in range(1, 11):
            offset = (page - 1) * 15 + 1
            try:
                html = _get(
                    _CBTP_LIST.format(page=page, offset=offset),
                    session=session,
                    verify=False,
                )
            except Exception:
                break

            found_new = False
            for m in _CBTP_RE.finditer(html):
                no = m.group(1)
                if no in seen:
                    continue
                seen.add(no)
                found_new = True

                title = _clean(m.group(2))
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                ctx = html[max(0, m.start() - 400): m.end() + 400]

                if not title.startswith("["):
                    title = f"[충북] {title}"

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_CBTP_BASE}/index.php"
                        f"?control=bbs&board_id=saup_notice&mode=view&no={no}&lm_uid=387"
                    ),
                    "region": "충북",
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(CbtpScraper())


# ─────────────────────────────────────────────────────────────
# 4. 강원테크노파크 (gwtp.or.kr)
#    GET /gwtp/bbsNew_list.php, bbs_data=base64(idx=N&...) 파라미터
# ─────────────────────────────────────────────────────────────
_GWTP_BASE = "https://www.gwtp.or.kr"
_GWTP_LIST = (
    f"{_GWTP_BASE}/gwtp/bbsNew_list.php"
    "?code=sub01b&keyvalue=sub01&page={page}"
)
_GWTP_RE = re.compile(
    r"""href=["']bbsNew_view\.php\?bbs_data=([A-Za-z0-9+/=]+)\|\|["'][^>]*>(.*?)</a>""",
    re.DOTALL,
)


def _gwtp_idx(bbs_data_b64: str) -> str | None:
    """bbs_data base64 → idx 값 추출."""
    try:
        padding = 4 - len(bbs_data_b64) % 4
        decoded = base64.b64decode(bbs_data_b64 + "=" * (padding % 4)).decode("utf-8", errors="replace")
        m = re.search(r"idx=(\d+)", decoded)
        return m.group(1) if m else None
    except Exception:
        return None


class GwtpScraper(BaseScraper):
    name = "gangwon_tp"
    display_name = "강원테크노파크(GWTP)"
    origin_url_prefix = f"{_GWTP_BASE}/gwtp/bbsNew_view.php"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                html = _get(_GWTP_LIST.format(page=page))
            except Exception:
                break

            found_new = False
            for m in _GWTP_RE.finditer(html):
                bbs_data = m.group(1)
                idx = _gwtp_idx(bbs_data)
                key = idx or bbs_data[:20]

                if key in seen:
                    continue
                seen.add(key)
                found_new = True

                title = _clean(m.group(2))
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                ctx = html[max(0, m.start() - 400): m.end() + 400]

                if not title.startswith("["):
                    title = f"[강원] {title}"

                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_GWTP_BASE}/gwtp/bbsNew_view.php"
                        f"?bbs_data={bbs_data}||"
                    ),
                    "region": "강원",
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": _parse_deadline(ctx),
                    "support_amount": None,
                })

            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(GwtpScraper())


# ─────────────────────────────────────────────────────────────
# 5. 대구테크노파크 (dgtp.or.kr)
#    eGovFramework 표준 게시판 — SSL 인증서 오류 우회 필요
#    GET /bbs/BoardControll.do?bbsId=BBSMSTR_000000000003&pageNo={page}
#    fn_egov_inqire_notice(nttId, bbsId, userId) → BoardControllView.do
# ─────────────────────────────────────────────────────────────
_DGTP_BASE = "https://dgtp.or.kr"
_DGTP_LIST = (
    f"{_DGTP_BASE}/bbs/BoardControll.do"
    "?bbsId=BBSMSTR_000000000003&pageNo={page}"
)
_DGTP_BBS_ID = "BBSMSTR_000000000003"
_DGTP_ITEM_RE = re.compile(
    r"""fn_egov_inqire_notice\('(\d+)',\s*'BBSMSTR_000000000003',\s*'[^']*'\)">\s*(.*?)\s*</a>""",
    re.DOTALL,
)
_DGTP_DEADLINE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})")


def _dgtp_session() -> requests.Session:
    """SSL 인증서 검증 비활성화 세션 (자체 서명 인증서)."""
    sess = requests.Session()
    sess.verify = False
    return sess


class DgtpScraper(BaseScraper):
    name = "dgtp"
    display_name = "대구테크노파크(DGTP)"
    origin_url_prefix = f"{_DGTP_BASE}/bbs/BoardControllView.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        import datetime as _dt
        items: List[Dict[str, Any]] = []
        seen: set = set()
        sess = _dgtp_session()
        today = _dt.date.today()

        for page_idx in range(1, 51):  # 최대 50페이지 (pageUnit=10 → 500건)
            try:
                resp = sess.post(
                    f"{_DGTP_BASE}/bbs/BoardControll.do",
                    headers={**_HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                             "Referer": f"{_DGTP_BASE}/bbs/BoardControll.do?bbsId={_DGTP_BBS_ID}"},
                    data={"bbsId": _DGTP_BBS_ID, "pageIndex": str(page_idx), "pageUnit": "10"},
                    timeout=20,
                )
                resp.raise_for_status()
                html = resp.content.decode("utf-8", errors="replace")
            except Exception:
                break

            # tooltip span 제거 — 동일 텍스트 중복 방지
            html_clean = re.sub(
                r'<span\s+class="tooltiptext">.*?</span>', "", html, flags=re.DOTALL
            )

            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html_clean, re.DOTALL)
            bbs_rows = [r for r in rows if "fn_egov_inqire_notice" in r]
            if not bbs_rows:
                break

            found_new = False
            all_expired = True  # 페이지 전체가 마감 완료이면 중단

            for row in bbs_rows:
                m = _DGTP_ITEM_RE.search(row)
                if not m:
                    continue
                ntt_id = m.group(1)
                if ntt_id in seen:
                    continue
                seen.add(ntt_id)

                dl_m = _DGTP_DEADLINE_RE.search(row)
                deadline = dl_m.group(2) if dl_m else None

                # 마감일 확인 — 지난 것은 스킵, 단 deadline 없는 것(상시모집)은 통과
                if deadline:
                    try:
                        if _dt.date.fromisoformat(deadline) < today:
                            continue  # 마감 지난 것은 수집 안 함
                    except Exception:
                        pass
                    all_expired = False  # 마감일 있고 아직 유효
                else:
                    all_expired = False  # 상시모집은 유효로 간주

                title_raw = re.sub(r"<[^>]+>", " ", m.group(2))
                title = re.sub(r"\s+", " ", title_raw).strip()
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                found_new = True
                items.append({
                    "title": title[:400],
                    "origin_url": (
                        f"{_DGTP_BASE}/bbs/BoardControllView.do"
                        f"?nttId={ntt_id}&bbsId={_DGTP_BBS_ID}"
                    ),
                    "region": "대구",
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": deadline,
                    "support_amount": None,
                })

            # 이 페이지의 모든 공고가 마감됐으면 이후 페이지도 마감 → 중단
            if all_expired:
                break
            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(DgtpScraper())


# ─────────────────────────────────────────────────────────────
# 6. 제주테크노파크 (jejutp.or.kr)
#    Spring + Vue 2.6 — 내부 JSON API 사용
#    GET /board/business/list?keyword=&page={page}&size=30&businessDiv=
#    Content-Type: application/json 필수 (axios 기본값 일치)
#    Spring Page 응답: {content: [...], totalPages, totalElements}
# ─────────────────────────────────────────────────────────────
_JEJU_BASE = "https://www.jejutp.or.kr"
_JEJU_API = f"{_JEJU_BASE}/board/business/list"
_JEJU_API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": f"{_JEJU_BASE}/board/business",
}


class JejuTpScraper(BaseScraper):
    name = "jejutp"
    display_name = "제주테크노파크(JTP)"
    origin_url_prefix = f"{_JEJU_BASE}/board/business/detail/"

    def fetch_items(self) -> List[Dict[str, Any]]:
        import datetime as _dt
        items: List[Dict[str, Any]] = []
        seen: set = set()
        today = _dt.date.today()

        for page in range(0, 30):  # 0-indexed Spring pagination, 최대 30페이지
            try:
                resp = requests.get(
                    _JEJU_API,
                    headers=_JEJU_API_HEADERS,
                    params={"keyword": "", "page": page, "size": 30, "businessDiv": ""},
                    timeout=20,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                break

            content = data.get("content", [])
            if not content:
                break

            found_new = False
            all_expired = True

            for item in content:
                post_id = str(item.get("id", ""))
                if not post_id or post_id in seen:
                    continue
                seen.add(post_id)

                deadline = item.get("receiptEDate") or None

                # 마감일 지난 것 스킵
                if deadline:
                    try:
                        if _dt.date.fromisoformat(str(deadline)) < today:
                            continue
                    except Exception:
                        pass
                    all_expired = False
                else:
                    all_expired = False

                title = (item.get("annoName") or item.get("businessName") or "").strip()
                if not title or len(title) < 5:
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                found_new = True
                items.append({
                    "title": title[:400],
                    "origin_url": f"{_JEJU_BASE}/board/business/detail/{post_id}",
                    "region": "제주",
                    "target_type": "business",
                    "category": item.get("businessDivName") or None,
                    "summary_text": None,
                    "deadline_date": deadline,
                    "support_amount": None,
                })

            if all_expired:
                break
            if not found_new:
                break

        return items


SCRAPER_REGISTRY.append(JejuTpScraper())
