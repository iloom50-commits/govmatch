"""소스 진단자 — 조용한 admin_urls 소스의 등록 URL을 재fetch해 0건 원인 분류.

프로덕션은 진단·제안까지만(수리는 Claude 세션 TDD). 회귀감지(coverage_checker)와
분리: 진단은 외부 HTTP fetch라는 별개 관심사.
"""
from __future__ import annotations
import re
import warnings
from typing import Dict, Any, List, Optional

LINK_MANY = 5      # 공고 게시판이면 통상 목록 링크 5개 이상
BODY_STUB = 800    # 정상 렌더 페이지 가시 텍스트 하한(미만이면 JS 스텁 의심)

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# 공고 상세 링크로 볼 URL 패턴(admin_scraper._DETAIL_URL_PATTERNS와 동일 취지, 독립 정의)
_DETAIL_URL_RE = re.compile(
    r"(view|detail|read|notice|board|bbs|seq=|idx=|id=|no=|nttId=|articleId=|bid=|num=|post|content)",
    re.IGNORECASE,
)

_SUGGEST = {
    "unreachable":    "URL 폐쇄·이전 의심 — 새 URL 확인",
    "extract_fail":   "링크는 있으나 미추출 — 파서/전용 스크래퍼 점검",
    "js_only":        "JS 전용 렌더링 의심 — Playwright 전용 스크래퍼 필요",
    "wrong_or_empty": "엉뚱한 URL/빈 게시판 — 올바른 게시판 URL 확인",
}


def classify_diagnosis(http_status: Optional[int], link_count: int, body_len: int) -> Dict[str, str]:
    """순수함수. (HTTP상태, 공고링크수, 본문길이) → {diag_type, suggested_action}."""
    if http_status is None or http_status >= 400:
        t = "unreachable"
    elif link_count >= LINK_MANY:
        t = "extract_fail"
    elif body_len < BODY_STUB:
        t = "js_only"
    else:
        t = "wrong_or_empty"
    return {"diag_type": t, "suggested_action": _SUGGEST[t]}


def count_article_links(soup) -> int:
    """공고 상세 링크로 볼 <a href> 개수."""
    n = 0
    for a in soup.select("a[href]"):
        if _DETAIL_URL_RE.search(a.get("href", "")):
            n += 1
    return n


def visible_text_len(soup) -> int:
    """script/style 제외 가시 텍스트 길이."""
    for tag in soup(["script", "style"]):
        tag.extract()
    return len(soup.get_text(strip=True))


def _fetch_and_measure(url: str) -> tuple:
    """(http_status, link_count, body_len). 실패 시 (None, 0, 0). SSL 실패면 verify=False 재시도."""
    import requests
    from bs4 import BeautifulSoup
    def _do(verify):
        return requests.get(url, headers=_HEADERS, timeout=15, verify=verify)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            try:
                resp = _do(True)
            except requests.exceptions.SSLError:
                resp = _do(False)
            soup = BeautifulSoup(resp.text, "html.parser")
            return resp.status_code, count_article_links(soup), visible_text_len(soup)
        except Exception:
            return None, 0, 0


def _admin_source_name(origin_source: str) -> Optional[str]:
    """origin_source 'admin-manual:X' → admin_urls.source_name 'X'. 그 외 접두는 None(진단 대상 아님)."""
    if origin_source and origin_source.startswith("admin-manual:"):
        return origin_source[len("admin-manual:"):]
    return None


def diagnose_silent_sources(conn, silent_origin_sources: List[str]) -> int:
    """주1회. 조용한 admin-manual 소스의 admin_urls URL을 재fetch·분류해 coverage_targets diag_* 갱신.
    반환: 진단한 소스 수."""
    cur = conn.cursor()
    diagnosed = 0
    for origin in silent_origin_sources or []:
        name = _admin_source_name(origin)
        if not name:
            continue  # scraper:*/*-api 는 admin_urls에 없음 → 대상 아님
        try:
            cur.execute("SELECT url FROM admin_urls WHERE source_name = %s AND is_active = 1 LIMIT 1", (name,))
            row = cur.fetchone()
            if not row or not row.get("url"):
                continue
            status, links, body = _fetch_and_measure(row["url"])
            d = classify_diagnosis(status, links, body)
            cur.execute("""
                UPDATE coverage_targets
                   SET diag_type=%s, diag_detail=%s, diag_link_count=%s,
                       diag_http_status=%s, diag_at=NOW()
                 WHERE source_name = %s
            """, (d["diag_type"], d["suggested_action"], links, status, origin))
            conn.commit()
            diagnosed += 1
        except Exception:
            try: conn.rollback()
            except Exception: pass
    return diagnosed


def _search_keys(origin_source: str) -> List[str]:
    """origin_source에서 기관 검색키 추출(순수). 본명 + 괄호안 약칭.
    예: 'admin-manual:부산경제진흥원(BEPA)' → ['부산경제진흥원', 'BEPA']."""
    s = (origin_source or "").split(":", 1)[-1]
    paren = re.findall(r"[(（]([^)）]+)[)）]", s)
    main = re.sub(r"[(（][^)）]*[)）]", "", s)
    main = re.sub(r"\s*(기업지원|정책|공지공고|공고)$", "", main).strip()
    keys = [main] + [p.strip() for p in paren]
    return [k for k in keys if len(k) >= 2]


def find_redundant_coverage(conn, silent_origin_sources: List[str]) -> List[Dict[str, Any]]:
    """v2. 조용한 소스 중 '같은 기관을 최근 활성 소스가 이미 커버'하는 중복(뮤트 후보) 탐지.
    department/origin_source ILIKE 기관명 기준(신뢰도 높음). 반환: [{source, covered_by[]}]."""
    if not silent_origin_sources:
        return []
    cur = conn.cursor()
    out: List[Dict[str, Any]] = []
    for s in silent_origin_sources:
        keys = _search_keys(s)
        if not keys:
            continue
        conds = " OR ".join(["department ILIKE %s OR origin_source ILIKE %s" for _ in keys])
        params: list = [s]
        for k in keys:
            params += [f"%{k}%", f"%{k}%"]
        try:
            cur.execute(f"""
                SELECT origin_source, COUNT(*) n FROM announcements
                WHERE created_at > NOW() - INTERVAL '14 days'
                  AND origin_source <> %s AND ({conds})
                GROUP BY origin_source ORDER BY n DESC LIMIT 3
            """, params)
            rows = cur.fetchall()
        except Exception:
            try: conn.rollback()
            except Exception: pass
            rows = []
        if rows:
            out.append({"source": s, "covered_by": [r["origin_source"] for r in rows]})
    return out


def build_repair_list(conn, silent_origin_sources: List[str]) -> List[Dict[str, Any]]:
    """매일. 현재 조용한 소스들의 저장된 diag_* 스냅샷을 읽어 수리 목록 구성."""
    if not silent_origin_sources:
        return []
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT source_name, diag_type, diag_detail, diag_at
            FROM coverage_targets
            WHERE source_name = ANY(%s) AND diag_type IS NOT NULL
            ORDER BY diag_at DESC NULLS LAST
        """, (list(silent_origin_sources),))
        return [{"source": r["source_name"], "diag_type": r["diag_type"],
                 "suggested_action": r["diag_detail"],
                 "diag_at": r["diag_at"].strftime("%Y-%m-%d") if r.get("diag_at") else None}
                for r in cur.fetchall()]
    except Exception:
        try: conn.rollback()
        except Exception: pass
        return []
