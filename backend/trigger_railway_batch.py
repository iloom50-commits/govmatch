#!/usr/bin/env python
"""[Railway 배치 트리거] /api/admin/analyze-batch-priority를 반복 호출.

- Railway 프로덕션 워커가 250초씩 처리 → 자동으로 반복 호출
- DB 연결 끊김 문제 없음 (Railway 커넥션풀)
- 'done: true' 응답 시 종료

실행:
  python trigger_railway_batch.py

환경변수 (.env):
  ADMIN_PASSWORD — 프로덕션과 동일해야 함
"""
import os
import sys
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.environ.get("RAILWAY_API_URL", "https://govmatch-production.up.railway.app")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin1234")
INTERVAL_SEC = 15  # 호출 간 간격

# priority(금액+summary200+) 완료 후 broad(summary50+)로 전환
ENDPOINTS = [
    ("priority", "/api/admin/analyze-batch-priority"),
    ("broad",    "/api/admin/analyze-batch-broad"),
]
current_ep_idx = 0


def trigger_once() -> dict:
    global current_ep_idx
    if current_ep_idx >= len(ENDPOINTS):
        return {"all_done": True}
    name, path = ENDPOINTS[current_ep_idx]
    url = f"{API_BASE}{path}"
    try:
        resp = httpx.post(url, json={"password": ADMIN_PASSWORD}, timeout=300)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}", "endpoint": name}
        data = resp.json()
        data["_endpoint"] = name
        return data
    except Exception as e:
        return {"error": str(e)[:200], "endpoint": name}


def main():
    print(f"[Railway batch] start — target {API_BASE}")
    total_success = 0
    total_failed = 0
    call_n = 0

    global current_ep_idx
    while current_ep_idx < len(ENDPOINTS):
        call_n += 1
        ep_name = ENDPOINTS[current_ep_idx][0]
        print(f"\n[호출 #{call_n}] endpoint={ep_name} ...", flush=True)
        t0 = time.time()
        result = trigger_once()
        elapsed = round(time.time() - t0, 1)

        if result.get("all_done"):
            break

        if "error" in result:
            print(f"  에러 ({result.get('endpoint')}): {result['error']}", flush=True)
            time.sleep(INTERVAL_SEC)
            continue

        processed = result.get("processed", 0)
        success = result.get("success", 0)
        failed = result.get("failed", 0)
        remaining = result.get("remaining_after", result.get("remaining", -1))
        done = result.get("done", False)

        total_success += success
        total_failed += failed
        print(f"  [{elapsed}s] 처리 {processed} / 성공 {success} / 실패 {failed} / 남음 {remaining}", flush=True)
        print(f"  [누적] 성공 {total_success} / 실패 {total_failed}", flush=True)

        if done:
            print(f"  ✓ {ep_name} 완료 — 다음 엔드포인트로 전환", flush=True)
            current_ep_idx += 1
            continue

        if processed == 0:
            print(f"  처리량 0 — 대기 후 재시도", flush=True)
            time.sleep(INTERVAL_SEC * 4)
        else:
            time.sleep(INTERVAL_SEC)

    print(f"\n[완료] 모든 엔드포인트 처리 끝. 총 성공 {total_success}, 실패 {total_failed}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
