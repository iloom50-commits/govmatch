"""창조경제혁신센터 통합 스크래퍼 — 18개 지역 CCEI 공통 CMS.

구조: https://ccei.creativekorea.or.kr/{region}/custom/notice_list.do
  - seoul/busan/daegu/incheon/gwangju/daejeon/ulsan/sejong/gyeonggi/gangwon/
    chungbuk/chungnam/jeonbuk/jeonnam/gyeongbuk/gyeongnam/jeju/pohang

공통 CMS라 HTML 구조 동일. 리스트 + 상세 페이지 둘 다 같은 형식.
"""
from __future__ import annotations
import re
import time
import datetime
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, SCRAPER_REGISTRY

CCEI_REGIONS = {
    "seoul":    "서울창조경제혁신센터",
    "busan":    "부산창조경제혁신센터",
    "daegu":    "대구창조경제혁신센터",
    "incheon":  "인천창조경제혁신센터",
    "gwangju":  "광주창조경제혁신센터",
    "daejeon":  "대전창조경제혁신센터",
    "ulsan":    "울산창조경제혁신센터",
    "sejong":   "세종창조경제혁신센터",
    "gyeonggi": "경기창조경제혁신센터",
    "gangwon":  "강원창조경제혁신센터",
    "chungbuk": "충북창조경제혁신센터",
    "chungnam": "충남창조경제혁신센터",
    "jeonbuk":  "전북창조경제혁신센터",
    "jeonnam":  "전남창조경제혁신센터",
    "gyeongbuk":"경북창조경제혁신센터",
    "gyeongnam":"경남창조경제혁신센터",
    "jeju":     "제주창조경제혁신센터",
    "pohang":   "포항창조경제혁신센터",
}

REGION_TO_SIDO = {
    "seoul": "서울", "busan": "부산", "daegu": "대구", "incheon": "인천",
    "gwangju": "광주", "daejeon": "대전", "ulsan": "울산", "sejong": "세종",
    "gyeonggi": "경기", "gangwon": "강원", "chungbuk": "충북", "chungnam": "충남",
    "jeonbuk": "전북", "jeonnam": "전남", "gyeongbuk": "경북", "gyeongnam": "경남",
    "jeju": "제주", "pohang": "경북",
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


class _CceiRegionScraper(BaseScraper):
    """지역별 CCEI 스크래퍼 — 동적 생성되어 SCRAPER_REGISTRY에 등록됨."""

    def __init__(self, region_code: str, display_name: str):
        self.region_code = region_code
        self.name = f"ccei_{region_code}"
        self.display_name = display_name
        self.origin_url_prefix = f"https://ccei.creativekorea.or.kr/{region_code}/"

    def fetch_items(self) -> List[Dict[str, Any]]:
        """공고 리스트 페이지에서 최근 공고 추출."""
        list_url = f"https://ccei.creativekorea.or.kr/{self.region_code}/custom/notice_list.do"
        resp = requests.get(list_url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        items: List[Dict[str, Any]] = []
        # CCEI는 리스트를 테이블 또는 div.board-list 형식으로 제공
        # 공고 상세 링크 패턴: /region/custom/notice_view.do?...
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "notice_view" not in href and "pbancId" not in href.lower():
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            # 상대 URL → 절대 URL
            if href.startswith("/"):
                full_url = f"https://ccei.creativekorea.or.kr{href}"
            elif href.startswith("http"):
                full_url = href
            else:
                full_url = f"https://ccei.creativekorea.or.kr/{self.region_code}/custom/{href}"

            # 중복 제거 (같은 링크)
            if any(it["origin_url"] == full_url for it in items):
                continue

            items.append({
                "title": title[:400],
                "origin_url": full_url,
                "region": REGION_TO_SIDO.get(self.region_code, ""),
                "target_type": "business",
                "category": None,
                "summary_text": None,
                "deadline_date": None,
                "support_amount": None,
            })
            if len(items) >= 30:
                break

        return items


# 18개 지역 스크래퍼 일괄 등록
for _code, _name in CCEI_REGIONS.items():
    SCRAPER_REGISTRY.append(_CceiRegionScraper(_code, _name))
