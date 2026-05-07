"""경남테크노파크(GNTP) 스크래퍼.

사이트: https://www.gntp.or.kr/biz/apply
구조: JS 렌더링 필요, 공고 링크는 onclick=goPage('S', null, '/biz/applyInfo/{id}') 형식
"""
from __future__ import annotations
import re
import asyncio
import datetime
from typing import List, Dict, Any

from .base import BaseScraper, SCRAPER_REGISTRY

BASE_URL = "https://www.gntp.or.kr"
LIST_URL = f"{BASE_URL}/biz/apply"

_GOPAGE_RE = re.compile(r"goPage\([^,]+,\s*[^,]+,\s*'(/biz/applyInfo/\d+)'\)")


def _parse_date(text: str) -> str | None:
    """YYYY-MM-DD 형식 날짜 추출."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return m.group(0)
    return None


class GntpScraper(BaseScraper):
    name = "gntp"
    display_name = "경남테크노파크"
    origin_url_prefix = "https://www.gntp.or.kr/biz/applyInfo/"

    def fetch_items(self) -> List[Dict[str, Any]]:
        return asyncio.run(self._fetch_async())

    async def _fetch_async(self) -> List[Dict[str, Any]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return []

        items: List[Dict[str, Any]] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"}
            )
            try:
                await page.goto(LIST_URL, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)

                # onclick에서 공고 ID 추출 (a 태그 onclick 구조)
                tds = await page.eval_on_selector_all("a[onclick*='/biz/applyInfo/']", """
                    els => els.map(e => ({
                        text: e.innerText.trim(),
                        onclick: e.getAttribute('onclick') || ''
                    }))
                """)

                # 날짜 텍스트: tr 전체에서 추출
                rows = await page.eval_on_selector_all("tr", """
                    els => els.map(tr => tr.innerText.trim())
                """)

                # td onclick → applyInfo URL 매핑
                row_texts = "\n".join(rows)
                for td in tds:
                    m = _GOPAGE_RE.search(td["onclick"])
                    if not m:
                        continue
                    path = m.group(1)
                    origin_url = f"{BASE_URL}{path}"
                    title = td["text"][:400]
                    if not title or len(title) < 5:
                        continue

                    # 마감일 추출 (같은 행 텍스트에서)
                    deadline = None
                    for row in rows:
                        if title[:20] in row:
                            dates = re.findall(r"\d{4}-\d{2}-\d{2}", row)
                            if len(dates) >= 2:
                                deadline = dates[1]  # 두 번째 날짜 = 마감일
                            break

                    items.append({
                        "title": title,
                        "origin_url": origin_url,
                        "region": "경남",
                        "target_type": "business",
                        "category": None,
                        "summary_text": None,
                        "deadline_date": deadline,
                        "support_amount": None,
                    })

                    if len(items) >= 30:
                        break

            finally:
                await browser.close()

        return items


SCRAPER_REGISTRY.append(GntpScraper())
