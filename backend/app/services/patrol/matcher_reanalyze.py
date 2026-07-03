"""matcher용 eligibility_logic 백필 재분석.

matcher.py는 announcements.eligibility_logic(target_industries/business_type/
target_keywords 등)을 제외 판정에 사용한다. 이 값이 비어있으면 PRO 매칭이 부실해진다.

이 모듈은 elig이 비어있고 아직 AI 재분석되지 않은(ai_analyzed_at IS NULL) 공고를
Gemini로 구조화 추출하여 eligibility_logic을 채우고 ai_analyzed_at을 마킹한다.

우선순위: 기업(business/both) → 실제 마감 있는 것 → 오래된 것(announcement_id ASC).
오래된 것부터 처리하여 starvation(신규만 처리되고 구건이 영원히 밀리는 문제)을 방지한다.
마감 지난 공고는 매칭에 불필요하므로 제외한다.

일일 파이프라인(run_daily_pipeline)의 한 스텝으로 호출된다. 항목별 즉시 커밋하여
중간에 끊겨도 재실행 시 남은 것부터 이어서 처리된다(ai_analyzed_at IS NULL 조건).
"""
import re
import json
import asyncio
import psycopg2.extras
from typing import Dict, Any

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _as_text(v) -> str:
    """AI가 스칼라 컬럼용 필드(department/category/summary)를 리스트로 줄 때가 있어
    varchar/text 컬럼에 그대로 넣으면 psycopg2가 text[]로 변환→타입 불일치 크래시.
    항상 문자열로 강제 변환."""
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v if x)
    return str(v)


def _mark_analyzed_only(db_conn, ann_id: int):
    """지원사업 아님/데이터 부족 등 elig 못 채워도 재처리 방지 마킹."""
    cur = db_conn.cursor()
    cur.execute(
        "UPDATE announcements SET ai_analyzed_at = NOW() WHERE announcement_id = %s",
        (ann_id,),
    )
    db_conn.commit()


def _save(db_conn, ann_id: int, details: dict):
    elig = details.get("eligibility_logic", {})
    if not isinstance(elig, dict):
        elig = {}
    if details.get("business_type"):
        elig["business_type"] = details["business_type"]
    if details.get("target_keywords"):
        elig["target_keywords"] = details["target_keywords"]
    if details.get("target_industries"):
        elig["target_industries"] = details["target_industries"]

    eligibility_json = json.dumps(elig, ensure_ascii=False)
    ai_summary = _as_text(details.get("summary_text") or details.get("description", ""))
    dept = _as_text(details.get("department", ""))
    cat = _as_text(details.get("category", ""))

    dl = details.get("deadline_date")
    dl = dl if (isinstance(dl, str) and _DATE_RE.match(dl)) else None

    cur = db_conn.cursor()
    cur.execute(
        """
        UPDATE announcements SET
            eligibility_logic = %s,
            summary_text = CASE WHEN %s != '' THEN %s ELSE summary_text END,
            department = CASE WHEN department IS NULL OR department = '' THEN %s ELSE department END,
            category = CASE WHEN category IS NULL OR category = '' THEN %s ELSE category END,
            deadline_date = CASE WHEN deadline_date IS NULL AND %s IS NOT NULL THEN CAST(%s AS DATE) ELSE deadline_date END,
            ai_analyzed_at = NOW()
        WHERE announcement_id = %s
        """,
        (
            eligibility_json,
            ai_summary, ai_summary,
            dept,
            cat,
            dl, dl,
            ann_id,
        ),
    )
    db_conn.commit()


def reanalyze_empty_eligibility(db_conn, limit: int = 400) -> Dict[str, Any]:
    """elig 비어있는 미분석 공고를 재분석하여 matcher용 데이터 백필.

    Returns: {"target", "ok", "skipped", "non_support", "failed"}
    """
    from app.services.ai_service import ai_service

    cur = db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT announcement_id, title, summary_text, deadline_date, target_type
        FROM announcements
        WHERE ai_analyzed_at IS NULL
          AND (eligibility_logic IS NULL OR eligibility_logic = '' OR eligibility_logic = '{}')
          AND (deadline_date IS NULL OR deadline_date >= CURRENT_DATE)
        ORDER BY
          CASE WHEN target_type IN ('business', 'both') THEN 0 ELSE 1 END,
          CASE WHEN deadline_date IS NOT NULL THEN 0 ELSE 1 END,
          announcement_id ASC
        LIMIT %s
        """,
        (limit,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    total = len(rows)
    if total == 0:
        return {"target": 0, "ok": 0, "skipped": 0, "non_support": 0, "failed": 0}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    ok = skipped = non_support = failed = 0
    try:
        for row in rows:
            ann_id = row["announcement_id"]
            title = row.get("title") or ""
            clean = _strip_html(row.get("summary_text") or "")

            # 데이터 너무 부족 → 마킹만 (재처리 방지)
            if len(clean) < 20 and len(title.strip()) < 10:
                _mark_analyzed_only(db_conn, ann_id)
                skipped += 1
                continue

            input_text = f"제목: {title}\n\n내용: {clean[:8000]}"
            try:
                details = loop.run_until_complete(ai_service.extract_program_details(input_text))
            except Exception:
                failed += 1  # AI 예외 → 마킹 안 함(다음 실행에서 재시도)
                continue

            if not details:  # {} = AI/파싱 오류 → 재시도 대상
                failed += 1
                continue

            try:
                if details.get("is_support_program") is False:
                    _mark_analyzed_only(db_conn, ann_id)
                    non_support += 1
                else:
                    _save(db_conn, ann_id, details)
                    ok += 1
            except Exception:
                try:
                    db_conn.rollback()
                except Exception:
                    pass
                failed += 1
    finally:
        loop.close()

    return {"target": total, "ok": ok, "skipped": skipped,
            "non_support": non_support, "failed": failed}
