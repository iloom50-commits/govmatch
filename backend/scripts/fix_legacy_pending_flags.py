"""레거시 플래그 정리 — 컨텐츠 있는데 analysis_status='pending'인 공고를 'analyzed'로 전환.

안전 장치:
  - 첫 실행: dry-run (건수만 카운트, 변경 없음)
  - --apply 플래그 명시 시만 실제 UPDATE
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv()
from app.main import get_db_connection

APPLY = "--apply" in sys.argv
mode = "APPLY (실제 UPDATE)" if APPLY else "DRY-RUN (변경 없음)"
print(f"모드: {mode}\n")

conn = get_db_connection()
cur = conn.cursor()

# 공통 조건: pending + 컨텐츠 있음 + 최소 품질 (summary >= 100자)
where_legacy = """
    analysis_status = 'pending'
    AND eligibility_logic IS NOT NULL
    AND eligibility_logic::text NOT IN ('null','{}','[]')
    AND summary_text IS NOT NULL
    AND LENGTH(summary_text) >= 100
"""

# 1) 영향 건수 사전 확인
cur.execute(f"SELECT COUNT(*) c FROM announcements WHERE {where_legacy}")
n = cur.fetchone()['c']
print(f"대상 건수 (summary ≥ 100자): {n}건")

# 1-b) 요약 길이 분포 — pending 전체 중
cur.execute("""
    SELECT
      COUNT(*) FILTER (WHERE LENGTH(summary_text) < 50)  AS lt50,
      COUNT(*) FILTER (WHERE LENGTH(summary_text) >= 50 AND LENGTH(summary_text) < 100) AS b50_100,
      COUNT(*) FILTER (WHERE LENGTH(summary_text) >= 100 AND LENGTH(summary_text) < 300) AS b100_300,
      COUNT(*) FILTER (WHERE LENGTH(summary_text) >= 300 AND LENGTH(summary_text) < 1000) AS b300_1000,
      COUNT(*) FILTER (WHERE LENGTH(summary_text) >= 1000) AS gte1000
    FROM announcements
    WHERE analysis_status = 'pending'
      AND summary_text IS NOT NULL
      AND eligibility_logic IS NOT NULL
      AND eligibility_logic::text NOT IN ('null','{}','[]')
""")
r = cur.fetchone()
print(f"\npending 전체 요약 길이 분포 (참고):")
print(f"  < 50자    : {r['lt50']:>6}  ← 부실 (제외)")
print(f"  50~100자  : {r['b50_100']:>6}  ← 경계 (제외)")
print(f"  100~300자 : {r['b100_300']:>6}  ← 전환 대상")
print(f"  300~1000자: {r['b300_1000']:>6}  ← 전환 대상")
print(f"  ≥ 1000자  : {r['gte1000']:>6}  ← 전환 대상")

# 2) 샘플 5건
cur.execute(f"""
    SELECT announcement_id, title, analysis_status,
           LENGTH(summary_text) AS s_len,
           eligibility_logic::text <> 'null' AS has_elig
    FROM announcements WHERE {where_legacy}
    ORDER BY announcement_id DESC LIMIT 5
""")
print("\n샘플 (최근 5건):")
for r in cur.fetchall():
    print(f"  #{r['announcement_id']}: status={r['analysis_status']} summary={r['s_len']}자 elig={r['has_elig']}")
    print(f"      {r['title'][:80]}")

if not APPLY:
    print("\n→ DRY-RUN 종료. 실제 변경하려면: python scripts/fix_legacy_pending_flags.py --apply")
    conn.close()
    sys.exit(0)

# 3) 실제 UPDATE
print(f"\n{n}건 UPDATE 실행 중...")
cur.execute(f"""
    UPDATE announcements
    SET analysis_status = 'analyzed'
    WHERE {where_legacy}
""")
affected = cur.rowcount
conn.commit()
print(f"✓ {affected}건 'analyzed'로 갱신 완료")

# 4) 갱신 후 분포 재확인
cur.execute("""
    SELECT COALESCE(analysis_status,'(null)') s, COUNT(*) c
    FROM announcements
    GROUP BY s ORDER BY c DESC
""")
print("\n갱신 후 분포:")
for r in cur.fetchall():
    print(f"  {r['s']:<15} {r['c']:>6}")

conn.close()
print("\n완료.")
