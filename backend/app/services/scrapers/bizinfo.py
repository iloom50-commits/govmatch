from .base import BaseScraper
from typing import List, Dict, Any
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
from app.services.ai_service import ai_service
from app.services.scrapers.smart_html_parser import SmartHTMLParser


class BizinfoScraper(BaseScraper):
    """기업마당 (Bizinfo) 스크래퍼 - 목록 페이지에서 클릭으로 상세 URL 확보"""
    BASE_URL = "https://www.bizinfo.go.kr"
    LIST_URL = "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parser = SmartHTMLParser()

    async def scrape(self) -> List[Dict]:
        print(f"[{datetime.now()}] Starting Bizinfo Scrape...")
        results = []

        try:
            await self.start_browser()
            page = await self.browser.new_page()

            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            print(f"Loading Bizinfo list page: {self.LIST_URL}")
            await page.goto(self.LIST_URL, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(2000)

            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')

            rows = soup.select("div.table_Type_1 table tbody tr")
            if not rows:
                rows = soup.select("table.table_style01 tbody tr")

            print(f"Found {len(rows)} rows in list.")

            for idx, row in enumerate(rows[:5]):
                try:
                    link_elem = row.select_one("td.txt_l a")
                    if not link_elem:
                        continue

                    title = link_elem.get_text(strip=True)
                    href = link_elem.get('href', '')
                    onclick = link_elem.get('onclick', '')

                    if not href and not onclick:
                        continue

                    print(f"  Processing [{idx+1}]: {title[:35]}...")

                    detail_url = await self._navigate_to_detail(page, idx, href, onclick)

                    if not detail_url or detail_url == self.LIST_URL:
                        print(f"    Skipped (no valid detail URL)")
                        await page.goto(self.LIST_URL, wait_until="networkidle", timeout=30000)
                        await page.wait_for_timeout(1000)
                        continue

                    detail_html = await page.content()
                    parsed_info = self.parser.parse(detail_html, detail_url)

                    program_data = {
                        "title": title,
                        "description": parsed_info.get('main_content', '')[:3000],
                        "department": "기업마당",
                        "category": "General Business Support",
                        "region": "All",
                        "url": detail_url,
                        "origin_source": "bizinfo-scraper"
                    }

                    full_text = f"제목: {title}\n내용: {program_data['description']}"
                    details = await ai_service.extract_program_details(full_text)

                    if details:
                        program_data.update({
                            "title": details.get("title", title),
                            "department": details.get("department", "기업마당"),
                            "category": details.get("category", "General Business Support"),
                            "eligibility_logic": details.get("eligibility_logic", {}),
                            "summary_text": details.get("description", ""),
                            "summary_noun": details.get("summary_noun", title)
                        })

                    results.append(program_data)
                    print(f"    OK → {detail_url[:80]}")

                    await page.goto(self.LIST_URL, wait_until="networkidle", timeout=30000)
                    await page.wait_for_timeout(1000)

                except Exception as e:
                    print(f"    Error: {e}")
                    try:
                        await page.goto(self.LIST_URL, wait_until="networkidle", timeout=30000)
                    except Exception:
                        pass

            await self.close_browser()

        except Exception as e:
            print(f"BizinfoScraper Error: {e}")
            await self.close_browser()

        return results

    async def _navigate_to_detail(self, page, row_index: int, href: str, onclick: str) -> str:
        """
        목록 행을 클릭하여 상세 페이지로 이동하고 실제 URL을 반환.
        href가 불완전한 경우(hashCode= 빈 값 등) 직접 클릭 방식으로 전환.
        """
        is_href_valid = href and 'pblancId=' in href and 'pblancId=&' not in href

        if is_href_valid:
            detail_url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
            await page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)
            return page.url

        try:
            selector = f"div.table_Type_1 table tbody tr:nth-child({row_index + 1}) td.txt_l a"
            alt_selector = f"table.table_style01 tbody tr:nth-child({row_index + 1}) td.txt_l a"

            link = page.locator(selector).first
            if await link.count() == 0:
                link = page.locator(alt_selector).first
            if await link.count() == 0:
                return ""

            async with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                await link.click()

            await page.wait_for_timeout(1500)
            return page.url

        except Exception as e:
            print(f"    Click navigation failed: {e}")
            if href:
                fallback = href if href.startswith('http') else f"{self.BASE_URL}{href}"
                await page.goto(fallback, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(1500)
                return page.url
            return ""
