"""경남테크노파크(GNTP) 스크래퍼.

사이트: https://www.gntp.or.kr/biz/apply
구조: 1페이지 정적 HTML(10건) + POST /biz/apply2?pageIndex=N 으로 페이지네이션
      li.table-li[onclick=goPage(...,'/biz/applyInfo/{id}')] 형식
"""
from __future__ import annotations
import re
import json
import urllib.request
from typing import List, Dict, Any

from .base import BaseScraper, SCRAPER_REGISTRY

BASE_URL = "https://www.gntp.or.kr"
LIST_URL = f"{BASE_URL}/biz/apply"
API_URL = f"{BASE_URL}/biz/apply2"
MAX_PAGES = 20  # 안전 상한

_ITEM_RE = re.compile(
    r'<li[^>]+class="table-li"[^>]+onclick="goPage\([^,]+,\s*[^,]+,\s*\'(/biz/applyInfo/\d+)\'\)">(.*?)</li>',
    re.DOTALL,
)
_PAGE_RE = re.compile(r"bizNotiPaging\((\d+)\)")
_DATE_RE = re.compile(r"(\d{4})[.\-](\d{2})[.\-](\d{2})")


def _fetch_first_page() -> str:
    req = urllib.request.Request(
        LIST_URL,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _fetch_api_page(page_index: int) -> str:
    payload = json.dumps({
        "pageIndex": str(page_index),
        "before": None, "ing": None, "end": None,
        "searchStartDate": None, "searchEndDate": None,
        "bizManagerDept": None, "bizNotiNm": None,
        "bizCreateNm": None, "bizNotiContent": None,
        "searchBizType": None,
        "managerNm": None, "notiNm": None,
        "startTime": None, "endTime": None, "status": None,
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json;charset=UTF-8",
            "Referer": LIST_URL,
        },
        method="POST",
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


def _extract_items(html: str, seen: set) -> List[Dict[str, Any]]:
    results = []
    for m in _ITEM_RE.finditer(html):
        path, body = m.group(1), m.group(2)
        if path in seen:
            continue
        seen.add(path)

        title_m = re.search(r'class="table-title"[^>]*>(.*?)</div>', body, re.DOTALL)
        title = _strip_tags(title_m.group(1)) if title_m else _strip_tags(body)
        title = re.sub(r"\s+", " ", title).strip()
        title = re.sub(r"\s*담당자\s*:.*$", "", title).strip()
        if not title.startswith("["):
            title = f"[경남] {title}"
        title = title[:400]
        if not title or len(title) < 5:
            continue

        results.append({
            "title": title,
            "origin_url": f"{BASE_URL}{path}",
            "region": "경남",
            "target_type": "business",
            "category": None,
            "summary_text": None,
            "deadline_date": _parse_deadline(body),
            "support_amount": None,
        })
    return results


class GntpScraper(BaseScraper):
    name = "gntp"
    display_name = "경남테크노파크"
    origin_url_prefix = "https://www.gntp.or.kr/biz/applyInfo/"

    def fetch_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set = set()

        # 1페이지: 정적 HTML에서 수집 + 총 페이지 수 파악
        try:
            first_html = _fetch_first_page()
        except Exception:
            return []

        items.extend(_extract_items(first_html, seen))

        # pagination 버튼에서 최대 페이지 수 확인
        page_nums = [int(p) for p in _PAGE_RE.findall(first_html)]
        total_pages = max(page_nums) if page_nums else 1

        # 2페이지부터 POST API로 수집
        for page in range(2, min(total_pages, MAX_PAGES) + 1):
            try:
                html = _fetch_api_page(page)
                items.extend(_extract_items(html, seen))
            except Exception:
                break

        return items


SCRAPER_REGISTRY.append(GntpScraper())
