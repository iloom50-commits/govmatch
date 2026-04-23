"""API별 실제 수집량 진단 — 최근 7일 일자별 × origin_source 집계.

사장님 질문: "어제 각 API가 몇 건씩 가져왔는지" 팩트 확인.
read-only. DB 수정 없음.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from app.main import get_db_connection

conn = get_db_connection()
cur = conn.cursor()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ① 최근 7일 일자별 × origin_source 신규 저장 건수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("=" * 80)
print("① 최근 7일 일자별 × origin_source 신규 저장 건수")
print("=" * 80)
cur.execute("""
    SELECT DATE(created_at) AS d,
           COALESCE(NULLIF(origin_source,''),'(empty)') AS src,
           COUNT(*) AS c
    FROM announcements
    WHERE created_at > NOW() - INTERVAL '7 days'
    GROUP BY DATE(created_at), src
    ORDER BY DATE(created_at) DESC, c DESC
""")
rows = cur.fetchall()

# 일자별로 그룹핑
from collections import defaultdict
by_day = defaultdict(list)
for r in rows:
    by_day[str(r['d'])].append((r['src'], r['c']))

if not by_day:
    print("  (최근 7일간 신규 저장 없음)")
else:
    for day in sorted(by_day.keys(), reverse=True):
        total = sum(c for _, c in by_day[day])
        print(f"\n📅 {day} (총 {total}건)")
        for src, c in by_day[day]:
            print(f"    {src:<50} {c:>6}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ② API별 최근 마지막 저장 시점 (죽은 API 식별)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n" + "=" * 80)
print("② origin_source별 최근 마지막 저장 시점 + 총 누적")
print("=" * 80)
cur.execute("""
    SELECT COALESCE(NULLIF(origin_source,''),'(empty)') AS src,
           COUNT(*) AS total,
           MAX(created_at) AS last_at
    FROM announcements
    GROUP BY src
    ORDER BY MAX(created_at) DESC NULLS LAST
""")
for r in cur.fetchall():
    last = r['last_at'].strftime('%Y-%m-%d %H:%M') if r['last_at'] else '(없음)'
    print(f"  {r['src']:<50} 총 {r['total']:>6}건  |  마지막: {last}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ③ scraper_runs 테이블 최근 실행 결과 (Tier 1 + admin_scraper)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n" + "=" * 80)
print("③ scraper_runs 최근 3일 실행 결과")
print("=" * 80)
try:
    cur.execute("""
        SELECT source,
               COUNT(*) AS runs,
               SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) AS ok,
               SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS err,
               SUM(CASE WHEN status='empty' THEN 1 ELSE 0 END) AS empty_,
               SUM(items_saved) AS saved,
               MAX(started_at) AS last_run
        FROM scraper_runs
        WHERE started_at > NOW() - INTERVAL '3 days'
        GROUP BY source
        ORDER BY MAX(started_at) DESC
    """)
    scraper_rows = cur.fetchall()
    if not scraper_rows:
        print("  (최근 3일간 scraper_runs 기록 없음)")
    else:
        for r in scraper_rows:
            last = r['last_run'].strftime('%Y-%m-%d %H:%M') if r['last_run'] else '(없음)'
            print(f"  {r['source']:<30} 실행 {r['runs']}회 (ok {r['ok']}/err {r['err']}/empty {r['empty_']}) "
                  f"저장 {r['saved'] or 0}건 | 마지막 {last}")
except Exception as e:
    print(f"  scraper_runs 조회 실패: {e}")
    try: conn.rollback()
    except: pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ④ origin_source 비어있는 건수 (분류 누락)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n" + "=" * 80)
print("④ 분류 누락 현황")
print("=" * 80)
cur.execute("""
    SELECT
      COUNT(*) FILTER (WHERE origin_source IS NULL OR origin_source='') AS no_source,
      COUNT(*) FILTER (WHERE department IS NULL OR department='' OR department='기타') AS no_dept,
      COUNT(*) FILTER (WHERE region IS NULL OR region='') AS no_region,
      COUNT(*) AS total
    FROM announcements
""")
r = cur.fetchone()
print(f"  origin_source 빈값     : {r['no_source']:>6} / {r['total']}")
print(f"  department 빈값/기타   : {r['no_dept']:>6} / {r['total']}")
print(f"  region 빈값            : {r['no_region']:>6} / {r['total']}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⑤ 최근 24시간 시간대별 저장 (수집 스케줄 작동 확인)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n" + "=" * 80)
print("⑤ 최근 24시간 시간대별 저장 (스케줄 03:00 KST 작동 확인)")
print("=" * 80)
cur.execute("""
    SELECT DATE_TRUNC('hour', created_at) AS h, COUNT(*) AS c
    FROM announcements
    WHERE created_at > NOW() - INTERVAL '24 hours'
    GROUP BY DATE_TRUNC('hour', created_at)
    ORDER BY h DESC
""")
hours = cur.fetchall()
if not hours:
    print("  (최근 24시간 저장 없음 — 스케줄러 정지 가능성)")
else:
    for r in hours:
        print(f"  {r['h'].strftime('%Y-%m-%d %H:%M')}  {r['c']}건")

conn.close()
print("\n진단 완료.")
