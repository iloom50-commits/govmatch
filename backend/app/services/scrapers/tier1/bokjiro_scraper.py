"""복지로 Open API 스크래퍼 — 중앙부처 복지서비스

출처: apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001
인증: PUBLIC_DATA_PORTAL_KEY (공공데이터포털 인증키)
커버: 복지·취업·주거·교육·청년·출산·육아·장애·저소득 등 (413건+)

지자체 복지서비스 API는 별도 활용신청 후 추가 예정:
  LocalGovernmentWelfareInformationsV001/LocalWelfarelistV001
"""
from __future__ import annotations
import os
import re
import logging
import xml.etree.ElementTree as ET
import requests
from typing import List, Dict, Any

from .base import BaseScraper, register

logger = logging.getLogger(__name__)

_KEY = os.getenv("PUBLIC_DATA_PORTAL_KEY", "")
_CENTRAL_URL = (
    "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"
)
_LOCAL_URL = (
    "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformationsV001/LocalWelfarelistV001"
)
_NUM_ROWS = 100  # 복지로는 100이 안정적 (500은 타임아웃 위험)
_MAX_PAGES = 20  # 최대 2,000건

_EXCLUDE_KW = re.compile(
    r"채용|입찰|구매|계약|임원|면접|합격자|공사|용역|물품|청소|경비"
)

_CATEGORY_MAP = {
    "취업": "취업",
    "고용": "취업",
    "주거": "주거",
    "임대": "주거",
    "전세": "주거",
    "교육": "교육",
    "장학": "장학금",
    "청년": "청년",
    "출산": "출산",
    "육아": "육아",
    "보육": "육아",
    "다자녀": "다자녀",
    "장애": "장애",
    "저소득": "저소득",
    "기초생활": "저소득",
    "노인": "노인",
    "어르신": "노인",
    "의료": "의료",
    "건강": "의료",
    "문화": "문화",
    "창업": "창업지원",
    "기술": "기술개발",
}


def _guess_category(text: str) -> str | None:
    for kw, cat in _CATEGORY_MAP.items():
        if kw in text:
            return cat
    return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _t(el_parent, tag: str) -> str:
    el = el_parent.find(tag)
    return _clean(el.text if el is not None and el.text else "")


def _fetch_page(url: str, page: int) -> ET.Element | None:
    try:
        resp = requests.get(
            url,
            params={
                "serviceKey": _KEY,
                "callTp": "L",
                "pageNo": page,
                "numOfRows": _NUM_ROWS,
                "srchKeyCode": "003",  # 전체검색 (필수 파라미터)
            },
            timeout=30,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        result_code = root.findtext(".//resultCode") or ""
        if result_code != "0":
            msg = root.findtext(".//resultMessage") or ""
            logger.warning(f"[bokjiro] API 오류 {result_code}: {msg}")
            return None
        return root
    except Exception as e:
        logger.warning(f"[bokjiro] {url} page {page} 실패: {e}")
        return None


def _parse_items(root: ET.Element, dept_fallback: str) -> List[Dict[str, Any]]:
    results = []
    # V001 응답 구조: <wantedList><servList>...</servList>...
    for item in root.findall(".//servList"):
        title = _t(item, "servNm")
        if not title or _EXCLUDE_KW.search(title):
            continue

        detail_url = _t(item, "servDtlLink")
        if not detail_url:
            serv_id = _t(item, "servId")
            if serv_id:
                detail_url = (
                    f"https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/"
                    f"moveTWAT52011M.do?wlfareInfId={serv_id}&wlfareInfSclCd=1"
                )
        if not detail_url:
            continue

        summary = _t(item, "servDgst") or None
        dept = _t(item, "jurMnofNm") or _t(item, "jurOrgNm") or dept_fallback

        content_txt = title + " " + (summary or "")
        category = _guess_category(content_txt)

        results.append(
            {
                "title": title,
                "origin_url": detail_url,
                "deadline_date": None,
                "support_amount": None,
                "summary_text": summary,
                "region": "전국",  # 복지로 중앙은 전국 단위
                "category": category,
                "target_type": None,
                "department": dept,
            }
        )
    return results


def _get_total(root: ET.Element) -> int:
    el = root.find(".//totalCount")
    if el is not None and el.text:
        try:
            return int(el.text)
        except ValueError:
            pass
    return 0


def _scrape_all(url: str, dept_fallback: str) -> List[Dict[str, Any]]:
    all_items: List[Dict[str, Any]] = []
    for page in range(1, _MAX_PAGES + 1):
        root = _fetch_page(url, page)
        if root is None:
            break
        items = _parse_items(root, dept_fallback)
        all_items.extend(items)
        total = _get_total(root)
        if page * _NUM_ROWS >= total or not items:
            break
    return all_items


@register
class BokjiroCentralScraper(BaseScraper):
    """복지로 — 중앙부처 복지서비스"""

    name = "bokjiro_central"
    display_name = "복지로(중앙부처)"
    origin_url_prefix = "https://www.bokjiro.go.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        if not _KEY:
            logger.warning("[bokjiro_central] PUBLIC_DATA_PORTAL_KEY 미설정 — 스킵")
            return []
        items = _scrape_all(_CENTRAL_URL, "복지로(중앙)")
        logger.info(f"[bokjiro_central] 수집 완료: {len(items)}건")
        return items


@register
class BokjiroLocalScraper(BaseScraper):
    """복지로 — 지자체 복지서비스 (시·군·구 단위 포함)

    활용신청 승인 후 활성화됨. 미승인 시 빈 배열 반환.
    신청: data.go.kr/data/15108347/openapi.do
    """

    name = "bokjiro_local"
    display_name = "복지로(지자체)"
    origin_url_prefix = "https://www.bokjiro.go.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        if not _KEY:
            logger.warning("[bokjiro_local] PUBLIC_DATA_PORTAL_KEY 미설정 — 스킵")
            return []
        items = _scrape_all(_LOCAL_URL, "복지로(지자체)")
        logger.info(f"[bokjiro_local] 수집 완료: {len(items)}건")
        return items
