"""Playwright 기반 스크래퍼 — JS 렌더링 필요 사이트 (로컬 전용)

kosmes.or.kr  : 중소기업진흥공단(중진공) 사업공고  — fn_detail(seqNo)
kiat.or.kr    : 한국산업기술진흥원(KIAT) 사업공고  — contentsView(hash)

Railway 서버에는 Playwright 없음 → 관리자 대시보드 /local-scrapers/run 에서만 실행.
"""
from __future__ import annotations
import html as html_lib
import re
import time
from typing import List, Dict, Any

_EXCLUDE_KW = re.compile(r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품|청소|경비|보안|퇴직|임원")
_DATE_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
_DEADLINE_RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})~(\d{4}-\d{2}-\d{2})")


def _parse_date(text: str) -> str | None:
    m = _DATE_RE.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return None


def _launch_browser():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    return pw, browser


# ─────────────────────────────────────────────────────────────
# 1. 중소기업진흥공단 (kosmes.or.kr) — 사업공고
# ─────────────────────────────────────────────────────────────
_KOSMES_BASE = "https://www.kosmes.or.kr"
_KOSMES_LIST = f"{_KOSMES_BASE}/nsh/SH/NTS/SHNTS001M0.do"
_KOSMES_SEQ_RE = re.compile(r"fn_detail\s*\(\s*(\d+)\s*\)")


class KosmesPWScraper:
    name = "kosmes"
    display_name = "중소기업진흥공단(중진공)"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()
        pw, browser = _launch_browser()

        try:
            page = browser.new_page()
            for pg_num in range(1, 6):
                try:
                    page.goto(
                        f"{_KOSMES_LIST}?pageIndex={pg_num}&pageUnit=10",
                        wait_until="networkidle",
                        timeout=30000,
                    )
                    rows = page.query_selector_all("table tbody tr")
                except Exception:
                    break

                found_new = False
                for row in rows:
                    link = row.query_selector("a[onclick]")
                    if not link:
                        continue

                    onclick = link.get_attribute("onclick") or ""
                    m = _KOSMES_SEQ_RE.search(onclick)
                    if not m:
                        continue
                    seq = m.group(1)
                    if seq in seen:
                        continue

                    title = html_lib.unescape(link.inner_text().strip())
                    if not title or len(title) < 5:
                        continue
                    if _EXCLUDE_KW.search(title):
                        continue

                    seen.add(seq)
                    found_new = True

                    row_text = row.inner_text()
                    deadline = _parse_date(row_text)

                    items.append({
                        "title": title[:400],
                        "origin_url": f"{_KOSMES_BASE}/nsh/SH/NTS/SHNTS001M0.do?seq={seq}",
                        "region": "전국",
                        "target_type": "business",
                        "category": "자금·지원",
                        "summary_text": None,
                        "deadline_date": deadline,
                        "support_amount": None,
                    })

                if not found_new:
                    break
                time.sleep(0.5)

            page.close()
        finally:
            browser.close()
            pw.stop()

        return items


# ─────────────────────────────────────────────────────────────
# 2. 한국산업기술진흥원 (kiat.or.kr) — 사업공고
# ─────────────────────────────────────────────────────────────
_KIAT_BASE = "https://www.kiat.or.kr"
_KIAT_LIST = (
    f"{_KIAT_BASE}/front/board/boardContentsListPage.do"
    "?board_id=90&MenuId=b159c9dac684471b87256f1e25404f5e"
)
_KIAT_HASH_RE = re.compile(r"contentsView\s*\(\s*['\"](\w+)['\"]\s*\)")


class KiatPWScraper:
    name = "kiat"
    display_name = "한국산업기술진흥원(KIAT)"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()
        pw, browser = _launch_browser()

        try:
            page = browser.new_page()
            for pg_num in range(1, 6):
                try:
                    url = f"{_KIAT_LIST}&page={pg_num}" if pg_num > 1 else _KIAT_LIST
                    page.goto(url, wait_until="networkidle", timeout=30000)
                    rows = page.query_selector_all("table tbody tr")
                except Exception:
                    break

                found_new = False
                for row in rows:
                    link = row.query_selector("a[href*='contentsView']")
                    if not link:
                        continue

                    href = link.get_attribute("href") or ""
                    m = _KIAT_HASH_RE.search(href)
                    if not m:
                        continue
                    cid = m.group(1)
                    if cid in seen:
                        continue

                    title = html_lib.unescape(link.inner_text().strip())
                    if not title or len(title) < 5:
                        continue
                    if _EXCLUDE_KW.search(title):
                        continue

                    seen.add(cid)
                    found_new = True

                    # 마감일: "2026-05-08~2026-06-08" 패턴에서 끝 날짜 추출
                    row_text = row.inner_text()
                    deadline = None
                    dr = _DEADLINE_RANGE_RE.search(row_text)
                    if dr:
                        deadline = dr.group(2)  # 마감일
                    else:
                        deadline = _parse_date(row_text)

                    items.append({
                        "title": title[:400],
                        "origin_url": (
                            f"{_KIAT_BASE}/front/board/boardContentsView.do"
                            f"?contents_id={cid}"
                            f"&MenuId=b159c9dac684471b87256f1e25404f5e"
                        ),
                        "region": "전국",
                        "target_type": "business",
                        "category": "R&D",
                        "summary_text": None,
                        "deadline_date": deadline,
                        "support_amount": None,
                    })

                if not found_new:
                    break
                time.sleep(0.5)

            page.close()
        finally:
            browser.close()
            pw.stop()

        return items
