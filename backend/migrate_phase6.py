#!/usr/bin/env python
"""[Phase 6] 기존 공고 데이터 일괄 마이그레이션.

휴리스틱만으로 처리 가능한 부분을 먼저 채움 (Gemini 비용 없음):
1. 기존 support_amount 문자열 → support_amount_type/max/min 역추출
2. 기존 deadline_date가 있는 공고 → deadline_type 결정 (future→fixed, past→expired)
3. 제목/summary에 '상시' 키워드 + deadline_date NULL → deadline_type='ongoing'
4. 제목 과거 연도 + deadline_date NULL → is_archived=TRUE + deadline_type='expired'
5. announcement_analysis에 데이터 있는 공고 → analysis_status='analyzed'

실행: python migrate_phase6.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
import psycopg2.extras
from app.config import DATABASE_URL
from app.services.amount_parser import parse_support_amount


def main():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    print("=" * 60)
    print("[Phase 6] 기존 17,463건 일괄 마이그레이션 시작")
    print("=" * 60)

    # ─── 1. 기존 support_amount 문자열 → 정규화 값 채우기 ────────
    print("\n[1/5] support_amount 문자열 → 정규화 값 역추출...")
    cur.execute("""
        SELECT announcement_id, support_amount
        FROM announcements
        WHERE support_amount IS NOT NULL
          AND support_amount != ''
          AND support_amount_max IS NULL
    """)
    rows = cur.fetchall()
    print(f"  대상: {len(rows)}건")
    updated = 0
    for r in rows:
        t, mx, mn = parse_support_amount(r["support_amount"])
        try:
            cur.execute(
                """UPDATE announcements
                   SET support_amount_type = %s, support_amount_max = %s, support_amount_min = %s
                   WHERE announcement_id = %s""",
                (t, mx, mn, r["announcement_id"])
            )
            updated += 1
            if updated % 500 == 0:
                conn.commit()
                print(f"    ... {updated}건 처리")
        except Exception as e:
            print(f"  [amount] #{r['announcement_id']} 에러: {e}")
            conn.rollback()
    conn.commit()
    print(f"  완료: {updated}건 정규화")

    # ─── 2. 빈 support_amount → 'unknown' 재확인 ────────
    cur.execute("""
        UPDATE announcements
        SET support_amount_type = 'unknown'
        WHERE (support_amount IS NULL OR support_amount = '')
          AND support_amount_type IS NULL
    """)
    conn.commit()

    # ─── 3. deadline_date 있는 공고 → deadline_type 결정 ────────
    print("\n[2/5] deadline_date 있는 공고 → deadline_type 결정...")
    # 미래 마감일 → fixed
    cur.execute("""
        UPDATE announcements
        SET deadline_type = 'fixed'
        WHERE deadline_date IS NOT NULL
          AND deadline_date >= CURRENT_DATE
          AND deadline_type = 'unknown'
    """)
    fixed_cnt = cur.rowcount
    # 과거 마감일 → expired
    cur.execute("""
        UPDATE announcements
        SET deadline_type = 'expired'
        WHERE deadline_date IS NOT NULL
          AND deadline_date < CURRENT_DATE
          AND deadline_type = 'unknown'
    """)
    expired_cnt = cur.rowcount
    conn.commit()
    print(f"  → fixed: {fixed_cnt}건, expired: {expired_cnt}건")

    # ─── 4. '상시' 키워드 감지 → ongoing ────────
    print("\n[3/5] '상시/연중/수시' 키워드 감지 → deadline_type='ongoing'...")
    cur.execute("""
        UPDATE announcements
        SET deadline_type = 'ongoing'
        WHERE deadline_type = 'unknown'
          AND deadline_date IS NULL
          AND (
            title ~ '(상시|연중|수시|마감일 ?없음|마감 ?없음)'
            OR summary_text ~ '(상시 ?모집|연중 ?모집|수시 ?모집)'
          )
    """)
    ongoing_cnt = cur.rowcount
    conn.commit()
    print(f"  → ongoing: {ongoing_cnt}건")

    # ─── 5. 과거 연도 제목 + deadline NULL → expired + archived ────────
    print("\n[4/5] 제목 과거 연도 + deadline 불명 → 자동 만료 아카이브...")
    cur.execute(r"""
        UPDATE announcements
        SET deadline_type = 'expired',
            is_archived = TRUE
        WHERE deadline_type = 'unknown'
          AND title ~ '^\d{4}년'
          AND SUBSTRING(title FROM '^(\d{4})년')::int < EXTRACT(YEAR FROM CURRENT_DATE)::int
    """)
    past_year_cnt = cur.rowcount
    conn.commit()
    print(f"  → 아카이브: {past_year_cnt}건")

    # ─── 6. announcement_analysis에 데이터 있는 공고 → analyzed ────────
    print("\n[5/5] announcement_analysis 데이터 있는 공고 → analysis_status='analyzed'...")
    cur.execute("""
        UPDATE announcements a
        SET analysis_status = 'analyzed'
        WHERE a.analysis_status = 'pending'
          AND EXISTS (
            SELECT 1 FROM announcement_analysis aa
            WHERE aa.announcement_id = a.announcement_id
          )
    """)
    analyzed_cnt = cur.rowcount
    conn.commit()
    print(f"  → analyzed: {analyzed_cnt}건")

    # ─── 최종 현황 ────────
    print("\n" + "=" * 60)
    print("[최종 현황]")
    cur.execute("SELECT deadline_type, COUNT(*) AS c FROM announcements GROUP BY deadline_type ORDER BY c DESC")
    for r in cur.fetchall(): print(f"  deadline_type = {r['deadline_type']:10s}: {r['c']:5d}")
    print()
    cur.execute("SELECT analysis_status, COUNT(*) AS c FROM announcements GROUP BY analysis_status ORDER BY c DESC")
    for r in cur.fetchall(): print(f"  analysis_status = {r['analysis_status']:10s}: {r['c']:5d}")
    print()
    cur.execute("SELECT support_amount_type, COUNT(*) AS c FROM announcements GROUP BY support_amount_type ORDER BY c DESC")
    for r in cur.fetchall(): print(f"  support_amount_type = {r['support_amount_type']:10s}: {r['c']:5d}")
    print()
    cur.execute("SELECT is_archived, COUNT(*) AS c FROM announcements GROUP BY is_archived")
    for r in cur.fetchall(): print(f"  is_archived = {str(r['is_archived']):5s}: {r['c']:5d}")

    # 유효 공고 (새 필터 기준)
    cur.execute("""
        SELECT COUNT(*) AS c FROM announcements
        WHERE is_archived = FALSE AND (
          deadline_type = 'ongoing'
          OR (deadline_type = 'fixed' AND deadline_date >= CURRENT_DATE)
          OR (deadline_type = 'unknown' AND created_at >= CURRENT_DATE - INTERVAL '3 months')
        )
    """)
    valid = cur.fetchone()["c"]
    print(f"\n[유효 공고 (새 필터 통과)]: {valid}건")

    conn.close()
    print("=" * 60)
    print("[Phase 6] 마이그레이션 완료")


if __name__ == "__main__":
    main()
