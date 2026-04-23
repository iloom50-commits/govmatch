"""Phase 1: DB 수집 현황 분석"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from app.main import get_db_connection, valid_announcement_where

conn = get_db_connection()
cur = conn.cursor()
valid = valid_announcement_where()

cur.execute("SELECT COUNT(*) c FROM announcements")
total = cur.fetchone()['c']
cur.execute(f"SELECT COUNT(*) c FROM announcements WHERE {valid}")
valid_cnt = cur.fetchone()['c']
print(f"전체: {total} / 유효: {valid_cnt}")

print("\n=== origin_source 상위 20 ===")
cur.execute("SELECT COALESCE(origin_source,'(empty)') s, COUNT(*) c FROM announcements GROUP BY s ORDER BY c DESC LIMIT 20")
for r in cur.fetchall():
    print(f"  {r['s']:<40} {r['c']:>6}")

print("\n=== department 상위 50 ===")
cur.execute("SELECT COALESCE(department,'(empty)') d, COUNT(*) c FROM announcements GROUP BY d ORDER BY c DESC LIMIT 50")
for r in cur.fetchall():
    print(f"  {r['d']:<45} {r['c']:>6}")

print("\n=== region 분포 ===")
cur.execute("SELECT COALESCE(NULLIF(region,''),'(empty)') rg, COUNT(*) c FROM announcements GROUP BY rg ORDER BY c DESC LIMIT 20")
for r in cur.fetchall():
    print(f"  {r['rg']:<15} {r['c']:>6}")

print("\n=== 주관기관 미표기 비율 ===")
cur.execute("SELECT COUNT(*) FROM announcements WHERE department IS NULL OR department = ''")
print(f"  department 비어있음: {cur.fetchone()[0]}")

conn.close()
