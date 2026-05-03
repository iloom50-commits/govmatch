import google.generativeai as genai
import os
import json
import psycopg2
import psycopg2.extras
import datetime
import httpx
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv
from app.config import DATABASE_URL

load_dotenv()


class NotificationService:
    """
    이메일 발송: Resend HTTP API (https://resend.com)
    Railway는 outbound SMTP 포트(25/587/465)를 차단하므로 SMTP 직접 발송 불가.
    Resend는 HTTPS로 통신하므로 Railway에서도 정상 작동.
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            self.model = None

        # Resend 설정
        self.resend_api_key = os.getenv("RESEND_API_KEY", "")
        # 도메인 검증 전엔 onboarding@resend.dev 기본값. 검증 후 RESEND_FROM 지정.
        self.resend_from = os.getenv("RESEND_FROM", "onboarding@resend.dev")

    @property
    def email_configured(self) -> bool:
        return bool(self.resend_api_key)

    async def get_target_users(self):
        """이메일 알림 동의한 전체 사용자 조회 (플랜 무관)"""
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT u.*, ns.email AS notify_email, ns.channel, ns.is_active AS notify_active
            FROM users u
            LEFT JOIN notification_settings ns ON u.business_number = ns.business_number
            LEFT JOIN push_subscriptions ps ON u.business_number = ps.business_number
            WHERE ((ns.is_active = 1 AND ns.email IS NOT NULL AND ns.email != '')
               OR ps.id IS NOT NULL)
        """)
        users = cursor.fetchall()
        conn.close()
        return users

    async def get_filtered_programs(self, user):
        """사용자 프로필 기반 1차 필터링 — 제외 조건 우선 적용"""
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cursor = conn.cursor()

        user_dict = dict(user)
        user_loc = user_dict.get('address_city') or '전국'
        user_type = user_dict.get('user_type') or 'business'

        # 창업연수 계산
        user_years = 0
        est_val = user_dict.get('establishment_date')
        if est_val:
            try:
                if isinstance(est_val, (datetime.date, datetime.datetime)):
                    est_date = datetime.datetime(est_val.year, est_val.month, est_val.day)
                else:
                    est_date = datetime.datetime.strptime(str(est_val)[:10], "%Y-%m-%d")
                user_years = (datetime.datetime.now() - est_date).days // 365
            except Exception:
                pass

        # target_type 조건: 기업 사용자는 business/both, 개인은 individual/both
        if user_type == 'individual':
            target_type_clause = "AND target_type IN ('individual', 'both')"
        else:
            target_type_clause = "AND target_type IN ('business', 'both')"

        # 지역 조건: 전국/All/온라인이거나 사용자 지역 포함
        params = [f"%{user_loc}%", user_years]

        query = f"""
            SELECT * FROM announcements
            WHERE (
                region IN ('전국', 'All', '온라인', '해외', '기타', '')
                OR region LIKE %s
            )
            {target_type_clause}
            AND (established_years_limit IS NULL OR established_years_limit >= %s)
            AND (deadline_date IS NULL OR deadline_date >= CURRENT_DATE)
            ORDER BY
                CASE WHEN support_amount IS NOT NULL AND support_amount != '' THEN 0 ELSE 1 END,
                CASE WHEN deadline_date IS NOT NULL THEN 0 ELSE 1 END,
                deadline_date ASC NULLS LAST,
                created_at DESC
            LIMIT 100
        """

        try:
            cursor.execute(query, params)
            programs = cursor.fetchall()
        except Exception as e:
            print(f"  [get_filtered_programs] SQL error for {user_dict.get('email','?')}: {e}")
            programs = []
        finally:
            conn.close()
        return programs

    def _check_exclusions(self, program, user_data: dict) -> str | None:
        """제외 조건 체크 — 해당하면 이유 반환, 통과하면 None"""
        import json as _json

        title = program.get('title') or ''
        eligibility_logic = {}
        try:
            raw = program.get('eligibility_logic')
            if raw:
                eligibility_logic = _json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            pass

        el_kw = eligibility_logic.get('target_keywords', []) or []
        el_ind = eligibility_logic.get('target_industries', []) or []
        el_biz = eligibility_logic.get('business_type', []) if isinstance(eligibility_logic.get('business_type'), list) else []
        target_text = f"{title} {' '.join(el_kw)} {' '.join(el_ind)}"

        # 사용자 인증/자격 파싱
        certs_raw = user_data.get('certifications') or ''
        certs = [c.strip() for c in certs_raw.split(',') if c.strip() and c.strip() != '없음']
        has_female  = any('여성' in c for c in certs)
        has_disabled = any('장애' in c for c in certs)
        has_social  = any(('사회적' in c) or ('협동조합' in c) or ('마을기업' in c) for c in certs)
        has_youth   = any('청년' in c for c in certs)
        has_restart = any(('재창업' in c) or ('재도전' in c) for c in certs)

        ind_code = (user_data.get('industry_code') or '')[:2]
        is_farmer  = ind_code in ('01', '02', '03')
        is_fishery = ind_code == '03'
        is_food    = ind_code in ('10', '11')

        # 소상공인 여부 (매출·직원 기준)
        rev = user_data.get('revenue_bracket') or user_data.get('revenue') or ''
        emp = user_data.get('employee_count_bracket') or user_data.get('employees') or ''
        is_soho = (rev in ('1억 미만', '1억~5억', 'UNDER_1B', '1B_TO_5B') and
                   emp in ('5인 미만', '5인~10인', 'UNDER_5', '5_TO_10'))

        # ── 배타적 대상 유형 체크 ──
        EXCLUSIVE = {'소상공인', '여성기업', '청년기업', '예비창업자', '사회적기업', '수출기업',
                     '장애인기업', '재창업기업'}
        exclusive_biz = [b for b in el_biz if b in EXCLUSIVE]
        if exclusive_biz:
            if '소상공인' in exclusive_biz and not is_soho:
                if not any(b in el_biz for b in ['중소기업', '스타트업', '기업']):
                    return '소상공인 전용 (사용자 비해당)'
            if '예비창업자' in exclusive_biz:
                user_years = 0
                est = user_data.get('establishment_date')
                if est:
                    try:
                        import datetime as _dt
                        d = _dt.datetime.strptime(str(est)[:10], '%Y-%m-%d')
                        user_years = (_dt.datetime.now() - d).days // 365
                    except Exception:
                        pass
                if user_years > 0:
                    return '예비창업자 전용'
            if '사회적기업' in exclusive_biz and not has_social:
                return '사회적경제기업 전용 자격'

        # ── 제목/키워드 기반 대상 제한 ──
        if any(kw in target_text for kw in ['여성기업', '여성창업', '여성경제인']) and not has_female:
            return '여성기업 전용 자격'
        if any(kw in target_text for kw in ['장애인기업', '장애인창업']) and not has_disabled:
            return '장애인기업 전용 자격'
        if any(kw in title for kw in ['보훈', '제대군인', '국가유공자']):
            return '보훈/제대군인 전용'
        if any(kw in title for kw in ['농업인', '영농', '농촌', '농가']) and not is_farmer:
            return '농업인 전용'
        if any(kw in title for kw in ['어업인', '수산업']) and not is_fishery:
            return '어업/수산업 전용'
        if any(kw in title for kw in ['식품진흥', '식품위생업']) and not is_food:
            return '식품업 전용'
        if any(kw in title for kw in ['사회적경제기업', '사회적기업', '마을기업', '협동조합']) and not has_social:
            return '사회적경제기업 전용 자격'
        if any(kw in title for kw in ['청년창업', '청년기업', '만39세', '만 39세']) and not has_youth:
            return '청년기업 전용 자격'
        if any(kw in title for kw in ['재도전', '재창업', '폐업 후']) and not has_restart:
            return '재도전/재창업 전용'

        return None

    async def match_program_with_user(self, program, user):
        """제외 조건 체크 후 키워드·지역 기반 점수 산출"""
        user_data = dict(user) if not isinstance(user, dict) else user

        # 제외 조건 먼저 체크
        exclude_reason = self._check_exclusions(program, user_data)
        if exclude_reason:
            return {"score": 0, "reasoning": exclude_reason, "excluded": True}

        title = (program.get('title') or '').lower()
        summary = (program.get('summary_text') or '').lower()
        text = title + ' ' + summary

        score = 60  # 기본 통과 점수

        # 관심사 키워드 일치 보너스
        interests_str = user_data.get('interests') or ''
        interests = [k.strip().lower() for k in interests_str.split(',') if k.strip()]
        kw_hits = sum(1 for kw in interests if kw and kw in text)
        score += min(kw_hits * 10, 30)

        # 지역 일치 보너스
        user_city = (user_data.get('address_city') or '').strip()
        ad_region = (program.get('region') or '').strip()
        if user_city and user_city in ad_region:
            score += 10

        # 금액·마감일 있으면 보너스 (상위 노출 유도)
        if program.get('support_amount'):
            score += 5
        if program.get('deadline_date'):
            score += 5

        score = min(score, 100)
        reasoning = f"관심사 {kw_hits}개 키워드 일치" if kw_hits else "전국 공통 지원사업"
        return {"score": score, "reasoning": reasoning, "excluded": False}

    def _build_email_html(self, company_name: str, matches: List[Dict], user_type: str = "business") -> str:
        """매칭 결과를 HTML 이메일 본문으로 변환 — 기업/개인 섹션 분리"""
        today = datetime.date.today()
        today_str = today.strftime("%Y년 %m월 %d일")
        APP_URL = os.getenv("FRONTEND_URL", "https://govmatch.kr")

        def _deadline_badge(deadline_str: str) -> str:
            if not deadline_str:
                return ""
            try:
                dl = datetime.date.fromisoformat(deadline_str[:10])
                days_left = (dl - today).days
                if days_left < 0:
                    return ""
                if days_left <= 3:
                    return f'<span style="background:#fee2e2;color:#dc2626;font-size:11px;font-weight:700;padding:2px 7px;border-radius:99px;">⚠️ D-{days_left}</span>'
                if days_left <= 7:
                    return f'<span style="background:#fef3c7;color:#d97706;font-size:11px;font-weight:700;padding:2px 7px;border-radius:99px;">D-{days_left}</span>'
                return f'<span style="background:#f1f5f9;color:#64748b;font-size:11px;font-weight:600;padding:2px 7px;border-radius:99px;">~{deadline_str[2:].replace("-",".")}</span>'
            except Exception:
                return ""

        def _card_html(m: dict) -> str:
            title      = m.get("program_title") or ""
            ann_id     = m.get("announcement_id") or m.get("id")
            amount     = (m.get("support_amount") or "").strip()
            deadline   = str(m.get("deadline_date") or "")[:10]
            category   = (m.get("category") or "").strip()
            department = (m.get("department") or "").strip()[:20]
            link       = f"{APP_URL}?aid={ann_id}" if ann_id else APP_URL

            # 카테고리 뱃지
            cat_html = f'<span style="background:#ede9fe;color:#7c3aed;font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;margin-right:6px;">{category}</span>' if category else ""
            # 기관명
            dept_html = f'<span style="color:#94a3b8;font-size:11px;">{department}</span>' if department else ""
            # 상단 메타 (카테고리 + 기관명)
            meta_top = f'<div style="margin-bottom:8px;">{cat_html}{dept_html}</div>' if (category or department) else ""

            # 금액
            amount_short = amount[:40] + "…" if len(amount) > 40 else amount
            amount_html = f'<div style="margin:10px 0 6px;"><span style="font-size:16px;font-weight:800;color:#2563eb;">💰 {amount_short}</span></div>' if amount_short else ""

            # 마감일 뱃지
            dl_badge = _deadline_badge(deadline)
            dl_html  = f'<div style="margin-bottom:12px;">{dl_badge}</div>' if dl_badge else '<div style="margin-bottom:12px;"></div>'

            return f'''<div style="margin:0 0 14px;border-radius:10px;border:1px solid #e2e8f0;overflow:hidden;">
  <div style="border-left:4px solid #4f46e5;padding:16px 16px 14px;background:#ffffff;">
    {meta_top}
    <p style="margin:0;color:#1e293b;font-size:14px;font-weight:700;line-height:1.6;">{title}</p>
    {amount_html}
    {dl_html}
    <a href="{link}" style="display:block;text-align:center;padding:10px;background:#4f46e5;color:#ffffff;text-decoration:none;border-radius:7px;font-size:13px;font-weight:700;">공고 바로가기 →</a>
  </div>
</div>\n'''

        # 기업/개인 섹션 분리
        biz_matches   = [m for m in matches if m.get("target_type") != "individual"]
        indiv_matches = [m for m in matches if m.get("target_type") == "individual"]

        show_biz   = user_type != "individual"
        show_indiv = user_type != "business"
        if biz_matches and indiv_matches:
            show_biz = show_indiv = True

        sections_html = ""

        if show_biz and biz_matches:
            label = "🏢 기업 맞춤 공고" if show_indiv else "맞춤 공고"
            top = biz_matches[:5]
            sections_html += f'<p style="margin:0 0 12px;font-size:15px;font-weight:700;color:#1e293b;">{label} {len(top)}건</p>'
            sections_html += "".join(_card_html(m) for m in top)

        if show_indiv and indiv_matches:
            top = indiv_matches[:5]
            mt = "margin-top:28px;" if sections_html else ""
            sections_html += f'<p style="{mt}margin-bottom:12px;font-size:15px;font-weight:700;color:#1e293b;">👤 개인 맞춤 공고 {len(top)}건</p>'
            sections_html += "".join(_card_html(m) for m in top)

        if not sections_html:
            top = matches[:5]
            sections_html = f'<p style="margin:0 0 12px;font-size:15px;font-weight:700;color:#1e293b;">맞춤 공고 {len(top)}건</p>'
            sections_html += "".join(_card_html(m) for m in top)

        total = len(matches)
        return f"""<div style="max-width:520px;margin:0 auto;font-family:-apple-system,'Pretendard',Arial,sans-serif;color:#1e293b;background:#f8fafc;">
  <!-- 헤더 -->
  <div style="background:#4f46e5;padding:28px 24px 22px;">
    <p style="margin:0;font-size:20px;font-weight:800;color:#ffffff;letter-spacing:-0.3px;">지원금AI</p>
    <p style="margin:6px 0 0;font-size:13px;color:#c7d2fe;">{today_str} · {company_name} 맞춤 공고 {total}건</p>
  </div>
  <!-- 본문 -->
  <div style="padding:24px;">
    {sections_html}
    <div style="margin:8px 0 4px;text-align:center;">
      <a href="{APP_URL}" style="display:inline-block;padding:13px 36px;background:#1e293b;color:#ffffff;text-decoration:none;border-radius:8px;font-size:14px;font-weight:700;">전체 공고 보기</a>
    </div>
  </div>
  <!-- 푸터 -->
  <div style="padding:16px 24px;text-align:center;border-top:1px solid #e2e8f0;">
    <p style="margin:0;font-size:11px;color:#94a3b8;">지원금AI · 자동 발송 알림 · <a href="{APP_URL}/unsubscribe" style="color:#94a3b8;">수신 거부</a></p>
  </div>
</div>"""

    def send_email(self, to_email: str, company_name: str, matches: List[Dict], user_type: str = "business") -> bool:
        """Resend HTTP API를 통해 매칭 결과 이메일 발송.

        Railway가 SMTP(25/587/465)를 차단하므로 Resend HTTPS API 사용.
        """
        if not self.email_configured:
            print(f"  Resend 미설정 (RESEND_API_KEY 없음) -> 이메일 발송 건너뜀: {to_email}")
            try: self._log_notification(to_email, company_name, "email", "not_configured")
            except Exception: pass
            return False

        html_body = self._build_email_html(company_name, matches, user_type)
        subject = f"[지원금AI] {company_name} 맞춤 공고 {len(matches)}건"

        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": self.resend_from,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body,
                },
                timeout=15,
            )
            if resp.status_code in (200, 202):
                print(f"  Email sent to {to_email} via Resend (id={resp.json().get('id','?')})")
                try: self._log_notification(to_email, company_name, "email", "sent")
                except Exception: pass
                return True
            else:
                err_text = resp.text[:200]
                print(f"  Resend API error ({to_email}): {resp.status_code} {err_text}")
                try: self._log_notification(to_email, company_name, "email", f"http_{resp.status_code}")
                except Exception: pass
                return False
        except Exception as e:
            print(f"  Resend request error ({to_email}): {e}")
            try: self._log_notification(to_email, company_name, "email", f"exc: {type(e).__name__}")
            except Exception: pass
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

        APP_URL = os.getenv("FRONTEND_URL", "https://govmatch.kr")
        top = matches[0] if matches else {}
        payload = json.dumps({
            "title": f"맞춤 공고 {len(matches)}건 도착",
            "body": top.get("program_title", "새로운 지원사업이 매칭되었습니다."),
            "url": APP_URL,
            "icon": "https://www.govmatch.kr/icon-192-maskable.png",
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

    async def send_kakao_message(self, business_number: str, company_name: str, matches: List[Dict]) -> bool:
        """카카오 refresh_token으로 액세스 토큰 갱신 후 나에게 보내기 API로 맞춤 공고 발송"""
        kakao_client_id = os.getenv("KAKAO_CLIENT_ID", "")
        kakao_client_secret = os.getenv("KAKAO_CLIENT_SECRET", "")
        if not kakao_client_id:
            return False

        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cursor = conn.cursor()
        cursor.execute("SELECT kakao_refresh_token FROM users WHERE business_number = %s", (business_number,))
        row = cursor.fetchone()
        conn.close()

        if not row or not row.get("kakao_refresh_token"):
            return False

        refresh_token = row["kakao_refresh_token"]

        try:
            async with httpx.AsyncClient() as client:
                # 1. refresh_token → 새 access_token
                token_res = await client.post("https://kauth.kakao.com/oauth/token", data={
                    "grant_type": "refresh_token",
                    "client_id": kakao_client_id,
                    "client_secret": kakao_client_secret,
                    "refresh_token": refresh_token,
                })
                token_data = token_res.json()
                access_token = token_data.get("access_token")
                if not access_token:
                    return False

                # refresh_token이 갱신된 경우 DB 업데이트
                new_refresh = token_data.get("refresh_token")
                if new_refresh:
                    conn2 = psycopg2.connect(DATABASE_URL)
                    cur2 = conn2.cursor()
                    cur2.execute("UPDATE users SET kakao_refresh_token = %s WHERE business_number = %s",
                                 (new_refresh, business_number))
                    conn2.commit()
                    conn2.close()

                # 2. 나에게 보내기 메시지 구성
                top = matches[0] if matches else {}
                more = len(matches) - 1
                desc = f"총 {len(matches)}건 매칭 | 최고점: {top.get('score', 0)}점"
                link_url = top.get("url", "https://govmatch.kr")

                msg_res = await client.post(
                    "https://kapi.kakao.com/v2/api/talk/memo/default/send",
                    headers={"Authorization": f"Bearer {access_token}"},
                    data={"template_object": json.dumps({
                        "object_type": "feed",
                        "content": {
                            "title": f"[지원금AI] {company_name} 맞춤 공고 {len(matches)}건",
                            "description": desc + (f"\n외 {more}건" if more > 0 else ""),
                            "image_url": "https://govmatch.kr/og-image.png",
                            "link": {"web_url": link_url, "mobile_web_url": link_url},
                        },
                        "buttons": [{"title": "공고 확인하기", "link": {"web_url": "https://govmatch.kr", "mobile_web_url": "https://govmatch.kr"}}],
                    }, ensure_ascii=False)},
                )
                result = msg_res.json()
                success = result.get("result_code") == 0
                if success:
                    self._log_notification(business_number, company_name, "kakao", "sent")
                else:
                    self._log_notification(business_number, company_name, "kakao", f"error:{result}")
                return success
        except Exception as e:
            print(f"  Kakao message error: {e}")
            return False

    def _log_notification(self, recipient: str, company_name: str, channel: str, status: str):
        """알림 발송 이력 저장 (DB의 기존 컬럼 + 추가된 컬럼 모두 사용)"""
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
            conn.autocommit = True
            cursor = conn.cursor()
            # 누락 컬럼 자동 보강 + 짧은 VARCHAR 확장 (이미 적용돼있으면 무시)
            for alt in [
                "ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS recipient TEXT",
                "ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS company_name TEXT",
                "ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS channel TEXT",
                # 기존 스키마의 business_number/status 컬럼이 너무 짧아 저장 실패 → 확장
                "ALTER TABLE notification_logs ALTER COLUMN business_number TYPE VARCHAR(50)",
                "ALTER TABLE notification_logs ALTER COLUMN notification_type TYPE VARCHAR(30)",
                "ALTER TABLE notification_logs ALTER COLUMN status TYPE VARCHAR(200)",
            ]:
                try: cursor.execute(alt)
                except Exception: pass
            cursor.execute(
                """INSERT INTO notification_logs
                   (business_number, notification_type, recipient, company_name, channel, status)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (recipient[:50] if recipient else "", channel, recipient, company_name, channel, status[:200])
            )
            conn.close()
        except Exception as e:
            print(f"  Log error: {e}")

    async def generate_daily_digest(self):
        """데일리 다이제스트 생성 + 이메일 발송 — 모든 단계 격리"""
        try:
            users = await self.get_target_users()
        except Exception as e:
            print(f"  [digest] get_target_users error: {e}")
            return []

        digest_results = []
        for user in users:
            user_email_label = user.get('email','?') if isinstance(user, dict) else '?'
            try:
                try:
                    programs = await self.get_filtered_programs(user)
                except Exception as e:
                    print(f"  [digest] {user_email_label}: filter error: {e}")
                    continue

                matches = []
                for program in programs:
                    try:
                        match_result = await self.match_program_with_user(program, user)
                    except Exception as e:
                        print(f"  [digest] AI match error: {e}")
                        match_result = {"score": 60, "reasoning": "AI 매칭 실패 — 기본 추천"}

                    # 임계값 완화: 80 → 60 (매칭 확대 + AI 실패 시에도 통과)
                    threshold = 60
                    try:
                        if user.get('matching_threshold'):
                            threshold = int(user['matching_threshold'])
                    except (KeyError, TypeError, ValueError):
                        pass

                    if match_result.get('excluded'):
                        continue

                    if match_result.get('score', 0) >= threshold:
                        matches.append({
                            "program_title": program['title'],
                            "score": match_result['score'],
                            "reasoning": match_result.get('reasoning', ''),
                            "url": program.get('origin_url') or '',
                            "announcement_id": program.get('announcement_id'),
                            "support_amount": program.get('support_amount') or '',
                            "deadline_date": str(program.get('deadline_date') or '')[:10],
                            "target_type": program.get('target_type') or '',
                            "category": program.get('category') or '',
                            "department": program.get('department') or '',
                        })

                if matches:
                    user_dict = dict(user)
                    company_name = user_dict.get('company_name') or '회원'
                    email = user_dict.get('notify_email') or user_dict.get('email')
                    bn = user_dict.get('business_number', '')

                    entry = {
                        "user_email": email,
                        "company_name": company_name,
                        "matches": matches,
                        "email_sent": False,
                        "push_sent": 0,
                        "kakao_sent": False,
                    }

                    if email:
                        try:
                            u_type = user_dict.get('user_type') or 'business'
                            entry["email_sent"] = self.send_email(email, company_name, matches, user_type=u_type)
                        except Exception as e:
                            print(f"  [digest] email send error: {e}")

                    try:
                        entry["push_sent"] = self.send_push(bn, company_name, matches)
                    except Exception as e:
                        print(f"  [digest] push send error: {e}")

                    try:
                        entry["kakao_sent"] = await self.send_kakao_message(bn, company_name, matches)
                    except Exception as e:
                        print(f"  [digest] kakao send error: {e}")

                    digest_results.append(entry)
            except Exception as outer_e:
                print(f"  [digest] {user_email_label} unexpected error: {outer_e}")
                continue

        return digest_results


notification_service = NotificationService()
