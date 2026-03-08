from .base_enhanced import EnhancedBaseScraper
from typing import List, Dict, Any
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
from app.services.ai_service import ai_service
from app.services.scrapers.smart_html_parser import SmartHTMLParser

class SBCScraper(EnhancedBaseScraper):
    """중소벤처기업진흥공단 (SBC) 스크래퍼"""
    BASE_URL = "https://www.sbc.or.kr"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parser = SmartHTMLParser()

    async def scrape(self) -> List[Dict]:
        print(f"[{datetime.now()}] Starting SBC Scrape...")
        results = []
        pw = None
        browser = None
        
        try:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()
            
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            list_url = f"{self.BASE_URL}/nsh/svc/svcInfo.do"
            print(f"Loading SBC list page: {list_url}")
            await page.goto(list_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            announcements = []
            for link in soup.find_all('a', href=True):
                text = link.get_text(strip=True)
                href = link.get('href', '')
                if href.startswith('#') or href == 'javascript:void(0)' or 'main.do' in href:
                    continue
                if any(kw in text for kw in ['공고', '지원', '사업', '모집', '융자', '정책자금']) and len(text) > 10:
                    if not href.startswith('http'):
                        href = self.BASE_URL + (href if href.startswith('/') else f"/{href}")
                    announcements.append({'title': text, 'url': href})
            
            if not announcements:
                print("  No links from list page, trying click navigation...")
                rows = page.locator("table tbody tr a, .board-list a, .list-area a")
                count = await rows.count()
                for i in range(min(count, 5)):
                    el = rows.nth(i)
                    text = (await el.text_content() or "").strip()
                    if len(text) > 10:
                        announcements.append({'title': text, 'url': '', 'click_idx': i})

            print(f"Found {len(announcements)} potential SBC links. Processing top 5...")

            for ann in announcements[:5]:
                try:
                    if ann.get('click_idx') is not None:
                        row_link = rows.nth(ann['click_idx'])
                        async with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                            await row_link.click()
                        await page.wait_for_timeout(1500)
                    else:
                        await page.goto(ann['url'], wait_until="domcontentloaded", timeout=30000)

                    actual_url = page.url
                    if 'main.do' in actual_url or actual_url.rstrip('/') == self.BASE_URL.rstrip('/'):
                        print(f"  ⏩ Skipped (main page URL): {ann['title'][:30]}")
                        await page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
                        continue

                    detail_html = await page.content()
                    parsed_info = self.parser.parse(detail_html, actual_url)
                    
                    program_data = {
                        "title": ann['title'],
                        "description": parsed_info.get('main_content', '')[:3000],
                        "department": "중소벤처기업부",
                        "category": "Loan/Investment",
                        "region": "All",
                        "url": actual_url,
                        "status": "Open",
                        "origin_source": "sbc"
                    }
                    
                    eligibility = await ai_service.extract_structured_eligibility(program_data["description"])
                    if eligibility:
                        program_data["eligibility_logic"] = eligibility
                    
                    results.append(program_data)
                    print(f"  ✅ Scraped & Analyzed: {ann['title'][:30]}")

                    await page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(1000)
                    
                except Exception as e:
                    print(f"  ❌ Error processing SBC item: {e}")
                    try:
                        await page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
                    except Exception:
                        pass

        except Exception as e:
            print(f"❌ SBCScraper Error: {e}")
        finally:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()
            
        return results
