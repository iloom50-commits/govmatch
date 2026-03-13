import sys
import os
import asyncio

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import psycopg2
import psycopg2.extras
import datetime
import json
import hmac
import hashlib
import jwt
import bcrypt
from app.core.url_checker import check_duplicate_url
from app.core.matcher import get_matches_for_user
from app.config import DATABASE_URL

# Admin Scraper Import for Manual Sync
from app.services.admin_scraper import admin_scraper


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production-env")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # 7일

sync_status = {"running": False, "last_result": None, "last_time": None}
manual_sync_status = {"running": False, "last_result": None, "last_time": None}
reanalyze_status = {"running": False, "done": 0, "total": 0, "last_result": None, "last_time": None}


def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def init_database():
    """DB 연결 확인 (테이블은 Supabase SQL Editor에서 미리 생성됨)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        print("  DB connection OK (PostgreSQL/Supabase)")
    except Exception as e:
        print(f"  DB connection error (app will continue): {e}")


init_database()


DIGEST_HOUR = int(os.environ.get("DIGEST_HOUR", "9"))


async def _daily_digest_loop():
    """매일 지정 시각(DIGEST_HOUR)에 다이제스트를 자동 생성하는 백그라운드 루프"""
    from app.services.notification_service import notification_service
    while True:
        now = datetime.datetime.now()
        target = now.replace(hour=DIGEST_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        print(f"[Scheduler] next digest at {target.isoformat()} (in {wait_seconds/3600:.1f}h)")
        await asyncio.sleep(wait_seconds)
        try:
            print("[Scheduler] Running scheduled daily digest...")
            results = await notification_service.generate_daily_digest()
            sent = sum(1 for r in results if r.get("email_sent"))
            print(f"[Scheduler] Digest complete: {len(results)} users, {sent} emails sent")
        except Exception as e:
            print(f"[Scheduler] digest error: {e}")


def _delete_expired_announcements():
    """마감일이 지난 공고를 DB에서 삭제"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM announcements WHERE deadline_date IS NOT NULL AND deadline_date < CURRENT_DATE")
        row = cur.fetchone()
        count = row["count"] if row else 0
        if count > 0:
            cur.execute("DELETE FROM announcements WHERE deadline_date IS NOT NULL AND deadline_date < CURRENT_DATE")
            conn.commit()
            print(f"[Scheduler] Deleted {count} expired announcements")
        conn.close()
    except Exception as e:
        print(f"[Scheduler] expire cleanup error: {e}")


async def _daily_cleanup_loop():
    """매일 자정에 만료 공고 자동 삭제"""
    while True:
        now = datetime.datetime.now()
        target = now.replace(hour=0, minute=5, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        _delete_expired_announcements()


@asynccontextmanager
async def lifespan(app):
    _delete_expired_announcements()  # 시작 시 즉시 만료 공고 정리
    task_digest = asyncio.create_task(_daily_digest_loop())
    task_cleanup = asyncio.create_task(_daily_cleanup_loop())
    yield
    task_digest.cancel()
    task_cleanup.cancel()
    try:
        await task_digest
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Gov Support Matching Assistant", lifespan=lifespan)


@app.get("/health")
def health_check():
    return {"status": "ok"}


_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BusinessNumberRequest(BaseModel):
    business_number: str

class UserProfile(BaseModel):
    business_number: str
    company_name: str
    establishment_date: str
    address_city: str
    industry_code: str
    revenue_bracket: Optional[str] = None
    employee_count_bracket: Optional[str] = None
    interests: Optional[str] = None

class CompanyNameRequest(BaseModel):
    company_name: str
    business_content: Optional[str] = ""

class URLRequest(BaseModel):
    url: str

class NotificationSettings(BaseModel):
    business_number: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    channel: str = "email"
    is_active: bool = True

class AdminURLRequest(BaseModel):
    url: str
    source_name: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    business_number: str
    company_name: Optional[str] = ""
    address_city: Optional[str] = "전국"
    industry_code: Optional[str] = "00000"
    establishment_date: Optional[str] = None
    revenue_bracket: Optional[str] = None
    employee_count_bracket: Optional[str] = None
    interests: Optional[str] = None
    referred_by: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str


def _create_jwt(user_id: int, business_number: str, email: str, plan: str, trial_ends_at: str | None) -> str:
    payload = {
        "user_id": user_id,
        "bn": business_number,
        "email": email,
        "plan": plan,
        "trial_ends_at": trial_ends_at,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다. 다시 로그인해 주세요.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")


def _get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    token = authorization.split(" ", 1)[1]
    return _decode_jwt(token)


def _get_plan_status(plan: str, trial_ends_at: str | None) -> dict:
    """플랜 상태와 남은 일수를 계산"""
    now = datetime.datetime.utcnow()
    if plan == "basic":
        return {"plan": "basic", "active": True, "days_left": None, "label": "베이직"}
    if plan == "trial" and trial_ends_at:
        try:
            ends = datetime.datetime.fromisoformat(str(trial_ends_at))
            days_left = (ends - now).days
            if days_left < 0:
                return {"plan": "expired", "active": False, "days_left": 0, "label": "만료됨"}
            return {"plan": "trial", "active": True, "days_left": days_left, "label": f"무료체험 D-{days_left}"}
        except ValueError:
            pass
    return {"plan": plan, "active": plan != "expired", "days_left": None, "label": plan}


@app.post("/api/auth/register")
def api_register(req: RegisterRequest):
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=400, detail="올바른 이메일을 입력해 주세요.")
    if not req.password or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="비밀번호는 6자 이상이어야 합니다.")
    if len(req.business_number) != 10:
        raise HTTPException(status_code=400, detail="사업자번호 10자리를 입력해 주세요.")

    import hashlib as _hashlib
    hashed = _hash_password(req.password)
    trial_end = (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (req.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다.")

        cursor.execute("SELECT user_id FROM users WHERE business_number = %s", (req.business_number,))
        existing = cursor.fetchone()

        est_date = req.establishment_date or datetime.date.today().isoformat()
        if existing:
            cursor.execute(
                """UPDATE users SET email=%s, password_hash=%s, plan='trial', trial_ends_at=%s,
                   company_name=COALESCE(NULLIF(%s, ''), company_name),
                   address_city=COALESCE(NULLIF(%s, '전국'), address_city),
                   industry_code=COALESCE(NULLIF(%s, '00000'), industry_code),
                   establishment_date=COALESCE(%s, establishment_date),
                   revenue_bracket=COALESCE(%s, revenue_bracket),
                   employee_count_bracket=COALESCE(%s, employee_count_bracket),
                   interests=COALESCE(%s, interests)
                   WHERE business_number=%s""",
                (req.email, hashed, trial_end,
                 req.company_name or "", req.address_city or "전국",
                 req.industry_code or "00000", req.establishment_date,
                 req.revenue_bracket, req.employee_count_bracket, req.interests,
                 req.business_number),
            )
            user_id = existing["user_id"]
        else:
            cursor.execute(
                """INSERT INTO users (business_number, company_name, email, password_hash, plan, trial_ends_at,
                   address_city, establishment_date, industry_code, revenue_bracket, employee_count_bracket, interests,
                   referred_by)
                   VALUES (%s, %s, %s, %s, 'trial', %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING user_id""",
                (req.business_number, req.company_name or "", req.email, hashed, trial_end,
                 req.address_city or "전국", est_date,
                 req.industry_code or "00000", req.revenue_bracket,
                 req.employee_count_bracket, req.interests,
                 req.referred_by or None),
            )
            user_id = cursor.fetchone()["user_id"]
            # 추천 코드 자동 생성
            ref_code = _hashlib.md5(f'{req.business_number}{user_id}'.encode()).hexdigest()[:8].upper()
            cursor.execute("UPDATE users SET referral_code=%s WHERE business_number=%s", (ref_code, req.business_number))

        conn.commit()
        token = _create_jwt(user_id, req.business_number, req.email, "trial", trial_end)
        return {
            "status": "SUCCESS",
            "token": token,
            "plan": _get_plan_status("trial", trial_end),
        }
    finally:
        conn.close()


@app.post("/api/auth/login")
def api_login(req: LoginRequest):
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail="이메일과 비밀번호를 입력해 주세요.")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = %s", (req.email,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="등록되지 않은 이메일입니다.")

    u = dict(user)
    if not u.get("password_hash"):
        raise HTTPException(status_code=401, detail="비밀번호가 설정되지 않은 계정입니다. 회원가입을 진행해 주세요.")

    if not _verify_password(req.password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")

    plan = u.get("plan") or "trial"
    trial_ends = u.get("trial_ends_at")
    if trial_ends is not None:
        trial_ends = str(trial_ends)
    plan_status = _get_plan_status(plan, trial_ends)

    if plan_status["plan"] == "expired":
        plan = "expired"
        conn2 = get_db_connection()
        cur2 = conn2.cursor()
        cur2.execute("UPDATE users SET plan = 'expired' WHERE user_id = %s", (u["user_id"],))
        conn2.commit()
        conn2.close()

    token = _create_jwt(u["user_id"], u["business_number"], u["email"], plan, trial_ends)
    return {
        "status": "SUCCESS",
        "token": token,
        "user": {
            "business_number": u["business_number"],
            "company_name": u.get("company_name", ""),
            "email": u["email"],
            "address_city": u.get("address_city", ""),
            "establishment_date": str(u.get("establishment_date", "") or ""),
            "industry_code": u.get("industry_code", ""),
            "revenue_bracket": u.get("revenue_bracket", ""),
            "employee_count_bracket": u.get("employee_count_bracket", ""),
            "interests": u.get("interests", ""),
        },
        "plan": plan_status,
    }


@app.get("/api/auth/me")
def api_auth_me(current_user: dict = Depends(_get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE business_number = %s", (current_user["bn"],))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    u = dict(user)
    # Lookup KSIC industry name
    industry_name = ""
    if u.get("industry_code"):
        cursor.execute("SELECT name FROM ksic_classification WHERE code = %s", (u["industry_code"],))
        row = cursor.fetchone()
        if row:
            industry_name = row["name"]
    conn.close()
    trial_ends = u.get("trial_ends_at")
    if trial_ends is not None:
        trial_ends = str(trial_ends)
    plan_status = _get_plan_status(u.get("plan") or "trial", trial_ends)
    return {
        "status": "SUCCESS",
        "user": {
            "business_number": u["business_number"],
            "company_name": u["company_name"],
            "email": u.get("email"),
            "address_city": u["address_city"],
            "industry_code": u["industry_code"],
            "industry_name": industry_name,
            "revenue_bracket": u["revenue_bracket"],
            "employee_count_bracket": u["employee_count_bracket"],
            "interests": u.get("interests"),
            "establishment_date": str(u["establishment_date"]) if u.get("establishment_date") else "",
            "referral_code": u.get("referral_code"),
            "merit_months": u.get("merit_months", 0),
        },
        "plan": plan_status,
    }


class UpgradePlanRequest(BaseModel):
    payment_key: Optional[str] = None
    order_id: Optional[str] = None
    amount: Optional[int] = 4900


TOSS_SECRET_KEY = os.getenv("TOSS_SECRET_KEY", "")


@app.post("/api/plan/upgrade")
def api_plan_upgrade(
    req: UpgradePlanRequest,
    current_user: dict = Depends(_get_current_user),
):
    """결제 확인 후 플랜을 basic으로 업그레이드"""
    bn = current_user["bn"]

    if TOSS_SECRET_KEY and req.payment_key:
        import httpx
        import base64
        auth = base64.b64encode(f"{TOSS_SECRET_KEY}:".encode()).decode()
        confirm_res = httpx.post(
            "https://api.tosspayments.com/v1/payments/confirm",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
            },
            json={
                "paymentKey": req.payment_key,
                "orderId": req.order_id,
                "amount": req.amount,
            },
            timeout=15,
        )
        if confirm_res.status_code != 200:
            detail = confirm_res.json().get("message", "결제 승인에 실패했습니다.")
            raise HTTPException(status_code=400, detail=detail)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET plan = 'basic', trial_ends_at = NULL WHERE business_number = %s",
        (bn,),
    )
    # 추천인에게 merit_months +1 및 플랜 연장
    cur.execute("SELECT referred_by FROM users WHERE business_number = %s", (bn,))
    row = cur.fetchone()
    if row and row["referred_by"]:
        ref_code = row["referred_by"]
        cur.execute("SELECT user_id, plan, trial_ends_at, merit_months FROM users WHERE referral_code = %s", (ref_code,))
        referrer = cur.fetchone()
        if referrer:
            new_merit = (referrer["merit_months"] or 0) + 1
            if referrer["plan"] == "basic":
                # basic 플랜은 이미 무제한이므로 merit만 기록
                cur.execute("UPDATE users SET merit_months=%s WHERE user_id=%s", (new_merit, referrer["user_id"]))
            else:
                # trial 또는 expired → trial_ends_at 30일 연장
                try:
                    base = datetime.datetime.fromisoformat(str(referrer["trial_ends_at"])) if referrer["trial_ends_at"] else datetime.datetime.utcnow()
                    if base < datetime.datetime.utcnow():
                        base = datetime.datetime.utcnow()
                    new_end = (base + datetime.timedelta(days=30)).isoformat()
                except Exception:
                    new_end = (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat()
                cur.execute(
                    "UPDATE users SET merit_months=%s, plan='trial', trial_ends_at=%s WHERE user_id=%s",
                    (new_merit, new_end, referrer["user_id"])
                )
    conn.commit()
    conn.close()

    plan_status = _get_plan_status("basic", None)
    new_token = _create_jwt(
        current_user["user_id"], bn, current_user["email"], "basic", None
    )

    return {
        "status": "SUCCESS",
        "token": new_token,
        "plan": plan_status,
        "message": "베이직 플랜으로 업그레이드되었습니다.",
    }


@app.get("/api/plan/status")
def api_plan_status(current_user: dict = Depends(_get_current_user)):
    """현재 플랜 상태 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT plan, trial_ends_at FROM users WHERE business_number = %s", (current_user["bn"],))
    user = cursor.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    u = dict(user)
    trial_ends = u.get("trial_ends_at")
    if trial_ends is not None:
        trial_ends = str(trial_ends)
    return {
        "status": "SUCCESS",
        "plan": _get_plan_status(u.get("plan") or "trial", trial_ends),
    }


class AdminAuthRequest(BaseModel):
    password: str


ADMIN_TOKEN_SECRET = os.getenv("ADMIN_PASSWORD", "fallback")


def _create_admin_token() -> str:
    payload = ADMIN_TOKEN_SECRET.encode()
    return hmac.new(payload, b"admin-session", hashlib.sha256).hexdigest()


def _verify_admin(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
    token = authorization.split(" ", 1)[1]
    expected = _create_admin_token()
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")


@app.post("/api/admin/auth")
def admin_auth(request: AdminAuthRequest):
    admin_pw = os.getenv("ADMIN_PASSWORD", "")
    if not admin_pw:
        raise HTTPException(status_code=500, detail="ADMIN_PASSWORD가 설정되지 않았습니다.")
    if request.password != admin_pw:
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")
    token = _create_admin_token()
    return {"status": "SUCCESS", "token": token}


@app.get("/api/admin/users", dependencies=[Depends(_verify_admin)])
def get_admin_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.user_id, u.business_number, u.company_name, u.address_city,
               u.industry_code, u.revenue_bracket, u.employee_count_bracket, u.updated_at,
               ns.email, ns.channel, ns.is_active as notify_active
        FROM users u
        LEFT JOIN notification_settings ns ON u.business_number = ns.business_number
        ORDER BY u.updated_at DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"status": "SUCCESS", "data": rows}


@app.delete("/api/admin/users/{user_id}", dependencies=[Depends(_verify_admin)])
def delete_admin_user(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT business_number FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    if row:
        bn = row["business_number"]
        cursor.execute("DELETE FROM notification_settings WHERE business_number = %s", (bn,))
    cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "사용자 삭제 완료"}


@app.get("/api/admin/stats", dependencies=[Depends(_verify_admin)])
def get_admin_stats():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM announcements")
    total = cursor.fetchone()["count"]

    cursor.execute("""
        SELECT origin_source, COUNT(*) as cnt
        FROM announcements
        WHERE origin_source IS NOT NULL AND origin_source != ''
        GROUP BY origin_source
        ORDER BY cnt DESC
    """)
    by_source = [{"source": r["origin_source"], "count": r["cnt"]} for r in cursor.fetchall()]

    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) FROM admin_urls WHERE is_active = true")
    active_urls = cursor.fetchone()["count"]

    conn.close()
    return {
        "status": "SUCCESS",
        "data": {
            "total_announcements": total,
            "by_source": by_source,
            "user_count": user_count,
            "active_manual_urls": active_urls,
        }
    }


@app.get("/api/admin/system-sources", dependencies=[Depends(_verify_admin)])
def get_system_sources():
    from app.services.public_api_service import gov_api_service
    is_live = gov_api_service.is_configured()

    apis = [
        {
            "id": "kised-api", "name": "K-Startup 공식 API", "type": "API",
            "status": "LIVE" if is_live else "SIMULATED",
            "description": "중소벤처기업부 창업지원사업 통합 데이터"
        },
        {
            "id": "msit-rnd-api", "name": "과기정통부 R&D 사업공고 API", "type": "API",
            "status": "LIVE" if is_live else "SIMULATED",
            "description": "과학기술정보통신부 국가R&D 사업공고 (data.go.kr)"
        },
        {
            "id": "mss-api", "name": "중소벤처기업부 사업공고 API", "type": "API",
            "status": "LIVE" if is_live else "SIMULATED",
            "description": "중소벤처기업부 공식 사업공고 조회"
        },
        {
            "id": "bizinfo-portal-api", "name": "기업마당 포털 API", "type": "API",
            "status": "LIVE" if os.getenv("BIZINFO_PORTAL_KEY") else "KEY_REQUIRED",
            "description": "기업마당 포털 직접 연동 API (bizinfoApi.do)"
        },
        {
            "id": "smes24-api", "name": "중소벤처24 공고정보 API", "type": "API",
            "status": "LIVE" if os.getenv("SMES24_API_TOKEN") else "KEY_REQUIRED",
            "description": "중소벤처24 사업공고 (자격요건 구조화 데이터 포함)"
        },
        {
            "id": "foodpolis-api", "name": "한국식품산업클러스터진흥원 API", "type": "API",
            "status": "LIVE" if os.getenv("FOODPOLIS_API_KEY") else "KEY_REQUIRED",
            "description": "식품산업 관련 사업공고 (foodpolis.kr)"
        },
    ]

    scrapers = [
        {
            "id": "sbc", "name": "중진공(SBC) 스크래퍼", "type": "Scraper",
            "status": "ACTIVE",
            "description": "중소벤처기업진흥공단 공고 Playwright 크롤링 (공식 API 미제공)"
        },
    ]

    return {
        "status": "SUCCESS",
        "data": {"apis": apis, "scrapers": scrapers}
    }

@app.get("/api/admin/urls", dependencies=[Depends(_verify_admin)])
def get_admin_urls():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admin_urls")
    rows = cursor.fetchall()
    conn.close()
    return {"status": "SUCCESS", "data": [dict(r) for r in rows]}

@app.post("/api/admin/urls", dependencies=[Depends(_verify_admin)])
def add_admin_url(request: AdminURLRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO admin_urls (url, source_name) VALUES (%s, %s)",
                     (request.url, request.source_name))
        conn.commit()
        return {"status": "SUCCESS", "message": "URL 등록 완료"}
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="이미 등록된 URL입니다.")
    finally:
        conn.close()

@app.delete("/api/admin/urls/{url_id}", dependencies=[Depends(_verify_admin)])
def delete_admin_url(url_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admin_urls WHERE id = %s", (url_id,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "URL 삭제 완료"}

async def _run_manual_sync():
    manual_sync_status["running"] = True
    manual_sync_status["last_result"] = "진행 중..."
    manual_sync_status["last_time"] = datetime.datetime.now().isoformat()
    try:
        await admin_scraper.run_all()
        manual_sync_status["last_result"] = "완료"
    except Exception as e:
        manual_sync_status["last_result"] = f"오류: {e}"
    finally:
        manual_sync_status["running"] = False
        manual_sync_status["last_time"] = datetime.datetime.now().isoformat()


@app.post("/api/admin/sync-manual", dependencies=[Depends(_verify_admin)])
async def trigger_admin_sync(background_tasks: BackgroundTasks):
    if manual_sync_status["running"]:
        return {"status": "ALREADY_RUNNING", "message": "수동 동기화가 이미 진행 중입니다."}
    background_tasks.add_task(_run_manual_sync)
    return {"status": "STARTED", "message": "백그라운드에서 수동 동기화를 시작합니다."}


@app.get("/api/admin/sync-manual-status", dependencies=[Depends(_verify_admin)])
def get_manual_sync_status():
    return {"status": "SUCCESS", "data": manual_sync_status}

async def _run_reanalyze(limit: int):
    import re as _re
    from app.services.ai_service import ai_service as _ai

    def _strip(text):
        if not text:
            return ""
        text = _re.sub(r'<[^>]+>', ' ', text)
        text = _re.sub(r'&[a-z]+;', ' ', text)
        text = _re.sub(r'&#\d+;', ' ', text)
        text = _re.sub(r'\s+', ' ', text)
        return text.strip()

    reanalyze_status["running"] = True
    reanalyze_status["done"] = 0
    reanalyze_status["last_time"] = datetime.datetime.now().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT announcement_id, title, summary_text
        FROM announcements
        WHERE eligibility_logic IS NULL OR eligibility_logic = '' OR eligibility_logic = '{}'
        ORDER BY announcement_id
        LIMIT %s
    """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    reanalyze_status["total"] = len(rows)

    success = 0
    for row in rows:
        try:
            clean = _strip(row.get("summary_text", ""))
            input_text = f"제목: {row.get('title', '')}\n\n내용: {clean[:8000]}"
            if len(clean) < 20 and len(row.get("title", "")) < 10:
                reanalyze_status["done"] += 1
                continue
            details = await _ai.extract_program_details(input_text)
            if details:
                elig = details.get("eligibility_logic", {}) or {}
                if details.get("business_type"):
                    elig["business_type"] = details["business_type"]
                if details.get("target_keywords"):
                    elig["target_keywords"] = details["target_keywords"]
                ai_summary = details.get("summary_text") or details.get("description", "")
                pk = row.get("announcement_id")
                cursor.execute("""
                    UPDATE announcements SET
                        eligibility_logic = %s,
                        summary_text = CASE WHEN %s != '' THEN %s ELSE summary_text END,
                        department = CASE WHEN department IS NULL OR department = '' THEN %s ELSE department END,
                        category = CASE WHEN category IS NULL OR category = '' THEN %s ELSE category END,
                        deadline_date = CASE WHEN deadline_date IS NULL AND %s IS NOT NULL THEN %s ELSE deadline_date END
                    WHERE announcement_id = %s
                """, (
                    json.dumps(elig, ensure_ascii=False),
                    ai_summary, ai_summary,
                    details.get("department", ""),
                    details.get("category", ""),
                    details.get("deadline_date"), details.get("deadline_date"),
                    pk,
                ))
                conn.commit()
                success += 1
        except Exception as e:
            print(f"Reanalyze error: {e}")
        reanalyze_status["done"] += 1
        await asyncio.sleep(0.5)

    conn.close()
    reanalyze_status["running"] = False
    reanalyze_status["last_result"] = f"완료: {success}/{len(rows)}건 분석"
    reanalyze_status["last_time"] = datetime.datetime.now().isoformat()


@app.post("/api/admin/reanalyze", dependencies=[Depends(_verify_admin)])
async def trigger_reanalyze(background_tasks: BackgroundTasks, limit: int = 200):
    if reanalyze_status["running"]:
        return {"status": "ALREADY_RUNNING", "message": "재분석이 이미 진행 중입니다."}
    background_tasks.add_task(_run_reanalyze, limit)
    return {"status": "STARTED", "message": f"최대 {limit}건 백그라운드 재분석 시작"}


@app.get("/api/admin/reanalyze-status", dependencies=[Depends(_verify_admin)])
def get_reanalyze_status():
    return {"status": "SUCCESS", "data": reanalyze_status}


@app.get("/")
def read_root():
    return {"message": "Welcome to Auto_Gov_Macting API"}

@app.post("/api/industry-recommend")
async def api_industry_recommend(request: CompanyNameRequest):
    """기업명과 사업 내용을 기반으로 DB 검색 + AI 보완 하이브리드 추천 업종 후보군을 반환합니다."""
    from app.services.ai_service import ai_service
    # Use business_content if available, otherwise fallback to company_name
    query = request.business_content if request.business_content else request.company_name
    result = await ai_service.search_industry_hybrid(query)
    return {"status": "SUCCESS", "data": result}

@app.post("/api/check-url")
def api_check_url(request: URLRequest):
    result = check_duplicate_url(request.url)
    return {
        "status": "SUCCESS",
        "is_duplicate": result["status"] == "ALREADY_EXISTS",
        "detail": result
    }

def is_update_required(business_number: str, updated_at) -> bool:
    """
    Checks if revenue update is required based on Korean tax deadlines.
    - Corporations: April (4)
    - Individuals: June (6)
    """
    try:
        # Business number middle digits: 81, 82, 86, 87, 88 are usually corps
        middle = int(business_number[3:5])
        is_corp = middle in [81, 82, 86, 87, 88]

        current_date = datetime.datetime.now()
        update_month = 4 if is_corp else 6

        # Parse updated_at
        if isinstance(updated_at, datetime.datetime):
            last_updated = updated_at
        else:
            last_updated = datetime.datetime.strptime(str(updated_at)[:19], "%Y-%m-%d %H:%M:%S")

        # If we are past the update month in the current year,
        # but the data was updated in a previous year (or before the update month of this year).
        if current_date.month >= update_month:
            if last_updated.year < current_date.year:
                return True
        return False
    except Exception:
        return False

@app.post("/api/fetch-company")
def api_fetch_company(request: BusinessNumberRequest):
    if len(request.business_number) != 10:
        raise HTTPException(status_code=400, detail="사업자 번호는 10자리여야 합니다.")

    # 1. Check DB first
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE business_number = %s", (request.business_number,))
    user = cursor.fetchone()
    conn.close()

    if user:
        user_dict = dict(user)
        requires_update = is_update_required(user_dict["business_number"], user_dict["updated_at"])
        return {
            "status": "SUCCESS",
            "type": "EXISTING",
            "data": {
                "business_number": user_dict["business_number"],
                "company_name": user_dict["company_name"],
                "establishment_date": str(user_dict["establishment_date"]) if user_dict.get("establishment_date") else "",
                "address_city": user_dict["address_city"],
                "industry_code": user_dict["industry_code"],
                "revenue": user_dict["revenue_bracket"],
                "employees": user_dict["employee_count_bracket"]
            },
            "requires_update": requires_update
        }

    # 2. If not found, return NEW immediately (Bypass slow API/AI)
    is_corp = int(request.business_number[3:5]) in [81, 82, 86, 87, 88]

    return {
        "status": "SUCCESS",
        "type": "NEW",
        "data": {
            "business_number": request.business_number,
            "company_name": "(신규 기업 등록 중)",
            "establishment_date": datetime.date.today().isoformat(),
            "address_city": "전국",
            "industry_code": "00000",
            "revenue": "UNDER_1B",
            "employees": "UNDER_10",
            "is_corp": is_corp
        }
    }

@app.post("/api/save-profile")
def api_save_profile(profile: UserProfile):
    """
    UPSERT logic for user profile.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
        INSERT INTO users (business_number, company_name, establishment_date, address_city, industry_code, revenue_bracket, employee_count_bracket, interests)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(business_number) DO UPDATE SET
            company_name=EXCLUDED.company_name,
            establishment_date=EXCLUDED.establishment_date,
            address_city=EXCLUDED.address_city,
            industry_code=EXCLUDED.industry_code,
            revenue_bracket=EXCLUDED.revenue_bracket,
            employee_count_bracket=EXCLUDED.employee_count_bracket,
            interests=EXCLUDED.interests
        """
        cursor.execute(query, (
            profile.business_number, profile.company_name, profile.establishment_date,
            profile.address_city, profile.industry_code, profile.revenue_bracket,
            profile.employee_count_bracket, profile.interests
        ))
        conn.commit()
        return {"status": "SUCCESS", "message": "프로필이 저장되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

from app.services.sync_service import sync_service

async def _run_sync():
    sync_status["running"] = True
    sync_status["last_result"] = "진행 중..."
    sync_status["last_time"] = datetime.datetime.now().isoformat()
    try:
        await sync_service.sync_all()
        sync_status["last_result"] = "완료"
    except Exception as e:
        sync_status["last_result"] = f"오류: {e}"
    finally:
        sync_status["running"] = False
        sync_status["last_time"] = datetime.datetime.now().isoformat()


@app.post("/api/sync", dependencies=[Depends(_verify_admin)])
async def api_sync_data(background_tasks: BackgroundTasks):
    if sync_status["running"]:
        return {"status": "ALREADY_RUNNING", "message": "동기화가 이미 진행 중입니다."}
    background_tasks.add_task(_run_sync)
    return {"status": "STARTED", "message": "백그라운드에서 동기화를 시작합니다."}


@app.get("/api/admin/sync-status", dependencies=[Depends(_verify_admin)])
def get_sync_status():
    return {"status": "SUCCESS", "data": sync_status}

class PushSubscription(BaseModel):
    business_number: Optional[str] = None
    endpoint: str
    keys: dict


@app.get("/api/push/vapid-key")
def get_vapid_key():
    pub = os.getenv("VAPID_PUBLIC_KEY", "")
    return {"publicKey": pub}


@app.post("/api/push/subscribe")
def push_subscribe(sub: PushSubscription):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO push_subscriptions (business_number, endpoint, p256dh, auth)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT(endpoint) DO UPDATE SET
               business_number=EXCLUDED.business_number,
               p256dh=EXCLUDED.p256dh,
               auth=EXCLUDED.auth""",
        (sub.business_number, sub.endpoint, sub.keys.get("p256dh", ""), sub.keys.get("auth", ""))
    )
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "푸시 알림 구독 완료"}


@app.post("/api/push/unsubscribe")
def push_unsubscribe(data: dict):
    endpoint = data.get("endpoint", "")
    if not endpoint:
        raise HTTPException(status_code=400, detail="endpoint 필수")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM push_subscriptions WHERE endpoint = %s", (endpoint,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "푸시 알림 해제 완료"}


@app.post("/api/admin/push-test", dependencies=[Depends(_verify_admin)])
def admin_push_test():
    from pywebpush import webpush, WebPushException
    vapid_private = os.getenv("VAPID_PRIVATE_KEY", "")
    vapid_claims = {"sub": os.getenv("VAPID_CLAIMS_EMAIL", "mailto:admin@example.com")}

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT endpoint, p256dh, auth FROM push_subscriptions")
    subs = cursor.fetchall()
    conn.close()

    sent = 0
    failed = 0
    payload = json.dumps({
        "title": "AI 맞춤 정부지원금 매칭",
        "body": "새로운 맞춤 공고가 등록되었습니다!",
        "url": "/",
    }, ensure_ascii=False)

    for sub in subs:
        try:
            webpush(
                subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims=vapid_claims,
            )
            sent += 1
        except WebPushException:
            failed += 1

    return {"status": "SUCCESS", "message": f"발송 {sent}건, 실패 {failed}건"}


@app.post("/api/match")
def api_match_programs(request: BusinessNumberRequest):
    """
    Fetches user profile and runs the hybrid matching engine.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE business_number = %s", (request.business_number,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")

    user_dict = dict(user)
    print(f"DEBUG: Matching requested for BN={request.business_number}, Profile={user_dict}")
    matches = get_matches_for_user(user_dict)
    print(f"DEBUG: Matcher returned {len(matches)} results")

    # AI 추출 데이터 보완 (프론트엔드 대응)
    for match in matches:
        if match.get("eligibility_logic") and isinstance(match["eligibility_logic"], str):
            try:
                match["eligibility_logic"] = json.loads(match["eligibility_logic"])
            except (json.JSONDecodeError, TypeError):
                pass

    return {"status": "SUCCESS", "data": matches}

@app.post("/api/notification-settings")
def api_save_notification_settings(settings: NotificationSettings):
    """
    Saves or updates user notification preferences.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
        INSERT INTO notification_settings (business_number, email, phone_number, channel, is_active)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT(business_number) DO UPDATE SET
            email=EXCLUDED.email,
            phone_number=EXCLUDED.phone_number,
            channel=EXCLUDED.channel,
            is_active=EXCLUDED.is_active,
            updated_at=NOW()
        """
        cursor.execute(query, (
            settings.business_number, settings.email, settings.phone_number,
            settings.channel, settings.is_active
        ))
        conn.commit()
        return {"status": "SUCCESS", "message": "알림 설정이 저장되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/notification-settings/{bn}")
def api_get_notification_settings(bn: str):
    """
    Retrieves user notification preferences.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notification_settings WHERE business_number = %s", (bn,))
    settings = cursor.fetchone()
    conn.close()

    if settings:
        return {"status": "SUCCESS", "data": dict(settings)}
    else:
        # Return default empty settings if not found
        return {
            "status": "SUCCESS",
            "data": {
                "business_number": bn,
                "email": "",
                "phone_number": "",
                "channel": "BOTH",
                "is_active": 1
            }
        }

@app.post("/api/admin/send-digest", dependencies=[Depends(_verify_admin)])
async def api_send_digest():
    """데일리 다이제스트를 즉시 생성하고 이메일 발송 (관리자용)"""
    from app.services.notification_service import notification_service
    results = await notification_service.generate_daily_digest()
    sent_count = sum(1 for r in results if r.get("email_sent"))
    return {
        "status": "SUCCESS",
        "message": f"다이제스트 생성 완료: {len(results)}명 대상, {sent_count}건 이메일 발송",
        "data": results
    }


class SavedBulk(BaseModel):
    business_number: str
    announcement_ids: List[int]


@app.post("/api/saved/bulk")
def api_save_bulk(body: SavedBulk):
    conn = get_db_connection()
    cursor = conn.cursor()
    inserted = 0
    try:
        for aid in body.announcement_ids:
            try:
                cursor.execute(
                    """INSERT INTO saved_announcements (business_number, announcement_id)
                       VALUES (%s, %s)
                       ON CONFLICT (business_number, announcement_id) DO NOTHING""",
                    (body.business_number, aid),
                )
                inserted += cursor.rowcount
            except psycopg2.IntegrityError:
                conn.rollback()
        conn.commit()
    finally:
        conn.close()
    return {"status": "SUCCESS", "message": f"{inserted}건 저장됨", "inserted": inserted}


@app.get("/api/saved/{bn}")
def api_get_saved(bn: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sa.id, sa.announcement_id, sa.memo, sa.saved_at,
               a.title, a.deadline_date, a.origin_url, a.department,
               a.category, a.support_amount, a.origin_source
        FROM saved_announcements sa
        JOIN announcements a ON sa.announcement_id = a.announcement_id
        WHERE sa.business_number = %s
        ORDER BY a.deadline_date ASC NULLS LAST
    """, (bn,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"status": "SUCCESS", "data": rows}


@app.delete("/api/saved/{saved_id}")
def api_delete_saved(saved_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_announcements WHERE id = %s", (saved_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    if deleted:
        return {"status": "SUCCESS", "message": "삭제됨"}
    raise HTTPException(status_code=404, detail="해당 저장 항목을 찾을 수 없습니다.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
