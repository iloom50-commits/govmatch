"""
고도화된 파서를 사용하는 기본 스크래퍼 클래스
다른 스크래퍼들이 상속받아 사용할 수 있는 공통 기능
"""
from .base import BaseScraper
from typing import Dict, Any, Optional
import sys
import os
from datetime import date, datetime

# 고도화된 파서 import
try:
    # app/services/smart_html_parser.py 등을 찾을 수 있도록 경로 조정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    from app.services.scrapers.smart_html_parser import SmartHTMLParser
    from app.services.scrapers.attachment_downloader import AttachmentDownloader
    SMART_PARSER_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Scraper components not fully ported yet: {e}")
    SMART_PARSER_AVAILABLE = False
    SmartHTMLParser = None
    AttachmentDownloader = None


class EnhancedBaseScraper(BaseScraper):
    """고도화된 파서를 사용하는 기본 스크래퍼"""
    
    def __init__(self, use_enhanced_parser: bool = True, download_attachments: bool = True, *args, **kwargs):
        """
        Args:
            use_enhanced_parser: True면 고도화된 파서 사용
            download_attachments: True면 첨부 파일 다운로드 (마감되지 않은 공고문에만)
        """
        super().__init__(*args, **kwargs)
        self.use_enhanced_parser = use_enhanced_parser and SMART_PARSER_AVAILABLE
        self.download_attachments = download_attachments and SMART_PARSER_AVAILABLE
        self.smart_parser = None
        self.attachment_downloader = None
        
        if self.use_enhanced_parser:
            try:
                self.smart_parser = SmartHTMLParser()
            except Exception as e:
                print(f"[WARN] Smart parser init failed: {e}")
                self.use_enhanced_parser = False
        
        if self.download_attachments:
            try:
                self.attachment_downloader = AttachmentDownloader()
            except Exception as e:
                print(f"[WARN] Attachment downloader init failed: {e}")
                self.download_attachments = False
    
    async def _scrape_details_enhanced(self, page, url: str) -> Dict[str, Any]:
        """
        고도화된 파서를 사용한 상세 페이지 크롤링
        """
        if not self.use_enhanced_parser or not self.smart_parser:
            return await self._scrape_details_basic(page, url)
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2000)
            
            html = await page.content()
            extracted_info = self.smart_parser.parse(html, url)
            
            description = extracted_info.get('main_content', '') or extracted_info.get('cleaned_text', '')
            result = {
                "description": description,
                "target_industry": self._extract_industry_from_content(extracted_info),
            }
            
            dates = extracted_info.get('dates', {})
            if dates.get('start_date'):
                result['start_date'] = dates['start_date']
            if dates.get('end_date'):
                result['end_date'] = dates['end_date']
            
            return result
            
        except Exception as e:
            print(f"  [WARN] Enhanced parser error: {e}")
            return await self._scrape_details_basic(page, url)
    
    async def _scrape_details_basic(self, page, url: str) -> Dict[str, Any]:
        """기본 파싱 (Fallback)"""
        from bs4 import BeautifulSoup
        import re
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(1000)
            
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            content_div = (
                soup.select_one('.view_cont') or 
                soup.select_one('.editor_view') or
                soup.find('div', {'class': lambda x: x and 'view' in str(x).lower()})
            )
            description = content_div.get_text(strip=True) if content_div else ""
            
            date_text = soup.get_text()
            end_date = None
            end_date_match = re.search(r'마감.*?(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', date_text)
            if end_date_match:
                end_date = f"{end_date_match.group(1)}-{end_date_match.group(2).zfill(2)}-{end_date_match.group(3).zfill(2)}"
            
            return {
                "description": description[:3000],
                "target_industry": ["General"],
                "end_date": end_date
            }
        except Exception as e:
            print(f"  [WARN] Basic parsing error: {e}")
            return {}
    
    def _extract_industry_from_content(self, extracted_info: Dict) -> list:
        """콘텐츠에서 업종 정보 추출 (Simplified for now)"""
        return ["General"]
