"""users 테이블에 있지만 notification_settings에 없는 사용자 백필.

원칙:
- email 보유자만 (email 없으면 발송 불가)
- 기본값: channel='email', is_active=true, kakao_enabled=false
- ON CONFLICT DO NOTHING — 기존 설정 덮어쓰기 금지

사용법:
  python scripts/backfill_notification_settings.py          # dry-run
  python scripts/backfill_notification_settings.py --apply  # 실제 INSERT
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from app.main import get_db_connection

apply = "--apply" in sys.argv

conn = get_db_connection()
try:
    with conn.cursor() as cur:
        # 대상 조회 — 테스트 계정 제외 (bounce로 Resend 평판 하락 방지)
        cur.execute("""
            SELECT u.business_number, u.email, u.company_name, u.plan
            FROM users u
            LEFT JOIN notification_settings ns ON ns.business_number = u.business_number
            WHERE ns.id IS NULL
              AND u.email IS NOT NULL
              AND LENGTH(u.email) > 0
              AND u.email NOT LIKE '%@test.com'
              AND u.email NOT LIKE '%@example.com'
              AND u.email NOT LIKE '%@testverify%'
              AND u.email NOT LIKE 'test_%'
              AND u.email NOT LIKE 'testverify%'
              AND u.email NOT LIKE 'plan_%'
              AND u.email NOT LIKE 'pay_%'
              AND u.email NOT LIKE 'demo@%'
              AND u.email NOT LIKE 'fulltest%'
              AND u.email NOT LIKE 'pro_test%'
              AND u.email NOT LIKE '%@govmatch.kr'
              AND u.email NOT LIKE '%@govmatch.test'
              AND u.email NOT LIKE '%@valuefinder.%'
              AND u.email NOT LIKE '%,%'
              AND u.email NOT LIKE 'qctest_%'
              AND u.email NOT LIKE 'qcmulti_%'
              AND u.email NOT LIKE 'crawltest%'
              AND u.email NOT LIKE 'finaltest%'
              AND u.email NOT LIKE 'kakao-%'
              AND u.email ~ '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
              AND LENGTH(SPLIT_PART(u.email, '@', 2)) >= 6
              AND LENGTH(SPLIT_PART(u.email, '@', 1)) >= 4
              AND u.business_number NOT LIKE 'DEMO%'
              AND u.business_number NOT LIKE '123456%'
              AND u.business_number NOT LIKE '000000%'
              AND u.business_number NOT LIKE '111111%'
              AND u.business_number NOT LIKE '222222%'
              AND u.business_number NOT LIKE '333333%'
              AND u.business_number NOT LIKE '444444%'
              AND u.business_number NOT LIKE '777777%'
            ORDER BY u.user_id
        """)
        targets = cur.fetchall()

        print("=" * 70)
        print(f"{'DRY-RUN' if not apply else 'APPLY'}: 백필 대상 {len(targets)}명")
        print("=" * 70)
        for i, row in enumerate(targets[:20], 1):
            bn = row["business_number"]; email = row["email"]
            name = row["company_name"]; plan = row["plan"]
            print(f"  {i:3d}. {bn[:6]}*** {email[:30]:30s} {(name or '(미입력)')[:15]:15s} plan={plan or '-'}")
        if len(targets) > 20:
            print(f"  ... (나머지 {len(targets)-20}명 생략)")

        if not apply:
            print("\n[DRY-RUN] --apply 플래그로 실제 INSERT 실행")
            sys.exit(0)

        # 실제 INSERT
        inserted = 0
        failed = 0
        for row in targets:
            bn = row["business_number"]; email = row["email"]
            try:
                cur.execute("""
                    INSERT INTO notification_settings
                        (business_number, email, phone_number, channel, is_active, kakao_enabled)
                    VALUES (%s, %s, %s, 'email', true, false)
                    ON CONFLICT (business_number) DO NOTHING
                """, (bn, email, ''))
                if cur.rowcount > 0:
                    inserted += 1
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"  ❌ {bn}: {str(e)[:80]}")
                failed += 1

        print(f"\n✅ INSERT 성공: {inserted}건")
        if failed:
            print(f"❌ 실패: {failed}건")

        # 검증
        cur.execute("SELECT COUNT(*) AS c FROM notification_settings WHERE is_active = true")
        total = cur.fetchone()["c"]
        print(f"\n현재 활성 알림 설정 총 수: {total}명")
finally:
    conn.close()
