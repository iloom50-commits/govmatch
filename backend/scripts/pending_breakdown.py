"""pending 공고의 실제 분석 유무 구분 — 플래그 문제 vs 진짜 미분석."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv()
from app.main import get_db_connection, valid_announcement_where

conn = get_db_connection()
cur = conn.cursor()
valid = valid_announcement_where()

print("=" * 70)
print("pending 공고의 세부 분류 (유효 공고만)")
print("=" * 70)
cur.execute(f"""
    SELECT
      COUNT(*) AS pending_total,
      COUNT(*) FILTER (
        WHERE eligibility_logic IS NOT NULL
          AND eligibility_logic::text NOT IN ('null','{{}}','[]')
          AND summary_text IS NOT NULL AND summary_text <> ''
      ) AS has_content_flag_legacy,
      COUNT(*) FILTER (
        WHERE (eligibility_logic IS NULL OR eligibility_logic::text IN ('null','{{}}','[]'))
           OR summary_text IS NULL OR summary_text = ''
      ) AS truly_unanalyzed,
      COUNT(*) FILTER (WHERE ai_analyzed_at IS NOT NULL) AS has_analyzed_ts,
      COUNT(*) FILTER (WHERE ai_analyzed_at IS NULL) AS no_analyzed_ts
    FROM announcements
    WHERE {valid} AND analysis_status = 'pending'
""")
r = cur.fetchone()
total = r['pending_total']
print(f"  pending 총: {total}")
print(f"  ├─ 컨텐츠는 있는데 플래그만 pending (legacy): {r['has_content_flag_legacy']}  → 단순 플래그 갱신으로 해결")
print(f"  └─ 진짜 미분석 (컨텐츠 부족): {r['truly_unanalyzed']}  → 실제 Gemini 분석 필요")
print(f"")
print(f"  ai_analyzed_at 채움: {r['has_analyzed_ts']}")
print(f"  ai_analyzed_at 없음: {r['no_analyzed_ts']}")

print("\n" + "=" * 70)
print("진짜 미분석 공고 샘플 10건")
print("=" * 70)
cur.execute(f"""
    SELECT announcement_id, title, department, origin_source, created_at
    FROM announcements
    WHERE {valid}
      AND analysis_status = 'pending'
      AND (eligibility_logic IS NULL OR eligibility_logic::text IN ('null','{{}}','[]')
           OR summary_text IS NULL OR summary_text = '')
    ORDER BY created_at DESC
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  #{row['announcement_id']:>6}: [{(row['origin_source'] or '-')[:20]:<20}] {row['title'][:60]}")
    print(f"         기관: {row['department']} / 수집: {row['created_at']}")

conn.close()
