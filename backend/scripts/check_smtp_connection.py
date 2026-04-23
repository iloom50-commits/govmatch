"""SMTP 서버 연결/인증만 테스트 — 실제 이메일 발송 안 함.

로컬 .env의 SMTP 설정이 유효한지 확인.
프로덕션(Railway) 검증은 별도로 /api/admin/send-digest 호출 필요.
"""
import os, sys, smtplib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv()

host = os.getenv("SMTP_HOST", "smtp.gmail.com")
port = int(os.getenv("SMTP_PORT", "587"))
user = os.getenv("SMTP_USER", "")
password = os.getenv("SMTP_PASSWORD", "")
sender = os.getenv("SMTP_FROM", user)

print("=" * 60)
print("SMTP 설정 확인")
print("=" * 60)
print(f"  SMTP_HOST  : {host}")
print(f"  SMTP_PORT  : {port}")
print(f"  SMTP_USER  : {user}")
print(f"  SMTP_PASSWORD: {'***' if password else '(미설정)'}")
print(f"  SMTP_FROM  : {sender}")

if not user or not password:
    print("\n❌ SMTP_USER 또는 SMTP_PASSWORD 미설정 — 이메일 발송 불가")
    sys.exit(1)

print("\n" + "=" * 60)
print("연결 + 로그인 테스트 (실제 발송 안 함)")
print("=" * 60)
try:
    with smtplib.SMTP(host, port, timeout=15) as server:
        server.set_debuglevel(0)
        print("  ① 연결 OK")
        server.ehlo()
        print("  ② EHLO OK")
        server.starttls()
        print("  ③ STARTTLS OK")
        server.login(user, password)
        print("  ④ LOGIN OK")
        print("\n✅ SMTP 서버 연결 + 인증 성공")
        print(f"   → {user} 계정으로 이메일 발송 가능한 상태")
except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ 로그인 실패: {e}")
    print("   → Gmail일 경우 '앱 비밀번호' 사용 필요 (2단계 인증 계정)")
except Exception as e:
    print(f"\n❌ 연결/인증 실패: {type(e).__name__}: {e}")
