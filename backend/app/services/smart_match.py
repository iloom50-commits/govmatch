"""AI 맞춤 매칭 엔진 — 2단계 정밀 매칭.

1단계: 기존 매칭 (키워드 + 임베딩) → 후보 50건
2단계: AI가 제외 필터 + 우선순위 정렬 → 최종 10건

새벽 파이프라인에서 유료 사용자별로 실행 → user_smart_matches 캐시 저장.
"""

import os
import json
import logging
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def ai_smart_match(
    user_profile: dict,
    candidates: List[dict],
    db_conn=None,
    max_results: int = 10,
) -> List[dict]:
    """AI 2단계 매칭 — 제외 필터 + 우선순위 정렬.

    Args:
        user_profile: 사용자 프로필 (지역/업종/매출/관심사 등)
        candidates: 1단계 매칭 후보 (announcement 딕셔너리 리스트)
        max_results: 최종 반환 건수

    Returns: 정렬된 맞춤 공고 리스트 [{...announcement, match_reason, priority}]
    """
    if not candidates:
        return []

    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        # OpenAI 없으면 기존 결과 그대로 반환
        return candidates[:max_results]

    # 사용자 프로필 요약
    profile_summary = _build_profile_summary(user_profile)

    # 후보 공고 요약 (AI에게 전달할 분량 제한)
    candidates_text = _build_candidates_text(candidates[:50])

    prompt = f"""당신은 정부 지원사업 매칭 전문가입니다.

[사용자 프로필]
{profile_summary}

[후보 공고 {len(candidates[:50])}건]
{candidates_text}

위 사용자에게 맞는 공고를 선별해주세요.

## 1단계: 제외 (반드시 먼저)
아래 해당하면 제외:
- 사용자 업종/지역이 제외 대상에 해당
- 매출/직원수/업력 조건 미충족
- "수행기관 모집", "평가위원 모집", "컨설팅기관 모집" 등 대상이 다른 공고
- 사용자가 기업인데 개인 대상 공고 (또는 반대)

## 2단계: 우선순위 정렬
남은 공고를 아래 순서로 정렬:
1순위: 보조금/무상 지원 (상환 불필요)
2순위: 바우처 (특정 용도 무상)
3순위: 융자/대출 (저금리 상환)
4순위: 기타 (교육, 컨설팅, 인력 등)

같은 순위 내:
- 마감 임박 → 먼저
- 지원금액 큰 것 → 먼저
- 사용자 지역 매칭 → 전국보다 우선

## 응답 형식 (순수 JSON)
{{"results": [
  {{"id": 공고ID, "reason": "추천 이유 (1줄)", "priority": "보조금|바우처|융자|기타", "fit_score": 0~100}},
  ...
]}}

최대 {max_results}건. 자격 미달인 공고는 절대 포함하지 마세요."""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        result_text = resp.choices[0].message.content or ""
        result_data = json.loads(result_text)
        ai_results = result_data.get("results", [])

        # AI 결과를 원본 candidates와 매칭
        matched = []
        candidate_map = {c.get("announcement_id", c.get("id")): c for c in candidates}
        for ar in ai_results[:max_results]:
            ann_id = ar.get("id")
            if ann_id and ann_id in candidate_map:
                entry = dict(candidate_map[ann_id])
                entry["match_reason"] = ar.get("reason", "")
                entry["priority"] = ar.get("priority", "기타")
                entry["fit_score"] = ar.get("fit_score", 50)
                matched.append(entry)

        logger.info(f"[SmartMatch] {len(candidates)} candidates → {len(matched)} matched")
        return matched

    except Exception as e:
        logger.warning(f"[SmartMatch] AI matching error: {e}")
        # 폴백: 기존 결과 그대로
        return candidates[:max_results]


def _build_profile_summary(profile: dict) -> str:
    """사용자 프로필을 AI에게 전달할 요약 텍스트로 변환."""
    parts = []
    field_labels = {
        "address_city": "지역", "industry_code": "업종코드", "company_name": "기업명",
        "revenue_bracket": "매출", "employee_count_bracket": "직원수",
        "establishment_date": "설립일", "interests": "관심분야",
        "age_range": "연령대", "income_level": "소득수준",
        "family_type": "가구형태", "employment_status": "고용상태",
        "housing_status": "주거상태", "user_type": "유형",
        "certifications": "인증", "custom_keywords": "관심키워드",
    }
    for key, label in field_labels.items():
        val = profile.get(key)
        if val:
            parts.append(f"{label}: {val}")
    return "\n".join(parts) if parts else "프로필 정보 없음"


def _build_candidates_text(candidates: List[dict]) -> str:
    """후보 공고를 AI에게 전달할 텍스트로 변환."""
    lines = []
    for i, c in enumerate(candidates, 1):
        ann_id = c.get("announcement_id", c.get("id", "?"))
        title = (c.get("title") or "")[:80]
        dept = (c.get("department") or "")[:30]
        amount = (c.get("support_amount") or "")[:40]
        region = (c.get("region") or "전국")[:20]
        deadline = str(c.get("deadline_date") or "")[:10]
        summary = (c.get("summary_text") or c.get("recommendation_reason") or "")[:150]

        line = f"{i}. [ID:{ann_id}] {title}"
        if dept:
            line += f" ({dept})"
        if amount:
            line += f" | {amount}"
        if region:
            line += f" | {region}"
        if deadline and deadline != "None":
            line += f" | ~{deadline}"
        if summary:
            line += f"\n   {summary}"
        lines.append(line)
    return "\n".join(lines)


def batch_smart_match_for_users(db_conn, limit: int = 50) -> Dict[str, Any]:
    """유료 사용자 전체에 대해 AI 맞춤 매칭 실행 → DB 캐시 저장.

    Returns: {"processed": int, "matched": int}
    """
    cur = db_conn.cursor()
    stats = {"processed": 0, "matched": 0}

    # smart_matches 테이블 생성 (없으면)
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_smart_matches (
                id SERIAL PRIMARY KEY,
                business_number VARCHAR(20) NOT NULL,
                matches JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(business_number)
            )
        """)
        db_conn.commit()
    except Exception:
        try:
            db_conn.rollback()
        except Exception:
            pass

    # 유료 사용자 (LITE + PRO)
    cur.execute("""
        SELECT business_number, company_name, address_city, industry_code,
               revenue_bracket, employee_count_bracket, establishment_date,
               interests, user_type, age_range, income_level, family_type,
               employment_status, housing_status, certifications, custom_keywords
        FROM users
        WHERE plan IN ('lite', 'lite_trial', 'basic', 'pro', 'biz')
          AND business_number IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT %s
    """, (limit,))
    users = cur.fetchall()

    for user in users:
        u = dict(user)
        bn = u.get("business_number")
        if not bn:
            continue

        stats["processed"] += 1
        user_type = (u.get("user_type") or "business").lower()

        try:
            # 1단계: 기존 매칭
            from app.core.matcher import get_matches_hybrid
            target = "individual" if user_type == "individual" else "business"
            matches_conn = db_conn  # 같은 커넥션 사용
            candidates = get_matches_hybrid(u, matches_conn, target_type=target, limit=50)

            if not candidates:
                continue

            # 2단계: AI 정밀 매칭
            smart_results = ai_smart_match(
                user_profile=u,
                candidates=candidates,
                db_conn=db_conn,
                max_results=10,
            )

            if smart_results:
                # DB 캐시 저장
                cur.execute("""
                    INSERT INTO user_smart_matches (business_number, matches, created_at)
                    VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
                    ON CONFLICT (business_number) DO UPDATE SET
                        matches = EXCLUDED.matches,
                        created_at = CURRENT_TIMESTAMP
                """, (bn, json.dumps(smart_results, ensure_ascii=False, default=str)))
                db_conn.commit()
                stats["matched"] += 1

        except Exception as e:
            logger.warning(f"[SmartMatch] Error for {bn}: {e}")
            try:
                db_conn.rollback()
            except Exception:
                pass

        # rate limit
        time.sleep(1)

    logger.info(f"[SmartMatch] Batch done: {stats['processed']} users, {stats['matched']} matched")
    return stats
