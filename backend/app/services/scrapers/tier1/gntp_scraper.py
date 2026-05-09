"""경남테크노파크(GNTP) 스크래퍼.

사이트: https://www.gntp.or.kr/biz/apply
구조: 정적 HTML — li.table-li[onclick=goPage(...,'/biz/applyInfo/{id}')] 형식
"""
from __future__ import annotations
import re
import urllib.request
from typing import List, Dict, Any

from .base import BaseScraper, SCRAPER_REGISTRY

BASE_URL = "https://www.gntp.or.kr"
LIST_URL = f"{BASE_URL}/biz/apply"

_ITEM_RE = re.compile(
    r'<li[^>]+class="table-li"[^>]+onclick="goPage\([^,]+,\s*[^,]+,\s*\'(/biz/applyInfo/\d+)\'\)">(.*?)</li>',
    re.DOTALL,
)
_DATE_RE = re.compile(r"(\d{4})[.\-](\d{2})[.\-](\d{2})")


def _fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _parse_deadline(body: str) -> str | None:
    dates = _DATE_RE.findall(body)
    if len(dates) >= 2:
        y, m, d = dates[1]
        return f"{y}-{m}-{d}"
    if dates:
        y, m, d = dates[0]
        return f"{y}-{m}-{d}"
    return None


class GntpScraper(BaseScraper):
    name = "gntp"
    display_name = "경남테크노파크"
    origin_url_prefix = "https://www.gntp.or.kr/biz/applyInfo/"

    def fetch_items(self) -> List[Dict[str, Any]]:
        try:
            html = _fetch_html(LIST_URL)
        except Exception:
            return []

        items: List[Dict[str, Any]] = []
        for m in _ITEM_RE.finditer(html):
            path, body = m.group(1), m.group(2)
            title = _strip_tags(body)
            # 제목은 table-title div에서 추출
            title_m = re.search(r'class="table-title"[^>]*>(.*?)</div>', body, re.DOTALL)
            if title_m:
                title = _strip_tags(title_m.group(1))
            title = re.sub(r"\s+", " ", title).strip()
            # "담당자 : ..." 접미어 제거
            title = re.sub(r"\s*담당자\s*:.*$", "", title).strip()[:400]
            if not title or len(title) < 5:
                continue

            items.append({
                "title": title,
                "origin_url": f"{BASE_URL}{path}",
                "region": "경남",
                "target_type": "business",
                "category": None,
                "summary_text": None,
                "deadline_date": _parse_deadline(body),
                "support_amount": None,
            })

            if len(items) >= 30:
                break

        return items


SCRAPER_REGISTRY.append(GntpScraper())
