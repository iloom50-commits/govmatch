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
