import os
import httpx
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse
import re

class AttachmentDownloader:
    """첨부 파일 다운로드 및 텍스트 추출"""
    
    SUPPORTED_EXTENSIONS = {
        '.pdf': 'pdf',
        '.docx': 'docx',
        '.xlsx': 'xlsx',
        '.txt': 'txt',
    }
    
    def __init__(self, base_dir: str = "attachments"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def is_attachment_url(self, url: str, text: str = "") -> bool:
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS.keys())
    
    async def download_and_extract(self, url: str, program_id: int, base_url: str = "") -> Optional[Dict]:
        # Simplified version for now
        # In a real environment, we'd use pdfplumber, python-docx etc.
        return None
