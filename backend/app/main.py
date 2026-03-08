import sys
import os
import asyncio

# Windows에서 Playwright(Subprocess)를 사용하기 위한 Event Loop 정책 설정
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import datetime
import json
from app.core.url_checker import check_duplicate_url
from app.services.business_api import get_company_profile
from app.core.matcher import get_matches_for_user

DB_PATH = "gov_matching.db"

# Admin Scraper Import for Manual Sync
from app.services.admin_scraper import admin_scraper


def init_database():
    """DB 테이블 생성 및 기존 테이블에 누락 컬럼 마이그레이션"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    with open("app/db/init.sql", "r", encoding="utf-8") as f:
        cursor.executescript(f.read())

    ksic_path = "app/db/ksic_metadata.sql"
    if os.path.exists(ksic_path):
        with open(ksic_path, "r", encoding="utf-8") as f:
            try:
                cursor.executescript(f.read())
            except sqlite3.OperationalError:
                pass

    migration_columns = {
        "announcements": [
            ("eligibility_logic", "TEXT"),
            ("department", "VARCHAR(255)"),
            ("category", "VARCHAR(100)"),
            ("origin_source", "VARCHAR(100)"),
        ]
    }
    for table, columns in migration_columns.items():
        existing = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
        for col_name, col_type in columns:
            if col_name not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                print(f"  Migration: added {col_name} to {table}")

    conn.commit()
    conn.close()


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
        print(f"📅 Scheduler: next digest at {target.isoformat()} (in {wait_seconds/3600:.1f}h)")
        await asyncio.sleep(wait_seconds)
        try:
            print("📬 Running scheduled daily digest...")
            results = await notification_service.generate_daily_digest()
            sent = sum(1 for r in results if r.get("email_sent"))
            print(f"📬 Digest complete: {len(results)} users, {sent} emails sent")
        except Exception as e:
            print(f"❌ Scheduled digest error: {e}")


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(_daily_digest_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Gov Support Matching Assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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

@app.get("/api/admin/system-sources")
def get_system_sources():
    from app.services.public_api_service import gov_api_service
    is_live = gov_api_service.is_configured()
    return {
        "status": "SUCCESS",
        "data": [
            {
                "id": "k-startup",
                "name": "K-Startup 공식 API",
                "type": "API",
                "status": "LIVE" if is_live else "SIMULATED",
                "description": "중소벤처기업부 창업지원사업 통합 데이터"
            },
            {
                "id": "msit-rnd",
                "name": "과기정통부 R&D 사업공고 API",
                "type": "API",
                "status": "LIVE" if is_live else "SIMULATED",
                "description": "과학기술정보통신부 국가R&D 사업공고 (data.go.kr 15074634)"
            },
            {
                "id": "bizinfo",
                "name": "기업마당 (Bizinfo)",
                "type": "Portal API",
                "status": "LIVE (API)",
                "description": "기업마당 포털 직접 연동 API (bizinfoApi.do) 실시간 수집"
            },
            {
                "id": "smes24",
                "name": "중소벤처24 공고정보 API",
                "type": "API",
                "status": "LIVE" if os.getenv("SMES24_API_TOKEN") else "KEY_REQUIRED",
                "description": "중소벤처24 사업공고 (자격요건 구조화 데이터 포함)"
            },
            {
                "id": "foodpolis",
                "name": "한국식품산업클러스터진흥원 API",
                "type": "API",
                "status": "LIVE" if os.getenv("FOODPOLIS_API_KEY") else "KEY_REQUIRED",
                "description": "식품산업 관련 사업공고 (foodpolis.kr)"
            }
        ]
    }

@app.get("/api/admin/urls")
def get_admin_urls():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admin_urls")
    rows = cursor.fetchall()
    conn.close()
    return {"status": "SUCCESS", "data": [dict(r) for r in rows]}

@app.post("/api/admin/urls")
def add_admin_url(request: AdminURLRequest):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO admin_urls (url, source_name) VALUES (?, ?)", 
                     (request.url, request.source_name))
        conn.commit()
        return {"status": "SUCCESS", "message": "URL 등록 완료"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="이미 등록된 URL입니다.")
    finally:
        conn.close()

@app.delete("/api/admin/urls/{url_id}")
def delete_admin_url(url_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admin_urls WHERE id = ?", (url_id,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "URL 삭제 완료"}

@app.post("/api/admin/sync-manual")
async def trigger_admin_sync():
    # 비동기로 실행하거나 즉시 실행 (데모를 위해 즉시 실행)
    await admin_scraper.run_all()
    return {"status": "SUCCESS", "message": "수동 동기화 완료"}

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

def is_update_required(business_number: str, updated_at: str) -> bool:
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
        
        # Parse updated_at (SQLite CURRENT_TIMESTAMP is YYYY-MM-DD HH:MM:SS)
        last_updated = datetime.datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
        
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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE business_number = ?", (request.business_number,))
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
                "establishment_date": user_dict["establishment_date"],
                "address_city": user_dict["address_city"],
                "industry_code": user_dict["industry_code"],
                "revenue": user_dict["revenue_bracket"],
                "employees": user_dict["employee_count_bracket"]
            },
            "requires_update": requires_update
        }
    
    # 2. If not found, return NEW immediately (Bypass slow API/AI)
    # Extract some info from biz_number if possible (e.g., individual/corp)
    # Middle: 81, 86, 87 (Corp), 01~79 (Individual)
    is_corp = int(request.business_number[3:5]) in [81, 82, 86, 87, 88]
    
    return {
        "status": "SUCCESS",
        "type": "NEW",
        "data": {
            "business_number": request.business_number,
            "company_name": "(신규 기업 등록 중)",
            "establishment_date": datetime.date.today().isoformat(), # Default to today
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        query = """
        INSERT INTO users (business_number, company_name, establishment_date, address_city, industry_code, revenue_bracket, employee_count_bracket, interests)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(business_number) DO UPDATE SET
            company_name=excluded.company_name,
            establishment_date=excluded.establishment_date,
            address_city=excluded.address_city,
            industry_code=excluded.industry_code,
            revenue_bracket=excluded.revenue_bracket,
            employee_count_bracket=excluded.employee_count_bracket,
            interests=excluded.interests
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

@app.post("/api/sync")
async def api_sync_data():
    """
    모든 스크래퍼를 실행하여 최신 공고 데이터를 수집하고 AI 분석을 수행합니다.
    """
    try:
        # 백그라운드 태스크로 실행하는 것이 좋으나, 데모를 위해 직접 실행
        await sync_service.sync_all()
        return {"status": "SUCCESS", "message": "데이터 동기화 및 AI 분석이 완료되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/match")
def api_match_programs(request: BusinessNumberRequest):
    """
    Fetches user profile and runs the hybrid matching engine.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE business_number = ?", (request.business_number,))
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
    conn = sqlite3.connect("gov_matching.db")
    cursor = conn.cursor()
    try:
        query = """
        INSERT INTO notification_settings (business_number, email, phone_number, channel, is_active)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(business_number) DO UPDATE SET
            email=excluded.email,
            phone_number=excluded.phone_number,
            channel=excluded.channel,
            is_active=excluded.is_active,
            updated_at=CURRENT_TIMESTAMP
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
    conn = sqlite3.connect("gov_matching.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notification_settings WHERE business_number = ?", (bn,))
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

@app.post("/api/admin/send-digest")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
