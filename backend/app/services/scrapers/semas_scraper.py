"""소상공인시장진흥공단(semas.or.kr) 공지사항 수집기.

상세 페이지는 JavaScript 렌더링이라 직접 크롤링 불가.
목록 API에서 자금 종류/대출 유형/제목/날짜를 수집하여 knowledge_base에 저장.
상세 공고문은 중기부(mss.go.kr)에서 수집.
"""

import os
import json
import logging
import requests
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

LIST_API = "https://ols.semas.or.kr/ols/man/SMAN051M/search.do"
DETAIL_PAGE = "https://ols.semas.or.kr/ols/man/SMAN052M/page.do"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://ols.semas.or.kr/ols/man/SMAN051M/page.do",
}


def fetch_semas_list(page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
    """소진공 공지사항 목록 API 호출."""
    try:
        resp = requests.post(
            LIST_API,
            headers=_HEADERS,
            data={"pageNo": str(page), "pageSize": str(page_size)},
            timeout=15,
        )
        if resp.status_code not in (200, 201):
            return []
        data = resp.json()
        return data.get("result", [])
    except Exception as e:
        logger.warning(f"[SEMAS] List fetch error: {e}")
        return []


def sync_semas_knowledge(db_conn, max_pages: int = 3) -> Dict[str, Any]:
    """소진공 공고 목록을 knowledge_base에 동기화.

    소진공 자금 정보(직접대출/대리대출, 자금 종류)를
    knowledge_base에 저장하여 AI 상담 품질 향상.
    """
    from app.services.ai_consultant import save_knowledge

    stats = {"fetched": 0, "new_knowledge": 0}

    for page in range(1, max_pages + 1):
        items = fetch_semas_list(page=page, page_size=20)
        if not items:
            break

        for item in items:
            stats["fetched"] += 1
            title = item.get("bltwtrTitNm", "")
            loan_type = item.get("loanSeCdNm", "")
            category = item.get("bltwtrClcd", "")
            reg_date = item.get("frstRegDt", "")
            seq = item.get("bltwtrSeq")

            if not title:
                continue

            # knowledge_base에 이미 있는지 확인 (제목 기준)
            try:
                cur = db_conn.cursor()
                cur.execute("""
                    SELECT id FROM knowledge_base
                    WHERE source = 'semas_sync'
                      AND content::text ILIKE %s
                    LIMIT 1
                """, (f"%{title[:50]}%",))
                if cur.fetchone():
                    continue
            except Exception:
                try:
                    db_conn.rollback()
                except Exception:
                    pass
                continue

            content = {
                "title": title,
                "loan_type": loan_type,
                "category": category,
                "reg_date": reg_date,
                "source_url": f"{DETAIL_PAGE}?bltwtrSeq={seq}",
                "organization": "소상공인시장진흥공단",
            }

            try:
                save_knowledge(
                    source="semas_sync",
                    knowledge_type="trend",
                    content=content,
                    db_conn=db_conn,
                    category="소상공인",
                    confidence=0.7,
                    source_agent="crawler",
                )
                stats["new_knowledge"] += 1
            except Exception as e:
                logger.warning(f"[SEMAS] Knowledge save error: {e}")

    logger.info(f"[SEMAS] Synced: fetched={stats['fetched']}, new={stats['new_knowledge']}")
    return stats
