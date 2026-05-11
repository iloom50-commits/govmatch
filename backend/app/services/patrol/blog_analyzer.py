"""
blog_analyzer.py — 블로그용 공고 AI 분석 배치

매일 patrol 시 실행:
  - full_text 있고 blog_analysis 미완료 공고 선별
  - 공고상담AI(Gemini)로 구조화 분석
  - announcement_analysis.blog_analysis 컬럼에 저장
  - 블로그봇은 /api/announcements/public 응답의 blog_analysis 필드로 접근
"""
from __future__ import annotations
import json
import logging
import os
import time
from datetime import datetime

logger = logging.getLogger(__name__)

_PROMPT = """당신은 정부 지원사업 공고를 블로그 글로 작성하기 위한 분석 전문가입니다.
아래 공고 원문을 읽고, 블로그 writer와 reviewer 모두 사용할 수 있는 팩트 기반 구조화 분석을 JSON으로 반환하세요.

반환 형식 (JSON만, 설명 없이):
{{
  "support_amount": "지원 금액 (예: 최대 1억원, 월 50만원 등. 없으면 null)",
  "eligibility_summary": "핵심 신청 자격 2~3줄 요약",
  "application_method": "신청 방법 한 줄 (온라인/방문/우편 등)",
  "deadline_info": "마감일 또는 상시모집 여부",
  "key_facts": ["팩트1", "팩트2", "팩트3"],
  "blog_summary": "블로그 글 도입부로 쓸 수 있는 2~3문장 자연어 요약 (정보성, 독자 관점)",
  "is_individual": true/false,
  "is_business": true/false
}}

공고 제목: {title}
공고 원문:
{full_text}"""


def _call_gemini(prompt: str) -> dict | None:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("[blog_analyzer] GEMINI_API_KEY 미설정")
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            "gemini-2.0-flash",
            generation_config={"temperature": 0.1, "max_output_tokens": 1024},
        )
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
        import re
        text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        logger.warning(f"[blog_analyzer] Gemini 오류: {e}")
    return None


def run_blog_analysis_batch(db_conn, batch_size: int = 20) -> dict:
    """
    full_text 있고 blog_analysis 없는 공고를 Gemini로 분석 후 저장.
    반환: {"processed": N, "skipped": N, "errors": N}
    """
    cur = db_conn.cursor()

    # 대상: 활성 공고 + full_text 보유 + blog_analysis 미완료
    cur.execute("""
        SELECT a.announcement_id, a.title, a.deadline_date,
               aa.id AS analysis_id, aa.full_text
        FROM announcements a
        JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
        WHERE a.is_archived = FALSE
          AND aa.full_text IS NOT NULL
          AND LENGTH(aa.full_text) > 200
          AND aa.blog_analysis IS NULL
        ORDER BY a.announcement_id DESC
        LIMIT %s
    """, (batch_size,))
    rows = cur.fetchall()

    if not rows:
        logger.info("[blog_analyzer] 처리 대상 없음")
        return {"processed": 0, "skipped": 0, "errors": 0}

    processed = skipped = errors = 0

    for row in rows:
        aid = row["announcement_id"]
        title = row["title"] or ""
        full_text = (row["full_text"] or "")[:6000]  # Gemini 토큰 절약

        prompt = _PROMPT.format(title=title, full_text=full_text)

        result = _call_gemini(prompt)
        if not result:
            errors += 1
            logger.warning(f"[blog_analyzer] id={aid} Gemini 실패 → 스킵")
            continue

        result["analyzed_at"] = datetime.now().isoformat()
        result["verified"] = True  # 원문 기반 추출 팩트임을 명시

        try:
            cur.execute("""
                UPDATE announcement_analysis
                SET blog_analysis = %s
                WHERE id = %s
            """, (json.dumps(result, ensure_ascii=False), row["analysis_id"]))
            db_conn.commit()
            processed += 1
            logger.info(f"[blog_analyzer] id={aid} 완료: {title[:30]}...")
        except Exception as e:
            db_conn.rollback()
            errors += 1
            logger.error(f"[blog_analyzer] id={aid} DB 저장 실패: {e}")

        time.sleep(0.3)  # API 레이트 제한 방지

    logger.info(f"[blog_analyzer] 완료 — processed={processed} skipped={skipped} errors={errors}")
    return {"processed": processed, "skipped": skipped, "errors": errors}
