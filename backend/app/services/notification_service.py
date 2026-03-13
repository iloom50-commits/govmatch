import google.generativeai as genai
import os
import json
import psycopg2
import psycopg2.extras
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
from dotenv import load_dotenv
from app.config import DATABASE_URL

load_dotenv()


class NotificationService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
        else:
            self.model = None

        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from = os.getenv("SMTP_FROM", self.smtp_user)

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_user and self.smtp_password)

    async def get_target_users(self):
        """푸시 구독이 있거나 이메일 알림이 활성화된 사용자만 조회"""
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT u.*, ns.email AS notify_email, ns.channel, ns.is_active AS notify_active
            FROM users u
            LEFT JOIN notification_settings ns ON u.business_number = ns.business_number
            LEFT JOIN push_subscriptions ps ON u.business_number = ps.business_number
            WHERE (ns.is_active = 1 AND ns.email IS NOT NULL AND ns.email != '')
               OR ps.id IS NOT NULL
        """)
        users = cursor.fetchall()
        conn.close()
        return users

    async def get_filtered_programs(self, user):
        """사용자 프로필 기반 DB 레벨 1차 필터링"""
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cursor = conn.cursor()

        user_loc = user['address_city'] if user['address_city'] else '전국'

        user_years = 0
        if user['establishment_date']:
            try:
                est_date = datetime.datetime.strptime(str(user['establishment_date'])[:10], "%Y-%m-%d")
                today = datetime.datetime.now()
                user_years = (today - est_date).days // 365
            except Exception:
                pass

        interests = [k.strip() for k in user['interests'].split(',') if k.strip()] if user['interests'] else []

        params = [f"%{user_loc}%", user_years]

        keyword_clause = ""
        if interests:
            placeholders = []
            for kw in interests:
                placeholders.append("(title LIKE %s OR summary_text LIKE %s)")
                params.append(f"%{kw}%")
                params.append(f"%{kw}%")
            keyword_clause = f"AND ({' OR '.join(placeholders)})"

        query = f"""
            SELECT * FROM announcements
            WHERE (region LIKE %s OR region IN ('전국', 'All', '온라인', '해외', '기타'))
            {keyword_clause}
            AND (established_years_limit IS NULL OR established_years_limit >= %s)
            AND (deadline_date >= CURRENT_DATE OR deadline_date IS NULL OR deadline_date::text = '')
            ORDER BY created_at DESC
            LIMIT 10
        """

        cursor.execute(query, params)
        programs = cursor.fetchall()
        conn.close()
        return programs

    async def match_program_with_user(self, program, user):
        """AI를 사용하여 공고와 사용자 프로필 매칭 및 사유 생성"""
        user_data = dict(user) if not isinstance(user, dict) else user

        if not self.model:
            return {"score": 0, "reasoning": "AI 모델 미설정"}

        prompt = f"""
        당신은 기업 지원사업 전문 컨설턴트입니다.
        아래의 기업 프로필과 지원사업 공고를 분석하여 매칭 점수와 구체적인 추천 사유를 작성해 주세요.

        [기업 프로필]
        - 기업명: {user_data.get('company_name', '알 수 없음')}
        - 지역: {user_data.get('address_city', '전국')}
        - 주요분야: {user_data.get('industry_code', '미지정')}
        - 관심사: {user_data.get('interests', '없음')}

        [지원사업 공고]
        - 제목: {program['title']}
        - 요약: {program['summary_text'] if program['summary_text'] else '요약 정보 없음'}

        결과는 반드시 아래 JSON 형식으로만 답변해 주세요:
        {{
            "score": (0~100 사이의 정수),
            "reasoning": "(사용자에게 직접 말하는 듯한 친절한 말투의 추천 사유, 2~3문장)"
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            result = json.loads(response.text.replace('```json', '').replace('```', '').strip())
            return result
        except Exception as e:
            print(f"Error in AI Matching: {e}")
            return {"score": 0, "reasoning": "분석 중 오류가 발생했습니다."}

    def _build_email_html(self, company_name: str, matches: List[Dict]) -> str:
        """매칭 결과를 HTML 이메일 본문으로 변환"""
        today_str = datetime.date.today().strftime("%Y년 %m월 %d일")

        rows = ""
        for m in matches:
            rows += f"""
            <tr>
              <td style="padding:12px 16px; border-bottom:1px solid #eee;">
                <a href="{m['url']}" style="color:#2563eb; font-weight:600; text-decoration:none;">
                  {m['program_title']}
                </a>
              </td>
              <td style="padding:12px 16px; border-bottom:1px solid #eee; text-align:center;">
                <span style="background:#dbeafe; color:#1e40af; padding:4px 12px; border-radius:20px; font-weight:700;">
                  {m['score']}점
                </span>
              </td>
            </tr>
            <tr>
              <td colspan="2" style="padding:8px 16px 16px; color:#64748b; font-size:13px; border-bottom:2px solid #f1f5f9;">
                {m['reasoning']}
              </td>
            </tr>"""

        return f"""
        <div style="max-width:600px; margin:0 auto; font-family:'Pretendard',sans-serif;">
          <div style="background:linear-gradient(135deg,#1e3a5f,#2563eb); padding:32px; border-radius:16px 16px 0 0;">
            <h1 style="color:white; margin:0; font-size:22px;">AI 매칭 비서 데일리 리포트</h1>
            <p style="color:#93c5fd; margin:8px 0 0; font-size:14px;">{today_str} | {company_name}</p>
          </div>
          <div style="background:white; padding:24px; border:1px solid #e2e8f0; border-top:none;">
            <p style="color:#334155; font-size:15px; margin-bottom:20px;">
              오늘 <strong>{company_name}</strong>에 맞춤 추천된 지원사업 <strong>{len(matches)}건</strong>을 안내드립니다.
            </p>
            <table style="width:100%; border-collapse:collapse;">
              <thead>
                <tr style="background:#f8fafc;">
                  <th style="padding:12px 16px; text-align:left; color:#64748b; font-size:13px;">지원사업</th>
                  <th style="padding:12px 16px; text-align:center; color:#64748b; font-size:13px; width:80px;">점수</th>
                </tr>
              </thead>
              <tbody>{rows}</tbody>
            </table>
          </div>
          <div style="background:#f8fafc; padding:20px; border-radius:0 0 16px 16px; border:1px solid #e2e8f0; border-top:none; text-align:center;">
            <p style="color:#94a3b8; font-size:11px; margin:0;">AI 매칭 비서 | 자동 발송 알림</p>
          </div>
        </div>"""

    def send_email(self, to_email: str, company_name: str, matches: List[Dict]) -> bool:
        """SMTP를 통해 매칭 결과 이메일 발송"""
        if not self.smtp_configured:
            print(f"  SMTP 미설정 -> 이메일 발송 건너뜀 (to: {to_email})")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[AI 매칭 비서] {company_name} 맞춤 지원사업 {len(matches)}건 안내"
        msg["From"] = self.smtp_from
        msg["To"] = to_email

        html_body = self._build_email_html(company_name, matches)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            print(f"  Email sent to {to_email}")
            self._log_notification(to_email, company_name, "email", "sent")
            return True
        except Exception as e:
            print(f"  Email send error ({to_email}): {e}")
            self._log_notification(to_email, company_name, "email", f"error: {e}")
            return False

    def send_push(self, business_number: str, company_name: str, matches: List[Dict]) -> int:
        """해당 사업자의 웹 푸시 구독 전부에 알림 발송, 발송 수 리턴"""
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            print("  pywebpush 미설치 -> 푸시 발송 건너뜀")
            return 0

        vapid_private = os.getenv("VAPID_PRIVATE_KEY", "")
        vapid_claims_email = os.getenv("VAPID_CLAIMS_EMAIL", "")
        if not vapid_private or not vapid_claims_email:
            return 0

        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cursor = conn.cursor()
        cursor.execute("SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE business_number = %s", (business_number,))
        subs = cursor.fetchall()
        conn.close()

        if not subs:
            return 0

        top = matches[0] if matches else {}
        payload = json.dumps({
            "title": f"[AI 매칭] {company_name} 맞춤 공고 {len(matches)}건",
            "body": top.get("program_title", "새로운 지원사업이 매칭되었습니다."),
            "url": top.get("url", "/"),
        }, ensure_ascii=False)

        sent = 0
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub["endpoint"],
                        "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                    },
                    data=payload,
                    vapid_private_key=vapid_private,
                    vapid_claims={"sub": vapid_claims_email},
                )
                sent += 1
            except WebPushException as e:
                if "410" in str(e) or "404" in str(e):
                    conn2 = psycopg2.connect(DATABASE_URL)
                    cur2 = conn2.cursor()
                    cur2.execute("DELETE FROM push_subscriptions WHERE endpoint = %s", (sub["endpoint"],))
                    conn2.commit()
                    conn2.close()
                print(f"  Push error ({sub['endpoint'][:40]}...): {e}")
            except Exception as e:
                print(f"  Push error: {e}")

        if sent:
            self._log_notification(business_number, company_name, "push", f"sent:{sent}")
        return sent

    def _log_notification(self, recipient: str, company_name: str, channel: str, status: str):
        """알림 발송 이력 저장"""
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_logs (
                    id SERIAL PRIMARY KEY,
                    recipient TEXT,
                    company_name TEXT,
                    channel TEXT,
                    status TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute(
                "INSERT INTO notification_logs (recipient, company_name, channel, status) VALUES (%s, %s, %s, %s)",
                (recipient, company_name, channel, status)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"  Log error: {e}")

    async def generate_daily_digest(self):
        """데일리 다이제스트 생성 + 이메일 발송"""
        users = await self.get_target_users()

        digest_results = []
        for user in users:
            programs = await self.get_filtered_programs(user)

            matches = []
            for program in programs:
                match_result = await self.match_program_with_user(program, user)

                threshold = 80
                try:
                    if user['matching_threshold']:
                        threshold = int(user['matching_threshold'])
                except (KeyError, TypeError, ValueError):
                    pass

                if match_result['score'] >= threshold:
                    matches.append({
                        "program_title": program['title'],
                        "score": match_result['score'],
                        "reasoning": match_result['reasoning'],
                        "url": program['origin_url'] if program['origin_url'] else '#'
                    })

            if matches:
                user_dict = dict(user)
                company_name = user_dict.get('company_name', '기업')
                email = user_dict.get('notify_email') or user_dict.get('email')
                bn = user_dict.get('business_number', '')

                entry = {
                    "user_email": email,
                    "company_name": company_name,
                    "matches": matches,
                    "email_sent": False,
                    "push_sent": 0,
                }

                if email:
                    entry["email_sent"] = self.send_email(email, company_name, matches)

                entry["push_sent"] = self.send_push(bn, company_name, matches)

                digest_results.append(entry)

        return digest_results


notification_service = NotificationService()
