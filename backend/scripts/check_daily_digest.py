"""맞춤 알림(daily digest) 작동 점검 — 최근 7일 발송 이력.

평일 09시 KST에 자동 발송되어야 함. notification_logs 테이블 조회.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv()
from app.main import get_db_connection

conn = get_db_connection()
cur = conn.cursor()

print("=" * 75)
print("① notification_logs 테이블 스키마 확인")
print("=" * 75)
try:
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'notification_logs'
        ORDER BY ordinal_position
    """)
    cols = cur.fetchall()
    if not cols:
        print("  테이블 없음")
    else:
        for c in cols:
            print(f"  {c['column_name']:<25} {c['data_type']}")
except Exception as e:
    print(f"  조회 실패: {e}")

print("\n" + "=" * 75)
print("② 최근 14일 일자별 발송 건수")
print("=" * 75)
try:
    cur.execute("""
        SELECT DATE(sent_at) AS d,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE status = 'sent') AS sent,
               COUNT(*) FILTER (WHERE status = 'failed') AS failed,
               COUNT(DISTINCT COALESCE(recipient, business_number::text)) AS uniq_recipients
        FROM notification_logs
        WHERE sent_at > NOW() - INTERVAL '14 days'
        GROUP BY DATE(sent_at)
        ORDER BY DATE(sent_at) DESC
    """)
    rows = cur.fetchall()
    if not rows:
        print("  (최근 14일 발송 기록 없음)")
    else:
        print(f"  {'날짜':<12} {'총':>6} {'성공':>6} {'실패':>6} {'수신자':>8}")
        for r in rows:
            print(f"  {str(r['d']):<12} {r['total']:>6} {r['sent']:>6} {r['failed']:>6} {r['uniq_recipients']:>8}")
except Exception as e:
    print(f"  조회 실패: {e}")
    try: conn.rollback()
    except: pass

print("\n" + "=" * 75)
print("③ 최근 30일 채널별 분포")
print("=" * 75)
try:
    cur.execute("""
        SELECT COALESCE(channel, '(unknown)') AS ch,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE status = 'sent') AS sent,
               MAX(sent_at) AS last_sent
        FROM notification_logs
        WHERE sent_at > NOW() - INTERVAL '30 days'
        GROUP BY channel
        ORDER BY total DESC
    """)
    rows = cur.fetchall()
    if not rows:
        print("  (최근 30일 기록 없음)")
    else:
        for r in rows:
            last = r['last_sent'].strftime('%Y-%m-%d %H:%M') if r['last_sent'] else '-'
            print(f"  {r['ch']:<15} 총 {r['total']:>6} (성공 {r['sent']:>5}) | 마지막 {last}")
except Exception as e:
    print(f"  조회 실패: {e}")
    try: conn.rollback()
    except: pass

print("\n" + "=" * 75)
print("④ 알림 수신자 총 수 (users + notification_settings)")
print("=" * 75)
try:
    cur.execute("""
        SELECT
          COUNT(*) AS total_users,
          COUNT(*) FILTER (WHERE email IS NOT NULL AND email <> '') AS has_email,
          COUNT(*) FILTER (WHERE plan IN ('lite','lite_trial','pro','basic')) AS paid_or_lite
        FROM users
    """)
    r = cur.fetchone()
    print(f"  전체 사용자: {r['total_users']}")
    print(f"  이메일 보유: {r['has_email']}")
    print(f"  lite+ 플랜 (디지스트 대상): {r['paid_or_lite']}")
except Exception as e:
    print(f"  조회 실패: {e}")
    try: conn.rollback()
    except: pass

try:
    cur.execute("""
        SELECT
          COUNT(*) AS rows,
          COUNT(*) FILTER (WHERE is_active::text IN ('1','true','True')) AS active
        FROM notification_settings
    """)
    r = cur.fetchone()
    print(f"  notification_settings 행 수: {r['rows']}")
    print(f"  활성 설정: {r['active']}")
except Exception as e:
    print(f"  notification_settings 조회 실패: {e}")
    try: conn.rollback()
    except: pass

print("\n" + "=" * 75)
print("⑤ 최근 발송 샘플 5건")
print("=" * 75)
try:
    cur.execute("""
        SELECT sent_at, status, channel, recipient, company_name, notification_type
        FROM notification_logs
        ORDER BY sent_at DESC LIMIT 8
    """)
    for r in cur.fetchall():
        print(f"  [{r['sent_at']}] {r['status']} ch={r['channel']} type={r['notification_type']} → {r['recipient']} ({r['company_name']})")
except Exception as e:
    print(f"  조회 실패: {e}")

conn.close()
print("\n완료.")
