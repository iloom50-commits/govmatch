"""공고 분석 진행 상태 확인 — 전수 분석이 완료됐는지 점검."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from app.main import get_db_connection, valid_announcement_where

conn = get_db_connection()
cur = conn.cursor()

print("=" * 70)
print("① analysis_status 분포 (전체)")
print("=" * 70)
cur.execute("""
    SELECT COALESCE(analysis_status,'(null)') s, COUNT(*) c
    FROM announcements
    GROUP BY s ORDER BY c DESC
""")
for r in cur.fetchall():
    print(f"  {r['s']:<25} {r['c']:>6}")

print("\n" + "=" * 70)
print("② analysis_status 분포 (유효 공고만 — 만료/아카이브 제외)")
print("=" * 70)
valid = valid_announcement_where()
cur.execute(f"""
    SELECT COALESCE(analysis_status,'(null)') s, COUNT(*) c
    FROM announcements
    WHERE {valid}
    GROUP BY s ORDER BY c DESC
""")
for r in cur.fetchall():
    print(f"  {r['s']:<25} {r['c']:>6}")

print("\n" + "=" * 70)
print("③ eligibility_logic / summary_text 유무 (유효 공고만)")
print("=" * 70)
cur.execute(f"""
    SELECT
      COUNT(*) AS total,
      COUNT(*) FILTER (WHERE eligibility_logic IS NOT NULL
                          AND eligibility_logic::text != 'null'
                          AND eligibility_logic::text != '{{}}'
                          AND eligibility_logic::text != '[]') AS has_eligibility,
      COUNT(*) FILTER (WHERE summary_text IS NOT NULL AND summary_text <> '') AS has_summary
    FROM announcements
    WHERE {valid}
""")
r = cur.fetchone()
print(f"  유효 총      : {r['total']}")
print(f"  eligibility_logic 채움: {r['has_eligibility']}  (부족 {r['total'] - r['has_eligibility']})")
print(f"  summary_text 채움      : {r['has_summary']}")

print("\n" + "=" * 70)
print("④ 최근 24h analysis_status 변화 — 재분석이 활성인지")
print("=" * 70)
cur.execute("""
    SELECT COALESCE(analysis_status,'(null)') s, COUNT(*) c
    FROM announcements
    WHERE analyzed_at IS NOT NULL
      AND analyzed_at > NOW() - INTERVAL '24 hours'
    GROUP BY s
""")
rows = cur.fetchall()
if not rows:
    print("  (최근 24시간 내 분석 업데이트 없음)")
else:
    for r in rows:
        print(f"  {r['s']:<25} {r['c']:>6}")

print("\n" + "=" * 70)
print("⑤ pending/failed 공고 중 최근 생성된 것 (분석 대기)")
print("=" * 70)
cur.execute("""
    SELECT analysis_status, COUNT(*) c,
           MIN(created_at) AS oldest, MAX(created_at) AS newest
    FROM announcements
    WHERE analysis_status IN ('pending','failed','in_progress')
    GROUP BY analysis_status
""")
for r in cur.fetchall():
    old = r['oldest'].strftime('%Y-%m-%d') if r['oldest'] else '-'
    new = r['newest'].strftime('%Y-%m-%d') if r['newest'] else '-'
    print(f"  {r['analysis_status']:<15} {r['c']:>6}  | 가장 오래 {old} / 가장 최근 {new}")

conn.close()
