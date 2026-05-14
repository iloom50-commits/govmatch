"""KOCCA 지원사업 공고 API 스크래퍼

한국콘텐츠진흥원 공식 Open API (kocca.kr 자체 API)
엔드포인트: https://kocca.kr/api/pims/List.do

콘텐츠·미디어·게임·웹툰·애니메이션 분야 지원사업 공고 제공.
인증: KOCCA_API_KEY (KOCCA 자체 발급 서비스키)
"""
from __future__ import annotations
import os
import re
import time
import logging
import requests
from typing import List, Dict, Any

from .base import BaseScraper, SCRAPER_REGISTRY

logger = logging.getLogger(__name__)

_KEY = os.getenv("KOCCA_API_KEY", "")

_KOCCA_API_URL = "https://kocca.kr/api/pims/List.do"
_KOCCA_BASE = "https://www.kocca.kr"

_EXCLUDE_KW = re.compile(
    r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품|청소|경비|보안|퇴직|임원|낙찰|유찰"
)


def _parse_date(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", str(text))
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    # YYYYMMDD 형식
    m2 = re.match(r"(\d{4})(\d{2})(\d{2})", str(text))
    if m2:
        return f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}"
    return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


class KOCCAAPIScraper(BaseScraper):
    """한국콘텐츠진흥원 지원사업 공고 (공식 API)"""

    name = "kocca_api"
    display_name = "한국콘텐츠진흥원(KOCCA API)"
    origin_url_prefix = f"{_KOCCA_BASE}/kocca/pims"

    def fetch_items(self) -> List[Dict[str, Any]]:
        if not _KEY:
            logger.warning("[kocca_api] KOCCA_API_KEY 미설정 — 스킵")
            return []

        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                resp = requests.get(
                    _KOCCA_API_URL,
                    params={
                        "serviceKey": _KEY,
                        "pageNo": page,
                        "numOfRows": 100,
                    },
                    timeout=20,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"[kocca_api] page {page} 실패: {e}")
                break

            # 응답 구조: {"resultCode": "INFO-000", "data": {"list": [...], "totalCount": N}}
            try:
                result_code = data.get("resultCode", "")
                if result_code != "INFO-000":
                    logger.warning(f"[kocca_api] API 오류: {result_code}")
                    break

                body = data.get("data", {})
                raw_list = body.get("list") or []
                total = int(body.get("totalCount", 0))
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"[kocca_api] 응답 파싱 실패: {e}")
                break

            if not raw_list:
                break

            found_new = False
            for item in raw_list:
                title = _clean(item.get("subject") or item.get("title") or "")
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                intc_no = str(item.get("intcNo") or item.get("id") or "")
                if not intc_no:
                    continue
                if intc_no in seen:
                    continue

                # 상세 URL
                link = item.get("link") or item.get("viewUrl") or ""
                if link and not link.startswith("http"):
                    link = _KOCCA_BASE + link
                if not link:
                    link = f"{_KOCCA_BASE}/kocca/pims/view.do?menuNo=204848&intcNo={intc_no}"

                # 날짜
                reg_dt = _parse_date(item.get("regDt") or item.get("startDt") or "")
                deadline = _parse_date(item.get("endDt") or item.get("deadlineDt") or "")

                seen.add(intc_no)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": link,
                        "deadline_date": deadline,
                        "support_amount": None,
                        "summary_text": f"등록일: {reg_dt}" if reg_dt else None,
                        "region": "전국",
                        "category": "콘텐츠",
                        "target_type": "business",
                        "department": "한국콘텐츠진흥원",
                    }
                )

            if not found_new:
                break
            if len(items) >= total:
                break

            time.sleep(0.3)

        logger.info(f"[kocca_api] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(KOCCAAPIScraper())
