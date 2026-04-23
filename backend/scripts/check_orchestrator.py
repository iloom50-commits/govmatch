"""오케스트레이터 작동 현황 점검 — 추측 없이 팩트만."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv()
from app.main import get_db_connection

conn = get_db_connection()
cur = conn.cursor()

print("=" * 70)
print("① orchestrator_reviews 테이블 — 품질 리뷰 기록")
print("=" * 70)
try:
    cur.execute("SELECT COUNT(*) c, MAX(created_at) last_at FROM orchestrator_reviews")
    r = cur.fetchone()
    print(f"  총 리뷰 {r['c']}건, 마지막: {r['last_at']}")
    cur.execute("""
        SELECT created_at, agent_type, score_accuracy, score_completeness,
               LEFT(feedback, 80) AS fb
        FROM orchestrator_reviews
        ORDER BY created_at DESC LIMIT 5
    """)
    for row in cur.fetchall():
        print(f"    [{row['created_at']}] {row['agent_type']} acc={row['score_accuracy']} comp={row['score_completeness']}")
        print(f"      {row['fb']}")
except Exception as e:
    print(f"  조회 실패: {e}")
    try: conn.rollback()
    except: pass

print("\n" + "=" * 70)
print("② system_logs — 오케스트레이터/스케줄러 관련")
print("=" * 70)
try:
    cur.execute("""
        SELECT created_at, action, category, status, LEFT(message,120) AS msg
        FROM system_logs
        WHERE (action ILIKE '%orchestrator%' OR action ILIKE '%supervisor%'
               OR action ILIKE '%scheduler%' OR action ILIKE '%pipeline%'
               OR action ILIKE '%sync%' OR action ILIKE '%manual_sync%')
          AND created_at > NOW() - INTERVAL '7 days'
        ORDER BY created_at DESC LIMIT 15
    """)
    rows = cur.fetchall()
    if not rows:
        print("  (최근 7일 관련 로그 없음)")
    else:
        for r in rows:
            print(f"  [{r['created_at']}] {r['action']}/{r['category']} {r['status']}")
            print(f"    {r['msg']}")
except Exception as e:
    print(f"  조회 실패: {e}")
    try: conn.rollback()
    except: pass

print("\n" + "=" * 70)
print("③ 최근 24h analysis_status 변화 — 분석 복구가 진행 중인가")
print("=" * 70)
try:
    cur.execute("""
        SELECT COALESCE(analysis_status,'(null)') s, COUNT(*) c
        FROM announcements
        WHERE ai_analyzed_at > NOW() - INTERVAL '24 hours'
        GROUP BY s ORDER BY c DESC
    """)
    rows = cur.fetchall()
    if not rows:
        print("  (최근 24h 분석 업데이트 없음)")
    else:
        for r in rows:
            print(f"  {r['s']:<20} {r['c']:>6}")
except Exception as e:
    print(f"  조회 실패: {e}")

conn.close()
print("\n완료.")
