"""
[B 작업] eligibility_logic / category 비어있는 공고 67건 메타데이터 재추론

각 공고에 대해:
- 제목 + 요약을 Gemini에 전달
- target_type (business/individual), category, eligibility_logic JSON 추출
- DB 업데이트

Usage:
  python scripts/reclassify_missing_metadata.py          # dry-run
  python scripts/reclassify_missing_metadata.py --apply  # 실제 적용
"""
import os
import sys
import json
import time
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.main import get_db_connection, valid_announcement_where

import google.generativeai as genai
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

SCHEMA = {
    "type": "object",
    "properties": {
        "target_type": {"type": "string", "enum": ["business", "individual", "both"]},
        "category": {
            "type": "string",
            "enum": [
                "창업지원", "R&D/기술개발", "자금/융자", "경영지원",
                "수출/해외진출", "인력양성/교육", "고용/채용",
                "시설/환경", "정보/안내", "복지/지원금", "기타"
            ],
        },
        "region_restriction": {"type": "string"},
        "min_founding_years": {"type": "integer"},
        "max_founding_years": {"type": "integer"},
        "min_employee_count": {"type": "integer"},
        "max_employee_count": {"type": "integer"},
        "max_revenue": {"type": "number"},
        "target_industries": {"type": "array", "items": {"type": "string"}},
        "business_types": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["target_type", "category"],
}

SYSTEM = """당신은 정부지원사업 공고 분류 전문가입니다.
공고 제목·요약·부처를 보고 다음을 판정하세요:

1. target_type — 실제 신청 대상
   - business: 기업(법인/개인사업자)이 신청
   - individual: 개인(자연인, 청년/구직자/소상공인 개인 등)이 신청
   - 판단 기준: "교육생 모집"/"수강생"/"연수생"/"참가자 모집"/"청년 인재" → individual,
              "기업 모집"/"참여기업"/"중소기업" → business

2. category — 11개 중 정확히 1개

3. 자격 요건 JSON:
   - region_restriction: "전국" 또는 "서울"·"경기"·"부산" 등 시도명
   - min/max_founding_years: 업력 제약 (N년 이내/이상)
   - min/max_employee_count: 직원수 제약
   - max_revenue: 매출 상한 (원 단위)
   - target_industries: 업종 제한 키워드 배열 (예: ["AI","IT"])
   - business_types: 기업 유형 키워드 (예: ["중소기업","스타트업","예비창업자","청년"])"""


def infer_metadata(ann: dict) -> dict:
    prompt = f"""[공고 정보]
제목: {ann.get('title','')}
부처: {ann.get('department','')}
기존 카테고리: {ann.get('category') or '(없음)'}
기존 target_type: {ann.get('target_type') or '(없음)'}
요약: {(ann.get('summary_text') or '')[:1500]}

위 공고를 정확히 분류해주세요."""

    model = genai.GenerativeModel(
        "models/gemini-2.5-flash",
        system_instruction=SYSTEM,
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": SCHEMA,
            "temperature": 0.1,
            "max_output_tokens": 2048,
        },
    )
    resp = model.generate_content(prompt)
    return json.loads(resp.text or "{}")


def main(dry_run: bool = True):
    conn = get_db_connection()
    cur = conn.cursor()
    valid = valid_announcement_where()
    cur.execute(f"""
        SELECT announcement_id, title, department, category, target_type,
               summary_text, region
        FROM announcements
        WHERE {valid}
          AND (eligibility_logic IS NULL OR eligibility_logic::text IN ('null',''))
        ORDER BY announcement_id DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    print(f"대상: {len(rows)}건")

    success = 0
    failed = 0
    changed_target = 0

    for i, ann in enumerate(rows, 1):
        aid = ann["announcement_id"]
        try:
            meta = infer_metadata(ann)
        except Exception as e:
            print(f"  [{i}/{len(rows)}] #{aid} FAIL: {e}")
            failed += 1
            time.sleep(1)
            continue

        new_target = meta.get("target_type", "business")
        new_category = meta.get("category", "기타")
        # eligibility_logic JSON 구성
        elig_logic = {
            "region_restriction": meta.get("region_restriction") or "전국",
            "min_founding_years": meta.get("min_founding_years"),
            "max_founding_years": meta.get("max_founding_years"),
            "min_employee_count": meta.get("min_employee_count"),
            "max_employee_count": meta.get("max_employee_count"),
            "max_revenue": meta.get("max_revenue"),
            "target_industries": meta.get("target_industries", []),
            "business_types": meta.get("business_types", []),
            "required_certifications": [],
        }
        elig_json = json.dumps(elig_logic, ensure_ascii=False)

        old_target = ann.get("target_type") or "business"
        if new_target != old_target:
            changed_target += 1

        print(f"  [{i}/{len(rows)}] #{aid} {ann['title'][:40]}")
        print(f"      target: {old_target} → {new_target} | cat: {ann.get('category') or '(없음)'} → {new_category}")

        if not dry_run:
            try:
                cur.execute(
                    """UPDATE announcements
                       SET target_type = %s,
                           category = %s,
                           eligibility_logic = %s::jsonb
                       WHERE announcement_id = %s""",
                    (new_target, new_category, elig_json, aid),
                )
                conn.commit()
            except Exception as e:
                print(f"      DB UPDATE fail: {e}")
                conn.rollback()
                failed += 1
                continue

        success += 1
        time.sleep(0.3)  # rate limit

    print(f"\n=== 결과 ===")
    print(f"성공: {success} / 실패: {failed} / target_type 변경: {changed_target}")

    if dry_run:
        print("\n[DRY RUN] DB 변경 없음. 실제 적용: --apply")
    else:
        print("\n[APPLIED] DB 커밋 완료")

    conn.close()


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    main(dry_run=not apply)
