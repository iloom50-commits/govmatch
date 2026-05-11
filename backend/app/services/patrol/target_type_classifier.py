"""공고 target_type AI 분류기

근본 해결: 키워드 매칭이 아닌 Gemini AI가 공고 제목+요약+카테고리를 보고
business / individual / both 를 정확하게 판별한다.

안전장치:
  backup_target_types(conn, label)  → 백업 테이블에 현재 값 저장
  rollback_target_types(conn, label) → 백업에서 원복
  ai_classify_pending(conn, batch_size) → NULL or 'business'(기본값) 공고 AI 분류
  reclassify_all(conn, batch_size) → 전체 공고 일괄 재분류 (1회성 마이그레이션)
"""

from __future__ import annotations
import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

_CLASSIFY_PROMPT = """당신은 한국 정부 지원사업 공고의 신청 대상을 분류하는 전문가입니다.

아래 공고 목록을 보고 각 공고의 신청 대상을 정확히 분류하세요.

분류 기준:
- business: 기업/법인/사업체/창업기업이 신청 대상 (중소기업, 스타트업, 법인, 협동조합, 창업기업, 창업팀 등)
- individual: 개인이 신청 대상 (청년, 취업자, 구직자, 1인 가구, 임산부, 노인, 장애인, 학생, 저소득층 등 사업자등록 없이 개인 자격으로 신청)
- both: 개인사업자(사업자등록증 보유)와 법인 모두 신청 가능한 경우만 해당 (주로 소상공인 대상 공고)

판단 원칙 (엄격 적용):
- 창업기업/스타트업/벤처 모집 공고 → business (법인 여부 무관, 창업 "기업" 대상이면 business)
- 예비창업자 개인 단독 대상 → individual
- 예비창업자 + 창업기업 모두 대상 → both
- 소상공인 (개인사업자 + 법인 모두) → both
- R&D, 수출, 투자유치, 기업인증, 입주, 판로 → business
- K-Startup, 창업진흥원, 중기부 창업 지원사업 → business
- 주거지원, 복지급여, 장학금, 취업지원, 의료비, 육아, 출산 → individual
- 청년창업: "창업기업" 또는 "창업팀" 신청 → business / "예비창업자 개인" 신청 → individual

⚠️ 핵심: "both"는 소상공인처럼 개인사업자와 법인이 동시에 신청 가능한 경우만 사용하세요.
창업기업 모집공고, 스타트업 모집공고는 "both"가 아니라 "business"입니다.

공고 목록 (JSON):
{items_json}

응답은 반드시 아래 형식의 JSON 배열만 반환하세요. 설명 없이 JSON만:
[{{"id": 1, "type": "business"}}, {{"id": 2, "type": "individual"}}, ...]"""


def _ensure_backup_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS announcements_target_type_backup (
            id SERIAL PRIMARY KEY,
            announcement_id INTEGER NOT NULL,
            original_target_type VARCHAR(20),
            backed_up_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            backup_label VARCHAR(100)
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_attb_label
        ON announcements_target_type_backup (backup_label)
    """)


def backup_target_types(conn, label: str = "auto") -> int:
    """현재 announcements.target_type 값을 백업 테이블에 저장.

    Returns: 백업된 건수
    """
    cur = conn.cursor()
    _ensure_backup_table(cur)

    # 같은 label이 이미 있으면 덮어쓰기 (중복 방지)
    cur.execute(
        "DELETE FROM announcements_target_type_backup WHERE backup_label = %s",
        (label,),
    )

    cur.execute("""
        INSERT INTO announcements_target_type_backup
            (announcement_id, original_target_type, backup_label)
        SELECT announcement_id, target_type, %s
        FROM announcements
    """, (label,))

    count = cur.rowcount
    conn.commit()
    logger.info(f"[backup] target_type 백업 완료: {count}건 (label={label})")
    return count


def rollback_target_types(conn, label: str = "auto") -> int:
    """백업 테이블에서 target_type 원복.

    Returns: 원복된 건수
    """
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) as cnt FROM announcements_target_type_backup WHERE backup_label = %s",
        (label,),
    )
    row = cur.fetchone()
    cnt = row["cnt"] if row else 0
    if cnt == 0:
        logger.error(f"[rollback] 백업 없음 (label={label})")
        return 0

    cur.execute("""
        UPDATE announcements a
        SET target_type = b.original_target_type
        FROM announcements_target_type_backup b
        WHERE a.announcement_id = b.announcement_id
          AND b.backup_label = %s
    """, (label,))

    updated = cur.rowcount
    conn.commit()
    logger.info(f"[rollback] target_type 원복 완료: {updated}건 (label={label})")
    return updated


# 출처 기반 강제 규칙 — Gemini 판단 없이 고정
_BUSINESS_ONLY_SOURCES = {
    "kstartup",          # K-Startup 창업진흥원 포털
    "kstartup-api",
    "bizinfo",           # 비즈인포 (중기부)
    "bizinfo-api",
    "kosme",             # 중소벤처기업진흥공단
    "smba",              # 중소벤처기업부
    "kotra",             # KOTRA 수출
    "kibo",              # 기술보증기금
    "kdb",               # KDB 산업은행
    "ibk",               # IBK 기업은행
    "kventure",          # 벤처기업협회
}


def _apply_source_override(items: list[dict]) -> tuple[dict[int, str], list[dict]]:
    """출처 기반 강제 분류. 나머지는 Gemini로 넘김.
    Returns: (강제분류결과, Gemini에 넘길 items)
    """
    forced = {}
    remaining = []
    for it in items:
        src = (it.get("origin_source") or "").lower()
        if any(s in src for s in _BUSINESS_ONLY_SOURCES):
            forced[it["id"]] = "business"
        else:
            remaining.append(it)
    return forced, remaining


def _call_gemini_classify(items: list[dict]) -> dict[int, str]:
    """Gemini에 배치 분류 요청. {id: type} dict 반환."""
    import google.generativeai as genai
    import os

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 없음")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    items_json = json.dumps(
        [{"id": it["id"], "title": it["title"], "category": it["category"] or "", "summary": (it["summary"] or "")[:200]}
         for it in items],
        ensure_ascii=False,
    )

    prompt = _CLASSIFY_PROMPT.replace("{items_json}", items_json)

    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.1, "max_output_tokens": 2048},
    )

    raw = response.text.strip()
    # JSON 블록 추출 (마크다운 코드블록 감싸진 경우 대응)
    if "```" in raw:
        import re
        m = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
        raw = m.group(1).strip() if m else raw

    result_list = json.loads(raw)
    return {item["id"]: item["type"] for item in result_list}


def ai_classify_pending(conn, batch_size: int = 20) -> dict:
    """NULL 또는 분류 미확정 공고만 AI로 분류.

    daily_pipeline ③ DB 정리 단계에서 호출.
    신규 수집 공고(target_type IS NULL)를 대상으로 실행.
    """
    cur = conn.cursor()

    cur.execute("""
        SELECT announcement_id AS id, title, category, summary_text AS summary, origin_source
        FROM announcements
        WHERE target_type IS NULL
          AND is_archived = FALSE
        ORDER BY created_at DESC
        LIMIT %s
    """, (batch_size,))

    rows = cur.fetchall()
    if not rows:
        return {"classified": 0, "skipped": 0}

    items = [dict(r) for r in rows]
    return _classify_and_update(conn, cur, items, label="pending")


def reclassify_all(conn, batch_size: int = 20, max_batches: int = 200,
                   backup_label: str = "before_reclassify_all") -> dict:
    """기존 DB 전체 공고 AI 재분류 (1회성 마이그레이션).

    실행 전 자동 백업. 오류 시 rollback 가능.
    admin 엔드포인트에서 수동 트리거.
    """
    # 안전장치: 실행 전 백업
    backed_up = backup_target_types(conn, label=backup_label)
    logger.info(f"[reclassify_all] 백업 완료 {backed_up}건 → 분류 시작")

    cur = conn.cursor()

    total_classified = 0
    total_errors = 0
    batches_done = 0

    for _ in range(max_batches):
        cur.execute("""
            SELECT announcement_id AS id, title, category, summary_text AS summary, origin_source
            FROM announcements
            WHERE is_archived = FALSE
            ORDER BY announcement_id
            LIMIT %s OFFSET %s
        """, (batch_size, batches_done * batch_size))

        rows = cur.fetchall()
        if not rows:
            break

        items = [dict(r) for r in rows]

        try:
            result = _classify_and_update(conn, cur, items, label=None)
            total_classified += result["classified"]
            total_errors += result.get("errors", 0)
        except Exception as e:
            logger.error(f"[reclassify_all] 배치 {batches_done} 오류: {e}")
            total_errors += len(items)

        batches_done += 1
        time.sleep(0.5)  # API rate limit 방지

    summary = {
        "backed_up": backed_up,
        "backup_label": backup_label,
        "classified": total_classified,
        "errors": total_errors,
        "batches": batches_done,
    }
    logger.info(f"[reclassify_all] 완료: {summary}")
    return summary


def _classify_and_update(conn, cur, items: list[dict], label: Optional[str]) -> dict:
    """items 배치를 Gemini로 분류 후 DB 업데이트."""
    valid_types = {"business", "individual", "both"}
    classified = 0
    errors = 0

    # 1단계: 출처 기반 강제 분류
    forced_map, remaining = _apply_source_override(items)
    if forced_map:
        logger.info(f"[classifier] 출처 강제 business: {len(forced_map)}건")

    # 2단계: 나머지만 Gemini 분류
    gemini_map: dict[int, str] = {}
    if remaining:
        try:
            gemini_map = _call_gemini_classify(remaining)
        except Exception as e:
            logger.error(f"[classifier] Gemini 호출 오류: {e}")
            gemini_map = _keyword_fallback([it["id"] for it in remaining],
                                           {it["id"]: it for it in remaining})
            errors += 1

    type_map = {**forced_map, **gemini_map}

    for item in items:
        aid = item["id"]
        new_type = type_map.get(aid, "business")
        if new_type not in valid_types:
            new_type = "business"

        try:
            cur.execute(
                "UPDATE announcements SET target_type = %s WHERE announcement_id = %s",
                (new_type, aid),
            )
            classified += 1
        except Exception as e:
            logger.error(f"[classifier] UPDATE 오류 id={aid}: {e}")
            errors += 1

    conn.commit()
    return {"classified": classified, "errors": errors}


def _keyword_fallback(ids: list[int], items_by_id: dict) -> dict[int, str]:
    """Gemini 실패 시 키워드 기반 폴백 분류."""
    INDIVIDUAL_KW = [
        "다자녀", "출산", "임신", "산모", "육아", "보육", "어린이집",
        "장학금", "학비", "등록금", "학자금",
        "취업지원", "구직", "직업훈련", "취업성공패키지",
        "주거급여", "전세대출", "임대주택", "월세지원",
        "노인", "어르신", "경로", "고령자",
        "장애인", "장애수당", "활동지원",
        "기초생활", "차상위", "한부모", "긴급복지", "생계급여", "저소득",
        "청년수당", "청년월세", "청년내일저축", "청년지원",
        "의료비지원", "건강검진", "진료비",
        "교육바우처", "배움카드",
    ]
    BOTH_KW = [
        "소상공인", "자영업자", "1인창조기업",
        "예비창업자",  # 예비창업자(개인)+창업기업 모두 가능한 경우
    ]
    result = {}
    for aid in ids:
        item = items_by_id.get(aid, {})
        text = f"{item.get('title','')} {item.get('category','')}"
        if any(kw in text for kw in BOTH_KW):
            result[aid] = "both"
        elif any(kw in text for kw in INDIVIDUAL_KW):
            result[aid] = "individual"
        else:
            result[aid] = "business"
    return result
