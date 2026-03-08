from bs4 import BeautifulSoup, Tag, NavigableString
from typing import Dict, List, Optional, Tuple
import re
import os

class SmartHTMLParser:
    """스마트 HTML 파서: 다양한 사이트 구조에 대응하는 범용 HTML 파서"""
    
    CONTENT_PATTERNS = [
        r'content', r'cont', r'article', r'main', r'body',
        r'view', r'detail', r'post', r'entry', r'text',
        r'editor', r'description', r'본문', r'내용'
    ]
    
    EXCLUDE_PATTERNS = [
        r'ad', r'advertisement', r'banner', r'popup',
        r'nav', r'navigation', r'menu', r'sidebar',
        r'footer', r'header', r'comment', r'댓글',
        r'script', r'style', r'noscript'
    ]
    
    SECTION_KEYWORDS = {
        'title': ['제목', 'title', 'subject', '공고제목'],
        'overview': ['개요', '목적', '배경', 'overview', 'purpose', 'background'],
        'eligibility': ['자격요건', '지원대상', '지원자격', 'eligibility', 'qualification', '대상'],
        'application_method': ['신청방법', '접수방법', '지원방법', 'application', 'apply', '접수'],
        'schedule': ['일정', '기간', '마감', '신청기간', 'schedule', 'deadline', 'period'],
        'support_details': ['지원내용', '지원규모', '지원금액', 'support', 'amount', '규모'],
        'contact': ['문의', '연락처', 'contact', 'inquiry', '문의처'],
        'attachments': ['첨부', 'attachment', 'download', '다운로드']
    }
    
    def __init__(self):
        self.soup = None
    
    def parse(self, html: str, url: str = "") -> Dict:
        self.soup = BeautifulSoup(html, 'html.parser')
        
        main_content = self._extract_main_content()
        
        result = {
            'title': self._extract_title(),
            'main_content': main_content,
            'sections': self._extract_sections(),
            'tables': self._extract_tables(),
            'links': self._extract_links(),
            'cleaned_text': self._get_cleaned_text()
        }
        
        return result
    
    def _extract_title(self) -> Optional[str]:
        title = None
        h1 = self.soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
            if len(title) > 5: return title
        
        title_tag = self.soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            if len(title) > 5: return title
        
        return title
    
    def _extract_main_content(self) -> str:
        self._remove_noise_elements()
        content_div = self._find_content_div()
        if content_div:
            return self._clean_text(content_div.get_text())
        
        body = self.soup.find('body')
        if body:
            return self._clean_text(body.get_text())
        
        return ""
    
    def _remove_noise_elements(self):
        for tag_name in ['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript']:
            for tag in self.soup.find_all(tag_name):
                tag.decompose()
    
    def _find_content_div(self) -> Optional[Tag]:
        for pattern in self.CONTENT_PATTERNS:
            divs = self.soup.find_all('div', class_=re.compile(pattern, re.I))
            if divs:
                best_div = max(divs, key=lambda d: len(d.get_text(strip=True)))
                if len(best_div.get_text(strip=True)) > 50:
                    return best_div
        return None
    
    def _extract_sections(self) -> Dict[str, str]:
        sections = {}
        main_content = self._extract_main_content()
        
        for section_type, keywords in self.SECTION_KEYWORDS.items():
            for keyword in keywords:
                pattern = rf'{keyword}[:\s\n]*([^\n]+(?:\n(?![^가-힣]*[0-9]\.)[^\n]+)*)'
                match = re.search(pattern, main_content, re.IGNORECASE | re.MULTILINE)
                if match:
                    content = match.group(1).strip()
                    if 10 <= len(content) <= 3000:
                        sections[section_type] = self._clean_text(content)
                        break
        return sections
    
    def _extract_tables(self) -> List[Dict]:
        tables = []
        for table in self.soup.find_all('table'):
            rows = []
            for tr in table.find_all('tr'):
                cells = [self._clean_text(td.get_text()) for td in tr.find_all(['td', 'th'])]
                if any(cells):
                    rows.append(cells)
            if rows:
                tables.append({'rows': rows})
        return tables
    
    def _extract_links(self) -> List[Dict]:
        links = []
        for link in self.soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            if href and text:
                links.append({'text': text, 'url': href})
        return links
    
    def _get_cleaned_text(self) -> str:
        return self._clean_text(self._extract_main_content())
    
    def _clean_text(self, text: str) -> str:
        if not text: return ""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        return text.strip()
