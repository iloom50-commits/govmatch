"""
[프로모션] 2026-04-22 ~ 2026-05-23 LITE 1개월 무료 개방

대상:
- free / trial / basic (legacy) → LITE로 승격, 만료 2026-05-23
- 기존 lite 유료 회원 → plan_expires_at 1개월 연장 (보상)
- pro 회원 → 건드리지 않음

일회성 실행 — 실행 전 DB 백업 권장.
"""
import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
load_dotenv()

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.main import get_db_connection

PROMO_END = "2026-05-23 23:59:59"  # 프로모션 일괄 만료일

def main(dry_run: bool = True):
    conn = get_db_connection()
    cur = conn.cursor()

    # 1) 사전 조사
    cur.execute("SELECT plan, COUNT(*) c FROM users GROUP BY plan ORDER BY c DESC")
    before = {r['plan']: r['c'] for r in cur.fetchall()}
    print("== BEFORE ==")
    for p, c in before.items():
        print(f"  {p}: {c}")

    # 2) [먼저] 기존 lite 유료 회원 → plan_expires_at +31일 연장 보상
    #    순서 중요: free→lite 승격 전에 해야 기존 48명만 대상이 됨
    cur.execute("""
        UPDATE users
        SET plan_expires_at = CASE
            WHEN plan_expires_at IS NULL OR plan_expires_at < NOW() THEN %s::timestamp
            ELSE plan_expires_at + INTERVAL '31 days'
        END
        WHERE plan = 'lite'
    """, (PROMO_END,))
    extended = cur.rowcount
    print(f"[Step A] 기존 lite 유료 회원 1개월 연장 보상: {extended}명")

    # 3) [그 다음] free/trial/basic → lite + 만료 5/23
    cur.execute("""
        UPDATE users
        SET plan = 'lite',
            plan_expires_at = %s
        WHERE plan IN ('free', 'trial', 'basic', 'premium')
           OR plan IS NULL
           OR plan = ''
    """, (PROMO_END,))
    promoted = cur.rowcount
    print(f"[Step B] free/trial/basic → lite 승격: {promoted}명")

    # 4) pro는 건드리지 않음 (이미 결제분 그대로 유지)
    cur.execute("SELECT COUNT(*) c FROM users WHERE plan = 'pro'")
    pro_count = cur.fetchone()['c']
    print(f"[Step C] pro 회원 (변경 없음): {pro_count}명")

    # 5) 사후 확인
    cur.execute("SELECT plan, COUNT(*) c FROM users GROUP BY plan ORDER BY c DESC")
    after = {r['plan']: r['c'] for r in cur.fetchall()}
    print("\n== AFTER ==")
    for p, c in after.items():
        print(f"  {p}: {c}")

    if dry_run:
        conn.rollback()
        print("\n[DRY RUN] 롤백됨. 실제 적용하려면 --apply 플래그 전달")
    else:
        conn.commit()
        print("\n[APPLIED] 커밋 완료.")

    conn.close()

if __name__ == "__main__":
    apply = "--apply" in sys.argv
    main(dry_run=not apply)
