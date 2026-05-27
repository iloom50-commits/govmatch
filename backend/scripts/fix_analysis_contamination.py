# -*- coding: utf-8 -*-
"""
announcement_analysis 오염 데이터 정리 스크립트

오염 패턴: full_text / parsed_sections / deep_analysis 컬럼에
"유아학비" 또는 "유치원 교육비" 텍스트가 포함된 행
→ 해당 컬럼만 NULL로 초기화 (행 자체는 보존)
→ 연관 blog_context_cache도 함께 삭제

실행:
    python backend/scripts/fix_analysis_contamination.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\Users\osung\.gemini\antigravity\scratch\Auto_Gov_Macting\backend')

from app.config import DATABASE_URL
import psycopg2
import psycopg2.extras
import json

KEYWORDS = ["유아학비", "유치원 교육비"]

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# ─────────────────────────────────────────────
# 1. 오염된 행 탐색
# ─────────────────────────────────────────────
print("\n[1/3] 오염 행 탐색 중...")

like_clauses = []
params = []
for kw in KEYWORDS:
    like_clauses.append(
        "(full_text ILIKE %s"
        " OR parsed_sections::text ILIKE %s"
        " OR deep_analysis::text ILIKE %s)"
    )
    params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])

where = " OR ".join(like_clauses)
cur.execute(
    f"""SELECT aa.id, aa.announcement_id, a.title,
               LEFT(aa.full_text, 80) AS full_text_preview,
               aa.full_text IS NOT NULL AS has_full_text,
               aa.parsed_sections IS NOT NULL AS has_parsed,
               aa.deep_analysis IS NOT NULL AS has_deep
        FROM announcement_analysis aa
        LEFT JOIN announcements a ON a.announcement_id = aa.announcement_id
        WHERE {where}
        ORDER BY aa.announcement_id""",
    params,
)
rows = cur.fetchall()

if not rows:
    print("  → 오염 행 없음. 종료.")
    conn.close()
    sys.exit(0)

print(f"  → 오염 행 {len(rows)}건 발견:")
contaminated_ann_ids = []
for r in rows:
    print(f"     aa.id={r['id']} ann_id={r['announcement_id']} "
          f"title='{(r['title'] or '')[:40]}' "
          f"full_text={'Y' if r['has_full_text'] else 'N'} "
          f"parsed={'Y' if r['has_parsed'] else 'N'} "
          f"deep={'Y' if r['has_deep'] else 'N'}")
    print(f"       full_text preview: {(r['full_text_preview'] or '').strip()[:60]}")
    contaminated_ann_ids.append(r['announcement_id'])

# ─────────────────────────────────────────────
# 2. 오염 컬럼 NULL 초기화
# ─────────────────────────────────────────────
print(f"\n[2/3] 오염 컬럼 NULL 초기화 ({len(rows)}행)...")

cur.execute(
    f"""UPDATE announcement_analysis
        SET full_text     = NULL,
            parsed_sections = NULL,
            deep_analysis = NULL,
            updated_at    = CURRENT_TIMESTAMP
        WHERE {where}""",
    params,
)
updated = cur.rowcount
print(f"  → {updated}행 초기화 완료")

# ─────────────────────────────────────────────
# 3. 연관 blog_context_cache 삭제
# ─────────────────────────────────────────────
print(f"\n[3/3] 연관 blog_context_cache 삭제...")
if contaminated_ann_ids:
    cur.execute(
        "DELETE FROM blog_context_cache WHERE announcement_id = ANY(%s)",
        (contaminated_ann_ids,),
    )
    cache_deleted = cur.rowcount
    print(f"  → blog_context_cache {cache_deleted}건 삭제")
else:
    print("  → 삭제할 캐시 없음")

conn.commit()

# ─────────────────────────────────────────────
# 4. 결과 검증
# ─────────────────────────────────────────────
print("\n[결과 검증]")
cur.execute(
    f"""SELECT COUNT(*) AS cnt FROM announcement_analysis WHERE {where}""",
    params,
)
remaining = (cur.fetchone() or {}).get("cnt", 0)
print(f"  남은 오염 행: {remaining}건")

cur.execute(
    "SELECT COUNT(*) AS cnt FROM blog_context_cache WHERE announcement_id = ANY(%s)",
    (contaminated_ann_ids,),
)
remaining_cache = (cur.fetchone() or {}).get("cnt", 0)
print(f"  남은 오염 캐시: {remaining_cache}건")

if remaining == 0 and remaining_cache == 0:
    print("\n  ✅ 정리 완료")
else:
    print("\n  ⚠️  잔여 오염 데이터 있음 — 수동 확인 필요")

conn.close()
