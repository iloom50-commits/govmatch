"""자동 수집 시스템 작동 확인"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from app.main import get_db_connection

conn = get_db_connection()
cur = conn.cursor()

print("=== admin_urls 현황 ===")
cur.execute("SELECT COUNT(*) c FROM admin_urls")
print(f"전체: {cur.fetchone()['c']}")
cur.execute("SELECT COUNT(*) c FROM admin_urls WHERE is_active = 1")
print(f"활성: {cur.fetchone()['c']}")

# 컬럼 조사
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='admin_urls'")
cols = [r['column_name'] for r in cur.fetchall()]
print(f"컬럼: {cols}")

# 샘플 20건
print("\n--- 등록된 admin_urls 샘플 ---")
cur.execute("SELECT * FROM admin_urls LIMIT 20")
for r in cur.fetchall():
    print(dict(r))

# 최근 공고 수집 동향
print("\n=== 최근 14일 일별 신규 공고 ===")
cur.execute("""
SELECT DATE(created_at) d, COUNT(*) c, COUNT(DISTINCT origin_source) sources
FROM announcements
WHERE created_at > NOW() - INTERVAL '14 days'
GROUP BY d ORDER BY d DESC
""")
for r in cur.fetchall():
    print(f"  {r['d']}: {r['c']:>4}건 / {r['sources']}소스")

# 최근 7일 origin_source별
print("\n=== 최근 7일 origin_source별 ===")
cur.execute("""
SELECT COALESCE(origin_source, '(none)') s, COUNT(*) c
FROM announcements
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY s ORDER BY c DESC
""")
for r in cur.fetchall():
    print(f"  {r['s']:<40} {r['c']:>4}")

conn.close()
