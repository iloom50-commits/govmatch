# -*- coding: utf-8 -*-
"""기존 announcements 데이터 품질 일괄 수정.

실행:
    python backend/scripts/fix_data_quality.py

수행 내용:
  1. region 비표준값 → 표준 광역시도명으로 UPDATE
  2. category 비표준값 → CATEGORY_NORMALIZE 기준 UPDATE
  3. category NULL + 유효공고 → 제목 키워드로 추론 UPDATE
  4. target_type NULL → ai_classify_pending 대량 실행 (최대 300건)
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\Users\osung\.gemini\antigravity\scratch\Auto_Gov_Macting\backend')

from app.config import DATABASE_URL
from app.services.rule_engine import (
    REGION_NORMALIZE,
    _CITY_TO_SIDO,
    _STANDARD_REGIONS,
    normalize_region_for_save,
    _CATEGORY_NORMALIZE,
    VALID_CATEGORIES,
    normalize_category,
    infer_category_from_title,
)
import psycopg2
import psycopg2.extras

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# ─────────────────────────────────────────────
# 1. region 비표준값 수정
# ─────────────────────────────────────────────
print("\n[1/4] region 비표준값 수정...")

cur.execute("""
    SELECT DISTINCT region FROM announcements
    WHERE (deadline_date >= CURRENT_DATE OR deadline_date IS NULL)
      AND region IS NOT NULL AND region != ''
""")
all_regions = [r["region"] for r in cur.fetchall()]

region_updates = {}
for raw in all_regions:
    normalized = normalize_region_for_save(raw)
    if normalized and normalized != raw:
        region_updates[raw] = normalized

total_region = 0
for raw, normalized in region_updates.items():
    cur.execute(
        "UPDATE announcements SET region = %s WHERE region = %s",
        (normalized, raw),
    )
    cnt = cur.rowcount
    total_region += cnt
    print(f"  '{raw}' → '{normalized}': {cnt}건")

conn.commit()
print(f"  ✅ region 수정 완료: 총 {total_region}건")

# ─────────────────────────────────────────────
# 2. category 비표준값 수정
# ─────────────────────────────────────────────
print("\n[2/4] category 비표준값 수정...")

cur.execute("""
    SELECT DISTINCT category FROM announcements
    WHERE (deadline_date >= CURRENT_DATE OR deadline_date IS NULL)
      AND category IS NOT NULL AND category != ''
""")
all_cats = [r["category"] for r in cur.fetchall()]

cat_updates = {}
for raw in all_cats:
    normalized = normalize_category(raw)
    if normalized and normalized != raw:
        cat_updates[raw] = normalized

total_cat = 0
for raw, normalized in cat_updates.items():
    cur.execute(
        "UPDATE announcements SET category = %s WHERE category = %s",
        (normalized, raw),
    )
    cnt = cur.rowcount
    total_cat += cnt
    print(f"  '{raw}' → '{normalized}': {cnt}건")

conn.commit()
print(f"  ✅ category 비표준값 수정 완료: 총 {total_cat}건")

# ─────────────────────────────────────────────
# 3. category NULL → 제목 키워드로 추론
# ─────────────────────────────────────────────
print("\n[3/4] category NULL 공고 제목 기반 추론...")

cur.execute("""
    SELECT announcement_id, title FROM announcements
    WHERE (deadline_date >= CURRENT_DATE OR deadline_date IS NULL)
      AND (category IS NULL OR category = '')
    ORDER BY announcement_id
""")
null_cat_rows = cur.fetchall()

inferred_count = 0
skipped_count = 0
for row in null_cat_rows:
    inferred = infer_category_from_title(row["title"])
    if inferred:
        cur.execute(
            "UPDATE announcements SET category = %s WHERE announcement_id = %s",
            (inferred, row["announcement_id"]),
        )
        inferred_count += 1
    else:
        skipped_count += 1

conn.commit()
print(f"  ✅ category 추론 완료: {inferred_count}건 / 미추론(키워드 없음): {skipped_count}건")

# ─────────────────────────────────────────────
# 4. target_type NULL → AI 분류 (최대 300건)
# ─────────────────────────────────────────────
print("\n[4/4] target_type NULL → AI 분류 (최대 300건)...")
try:
    from app.services.patrol.target_type_classifier import ai_classify_pending
    result = ai_classify_pending(conn, batch_size=300)
    print(f"  ✅ AI 분류 완료: {result}")
except Exception as e:
    print(f"  ⚠️  AI 분류 오류: {e}")
    print("     (GEMINI_API_KEY 환경변수 필요 — Railway에서 실행하거나 .env 설정 후 재시도)")

# ─────────────────────────────────────────────
# 최종 요약
# ─────────────────────────────────────────────
print("\n[결과 요약]")
cur.execute("""
    SELECT
        COUNT(*) total,
        SUM(CASE WHEN region IS NULL OR region = '' THEN 1 ELSE 0 END) no_region,
        SUM(CASE WHEN target_type IS NULL OR target_type = '' THEN 1 ELSE 0 END) no_target,
        SUM(CASE WHEN category IS NULL OR category = '' THEN 1 ELSE 0 END) no_cat
    FROM announcements
    WHERE deadline_date >= CURRENT_DATE OR deadline_date IS NULL
""")
r = cur.fetchone()
print(f"  전체 유효공고: {r['total']}건")
print(f"  region NULL:      {r['no_region']}건")
print(f"  target_type NULL: {r['no_target']}건")
print(f"  category NULL:    {r['no_cat']}건")

conn.close()
