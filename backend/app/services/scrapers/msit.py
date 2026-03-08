from .base import BaseScraper
from typing import List, Dict, Any
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from app.services.ai_service import ai_service
from app.services.scrapers.smart_html_parser import SmartHTMLParser

class MSITScraper(BaseScraper):
    """과학기술정보통신부 (MSIT) 스크래퍼"""
    BASE_URL = "https://www.msit.go.kr"
    LIST_URL = "https://www.msit.go.kr/bbs/list.do"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parser = SmartHTMLParser()

    async def scrape(self) -> List[Dict]:
        print(f"[{datetime.now()}] Starting MSIT Scrape...")
        results = []
        
        try:
            await self.start_browser()
            page = await self.browser.new_page()
            
            await page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=60000)
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # 공고 관련 링크 찾기
            potential_links = []
            for link in soup.find_all('a', href=True):
                text = link.get_text(strip=True)
                href = link.get('href', '')
                if any(kw in text for kw in ['공고', '사업'] ) and len(text) > 10:
                    if not href.startswith('http'):
                        href = self.BASE_URL + (href if href.startswith('/') else f"/{href}")
                    potential_links.append((text, href))
            
            print(f"Found {len(potential_links)} potential MSIT links. Processing top 5...")

            for title, url in potential_links[:5]:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    detail_html = await page.content()
                    parsed_info = self.parser.parse(detail_html, url)
                    
                    program_data = {
                        "title": title,
                        "description": parsed_info.get('main_content', '')[:3000],
                        "department": "과학기술정보통신부",
                        "category": "R&D",
                        "region": "All",
                        "url": url,
                        "status": "Open",
                        "origin_source": "msit"
                    }
                    
                    # AI 구조화
                    eligibility = await ai_service.extract_structured_eligibility(program_data["description"])
                    if eligibility:
                        program_data["eligibility_logic"] = eligibility
                    
                    results.append(program_data)
                    print(f"  ✅ Scraped & Analyzed: {title[:30]}")
                    
                except Exception as e:
                    print(f"  ⚠️ Error parsing MSIT item: {e}")
            
            await self.close_browser()

        except Exception as e:
            print(f"❌ MSITScraper Error: {e}")
            await self.close_browser()
            
        return results
