import google.generativeai as genai
import os
import json
import hmac
import hashlib
import psycopg2
import psycopg2.extras
import datetime
import httpx
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv
from app.config import DATABASE_URL

load_dotenv()

# 수신거부 원클릭 토큰 — 로그인 불필요(이메일 클릭), bn+서버시크릿 HMAC
_UNSUB_SECRET = os.getenv("JWT_SECRET", "change-me-in-production-env")


def make_unsubscribe_token(bn: str) -> str:
    return hmac.new(_UNSUB_SECRET.encode(), f"unsub:{bn}".encode(), hashlib.sha256).hexdigest()[:20]


def verify_unsubscribe_token(bn: str, token: str) -> bool:
    if not bn or not token:
        return False
    return hmac.compare_digest(make_unsubscribe_token(str(bn)), str(token))


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
               OR (ps.id IS NOT NULL AND COALESCE(ns.is_active, 1) = 1))
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

        # 지역 조건: 전국/All/온라인이거나 사용자 지역 포함 (타지역 제외)
        # address_city는 쉼표로 여러 지역이 저장될 수 있음 (예: '서울,부산')
        # '전국'이 포함되거나 비어 있으면 전국 공고만, 아니면 각 도시별 OR 조건
        _NATIONWIDE = {'전국', 'All', '온라인', '해외', '기타', ''}
        _NATIONWIDE_SQL = "('전국', 'All', '온라인', '해외', '기타')"

        user_cities = [
            c.strip() for c in user_loc.split(',')
            if c.strip() and c.strip() not in _NATIONWIDE
        ]

        params: list = []

        # 지역 절
        if user_cities:
            like_parts = " OR ".join(["region LIKE %s" for _ in user_cities])
            region_clause = f"(region IN {_NATIONWIDE_SQL} OR {like_parts})"
            params.extend([f"%{c}%" for c in user_cities])
        else:
            region_clause = f"region IN {_NATIONWIDE_SQL}"

        # 기업/개인 탭 기준 유효 관심사 카테고리 (혼입 방지)
        _BIZ_CATS = {
            "창업지원", "기술개발", "수출마케팅", "고용지원", "시설개선", "정책자금",
            "디지털전환", "판로개척", "교육훈련", "에너지환경", "소상공인", "R&D",
        }
        _INDIV_CATS = {
            "취업", "주거", "교육", "청년", "출산", "육아", "다자녀",
            "장학금", "의료", "장애", "저소득", "노인", "문화",
        }

        # 관심사 키워드 절 (user_type에 맞는 카테고리만 필터)
        interests_str = user_dict.get('interests') or ''
        all_interests = [i.strip() for i in interests_str.split(',') if i.strip()]
        if user_type == 'individual':
            interests_kw = [i for i in all_interests if i in _INDIV_CATS]
        else:
            interests_kw = [i for i in all_interests if i in _BIZ_CATS]
        # 분류된 관심사 없으면 전체 사용 (자유 키워드 입력 케이스)
        if not interests_kw:
            interests_kw = all_interests
        if interests_kw:
            kw_parts = " OR ".join(
                ["(title ILIKE %s OR category ILIKE %s)" for _ in interests_kw]
            )
            interest_clause = f"AND ({kw_parts})"
            for kw in interests_kw:
                params.extend([f"%{kw}%", f"%{kw}%"])
            # 관심사 매칭 점수 (정렬용)
            score_parts = " + ".join(
                [f"(CASE WHEN title ILIKE %s OR category ILIKE %s THEN 1 ELSE 0 END)" for _ in interests_kw]
            )
            score_params = []
            for kw in interests_kw:
                score_params.extend([f"%{kw}%", f"%{kw}%"])
        else:
            interest_clause = ""
            score_parts = "0"
            score_params = []

        params_for_years = [user_years]

        query = f"""
            SELECT *, ({score_parts}) AS interest_score
            FROM announcements
            WHERE {region_clause}
            {target_type_clause}
            {interest_clause}
            AND (established_years_limit IS NULL OR established_years_limit >= %s)
            AND is_archived = FALSE
            AND (
                (deadline_date IS NOT NULL AND deadline_date >= CURRENT_DATE)
                OR (deadline_date IS NULL AND created_at >= CURRENT_DATE - INTERVAL '3 months')
            )
            ORDER BY
                interest_score DESC,
                CASE WHEN support_amount IS NOT NULL AND support_amount != '' THEN 0 ELSE 1 END,
                deadline_date ASC NULLS LAST,
                created_at DESC
            LIMIT 100
        """
        params = score_params + params + params_for_years

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

        score = 60  # 기본 점수 — interests 없어도 금액+마감일 있으면 임계값 달성 가능

        # 관심사 키워드 일치 보너스
        interests_str = user_data.get('interests') or ''
        interests = [k.strip().lower() for k in interests_str.split(',') if k.strip()]
        kw_hits = sum(1 for kw in interests if kw and kw in text)
        score += min(kw_hits * 10, 30)

        # 지역 일치 보너스 — 전국 공고는 모든 사람 대상이므로 가산
        # address_city는 쉼표 구분 다중값 가능 (예: '서울,부산')
        _user_cities = [
            c.strip() for c in (user_data.get('address_city') or '').split(',')
            if c.strip() and c.strip() not in ('전국', 'All', '온라인', '해외', '기타', '')
        ]
        ad_region = (program.get('region') or '').strip()
        if not ad_region or ad_region in ('전국', 'All', '온라인', '해외', '기타'):
            score += 10
        elif any(city and city in ad_region for city in _user_cities):
            score += 10

        # 금액·마감일 있으면 보너스 (상위 노출 유도)
        if program.get('support_amount'):
            score += 5
        if program.get('deadline_date'):
            score += 5

        score = min(score, 100)
        reasoning = f"관심사 {kw_hits}개 키워드 일치" if kw_hits else "전국 공통 지원사업"
        return {"score": score, "reasoning": reasoning, "excluded": False}

    def _build_email_html(self, company_name: str, matches: List[Dict], user_type: str = "business", bn: str = "") -> str:
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

        def _fmt_amount(raw: str) -> str:
            """'총 500000000원 이내 (지원비율 50%)', '15,000,000 KRW' 등 → '5억원 이내' 형태로 통일"""
            import re as _re
            if not raw:
                return ""
            # KRW 제거
            cleaned = raw.replace("KRW", "").replace("krw", "").strip()
            # 이미 한글 단위 포함이면 그대로 반환 (원 단위 정리만)
            if any(u in cleaned for u in ["억", "만원", "천만"]):
                return cleaned[:50]
            # prefix: 총/최대
            prefix = ""
            if "최대" in raw:
                prefix = "최대 "
            elif "총" in raw:
                prefix = "총 "
            # suffix: 이내/이상
            suffix = ""
            if "이내" in raw:
                suffix = " 이내"
            elif "이상" in raw:
                suffix = " 이상"
            # 괄호 안 부가 설명 추출
            paren_m = _re.search(r'\(([^)]{2,40})\)', raw)
            extra = f" ({paren_m.group(1)})" if paren_m else ""
            # 문자열에서 가장 큰 숫자 추출
            candidates = _re.findall(r'[\d,]+', cleaned)
            best_n = 0
            for c in candidates:
                try:
                    n = int(c.replace(",", ""))
                    if n > best_n:
                        best_n = n
                except ValueError:
                    pass
            if best_n <= 0:
                return raw[:50]
            uk  = best_n // 100_000_000
            man = (best_n % 100_000_000) // 10_000
            chun = (best_n % 10_000) // 1_000
            if uk > 0 and man > 0:
                amount_str = f"{uk}억 {man:,}만원"
            elif uk > 0:
                amount_str = f"{uk}억원"
            elif man > 0:
                amount_str = f"{man:,}만원"
            elif chun > 0:
                amount_str = f"{chun:,}천원"
            else:
                amount_str = f"{best_n:,}원"
            return f"{prefix}{amount_str}{suffix}{extra}"[:60]

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

            # 금액 — 한국어 단위로 변환
            amount_fmt = _fmt_amount(amount)
            amount_html = f'<div style="margin:10px 0 6px;"><span style="font-size:16px;font-weight:800;color:#2563eb;">💰 {amount_fmt}</span></div>' if amount_fmt else ""

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
    <p style="margin:0;font-size:11px;color:#94a3b8;">지원금AI · 자동 발송 알림 · <a href="{APP_URL}/unsubscribe?bn={bn}&token={make_unsubscribe_token(bn) if bn else ''}" style="color:#94a3b8;">수신 거부</a></p>
  </div>
</div>"""

    def send_email(self, to_email: str, company_name: str, matches: List[Dict], user_type: str = "business", bn: str = "") -> bool:
        """Resend HTTP API를 통해 매칭 결과 이메일 발송.

        Railway가 SMTP(25/587/465)를 차단하므로 Resend HTTPS API 사용.
        """
        if not self.email_configured:
            print(f"  Resend 미설정 (RESEND_API_KEY 없음) -> 이메일 발송 건너뜀: {to_email}")
            try: self._log_notification(to_email, company_name, "email", "not_configured")
            except Exception: pass
            return False

        html_body = self._build_email_html(company_name, matches, user_type, bn=bn)
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
        import datetime as _dt
        _kst_hour = (_dt.datetime.utcnow().hour + 9) % 24
        if not (9 <= _kst_hour < 18):
            print(f"  [push] KST {_kst_hour:02d}시 — 발송 시간 외(09~18시) 스킵")
            return 0

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
        ann_id = top.get("announcement_id")
        target_url = f"{APP_URL}?aid={ann_id}" if ann_id else APP_URL
        payload = json.dumps({
            "title": f"맞춤 공고 {len(matches)}건 도착",
            "body": top.get("program_title", "새로운 지원사업이 매칭되었습니다."),
            "url": target_url,
            "icon": "https://www.govmatch.kr/icon-192.png",
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

    def send_transactional_push(self, business_number: str, title: str, body: str, url: str) -> int:
        """트랜잭션 알림(상담 완료 등) — 시간대 게이트 없음, 임의 title/body/url."""
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            print("  pywebpush 미설치 -> 트랜잭션 푸시 건너뜀")
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

        payload = json.dumps({
            "title": title,
            "body": body,
            "url": url,
            "icon": "https://www.govmatch.kr/icon-192.png",
        }, ensure_ascii=False)

        sent = 0
        for sub in subs:
            try:
                webpush(
                    subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
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
                print(f"  TxPush error ({sub['endpoint'][:40]}...): {e}")
            except Exception as e:
                print(f"  TxPush error: {e}")

        if sent:
            self._log_notification(business_number, "", "push", f"consult_tx_sent:{sent}")
        return sent

    async def send_kakao_message(self, business_number: str, company_name: str, matches: List[Dict]) -> bool:
        """카카오 refresh_token으로 액세스 토큰 갱신 후 나에게 보내기 API로 맞춤 공고 발송"""
        import datetime as _dt
        _kst_hour = (_dt.datetime.utcnow().hour + 9) % 24
        if not (9 <= _kst_hour < 18):
            print(f"  [kakao] KST {_kst_hour:02d}시 — 발송 시간 외(09~18시) 스킵")
            return False

        kakao_client_id = os.getenv("KAKAO_CLIENT_ID", "")
        kakao_client_secret = os.getenv("KAKAO_CLIENT_SECRET", "")
        if not kakao_client_id:
            return False

        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cursor = conn.cursor()
        # [M-2] 알림 설정에서 카카오 토글(kakao_enabled=1)을 켠 사용자만 발송
        cursor.execute("""
            SELECT u.kakao_refresh_token
            FROM users u
            JOIN notification_settings ns ON ns.business_number = u.business_number
            WHERE u.business_number = %s AND COALESCE(ns.kakao_enabled, 0) = 1
        """, (business_number,))
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
                    # [M-2] talk_message scope 미동의(-402)는 재시도 무의미 — 토글 자동 해제
                    # (30일간 동일 사용자 49회 반복 실패 실측)
                    if result.get("code") == -402:
                        try:
                            conn3 = psycopg2.connect(DATABASE_URL)
                            cur3 = conn3.cursor()
                            cur3.execute(
                                "UPDATE notification_settings SET kakao_enabled = 0 WHERE business_number = %s",
                                (business_number,))
                            conn3.commit()
                            conn3.close()
                            print(f"  [kakao] {business_number} scope 미동의 — kakao_enabled 자동 해제")
                        except Exception as _ke:
                            print(f"  [kakao] toggle-off error: {_ke}")
                return success
        except Exception as e:
            print(f"  Kakao message error: {e}")
            return False

    def _log_notification(self, recipient: str, company_name: str, channel: str, status: str, announcement_id=None):
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
                "ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS announcement_id INTEGER",
                # 기존 스키마의 business_number/status 컬럼이 너무 짧아 저장 실패 → 확장
                "ALTER TABLE notification_logs ALTER COLUMN business_number TYPE VARCHAR(50)",
                "ALTER TABLE notification_logs ALTER COLUMN notification_type TYPE VARCHAR(30)",
                "ALTER TABLE notification_logs ALTER COLUMN status TYPE VARCHAR(200)",
            ]:
                try: cursor.execute(alt)
                except Exception: pass
            cursor.execute(
                """INSERT INTO notification_logs
                   (business_number, notification_type, recipient, company_name, channel, status, announcement_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (recipient[:50] if recipient else "", channel, recipient, company_name, channel, status[:200], announcement_id)
            )
            conn.close()
        except Exception as e:
            print(f"  Log error: {e}")

    def _get_sent_info(self, business_number: str) -> dict:
        """최근 90일 발송 이력 반환: {announcement_id: last_sent_date}"""
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            cur.execute("""
                SELECT announcement_id, MAX(sent_at)::date AS last_sent
                FROM notification_logs
                WHERE business_number = %s
                  AND announcement_id IS NOT NULL
                  AND status = 'sent'
                  AND sent_at >= NOW() - INTERVAL '90 days'
                GROUP BY announcement_id
            """, (business_number,))
            rows = cur.fetchall()
            conn.close()
            return {r['announcement_id']: r['last_sent'] for r in rows}
        except Exception as e:
            print(f"  [sent_info] error: {e}")
            return {}

    def _log_sent_announcements(self, business_number: str, matches: list, channel: str):
        """발송 성공한 공고별 이력 기록 (중복 방지용)"""
        try:
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = True
            cur = conn.cursor()
            for m in matches:
                aid = m.get('announcement_id')
                if aid:
                    cur.execute("""
                        INSERT INTO notification_logs
                        (business_number, notification_type, recipient, channel, status, announcement_id)
                        VALUES (%s, %s, %s, %s, 'sent', %s)
                    """, (business_number[:50], channel, business_number[:50], channel, aid))
            conn.close()
        except Exception as e:
            print(f"  [log_sent] error: {e}")

    def _matches_to_digest_cards(self, results: list, limit: int = 10) -> list:
        """매칭 정본(get_matches_hybrid) 결과 → 다이제스트 카드 매핑.
        ineligible 제외, announcement_id 없는 행 스킵, 상위 limit건."""
        cards = []
        for r in results or []:
            if not isinstance(r, dict):
                continue
            if r.get("eligibility_status") == "ineligible":
                continue
            aid = r.get("announcement_id")
            if not aid:
                continue
            cards.append({
                "program_title": r.get("title") or "",
                "score": int(round(r.get("match_score") or 0)),
                "reasoning": r.get("recommendation_reason") or r.get("match_reason") or "프로필 기반 맞춤 매칭",
                "url": r.get("origin_url") or "",
                "announcement_id": aid,
                "support_amount": r.get("support_amount") or "",
                "deadline_date": str(r.get("deadline_date") or "")[:10],
                "target_type": r.get("target_type") or "",
                "category": r.get("category") or "",
                "department": r.get("department") or "",
            })
            if len(cards) >= limit:
                break
        return cards

    def _select_matches_via_matcher(self, user_dict: dict) -> list:
        """[2026-07-05 C-1 수정] 다이제스트 공고 선정을 매칭 정본으로 전환.
        기존 자체 SQL+휴리스틱은 지역/전용공고/아카이브 오발송이 실증돼 폐기(진단서 §3).
        both 사용자는 기업+개인 결과를 합침(M-4 동시 해소)."""
        from app.core.matcher import get_matches_hybrid
        user_type = (user_dict.get("user_type") or "business").lower()
        results = []
        if user_type in ("business", "both"):
            results.extend(get_matches_hybrid(user_dict, is_individual=False) or [])
        if user_type in ("individual", "both"):
            results.extend(get_matches_hybrid(user_dict, is_individual=True) or [])
        seen = set()
        uniq = []
        for r in results:
            aid = r.get("announcement_id") if isinstance(r, dict) else None
            if aid and aid in seen:
                continue
            if aid:
                seen.add(aid)
            uniq.append(r)
        return self._matches_to_digest_cards(uniq)

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
                # [2026-07-05 C-1] 공고 선정을 매칭 정본(get_matches_hybrid)으로 전환 —
                # 대시보드 매칭과 동일 기준(지역 하드필터·전용공고·아카이브·자격판정) 적용.
                # 매칭 자체가 규칙 기반이므로 구 AI 점수 폴백(6/25형 빈 다이제스트)도 불필요.
                try:
                    matches = self._select_matches_via_matcher(dict(user))
                except Exception as e:
                    print(f"  [digest] {user_email_label}: matcher error: {e}")
                    continue

                # ── 중복 발송 방지: 이미 보낸 공고는 D-7 임박이 아니면 제외 ──
                _bn_check = (user.get('business_number') or '') if isinstance(user, dict) else ''
                if _bn_check:
                    try:
                        _sent_info = self._get_sent_info(_bn_check)
                        if _sent_info:
                            _today = datetime.date.today()
                            _filtered = []
                            for _m in matches:
                                _aid = _m.get('announcement_id')
                                if not _aid or _aid not in _sent_info:
                                    _filtered.append(_m)  # 처음 발송
                                else:
                                    _ddl = _m.get('deadline_date', '')
                                    try:
                                        _ddl_date = datetime.date.fromisoformat(_ddl) if _ddl else None
                                        _days_left = (_ddl_date - _today).days if _ddl_date else 999
                                        _days_since = (_today - _sent_info[_aid]).days
                                        if _days_left <= 7 and _days_since >= 7:
                                            _filtered.append(_m)  # D-7 임박 재발송
                                    except Exception:
                                        _filtered.append(_m)  # 날짜 파싱 실패 → 안전하게 포함
                            matches = _filtered
                    except Exception as _de:
                        print(f"  [digest] dedup check error: {_de}")

                if matches:
                    user_dict = dict(user)
                    company_name = user_dict.get('company_name') or '회원'
                    # [M-3] 이메일은 알림 설정에서 동의한 주소(notify_email)만 사용 —
                    # push 구독만 한 사용자에게 계정 이메일(users.email)로 폴백 발송 금지
                    email = user_dict.get('notify_email')
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
                            entry["email_sent"] = self.send_email(email, company_name, matches, user_type=u_type, bn=bn)
                            if entry["email_sent"] and bn:
                                self._log_sent_announcements(bn, matches, "email")
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

                    # [M-1] 이메일 없이 push/kakao만 성공한 사용자도 per-공고 이력 기록 —
                    # 미기록 시 dedup이 안 걸려 동일 공고를 매일 반복 수신
                    try:
                        if bn and not entry["email_sent"] and (entry["push_sent"] or entry["kakao_sent"]):
                            self._log_sent_announcements(bn, matches, "push" if entry["push_sent"] else "kakao")
                    except Exception as e:
                        print(f"  [digest] sent-log error: {e}")

                    digest_results.append(entry)
            except Exception as outer_e:
                print(f"  [digest] {user_email_label} unexpected error: {outer_e}")
                continue

        return digest_results


notification_service = NotificationService()
