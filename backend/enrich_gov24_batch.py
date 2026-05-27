#!/usr/bin/env python
"""gov24 개인지원사업 상세 보강 — Railway admin 엔드포인트 반복 호출.

실행:
  python backend/enrich_gov24_batch.py [--batch 500] [--max-calls 30]

환경변수 (.env):
  ADMIN_PASSWORD, RAILWAY_API_URL
"""
import os, sys, time, argparse
import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.environ.get("RAILWAY_API_URL", "https://govmatch-production.up.railway.app")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
ENDPOINT = "/api/admin/enrich-gov24-individual"


def call_once(batch_size: int) -> dict:
    url = f"{API_BASE}{ENDPOINT}"
    try:
        resp = httpx.post(url, json={"password": ADMIN_PASSWORD, "batch_size": batch_size}, timeout=300)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        return resp.json()
    except Exception as e:
        return {"error": str(e)[:200]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=500, help="1회 처리 건수")
    parser.add_argument("--max-calls", type=int, default=30, help="최대 호출 횟수")
    args = parser.parse_args()

    if not ADMIN_PASSWORD:
        print("[ERROR] ADMIN_PASSWORD 미설정 — .env 확인")
        return 1

    print(f"[Enrich] {API_BASE}{ENDPOINT} batch={args.batch}, max_calls={args.max_calls}")
    total_updated = 0

    for call_n in range(1, args.max_calls + 1):
        print(f"\n[호출 #{call_n}]", flush=True)
        t0 = time.time()
        result = call_once(args.batch)
        elapsed = round(time.time() - t0, 1)

        if "error" in result:
            print(f"  에러: {result['error']}")
            time.sleep(10)
            continue

        r = result.get("result", {})
        updated = r.get("updated", 0)
        skipped = r.get("skipped", 0)
        errors  = r.get("errors", 0)
        total_updated += updated

        print(f"  [{elapsed}s] updated={updated} skipped={skipped} errors={errors} | 누적 updated={total_updated}")

        if updated == 0:
            print("  → 처리할 항목 없음. 완료.")
            break

        time.sleep(5)

    print(f"\n[완료] 총 보강 {total_updated}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
