"""창조경제혁신센터(CCEI) 통합 스크래퍼 — 18개 지역.

구조: POST https://ccei.creativekorea.or.kr/{region}/custom/noticeList.json
      kind=my → 해당 센터 + 통합 공고만 반환
      SEQ 기반 상세 URL: /custom/notice_view.do?SEQ={SEQ}
"""
from __future__ import annotations
import re
import requests
from typing import List, Dict, Any

from .base import BaseScraper, SCRAPER_REGISTRY

BASE = "https://ccei.creativekorea.or.kr"

CCEI_REGIONS = {
    "seoul":    ("서울", "서울창조경제혁신센터"),
    "busan":    ("부산", "부산창조경제혁신센터"),
    "daegu":    ("대구", "대구창조경제혁신센터"),
    "incheon":  ("인천", "인천창조경제혁신센터"),
    "gwangju":  ("광주", "광주창조경제혁신센터"),
    "daejeon":  ("대전", "대전창조경제혁신센터"),
    "ulsan":    ("울산", "울산창조경제혁신센터"),
    "sejong":   ("세종", "세종창조경제혁신센터"),
    "gyeonggi": ("경기", "경기창조경제혁신센터"),
    "gangwon":  ("강원", "강원창조경제혁신센터"),
    "chungbuk": ("충북", "충북창조경제혁신센터"),
    "chungnam": ("충남", "충남창조경제혁신센터"),
    "jeonbuk":  ("전북", "전북창조경제혁신센터"),
    "jeonnam":  ("전남", "전남창조경제혁신센터"),
    "gyeongbuk":("경북", "경북창조경제혁신센터"),
    "gyeongnam":("경남", "경남창조경제혁신센터"),
    "jeju":     ("제주", "제주창조경제혁신센터"),
    "pohang":   ("경북", "포항창조경제혁신센터"),
}

_SUPPORT_KW = re.compile(r"모집|지원|공모|사업|창업|육성|선발|참여|공고")
_EXCLUDE_KW = re.compile(r"채용|인재|직원|합격자|서류전형|면접|입사|퇴사|인사|결과발표")
_DATE_RE = re.compile(r"(\d{4})[.\-/](\d{2})[.\-/](\d{2})")


def _parse_date(text: str):
    m = _DATE_RE.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


class _CceiRegionScraper(BaseScraper):

    def __init__(self, region_code: str, sido: str, display_name: str):
        self.region_code = region_code
        self.sido = sido
        self.name = f"ccei_{region_code}"
        self.display_name = display_name
        self.origin_url_prefix = f"{BASE}/{region_code}/custom/notice_view.do"

    def fetch_items(self) -> List[Dict[str, Any]]:
        api_url = f"{BASE}/{self.region_code}/custom/noticeList.json"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{BASE}/{self.region_code}/custom/notice_list.do",
            "X-Requested-With": "XMLHttpRequest",
        }
        items: List[Dict[str, Any]] = []
        page = 1
        seen: set = set()
        scanned = 0          # 훑은 게시물 수(걸러진 것 포함)

        # ★ 「지원사업을 30건 모을 때까지」로 센다. 전에는 훑은 건수로 세어
        #   30건에서 멈췄는데, 그 30건이 채용 공고로 채워지면 지원사업에 닿지 못했다.
        #   실측(2026-08-26): chungbuk 60건 중 채용 등 32건 · 지원사업 20건,
        #   jeonbuk 60건 중 채용 33건 · 지원사업 26건.
        #   최신 공고가 「(사)창조경제혁신센터협의회 직원 채용」으로 도배돼 있어
        #   두 곳 모두 7월 말 이후 신규 0건이었다(사이트에는 지원사업이 있었다).
        #   훑는 상한(MAX_SCAN)은 두어 무한정 돌지 않게 한다.
        MAX_SCAN = 120
        while len(items) < 30 and scanned < MAX_SCAN:
            try:
                resp = requests.post(
                    api_url,
                    data={"pn": page, "kind": "my"},
                    headers=headers,
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                result = data.get("result") or {}
                rows = result.get("list") or []
            except Exception:
                break

            if not rows:
                break

            for row in rows:
                scanned += 1
                seq = str(row.get("SEQ", ""))
                if not seq or seq in seen:
                    continue
                seen.add(seq)

                title = (row.get("TITLE") or "").strip()
                if not title or len(title) < 5:
                    continue
                if not _SUPPORT_KW.search(title):
                    continue
                if _EXCLUDE_KW.search(title):
                    continue

                country = (row.get("COUNTRY_NM") or "").strip()
                region = country if country and country != "통합" else self.sido
                if not title.startswith("["):
                    title = f"[{region}] {title}"

                origin_url = f"{BASE}/{self.region_code}/custom/notice_view.do?SEQ={seq}"
                reg_date = _parse_date(row.get("REG_DATE", ""))

                items.append({
                    "title": title[:400],
                    "origin_url": origin_url,
                    "region": region,
                    "target_type": "business",
                    "category": None,
                    "summary_text": None,
                    "deadline_date": None,
                    "support_amount": None,
                })

            total = int(result.get("size", 0))
            row_size = int(result.get("rowSize", 5))
            # page 상한을 6(=30건)에서 올린다. MAX_SCAN 이 실제 상한 역할을 하므로
            # 지원사업이 일찍 모이면 여기까지 오지 않는다 — 정상인 센터는 전처럼 빨리 끝난다.
            if page * row_size >= total or page >= 24:
                break
            page += 1

        return items


for _code, (_sido, _name) in CCEI_REGIONS.items():
    SCRAPER_REGISTRY.append(_CceiRegionScraper(_code, _sido, _name))
