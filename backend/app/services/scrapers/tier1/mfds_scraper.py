"""식품의약품안전처 연구관리 사업공고 API 스크래퍼

식품의약품안전처(MFDS) / 식품의약품안전평가원(NIFDS) 연구관리 사업공고
엔드포인트: apis.data.go.kr/1471057/RNDBSNSPBLANC01/getRndbsnspblanc01

바이오·제약·식품·의료기기 분야 R&D 지원사업 공고 제공.
인증: PUBLIC_DATA_PORTAL_KEY (공공데이터포털 인증키 — 기존 키 동일)
응답형식: XML
"""
from __future__ import annotations
import os
import re
import time
import logging
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

from .base import BaseScraper, SCRAPER_REGISTRY

logger = logging.getLogger(__name__)

_KEY = os.getenv("PUBLIC_DATA_PORTAL_KEY", "")

_MFDS_URL = (
    "https://apis.data.go.kr/1471057/RNDBSNSPBLANC01/getRndbsnspblanc01"
)

_EXCLUDE_KW = re.compile(
    r"채용|입찰|구매|계약|입사|인재|면접|합격자|공사|용역|물품|청소|경비|보안|퇴직|임원|낙찰|유찰"
)


def _parse_date(text: str) -> str | None:
    if not text:
        return None
    # YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # YYYYMMDD
    m2 = re.match(r"(\d{4})(\d{2})(\d{2})", text.strip())
    if m2:
        return f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}"
    return None


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _find_any(item: ET.Element, *tags: str) -> str:
    """여러 후보 태그 중 처음으로 값이 있는 것 반환."""
    for tag in tags:
        val = _text(item.find(tag))
        if val:
            return val
    return ""


class MFDSScraper(BaseScraper):
    """식품의약품안전처 — 연구관리 사업공고 (바이오·제약·식품·의료기기 R&D)"""

    name = "mfds"
    display_name = "식품의약품안전처(MFDS)"
    origin_url_prefix = "https://www.nifds.go.kr"

    def fetch_items(self) -> List[Dict[str, Any]]:
        if not _KEY:
            logger.warning("[mfds] PUBLIC_DATA_PORTAL_KEY 미설정 — 스킵")
            return []

        items: List[Dict[str, Any]] = []
        seen: set = set()

        for page in range(1, 11):
            try:
                resp = requests.get(
                    _MFDS_URL,
                    params={
                        "serviceKey": _KEY,
                        "pageNo": page,
                        "numOfRows": 100,
                        "type": "xml",
                    },
                    timeout=20,
                )
                resp.raise_for_status()
                root = ET.fromstring(resp.content)
            except Exception as e:
                logger.warning(f"[mfds] page {page} 실패: {e}")
                break

            # 결과코드 확인
            result_code = _text(root.find(".//resultCode"))
            if result_code and result_code != "00" and result_code != "0000":
                logger.warning(f"[mfds] API 오류 코드: {result_code}")
                break

            raw_items = root.findall(".//item")
            if not raw_items:
                break

            # 전체 건수
            try:
                total = int(_text(root.find(".//totalCount")) or "0")
            except ValueError:
                total = 0

            found_new = False
            for item in raw_items:
                # 공고명 — 다양한 태그명 시도
                title = _find_any(
                    item,
                    "blancNm", "subject", "title", "announceNm",
                    "bsnNm", "pjtNm", "rndBsnNm",
                )
                if not title or len(title) < 5 or _EXCLUDE_KW.search(title):
                    continue

                # 고유 ID
                uid = _find_any(
                    item,
                    "blancId", "announceId", "seq", "id", "bsnId",
                )
                if not uid:
                    uid = title[:50]  # fallback
                if uid in seen:
                    continue

                # 상세 URL
                url = _find_any(item, "url", "viewUrl", "linkUrl", "detailUrl")

                # 날짜
                reg_dt = _parse_date(
                    _find_any(item, "creatDt", "regDt", "announDt", "startDe")
                )
                deadline = _parse_date(
                    _find_any(item, "endDe", "deadlineDt", "closeDt", "endDt")
                )

                # 기관명
                dept = _find_any(item, "instNm", "deptNm", "orgNm", "instName") or "식품의약품안전처"

                # URL이 없으면 NIFDS 공고 목록 페이지로 대체
                if not url:
                    url = "https://www.nifds.go.kr/brd/m_15/list.do"

                seen.add(uid)
                found_new = True
                items.append(
                    {
                        "title": title[:400],
                        "origin_url": url,
                        "deadline_date": deadline,
                        "support_amount": None,
                        "summary_text": f"등록일: {reg_dt}" if reg_dt else None,
                        "region": "전국",
                        "category": "바이오·의약",
                        "target_type": None,
                        "department": dept,
                    }
                )

            if not found_new:
                break
            if total and len(items) >= total:
                break

            time.sleep(0.3)

        logger.info(f"[mfds] 수집: {len(items)}건")
        return items


SCRAPER_REGISTRY.append(MFDSScraper())
