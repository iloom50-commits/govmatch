"""IRIS/MSIT 사업공고 API 스크래퍼

과학기술정보통신부(MSIT) 사업공고 API — data.go.kr 제공
엔드포인트: apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList

산업부·과기부·복지부 등 주요 부처 R&D·지원사업 공고를 통합 제공.
인증: PUBLIC_DATA_PORTAL_KEY (공공데이터포털 인증키 — gov24와 동일 키)
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

_KEY = os.getenv("PUBLIC_DATA_PORTAL_KEY", "")

_MSIT_URL = (
    "https://apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList"
)

_EXCLUDE_KW = re.compile(
    r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품|청소|경비|보안|퇴직|임원|낙찰|유찰"
)


def _parse_date(text: str) -> str | None:
    if not text:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text.strip())
    if m:
        return text.strip()[:10]
    return None


class IRISScraper(BaseScraper):
    """과학기술정보통신부 사업공고 API (IRIS/MSIT) — 중앙부처 R&D·지원사업 통합"""

    name = "iris_msit"
    display_name = "과학기술정보통신부 사업공고(MSIT API)"
    origin_url_prefix = "https://www.msit.go.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        if not _KEY:
            logger.warning("[iris_msit] PUBLIC_DATA_PORTAL_KEY 미설정 — 스킵")
            return []

        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):  # 최대 10페이지 (numOfRows=100 → 최대 1000건)
            try:
                resp = requests.get(
                    _MSIT_URL,
                    params={
                        "ServiceKey": _KEY,
                        "pageNo": page,
                        "numOfRows": 100,
                        "returnType": "json",
                    },
                    timeout=20,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"[iris_msit] page {page} 실패: {e}")
                break

            try:
                body = data["response"]["body"]
                raw_items = body.get("items") or []
                total = int(body.get("totalCount", 0))
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"[iris_msit] 응답 파싱 실패: {e}")
                break

            if not raw_items:
                break

            # items가 dict(단건)로 올 수 있음
            if isinstance(raw_items, dict):
                raw_items = [raw_items]

            found_new = False
            for item in raw_items:
                subject = (item.get("subject") or "").strip()
                view_url = (item.get("viewUrl") or "").strip()
                dept = (item.get("deptName") or "").strip()
                press_dt = _parse_date(item.get("pressDt") or "")

                if not subject or len(subject) < 5:
                    continue
                if _EXCLUDE_KW.search(subject):
                    continue
                if not view_url:
                    continue
                if view_url in seen:
                    continue

                seen.add(view_url)
                found_new = True
                items.append(
                    {
                        "title": subject[:400],
                        "origin_url": view_url,
                        "deadline_date": None,
                        "support_amount": None,
                        "summary_text": f"공고부처: {dept}" if dept else None,
                        "region": "전국",
                        "category": "R&D",
                        "target_type": None,
                        "department": dept or "과학기술정보통신부",
                    }
                )

            if not found_new:
                break

            # 전체 수집 완료 여부 확인
            if len(items) >= total:
                break

            time.sleep(0.3)

        logger.info(f"[iris_msit] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(IRISScraper())
