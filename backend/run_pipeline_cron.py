"""Railway Cron 전용 — 일일 통합 파이프라인 트리거.

Railway Cron 서비스 설정:
  Schedule: 0 18 * * *  (매일 UTC 18:00 = KST 03:00)
  Command:  python run_pipeline_cron.py

환경변수:
  GOVMATCH_API_URL  : 백엔드 URL (예: https://govmatch-production.up.railway.app)
  CRON_SECRET       : 인증 시크릿 (백엔드와 동일한 값)
"""
import os
import sys
import requests

API_URL = os.environ.get("GOVMATCH_API_URL", "").rstrip("/")
CRON_SECRET = os.environ.get("CRON_SECRET", "")

if not API_URL:
    print("[ERROR] GOVMATCH_API_URL 환경변수가 설정되지 않았습니다.")
    sys.exit(1)

if not CRON_SECRET:
    print("[ERROR] CRON_SECRET 환경변수가 설정되지 않았습니다.")
    sys.exit(1)

print(f"[Cron] Triggering daily pipeline: {API_URL}/api/internal/run-pipeline")

try:
    resp = requests.post(
        f"{API_URL}/api/internal/run-pipeline",
        headers={"X-Cron-Secret": CRON_SECRET},
        timeout=30,  # 파이프라인은 백그라운드 실행 — 시작 확인만
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"[Cron] 완료: {data.get('message')}")
    else:
        print(f"[Cron] 실패: HTTP {resp.status_code} — {resp.text[:200]}")
        sys.exit(1)
except Exception as e:
    print(f"[Cron] 예외: {e}")
    sys.exit(1)