"""원문 URL 해석기 + 외부 검색 학습.

1. bizinfo/gov24/smes24 경유지 URL → 원본 기관 URL 추적
2. 공고 제목으로 Google 검색 → 보도자료/정책자료 → knowledge_base 학습
"""

import os
import re
import json
import logging
import requests
import time
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def resolve_bizinfo_final_url(origin_url: str) -> Optional[str]:
    """bizinfo.go.kr 상세 페이지에서 '출처 바로가기' 원본 URL 추출."""
    if not origin_url or "bizinfo.go.kr" not in origin_url:
        return None
    try:
        resp = requests.get(origin_url, headers=_HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            if "바로가기" in text and href.startswith("http") and "bizinfo" not in href:
                return href
        return None
    except Exception as e:
        logger.warning(f"[URLResolver] bizinfo error: {e}")
        return None


def batch_resolve_final_urls(db_conn, limit: int = 50) -> Dict[str, Any]:
    """경유지 URL을 가진 공고에서 원본 URL 일괄 추적.

    Returns: {"processed": int, "resolved": int}
    """
    cur = db_conn.cursor()
    stats = {"processed": 0, "resolved": 0}

    # bizinfo 공고 중 final_url 미확보 건
    cur.execute("""
        SELECT announcement_id, origin_url
        FROM announcements
        WHERE origin_source = 'bizinfo-portal-api'
          AND (final_url IS NULL OR final_url = '')
          AND origin_url IS NOT NULL
        ORDER BY announcement_id DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()

    for r in rows:
        stats["processed"] += 1
        final = resolve_bizinfo_final_url(r["origin_url"])
        if final:
            try:
                cur.execute(
                    "UPDATE announcements SET final_url = %s WHERE announcement_id = %s",
                    (final, r["announcement_id"]),
                )
                stats["resolved"] += 1
            except Exception:
                try:
                    db_conn.rollback()
                except Exception:
                    pass

        # rate limit 방지
        if stats["processed"] % 10 == 0:
            db_conn.commit()
            time.sleep(1)

    db_conn.commit()
    logger.info(f"[URLResolver] Done: {stats['resolved']}/{stats['processed']}")
    return stats


def search_and_learn(db_conn, limit: int = 10) -> Dict[str, Any]:
    """주요 공고 제목으로 Google 검색 → 보도자료/정책자료 → knowledge_base 학습.

    Returns: {"searched": int, "learned": int}
    """
    api_key = os.environ.get("GEMINI_BATCH_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"searched": 0, "learned": 0, "error": "API key not found"}

    cur = db_conn.cursor()
    stats = {"searched": 0, "learned": 0}

    # 분석 안 된 주요 공고 (자금/정책/R&D/창업)
    cur.execute("""
        SELECT a.announcement_id, a.title, a.department, a.category
        FROM announcements a
        LEFT JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
        WHERE aa.announcement_id IS NULL
          AND (a.title ILIKE '%%정책자금%%' OR a.title ILIKE '%%융자%%'
               OR a.title ILIKE '%%창업%%' OR a.title ILIKE '%%R&D%%'
               OR a.title ILIKE '%%스마트공장%%' OR a.title ILIKE '%%소상공인%%')
        ORDER BY a.created_at DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()

    if not rows:
        return stats

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
    except Exception as e:
        return {"searched": 0, "learned": 0, "error": str(e)}

    for r in rows:
        stats["searched"] += 1
        title = r["title"][:80]

        # Gemini + Google Search Grounding으로 검색
        try:
            from google import genai as genai_new
            from google.genai import types as genai_types

            client = genai_new.Client(api_key=api_key)
            prompt = f"""다음 정부 지원사업 공고에 대해 검색하여 핵심 정보를 정리해주세요.

공고명: {title}

다음 항목을 찾아주세요:
1. 지원 대상 (누가 신청 가능?)
2. 지원 금액/한도
3. 신청 기간
4. 자격 요건
5. 신청 방법

JSON 형식으로 응답:
{{"target": "...", "amount": "...", "period": "...", "requirements": "...", "method": "...", "source": "검색된 출처"}}"""

            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
                    max_output_tokens=1024,
                    temperature=0.2,
                ),
            )
            result_text = resp.text.strip()

            # JSON 추출
            try:
                # ```json ... ``` 블록 제거
                if "```json" in result_text:
                    result_text = result_text.split("```json")[-1].split("```")[0].strip()
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0].strip()

                # { ... } 추출
                brace_start = result_text.find("{")
                brace_end = result_text.rfind("}")
                if brace_start != -1 and brace_end > brace_start:
                    result_text = result_text[brace_start:brace_end + 1]

                learned_data = json.loads(result_text)
            except json.JSONDecodeError:
                learned_data = {"raw": result_text[:500]}

            # knowledge_base에 저장
            from app.services.ai_consultant import save_knowledge
            save_knowledge(
                source="web_search",
                knowledge_type="insight",
                content={
                    "title": title,
                    "department": r.get("department", ""),
                    **learned_data,
                },
                db_conn=db_conn,
                category=r.get("category", ""),
                announcement_id=r["announcement_id"],
                confidence=0.7,
                source_agent="crawler",
            )
            stats["learned"] += 1
            logger.info(f"[SearchLearn] Learned: {title[:40]}")

        except Exception as e:
            logger.warning(f"[SearchLearn] Error for '{title[:30]}': {e}")

        # rate limit
        time.sleep(2)

    return stats
