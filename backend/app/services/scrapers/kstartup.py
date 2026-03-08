from .base import BaseScraper
from typing import List, Dict, Any
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
from app.services.ai_service import ai_service
from app.services.scrapers.smart_html_parser import SmartHTMLParser

class KStartupScraper(BaseScraper):
    """K-Startup (중소벤처기업부) 스크래퍼"""
    BASE_URL = "https://www.k-startup.go.kr"
    LIST_URL = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do" 

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parser = SmartHTMLParser()

    async def scrape(self) -> List[Dict]:
        print(f"[{datetime.now()}] Starting K-Startup Scrape...")
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
            
            # fn_view 또는 상세 링크 찾기
            all_links = soup.find_all('a')
            potential_links = []
            
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                if href and ('fn_view' in href or 'bizpbanc-ongoing.do?schM=view' in href or 'view' in href.lower()):
                    if len(text) > 5:
                        potential_links.append((link, href, text))
            
            print(f"Found {len(potential_links)} potential links. Processing top 5 for demo...")

            for link_elem, href, title in potential_links[:5]:
                try:
                    # 상세 URL 추출
                    if 'id=' in href:
                        detail_url = f"{self.BASE_URL}{href}" if href.startswith('/') else href
                    else:
                        match = re.search(r"(\d+)", href)
                        if match:
                            detail_url = f"{self.BASE_URL}/web/contents/bizpbanc-ongoing.do?schM=view&id={match.group(1)}"
                        else: continue

                    # 상세 정보 파싱
                    await page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
                    detail_html = await page.content()
                    parsed_info = self.parser.parse(detail_html, detail_url)
                    
                    program_data = {
                        "title": title,
                        "description": parsed_info.get('main_content', '')[:3000],
                        "department": "중소벤처기업부",
                        "category": "Entrepreneurship",
                        "region": "All",
                        "start_date": datetime.now().strftime("%Y-%m-%d"),
                        "end_date": "2025-12-31",
                        "url": detail_url,
                        "status": "Open",
                        "origin_source": "k-startup"
                    }
                    
                    # AI 구조화 (Brain Transplant)
                    full_text = f"제목: {title}\n내용: {program_data['description']}"
                    eligibility = await ai_service.extract_structured_eligibility(full_text)
                    if eligibility:
                        program_data["eligibility_logic"] = eligibility
                        program_data["summary_text"] = eligibility.get("summary_noun", title)
                    
                    results.append(program_data)
                    print(f"  ✅ Scraped & Analyzed: {title[:30]}")
                    
                except Exception as e:
                    print(f"  ⚠️ Error parsing item: {e}")
            
            await self.close_browser()

        except Exception as e:
            print(f"❌ KStartupScraper Error: {e}")
            await self.close_browser()
            
        return results
