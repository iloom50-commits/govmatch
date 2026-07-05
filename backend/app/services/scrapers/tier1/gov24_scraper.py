"""보조금24 (정부24 공공서비스) API 스크래퍼

출처: api.odcloud.kr/api/gov24/v3/serviceList
인증: PUBLIC_DATA_PORTAL_KEY (공공데이터포털 인증키)
커버: 중앙부처 보조금·지원사업 (1,000건+)
"""
from __future__ import annotations
import os
import re
import logging
import requests
from typing import List, Dict, Any

from .base import BaseScraper, register

logger = logging.getLogger(__name__)

_KEY = os.getenv("PUBLIC_DATA_PORTAL_KEY", "")
_BASE = "https://api.odcloud.kr/api/gov24/v3/serviceList"
_PER_PAGE = 100
_MAX_PAGES = 300  # 안전 상한 (30,000건) — 실제론 totalCount 기준 조기 종료

_EXCLUDE_KW = re.compile(
    r"채용|입찰|구매|계약|임원|인재|면접|합격자|공사|용역|물품|청소|경비|보안|퇴직|고용공고"
)

_CATEGORY_MAP = {
    "창업": "창업지원",
    "기술": "기술개발",
    "수출": "수출마케팅",
    "금융": "정책자금",
    "보증": "정책자금",
    "고용": "고용지원",
    "복지": "취업",
    "주거": "주거",
    "교육": "교육",
    "청년": "청년",
    "장애": "장애",
    "노인": "노인",
    "육아": "육아",
    "출산": "출산",
    "의료": "의료",
    "저소득": "저소득",
}


def _guess_category(text: str) -> str | None:
    for kw, cat in _CATEGORY_MAP.items():
        if kw in text:
            return cat
    return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


@register
class Gov24Scraper(BaseScraper):
    name = "gov24"
    display_name = "보조금24(정부24)"
    origin_url_prefix = "https://www.gov.kr"
    skip_consecutive_break = True  # serviceList는 최신순 정렬 아님 — 전체 순회 필요

    def fetch_items(self) -> List[Dict[str, Any]]:
        if not _KEY:
            logger.warning("[gov24] PUBLIC_DATA_PORTAL_KEY 미설정 — 스킵")
            return []

        results = []
        for page in range(1, _MAX_PAGES + 1):
            try:
                resp = requests.get(
                    _BASE,
                    params={
                        "serviceKey": _KEY,
                        "returnType": "JSON",
                        "page": page,
                        "perPage": _PER_PAGE,
                    },
                    timeout=20,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"[gov24] page {page} 요청 실패: {e}")
                break

            items = data.get("data") or []
            if not items:
                break

            for item in items:
                title = _clean(item.get("서비스명") or item.get("svcNm") or "")
                if not title or _EXCLUDE_KW.search(title):
                    continue

                detail_url = (
                    item.get("온라인신청사이트URL")
                    or item.get("사이트URL")
                    or item.get("svcInfoUrl")
                    or ""
                ).strip()
                if not detail_url:
                    # gov.kr 서비스 상세 fallback
                    svc_id = item.get("서비스ID") or item.get("svcId") or ""
                    if svc_id:
                        detail_url = f"https://www.gov.kr/portal/rcvfvrSvc/dtlEx/{svc_id}"

                if not detail_url:
                    continue

                summary = _clean(
                    item.get("서비스목적요약") or item.get("svcPpo") or ""
                )
                dept = _clean(item.get("소관기관명") or item.get("jrsdDptAllNm") or "보조금24")

                # 지원대상 텍스트로 카테고리 추정
                target_txt = _clean(item.get("지원대상") or "")
                content_txt = title + " " + summary + " " + target_txt
                category = _guess_category(content_txt)

                results.append(
                    {
                        "title": title,
                        "origin_url": detail_url,
                        # serviceList가 신청기한 제공(구 주석 '마감일 필드 없음'은 오류) → 관문이 파싱 (P2-2 (d) 복구)
                        "deadline_raw": _clean(item.get("신청기한") or "") or None,
                        "support_amount": None,
                        "summary_text": summary or None,
                        "region": "전국",
                        "category": category,
                        "target_type": None,  # AI 분류 에이전트가 처리
                        "department": dept,
                    }
                )

            # 마지막 페이지 확인
            total = int(data.get("totalCount") or data.get("matchCount") or 0)
            if page * _PER_PAGE >= total:
                break

        logger.info(f"[gov24] 수집 완료: {len(results)}건")
        return results
