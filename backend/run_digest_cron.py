"""Railway Cron 전용 — 맞춤 공고 이메일 발송 트리거.

Railway Cron 서비스 설정:
  Schedule: 0 0 * * 1-5  (평일 UTC 00:00 = KST 09:00)
  Command:  python run_digest_cron.py

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

print(f"[Cron] Triggering daily digest: {API_URL}/api/internal/run-digest")

try:
    resp = requests.post(
        f"{API_URL}/api/internal/run-digest",
        headers={"X-Cron-Secret": CRON_SECRET},
        timeout=300,  # 발송 완료까지 최대 5분 대기
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"[Cron] 완료: users={data.get('users')}, email={data.get('email_sent')}, push={data.get('push_sent')}, prematch={data.get('prematch')}")
        if data.get("errors"):
            print(f"[Cron] 오류: {data['errors']}")
    else:
        print(f"[Cron] 실패: HTTP {resp.status_code} — {resp.text[:200]}")
        sys.exit(1)
except Exception as e:
    print(f"[Cron] 예외: {e}")
    sys.exit(1)
