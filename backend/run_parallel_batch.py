#!/usr/bin/env python
"""[병렬 배치] 4개 워커로 미분석 공고 동시 처리.

기존 단일 배치 대비 약 4배 속도.
안전장치:
  - FOR UPDATE SKIP LOCKED: 다른 워커가 처리 중인 공고 건너뜀 (중복 방지)
  - Per-item DB 커넥션: 장시간 커넥션 stale 문제 해결
  - analysis_attempts 증가로 같은 공고 무한 재시도 방지

실행:
  python run_parallel_batch.py [--workers 4] [--summary-min 100]

환경변수 (.env):
  - GEMINI_API_KEY: Gemini 2.5-flash (유료 1000 RPM)
"""

import os
import sys
import time
import signal
import argparse
import multiprocessing as mp
from datetime import datetime

# dotenv 먼저 로드
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

N_WORKERS_DEFAULT = 4
CHUNK_SIZE = 5          # 각 워커가 한 번에 가져올 공고 수
MAX_ATTEMPTS = 3        # 공고당 최대 시도 횟수


def worker_loop(worker_id: int, db_url: str, summary_min: int, stop_event, stats):
    """각 워커: 미분석 공고를 DB에서 가져와 analyze_and_store 수행."""
    import psycopg2
    import psycopg2.extras
    from app.services.doc_analysis_service import analyze_and_store

    print(f"[Worker {worker_id}] 시작", flush=True)

    while not stop_event.is_set():
        # 1) DB에서 SKIP LOCKED로 다음 배치 가져오기
        try:
            claim_conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            claim_cur = claim_conn.cursor()
            claim_cur.execute("""
                SELECT a.announcement_id, a.title, a.origin_url, a.summary_text
                FROM announcements a
                LEFT JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
                WHERE aa.id IS NULL
                  AND a.is_archived = FALSE
                  AND a.analysis_status IN ('pending', 'failed')
                  AND a.summary_text IS NOT NULL AND LENGTH(a.summary_text) >= %s
                  AND a.analysis_attempts < %s
                ORDER BY a.announcement_id DESC
                LIMIT %s
                FOR UPDATE OF a SKIP LOCKED
            """, (summary_min, MAX_ATTEMPTS, CHUNK_SIZE))
            rows = claim_cur.fetchall()

            if not rows:
                claim_conn.close()
                print(f"[Worker {worker_id}] 처리할 공고 없음 — 종료", flush=True)
                break

            # attempts 선제 증가 (다른 워커가 재획득 방지)
            ids = [r["announcement_id"] for r in rows]
            claim_cur.execute(
                "UPDATE announcements SET analysis_attempts = COALESCE(analysis_attempts, 0) + 1, last_analyzed_at = NOW() WHERE announcement_id = ANY(%s)",
                (ids,)
            )
            claim_conn.commit()
            claim_conn.close()
        except Exception as e:
            print(f"[Worker {worker_id}] claim error: {e}", flush=True)
            try: claim_conn.close()
            except Exception: pass
            time.sleep(5)
            continue

        # 2) 각 공고 처리 — 공고당 새 connection
        for r in rows:
            if stop_event.is_set():
                break
            ann_id = r["announcement_id"]
            try:
                item_conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
                res = analyze_and_store(
                    announcement_id=ann_id,
                    origin_url=r.get("origin_url") or "",
                    title=r.get("title") or "",
                    db_conn=item_conn,
                    summary_text=r.get("summary_text") or "",
                )
                item_conn.close()
                if res.get("success"):
                    with stats["success"].get_lock():
                        stats["success"].value += 1
                    status_str = "OK"
                else:
                    with stats["fail"].get_lock():
                        stats["fail"].value += 1
                    status_str = f"FAIL ({res.get('error', 'unknown')[:50]})"
                print(f"[Worker {worker_id}] #{ann_id}: {status_str}", flush=True)
            except Exception as e:
                with stats["fail"].get_lock():
                    stats["fail"].value += 1
                print(f"[Worker {worker_id}] #{ann_id} EXCEPTION: {str(e)[:150]}", flush=True)
                try: item_conn.close()
                except Exception: pass

    print(f"[Worker {worker_id}] 종료 (성공/실패는 메인에서 합산)", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=N_WORKERS_DEFAULT, help="병렬 워커 수 (기본 4)")
    parser.add_argument("--summary-min", type=int, default=100, help="summary_text 최소 길이 (기본 100)")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        from app.config import DATABASE_URL as db_url
    if not os.environ.get("GEMINI_API_KEY"):
        print("[ERROR] GEMINI_API_KEY 미설정")
        return 1

    # 시작 시점 남은 건수
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) AS cnt
        FROM announcements a
        LEFT JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
        WHERE aa.id IS NULL AND a.is_archived = FALSE
          AND a.analysis_status IN ('pending', 'failed')
          AND a.summary_text IS NOT NULL AND LENGTH(a.summary_text) >= %s
          AND a.analysis_attempts < %s
    """, (args.summary_min, MAX_ATTEMPTS))
    total_start = cur.fetchone()["cnt"]
    conn.close()
    print(f"[PARALLEL] workers={args.workers}, summary>={args.summary_min}, 대상 {total_start}건", flush=True)

    # 병렬 워커 시작
    stop_event = mp.Event()
    stats = {
        "success": mp.Value("i", 0),
        "fail": mp.Value("i", 0),
    }
    t0 = time.time()

    workers = []
    for i in range(args.workers):
        p = mp.Process(target=worker_loop, args=(i, db_url, args.summary_min, stop_event, stats))
        p.start()
        workers.append(p)

    # 종료 시그널
    def handler(sig, frame):
        print("\n[!] 중단 요청 감지 — 워커 정리 중...", flush=True)
        stop_event.set()
    signal.signal(signal.SIGINT, handler)
    try: signal.signal(signal.SIGTERM, handler)
    except Exception: pass

    # 진행 상황 모니터링
    try:
        while any(w.is_alive() for w in workers):
            time.sleep(30)
            elapsed = int(time.time() - t0)
            s = stats["success"].value
            f = stats["fail"].value
            rate = (s + f) / max(1, elapsed) * 60
            remain_est = max(0, total_start - s - f)
            eta_min = remain_est / max(rate, 0.01)
            print(f"[PROGRESS] elapsed={elapsed}s | ok={s} fail={f} | rate={rate:.1f}/min | remain~{remain_est} | ETA~{eta_min:.0f}min",
                  flush=True)
    except KeyboardInterrupt:
        stop_event.set()

    for w in workers:
        w.join(timeout=30)
        if w.is_alive():
            w.terminate()

    total_elapsed = time.time() - t0
    print(f"\n[DONE] 총 {int(total_elapsed/60)}분 {int(total_elapsed%60)}초 | "
          f"성공 {stats['success'].value} / 실패 {stats['fail'].value}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
