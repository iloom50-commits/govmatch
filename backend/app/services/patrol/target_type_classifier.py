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

_CLASSIFY_PROMPT = """당신은 한국 정부 지원사업 공고의 신청 대상을 분류하는 전문 AI입니다.

아래 공고 목록을 보고 각 공고의 신청 대상과 분류 신뢰도를 반환하세요.

━━━ 분류 기준 ━━━
- business: 기업/법인/사업체/창업기업이 신청 대상
  (중소기업, 스타트업, 법인, 협동조합, 창업기업, 창업팀, 벤처기업 등)
- individual: 개인이 신청 대상
  (사업자등록 없이 개인 자격으로 신청하는 청년·취업자·구직자·임산부·노인·장애인·학생·저소득층 등)
- both: 개인사업자(사업자등록증 보유)와 법인 모두 신청 가능
  (주로 소상공인, 자영업자, 1인창조기업 대상)

━━━ 판단 원칙 (엄격 적용) ━━━
- 창업기업/스타트업/벤처 모집 → business
- 예비창업자 개인 단독 대상 → individual
- 예비창업자 + 창업기업 모두 → both
- 소상공인/자영업자/1인창조기업 → business  ← 소상공인은 사업자이므로 기업 분류
- R&D, 수출, 투자유치, 기업인증, 입주, 판로지원 → business
- 주거지원, 복지급여, 장학금, 취업지원, 의료비, 육아, 출산 → individual
- 청년창업팀/창업기업 신청 → business / 예비창업자 개인 신청 → individual
- 소관기관(department)이 소상공인시장진흥공단·중소벤처기업진흥공단·기술보증기금·신용보증기금·중소벤처기업부·창업진흥원 등 기업지원기관이면 business 우선 (단 취업·주거·복지·장학·의료 성격이면 individual)

⚠️ "both"는 예비창업자와 창업기업이 동시 신청 가능한 경우만. 소상공인은 "business".

━━━ 분류 예시 (few-shot) ━━━
- "중소기업 R&D 사업화 지원" → business (90)
- "스타트업 투자유치 프로그램 모집" → business (95)
- "소상공인 경영 안정자금 지원" → business (92)
- "자영업자 고용보험 지원" → business (88)
- "청년 예비창업자 창업지원금" → individual (85)
- "청년 취업 연계 프로그램" → individual (90)
- "임산부 의료비 지원사업" → individual (98)
- "1인 가구 주거 임차 보증금 지원" → individual (95)
- "창업기업 글로벌 진출 지원" → business (88)
- "예비창업자·창업초기기업 공모전" → both (80)

━━━ 공고 목록 (JSON) ━━━
{items_json}

━━━ 응답 형식 ━━━
반드시 아래 JSON 배열만 반환하세요. 설명 없이 JSON만:
[{{"id": 1, "type": "business", "confidence": 90}}, {{"id": 2, "type": "individual", "confidence": 75}}, ...]

confidence는 0~100 정수. 판단이 불확실할수록 낮게 (70 미만이면 "both" 권장).
반드시 모든 id를 포함하세요."""


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
    "kised-api",         # 창업진흥원(KISED) API
    "bizinfo",           # 비즈인포 (중기부)
    "bizinfo-api",
    "bizinfo-portal-api",
    "smes24-api",        # 중소기업24 (중기부 직접 연계)
    "mss-direct",        # 중소벤처기업부 직접
    "kosme",             # 중소벤처기업진흥공단
    "smba",              # 중소벤처기업부
    "kotra",             # KOTRA 수출
    "kibo",              # 기술보증기금
    "kdb",               # KDB 산업은행
    "ibk",               # IBK 기업은행
    "kventure",          # 벤처기업협회
    "ccei",              # 창조경제혁신센터
    "창조경제혁신센터",   # admin-manual:창조경제혁신센터 형태 대응
}

# 출처 기반 강제 규칙 — 개인(복지) 전용 출처. 출처 자체가 대상 확정 → AI 판단 불필요.
_INDIVIDUAL_ONLY_SOURCES = {
    "gov24-individual-api",   # 정부24 개인 복지서비스
    "local-welfare-api",      # 지자체 복지서비스
    "national-welfare-api",   # 중앙부처 복지서비스
    "bokjiro",                # 복지로 (scraper:bokjiro_central / _local)
}

# 출처로 대상이 확정되는 모든 권위 출처 — 재분류 대상에서 제외 (Gemini가 뒤집지 못하게)
_AUTHORITATIVE_SOURCES = _BUSINESS_ONLY_SOURCES | _INDIVIDUAL_ONLY_SOURCES

# 소관기관 기반 강제 규칙 — 모든 사업이 '사업자(개인사업자+법인)' 전용인 전담기관.
# 출처가 개인피드(gov24-individual-api 등)여도 이 기관 소관이면 business 로 확정.
# (소상공인=개인사업자=사업자. target_type 축은 '사업자냐 아니냐'이지 법인이냐가 아님)
# 주의: 중소벤처기업부(부처)·창업진흥원(예비창업 혼재)은 범위가 넓어 제외 → Gemini 판단.
_BUSINESS_ONLY_DEPTS = (
    "소상공인시장진흥공단",
    "중소벤처기업진흥공단",
    "기술보증기금",
    "신용보증기금",
)


def _apply_source_override(items: list[dict]) -> tuple[dict[int, str], list[dict]]:
    """출처·소관기관 기반 강제 분류. 나머지는 Gemini로 넘김.
    Returns: (강제분류결과, Gemini에 넘길 items)
    """
    forced = {}
    remaining = []
    for it in items:
        src = (it.get("origin_source") or "").lower()
        dept = it.get("department") or ""
        # 1순위: 사업자 전담기관 소관 → 개인피드여도 business (소상공인 자금 구제)
        if any(d in dept for d in _BUSINESS_ONLY_DEPTS):
            forced[it["id"]] = "business"
        # 2순위: 개인 출처 — 복지 출처가 business로 뒤집히는 것을 영구 차단
        elif any(s in src for s in _INDIVIDUAL_ONLY_SOURCES):
            forced[it["id"]] = "individual"
        elif any(s in src for s in _BUSINESS_ONLY_SOURCES):
            forced[it["id"]] = "business"
        else:
            remaining.append(it)
    return forced, remaining


# Gemini 1회 호출당 항목 수 — gemini-2.5-flash는 thinking 토큰이 출력 한도를 소모하므로
# 청크를 작게 + 토큰 한도를 넉넉히 둬야 응답 본문이 비지 않음
_GEMINI_CHUNK = 10


def _call_gemini_classify(items: list[dict]) -> dict[int, dict]:
    """Gemini에 분류 요청. {id: {"type","confidence"}} dict 반환.

    items를 _GEMINI_CHUNK 단위로 나눠 호출 — 대량 배치 시 응답이 잘려 JSON이
    깨지는 것을 방지. 일부 청크 실패는 건너뛰고, 전체 실패 시에만 예외 전파
    (상위 _classify_and_update의 키워드 폴백이 처리).
    """
    import google.generativeai as genai
    import os
    import re

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 없음")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    out: dict[int, dict] = {}
    for start in range(0, len(items), _GEMINI_CHUNK):
        chunk = items[start:start + _GEMINI_CHUNK]
        items_json = json.dumps(
            [{"id": it["id"], "title": it["title"], "department": it.get("department") or "", "category": it["category"] or "", "summary": (it["summary"] or "")[:200]}
             for it in chunk],
            ensure_ascii=False,
        )
        prompt = _CLASSIFY_PROMPT.replace("{items_json}", items_json)
        try:
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 8192},
            )
            raw = (response.text or "").strip()
            if "```" in raw:
                m = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
                raw = m.group(1).strip() if m else raw
            for item in json.loads(raw):
                out[item["id"]] = {"type": item["type"], "confidence": item.get("confidence", 80)}
        except Exception as e:
            logger.warning(f"[classifier] 청크 분류 실패(start={start}, n={len(chunk)}): {e}")
            continue

    if not out and items:
        # 전체 실패 → 상위 키워드 폴백이 처리하도록 예외 전파
        raise RuntimeError("Gemini 분류 전체 실패 (모든 청크 파싱 불가)")
    return out


def ai_classify_pending(conn, batch_size: int = 20) -> dict:
    """신규/미분류 공고 AI 분류.

    대상:
    1. target_type IS NULL — 새로 수집된 공고 (base.py가 항상 NULL로 저장)
    2. 최근 30일 내 비화이트리스트 출처의 "business" — 하드코딩 잔재 재분류
    """
    cur = conn.cursor()

    # 비화이트리스트 출처 패턴 (출처로 대상 확정되는 권위 출처는 재분류 제외)
    # 주의: cur.execute에 params를 넘기므로 ILIKE 리터럴 '%'는 '%%'로 이스케이프 필수
    #       (그렇지 않으면 psycopg2가 '%s' 등을 파라미터로 오인 → IndexError)
    non_whitelist_condition = " AND ".join(
        f"origin_source NOT ILIKE '%%{s}%%'" for s in _AUTHORITATIVE_SOURCES
    )

    cur.execute(f"""
        SELECT announcement_id AS id, title, category, summary_text AS summary, origin_source, department
        FROM announcements
        WHERE is_archived = FALSE
          AND (
            target_type IS NULL
            OR (
              target_type = 'business'
              AND created_at >= NOW() - INTERVAL '30 days'
              AND {non_whitelist_condition}
            )
          )
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
            SELECT announcement_id AS id, title, category, summary_text AS summary, origin_source, department
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
    # gemini_map: {id: {"type": str, "confidence": int}}
    gemini_map: dict[int, dict] = {}
    if remaining:
        try:
            gemini_map = _call_gemini_classify(remaining)
        except Exception as e:
            logger.error(f"[classifier] Gemini 호출 오류: {e}")
            fallback = _keyword_fallback([it["id"] for it in remaining],
                                         {it["id"]: it for it in remaining})
            gemini_map = {aid: {"type": t, "confidence": 60} for aid, t in fallback.items()}
            errors += 1

    for item in items:
        aid = item["id"]
        if aid in forced_map:
            new_type = forced_map[aid]
        elif aid in gemini_map:
            result = gemini_map[aid]
            raw_type = result.get("type", "both")
            confidence = result.get("confidence", 80)
            # 신뢰도 70 미만 → 양쪽 탭에 노출되는 "both"로 안전 처리
            if confidence < 70:
                new_type = "both"
                logger.info(f"[classifier] id={aid} 신뢰도 낮음({confidence}) → both 처리")
            else:
                new_type = raw_type
        else:
            # Gemini 응답에 없는 항목 — 기업으로 추락시키지 않고 both(양쪽 노출)로 안전 처리
            new_type = "both"

        if new_type not in valid_types:
            new_type = "both"

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
