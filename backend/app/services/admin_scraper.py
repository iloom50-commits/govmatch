import sqlite3
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from app.services.ai_service import ai_service
import json

class AdminScraper:
    """관리자가 등록한 URL을 AI로 분석하여 수집하는 동적 스크래퍼"""
    
    def __init__(self, db_path="gov_matching.db"):
        self.db_path = db_path

    async def run_all(self):
        """모든 활성화된 관리자 URL을 순회하며 수집"""
        # timeout을 늘려 'database is locked' 에러 방지
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM admin_urls WHERE is_active = 1")
        targets = cursor.fetchall()
        
        print(f"🚀 Starting Admin Targeted Scrape for {len(targets)} URLs...")
        
        async with async_playwright() as p:
            # 브라우저 한 번만 실행
            browser = await p.chromium.launch(headless=True)
            for target in targets:
                try:
                    results = await self.scrape_url(target['url'], browser)
                    if results:
                        # 연결(conn)을 공유하여 'locked' 방지
                        self._save_to_db(results, target['source_name'], conn)
                        
                        # 업데이트 시간 갱신 루틴도 동일 연결에서 수행
                        cursor.execute("UPDATE admin_urls SET last_scraped = ? WHERE id = ?", 
                                     (datetime.now().isoformat(), target['id']))
                        conn.commit()
                except Exception as e:
                    print(f"  ❌ Error scraping {target['url']}: {e}")
            
            await browser.close()
        
        conn.close()

    async def scrape_url(self, url: str, browser) -> dict:
        """개별 URL에 접속하여 AI 분석 수행"""
        print(f"  🌐 Processing: {url}")
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # 텍스트 추출 (너무 길면 자름)
            raw_text = soup.get_text(separator='\n', strip=True)
            
            # AI 분석 요청
            details = await ai_service.extract_program_details(raw_text)
            if details:
                details['url'] = url
                return details
            return None
        finally:
            await page.close()

    def _save_to_db(self, item: dict, source_name: str, conn: sqlite3.Connection):
        """AI가 추출한 데이터를 announcements 테이블에 통합"""
        cursor = conn.cursor()
        
        try:
            # 중복 체크 (origin_url 기준)
            cursor.execute("SELECT announcement_id FROM announcements WHERE origin_url = ?", (item['url'],))
            exists = cursor.fetchone()
            
            eligibility_json = json.dumps(item.get('eligibility_logic', {}), ensure_ascii=False)
            
            if exists:
                query = """
                UPDATE announcements SET 
                    title = ?, summary_text = ?, eligibility_logic = ?, department = ?, category = ?, origin_source = ?, deadline_date = ?
                WHERE origin_url = ?
                """
                cursor.execute(query, (
                    item['title'], item.get('description', ''), eligibility_json,
                    item.get('department', ''), item.get('category', ''), f"admin-manual:{source_name}",
                    item.get('deadline_date'), item['url']
                ))
            else:
                query = """
                INSERT INTO announcements (title, origin_url, summary_text, eligibility_logic, department, category, origin_source, deadline_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                cursor.execute(query, (
                    item['title'], item['url'], item.get('description', ''), eligibility_json,
                    item.get('department', ''), item.get('category', ''), f"admin-manual:{source_name}",
                    item.get('deadline_date')
                ))
            
            print(f"    ✅ Saved/Updated: {item['title'][:30]}")
        except Exception as e:
            print(f"    ❌ DB Save Error: {e}")
            raise e # 상위 run_all에서 처리하도록 전파

admin_scraper = AdminScraper()
