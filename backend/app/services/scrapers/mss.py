from .base_enhanced import EnhancedBaseScraper
from typing import List, Dict, Any
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from app.services.ai_service import ai_service
from app.services.scrapers.smart_html_parser import SmartHTMLParser

class MSSScraper(EnhancedBaseScraper):
    """중소벤처기업부 (MSS) 스크래퍼"""
    BASE_URL = "https://www.mss.go.kr"
    LIST_URL = "https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=310"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parser = SmartHTMLParser()

    async def scrape(self) -> List[Dict]:
        print(f"[{datetime.now()}] Starting MSS Scrape...")
        results = []
        
        try:
            await self.start_browser()
            page = await self.browser.new_page()
            
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            print(f"Loading list page: {self.LIST_URL}")
            await page.goto(self.LIST_URL, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(2000)
            
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            announcements = []
            table = soup.find('table')
            if table:
                rows = table.find_all('tr')
                for row in rows[1:]:
                    links = row.find_all('a', href=True)
                    for link in links:
                        href = link.get('href', '')
                        text = link.get_text(strip=True)
                        if len(text) > 10 and ('공고' in text or '지원' in text or '사업' in text):
                            if href and not href.startswith('#') and href != 'javascript:void(0)':
                                if not href.startswith('http'):
                                    href = self.BASE_URL + (href if href.startswith('/') else f"/{href}")
                                announcements.append({'title': text, 'url': href, 'click': False})
                            else:
                                announcements.append({'title': text, 'url': '', 'click': True})
            
            print(f"Found {len(announcements)} potential MSS links. Processing top 5...")

            for idx, ann in enumerate(announcements[:5]):
                try:
                    if ann['click']:
                        selector = f"table tbody tr:nth-child({idx + 2}) a"
                        link_el = page.locator(selector).first
                        if await link_el.count() == 0:
                            continue
                        async with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                            await link_el.click()
                        await page.wait_for_timeout(1500)
                    else:
                        await page.goto(ann['url'], wait_until="domcontentloaded", timeout=30000)

                    actual_url = page.url
                    if actual_url.rstrip('/') == self.BASE_URL.rstrip('/') or '#' in actual_url:
                        print(f"  ⏩ Skipped (invalid detail URL): {ann['title'][:30]}")
                        await page.goto(self.LIST_URL, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(1000)
                        continue

                    detail_html = await page.content()
                    parsed_info = self.parser.parse(detail_html, actual_url)
                    
                    program_data = {
                        "title": ann['title'],
                        "description": parsed_info.get('main_content', '')[:3000],
                        "department": "중소벤처기업부",
                        "category": "SME Support",
                        "region": "All",
                        "url": actual_url,
                        "status": "Open",
                        "origin_source": "mss"
                    }
                    
                    eligibility = await ai_service.extract_structured_eligibility(program_data["description"])
                    if eligibility:
                        program_data["eligibility_logic"] = eligibility
                    
                    results.append(program_data)
                    print(f"  ✅ Scraped & Analyzed: {ann['title'][:30]}")

                    await page.goto(self.LIST_URL, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(1000)
                    
                except Exception as e:
                    print(f"  ❌ Error processing MSS item: {e}")
                    try:
                        await page.goto(self.LIST_URL, wait_until="domcontentloaded", timeout=30000)
                    except Exception:
                        pass
            
            await self.close_browser()

        except Exception as e:
            print(f"❌ MSSScraper Error: {e}")
            await self.close_browser()
            
        return results
