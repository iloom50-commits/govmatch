"""로컬 .env의 SMTP_PASSWORD 길이/마스킹만 출력 — 전체 값은 노출 안 함.

Railway 값과 대조하기 위한 안전한 비교.
"""
import os, sys, hashlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv()

pw = os.getenv("SMTP_PASSWORD", "")
if not pw:
    print("로컬 .env에 SMTP_PASSWORD 미설정")
    sys.exit(1)

masked = f"{pw[:4]}***{pw[-4:]}" if len(pw) >= 8 else "(too short)"
h = hashlib.sha256(pw.encode()).hexdigest()[:12]

print(f"로컬 SMTP_PASSWORD 길이: {len(pw)}자")
print(f"로컬 SMTP_PASSWORD 마스킹: {masked}")
print(f"로컬 SMTP_PASSWORD SHA256(앞12자): {h}")
