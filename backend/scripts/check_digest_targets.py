"""실제 digest 대상자 수 — get_target_users 쿼리 그대로 실행."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv()
from app.main import get_db_connection

conn = get_db_connection()
cur = conn.cursor()

print("=" * 70)
print("① 실제 get_target_users 쿼리 결과")
print("=" * 70)
cur.execute("""
    SELECT DISTINCT u.business_number, u.email, u.plan, u.company_name,
           ns.email AS notify_email, ns.is_active AS notify_active,
           ps.id IS NOT NULL AS has_push
    FROM users u
    LEFT JOIN notification_settings ns ON u.business_number = ns.business_number
    LEFT JOIN push_subscriptions ps ON u.business_number = ps.business_number
    WHERE ((ns.is_active = 1 AND ns.email IS NOT NULL AND ns.email != '')
       OR ps.id IS NOT NULL)
      AND u.plan IN ('lite', 'lite_trial', 'basic', 'pro', 'biz')
      AND (u.plan_expires_at IS NULL OR u.plan_expires_at > NOW())
""")
rows = cur.fetchall()
print(f"  대상자 수: {len(rows)}명\n")
for r in rows:
    ch = []
    if r['notify_active']: ch.append("email")
    if r['has_push']: ch.append("push")
    print(f"  [{r['plan']}] {r['company_name'] or '?':<20} {r['email'] or '-':<30} ch={','.join(ch)}")

print("\n" + "=" * 70)
print("② notification_settings 전체 — 왜 12건만 있는가")
print("=" * 70)
cur.execute("""
    SELECT ns.business_number, ns.email, ns.channel, ns.is_active,
           u.email AS user_email, u.plan
    FROM notification_settings ns
    LEFT JOIN users u ON u.business_number = ns.business_number
    ORDER BY ns.is_active DESC
""")
for r in cur.fetchall():
    print(f"  BN={r['business_number']:<15} email={r['email']:<30} ch={r['channel']} active={r['is_active']} user={r['user_email']}")

print("\n" + "=" * 70)
print("③ push_subscriptions 등록 현황")
print("=" * 70)
cur.execute("""
    SELECT ps.id, ps.business_number, u.email, u.plan
    FROM push_subscriptions ps
    LEFT JOIN users u ON u.business_number = ps.business_number
    ORDER BY ps.id DESC LIMIT 20
""")
for r in cur.fetchall():
    print(f"  id={r['id']} BN={r['business_number']} plan={r['plan']} email={r['email']}")

print("\n" + "=" * 70)
print("④ LITE+ 유저 중 notification_settings도 push도 없는 '조용한' 유저")
print("=" * 70)
cur.execute("""
    SELECT COUNT(*) AS silent
    FROM users u
    LEFT JOIN notification_settings ns ON u.business_number = ns.business_number
    LEFT JOIN push_subscriptions ps ON u.business_number = ps.business_number
    WHERE u.plan IN ('lite', 'lite_trial', 'basic', 'pro', 'biz')
      AND (u.plan_expires_at IS NULL OR u.plan_expires_at > NOW())
      AND ns.id IS NULL
      AND ps.id IS NULL
""")
print(f"  설정 없음(조용한) 유저: {cur.fetchone()['silent']}명")

conn.close()
