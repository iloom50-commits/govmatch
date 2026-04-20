#!/usr/bin/env python
"""[Phase 6 후속] 미분석 공고 Gemini 일괄 재분석 — 우선순위 배치.

환경변수 (.env): GEMINI_API_KEY 필요
실행:
  python run_gemini_batch.py [--mode priority|all] [--limit N]

기본: priority 모드 (금액 있고 summary 200자 이상 공고부터)
  - 예상 비용: 565건 약 $2, 12,872건 약 $30-40
  - 예상 시간: 우선순위 565건 약 60~90분

중간 중단 안전 — 다시 실행하면 미처리 공고부터 이어감.
"""

import sys
import os
import time
import argparse

# .env 로드
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
import psycopg2.extras
from app.config import DATABASE_URL
from app.services.doc_analysis_service import analyze_and_store


def fetch_batch(conn, mode: str, limit: int):
    """우선순위 기준으로 미분석 공고 선택."""
    cur = conn.cursor()
    if mode == "priority":
        # 금액 있고 summary 200자 이상 + 유효 공고
        cur.execute("""
            SELECT a.announcement_id, a.title, a.origin_url, a.summary_text
            FROM announcements a
            LEFT JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
            WHERE aa.id IS NULL
              AND a.is_archived = FALSE
              AND a.analysis_status IN ('pending', 'failed')
              AND a.support_amount IS NOT NULL AND a.support_amount != ''
              AND a.summary_text IS NOT NULL AND LENGTH(a.summary_text) >= 200
              AND a.analysis_attempts < 3
            ORDER BY
              CASE
                WHEN a.support_amount ILIKE '%%억%%' THEN 1
                WHEN a.support_amount ILIKE '%%천만%%' THEN 2
                WHEN a.support_amount ILIKE '%%백만%%' THEN 3
                WHEN a.support_amount ILIKE '%%만%%' THEN 4
                ELSE 5
              END,
              a.announcement_id DESC
            LIMIT %s
        """, (limit,))
    else:  # 'all'
        # summary 100자 이상 전체 미분석 유효 공고
        cur.execute("""
            SELECT a.announcement_id, a.title, a.origin_url, a.summary_text
            FROM announcements a
            LEFT JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
            WHERE aa.id IS NULL
              AND a.is_archived = FALSE
              AND a.analysis_status IN ('pending', 'failed')
              AND a.summary_text IS NOT NULL AND LENGTH(a.summary_text) >= 100
              AND a.analysis_attempts < 3
            ORDER BY a.announcement_id DESC
            LIMIT %s
        """, (limit,))
    return cur.fetchall()


def count_remaining(conn, mode: str) -> int:
    cur = conn.cursor()
    if mode == "priority":
        cur.execute("""
            SELECT COUNT(*) AS c
            FROM announcements a
            LEFT JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
            WHERE aa.id IS NULL AND a.is_archived = FALSE
              AND a.analysis_status IN ('pending', 'failed')
              AND a.support_amount IS NOT NULL AND a.support_amount != ''
              AND a.summary_text IS NOT NULL AND LENGTH(a.summary_text) >= 200
              AND a.analysis_attempts < 3
        """)
    else:
        cur.execute("""
            SELECT COUNT(*) AS c
            FROM announcements a
            LEFT JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
            WHERE aa.id IS NULL AND a.is_archived = FALSE
              AND a.analysis_status IN ('pending', 'failed')
              AND a.summary_text IS NOT NULL AND LENGTH(a.summary_text) >= 100
              AND a.analysis_attempts < 3
        """)
    return cur.fetchone()["c"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["priority", "all"], default="priority",
                        help="priority: 금액 있고 summary 200+ / all: summary 100+ 전체")
    parser.add_argument("--limit", type=int, default=50, help="한 배치에서 처리할 최대 건수")
    parser.add_argument("--max-time", type=int, default=0, help="최대 실행 시간(초), 0=무제한")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("[ERROR] GEMINI_API_KEY 환경변수 미설정 — .env 확인", flush=True)
        return 1

    start = time.time()
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

    total_target = count_remaining(conn, args.mode)
    print(f"[BATCH] mode={args.mode}, 시작 시점 남은 건수: {total_target}", flush=True)

    if total_target == 0:
        print("[BATCH] 처리할 공고 없음. 종료.", flush=True)
        conn.close()
        return 0

    ok = 0
    fail = 0
    processed_total = 0
    batch_no = 0

    while True:
        if args.max_time and (time.time() - start) > args.max_time:
            print(f"[BATCH] 최대 시간 {args.max_time}초 도달. 중단.", flush=True)
            break

        rows = fetch_batch(conn, args.mode, args.limit)
        if not rows:
            print("[BATCH] 더 이상 처리할 공고 없음. 완료.", flush=True)
            break

        batch_no += 1
        print(f"\n[BATCH #{batch_no}] {len(rows)}건 처리 시작...", flush=True)
        batch_start = time.time()

        for i, row in enumerate(rows, 1):
            r = dict(row)
            try:
                res = analyze_and_store(
                    announcement_id=r["announcement_id"],
                    origin_url=r.get("origin_url") or "",
                    title=r.get("title") or "",
                    db_conn=conn,
                    summary_text=r.get("summary_text") or "",
                )
                if res.get("success"):
                    ok += 1
                else:
                    fail += 1
            except Exception as e:
                fail += 1
                print(f"  [{i}/{len(rows)}] #{r['announcement_id']} ERROR: {str(e)[:150]}", flush=True)
            processed_total += 1

            # 진행 상황 로그 (10건마다)
            if processed_total % 10 == 0:
                elapsed = time.time() - start
                rate = processed_total / elapsed if elapsed > 0 else 0
                remaining_est = count_remaining(conn, args.mode)
                eta_min = (remaining_est / rate / 60) if rate > 0 else 0
                print(f"  진행: {processed_total} 처리 (ok={ok}, fail={fail}) | "
                      f"속도 {rate:.2f}/s | 남은 {remaining_est} | ETA {eta_min:.1f}분", flush=True)

        elapsed = time.time() - batch_start
        print(f"[BATCH #{batch_no}] 완료 ({elapsed:.1f}s) | 누적 ok={ok} fail={fail}", flush=True)

    conn.close()
    total_time = time.time() - start
    print(f"\n[결과] 총 처리 {processed_total}건 (ok={ok}, fail={fail}) / 소요 {total_time/60:.1f}분", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
