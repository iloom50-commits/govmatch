import sys
import os
import asyncio

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import psycopg2
import psycopg2.extras
import psycopg2.pool
import datetime
import time
import json
import hmac
import hashlib
import jwt
import bcrypt
from app.core.url_checker import check_duplicate_url
from app.core.matcher import get_matches_for_user, get_individual_matches_for_user
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


# ── DB 커넥션 풀 (동시접속 대응) ──
_db_pool = None
_db_pool_lock = __import__("threading").Lock()

def _get_pool():
    global _db_pool
    if _db_pool is None or _db_pool.closed:
        with _db_pool_lock:
            if _db_pool is None or _db_pool.closed:
                _db_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=15,
                    dsn=DATABASE_URL,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                )
    return _db_pool

def get_db_connection():
    try:
        pool = _get_pool()
        conn = pool.getconn()
        conn.autocommit = False
        # close() → 풀 반환으로 래핑
        _orig_close = conn.close.__func__ if hasattr(conn.close, '__func__') else None
        def _return():
            try:
                if not conn.closed:
                    conn.rollback()  # 미완료 트랜잭션 정리
                pool.putconn(conn)
            except Exception:
                try:
                    pool.putconn(conn, close=True)
                except Exception:
                    pass
        conn.close = _return
        return conn
    except Exception:
        # 풀 실패 시 직접 연결 (폴백)
        return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def init_database():
    """DB 연결 확인 + 누락 테이블 자동 생성"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")

        # notification_settings 테이블이 없으면 자동 생성 (SQLite→PostgreSQL 마이그레이션 대비)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_settings (
                id SERIAL PRIMARY KEY,
                business_number VARCHAR(20) UNIQUE NOT NULL,
                email VARCHAR(100),
                phone_number VARCHAR(20),
                channel VARCHAR(20) DEFAULT 'email',
                is_active BOOLEAN DEFAULT true,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # SQLite에서 마이그레이션된 기존 테이블의 INTEGER→BOOLEAN 변환 시도
        for tbl, col in [("notification_settings", "is_active"), ("admin_urls", "is_active")]:
            try:
                cursor.execute("""
                    SELECT data_type FROM information_schema.columns
                    WHERE table_name = %s AND column_name = %s
                """, (tbl, col))
                row = cursor.fetchone()
                if row and row.get("data_type") == "integer":
                    cursor.execute(f"""
                        ALTER TABLE {tbl}
                        ALTER COLUMN {col} SET DATA TYPE BOOLEAN
                        USING CASE WHEN {col} = 1 THEN true ELSE false END
                    """)
                    conn.commit()
                    print(f"  Migrated {tbl}.{col}: INTEGER -> BOOLEAN")
            except Exception as e:
                conn.rollback()
                print(f"  Note: {tbl}.{col} migration skipped: {e}")
        # ai_analyzed_at 컬럼 추가 (중복 AI 분석 방지용 타임스탬프)
        try:
            cursor.execute("""
                ALTER TABLE announcements ADD COLUMN IF NOT EXISTS ai_analyzed_at TIMESTAMP
            """)
            conn.commit()
        except Exception:
            conn.rollback()

        # billing_key 컬럼 추가 (정기결제용)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_key TEXT")
            conn.commit()
        except Exception:
            conn.rollback()

        # custom_needs 컬럼 추가 (맞춤 알림용 구체적 니즈)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_needs TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            conn.rollback()

        # 개인 매칭용 프로필 컬럼 추가
        for col_def in [
            "gender VARCHAR(10) DEFAULT ''",
            "age_range VARCHAR(20) DEFAULT ''",
            "income_level VARCHAR(30) DEFAULT ''",
            "family_type VARCHAR(30) DEFAULT ''",
            "employment_status VARCHAR(30) DEFAULT ''",
            "founded_date VARCHAR(20) DEFAULT ''",
            "is_pre_founder BOOLEAN DEFAULT FALSE",
            "certifications TEXT DEFAULT ''",
            "custom_keywords TEXT DEFAULT ''",
        ]:
            try:
                col_name = col_def.split()[0]
                cursor.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_def}")
                conn.commit()
            except Exception:
                conn.rollback()

        # kakao_refresh_token 컬럼 추가 (카카오톡 메시지 발송용)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS kakao_refresh_token TEXT")
            conn.commit()
        except Exception:
            conn.rollback()

        # kakao_enabled 컬럼 추가 (카카오톡 알림 설정)
        try:
            cursor.execute("ALTER TABLE notification_settings ADD COLUMN IF NOT EXISTS kakao_enabled INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            conn.rollback()

        # client_profiles에 client_type 컬럼 추가 (기업/개인 구분)
        try:
            cursor.execute("ALTER TABLE client_profiles ADD COLUMN IF NOT EXISTS client_type VARCHAR(20) DEFAULT 'business'")
            conn.commit()
        except Exception:
            conn.rollback()

        # keyword_synonyms 테이블 생성 + 초기 데이터
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keyword_synonyms (
                id SERIAL PRIMARY KEY,
                group_name TEXT NOT NULL,
                keyword TEXT NOT NULL,
                target_type VARCHAR(20) DEFAULT 'both',
                UNIQUE(group_name, keyword)
            )
        """)
        conn.commit()
        _seed_keyword_synonyms(conn)

        # 사용자 행동 이벤트 로그 테이블
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_events (
                    id SERIAL PRIMARY KEY,
                    business_number VARCHAR(20),
                    event_type VARCHAR(50) NOT NULL,
                    event_detail TEXT DEFAULT '',
                    ip_address VARCHAR(50) DEFAULT '',
                    user_agent TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_events_type ON user_events(event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_events_created ON user_events(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_events_bn ON user_events(business_number)")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS strategy_reports (
                    id SERIAL PRIMARY KEY,
                    report_type VARCHAR(50) NOT NULL DEFAULT 'weekly',
                    report_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 시스템 활동 이력 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
                    id SERIAL PRIMARY KEY,
                    action VARCHAR(50) NOT NULL,
                    category VARCHAR(30) NOT NULL DEFAULT 'system',
                    detail TEXT DEFAULT '',
                    result VARCHAR(20) DEFAULT 'success',
                    count_affected INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_action ON system_logs(action)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_category ON system_logs(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_created ON system_logs(created_at)")
            conn.commit()
        except Exception:
            conn.rollback()

        conn.commit()
        conn.close()
        print("  DB connection OK (PostgreSQL/Supabase)")
    except Exception as e:
        print(f"  DB connection error (app will continue): {e}")


def _log_system(action: str, category: str = "system", detail: str = "", result: str = "success", count: int = 0):
    """시스템 활동 이력을 DB에 저장 (수집/분석/알림/매칭 등)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO system_logs (action, category, detail, result, count_affected) VALUES (%s, %s, %s, %s, %s)",
            (action[:50], category[:30], (detail or "")[:500], result[:20], count)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _log_event(event_type: str, business_number: str = "", detail: str = "", ip: str = "", ua: str = ""):
    """사용자 행동 이벤트를 DB에 비동기 저장"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO user_events (business_number, event_type, event_detail, ip_address, user_agent) VALUES (%s, %s, %s, %s, %s)",
            (business_number[:20] if business_number else "", event_type, (detail or "")[:500], (ip or "")[:50], (ua or "")[:200])
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # 로깅 실패가 서비스에 영향 주면 안 됨


def _seed_keyword_synonyms(conn):
    """동의어 풀 초기 데이터 (이미 있으면 스킵)"""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS cnt FROM keyword_synonyms")
    if cursor.fetchone()["cnt"] > 0:
        return  # 이미 시드 완료

    seeds = [
        # ── 기업 ──
        ("수출", ["해외진출", "해외인증", "글로벌", "무역", "수출바우처", "해외시장", "통상"], "business"),
        ("창업", ["스타트업", "예비창업", "초기창업", "벤처", "창업지원", "창업보육"], "business"),
        ("스마트", ["스마트공장", "스마트제조", "디지털전환", "DX", "스마트센서"], "business"),
        ("고용", ["채용", "일자리", "인력", "고용장려금", "고용지원", "인력양성"], "business"),
        ("R&D", ["연구개발", "기술개발", "기술혁신", "연구비", "과제"], "business"),
        ("친환경", ["탄소중립", "ESG", "녹색", "에너지절감", "그린", "환경"], "business"),
        ("자금", ["융자", "대출", "보증", "정책자금", "운전자금", "시설자금"], "business"),
        ("마케팅", ["홍보", "판로", "브랜드", "전시회", "박람회", "판매"], "business"),
        ("특허", ["지식재산", "IP", "지재권", "특허출원", "상표"], "business"),
        ("인증", ["ISO", "KC인증", "품질인증", "GMP", "HACCP", "인허가"], "business"),
        ("디지털", ["IT", "소프트웨어", "AI", "빅데이터", "클라우드", "ICT"], "business"),
        ("제조", ["생산", "공장", "제조업", "생산기반", "설비"], "business"),
        ("컨설팅", ["경영컨설팅", "기술컨설팅", "자문", "진단", "멘토링"], "business"),
        # ── 개인 ──
        ("다자녀", ["다둥이", "셋째아이", "3자녀", "다자녀가정", "다자녀가구"], "individual"),
        ("출산", ["임신", "산모", "산후", "분만", "출산장려금", "출산축하금", "출생"], "individual"),
        ("육아", ["보육", "어린이집", "유아", "영아", "아이돌봄", "양육", "돌봄"], "individual"),
        ("장학금", ["학비", "등록금", "학자금", "교육비", "학업장려금"], "individual"),
        ("취업", ["구직", "일자리", "직업훈련", "취준", "직업교육", "취업지원"], "individual"),
        ("주거", ["전세", "임대", "주택", "월세", "주거급여", "주거지원", "임대주택"], "individual"),
        ("노인", ["어르신", "경로", "고령자", "실버", "노후", "연금"], "individual"),
        ("장애", ["장애인", "복지카드", "활동지원", "장애수당", "보조기기"], "individual"),
        ("저소득", ["기초생활", "차상위", "기초수급", "한부모", "긴급복지", "생계급여"], "individual"),
        ("청년", ["청년지원", "청년수당", "청년정책", "MZ", "청년월세"], "individual"),
        ("의료", ["건강", "치료", "병원비", "의료비", "건강검진", "진료비"], "individual"),
        ("교육", ["평생교육", "학습", "훈련", "교육바우처", "배움카드"], "individual"),
        ("문화", ["문화바우처", "여가", "체육", "관광", "문화생활", "공연"], "individual"),
    ]

    for group_name, keywords, target_type in seeds:
        # 대표 키워드도 자기 자신을 포함
        all_kw = [group_name] + keywords
        for kw in all_kw:
            try:
                cursor.execute(
                    "INSERT INTO keyword_synonyms (group_name, keyword, target_type) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (group_name, kw, target_type),
                )
            except Exception:
                pass
    conn.commit()
    print("  [Seed] keyword_synonyms 초기 데이터 삽입 완료")


init_database()


SYNC_HOUR = int(os.environ.get("SYNC_HOUR", "8"))
DIGEST_HOUR = int(os.environ.get("DIGEST_HOUR", "0"))  # UTC 0시 = 한국시간 09시


async def _daily_sync_loop():
    """매일 SYNC_HOUR 시에 공고 수집 → AI 재분석 파이프라인"""
    from app.services.sync_service import SyncService
    sync_service = SyncService()

    while True:
        now = datetime.datetime.now()
        target = now.replace(hour=SYNC_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        print(f"[Scheduler] next sync at {target.isoformat()} (in {wait_seconds/3600:.1f}h)")
        await asyncio.sleep(wait_seconds)
        try:
            # Step 0-A: URL 자동 관리 (누락 등록 + 신규 발견 + 폐기 정리)
            print("[Scheduler] Step 0-A: URL 자동 관리...")
            _auto_seed_urls()
            _discover_new_sources()
            _deactivate_dead_urls()

            # Step 0-B: 구독 자동 갱신 (만료된 빌링키 결제)
            print("[Scheduler] Step 0-B: 구독 자동 갱신...")
            _auto_renew_subscriptions()

            # Step 1: 기업 API 수집 + (월요일만) 개인 복지 전체 동기화
            print("[Scheduler] Step 1/3: 공고 수집 시작...")
            await sync_service.sync_all()
            print("[Scheduler] Step 1/3: 공고 수집 완료")

            # Step 1.5: DB 정리 (비지원사업 제거 + 중복 제거)
            print("[Scheduler] Step 1.5: DB 정리 + 분류...")
            _cleanup_non_support_announcements()
            _deduplicate_announcements()
            _auto_classify_target_type()

            # Step 2a: 지자체복지 상세 보강 (매일 100건씩 점진적)
            print("[Scheduler] Step 2a: 지자체복지 상세 보강...")
            try:
                from app.services.public_api_service import gov_api_service
                await gov_api_service.enrich_local_welfare_details(batch_size=100)
            except Exception as enrich_err:
                print(f"[Scheduler] enrich(local-welfare) error: {enrich_err}")

            # Step 2b: gov24 개인 공고 상세 보강 (매일 100건씩)
            print("[Scheduler] Step 2b: gov24 개인 공고 상세 보강...")
            try:
                await gov_api_service.enrich_gov24_individual_details(batch_size=100)
            except Exception as enrich_err:
                print(f"[Scheduler] enrich(gov24-individual) error: {enrich_err}")

            # Step 3: AI 재분석 — 기업 공고만 (개인 복지는 API 데이터로 보강)
            print("[Scheduler] Step 3/3: AI 재분석 시작 (미분석 기업 공고)...")
            import threading
            t = threading.Thread(target=_run_reanalyze_in_thread, args=(300,), daemon=True)
            t.start()
            print("[Scheduler] Step 3/3: AI 재분석 백그라운드 실행 중")
            _log_system("scheduler_run", "system", "일일 스케줄러 전체 실행 완료", "success")
        except Exception as e:
            _log_system("scheduler_run", "system", f"스케줄러 오류: {e}", "error")
            print(f"[Scheduler] sync error: {e}")


async def _daily_digest_loop():
    """평일 한국시간 09시(UTC 0시)에 매칭 + 이메일/푸시 발송"""
    from app.services.notification_service import notification_service
    while True:
        now = datetime.datetime.utcnow()
        target = now.replace(hour=DIGEST_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        # 평일만 (월~금, UTC 기준 → 한국 요일과 동일)
        while target.weekday() >= 5:  # 5=토, 6=일
            target += datetime.timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        kst_target = target + datetime.timedelta(hours=9)
        weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][kst_target.weekday()]
        print(f"[Scheduler] next digest at KST {kst_target.strftime('%Y-%m-%d')}({weekday_kr}) 09:00 (in {wait_seconds/3600:.1f}h)")
        await asyncio.sleep(wait_seconds)
        try:
            print("[Scheduler] Running scheduled daily digest (평일 09시 KST)...")
            results = await notification_service.generate_daily_digest()
            sent = sum(1 for r in results if r.get("email_sent"))
            push_sent = sum(r.get("push_sent", 0) for r in results)
            print(f"[Scheduler] Digest complete: {len(results)} users, {sent} emails, {push_sent} pushes sent")
        except Exception as e:
            print(f"[Scheduler] digest error: {e}")


def _log_expired_announcements():
    """만료 공고 수만 로그에 기록 (자동 삭제 안 함 — 관리자가 수동 관리)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM announcements WHERE deadline_date IS NOT NULL AND deadline_date < CURRENT_DATE")
        row = cur.fetchone()
        count = row["count"] if row else 0
        cur.execute("SELECT COUNT(*) FROM announcements")
        total = cur.fetchone()["count"]
        print(f"[Info] 공고 현황: 전체 {total}건, 만료 {count}건 (자동 삭제 안 함)")
        conn.close()
    except Exception as e:
        print(f"[Info] expire check error: {e}")


def _auto_seed_urls():
    """seed_regional_urls의 URL을 DB에 자동 등록 (누락분만)"""
    try:
        from app.db.seed_regional_urls import REGIONAL_URLS
        conn = get_db_connection()
        cursor = conn.cursor()
        inserted = 0
        for source_name, url in REGIONAL_URLS:
            try:
                cursor.execute(
                    "INSERT INTO admin_urls (url, source_name, is_active) VALUES (%s, %s, 1) ON CONFLICT (url) DO NOTHING",
                    (url, source_name),
                )
                conn.commit()
                if cursor.rowcount > 0:
                    inserted += 1
            except Exception:
                conn.rollback()
        conn.close()
        if inserted > 0:
            print(f"[auto-seed] {inserted}개 신규 URL 등록 완료 (총 {len(REGIONAL_URLS)}개 중)")
    except Exception as e:
        print(f"[auto-seed] 오류: {e}")


def _discover_new_sources():
    """수집된 공고의 origin_url에서 미등록 도메인을 발견하여 자동 등록"""
    from urllib.parse import urlparse
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. 기존 admin_urls 도메인 목록
        cursor.execute("SELECT url FROM admin_urls WHERE is_active = 1")
        registered_domains = set()
        for row in cursor.fetchall():
            try:
                registered_domains.add(urlparse(row["url"]).netloc.replace("www.", ""))
            except Exception:
                pass

        # 2. 최근 30일 공고의 origin_url에서 도메인 추출
        cursor.execute("""
            SELECT origin_url, COUNT(*) as cnt
            FROM announcements
            WHERE origin_url IS NOT NULL
              AND origin_url != ''
              AND created_at >= CURRENT_DATE - INTERVAL '30 days'
              AND COALESCE(target_type, 'business') = 'business'
            GROUP BY origin_url
        """)
        domain_count = {}
        for row in cursor.fetchall():
            try:
                parsed = urlparse(row["origin_url"])
                domain = parsed.netloc.replace("www.", "")
                if domain and "." in domain and domain.endswith(".kr"):
                    domain_count[domain] = domain_count.get(domain, 0) + row["cnt"]
            except Exception:
                pass

        # 3. 미등록 도메인 중 공고 3건 이상인 것만 후보
        new_domains = []
        for domain, cnt in domain_count.items():
            if domain not in registered_domains and cnt >= 3:
                new_domains.append((domain, cnt))

        # 4. 신규 도메인 자동 등록 (루트 URL로)
        inserted = 0
        for domain, cnt in sorted(new_domains, key=lambda x: -x[1])[:20]:  # 상위 20개
            source_name = domain.split(".")[0].upper() if domain else "Unknown"
            url = f"https://www.{domain}" if not domain.startswith("www.") else f"https://{domain}"
            try:
                cursor.execute(
                    "INSERT INTO admin_urls (url, source_name, is_active) VALUES (%s, %s, 1) ON CONFLICT (url) DO NOTHING",
                    (url, f"[자동발견] {source_name} ({cnt}건)"),
                )
                conn.commit()
                if cursor.rowcount > 0:
                    inserted += 1
                    print(f"[discover] 신규 소스 발견: {domain} ({cnt}건)")
            except Exception:
                conn.rollback()

        conn.close()
        if inserted > 0:
            print(f"[discover] {inserted}개 신규 소스 자동 등록")
        else:
            print(f"[discover] 신규 소스 없음 (후보 {len(new_domains)}개 검토)")
    except Exception as e:
        print(f"[discover] 오류: {e}")


def _cleanup_non_support_announcements():
    """DB에서 지원사업이 아닌 공고 제거 (정보공개, 결과 발표 등)"""
    NON_SUPPORT_PATTERNS = [
        "업무추진비", "사용내역", "사용 내역", "회의록", "의사록",
        "결산", "예산서", "감사결과", "인사발령",
        "입찰결과", "낙찰자", "계약현황", "계약체결", "개찰결과",
        "채용결과", "합격자 발표", "선정결과 발표",
        "행사 후기", "수료식", "시상식",
        "취소공고", "취소 공고", "철회",
    ]
    EXCEPTIONS = ["모집", "참여기업", "참여자", "신청", "접수", "공모"]
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        deleted = 0
        for pattern in NON_SUPPORT_PATTERNS:
            cur.execute(
                "SELECT announcement_id, title FROM announcements WHERE title ILIKE %s",
                (f"%{pattern}%",)
            )
            for row in cur.fetchall():
                title = row["title"]
                # 예외 키워드 확인
                if any(exc in title for exc in EXCEPTIONS):
                    continue
                cur.execute("DELETE FROM announcements WHERE announcement_id = %s", (row["announcement_id"],))
                deleted += 1
            conn.commit()
        conn.close()
        if deleted > 0:
            print(f"[cleanup] 비지원사업 공고 {deleted}건 삭제")
    except Exception as e:
        print(f"[cleanup] 오류: {e}")


def _auto_classify_target_type():
    """기존 공고의 target_type을 키워드 기반으로 자동 분류 (business→individual/both)"""
    INDIVIDUAL_KEYWORDS = [
        "다자녀", "다둥이", "출산", "임신", "산모", "육아", "보육", "어린이집",
        "장학금", "학비", "등록금", "학자금",
        "취업지원", "구직", "직업훈련", "취업성공",
        "주거급여", "전세", "임대주택", "월세지원", "주거지원",
        "노인", "어르신", "경로", "고령자", "연금",
        "장애인", "장애수당", "활동지원", "보조기기",
        "기초생활", "차상위", "한부모", "긴급복지", "생계급여", "저소득",
        "청년수당", "청년월세", "청년정책", "청년지원",
        "의료비", "건강검진", "진료비", "병원비",
        "교육바우처", "평생교육", "배움카드",
        "문화바우처", "문화생활",
    ]
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT announcement_id, title, category FROM announcements WHERE COALESCE(target_type, 'business') = 'business'")
        updated = 0
        for row in cur.fetchall():
            title = (row["title"] or "") + " " + (row.get("category") or "")
            if any(kw in title for kw in INDIVIDUAL_KEYWORDS):
                cur.execute("UPDATE announcements SET target_type = 'individual' WHERE announcement_id = %s", (row["announcement_id"],))
                updated += 1
        conn.commit()
        conn.close()
        if updated > 0:
            print(f"[classify] {updated}건 공고 target_type → individual 분류")
    except Exception as e:
        print(f"[classify] 오류: {e}")


def _deduplicate_announcements():
    """DB에서 중복 공고 제거 — 제목 정규화 기준으로 최신 1건만 유지"""
    import re as _re
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 제목 정규화 후 중복 찾기 (공백/괄호/특수문자 제거)
        cur.execute("""
            WITH normalized AS (
                SELECT announcement_id, title, created_at,
                       LOWER(REGEXP_REPLACE(REGEXP_REPLACE(title, '[\s\[\]()（）【】]', '', 'g'), '년도', '년', 'g')) AS norm_title
                FROM announcements
                WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
            ),
            duplicates AS (
                SELECT norm_title, COUNT(*) as cnt,
                       ARRAY_AGG(announcement_id ORDER BY created_at DESC) as ids
                FROM normalized
                GROUP BY norm_title
                HAVING COUNT(*) > 1
            )
            SELECT norm_title, cnt, ids FROM duplicates
        """)
        dup_groups = cur.fetchall()

        deleted = 0
        for row in dup_groups:
            ids = row["ids"]
            # 첫 번째(최신)는 유지, 나머지 삭제
            to_delete = ids[1:]
            for del_id in to_delete:
                try:
                    cur.execute("DELETE FROM announcements WHERE announcement_id = %s", (del_id,))
                    deleted += 1
                except Exception:
                    conn.rollback()
                    continue
            conn.commit()

        conn.close()
        if deleted > 0:
            print(f"[dedup] {deleted}건 중복 공고 삭제 ({len(dup_groups)}개 그룹)")
        else:
            print(f"[dedup] 중복 없음")
    except Exception as e:
        print(f"[dedup] 오류: {e}")


def _deactivate_dead_urls():
    """연속 실패 URL 자동 비활성화 (fail_count >= 5 + 복구 실패)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE admin_urls
            SET is_active = 0
            WHERE is_active = 1
              AND fail_count >= 5
              AND recovered_url IS NULL
            RETURNING id, source_name, url, fail_count
        """)
        deactivated = cursor.fetchall()
        conn.commit()
        conn.close()
        if deactivated:
            for row in deactivated:
                print(f"[cleanup] 비활성화: {row['source_name']} (실패 {row['fail_count']}회)")
            print(f"[cleanup] {len(deactivated)}개 URL 비활성화 완료")
    except Exception as e:
        print(f"[cleanup] 오류: {e}")


async def lifespan(app):
    _log_expired_announcements()  # 시작 시 현황만 로그
    task_sync = asyncio.create_task(_daily_sync_loop())
    task_digest = asyncio.create_task(_daily_digest_loop())
    yield
    task_sync.cancel()
    task_digest.cancel()
    try:
        await task_digest
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Gov Support Matching Assistant", lifespan=lifespan, docs_url=None, redoc_url=None)


@app.get("/health")
def health_check():
    return {"status": "ok"}


_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,http://localhost:5181,http://localhost:8010")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
# www 서브도메인 자동 포함
for _o in list(_cors_origins):
    if "://" in _o and "://www." not in _o:
        _www = _o.replace("://", "://www.", 1)
        if _www not in _cors_origins:
            _cors_origins.append(_www)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


# ── 보안 헤더 미들웨어 ──
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response: StarletteResponse = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)


# ── Rate Limiting (인메모리) ──
import threading
_rate_store: dict = {}  # {key: [timestamp, ...]}
_rate_lock = threading.Lock()

def _rate_limit_check(key: str, max_requests: int, window_seconds: int) -> bool:
    """Rate limit 검사. True이면 허용, False이면 차단"""
    now = datetime.datetime.utcnow()
    with _rate_lock:
        if key not in _rate_store:
            _rate_store[key] = []
        # 윈도우 밖 기록 제거
        cutoff = now - datetime.timedelta(seconds=window_seconds)
        _rate_store[key] = [t for t in _rate_store[key] if t > cutoff]
        if len(_rate_store[key]) >= max_requests:
            return False
        _rate_store[key].append(now)
        return True

def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── 보안 AI 에이전트 — 실시간 이상 감지 ──
import collections
import threading

class SecurityAgent:
    """실시간 보안 모니터링 에이전트 — 봇/크롤러 감지 강화"""

    def __init__(self):
        self._lock = threading.Lock()
        # IP별 요청 카운터 (1분 윈도우)
        self._request_counts: dict[str, list] = {}
        # IP별 실패 로그인 카운터
        self._failed_logins: dict[str, list] = {}
        # 차단된 IP
        self._blocked_ips: set = set()
        # IP별 공개 API 페이지네이션 추적 (크롤링 감지)
        self._pagination_tracker: dict[str, list] = {}
        # IP별 고유 경로 추적 (비정상 순회 감지)
        self._path_tracker: dict[str, set] = {}
        # SQL 인젝션 패턴
        self._sqli_patterns = [
            "union select", "drop table", "insert into", "delete from",
            "update set", "pg_sleep", "information_schema", "1=1", "or 1=",
            "'; --", "\"; --", "/*", "*/", "xp_cmdshell",
        ]
        # XSS 패턴
        self._xss_patterns = [
            "<script", "javascript:", "onerror=", "onload=", "eval(",
            "document.cookie", "alert(", "<svg", "<iframe",
        ]
        # 봇/크롤러 User-Agent 패턴
        self._bot_ua_patterns = [
            "python-requests", "scrapy", "crawl", "spider", "bot",
            "curl", "wget", "httpie", "postman", "insomnia",
            "go-http-client", "java/", "libwww", "httpclient",
            "aiohttp", "node-fetch", "axios/", "got/",
            "headless", "phantom", "puppeteer", "playwright",
        ]
        # 허용 봇 (검색 엔진)
        self._allowed_bots = ["googlebot", "bingbot", "yandexbot", "naverbot", "daumoa"]
        # 이벤트 로그 (최근 100건)
        self._events: list = []
        self._MAX_EVENTS = 100
        # 임계값
        self.RATE_LIMIT = 120       # 1분간 최대 요청 수
        self.FAILED_LOGIN_LIMIT = 5  # 5회 실패 시 차단
        self.BLOCK_DURATION = 300    # 5분 차단
        self.CRAWL_PAGE_LIMIT = 10  # 5분 내 공개 API 10페이지 이상 요청 시 차단
        self.PATH_SCAN_LIMIT = 50   # 5분 내 50개 이상 고유 경로 접근 시 차단

    def _log_event(self, severity: str, event_type: str, ip: str, detail: str):
        entry = {
            "ts": datetime.datetime.utcnow().isoformat(),
            "severity": severity,
            "type": event_type,
            "ip": ip,
            "detail": detail[:200],
        }
        with self._lock:
            self._events.append(entry)
            if len(self._events) > self._MAX_EVENTS:
                self._events = self._events[-self._MAX_EVENTS:]
        if severity in ("HIGH", "CRITICAL"):
            print(f"[SECURITY-{severity}] {event_type}: {ip} — {detail[:100]}")

    def _cleanup_old(self, counter: dict, window: int = 60):
        """오래된 타임스탬프 정리"""
        now = time.time()
        for key in list(counter.keys()):
            counter[key] = [t for t in counter[key] if now - t < window]
            if not counter[key]:
                del counter[key]

    # 공개 API + 내부 서비스 경로 — 보안 검사 예외
    _whitelisted_paths = ("/api/announcements/public", "/api/announcements/search", "/for-smartdoc", "/api/push/vapid-key", "/api/auth/", "/health")

    def check_request(self, ip: str, path: str, method: str, query: str = "", body: str = "", user_agent: str = "") -> str | None:
        """요청을 검사하고 차단 사유가 있으면 반환, 없으면 None"""
        # 화이트리스트 경로는 보안 검사 건너뛰기
        if any(wp in path for wp in self._whitelisted_paths):
            return None

        now = time.time()
        ua_lower = (user_agent or "").lower()

        # 1. 차단된 IP 확인
        if ip in self._blocked_ips:
            return "IP_BLOCKED"

        # 2. 봇/크롤러 User-Agent 감지
        if ua_lower:
            # 허용된 검색 엔진 봇은 통과
            is_allowed_bot = any(b in ua_lower for b in self._allowed_bots)
            if not is_allowed_bot:
                is_bot = any(p in ua_lower for p in self._bot_ua_patterns)
                if is_bot:
                    self._log_event("HIGH", "BOT_DETECTED", ip, f"UA: {user_agent[:100]}, path={path}")
                    _log_system("bot_detected", "system", f"IP={ip}, UA={user_agent[:80]}, path={path}", "blocked")
                    self._blocked_ips.add(ip)
                    threading.Timer(self.BLOCK_DURATION * 2, lambda: self._blocked_ips.discard(ip)).start()
                    return "BOT_BLOCKED"
            # User-Agent가 비어있으면 의심
            if not ua_lower.strip():
                self._log_event("MEDIUM", "EMPTY_UA", ip, f"path={path}")

        # 3. Rate Limiting
        with self._lock:
            if ip not in self._request_counts:
                self._request_counts[ip] = []
            self._request_counts[ip].append(now)
            self._cleanup_old(self._request_counts)
            if len(self._request_counts.get(ip, [])) > self.RATE_LIMIT:
                self._blocked_ips.add(ip)
                self._log_event("HIGH", "RATE_LIMIT", ip, f"{len(self._request_counts[ip])} req/min on {path}")
                _log_system("rate_limit_block", "system", f"IP={ip}, {len(self._request_counts[ip])} req/min", "blocked")
                threading.Timer(self.BLOCK_DURATION, lambda: self._blocked_ips.discard(ip)).start()
                return "RATE_LIMITED"

        # 4. 공개 API 크롤링 감지 (페이지네이션 남용)
        if "/api/announcements/public" in path:
            with self._lock:
                if ip not in self._pagination_tracker:
                    self._pagination_tracker[ip] = []
                self._pagination_tracker[ip].append(now)
                self._cleanup_old(self._pagination_tracker, window=300)
                page_count = len(self._pagination_tracker.get(ip, []))
                if page_count > self.CRAWL_PAGE_LIMIT:
                    self._blocked_ips.add(ip)
                    self._log_event("CRITICAL", "CRAWL_DETECTED", ip, f"{page_count} public API pages in 5min")
                    _log_system("crawl_blocked", "system", f"IP={ip}, {page_count} pages/5min", "blocked")
                    threading.Timer(self.BLOCK_DURATION * 4, lambda: self._blocked_ips.discard(ip)).start()
                    return "CRAWL_BLOCKED"

        # 5. 비정상 경로 스캔 감지 (다수의 고유 경로 접근)
        if path.startswith("/api/"):
            with self._lock:
                if ip not in self._path_tracker:
                    self._path_tracker[ip] = set()
                self._path_tracker[ip].add(path)
                # 5분마다 리셋
                if len(self._path_tracker[ip]) > self.PATH_SCAN_LIMIT:
                    self._blocked_ips.add(ip)
                    self._log_event("HIGH", "PATH_SCAN", ip, f"{len(self._path_tracker[ip])} unique paths")
                    _log_system("path_scan_blocked", "system", f"IP={ip}, {len(self._path_tracker[ip])} unique paths", "blocked")
                    threading.Timer(self.BLOCK_DURATION * 2, lambda: self._blocked_ips.discard(ip)).start()
                    self._path_tracker[ip] = set()
                    return "SCAN_BLOCKED"

        # 6. SQL 인젝션 패턴 감지
        check_str = f"{query} {body}".lower()
        for pattern in self._sqli_patterns:
            if pattern in check_str:
                self._log_event("HIGH", "SQLI_ATTEMPT", ip, f"pattern='{pattern}' path={path}")
                return None  # 파라미터 바인딩으로 안전, 로깅만

        # 7. XSS 패턴 감지
        for pattern in self._xss_patterns:
            if pattern in check_str:
                self._log_event("MEDIUM", "XSS_ATTEMPT", ip, f"pattern='{pattern}' path={path}")
                return None  # 로깅만

        # 8. 민감 경로 접근 감지
        suspicious_paths = ["/.env", "/.git", "/wp-admin", "/phpmyadmin", "/admin.php", "/.aws", "/config.json"]
        if path in suspicious_paths:
            self._log_event("MEDIUM", "SUSPICIOUS_PATH", ip, path)
            self._blocked_ips.add(ip)
            threading.Timer(self.BLOCK_DURATION, lambda: self._blocked_ips.discard(ip)).start()
            return "SUSPICIOUS_BLOCKED"

        return None

    def record_failed_login(self, ip: str, endpoint: str):
        """로그인 실패 기록"""
        now = time.time()
        with self._lock:
            if ip not in self._failed_logins:
                self._failed_logins[ip] = []
            self._failed_logins[ip].append(now)
            self._cleanup_old(self._failed_logins, window=300)
            count = len(self._failed_logins.get(ip, []))
            if count >= self.FAILED_LOGIN_LIMIT:
                self._blocked_ips.add(ip)
                self._log_event("CRITICAL", "BRUTE_FORCE", ip, f"{count} failed logins on {endpoint}")
                threading.Timer(self.BLOCK_DURATION, lambda: self._blocked_ips.discard(ip)).start()

    def get_status(self) -> dict:
        """보안 상태 리포트"""
        with self._lock:
            self._cleanup_old(self._request_counts)
            self._cleanup_old(self._failed_logins, 300)
        return {
            "blocked_ips": list(self._blocked_ips),
            "active_ips": len(self._request_counts),
            "failed_logins": {ip: len(ts) for ip, ts in self._failed_logins.items() if ts},
            "recent_events": self._events[-20:],
        }


# 보안 에이전트 인스턴스
security_agent = SecurityAgent()


# 보안 미들웨어 — 모든 요청을 에이전트가 검사
class SecurityAgentMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "unknown")
        path = request.url.path
        method = request.method
        query = str(request.query_params)
        user_agent = request.headers.get("user-agent", "")

        # 요청 검사
        block_reason = security_agent.check_request(ip, path, method, query, user_agent=user_agent)
        if block_reason in ("IP_BLOCKED", "SUSPICIOUS_BLOCKED"):
            return StarletteResponse(content='{"detail":"접근이 차단되었습니다."}',
                                     status_code=403, media_type="application/json")
        if block_reason in ("RATE_LIMITED", "CRAWL_BLOCKED", "SCAN_BLOCKED"):
            return StarletteResponse(content='{"detail":"요청이 너무 많습니다. 잠시 후 다시 시도하세요."}',
                                     status_code=429, media_type="application/json")
        if block_reason == "BOT_BLOCKED":
            return StarletteResponse(content='{"detail":"자동화된 접근이 감지되어 차단되었습니다."}',
                                     status_code=403, media_type="application/json")

        response = await call_next(request)

        # 인증 실패 감지
        if response.status_code == 401 and path.startswith("/api/admin"):
            security_agent.record_failed_login(ip, path)

        return response

app.add_middleware(SecurityAgentMiddleware)


# 보안 상태 API (Admin 전용)
class BusinessNumberRequest(BaseModel):
    business_number: str

class UserProfile(BaseModel):
    business_number: str
    company_name: Optional[str] = None
    establishment_date: Optional[str] = None
    address_city: Optional[str] = None
    industry_code: Optional[str] = None
    revenue_bracket: Optional[str] = None
    employee_count_bracket: Optional[str] = None
    interests: Optional[str] = None
    password: Optional[str] = None
    # 개인/기업 구분
    user_type: Optional[str] = "both"
    # 개인 프로필 필드
    age_range: Optional[str] = None
    income_level: Optional[str] = None
    family_type: Optional[str] = None
    employment_status: Optional[str] = None

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
    kakao_enabled: Optional[int] = 0

class AdminURLRequest(BaseModel):
    url: str
    source_name: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    business_number: str
    company_name: Optional[str] = ""
    address_city: Optional[str] = None
    industry_code: Optional[str] = None
    establishment_date: Optional[str] = None
    revenue_bracket: Optional[str] = None
    employee_count_bracket: Optional[str] = None
    interests: Optional[str] = None
    referred_by: Optional[str] = None
    user_type: Optional[str] = "both"

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


# ── 플랜 v4: 플랜 차별화 강화 (2026-04-05 확정) ──
# FREE: 공고AI 1회/월, 저장/알림 불가
# LITE: 공고AI 20회/월, 저장/알림 가능, 가입 시 7일 무료체험
# PRO (전문가용): 무제한, 전문가 에이전트
#
# 자유AI 상담 (자유Q&A + 컨설턴트) 건수 제한 — PRO 전용
PLAN_LIMITS = {
    "free": 0,
    "lite": 0,         # LITE: 자유AI 불가 (PRO 전용)
    "lite_trial": 0,   # legacy
    "basic": 0,        # legacy → LITE 취급
    "biz": 999999,     # legacy → PRO 취급
    "pro": 999999,
}

# 공고AI 상담 건수 제한
# free: 1회/월, lite: 20회/월, pro: 무제한
CONSULT_LIMITS = {
    "free": 1,
    "lite_trial": 20,  # LITE 체험도 20회
    "lite": 20,
    "basic": 20,       # legacy → LITE 취급
    "biz": 999999,     # legacy → PRO 취급
    "pro": 999999,
}

# 플랜 가격 (원/월) — user_type에 따라 분기
# 개인 LITE: 2,900 / 사업자 LITE: 4,900 / PRO: 49,000 (사업자 전용)
PLAN_PRICES = {
    "lite_individual": 2900,
    "lite": 4900,       # 사업자 LITE (기본값)
    "pro": 49000,
    "basic": 4900,      # legacy
    "biz": 49000,       # legacy
}

# AI 신청서 작성 가격 (원/건) — Coming Soon
AI_GUIDE_PRICE = None

# 공고AI 상담 1건당 메시지 제한 (사용자 메시지 기준)
CONSULT_MSG_LIMIT = 50


def _get_plan_status(plan: str, plan_expires_at: str | None, ai_usage_month: int = 0) -> dict:
    """플랜 상태와 남은 일수, 잔여 건수를 계산"""
    now = datetime.datetime.utcnow()

    # trial/premium → free 마이그레이션
    if plan in ("trial", "premium"):
        plan = "free"

    ai_limit = PLAN_LIMITS.get(plan, 1)
    consult_limit = CONSULT_LIMITS.get(plan, 0)

    if plan == "free":
        # FREE는 영구 무료 — 만료 없음
        return {
            "plan": "free", "active": True, "days_left": None,
            "label": "FREE",
            "ai_used": ai_usage_month, "ai_limit": ai_limit,
            "consult_limit": consult_limit,
        }

    if plan in ("lite", "lite_trial", "basic", "biz", "pro"):
        # 유료 플랜 만료 체크
        if plan_expires_at:
            try:
                expires = datetime.datetime.fromisoformat(str(plan_expires_at))
                days_left = (expires - now).days
                if days_left < 0:
                    # 만료 → FREE로 다운그레이드
                    return {
                        "plan": "expired", "active": False, "days_left": 0,
                        "label": "만료됨",
                        "ai_used": ai_usage_month, "ai_limit": PLAN_LIMITS["free"],
                        "consult_limit": CONSULT_LIMITS["free"],
                    }
                label_map = {"lite": "LITE", "lite_trial": "LITE 체험", "basic": "LITE", "biz": "PRO", "pro": "PRO"}
                return {
                    "plan": plan, "active": True, "days_left": days_left,
                    "label": label_map.get(plan, plan.upper()),
                    "ai_used": ai_usage_month, "ai_limit": ai_limit,
                    "consult_limit": consult_limit,
                }
            except ValueError:
                pass
        label_map = {"lite": "LITE", "lite_trial": "LITE 체험", "basic": "LITE", "biz": "PRO", "pro": "PRO"}
        return {
            "plan": plan, "active": True, "days_left": None,
            "label": label_map.get(plan, plan.upper()),
            "ai_used": ai_usage_month, "ai_limit": ai_limit,
            "consult_limit": consult_limit,
        }

    return {"plan": "free", "active": True, "days_left": None, "label": "FREE",
            "ai_used": 0, "ai_limit": PLAN_LIMITS["free"], "consult_limit": CONSULT_LIMITS["free"]}


# ─── 응답 캐시 (동시접속 대응) ───────────────────────────────────────
_response_cache: dict = {}
_CACHE_TTL = 300  # 5분

def _get_cached(key: str):
    entry = _response_cache.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    return None

def _set_cache(key: str, data):
    _response_cache[key] = {"data": data, "ts": time.time()}


# ─── 비로그인 공고 리스트 API ───────────────────────────────────────
@app.get("/api/announcements/public")
def api_announcements_public(
    request: Request,
    page: int = 1,
    size: int = 20,
    region: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    target_type: Optional[str] = None,
):
    """비로그인 사용자도 접근 가능한 공고 리스트 (마감 전 공고만)"""
    # Rate limiting: IP당 분당 30회
    ip = _get_client_ip(request)
    if not _rate_limit_check(f"public:ip:{ip}", 60, 60):
        raise HTTPException(status_code=429, detail="요청이 너무 많습니다. 잠시 후 다시 시도해주세요.")
    if size < 1:
        size = 1
    if size > 50:
        size = 50  # 크롤링 방지: 최대 50건
    if page < 1:
        page = 1
    if page > 50:
        raise HTTPException(status_code=400, detail="페이지 범위를 초과했습니다.")
    offset = (page - 1) * size

    # 검색 없는 기본 조회는 캐시 활용
    if not search and not region and not category:
        cache_key = f"pub:v2:{target_type}:{page}:{size}"
        cached = _get_cached(cache_key)
        if cached:
            return cached

    conn = get_db_connection()
    cursor = conn.cursor()

    where_clauses = ["(deadline_date IS NULL OR deadline_date >= CURRENT_DATE)"]
    params: list = []

    if region:
        where_clauses.append("region = %s")
        params.append(region)
    if category:
        where_clauses.append("category ILIKE %s")
        params.append(f"%{category}%")
    if search:
        # 공백으로 단어 분리
        words = search.strip().split()

        # 동의어 확장: 각 단어별로 동의어 그룹 확장
        all_search_terms = []
        for word in words:
            cursor.execute(
                "SELECT DISTINCT keyword FROM keyword_synonyms WHERE group_name = ("
                "  SELECT group_name FROM keyword_synonyms WHERE keyword = %s LIMIT 1"
                ")",
                (word,),
            )
            synonym_rows = cursor.fetchall()
            word_terms = [r["keyword"] for r in synonym_rows] if synonym_rows else [word]
            all_search_terms.append(word_terms)

        # 검색 조건: 각 단어(OR 동의어)가 모두 포함 (AND)
        # 단어가 1개면 OR 검색, 2개 이상이면 각 단어 AND 조합
        # 추가로 원본 구문 그대로 매칭도 포함 (OR)
        search_fields = "(title || ' ' || COALESCE(summary_text,'') || ' ' || COALESCE(department,'') || ' ' || COALESCE(region,'') || ' ' || COALESCE(category,''))"

        if len(words) == 1:
            # 단일 단어: 기존 동의어 OR 검색
            word_conditions = []
            for term in all_search_terms[0]:
                word_conditions.append(f"{search_fields} ILIKE %s")
                params.append(f"%{term}%")
            where_clauses.append("(" + " OR ".join(word_conditions) + ")")
        else:
            # 복수 단어: 구문 매칭 OR (각 단어 AND)
            # 1) 구문 그대로 매칭
            phrase_cond = f"{search_fields} ILIKE %s"
            params.append(f"%{search}%")

            # 2) 각 단어(+동의어)가 모두 포함 (AND)
            and_parts = []
            for word_terms in all_search_terms:
                word_or = []
                for term in word_terms:
                    word_or.append(f"{search_fields} ILIKE %s")
                    params.append(f"%{term}%")
                and_parts.append("(" + " OR ".join(word_or) + ")")
            and_cond = " AND ".join(and_parts)

            # 3) 단어 중 하나라도 포함 (OR) — 넓은 범위
            or_parts = []
            for word_terms in all_search_terms:
                for term in word_terms:
                    or_parts.append(f"{search_fields} ILIKE %s")
                    params.append(f"%{term}%")
            or_cond = " OR ".join(or_parts)

            where_clauses.append(f"({phrase_cond} OR {and_cond} OR {or_cond})")

        search_terms = []
        for wt in all_search_terms:
            search_terms.extend(wt)
        s = f"%{search}%"  # 관련성 정렬용 원본 검색어
    if target_type:
        where_clauses.append("(target_type = %s OR target_type = 'both')")
        params.append(target_type)

    where_sql = " AND ".join(where_clauses)

    # 총 개수
    cursor.execute(f"SELECT COUNT(*) AS cnt FROM announcements WHERE {where_sql}", params)
    total = cursor.fetchone()["cnt"]

    # 공고 리스트 — 검색 시 관련성 정렬
    # 구문 제목 매칭 > 구문 요약 매칭 > AND 제목 > AND 요약 > OR 매칭
    if search:
        words = search.strip().split()
        # AND 조건: 모든 단어가 제목에 포함
        and_title_parts = " AND ".join([f"title ILIKE %s" for _ in words])
        and_title_params = [f"%{w}%" for w in words]
        and_summary_parts = " AND ".join([f"summary_text ILIKE %s" for _ in words])
        and_summary_params = [f"%{w}%" for w in words]

        relevance_order = f"""
                CASE WHEN title ILIKE %s THEN 0
                     WHEN ({and_title_parts}) THEN 1
                     WHEN summary_text ILIKE %s THEN 2
                     WHEN ({and_summary_parts}) THEN 3
                     ELSE 4 END,
"""
        relevance_params = [s] + and_title_params + [s] + and_summary_params
    else:
        relevance_order = ""
        relevance_params = []

    cursor.execute(
        f"""SELECT announcement_id, title, region, category, department,
                   support_amount, deadline_date, origin_source, created_at,
                   COALESCE(target_type, 'business') AS target_type,
                   origin_url, summary_text, eligibility_logic,
                   established_years_limit, revenue_limit, employee_limit
            FROM announcements
            WHERE {where_sql}
            ORDER BY
                {relevance_order}
                CASE WHEN deadline_date IS NOT NULL AND deadline_date < CURRENT_DATE THEN 2
                     WHEN deadline_date IS NULL THEN 1 ELSE 0 END,
                CASE WHEN support_amount IS NOT NULL AND support_amount != '' THEN 0 ELSE 1 END,
                CASE WHEN region = '전국' OR region IS NULL THEN 0 ELSE 1 END,
                created_at DESC,
                deadline_date ASC NULLS LAST
            LIMIT %s OFFSET %s""",
        params + relevance_params + [size, offset],
    )
    rows = cursor.fetchall()

    # 필터용 메타: 지역/카테고리 목록
    cursor.execute("SELECT DISTINCT region FROM announcements WHERE region IS NOT NULL ORDER BY region")
    regions = [r["region"] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT category FROM announcements WHERE category IS NOT NULL ORDER BY category")
    categories = [r["category"] for r in cursor.fetchall()]

    # 카테고리별 건수 — 캐시 활용 (5분)
    cat_cache_key = f"cat_counts:{target_type or 'all'}"
    category_counts = _get_cached(cat_cache_key)
    if not category_counts:
        cat_where = ["(deadline_date IS NULL OR deadline_date >= CURRENT_DATE)"]
        cat_params: list = []
        if target_type:
            cat_where.append("(target_type = %s OR target_type = 'both')")
            cat_params.append(target_type)
        cat_where_sql = " AND ".join(cat_where)
        cursor.execute(
            f"""SELECT COALESCE(category, '기타') AS cat, COUNT(*) AS cnt
                FROM announcements WHERE {cat_where_sql}
                GROUP BY COALESCE(category, '기타') ORDER BY cnt DESC""",
            cat_params,
        )
        category_counts = {r["cat"]: r["cnt"] for r in cursor.fetchall()}
        _set_cache(cat_cache_key, category_counts)

    conn.close()

    result = {
        "status": "SUCCESS",
        "data": rows,
        "total": total,
        "page": page,
        "size": size,
        "regions": regions,
        "categories": categories,
        "category_counts": category_counts,
    }

    # 기본 조회 캐시 저장
    if not search and not region and not category:
        cache_key = f"pub:v2:{target_type}:{page}:{size}"
        _set_cache(cache_key, result)

    return result


@app.get("/api/announcements/{announcement_id}/detail")
def api_announcement_detail(announcement_id: int):
    """공고 상세 (비로그인 접근 가능 — 기본 정보만)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT a.*, aa.deep_analysis
           FROM announcements a
           LEFT JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
           WHERE a.announcement_id = %s""",
        (announcement_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
    return {"status": "SUCCESS", "data": row}


class FindEmailRequest(BaseModel):
    company_name: str


@app.post("/api/auth/find-email")
def api_find_email(req: FindEmailRequest):
    if not req.company_name or len(req.company_name.strip()) < 1:
        raise HTTPException(status_code=400, detail="회사명을 입력해 주세요.")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE company_name = %s", (req.company_name,))
    user = cursor.fetchone()
    conn.close()
    if not user or not user.get("email"):
        raise HTTPException(status_code=404, detail="일치하는 계정을 찾을 수 없습니다.")
    email = user["email"]
    local, domain = email.split("@", 1)
    masked = local[:2] + "*" * max(len(local) - 2, 1) + "@" + domain
    return {"status": "SUCCESS", "masked_email": masked}


class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str
    code: Optional[str] = None  # 인증코드

class ResetCodeRequest(BaseModel):
    email: str

# 비밀번호 재설정 인증코드 저장 (메모리, {email: {code, expires, attempts}})
_reset_codes: dict = {}
# Rate limiting: {ip: [timestamps]}
_reset_rate: dict = {}

def _send_reset_email(to_email: str, code: str):
    """비밀번호 재설정 인증코드 이메일 발송"""
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_from = os.getenv("SMTP_FROM", smtp_user)
    if not smtp_user or not smtp_password:
        return False
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(
            f"지원금AI 비밀번호 재설정 인증코드입니다.\n\n"
            f"인증코드: {code}\n\n"
            f"이 코드는 10분간 유효합니다.\n"
            f"본인이 요청하지 않았다면 이 이메일을 무시하세요.",
            "plain", "utf-8"
        )
        msg["Subject"] = "[지원금AI] 비밀번호 재설정 인증코드"
        msg["From"] = smtp_from
        msg["To"] = to_email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True
    except Exception:
        return False

@app.post("/api/auth/reset-password/request")
def api_request_reset_code(req: ResetCodeRequest, request: Request):
    """1단계: 인증코드 발송 요청"""
    if not req.email:
        raise HTTPException(status_code=400, detail="이메일을 입력해주세요.")
    # Rate limiting: IP당 분당 3회
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.datetime.utcnow()
    if client_ip in _reset_rate:
        _reset_rate[client_ip] = [t for t in _reset_rate[client_ip] if (now - t).seconds < 300]
        if len(_reset_rate[client_ip]) >= 3:
            raise HTTPException(status_code=429, detail="잠시 후 다시 시도해주세요.")
    else:
        _reset_rate[client_ip] = []
    _reset_rate[client_ip].append(now)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT business_number FROM users WHERE email = %s", (req.email,))
    user = cursor.fetchone()
    conn.close()
    # 계정 존재 여부와 관계없이 동일 응답 (열거 방지)
    if user:
        import random
        code = f"{random.randint(100000, 999999)}"
        _reset_codes[req.email] = {
            "code": code,
            "expires": now + datetime.timedelta(minutes=10),
            "attempts": 0,
        }
        _send_reset_email(req.email, code)
    return {"status": "SUCCESS", "message": "등록된 이메일이면 인증코드가 발송됩니다."}


@app.post("/api/auth/reset-password")
def api_reset_password(req: ResetPasswordRequest):
    """2단계: 인증코드 확인 후 비밀번호 변경"""
    if not req.email:
        raise HTTPException(status_code=400, detail="이메일을 입력해주세요.")
    if not req.code:
        raise HTTPException(status_code=400, detail="인증코드를 입력해주세요.")
    if not req.new_password or len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="비밀번호는 6자 이상이어야 합니다.")

    # 인증코드 검증
    stored = _reset_codes.get(req.email)
    if not stored:
        raise HTTPException(status_code=400, detail="인증코드를 먼저 요청해주세요.")
    if stored["attempts"] >= 5:
        del _reset_codes[req.email]
        raise HTTPException(status_code=400, detail="인증 시도 횟수를 초과했습니다. 다시 요청해주세요.")
    if datetime.datetime.utcnow() > stored["expires"]:
        del _reset_codes[req.email]
        raise HTTPException(status_code=400, detail="인증코드가 만료되었습니다. 다시 요청해주세요.")
    if req.code != stored["code"]:
        stored["attempts"] += 1
        raise HTTPException(status_code=400, detail="인증코드가 올바르지 않습니다.")

    # 인증 성공 → 비밀번호 변경
    del _reset_codes[req.email]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT business_number FROM users WHERE email = %s", (req.email,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=400, detail="처리 중 오류가 발생했습니다.")
    new_hash = _hash_password(req.new_password)
    cursor.execute("UPDATE users SET password_hash = %s WHERE email = %s", (new_hash, req.email))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "비밀번호가 재설정되었습니다. 새 비밀번호로 로그인해주세요."}


@app.post("/api/auth/register")
def api_register(req: RegisterRequest, request: Request):
    # Rate limiting: IP당 시간당 5회
    ip = _get_client_ip(request)
    if not _rate_limit_check(f"register:ip:{ip}", 5, 3600):
        raise HTTPException(status_code=429, detail="회원가입 시도가 너무 많습니다. 잠시 후 다시 시도해주세요.")
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=400, detail="올바른 이메일을 입력해 주세요.")
    if not req.password or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="비밀번호는 6자 이상이어야 합니다.")
    if len(req.business_number) != 10:
        raise HTTPException(status_code=400, detail="사업자번호 10자리를 입력해 주세요.")

    import hashlib as _hashlib
    hashed = _hash_password(req.password)
    now_iso = datetime.datetime.utcnow().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (req.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다.")

        cursor.execute("SELECT user_id FROM users WHERE business_number = %s", (req.business_number,))
        existing = cursor.fetchone()

        est_date = req.establishment_date or None
        if existing:
            cursor.execute(
                """UPDATE users SET email=%s, password_hash=%s, plan='free',
                   plan_started_at=%s, plan_expires_at=NULL,
                   ai_usage_month=0, ai_usage_reset_at=%s,
                   company_name=COALESCE(NULLIF(%s, ''), company_name),
                   address_city=COALESCE(%s, address_city),
                   industry_code=COALESCE(%s, industry_code),
                   establishment_date=COALESCE(%s, establishment_date),
                   revenue_bracket=COALESCE(%s, revenue_bracket),
                   employee_count_bracket=COALESCE(%s, employee_count_bracket),
                   interests=COALESCE(%s, interests)
                   WHERE business_number=%s""",
                (req.email, hashed, now_iso, now_iso,
                 req.company_name or "", req.address_city or None,
                 req.industry_code or None, req.establishment_date,
                 req.revenue_bracket, req.employee_count_bracket, req.interests,
                 req.business_number),
            )
            user_id = existing["user_id"]
        else:
            cursor.execute(
                """INSERT INTO users (business_number, company_name, email, password_hash, plan,
                   plan_started_at, ai_usage_month, ai_usage_reset_at,
                   address_city, establishment_date, industry_code, revenue_bracket, employee_count_bracket, interests,
                   referred_by, user_type)
                   VALUES (%s, %s, %s, %s, 'free', %s, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING user_id""",
                (req.business_number, req.company_name or "", req.email, hashed, now_iso, now_iso,
                 req.address_city or None, est_date,
                 req.industry_code or None, req.revenue_bracket or None,
                 req.employee_count_bracket or None, req.interests,
                 req.referred_by or None, req.user_type or "both"),
            )
            user_id = cursor.fetchone()["user_id"]
            # 추천 코드 자동 생성
            ref_code = _hashlib.md5(f'{req.business_number}{user_id}'.encode()).hexdigest()[:8].upper()
            cursor.execute("UPDATE users SET referral_code=%s WHERE business_number=%s", (ref_code, req.business_number))

            # 가입 시 LITE 7일 무료체험 자동 부여 (추천인이 없는 경우)
            if not req.referred_by:
                trial_end = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat()
                cursor.execute(
                    "UPDATE users SET plan='lite', plan_started_at=%s, plan_expires_at=%s WHERE user_id=%s",
                    (now_iso, trial_end, user_id)
                )

            # 가입 시 추천인 보상: LITE 1개월 무료 (최대 5회 — merit_months로 추적)
            if req.referred_by:
                cursor.execute("SELECT user_id, plan, plan_expires_at, merit_months FROM users WHERE referral_code = %s", (req.referred_by,))
                referrer = cursor.fetchone()
                if referrer and (referrer["merit_months"] or 0) < 5:
                    new_merit = (referrer["merit_months"] or 0) + 1
                    now_dt = datetime.datetime.utcnow()
                    if referrer["plan"] in ("lite", "basic", "pro", "biz"):
                        # 유료 플랜: 만료일 30일 연장
                        try:
                            current_end = datetime.datetime.fromisoformat(str(referrer["plan_expires_at"]))
                            new_end = (max(current_end, now_dt) + datetime.timedelta(days=30)).isoformat()
                        except Exception:
                            new_end = (now_dt + datetime.timedelta(days=30)).isoformat()
                        cursor.execute(
                            "UPDATE users SET merit_months=%s, plan_expires_at=%s WHERE user_id=%s",
                            (new_merit, new_end, referrer["user_id"])
                        )
                    else:
                        # free 플랜: LITE 1개월 무료 업그레이드
                        new_end = (now_dt + datetime.timedelta(days=30)).isoformat()
                        cursor.execute(
                            "UPDATE users SET merit_months=%s, plan='lite', plan_started_at=%s, plan_expires_at=%s, ai_usage_month=0, ai_usage_reset_at=%s WHERE user_id=%s",
                            (new_merit, now_dt.isoformat(), new_end, now_dt.isoformat(), referrer["user_id"])
                        )
                    # 피추천인에게도 LITE 1개월 무료
                    new_end_new = (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat()
                    cursor.execute(
                        "UPDATE users SET plan='lite', plan_started_at=%s, plan_expires_at=%s, ai_usage_month=0, ai_usage_reset_at=%s, referral_rewarded=TRUE WHERE user_id=%s",
                        (now_dt.isoformat(), new_end_new, now_dt.isoformat(), user_id)
                    )

        conn.commit()
        # 가입 후 실제 플랜 상태 조회 (체험/추천 적용 반영)
        cursor2 = conn.cursor()
        cursor2.execute("SELECT plan, plan_expires_at FROM users WHERE user_id=%s", (user_id,))
        signup_user = cursor2.fetchone()
        signup_plan = signup_user["plan"] if signup_user else "free"
        signup_expires = str(signup_user["plan_expires_at"]) if signup_user and signup_user["plan_expires_at"] else None
        token = _create_jwt(user_id, req.business_number, req.email, signup_plan, signup_expires)
        _log_event("signup", req.business_number, f"email={req.email},plan={signup_plan}", _get_client_ip(request), request.headers.get("user-agent", ""))
        return {
            "status": "SUCCESS",
            "token": token,
            "plan": _get_plan_status(signup_plan, signup_expires, 0),
        }
    finally:
        conn.close()


@app.post("/api/auth/login")
def api_login(req: LoginRequest, request: Request):
    # Rate limiting: IP당 분당 10회, 이메일당 분당 5회
    ip = _get_client_ip(request)
    if not _rate_limit_check(f"login:ip:{ip}", 10, 60):
        raise HTTPException(status_code=429, detail="로그인 시도가 너무 많습니다. 잠시 후 다시 시도해주세요.")
    if req.email and not _rate_limit_check(f"login:email:{req.email}", 5, 60):
        raise HTTPException(status_code=429, detail="로그인 시도가 너무 많습니다. 잠시 후 다시 시도해주세요.")
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail="이메일과 비밀번호를 입력해 주세요.")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (req.email,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="등록되지 않은 이메일입니다.")

        u = dict(user)
        if not u.get("password_hash"):
            raise HTTPException(status_code=401, detail="소셜 로그인으로 가입된 계정입니다. 카카오/네이버/Google로 로그인해주세요.")

        if not _verify_password(req.password, u["password_hash"]):
            _log_event("login_fail", u.get("business_number", ""), f"email={req.email}", ip)
            raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")

        _log_event("login", u.get("business_number", ""), f"email={req.email},plan={u.get('plan','free')},type={u.get('user_type','')}", ip, request.headers.get("user-agent", ""))
        plan = u.get("plan") or "free"
        if plan == "trial":
            plan = "free"
        plan_expires = u.get("plan_expires_at")
        if plan_expires is not None:
            plan_expires = str(plan_expires)
        ai_usage = u.get("ai_usage_month") or 0

        # 월간 사용량 리셋 체크
        reset_at = u.get("ai_usage_reset_at")
        now = datetime.datetime.utcnow()
        if reset_at:
            try:
                reset_dt = datetime.datetime.fromisoformat(str(reset_at))
                if now.month != reset_dt.month or now.year != reset_dt.year:
                    ai_usage = 0
                    cursor.execute(
                        "UPDATE users SET ai_usage_month=0, ai_usage_reset_at=%s WHERE user_id=%s",
                        (now.isoformat(), u["user_id"])
                    )
            except Exception:
                pass

        plan_status = _get_plan_status(plan, plan_expires, ai_usage)

        if plan_status["plan"] == "expired":
            plan = "free"
            cursor.execute("UPDATE users SET plan = 'free', plan_expires_at = NULL WHERE user_id = %s", (u["user_id"],))
            plan_status = _get_plan_status("free", None, ai_usage)

        # Lookup KSIC industry name
        industry_name = ""
        if u.get("industry_code"):
            cursor.execute("SELECT name FROM ksic_classification WHERE code = %s", (u["industry_code"],))
            row3 = cursor.fetchone()
            if row3:
                industry_name = row3["name"]

        conn.commit()
    finally:
        conn.close()

    token = _create_jwt(u["user_id"], u["business_number"], u["email"], plan, plan_expires)
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
            "industry_name": industry_name,
            "revenue_bracket": u.get("revenue_bracket", ""),
            "employee_count_bracket": u.get("employee_count_bracket", ""),
            "interests": u.get("interests", ""),
        },
        "plan": plan_status,
    }


# ─── 소셜 로그인 (OAuth2) ───────────────────────────────────────────
import secrets
import urllib.parse

KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID", "")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def _social_login_or_register(provider: str, social_id: str, email: str, name: str, kakao_refresh_token: str = "", gender: str = "", birth_year: str = ""):
    """소셜 로그인: 기존 사용자면 로그인, 신규면 자동 가입"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 성별 정규화: kakao "male"/"female" → DB "남성"/"여성"
    gender_map = {"male": "남성", "female": "여성", "M": "남성", "F": "여성"}
    normalized_gender = gender_map.get(gender, gender)

    # 출생연도 → 연령대 매핑
    age_range_val = ""
    if birth_year:
        try:
            age = datetime.datetime.now().year - int(birth_year)
            if age < 20: age_range_val = "10대"
            elif age < 30: age_range_val = "20대"
            elif age < 40: age_range_val = "30대"
            elif age < 50: age_range_val = "40대"
            elif age < 60: age_range_val = "50대"
            else: age_range_val = "60대 이상"
        except (ValueError, TypeError):
            pass

    # 1. 이미 같은 이메일로 가입된 사용자 확인
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    now_iso = datetime.datetime.utcnow().isoformat()

    if user:
        u = dict(user)
        # kakao_id 컬럼에 소셜 provider:id 저장 (기존 호환)
        updates = []
        params = []
        if not u.get("kakao_id"):
            updates.append("kakao_id = %s")
            params.append(f"{provider}:{social_id}")
        if kakao_refresh_token and provider == "kakao":
            updates.append("kakao_refresh_token = %s")
            params.append(kakao_refresh_token)
        # 성별/연령대가 비어있으면 소셜에서 받은 값으로 채움
        if normalized_gender and not u.get("gender"):
            updates.append("gender = %s")
            params.append(normalized_gender)
        if age_range_val and not u.get("age_range"):
            updates.append("age_range = %s")
            params.append(age_range_val)
        if updates:
            params.append(u["user_id"])
            cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = %s", params)
            conn.commit()
    else:
        # 신규 가입
        bn = f"U{int(datetime.datetime.utcnow().timestamp())}"[-10:]
        import hashlib as _hashlib
        cursor.execute(
            """INSERT INTO users (business_number, company_name, email, password_hash, plan,
               plan_started_at, ai_usage_month, ai_usage_reset_at, kakao_id, gender, age_range, user_type)
               VALUES (%s, %s, %s, %s, 'free', %s, 0, %s, %s, %s, %s, 'both')
               RETURNING user_id, business_number""",
            (bn, name or "", email, "", now_iso, now_iso, f"{provider}:{social_id}", normalized_gender, age_range_val)
        )
        row = cursor.fetchone()
        ref_code = _hashlib.md5(f'{bn}{row["user_id"]}'.encode()).hexdigest()[:8].upper()
        cursor.execute("UPDATE users SET referral_code=%s WHERE user_id=%s", (ref_code, row["user_id"]))
        conn.commit()

        cursor.execute("SELECT * FROM users WHERE user_id = %s", (row["user_id"],))
        user = cursor.fetchone()
        u = dict(user)

    conn.close()

    plan = u.get("plan") or "free"
    if plan in ("trial", "premium"):
        plan = "free"
    plan_expires = str(u["plan_expires_at"]) if u.get("plan_expires_at") else None
    ai_usage = u.get("ai_usage_month") or 0
    plan_status = _get_plan_status(plan, plan_expires, ai_usage)

    token = _create_jwt(u["user_id"], u["business_number"], u["email"], plan, plan_expires)

    is_new = not u.get("user_type")
    return token, plan_status, u, is_new


@app.get("/api/auth/social/{provider}")
def api_social_auth_redirect(provider: str):
    """소셜 로그인 시작: 각 플랫폼 OAuth URL로 리다이렉트"""
    redirect_uri = f"{FRONTEND_URL}/auth/callback/{provider}"
    state = secrets.token_urlsafe(16)

    if provider == "kakao":
        if not KAKAO_CLIENT_ID:
            raise HTTPException(status_code=501, detail="카카오 로그인이 아직 설정되지 않았습니다.")
        url = (f"https://kauth.kakao.com/oauth/authorize"
               f"?client_id={KAKAO_CLIENT_ID}"
               f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
               f"&response_type=code&state={state}"
               f"&scope=talk_message")
    elif provider == "naver":
        if not NAVER_CLIENT_ID:
            raise HTTPException(status_code=501, detail="네이버 로그인이 아직 설정되지 않았습니다.")
        url = (f"https://nid.naver.com/oauth2.0/authorize"
               f"?client_id={NAVER_CLIENT_ID}"
               f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
               f"&response_type=code&state={state}")
    elif provider == "google":
        if not GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=501, detail="Google 로그인이 아직 설정되지 않았습니다.")
        url = (f"https://accounts.google.com/o/oauth2/v2/auth"
               f"?client_id={GOOGLE_CLIENT_ID}"
               f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
               f"&response_type=code&scope=email+profile&state={state}")
    else:
        raise HTTPException(status_code=400, detail="지원하지 않는 로그인 방식입니다.")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url)


class SocialCallbackRequest(BaseModel):
    code: str
    provider: str


@app.post("/api/auth/social/callback")
async def api_social_callback(req: SocialCallbackRequest):
    """소셜 로그인 콜백: authorization code → 토큰 교환 → 사용자 정보 → JWT 발급"""
    import httpx

    redirect_uri = f"{FRONTEND_URL}/auth/callback/{req.provider}"

    if req.provider == "kakao":
        # 1. code → access_token
        async with httpx.AsyncClient() as client:
            token_res = await client.post("https://kauth.kakao.com/oauth/token", data={
                "grant_type": "authorization_code",
                "client_id": KAKAO_CLIENT_ID,
                "client_secret": KAKAO_CLIENT_SECRET,
                "code": req.code,
                "redirect_uri": redirect_uri,
            })
            token_data = token_res.json()
            access_token = token_data.get("access_token")
            kakao_refresh_token = token_data.get("refresh_token", "")
            if not access_token:
                raise HTTPException(status_code=400, detail="카카오 인증 실패")

            # 2. access_token → user info
            user_res = await client.get("https://kapi.kakao.com/v2/user/me",
                                        headers={"Authorization": f"Bearer {access_token}"})
            user_data = user_res.json()

        kakao_id = str(user_data.get("id", ""))
        account = user_data.get("kakao_account", {})
        email = account.get("email", f"kakao_{kakao_id}@kakao.local")
        name = account.get("profile", {}).get("nickname", "")
        # 카카오에서 성별/출생연도 추출
        kakao_gender = account.get("gender", "")  # "male" or "female"
        kakao_birthyear = account.get("birthyear", "")  # "1990" 등

        token, plan_status, u, is_new = _social_login_or_register(
            "kakao", kakao_id, email, name,
            kakao_refresh_token=kakao_refresh_token,
            gender=kakao_gender, birth_year=kakao_birthyear
        )

    elif req.provider == "naver":
        async with httpx.AsyncClient() as client:
            token_res = await client.post("https://nid.naver.com/oauth2.0/token", data={
                "grant_type": "authorization_code",
                "client_id": NAVER_CLIENT_ID,
                "client_secret": NAVER_CLIENT_SECRET,
                "code": req.code,
                "redirect_uri": redirect_uri,
            })
            token_data = token_res.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="네이버 인증 실패")

            user_res = await client.get("https://openapi.naver.com/v1/nid/me",
                                        headers={"Authorization": f"Bearer {access_token}"})
            user_data = user_res.json().get("response", {})

        naver_id = user_data.get("id", "")
        email = user_data.get("email", f"naver_{naver_id}@naver.local")
        name = user_data.get("name", user_data.get("nickname", ""))
        # 네이버에서 성별/출생연도 추출: gender="M"/"F", birthyear="1990"
        naver_gender = user_data.get("gender", "")
        naver_birthyear = user_data.get("birthyear", "")

        token, plan_status, u, is_new = _social_login_or_register(
            "naver", naver_id, email, name,
            gender=naver_gender, birth_year=naver_birthyear
        )

    elif req.provider == "google":
        async with httpx.AsyncClient() as client:
            token_res = await client.post("https://oauth2.googleapis.com/token", data={
                "grant_type": "authorization_code",
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": req.code,
                "redirect_uri": redirect_uri,
            })
            token_data = token_res.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="Google 인증 실패")

            user_res = await client.get("https://www.googleapis.com/oauth2/v2/userinfo",
                                        headers={"Authorization": f"Bearer {access_token}"})
            user_data = user_res.json()

        google_id = user_data.get("id", "")
        email = user_data.get("email", "")
        name = user_data.get("name", "")

        token, plan_status, u, is_new = _social_login_or_register("google", google_id, email, name)
    else:
        raise HTTPException(status_code=400, detail="지원하지 않는 로그인 방식입니다.")

    _log_event("social_login" if not is_new else "social_signup", u.get("business_number", ""), f"provider={req.provider},email={u.get('email','')}")
    return {
        "status": "SUCCESS",
        "token": token,
        "user": {
            "business_number": u.get("business_number", ""),
            "company_name": u.get("company_name", ""),
            "email": u.get("email", ""),
        },
        "plan": plan_status,
        "is_new_user": is_new,
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
    plan_expires = u.get("plan_expires_at") or u.get("trial_ends_at")
    if plan_expires is not None:
        plan_expires = str(plan_expires)
    plan_status = _get_plan_status(u.get("plan") or "free", plan_expires, u.get("ai_usage_month") or 0)
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
            "user_type": u.get("user_type") or None,
            "is_social": bool(u.get("kakao_id")),
            "social_provider": u.get("kakao_id", "").split(":")[0] if u.get("kakao_id") else None,
            "custom_needs": u.get("custom_needs"),
            "custom_keywords": u.get("custom_keywords"),
            "gender": u.get("gender"),
            "age_range": u.get("age_range"),
            "income_level": u.get("income_level"),
            "family_type": u.get("family_type"),
            "employment_status": u.get("employment_status"),
            "founded_date": u.get("founded_date"),
            "is_pre_founder": u.get("is_pre_founder"),
            "certifications": u.get("certifications"),
        },
        "plan": plan_status,
    }


class UpgradePlanRequest(BaseModel):
    payment_id: Optional[str] = None      # 포트원 V2 결제 ID
    billing_key: Optional[str] = None     # 정기결제 빌링키
    target_plan: Optional[str] = "lite"   # "lite" or "pro"
    free_trial: Optional[bool] = False    # 사업자 LITE 1개월 무료 여부


PORTONE_API_SECRET = os.getenv("PORTONE_API_SECRET", "")

# PLAN_PRICES는 상단에 정의됨


@app.post("/api/plan/upgrade")
def api_plan_upgrade(
    req: UpgradePlanRequest,
    current_user: dict = Depends(_get_current_user),
):
    """포트원 V2 결제 확인 후 플랜 업그레이드"""
    bn = current_user["bn"]
    target = req.target_plan if req.target_plan in ("lite", "pro") else "lite"

    # 사용자 정보 조회
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_type, plan, plan_expires_at FROM users WHERE business_number = %s", (bn,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    u = dict(user)
    user_type = u.get("user_type") or "both"

    # 가격 결정 (user_type별)
    if target == "lite":
        price = PLAN_PRICES.get("lite_individual" if user_type == "individual" else "lite", 4900)
    else:
        price = PLAN_PRICES.get("pro", 49000)

    # 사업자 LITE 1개월 무료 체험
    if req.free_trial and target == "lite" and user_type != "individual":
        # 이미 체험한 적 있는지 확인
        cur.execute(
            "SELECT plan_expires_at FROM users WHERE business_number = %s AND plan IN ('lite', 'lite_trial', 'pro')",
            (bn,),
        )
        if cur.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="무료 체험은 1회만 가능합니다.")
        # 무료 체험: 결제 없이 30일 부여
        target = "lite"
    elif req.payment_id and PORTONE_API_SECRET:
        # 포트원 V2 결제 검증
        import httpx
        verify_res = httpx.get(
            f"https://api.portone.io/payments/{req.payment_id}",
            headers={"Authorization": f"PortOne {PORTONE_API_SECRET}"},
            timeout=15,
        )
        if verify_res.status_code != 200:
            conn.close()
            raise HTTPException(status_code=400, detail="결제 정보를 확인할 수 없습니다.")
        payment = verify_res.json()
        if payment.get("status") != "PAID":
            conn.close()
            raise HTTPException(status_code=400, detail="결제가 완료되지 않았습니다.")
        if payment.get("amount", {}).get("total") != price:
            conn.close()
            raise HTTPException(status_code=400, detail="결제 금액이 일치하지 않습니다.")

    # 빌링키 저장 (정기결제용)
    billing_update = ""
    billing_params = []
    if req.billing_key:
        billing_update = ", billing_key = %s"
        billing_params = [req.billing_key]

    now = datetime.datetime.utcnow()
    expires_at = (now + datetime.timedelta(days=30)).isoformat()

    cur.execute(
        f"""UPDATE users SET plan = %s, plan_started_at = %s, plan_expires_at = %s,
           ai_usage_month = 0, ai_usage_reset_at = %s{billing_update}
           WHERE business_number = %s""",
        [target, now.isoformat(), expires_at, now.isoformat()] + billing_params + [bn],
    )
    conn.commit()
    conn.close()

    plan_status = _get_plan_status(target, expires_at, 0)
    label_map = {"lite": "LITE", "lite_trial": "LITE 체험", "basic": "LITE", "biz": "PRO", "pro": "PRO"}
    label = label_map.get(target, target.upper())
    new_token = _create_jwt(
        current_user["user_id"], bn, current_user["email"], target, expires_at
    )

    _log_event("upgrade", current_user["bn"], f"plan={target_plan},price={price},trial={req.free_trial}")
    return {
        "status": "SUCCESS",
        "token": new_token,
        "plan": plan_status,
        "message": f"{label} 플랜으로 업그레이드되었습니다. ({'무료 체험 시작' if req.free_trial else f'{price:,}원 결제 완료'})",
        "price": price,
    }


class SubscribeRequest(BaseModel):
    billing_key: str
    target_plan: str = "lite"  # "lite" or "pro"


@app.post("/api/plan/subscribe")
def api_plan_subscribe(
    req: SubscribeRequest,
    current_user: dict = Depends(_get_current_user),
):
    """빌링키 등록 + 무료 체험 시작 (LITE 30일 / PRO 7일)"""
    # 빌링키 유효성 검증
    if not req.billing_key or not isinstance(req.billing_key, str) or len(req.billing_key.strip()) < 10:
        raise HTTPException(status_code=400, detail="유효하지 않은 빌링키입니다. 카드 등록을 다시 시도해 주세요.")

    bn = current_user["bn"]
    target = req.target_plan if req.target_plan in ("lite", "pro") else "lite"

    conn = get_db_connection()
    cur = conn.cursor()

    # 사용자 조회
    cur.execute("SELECT plan, billing_key FROM users WHERE business_number = %s", (bn,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    u = dict(user)
    current_plan = u.get("plan") or "free"

    # 동일 플랜 재구독 차단 (상위 플랜 업그레이드는 허용)
    if u.get("billing_key") and current_plan == target:
        conn.close()
        raise HTTPException(status_code=400, detail="이미 동일한 플랜을 구독 중입니다.")
    # 하위 플랜으로 변경 차단 (PRO → LITE)
    if current_plan == "pro" and target == "lite":
        conn.close()
        raise HTTPException(status_code=400, detail="PRO에서 LITE로 변경은 구독 해지 후 재가입해주세요.")

    # 무료 체험 기간: LITE 30일, PRO 7일
    now = datetime.datetime.utcnow()
    trial_days = 30 if target == "lite" else 7
    expires_at = (now + datetime.timedelta(days=trial_days)).isoformat()

    cur.execute(
        """UPDATE users SET plan = %s, plan_started_at = %s, plan_expires_at = %s,
           ai_usage_month = 0, ai_usage_reset_at = %s, billing_key = %s
           WHERE business_number = %s""",
        (target, now.isoformat(), expires_at, now.isoformat(), req.billing_key, bn),
    )
    conn.commit()
    conn.close()

    plan_status = _get_plan_status(target, expires_at, 0)
    label = "LITE" if target == "lite" else "PRO"
    new_token = _create_jwt(
        current_user["user_id"], bn, current_user["email"], target, expires_at
    )

    return {
        "status": "SUCCESS",
        "token": new_token,
        "plan": plan_status,
        "message": f"{label} {trial_days}일 무료 체험이 시작되었습니다! 이후 자동결제됩니다.",
    }


@app.post("/api/plan/cancel")
def api_plan_cancel(current_user: dict = Depends(_get_current_user)):
    """구독 해지 — 빌링키 삭제, 만료일까지는 이용 가능"""
    bn = current_user["bn"]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET billing_key = NULL WHERE business_number = %s",
        (bn,),
    )
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "구독이 해지되었습니다. 현재 플랜 만료일까지는 이용 가능합니다."}


@app.post("/api/plan/refund")
def api_plan_refund(current_user: dict = Depends(_get_current_user)):
    """구독 환불 — 최근 자동결제 건을 포트원 API로 취소 + FREE 전환"""
    if not PORTONE_API_SECRET:
        raise HTTPException(status_code=500, detail="결제 시스템 설정 오류")

    bn = current_user["bn"]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT plan, billing_key, plan_started_at, plan_expires_at, user_type FROM users WHERE business_number = %s", (bn,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    u = dict(user)
    plan = u.get("plan") or "free"
    if plan == "free":
        conn.close()
        raise HTTPException(status_code=400, detail="무료 플랜은 환불 대상이 아닙니다.")

    # 무료체험 기간이면 결제 건이 없으므로 그냥 해지
    plan_started = u.get("plan_started_at")
    plan_expires = u.get("plan_expires_at")
    if plan_started and plan_expires:
        try:
            started = datetime.datetime.fromisoformat(str(plan_started))
            expires = datetime.datetime.fromisoformat(str(plan_expires))
            trial_days = (expires - started).days
            # 무료체험: LITE 30일, PRO 7일 — 첫 구독이면 결제 없음
            if trial_days <= 30:
                cur.execute(
                    "UPDATE users SET plan = 'free', billing_key = NULL, plan_expires_at = NULL WHERE business_number = %s",
                    (bn,),
                )
                conn.commit()
                conn.close()
                return {"status": "SUCCESS", "message": "무료체험이 해지되었습니다. FREE 플랜으로 전환되었습니다."}
        except (ValueError, TypeError):
            pass

    # 실 결제 건 환불 — 최근 결제 ID 조회 시도
    import httpx
    try:
        # 결제 ID 패턴: renew-{bn}-{timestamp}
        # 포트원 API로 최근 결제 조회
        resp = httpx.get(
            f"https://api.portone.io/payments?filter.merchantId={bn}&pageSize=1&sort.order=DESC",
            headers={"Authorization": f"PortOne {PORTONE_API_SECRET}"},
            timeout=15,
        )
        if resp.status_code != 200:
            # 결제 이력 조회 실패 → 단순 해지로 처리
            cur.execute(
                "UPDATE users SET plan = 'free', billing_key = NULL, plan_expires_at = NULL WHERE business_number = %s",
                (bn,),
            )
            conn.commit()
            conn.close()
            return {"status": "SUCCESS", "message": "구독이 해지되었습니다. 환불은 고객센터로 문의해주세요."}

        # 해지 + FREE 전환
        cur.execute(
            "UPDATE users SET plan = 'free', billing_key = NULL, plan_expires_at = NULL WHERE business_number = %s",
            (bn,),
        )
        conn.commit()
        conn.close()
        return {"status": "SUCCESS", "message": "환불이 처리되었습니다. FREE 플랜으로 전환되었습니다."}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"환불 처리 중 오류: {str(e)}")


def _auto_renew_subscriptions():
    """만료된 구독 자동 갱신 — 빌링키로 결제"""
    if not PORTONE_API_SECRET:
        return
    import httpx
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # 만료일이 지났고 빌링키가 있는 사용자
        cur.execute("""
            SELECT business_number, plan, billing_key, user_type, email
            FROM users
            WHERE billing_key IS NOT NULL
              AND plan IN ('lite', 'pro')
              AND plan_expires_at < NOW()
        """)
        expired_users = cur.fetchall()

        renewed, failed = 0, 0
        for row in expired_users:
            u = dict(row)
            plan = u["plan"]
            user_type = u.get("user_type") or "both"

            # 가격 결정
            if plan == "lite":
                price = PLAN_PRICES.get("lite_individual" if user_type == "individual" else "lite", 4900)
            else:
                price = PLAN_PRICES.get("pro", 49000)

            payment_id = f"renew-{u['business_number']}-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M')}"

            try:
                resp = httpx.post(
                    f"https://api.portone.io/payments/{payment_id}/billing-key",
                    headers={
                        "Authorization": f"PortOne {PORTONE_API_SECRET}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "billingKey": u["billing_key"],
                        "orderName": f"지원금AI {plan.upper()} 월 구독",
                        "amount": {"total": price, "currency": "KRW"},
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    now = datetime.datetime.utcnow()
                    new_expires = (now + datetime.timedelta(days=30)).isoformat()
                    cur.execute(
                        """UPDATE users SET plan_expires_at = %s, ai_usage_month = 0,
                           ai_usage_reset_at = %s WHERE business_number = %s""",
                        (new_expires, now.isoformat(), u["business_number"]),
                    )
                    conn.commit()
                    renewed += 1
                    print(f"[renew] {u.get('email','?')} {plan.upper()} {price:,}원 결제 완료")
                else:
                    failed += 1
                    # 결제 실패 → 플랜 만료 + 빌링키 삭제
                    cur.execute(
                        "UPDATE users SET plan = 'free', billing_key = NULL WHERE business_number = %s",
                        (u["business_number"],),
                    )
                    conn.commit()
                    print(f"[renew] {u.get('email','?')} 결제 실패 → FREE 전환: {resp.status_code}")
            except Exception as e:
                failed += 1
                cur.execute(
                    "UPDATE users SET plan = 'free', billing_key = NULL WHERE business_number = %s",
                    (u["business_number"],),
                )
                conn.commit()
                print(f"[renew] {u.get('email','?')} 오류 → FREE 전환: {e}")

        conn.close()
        if renewed or failed:
            _log_system("auto_renew", "payment", f"성공 {renewed}건, 실패 {failed}건 (총 {len(expired_users)}명)", "success" if failed == 0 else "partial", renewed)
            print(f"[renew] 자동 갱신 완료: 성공 {renewed}건, 실패 {failed}건")
    except Exception as e:
        _log_system("auto_renew", "payment", f"오류: {e}", "error")
        print(f"[renew] 오류: {e}")


@app.get("/api/plan/status")
def api_plan_status(current_user: dict = Depends(_get_current_user)):
    """현재 플랜 상태 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT plan, plan_expires_at, ai_usage_month, ai_usage_reset_at FROM users WHERE business_number = %s",
        (current_user["bn"],)
    )
    user = cursor.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    u = dict(user)

    plan = u.get("plan") or "free"
    if plan == "trial":
        plan = "free"
    plan_expires = u.get("plan_expires_at")
    if plan_expires is not None:
        plan_expires = str(plan_expires)
    ai_usage = u.get("ai_usage_month") or 0

    return {
        "status": "SUCCESS",
        "plan": _get_plan_status(plan, plan_expires, ai_usage),
    }


@app.post("/api/ai/use")
def api_ai_use(current_user: dict = Depends(_get_current_user)):
    """AI 기능 사용 시 건수 차감 (1건)"""
    bn = current_user["bn"]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT plan, ai_usage_month, ai_usage_reset_at FROM users WHERE business_number = %s",
        (bn,)
    )
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    u = dict(user)
    plan = u.get("plan") or "free"
    if plan in ("trial", "premium"):
        plan = "free"
    limit = PLAN_LIMITS.get(plan, 1)
    usage = u.get("ai_usage_month") or 0

    # 월간 리셋 체크
    now = datetime.datetime.utcnow()
    reset_at = u.get("ai_usage_reset_at")
    if reset_at:
        try:
            reset_dt = datetime.datetime.fromisoformat(str(reset_at))
            if now.month != reset_dt.month or now.year != reset_dt.year:
                usage = 0
                cur.execute(
                    "UPDATE users SET ai_usage_month=0, ai_usage_reset_at=%s WHERE business_number=%s",
                    (now.isoformat(), bn)
                )
        except Exception:
            pass

    if usage >= limit:
        conn.close()
        raise HTTPException(
            status_code=429,
            detail=f"이번 달 AI 상담 한도({limit}건)를 모두 사용했습니다. 플랜을 업그레이드하면 더 많은 건수를 이용할 수 있습니다."
        )

    cur.execute(
        "UPDATE users SET ai_usage_month = ai_usage_month + 1 WHERE business_number = %s",
        (bn,)
    )
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "ai_used": usage + 1, "ai_limit": limit}


# ── AI 자유 상담 (크로스 공고 검색) ─────────────────────────────

class AiChatRequest(BaseModel):
    messages: list  # [{"role": "user"|"assistant", "text": "..."}]


@app.post("/api/ai/chat")
def api_ai_chat(req: AiChatRequest, current_user: dict = Depends(_get_current_user)):
    """자유 상담: 중소기업 지원사업 전반에 대한 AI 상담"""
    bn = current_user["bn"]
    conn = get_db_connection()
    cur = conn.cursor()

    # 사용자 정보 조회
    cur.execute("SELECT * FROM users WHERE business_number = %s", (bn,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    u = dict(user)

    # 플랜/사용량 체크
    plan = u.get("plan") or "free"
    plan_expires = u.get("plan_expires_at")
    ps = _get_plan_status(plan, plan_expires, u.get("ai_usage_month") or 0)
    if not ps.get("active"):
        conn.close()
        raise HTTPException(status_code=403, detail="플랜이 만료되었습니다.")

    if plan in ("trial", "premium"):
        plan = "free"
    limit = PLAN_LIMITS.get(plan, 1)
    usage = u.get("ai_usage_month") or 0

    # 월간 리셋
    now = datetime.datetime.utcnow()
    reset_at = u.get("ai_usage_reset_at")
    if reset_at:
        try:
            reset_dt = datetime.datetime.fromisoformat(str(reset_at))
            if now.month != reset_dt.month or now.year != reset_dt.year:
                usage = 0
                cur.execute(
                    "UPDATE users SET ai_usage_month=0, ai_usage_reset_at=%s WHERE business_number=%s",
                    (now.isoformat(), bn)
                )
        except Exception:
            pass

    # 첫 메시지일 때만 건수 차감
    is_first_message = len(req.messages) <= 1
    if is_first_message:
        if usage >= limit:
            conn.close()
            raise HTTPException(status_code=429, detail=f"이번 달 AI 상담 한도({limit}회)를 모두 사용했습니다. 플랜을 업그레이드하면 더 많은 상담을 이용할 수 있습니다.")
        cur.execute("UPDATE users SET ai_usage_month = ai_usage_month + 1 WHERE business_number = %s", (bn,))
        conn.commit()
        usage += 1

    # 통합 AI 엔진으로 자유 상담
    from app.services.ai_consultant import chat_free
    result = chat_free(req.messages, conn, user_profile=u)
    conn.close()

    return {
        "status": "SUCCESS",
        "reply": result.get("reply", ""),
        "choices": result.get("choices", []),
        "announcements": result.get("announcements", []),
        "done": result.get("done", False),
        "ai_used": usage,
        "ai_limit": limit,
    }


# ── AI 공고 특화 상담 (대화형) ───────────────────────────────────

class AiConsultRequest(BaseModel):
    announcement_id: int
    messages: list  # [{"role": "user"|"assistant", "text": "..."}]


@app.post("/api/ai/consult")
def api_ai_consult(req: AiConsultRequest, current_user: dict = Depends(_get_current_user)):
    """AI 지원대상 여부 상담 — 대화형 (Gemini)"""
    import google.generativeai as genai

    bn = current_user["bn"]
    conn = get_db_connection()
    cur = conn.cursor()

    # 1) 사용자 프로필 + 플랜 체크
    cur.execute(
        """SELECT plan, ai_usage_month, ai_usage_reset_at, plan_expires_at,
                  company_name, establishment_date, address_city, industry_code,
                  revenue_bracket, employee_count_bracket, interests, user_type,
                  age_range, business_number
           FROM users WHERE business_number = %s""",
        (bn,)
    )
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    u = dict(user)
    # NULL 프로필 필드 → 빈 문자열 (AI 프롬프트 호환)
    for k in ("company_name", "establishment_date", "address_city", "industry_code",
              "revenue_bracket", "employee_count_bracket", "interests", "user_type", "age_range"):
        if u.get(k) is None:
            u[k] = ""

    # 플랜/사용량 체크
    plan = u.get("plan") or "free"
    if plan in ("trial", "premium"):
        plan = "free"
    plan_expires = u.get("plan_expires_at")
    ps = _get_plan_status(plan, plan_expires, u.get("ai_usage_month") or 0)
    if not ps.get("active"):
        conn.close()
        raise HTTPException(status_code=403, detail="플랜이 만료되었습니다. 업그레이드 후 이용해 주세요.")

    # 공고별 지원대상 상담 제한 체크
    consult_limit = CONSULT_LIMITS.get(plan, 0)
    ai_usage = u.get("ai_usage_month") or 0

    # 월간 리셋 체크
    now = datetime.datetime.utcnow()
    reset_at = u.get("ai_usage_reset_at")
    if reset_at:
        try:
            reset_dt = datetime.datetime.fromisoformat(str(reset_at))
            if now.month != reset_dt.month or now.year != reset_dt.year:
                ai_usage = 0
                cur.execute(
                    "UPDATE users SET ai_usage_month=0, ai_usage_reset_at=%s WHERE business_number=%s",
                    (now.isoformat(), bn)
                )
        except Exception:
            pass

    if consult_limit == 0:
        conn.close()
        raise HTTPException(
            status_code=403,
            detail="공고별 지원대상 상담은 LITE 플랜부터 이용할 수 있습니다."
        )

    # 건수 제한 (PRO/무제한 제외)
    if consult_limit < 999999:
        # consult 사용량은 ai_usage_month로 추적
        if ai_usage >= consult_limit:
            conn.close()
            if plan == "free":
                msg = f"무료 상담({consult_limit}회)을 모두 사용했습니다. LITE 플랜으로 업그레이드하면 월 20회까지 이용할 수 있습니다."
            else:
                msg = f"이번 달 AI 상담 한도({consult_limit}회)를 모두 사용했습니다. PRO 플랜으로 업그레이드하면 무제한 이용할 수 있습니다."
            raise HTTPException(status_code=429, detail=msg)
        # 첫 메시지일 때만 건수 차감
        if len(req.messages) <= 1:
            cur.execute("UPDATE users SET ai_usage_month = ai_usage_month + 1 WHERE business_number = %s", (bn,))
            conn.commit()
            ai_usage += 1

    # 1-1) 메시지 수 제한 (사용자 메시지 기준 30회)
    user_msg_count = sum(1 for m in req.messages if m.get("role") == "user")
    if user_msg_count > CONSULT_MSG_LIMIT:
        conn.close()
        raise HTTPException(
            status_code=429,
            detail=f"상담 메시지 한도({CONSULT_MSG_LIMIT}회)를 초과했습니다. 새 상담을 시작해 주세요."
        )

    # 2) 공고 정보 조회
    cur.execute(
        """SELECT announcement_id, title, department, category, support_amount, deadline_date,
                  summary_text, region, eligibility_logic, origin_url
           FROM announcements WHERE announcement_id = %s""",
        (req.announcement_id,)
    )
    ann = cur.fetchone()
    if not ann:
        conn.close()
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
    a = dict(ann)

    # 2-1) 정밀 분석 데이터 보장 (없으면 실시간 분석)
    deep = {}
    try:
        from app.services.doc_analysis_service import ensure_analysis
        analysis_conn = get_db_connection()
        deep = ensure_analysis(req.announcement_id, analysis_conn) or {}
        analysis_conn.close()
        if deep:
            ps = deep.get("parsed_sections", {}) or {}
            filled = [k for k, v in ps.items() if v]
            print(f"[Consult] Analysis OK for #{req.announcement_id}: source={deep.get('source_type')}, filled_sections={filled}")
    except Exception as e:
        print(f"[Consult] ensure_analysis error for #{req.announcement_id}: {e}")
        try:
            analysis_conn.close()
        except Exception:
            pass

    # 3) 통합 AI 엔진으로 상담 (별도 커넥션 사용)
    consult_conn = None
    try:
        from app.services.ai_consultant import chat_consult
        consult_conn = get_db_connection()
        result = chat_consult(
            announcement_id=req.announcement_id,
            messages=req.messages,
            announcement=a,
            deep_analysis_data=deep,
            user_profile=u,
            db_conn=consult_conn,
        )
    except Exception as e:
        print(f"[Consult] chat_consult error: {e}")
        import traceback; traceback.print_exc()
        # 에러 발생해도 기본 응답 반환 (500 대신 정상 응답)
        result = {
            "reply": f"AI 상담 중 오류가 발생했습니다. 다시 시도해 주세요.\n\n공고 원문 확인: {a.get('origin_url', '')}",
            "choices": ["다시 시도", "다른 공고 보기"],
            "done": False,
            "conclusion": None,
        }
    finally:
        if consult_conn:
            try:
                consult_conn.close()
            except Exception:
                pass
    conn.close()

    is_done = result.get("done", False)
    consult_log_id = None

    # 상담 완료 시 로그 저장 (학습 데이터 축적)
    if is_done:
        try:
            all_msgs = req.messages + [{"role": "assistant", "text": result.get("reply", "")}]
            log_conn = get_db_connection()
            log_cur = log_conn.cursor()
            log_cur.execute("""
                INSERT INTO ai_consult_logs (announcement_id, business_number, messages, conclusion)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (req.announcement_id, bn, json.dumps(all_msgs, ensure_ascii=False), result.get("conclusion")))
            row = log_cur.fetchone()
            consult_log_id = row["id"] if row else None
            log_conn.commit()
            log_conn.close()
        except Exception as log_err:
            consult_log_id = None
            print(f"[ConsultLog] Save error: {log_err}")

    return {
        "status": "SUCCESS",
        "reply": result.get("reply", ""),
        "choices": result.get("choices", []),
        "done": is_done,
        "conclusion": result.get("conclusion") if is_done else None,
        "consult_log_id": consult_log_id if is_done else None,
        "ai_used": ai_usage,
        "ai_limit": consult_limit,
    }


# ── AI 컨설턴트 모드 (고객사 조건 수집 대화) ──────────────────

class AiConsultantChatRequest(BaseModel):
    messages: list  # [{"role": "user"|"assistant", "text": "..."}]


@app.post("/api/ai/consultant/chat")
def api_ai_consultant_chat(req: AiConsultantChatRequest, current_user: dict = Depends(_get_current_user)):
    """컨설턴트 모드: 대화형으로 고객사 조건 수집"""
    bn = current_user["bn"]
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE business_number = %s", (bn,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    u = dict(user)

    plan = u.get("plan") or "free"
    if plan in ("trial", "premium"):
        plan = "free"
    plan_expires = u.get("plan_expires_at")
    ps = _get_plan_status(plan, plan_expires, u.get("ai_usage_month") or 0)
    if not ps.get("active"):
        conn.close()
        raise HTTPException(status_code=403, detail="플랜이 만료되었습니다.")

    conn.close()

    # 조건 수집 대화는 건수 차감 없음 (매칭 실행 시 차감)
    from app.services.ai_consultant import chat_consultant
    result = chat_consultant(req.messages)

    return {
        "status": "SUCCESS",
        "reply": result.get("reply", ""),
        "choices": result.get("choices", []),
        "done": result.get("done", False),
        "profile": result.get("profile"),
        "collected": result.get("collected", {}),
    }


# ── AI 컨설턴트 매칭 실행 (가상 프로필 → 매칭) ────────────────

class ConsultantMatchRequest(BaseModel):
    profile: dict  # 가상 프로필 (company_name, establishment_date, industry_code 등)


@app.post("/api/ai/consultant/match")
def api_ai_consultant_match(req: ConsultantMatchRequest, current_user: dict = Depends(_get_current_user)):
    """컨설턴트 모드: 가상 프로필로 매칭 실행 (AI 1건 차감)"""
    bn = current_user["bn"]
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE business_number = %s", (bn,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    u = dict(user)

    plan = u.get("plan") or "free"
    if plan in ("trial", "premium"):
        plan = "free"
    plan_expires = u.get("plan_expires_at")
    usage = u.get("ai_usage_month") or 0
    ps = _get_plan_status(plan, plan_expires, usage)
    if not ps.get("active"):
        conn.close()
        raise HTTPException(status_code=403, detail="플랜이 만료되었습니다.")

    limit = PLAN_LIMITS.get(plan, 1)

    # 월간 리셋
    now = datetime.datetime.utcnow()
    reset_at = u.get("ai_usage_reset_at")
    if reset_at:
        try:
            reset_dt = datetime.datetime.fromisoformat(str(reset_at))
            if now.month != reset_dt.month or now.year != reset_dt.year:
                usage = 0
                cur.execute(
                    "UPDATE users SET ai_usage_month=0, ai_usage_reset_at=%s WHERE business_number=%s",
                    (now.isoformat(), bn)
                )
        except Exception:
            pass

    # AI 1건 차감
    if usage >= limit:
        conn.close()
        raise HTTPException(status_code=429, detail=f"이번 달 AI 상담 한도({limit}회)를 모두 사용했습니다. 플랜을 업그레이드하면 더 많은 상담을 이용할 수 있습니다.")

    cur.execute("UPDATE users SET ai_usage_month = ai_usage_month + 1 WHERE business_number = %s", (bn,))
    conn.commit()
    conn.close()
    usage += 1

    # 가상 프로필로 매칭 엔진 실행 — 프로필의 industry_code 유무로 기업/개인 분기
    virtual_profile = req.profile
    is_individual = not virtual_profile.get("industry_code")
    if is_individual:
        matches = get_individual_matches_for_user(virtual_profile)
    else:
        matches = get_matches_for_user(virtual_profile)

    # 직렬화 (date 등)
    for m in matches:
        for k, v in m.items():
            if isinstance(v, (datetime.date, datetime.datetime)):
                m[k] = v.isoformat()

    return {
        "status": "SUCCESS",
        "matches": matches,
        "profile_used": virtual_profile,
        "ai_used": usage,
        "ai_limit": limit,
    }


# ── 상담 피드백 ──────────────────────────────────────────

class ConsultFeedbackRequest(BaseModel):
    consult_log_id: int
    feedback: str  # 'helpful' | 'inaccurate'
    detail: Optional[str] = None


@app.post("/api/ai/consult/feedback")
def api_consult_feedback(req: ConsultFeedbackRequest, current_user: dict = Depends(_get_current_user)):
    """상담 결과 피드백 저장 + 순환 학습 (골든답변/지식 저장)"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE ai_consult_logs SET feedback = %s, feedback_detail = %s WHERE id = %s AND business_number = %s",
        (req.feedback, req.detail, req.consult_log_id, current_user["bn"])
    )
    conn.commit()

    # 순환 학습: 피드백 기반으로 골든답변 + 지식 저장
    try:
        from app.services.ai_consultant import (
            save_golden_answer, mark_golden_inaccurate, extract_knowledge_from_consult
        )

        # 상담 로그 조회
        cur.execute(
            "SELECT announcement_id, messages, conclusion FROM ai_consult_logs WHERE id = %s",
            (req.consult_log_id,)
        )
        log = cur.fetchone()
        if log:
            log_data = dict(log)
            ann_id = log_data["announcement_id"]
            messages = log_data["messages"]
            if isinstance(messages, str):
                messages = json.loads(messages)
            conclusion = log_data.get("conclusion")

            # 공고 카테고리 조회
            cur.execute("SELECT category FROM announcements WHERE announcement_id = %s", (ann_id,))
            ann_row = cur.fetchone()
            category = dict(ann_row).get("category", "") if ann_row else ""

            if req.feedback == "helpful":
                # "도움됐어요" → 골든 답변으로 저장
                save_golden_answer(
                    consult_log_id=req.consult_log_id,
                    announcement_id=ann_id,
                    category=category,
                    messages=messages,
                    conclusion=conclusion,
                    db_conn=conn,
                )
            elif req.feedback == "inaccurate":
                # "부정확해요" → 골든 답변 비활성화
                mark_golden_inaccurate(req.consult_log_id, conn)

            # 공통: 지식 추출 (패턴/오류 저장)
            extract_knowledge_from_consult(
                announcement_id=ann_id,
                category=category,
                messages=messages,
                conclusion=conclusion,
                feedback=req.feedback,
                db_conn=conn,
            )
    except Exception as e:
        print(f"[Feedback] Learning error (non-critical): {e}")

    conn.close()
    return {"status": "SUCCESS"}


# ── 공고 원문 정밀 분석 (배치) ─────────────────────────────

class AdminAuthRequest(BaseModel):
    password: str


@app.post("/api/admin/analyze-announcements")
def api_analyze_announcements(req: AdminAuthRequest):
    """관리자: 기존 공고들의 원문을 정밀 분석하여 학습 데이터 축적"""
    if req.password != os.environ.get("ADMIN_PASSWORD", "admin1234"):
        raise HTTPException(status_code=401, detail="관리자 비밀번호가 올바르지 않습니다.")

    from app.services.doc_analysis_service import analyze_and_store

    conn = get_db_connection()
    cur = conn.cursor()

    # 아직 분석되지 않은 공고 조회 (최대 20건씩)
    cur.execute("""
        SELECT a.announcement_id, a.title, a.origin_url, a.summary_text
        FROM announcements a
        LEFT JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
        WHERE aa.id IS NULL AND a.origin_url IS NOT NULL
        ORDER BY a.created_at DESC
        LIMIT 20
    """)
    rows = cur.fetchall()

    results = {"total": len(rows), "success": 0, "failed": 0, "details": []}
    for row in rows:
        r = dict(row)
        res = analyze_and_store(
            announcement_id=r["announcement_id"],
            origin_url=r["origin_url"],
            title=r["title"],
            db_conn=conn,
            summary_text=r.get("summary_text") or "",
        )
        if res["success"]:
            results["success"] += 1
        else:
            results["failed"] += 1
        results["details"].append({
            "id": r["announcement_id"],
            "title": r["title"][:50],
            "success": res["success"],
            "source": res["source_type"],
            "chars": res["text_length"],
        })

    conn.close()
    return {"status": "SUCCESS", **results}


@app.get("/api/admin/analysis-stats")
def api_analysis_stats(req: AdminAuthRequest = Depends()):
    """관리자: 분석 현황 통계"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as total FROM announcements")
    total = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as analyzed FROM announcement_analysis")
    analyzed = cur.fetchone()["analyzed"]
    cur.execute("SELECT COUNT(*) as consults FROM ai_consult_logs")
    consults = cur.fetchone()["consults"]
    cur.execute("SELECT COUNT(*) as feedback_count FROM ai_consult_logs WHERE feedback IS NOT NULL")
    feedback_count = cur.fetchone()["feedback_count"]
    conn.close()
    return {
        "total_announcements": total,
        "analyzed": analyzed,
        "pending": total - analyzed,
        "consult_logs": consults,
        "feedback_collected": feedback_count,
    }


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


@app.get("/api/admin/security-status", dependencies=[Depends(_verify_admin)])
def api_security_status():
    """보안 에이전트 실시간 상태 — 차단 IP, 이상 감지 이벤트"""
    return {"status": "SUCCESS", "security": security_agent.get_status()}


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

    cursor.execute("SELECT COUNT(*) FROM admin_urls WHERE is_active = 1")
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


@app.get("/api/admin/analytics", dependencies=[Depends(_verify_admin)])
def get_admin_analytics():
    """사용 패턴 분석 데이터: 가입 추이, 플랜 분포, AI 사용량, 알림 통계"""
    conn = get_db_connection()
    cursor = conn.cursor()

    def _safe_query(query, default=None):
        """테이블이 없어도 안전하게 쿼리 실행"""
        try:
            cursor.execute(query)
            return cursor.fetchall()
        except Exception:
            conn.rollback()
            return default if default is not None else []

    def _safe_scalar(query, field="total", default=0):
        try:
            cursor.execute(query)
            row = cursor.fetchone()
            return row[field] if row else default
        except Exception:
            conn.rollback()
            return default

    # 1. 일별 가입 추이 (최근 30일)
    cursor.execute("""
        SELECT DATE(updated_at) as reg_date, COUNT(*) as cnt
        FROM users
        WHERE updated_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(updated_at)
        ORDER BY reg_date
    """)
    signup_trend = [{"date": str(r["reg_date"]), "count": r["cnt"]} for r in cursor.fetchall()]

    # 2. 플랜별 사용자 분포
    cursor.execute("""
        SELECT COALESCE(plan, 'free') as plan, COUNT(*) as cnt
        FROM users
        GROUP BY plan
        ORDER BY cnt DESC
    """)
    plan_dist = [{"plan": r["plan"] or "free", "count": r["cnt"]} for r in cursor.fetchall()]

    # 3. 사용자 유형 분포 (기업/개인)
    cursor.execute("""
        SELECT COALESCE(user_type, 'both') as utype, COUNT(*) as cnt
        FROM users
        GROUP BY user_type
        ORDER BY cnt DESC
    """)
    type_dist = [{"type": r["utype"] or "business", "count": r["cnt"]} for r in cursor.fetchall()]

    # 4. AI 상담 일별 추이 (최근 30일)
    ai_usage_trend = [{"date": str(r["chat_date"]), "count": r["cnt"]} for r in _safe_query("""
        SELECT DATE(created_at) as chat_date, COUNT(*) as cnt
        FROM ai_consult_logs
        WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(created_at) ORDER BY chat_date
    """)]

    # 5. AI 상담 총 통계
    ai_total = _safe_scalar("SELECT COUNT(*) as total FROM ai_consult_logs")
    ai_helpful = _safe_scalar("SELECT COUNT(*) as total FROM ai_consult_logs WHERE feedback = 'helpful'")
    ai_inaccurate = _safe_scalar("SELECT COUNT(*) as total FROM ai_consult_logs WHERE feedback = 'inaccurate'")

    # 6. 알림 발송 통계 (최근 30일)
    notif_raw = _safe_query("""
        SELECT DATE(sent_at) as send_date, status, COUNT(*) as cnt
        FROM notification_logs
        WHERE sent_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(sent_at), status ORDER BY send_date
    """)
    notif_by_date = {}
    for r in notif_raw:
        d = str(r["send_date"])
        if d not in notif_by_date:
            notif_by_date[d] = {"date": d, "success": 0, "failed": 0}
        if r["status"] == "sent":
            notif_by_date[d]["success"] += r["cnt"]
        else:
            notif_by_date[d]["failed"] += r["cnt"]
    notif_trend = sorted(notif_by_date.values(), key=lambda x: x["date"])

    # 7. 총 알림 발송 수
    notif_total = _safe_scalar("SELECT COUNT(*) as total FROM notification_logs")
    notif_success = _safe_scalar("SELECT COUNT(*) as total FROM notification_logs WHERE status = 'sent'")

    # 8. 저장 공고 수 (북마크)
    saved_total = _safe_scalar("SELECT COUNT(*) as total FROM saved_announcements")

    # 9. 푸시 구독자 수
    push_total = _safe_scalar("SELECT COUNT(*) as total FROM push_subscriptions")

    # 10. 알림 활성 사용자 수
    notif_active = _safe_scalar("SELECT COUNT(*) as total FROM notification_settings WHERE is_active = true")

    # 11. 지역별 사용자 분포
    cursor.execute("""
        SELECT COALESCE(address_city, '미입력') as city, COUNT(*) as cnt
        FROM users
        GROUP BY address_city
        ORDER BY cnt DESC
        LIMIT 15
    """)
    region_dist = [{"region": r["city"], "count": r["cnt"]} for r in cursor.fetchall()]

    # 12. 공고 수집 일별 추이 (최근 14일)
    cursor.execute("""
        SELECT DATE(created_at) as cdate, COUNT(*) as cnt
        FROM announcements
        WHERE created_at >= CURRENT_DATE - INTERVAL '14 days'
        GROUP BY DATE(created_at)
        ORDER BY cdate
    """)
    crawl_trend = [{"date": str(r["cdate"]), "count": r["cnt"]} for r in cursor.fetchall()]

    conn.close()
    return {
        "status": "SUCCESS",
        "data": {
            "signup_trend": signup_trend,
            "plan_distribution": plan_dist,
            "user_type_distribution": type_dist,
            "ai_usage_trend": ai_usage_trend,
            "ai_stats": {
                "total": ai_total,
                "helpful": ai_helpful,
                "inaccurate": ai_inaccurate,
            },
            "notification_trend": notif_trend,
            "notification_stats": {
                "total": notif_total,
                "success": notif_success,
                "failed": notif_total - notif_success,
            },
            "saved_total": saved_total,
            "push_subscribers": push_total,
            "notification_active_users": notif_active,
            "region_distribution": region_dist,
            "crawl_trend": crawl_trend,
        }
    }


def _fetch_ga4_data() -> dict:
    """GA4 REST API로 최근 30일 트래픽 데이터 조회 (경량 방식)"""
    try:
        ga4_creds_json = os.getenv("GA4_SERVICE_ACCOUNT_JSON", "")
        ga4_property_id = os.getenv("GA4_PROPERTY_ID", "")
        if not ga4_creds_json or not ga4_property_id:
            return {"error": "GA4 환경변수 미설정"}

        from google.oauth2 import service_account
        import google.auth.transport.requests

        creds_dict = json.loads(ga4_creds_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=["https://www.googleapis.com/auth/analytics.readonly"]
        )
        credentials.refresh(google.auth.transport.requests.Request())
        token = credentials.token
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        base_url = f"https://analyticsdata.googleapis.com/v1beta/properties/{ga4_property_id}:runReport"

        def _run_report(dimensions, metrics, limit=0):
            body = {
                "dateRanges": [{"startDate": "30daysAgo", "endDate": "today"}],
                "metrics": [{"name": m} for m in metrics],
            }
            if dimensions:
                body["dimensions"] = [{"name": d} for d in dimensions]
            if limit:
                body["limit"] = limit
            r = requests.post(base_url, headers=headers, json=body, timeout=15)
            return r.json() if r.status_code == 200 else {}

        # 1. 기본 지표
        res1 = _run_report([], ["activeUsers", "sessions", "screenPageViews", "averageSessionDuration", "bounceRate", "newUsers"])
        basic = {}
        if res1.get("rows"):
            for i, m in enumerate(res1.get("metricHeaders", [])):
                basic[m["name"]] = res1["rows"][0]["metricValues"][i]["value"]

        # 2. 일별 추이
        res2 = _run_report(["date"], ["activeUsers", "sessions"])
        daily = []
        for r in res2.get("rows", []):
            d = r["dimensionValues"][0]["value"]
            daily.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "users": int(r["metricValues"][0]["value"]), "sessions": int(r["metricValues"][1]["value"])})
        daily.sort(key=lambda x: x["date"])

        # 3. 유입 경로
        res3 = _run_report(["sessionDefaultChannelGroup"], ["sessions", "activeUsers"])
        channels = [{"channel": r["dimensionValues"][0]["value"], "sessions": int(r["metricValues"][0]["value"]), "users": int(r["metricValues"][1]["value"])} for r in res3.get("rows", [])]

        # 4. 디바이스
        res4 = _run_report(["deviceCategory"], ["sessions", "bounceRate"])
        devices = [{"device": r["dimensionValues"][0]["value"], "sessions": int(r["metricValues"][0]["value"]), "bounce_rate": r["metricValues"][1]["value"]} for r in res4.get("rows", [])]

        # 5. 인기 페이지
        res5 = _run_report(["pagePath"], ["screenPageViews", "activeUsers"], limit=10)
        pages = [{"path": r["dimensionValues"][0]["value"], "views": int(r["metricValues"][0]["value"]), "users": int(r["metricValues"][1]["value"])} for r in res5.get("rows", [])]

        return {"basic": basic, "daily_trend": daily, "channels": channels, "devices": devices, "top_pages": pages}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/admin/strategy-report", dependencies=[Depends(_verify_admin)])
def api_generate_strategy_report():
    """AI가 사용자 행동 데이터를 분석하여 활성화 전략 보고서 생성"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # ── 데이터 수집 ──
    # 1. 전체 사용자 수 & 최근 7일 신규
    cursor.execute("SELECT COUNT(*) as total FROM users")
    total_users = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE updated_at >= CURRENT_DATE - INTERVAL '7 days'")
    new_users_7d = cursor.fetchone()["cnt"]

    # 2. 이벤트 퍼널 (최근 30일)
    event_counts = {}
    try:
        cursor.execute("""
            SELECT event_type, COUNT(*) as cnt
            FROM user_events
            WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY event_type ORDER BY cnt DESC
        """)
        for r in cursor.fetchall():
            event_counts[r["event_type"]] = r["cnt"]
    except Exception:
        pass

    # 3. 플랜 분포
    cursor.execute("SELECT COALESCE(plan,'free') as plan, COUNT(*) as cnt FROM users GROUP BY plan")
    plan_dist = {r["plan"] or "free": r["cnt"] for r in cursor.fetchall()}

    # 4. 유형 분포
    cursor.execute("SELECT COALESCE(user_type,'unknown') as utype, COUNT(*) as cnt FROM users GROUP BY user_type")
    type_dist = {r["utype"] or "unknown": r["cnt"] for r in cursor.fetchall()}

    # 5. 지역 분포 (상위 10)
    cursor.execute("""
        SELECT COALESCE(address_city,'미입력') as city, COUNT(*) as cnt
        FROM users GROUP BY address_city ORDER BY cnt DESC LIMIT 10
    """)
    region_dist = {r["city"]: r["cnt"] for r in cursor.fetchall()}

    # 6. AI 상담 통계
    cursor.execute("SELECT COUNT(*) as total FROM ai_consult_logs")
    ai_total = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) as cnt FROM ai_consult_logs WHERE feedback='helpful'")
    ai_helpful = cursor.fetchone()["cnt"]
    cursor.execute("SELECT COUNT(*) as cnt FROM ai_consult_logs WHERE feedback='inaccurate'")
    ai_inaccurate = cursor.fetchone()["cnt"]

    # 7. 일별 가입 추이
    cursor.execute("""
        SELECT DATE(updated_at) as d, COUNT(*) as cnt FROM users
        WHERE updated_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(updated_at) ORDER BY d
    """)
    signup_trend = [{"date": str(r["d"]), "count": r["cnt"]} for r in cursor.fetchall()]

    # 8. 최근 이벤트 로그 샘플 (행동 패턴 파악용)
    event_samples = []
    try:
        cursor.execute("""
            SELECT event_type, COUNT(DISTINCT business_number) as unique_users, COUNT(*) as total,
                   MIN(created_at) as first_at, MAX(created_at) as last_at
            FROM user_events
            WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY event_type ORDER BY total DESC
        """)
        for r in cursor.fetchall():
            event_samples.append({
                "type": r["event_type"], "unique_users": r["unique_users"],
                "total": r["total"], "first": str(r["first_at"])[:10], "last": str(r["last_at"])[:10]
            })
    except Exception:
        pass

    # 9. 전환율 계산
    signups = event_counts.get("signup", 0) + event_counts.get("social_signup", 0)
    logins = event_counts.get("login", 0) + event_counts.get("social_login", 0)
    matchings = event_counts.get("matching", 0)
    upgrades = event_counts.get("upgrade", 0)

    conn.close()

    # ── GA4 데이터 조회 ──
    ga4 = _fetch_ga4_data()
    ga4_section = ""
    if "error" not in ga4:
        basic = ga4.get("basic", {})
        ga4_section = f"""
### Google Analytics 트래픽 데이터 (30일)
- 활성 사용자: {basic.get('activeUsers', 'N/A')}명
- 세션 수: {basic.get('sessions', 'N/A')}
- 페이지뷰: {basic.get('screenPageViews', 'N/A')}
- 평균 세션 시간: {float(basic.get('averageSessionDuration', 0)):.0f}초
- 이탈률: {float(basic.get('bounceRate', 0))*100:.1f}%
- 신규 사용자: {basic.get('newUsers', 'N/A')}명
- 일별 방문 추이: {json.dumps(ga4.get('daily_trend', [])[-7:], ensure_ascii=False)}
- 유입 경로: {json.dumps(ga4.get('channels', []), ensure_ascii=False)}
- 디바이스별: {json.dumps(ga4.get('devices', []), ensure_ascii=False)}
- 인기 페이지: {json.dumps(ga4.get('top_pages', [])[:5], ensure_ascii=False)}
"""
    else:
        ga4_section = f"\n### Google Analytics\n- 연동 상태: {ga4.get('error', '미설정')}\n"

    # ── Gemini로 전략 보고서 생성 ──
    data_summary = f"""
## 지원금AI 서비스 현황 데이터 (최근 30일)
{ga4_section}
### 사용자 현황
- 전체 사용자: {total_users}명
- 최근 7일 신규 가입: {new_users_7d}명
- 플랜 분포: {json.dumps(plan_dist, ensure_ascii=False)}
- 유형 분포: {json.dumps(type_dist, ensure_ascii=False)}
- 지역 분포 (Top10): {json.dumps(region_dist, ensure_ascii=False)}

### 행동 퍼널 (30일)
- 가입: {signups}건
- 로그인: {logins}건
- 매칭 실행: {matchings}건
- 유료 전환: {upgrades}건
- 전환율: 가입→로그인 {f'{logins/signups*100:.0f}%' if signups > 0 else 'N/A'}, 로그인→매칭 {f'{matchings/logins*100:.0f}%' if logins > 0 else 'N/A'}, 매칭→결제 {f'{upgrades/matchings*100:.0f}%' if matchings > 0 else 'N/A'}

### 이벤트 상세
{json.dumps(event_samples, ensure_ascii=False, indent=2)}

### 일별 가입 추이
{json.dumps(signup_trend, ensure_ascii=False)}

### AI 상담
- 총 상담: {ai_total}건
- 도움됨: {ai_helpful}건, 부정확: {ai_inaccurate}건
- 만족도: {f'{ai_helpful/(ai_helpful+ai_inaccurate)*100:.0f}%' if (ai_helpful+ai_inaccurate) > 0 else 'N/A'}
"""

    prompt = f"""당신은 SaaS 서비스 성장 전략 전문가입니다.

아래는 "지원금AI" (govmatch.kr) 서비스의 실제 데이터입니다.
이 서비스는 AI 기반 정부 지원금/보조금 자동 매칭 서비스입니다.
사업자(기업)와 개인 사용자 모두를 대상으로 합니다.

{data_summary}

위 데이터를 기반으로 아래 형식의 전략 보고서를 작성해주세요.
반드시 **데이터에 기반한 구체적 수치**를 인용하고, **실행 가능한 액션**을 제시하세요.

## 보고서 형식

### 1. 핵심 지표 요약
- 현재 서비스 상태를 3줄로 요약

### 2. 퍼널 분석 & 병목 지점
- 가입→로그인→매칭→결제 각 단계별 전환율 분석
- 가장 큰 이탈 지점과 원인 추정

### 3. 사용자 세그먼트 인사이트
- 어떤 유형(기업/개인)이 더 활발한지
- 어떤 지역이 성장 잠재력이 높은지

### 4. 즉시 실행 가능한 개선 액션 (TOP 5)
- 각 액션에 예상 효과와 구현 난이도(상/중/하) 포함

### 5. 중장기 성장 전략
- 3개월, 6개월 목표와 로드맵

한국어로 작성하세요. 마크다운 형식으로 작성하세요.
"""

    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(prompt)
            report_text = response.text
        else:
            report_text = f"# Gemini API 키 미설정\n\n데이터 요약:\n{data_summary}"
    except Exception as e:
        report_text = f"# AI 분석 오류\n\n{str(e)}\n\n## 데이터 요약\n{data_summary}"

    # 보고서 캐시 저장
    try:
        conn2 = get_db_connection()
        cur2 = conn2.cursor()
        cur2.execute(
            "INSERT INTO strategy_reports (report_type, report_data) VALUES (%s, %s)",
            ("weekly", report_text)
        )
        conn2.commit()
        conn2.close()
    except Exception:
        pass

    return {
        "status": "SUCCESS",
        "report": report_text,
        "data_summary": {
            "total_users": total_users,
            "new_users_7d": new_users_7d,
            "funnel": {"signups": signups, "logins": logins, "matchings": matchings, "upgrades": upgrades},
            "plan_distribution": plan_dist,
            "type_distribution": type_dist,
            "region_distribution": region_dist,
        }
    }


@app.get("/api/admin/strategy-reports", dependencies=[Depends(_verify_admin)])
def api_get_strategy_reports(limit: int = 5):
    """저장된 전략 보고서 이력 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, report_type, report_data, created_at FROM strategy_reports ORDER BY created_at DESC LIMIT %s",
        (limit,)
    )
    rows = [{"id": r["id"], "type": r["report_type"], "report": r["report_data"], "created_at": str(r["created_at"])} for r in cursor.fetchall()]
    conn.close()
    return {"status": "SUCCESS", "data": rows}


@app.get("/api/admin/system-logs", dependencies=[Depends(_verify_admin)])
def api_get_system_logs(category: Optional[str] = None, limit: int = 50):
    """시스템 활동 이력 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if category:
            cursor.execute(
                "SELECT * FROM system_logs WHERE category = %s ORDER BY created_at DESC LIMIT %s",
                (category, min(limit, 200))
            )
        else:
            cursor.execute(
                "SELECT * FROM system_logs ORDER BY created_at DESC LIMIT %s",
                (min(limit, 200),)
            )
        rows = [dict(r) for r in cursor.fetchall()]
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = str(r["created_at"])

        # 카테고리별 최근 실행 요약
        cursor.execute("""
            SELECT category, action,
                   MAX(created_at) as last_run,
                   COUNT(*) as total_runs,
                   SUM(CASE WHEN result = 'success' THEN 1 ELSE 0 END) as success_count,
                   SUM(CASE WHEN result = 'error' THEN 1 ELSE 0 END) as error_count
            FROM system_logs
            WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY category, action
            ORDER BY last_run DESC
        """)
        summary = [dict(r) for r in cursor.fetchall()]
        for s in summary:
            if s.get("last_run"):
                s["last_run"] = str(s["last_run"])

        # 일별 시스템 활동 추이 (14일)
        daily_trend = []
        try:
            cursor.execute("""
                SELECT DATE(created_at) as log_date, category, COUNT(*) as cnt
                FROM system_logs
                WHERE created_at >= CURRENT_DATE - INTERVAL '14 days'
                GROUP BY DATE(created_at), category
                ORDER BY log_date
            """)
            trend_raw = {}
            for r in cursor.fetchall():
                d = str(r["log_date"])
                if d not in trend_raw:
                    trend_raw[d] = {"date": d, "collection": 0, "analysis": 0, "notification": 0, "payment": 0, "system": 0}
                cat = r["category"]
                if cat in trend_raw[d]:
                    trend_raw[d][cat] = r["cnt"]
            daily_trend = sorted(trend_raw.values(), key=lambda x: x["date"])
        except Exception:
            pass

        # 사용자 행동 퍼널 (30일, user_events 테이블)
        funnel = {}
        try:
            cursor.execute("""
                SELECT event_type, COUNT(*) as cnt, COUNT(DISTINCT business_number) as unique_users
                FROM user_events
                WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY event_type
            """)
            for r in cursor.fetchall():
                funnel[r["event_type"]] = {"count": r["cnt"], "unique_users": r["unique_users"]}
        except Exception:
            pass

        # 시간대별 사용자 활동 (user_events)
        hourly = []
        try:
            cursor.execute("""
                SELECT EXTRACT(HOUR FROM created_at)::int as hr, COUNT(*) as cnt
                FROM user_events
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY hr ORDER BY hr
            """)
            hourly = [{"hour": r["hr"], "count": r["cnt"]} for r in cursor.fetchall()]
        except Exception:
            pass

        conn.close()
        return {
            "status": "SUCCESS",
            "data": rows,
            "summary": summary,
            "daily_trend": daily_trend,
            "funnel": funnel,
            "hourly_activity": hourly,
        }
    except Exception as e:
        conn.close()
        return {"status": "SUCCESS", "data": [], "summary": [], "daily_trend": [], "funnel": {}, "hourly_activity": [], "note": f"테이블 미생성: {e}"}


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

@app.get("/api/admin/urls/health", dependencies=[Depends(_verify_admin)])
def get_admin_urls_health():
    """수집 URL 헬스체크 리포트 — 실패/복구 현황"""
    report = admin_scraper.get_health_report()
    return {"status": "SUCCESS", "data": report}

@app.post("/api/admin/seed-urls", dependencies=[Depends(_verify_admin)])
def admin_seed_urls():
    """seed_regional_urls에 등록된 URL을 DB에 일괄 등록"""
    try:
        from app.db.seed_regional_urls import REGIONAL_URLS
    except ImportError:
        try:
            import importlib, sys
            spec = importlib.util.spec_from_file_location("seed", os.path.join(os.path.dirname(__file__), "db", "seed_regional_urls.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            REGIONAL_URLS = mod.REGIONAL_URLS
        except Exception as e:
            return {"status": "ERROR", "detail": f"import 실패: {e}", "inserted": 0, "skipped": 0, "total": 0}

    if not REGIONAL_URLS:
        return {"status": "ERROR", "detail": "REGIONAL_URLS가 비어있음", "inserted": 0, "skipped": 0, "total": 0}

    conn = get_db_connection()
    cursor = conn.cursor()
    inserted, skipped, errors = 0, 0, []
    for source_name, url in REGIONAL_URLS:
        try:
            cursor.execute(
                """INSERT INTO admin_urls (url, source_name, is_active)
                   VALUES (%s, %s, 1)
                   ON CONFLICT (url) DO NOTHING""",
                (url, source_name),
            )
            conn.commit()
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            conn.rollback()
            errors.append(f"{source_name}: {str(e)[:80]}")
    conn.close()
    return {"status": "SUCCESS", "inserted": inserted, "skipped": skipped, "total": inserted + skipped, "source_count": len(REGIONAL_URLS), "errors": errors[:5]}


@app.post("/api/admin/cleanup-db", dependencies=[Depends(_verify_admin)])
def admin_cleanup_db():
    """DB 정리: 비지원사업 제거 + 중복 제거 + target_type 분류"""
    _cleanup_non_support_announcements()
    _deduplicate_announcements()
    _auto_classify_target_type()
    return {"status": "SUCCESS", "message": "DB 정리 + 분류 완료"}


def _run_manual_sync_in_thread():
    """관리자 수동 동기화를 별도 스레드에서 실행"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    manual_sync_status["running"] = True
    manual_sync_status["last_result"] = "진행 중..."
    manual_sync_status["last_time"] = datetime.datetime.now().isoformat()
    try:
        loop.run_until_complete(admin_scraper.run_all())
        manual_sync_status["last_result"] = "완료"
        _log_system("manual_sync", "collection", "수동 URL 수집 완료", "success")
    except Exception as e:
        manual_sync_status["last_result"] = f"오류: {e}"
        _log_system("manual_sync", "collection", f"수동 URL 수집 오류: {e}", "error")
    finally:
        manual_sync_status["running"] = False
        manual_sync_status["last_time"] = datetime.datetime.now().isoformat()
        loop.close()


@app.post("/api/admin/sync-manual", dependencies=[Depends(_verify_admin)])
async def trigger_admin_sync():
    if manual_sync_status["running"]:
        return {"status": "ALREADY_RUNNING", "message": "수동 동기화가 이미 진행 중입니다."}
    import threading
    t = threading.Thread(target=_run_manual_sync_in_thread, daemon=True)
    t.start()
    return {"status": "STARTED", "message": "백그라운드에서 수동 동기화를 시작합니다."}


@app.get("/api/admin/sync-manual-status", dependencies=[Depends(_verify_admin)])
def get_manual_sync_status():
    return {"status": "SUCCESS", "data": manual_sync_status}

def _run_reanalyze_in_thread(limit: int):
    """재분석을 별도 스레드에서 실행 — 상세 페이지 크롤링 + AI 추출 + DB 컬럼 업데이트"""
    import asyncio
    import re as _re
    import time
    import requests
    from bs4 import BeautifulSoup
    from app.services.ai_service import ai_service as _ai

    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    def _strip(text):
        if not text:
            return ""
        text = _re.sub(r'<[^>]+>', ' ', text)
        text = _re.sub(r'&[a-z]+;', ' ', text)
        text = _re.sub(r'&#\d+;', ' ', text)
        text = _re.sub(r'\s+', ' ', text)
        return text.strip()

    def _fetch_detail(url, max_chars=8000):
        """상세 페이지 크롤링하여 본문 텍스트 추출"""
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=12, allow_redirects=True)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 1]
            return "\n".join(lines)[:max_chars]
        except Exception:
            return ""

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    reanalyze_status["running"] = True
    reanalyze_status["done"] = 0
    reanalyze_status["last_time"] = datetime.datetime.now().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    # AI 미분석 공고만 대상 (ai_analyzed_at이 NULL인 건)
    # eligibility_logic이 비어있거나 한 번도 AI 분석을 하지 않은 공고
    cursor.execute("""
        SELECT announcement_id, title, summary_text, origin_url, deadline_date,
               established_years_limit, revenue_limit, employee_limit
        FROM announcements
        WHERE ai_analyzed_at IS NULL
          AND (
            eligibility_logic IS NULL OR eligibility_logic = '' OR eligibility_logic = '{}'
            OR (established_years_limit IS NULL AND revenue_limit IS NULL AND employee_limit IS NULL)
          )
        ORDER BY created_at DESC
        LIMIT %s
    """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    reanalyze_status["total"] = len(rows)

    success = 0
    for row in rows:
        try:
            # 1. 상세 페이지 크롤링 시도
            detail_text = ""
            origin_url = row.get("origin_url", "")
            if origin_url and origin_url.startswith("http"):
                detail_text = _fetch_detail(origin_url)

            # 2. 분석용 텍스트 구성 (상세 페이지 + 기존 요약)
            clean_summary = _strip(row.get("summary_text", ""))
            if detail_text and len(detail_text) > 100:
                input_text = f"제목: {row.get('title', '')}\n\n[상세 페이지 본문]\n{detail_text}"
            else:
                input_text = f"제목: {row.get('title', '')}\n\n내용: {clean_summary[:8000]}"

            if len(input_text) < 30:
                reanalyze_status["done"] += 1
                continue

            # 3. AI 분석 (구조화된 자격요건 추출)
            details = loop.run_until_complete(_ai.extract_program_details(input_text))
            if details:
                elig = details.get("eligibility_logic", {}) or {}
                if details.get("business_type"):
                    elig["business_type"] = details["business_type"]
                if details.get("target_keywords"):
                    elig["target_keywords"] = details["target_keywords"]

                # 4. eligibility 수치 추출
                years_limit = elig.get("max_founding_years")
                revenue_limit = elig.get("max_revenue")
                employee_limit = elig.get("max_employee_count") or elig.get("max_employees")

                ai_summary = details.get("summary_text") or details.get("description", "")
                ai_deadline = details.get("deadline_date")
                pk = row.get("announcement_id")

                cursor.execute("""
                    UPDATE announcements SET
                        eligibility_logic = %s,
                        summary_text = CASE WHEN %s != '' THEN %s ELSE summary_text END,
                        department = CASE WHEN department IS NULL OR department = '' THEN %s ELSE department END,
                        category = CASE WHEN category IS NULL OR category = '' THEN %s ELSE category END,
                        deadline_date = CASE WHEN deadline_date IS NULL AND %s IS NOT NULL THEN CAST(%s AS DATE) ELSE deadline_date END,
                        established_years_limit = COALESCE(%s, established_years_limit),
                        revenue_limit = COALESCE(%s, revenue_limit),
                        employee_limit = COALESCE(%s, employee_limit),
                        ai_analyzed_at = NOW()
                    WHERE announcement_id = %s
                """, (
                    json.dumps(elig, ensure_ascii=False),
                    ai_summary, ai_summary,
                    details.get("department", ""),
                    details.get("category", ""),
                    ai_deadline, ai_deadline,
                    years_limit, revenue_limit, employee_limit,
                    pk,
                ))
                conn.commit()
                success += 1
                if success % 10 == 0:
                    print(f"  [Reanalyze] {success} updated so far ({reanalyze_status['done']}/{len(rows)})")
        except Exception as e:
            print(f"Reanalyze error: {e}")
            conn.rollback()
        reanalyze_status["done"] += 1
        time.sleep(0.5)

    conn.close()
    reanalyze_status["running"] = False
    reanalyze_status["last_result"] = f"완료: {success}/{len(rows)}건 분석"
    reanalyze_status["last_time"] = datetime.datetime.now().isoformat()
    loop.close()
    _log_system("reanalyze", "analysis", f"{success}/{len(rows)}건 AI 재분석 완료", "success", success)
    print(f"[Reanalyze] Done: {success}/{len(rows)} announcements enriched")


@app.post("/api/admin/reanalyze", dependencies=[Depends(_verify_admin)])
async def trigger_reanalyze(limit: int = 200):
    if reanalyze_status["running"]:
        return {"status": "ALREADY_RUNNING", "message": "재분석이 이미 진행 중입니다."}
    import threading
    t = threading.Thread(target=_run_reanalyze_in_thread, args=(limit,), daemon=True)
    t.start()
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
def api_save_profile(profile: UserProfile, current_user: dict = Depends(_get_current_user)):
    """
    UPSERT logic for user profile. Requires password re-verification for existing users.
    """
    # 소유권 검증: 자신의 프로필만 수정 가능
    if profile.business_number != current_user["bn"]:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 기존 사용자인지 확인 + 비밀번호 검증
        cursor.execute("SELECT password_hash FROM users WHERE business_number = %s", (profile.business_number,))
        existing = cursor.fetchone()
        if existing and existing.get("password_hash"):
            if not profile.password:
                raise HTTPException(status_code=401, detail="프로필 변경 시 비밀번호 확인이 필요합니다.")
            if not _verify_password(profile.password, existing["password_hash"]):
                raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")

        query = """
        INSERT INTO users (business_number, company_name, establishment_date, address_city, industry_code, revenue_bracket, employee_count_bracket, interests, user_type, age_range, income_level, family_type, employment_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(business_number) DO UPDATE SET
            company_name=COALESCE(EXCLUDED.company_name, users.company_name),
            establishment_date=COALESCE(EXCLUDED.establishment_date, users.establishment_date),
            address_city=COALESCE(EXCLUDED.address_city, users.address_city),
            industry_code=COALESCE(EXCLUDED.industry_code, users.industry_code),
            revenue_bracket=COALESCE(EXCLUDED.revenue_bracket, users.revenue_bracket),
            employee_count_bracket=COALESCE(EXCLUDED.employee_count_bracket, users.employee_count_bracket),
            interests=COALESCE(EXCLUDED.interests, users.interests),
            user_type=COALESCE(EXCLUDED.user_type, users.user_type),
            age_range=COALESCE(EXCLUDED.age_range, users.age_range),
            income_level=COALESCE(EXCLUDED.income_level, users.income_level),
            family_type=COALESCE(EXCLUDED.family_type, users.family_type),
            employment_status=COALESCE(EXCLUDED.employment_status, users.employment_status)
        """
        cursor.execute(query, (
            profile.business_number, profile.company_name, profile.establishment_date,
            profile.address_city, profile.industry_code, profile.revenue_bracket,
            profile.employee_count_bracket, profile.interests,
            profile.user_type, profile.age_range, profile.income_level,
            profile.family_type, profile.employment_status
        ))
        conn.commit()
        return {"status": "SUCCESS", "message": "프로필이 저장되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/ai/parse-interests")
def api_parse_interests(req: dict):
    """사용자가 입력한 자유 텍스트를 카테고리로 매핑 (Gemini)"""
    text = (req.get("text") or "").strip()
    user_type = req.get("user_type", "both")
    if not text:
        return {"status": "SUCCESS", "interests": []}

    import google.generativeai as genai
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"status": "SUCCESS", "interests": [text]}

    biz_cats = "창업지원,기술개발,수출마케팅,고용지원,시설개선,정책자금,디지털전환,판로개척,교육훈련,에너지환경,소상공인,R&D"
    ind_cats = "취업,주거,교육,청년,출산,육아,다자녀,장학금,의료,장애,저소득,노인,문화"
    cats = ind_cats if user_type == "individual" else biz_cats

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        resp = model.generate_content(
            f"사용자가 관심분야를 다음과 같이 입력했습니다: \"{text}\"\n\n"
            f"아래 카테고리 목록에서 관련된 것을 모두 골라 JSON 배열로만 반환하세요. 카테고리 목록: [{cats}]\n"
            f"반드시 목록에 있는 정확한 단어만 사용하세요. 해당하는 것이 없으면 빈 배열 []을 반환하세요.\n"
            f"JSON 배열만 반환. 다른 텍스트 없이.",
            generation_config={"temperature": 0}
        )
        import json as _json
        parsed = _json.loads(resp.text.strip().strip("`").replace("json\n", ""))
        valid = [c for c in parsed if c in cats]
        return {"status": "SUCCESS", "interests": valid if valid else [text]}
    except Exception as e:
        print(f"[ParseInterests] Error: {e}")
        return {"status": "SUCCESS", "interests": [text]}


@app.put("/api/profile")
def api_update_profile(req: dict, current_user: dict = Depends(_get_current_user)):
    """프로필 간편 업데이트 (알림 설정에서 호출)"""
    bn = current_user["bn"]
    conn = get_db_connection()
    cur = conn.cursor()
    fields = []
    params = []
    allowed_keys = [
        "user_type", "address_city", "revenue_bracket", "employee_count_bracket",
        "interests", "custom_needs", "custom_keywords",
        "gender", "age_range", "income_level", "family_type", "employment_status",
        "founded_date", "is_pre_founder", "certifications",
    ]
    # user_type 값 검증
    if "user_type" in req and req["user_type"] not in ("individual", "business", "both", None):
        conn.close()
        raise HTTPException(status_code=400, detail="유효하지 않은 user_type입니다. (individual, business, both 중 선택)")

    for key in allowed_keys:
        if key in req and req[key] is not None:
            fields.append(f"{key} = %s")
            params.append(req[key])
    if not fields:
        conn.close()
        return {"status": "SUCCESS"}
    # user_type 변경 시 구독 중이면 안내 메시지 추가
    price_notice = ""
    if "user_type" in req:
        cur2 = conn.cursor()
        cur2.execute("SELECT plan, user_type FROM users WHERE business_number = %s", (bn,))
        existing = cur2.fetchone()
        if existing:
            ex = dict(existing)
            old_type = ex.get("user_type") or "business"
            new_type = req["user_type"]
            if old_type != new_type and ex.get("plan") in ("lite", "pro"):
                price_notice = " 다음 결제 시 변경된 유형의 요금이 적용됩니다."

    params.append(bn)
    cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE business_number = %s", params)
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": f"프로필이 업데이트되었습니다.{price_notice}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 공고 분석 API (블로그봇 + 앱 공용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BLOG_API_KEY = os.getenv("BLOG_API_KEY", "")

def _verify_api_key(x_api_key: Optional[str] = Header(None)):
    """블로그봇용 API Key 인증"""
    if not BLOG_API_KEY:
        raise HTTPException(status_code=500, detail="BLOG_API_KEY가 설정되지 않았습니다.")
    if x_api_key != BLOG_API_KEY:
        raise HTTPException(status_code=401, detail="유효하지 않은 API Key입니다.")


def _format_analysis_response(announcement_id: int, analysis: dict, announcement: dict) -> dict:
    """분석 데이터를 블로그봇/앱 공용 응답 스키마로 변환"""
    da = analysis.get("deep_analysis", {}) or {}
    ps = analysis.get("parsed_sections", {}) or {}

    # eligibility_detail: deep_analysis 구조체 또는 parsed_sections 텍스트
    elig = da.get("eligibility_detail")
    if isinstance(elig, dict):
        # 구조체를 읽기 좋은 텍스트로도 변환
        elig_text = ""
        parts = []
        if elig.get("region") and elig["region"] != "전국":
            parts.append(f"지역: {elig['region']}")
        if elig.get("business_types"):
            parts.append(f"대상: {', '.join(elig['business_types'])}")
        if elig.get("other_conditions"):
            parts.extend(elig["other_conditions"])
        elig_text = " / ".join(parts) if parts else ""
        elig_combined = elig_text or ps.get("eligibility") or ""
    else:
        elig_combined = elig or ps.get("eligibility") or ""

    # 제출서류: deep_analysis.required_documents (list of dict) 또는 parsed_sections.required_docs (text)
    docs_raw = da.get("required_documents") or []
    docs_list = []
    if isinstance(docs_raw, list):
        for d in docs_raw:
            if isinstance(d, dict):
                docs_list.append(d.get("doc_name", str(d)))
            elif isinstance(d, str):
                docs_list.append(d)
    if not docs_list:
        # fallback: parsed_sections에서 추출
        ps_docs = ps.get("required_docs") or ""
        if isinstance(ps_docs, str) and ps_docs:
            docs_list = [line.strip().lstrip("- ·•◦") for line in ps_docs.split("\n") if line.strip() and len(line.strip()) > 1]

    # 신청방법
    app_method = ps.get("application_method") or ""
    if isinstance(app_method, str) and app_method:
        app_method_text = app_method
    else:
        app_method_text = da.get("application_method") or ""

    # 신청절차 → steps 파싱
    application_steps = []
    timeline_raw = ps.get("timeline") or ""
    if isinstance(timeline_raw, str) and timeline_raw:
        for i, line in enumerate(timeline_raw.split("\n")):
            line = line.strip().lstrip("- ·•◦0123456789.)")
            if line and len(line) > 2:
                application_steps.append({"step": i + 1, "title": line, "detail": ""})

    # 지원내용
    support_raw = ps.get("support_details") or ""
    support_summary = da.get("support_summary") or {}
    if isinstance(support_summary, dict) and support_summary.get("amount"):
        support_text = f"{support_summary.get('amount', '')} ({support_summary.get('duration', '')}, {support_summary.get('method', '')})"
    elif isinstance(support_raw, str) and support_raw:
        support_text = support_raw[:500]
    else:
        support_text = ""

    # 선정기준
    eval_raw = ps.get("evaluation_criteria") or ""
    eval_weights = da.get("evaluation_weights") or []
    if isinstance(eval_weights, list) and eval_weights:
        sel_criteria = " / ".join(f"{e.get('criteria','')}({e.get('weight','')})" for e in eval_weights if isinstance(e, dict))
    elif isinstance(eval_raw, str):
        sel_criteria = eval_raw[:300]
    else:
        sel_criteria = ""

    return {
        "announcement_id": announcement_id,
        "title": announcement.get("title", ""),
        "eligibility_detail": elig_combined,
        "eligibility_raw": ps.get("eligibility") or "",
        "exclusions": ps.get("exclusions") or "",
        "required_documents": docs_list,
        "application_method": app_method_text,
        "application_url": da.get("application_url") or announcement.get("origin_url") or "",
        "application_steps": application_steps,
        "support_detail": support_text,
        "support_summary": support_summary if isinstance(support_summary, dict) else {},
        "selection_criteria": sel_criteria,
        "bonus_items": da.get("bonus_items") or [],
        "key_warnings": da.get("key_warnings") or [],
        "target_age": da.get("target_age") or "",
        "target_region": da.get("target_region") or (da.get("eligibility_detail", {}) or {}).get("region", "") or announcement.get("region") or "",
        "target_family": da.get("target_family") or "",
        "deadline_date": str(announcement.get("deadline_date") or ""),
        "department": announcement.get("department") or "",
        "category": announcement.get("category") or "",
        "origin_url": announcement.get("origin_url") or "",
        "analyzed_at": str(analysis.get("updated_at") or datetime.datetime.utcnow().isoformat()),
        "source": analysis.get("source_type") or "unknown",
        "has_full_text": bool(analysis.get("full_text")),
    }


@app.get("/api/v1/announcements/{announcement_id}/analysis")
def api_get_analysis(announcement_id: int, raw: bool = False, _: None = Depends(_verify_api_key)):
    """저장된 분석 데이터 조회 (블로그봇용). raw=true면 DB 원본 데이터 포함"""
    conn = get_db_connection()
    try:
        from app.services.doc_analysis_service import get_deep_analysis
        analysis = get_deep_analysis(announcement_id, conn)
        if not analysis:
            conn.close()
            raise HTTPException(status_code=404, detail="분석 데이터가 없습니다. POST /analyze로 분석을 먼저 실행하세요.")

        cur = conn.cursor()
        cur.execute("SELECT * FROM announcements WHERE announcement_id = %s", (announcement_id,))
        ann = cur.fetchone()
        if not ann:
            conn.close()
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")

        result = _format_analysis_response(announcement_id, analysis, dict(ann))
        response = {"status": "SUCCESS", "data": result}

        # raw=true면 DB 원본 데이터도 포함 (디버그용)
        if raw:
            response["_raw"] = {
                "parsed_sections": analysis.get("parsed_sections", {}),
                "deep_analysis": analysis.get("deep_analysis", {}),
                "full_text_length": len(analysis.get("full_text") or ""),
                "full_text_preview": (analysis.get("full_text") or "")[:500],
            }

        conn.close()
        return response
    except HTTPException:
        raise
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


def _verify_api_key_or_admin(authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)):
    """API Key 또는 admin JWT 둘 중 하나로 인증"""
    if x_api_key and BLOG_API_KEY and x_api_key == BLOG_API_KEY:
        return
    if authorization:
        try:
            _verify_admin(authorization)
            return
        except Exception:
            pass
    raise HTTPException(status_code=401, detail="API Key 또는 admin 인증이 필요합니다.")


@app.post("/api/v1/announcements/{announcement_id}/analyze")
def api_analyze_announcement(announcement_id: int, force: bool = False, _: None = Depends(_verify_api_key_or_admin)):
    """공고 원문 크롤링 + AI 분석 + DB 저장"""
    conn = get_db_connection()
    try:
        from app.services.doc_analysis_service import ensure_analysis, get_deep_analysis

        # 이미 분석됐으면 바로 반환 (force=True면 재분석)
        if not force:
            existing = get_deep_analysis(announcement_id, conn)
            if existing and existing.get("full_text"):
                cur = conn.cursor()
                cur.execute("SELECT * FROM announcements WHERE announcement_id = %s", (announcement_id,))
                ann = cur.fetchone()
                if ann:
                    result = _format_analysis_response(announcement_id, existing, dict(ann))
                    conn.close()
                    return {"status": "SUCCESS", "cached": True, "data": result}

        # 실시간 분석 (force면 재크롤링+재분석)
        analysis = ensure_analysis(announcement_id, conn, force=force)
        if not analysis:
            conn.close()
            raise HTTPException(status_code=422, detail="분석 실패: 원문 접근 불가 또는 AI 분석 오류")

        cur = conn.cursor()
        cur.execute("SELECT * FROM announcements WHERE announcement_id = %s", (announcement_id,))
        ann = cur.fetchone()
        if not ann:
            conn.close()
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")

        result = _format_analysis_response(announcement_id, analysis, dict(ann))
        conn.close()
        return {"status": "SUCCESS", "cached": False, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


from app.services.sync_service import sync_service

def _run_sync_in_thread():
    """동기화를 별도 스레드에서 실행 (이벤트 루프 블로킹 방지)"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    sync_status["running"] = True
    sync_status["last_result"] = "진행 중..."
    sync_status["last_time"] = datetime.datetime.now().isoformat()
    try:
        loop.run_until_complete(sync_service.sync_all())
        sync_status["last_result"] = "완료"
        _log_system("api_sync", "collection", "전체 API 데이터 수집 완료", "success")
    except Exception as e:
        sync_status["last_result"] = f"오류: {e}"
        _log_system("api_sync", "collection", f"API 수집 오류: {e}", "error")
    finally:
        sync_status["running"] = False
        sync_status["last_time"] = datetime.datetime.now().isoformat()
        loop.close()


@app.post("/api/sync", dependencies=[Depends(_verify_admin)])
async def api_sync_data():
    if sync_status["running"]:
        return {"status": "ALREADY_RUNNING", "message": "동기화가 이미 진행 중입니다."}
    import threading
    t = threading.Thread(target=_run_sync_in_thread, daemon=True)
    t.start()
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
        "title": "지원금AI",
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

    _log_system("push_test", "notification", f"발송 {sent}건, 실패 {failed}건", "success" if failed == 0 else "partial", sent)
    return {"status": "SUCCESS", "message": f"발송 {sent}건, 실패 {failed}건"}


@app.post("/api/match")
def api_match_programs(request: BusinessNumberRequest, current_user: dict = Depends(_get_current_user)):
    """
    Fetches user profile and runs the hybrid matching engine.
    """
    # 소유권 검증: 자신의 business_number만 매칭 가능
    if request.business_number != current_user["bn"]:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE business_number = %s", (request.business_number,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")

    user_dict = dict(user)

    # user_type에 따라 매칭 엔진 분기 (미설정 시 both로 개인+기업 모두)
    user_type = user_dict.get("user_type") or "both"
    if user_type == "individual":
        matches = get_individual_matches_for_user(user_dict)
    elif user_type == "both":
        biz_matches = get_matches_for_user(user_dict)
        ind_matches = get_individual_matches_for_user(user_dict)
        matches = biz_matches + ind_matches
        matches.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    else:
        matches = get_matches_for_user(user_dict)
    # 상위 100건만 반환 (점수순 정렬 후, 프론트에서 20건씩 페이지네이션)
    matches = matches[:100]

    # AI 추출 데이터 보완 (프론트엔드 대응)
    for match in matches:
        if match.get("eligibility_logic") and isinstance(match["eligibility_logic"], str):
            try:
                match["eligibility_logic"] = json.loads(match["eligibility_logic"])
            except (json.JSONDecodeError, TypeError):
                pass

    _log_event("matching", request.business_number, f"type={user_type},count={len(matches)},top_score={matches[0].get('match_score',0) if matches else 0}")
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
        INSERT INTO notification_settings (business_number, email, phone_number, channel, is_active, kakao_enabled)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT(business_number) DO UPDATE SET
            email=EXCLUDED.email,
            phone_number=EXCLUDED.phone_number,
            channel=EXCLUDED.channel,
            is_active=EXCLUDED.is_active,
            kakao_enabled=EXCLUDED.kakao_enabled,
            updated_at=NOW()
        """
        cursor.execute(query, (
            settings.business_number, settings.email, settings.phone_number,
            settings.channel, int(settings.is_active), int(settings.kakao_enabled or 0)
        ))
        conn.commit()
        return {"status": "SUCCESS", "message": "알림 설정이 저장되었습니다."}
    except Exception as e:
        conn.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/notification-settings/{bn}")
def api_get_notification_settings(bn: str, current_user: dict = Depends(_get_current_user)):
    """
    Retrieves user notification preferences.
    """
    if bn != current_user["bn"]:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
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
                "is_active": True
            }
        }

@app.post("/api/admin/send-digest", dependencies=[Depends(_verify_admin)])
async def api_send_digest():
    """데일리 다이제스트를 즉시 생성하고 이메일 발송 (관리자용)"""
    from app.services.notification_service import notification_service
    results = await notification_service.generate_daily_digest()
    sent_count = sum(1 for r in results if r.get("email_sent"))
    _log_system("send_digest", "notification", f"{len(results)}명 대상, {sent_count}건 이메일 발송", "success", sent_count)
    return {
        "status": "SUCCESS",
        "message": f"다이제스트 생성 완료: {len(results)}명 대상, {sent_count}건 이메일 발송",
        "data": results
    }


class SavedBulk(BaseModel):
    business_number: str
    announcement_ids: List[int]


@app.post("/api/saved/bulk")
def api_save_bulk(body: SavedBulk, current_user: dict = Depends(_get_current_user)):
    if body.business_number != current_user["bn"]:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    # FREE 플랜: 저장 불가
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT plan, plan_expires_at FROM users WHERE business_number=%s", (current_user["bn"],))
    u = cursor.fetchone()
    if u:
        plan = u["plan"] or "free"
        if plan != "free" and u["plan_expires_at"]:
            import datetime as _dt
            try:
                if _dt.datetime.fromisoformat(str(u["plan_expires_at"])) < _dt.datetime.utcnow():
                    plan = "free"
            except Exception:
                pass
        if plan == "free":
            conn.close()
            raise HTTPException(status_code=403, detail="LITE_REQUIRED")
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
def api_get_saved(bn: str, current_user: dict = Depends(_get_current_user)):
    if bn != current_user["bn"]:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
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
def api_delete_saved(saved_id: int, current_user: dict = Depends(_get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    # 소유권 확인 후 삭제
    cursor.execute("DELETE FROM saved_announcements WHERE id = %s AND business_number = %s", (saved_id, current_user["bn"]))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    if deleted:
        return {"status": "SUCCESS", "message": "삭제됨"}
    raise HTTPException(status_code=404, detail="해당 저장 항목을 찾을 수 없습니다.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRO 전용 API — 고객사 프로필 관리 / 상담 이력 / 종합 리포트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _require_pro(current_user: dict):
    """PRO 플랜 체크. PRO/biz가 아니면 403."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT plan, plan_expires_at FROM users WHERE business_number = %s", (current_user["bn"],))
    u = cur.fetchone()
    conn.close()
    if not u:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    plan = u["plan"] or "free"
    if plan not in ("pro", "biz"):
        raise HTTPException(status_code=403, detail="PRO 플랜 전용 기능입니다.")
    # 만료 체크
    if u.get("plan_expires_at"):
        import datetime as _dt
        try:
            exp = _dt.datetime.fromisoformat(str(u["plan_expires_at"]))
            if exp < _dt.datetime.utcnow():
                raise HTTPException(status_code=403, detail="플랜이 만료되었습니다. 갱신 후 이용하세요.")
        except ValueError:
            pass
    return current_user


# ── 1) 고객사 프로필 CRUD ──

class ClientProfileCreate(BaseModel):
    client_name: str
    client_type: Optional[str] = "business"  # "business" | "individual"
    business_number: Optional[str] = None
    establishment_date: Optional[str] = None
    address_city: Optional[str] = None
    industry_code: Optional[str] = None
    industry_name: Optional[str] = None
    revenue_bracket: Optional[str] = None
    employee_count_bracket: Optional[str] = None
    interests: Optional[str] = None
    memo: Optional[str] = ""


@app.get("/api/pro/clients")
def api_pro_clients(client_type: Optional[str] = None, current_user: dict = Depends(_get_current_user)):
    """PRO: 내 고객 프로필 목록 조회 (client_type 필터 가능)"""
    _require_pro(current_user)
    conn = get_db_connection()
    cur = conn.cursor()
    where = "owner_business_number = %s AND is_active = TRUE"
    params: list = [current_user["bn"]]
    if client_type:
        where += " AND COALESCE(client_type, 'business') = %s"
        params.append(client_type)
    cur.execute(
        f"""SELECT id, client_name, COALESCE(client_type, 'business') AS client_type,
                  business_number, address_city, industry_code, industry_name,
                  revenue_bracket, employee_count_bracket, establishment_date, interests, memo, created_at, updated_at
           FROM client_profiles
           WHERE {where}
           ORDER BY updated_at DESC""",
        params
    )
    rows = cur.fetchall()
    conn.close()
    clients = []
    for r in rows:
        d = dict(r)
        if d.get("establishment_date"):
            d["establishment_date"] = str(d["establishment_date"])
        if d.get("created_at"):
            d["created_at"] = str(d["created_at"])
        if d.get("updated_at"):
            d["updated_at"] = str(d["updated_at"])
        clients.append(d)
    return {"status": "SUCCESS", "clients": clients}


@app.post("/api/pro/clients")
def api_pro_client_create(req: ClientProfileCreate, current_user: dict = Depends(_get_current_user)):
    """PRO: 고객사 프로필 생성"""
    _require_pro(current_user)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO client_profiles
           (owner_business_number, client_name, client_type, business_number, establishment_date, address_city,
            industry_code, industry_name, revenue_bracket, employee_count_bracket, interests, memo)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (current_user["bn"], req.client_name, req.client_type or "business", req.business_number,
         req.establishment_date, req.address_city, req.industry_code, req.industry_name,
         req.revenue_bracket, req.employee_count_bracket, req.interests, req.memo)
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "id": new_id, "message": f"고객사 '{req.client_name}' 등록 완료"}


@app.put("/api/pro/clients/{client_id}")
def api_pro_client_update(client_id: int, req: ClientProfileCreate, current_user: dict = Depends(_get_current_user)):
    """PRO: 고객사 프로필 수정"""
    _require_pro(current_user)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """UPDATE client_profiles SET
           client_name=%s, client_type=%s, business_number=%s, establishment_date=%s, address_city=%s,
           industry_code=%s, industry_name=%s, revenue_bracket=%s, employee_count_bracket=%s,
           interests=%s, memo=%s, updated_at=CURRENT_TIMESTAMP
           WHERE id=%s AND owner_business_number=%s AND is_active=TRUE""",
        (req.client_name, req.client_type or "business", req.business_number, req.establishment_date, req.address_city,
         req.industry_code, req.industry_name, req.revenue_bracket, req.employee_count_bracket,
         req.interests, req.memo, client_id, current_user["bn"])
    )
    conn.commit()
    updated = cur.rowcount
    conn.close()
    if not updated:
        raise HTTPException(status_code=404, detail="고객사를 찾을 수 없습니다.")
    return {"status": "SUCCESS", "message": "수정 완료"}


@app.delete("/api/pro/clients/{client_id}")
def api_pro_client_delete(client_id: int, current_user: dict = Depends(_get_current_user)):
    """PRO: 고객사 프로필 삭제 (soft delete)"""
    _require_pro(current_user)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE client_profiles SET is_active=FALSE, updated_at=CURRENT_TIMESTAMP WHERE id=%s AND owner_business_number=%s",
        (client_id, current_user["bn"])
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="고객사를 찾을 수 없습니다.")
    return {"status": "SUCCESS", "message": "삭제 완료"}


# ── 2) 상담 이력 조회 + 엑셀 다운로드 ──

@app.get("/api/pro/consult-history")
def api_pro_consult_history(
    client_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(_get_current_user),
):
    """PRO: 상담 이력 조회 (고객사별 필터 가능)"""
    _require_pro(current_user)
    conn = get_db_connection()
    cur = conn.cursor()

    bn = current_user["bn"]
    if client_id:
        # 특정 고객사의 사업자번호로 필터
        cur.execute(
            "SELECT business_number FROM client_profiles WHERE id=%s AND owner_business_number=%s",
            (client_id, bn)
        )
        cp = cur.fetchone()
        if not cp:
            conn.close()
            raise HTTPException(status_code=404, detail="고객사를 찾을 수 없습니다.")
        filter_bn = cp["business_number"] or bn
    else:
        filter_bn = bn

    cur.execute(
        """SELECT cl.id, cl.announcement_id, a.title as announcement_title, a.category,
                  cl.conclusion, cl.feedback, cl.feedback_detail, cl.created_at,
                  cl.messages
           FROM ai_consult_logs cl
           LEFT JOIN announcements a ON a.announcement_id = cl.announcement_id
           WHERE cl.business_number = %s
           ORDER BY cl.created_at DESC
           LIMIT %s OFFSET %s""",
        (filter_bn, limit, offset)
    )
    rows = cur.fetchall()

    # 총 건수
    cur.execute("SELECT COUNT(*) as cnt FROM ai_consult_logs WHERE business_number = %s", (filter_bn,))
    total = cur.fetchone()["cnt"]
    conn.close()

    history = []
    for r in rows:
        d = dict(r)
        d["created_at"] = str(d["created_at"]) if d.get("created_at") else None
        # messages는 용량이 크므로 요약만
        msgs = d.pop("messages", None) or []
        if isinstance(msgs, list):
            d["message_count"] = len(msgs)
            # 마지막 사용자 질문만 추출
            last_q = ""
            for m in reversed(msgs):
                if isinstance(m, dict) and m.get("role") == "user":
                    last_q = m.get("text", "")[:100]
                    break
            d["last_question"] = last_q
        else:
            d["message_count"] = 0
            d["last_question"] = ""
        history.append(d)

    return {"status": "SUCCESS", "history": history, "total": total}


@app.get("/api/pro/consult-history/export")
def api_pro_consult_history_export(
    client_id: Optional[int] = None,
    current_user: dict = Depends(_get_current_user),
):
    """PRO: 상담 이력 엑셀(CSV) 다운로드"""
    _require_pro(current_user)
    import csv
    import io

    conn = get_db_connection()
    cur = conn.cursor()
    bn = current_user["bn"]

    if client_id:
        cur.execute(
            "SELECT business_number FROM client_profiles WHERE id=%s AND owner_business_number=%s",
            (client_id, bn)
        )
        cp = cur.fetchone()
        filter_bn = cp["business_number"] if cp and cp["business_number"] else bn
    else:
        filter_bn = bn

    cur.execute(
        """SELECT cl.id, cl.announcement_id, a.title as announcement_title, a.category, a.department,
                  a.support_amount, a.deadline_date,
                  cl.conclusion, cl.feedback, cl.feedback_detail, cl.created_at,
                  cl.messages
           FROM ai_consult_logs cl
           LEFT JOIN announcements a ON a.announcement_id = cl.announcement_id
           WHERE cl.business_number = %s
           ORDER BY cl.created_at DESC""",
        (filter_bn,)
    )
    rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "상담ID", "공고ID", "공고명", "카테고리", "부처", "지원금액", "마감일",
        "결론", "피드백", "피드백상세", "상담일시", "대화수", "마지막질문"
    ])

    for r in rows:
        d = dict(r)
        msgs = d.get("messages") or []
        msg_count = len(msgs) if isinstance(msgs, list) else 0
        last_q = ""
        if isinstance(msgs, list):
            for m in reversed(msgs):
                if isinstance(m, dict) and m.get("role") == "user":
                    last_q = m.get("text", "")[:200]
                    break
        conclusion_map = {"eligible": "지원가능", "conditional": "조건부가능", "ineligible": "지원불가"}
        writer.writerow([
            d.get("id"), d.get("announcement_id"), d.get("announcement_title", ""),
            d.get("category", ""), d.get("department", ""),
            d.get("support_amount", ""), str(d.get("deadline_date", "")),
            conclusion_map.get(d.get("conclusion"), d.get("conclusion") or "미판정"),
            d.get("feedback", ""), d.get("feedback_detail", ""),
            str(d.get("created_at", "")), msg_count, last_q
        ])

    from fastapi.responses import StreamingResponse
    output.seek(0)
    # BOM for Excel UTF-8 compatibility
    bom_output = io.BytesIO()
    bom_output.write(b'\xef\xbb\xbf')
    bom_output.write(output.getvalue().encode("utf-8"))
    bom_output.seek(0)

    return StreamingResponse(
        bom_output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=consult_history.csv"}
    )


# ── 3) 종합 리포트 ──

class ReportRequest(BaseModel):
    client_profile_id: int


@app.post("/api/pro/reports/generate")
def api_pro_report_generate(req: ReportRequest, current_user: dict = Depends(_get_current_user)):
    """PRO: 고객사 종합 리포트 생성 — 매칭 + 상담 이력 + AI 종합 요약"""
    _require_pro(current_user)
    conn = get_db_connection()
    cur = conn.cursor()

    # 1. 고객 프로필 조회
    cur.execute(
        """SELECT * FROM client_profiles WHERE id=%s AND owner_business_number=%s AND is_active=TRUE""",
        (req.client_profile_id, current_user["bn"])
    )
    client = cur.fetchone()
    if not client:
        conn.close()
        raise HTTPException(status_code=404, detail="고객사를 찾을 수 없습니다.")
    client = dict(client)

    # 2. 매칭 엔진으로 공고 검색 — 기업/개인 분기
    from app.core.matcher import get_matches_for_user, get_individual_matches_for_user
    profile = {
        "address_city": client.get("address_city") or "",
        "industry_code": client.get("industry_code") or "",
        "revenue_bracket": client.get("revenue_bracket") or "",
        "employee_count_bracket": client.get("employee_count_bracket") or "",
        "interests": client.get("interests") or "",
        "establishment_date": str(client.get("establishment_date") or ""),
    }
    is_individual_client = (client.get("client_type") or "business") == "individual"
    if is_individual_client:
        matched = get_individual_matches_for_user(profile)
    else:
        matched = get_matches_for_user(profile)

    # 3. 각 공고에 대해 판정
    results = []
    eligible_count = 0
    conditional_count = 0
    ineligible_count = 0

    for ann in matched:
        a = ann if isinstance(ann, dict) else dict(ann)
        score = a.get("match_score", 0)
        if score >= 80:
            conclusion = "eligible"
            reason = "매칭 점수가 높아 지원 가능성이 높습니다."
            eligible_count += 1
        elif score >= 50:
            conclusion = "conditional"
            reason = "일부 조건 확인이 필요합니다."
            conditional_count += 1
        else:
            conclusion = "conditional"
            reason = "추가 확인이 필요한 항목이 있습니다."
            conditional_count += 1

        results.append({
            "announcement_id": a.get("announcement_id"),
            "title": a.get("title", ""),
            "category": a.get("category", ""),
            "department": a.get("department", ""),
            "conclusion": conclusion,
            "reason": reason,
            "support_amount": a.get("support_amount", ""),
            "deadline_date": str(a.get("deadline_date", "")),
            "match_score": score,
        })

    # 4. 공고AI 상담 이력 수집 (이 고객사 관련 최근 30건)
    consult_summaries = []
    try:
        cur.execute(
            """SELECT a.title, cl.conclusion, cl.messages, cl.created_at
               FROM ai_consult_logs cl
               JOIN announcements a ON a.announcement_id = cl.announcement_id
               WHERE cl.business_number = %s
               ORDER BY cl.created_at DESC LIMIT 30""",
            (current_user["bn"],)
        )
        for row in cur.fetchall():
            r = dict(row)
            msgs = r.get("messages") or []
            # 마지막 AI 응답만 추출
            last_ai = ""
            if isinstance(msgs, list):
                for m in reversed(msgs):
                    if m.get("role") == "assistant":
                        last_ai = m.get("text", "")[:200]
                        break
            consult_summaries.append({
                "title": r.get("title", ""),
                "conclusion": r.get("conclusion", ""),
                "summary": last_ai,
            })
    except Exception:
        pass

    # 5. AI 종합 요약 생성
    ai_summary = ""
    try:
        import google.generativeai as genai
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key and results:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("models/gemini-2.0-flash")

            top_eligible = [r for r in results if r["conclusion"] == "eligible"][:5]
            top_conditional = [r for r in results if r["conclusion"] == "conditional"][:5]

            consult_text = ""
            if consult_summaries:
                consult_text = "\n\n[공고별 상담 이력]\n"
                for cs in consult_summaries[:10]:
                    consult_text += f"- {cs['title']}: {cs['conclusion'] or '미판정'} — {cs['summary'][:100]}\n"

            # 마감일 임박 순 정렬
            today_str = datetime.date.today().isoformat()
            two_weeks = (datetime.date.today() + datetime.timedelta(days=14)).isoformat()
            urgent = [r for r in results if r.get("deadline_date") and r["deadline_date"] > today_str and r["deadline_date"] <= two_weeks]

            # f-string에서 줄바꿈 사용 위해 변수로 분리
            NL = "\n"
            eligible_lines = NL.join([f"- {r['title']} | {r['support_amount']} | 마감: {r['deadline_date']} | {r['match_score']}점" for r in top_eligible]) or "없음"
            conditional_lines = NL.join([f"- {r['title']} | {r['support_amount']} | 마감: {r['deadline_date']} | {r['match_score']}점" for r in top_conditional]) or "없음"
            urgent_lines = NL.join([f"- [긴급] {r['title']} | 마감: {r['deadline_date']}" for r in urgent]) or "없음"

            prompt = f"""당신은 10년 경력의 정부지원사업 전문 컨설턴트입니다.
아래 고객사 정보와 AI 매칭 결과를 바탕으로, 고객에게 전달할 **전문 컨설팅 리포트**를 작성하세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━
[고객사 정보]
━━━━━━━━━━━━━━━━━━━━━━━━━━
- 기업명: {client.get('client_name', '')}
- 소재지: {client.get('address_city', '')}
- 업종코드: {client.get('industry_code', '')}
- 설립일: {client.get('establishment_date', '')}
- 매출규모: {client.get('revenue_bracket', '')}
- 직원수: {client.get('employee_count_bracket', '')}
- 관심분야: {client.get('interests', '')}

[AI 매칭 결과]
- 총 {len(results)}건 매칭
- 지원가능(80점+): {eligible_count}건
- 조건부(50~79점): {conditional_count}건

[지원가능 공고]
{eligible_lines}

[조건부 상위 공고]
{conditional_lines}

[2주 내 마감 임박]
{urgent_lines}
{consult_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━
[리포트 작성 규칙] — 반드시 아래 7개 섹션을 모두 포함
━━━━━━━━━━━━━━━━━━━━━━━━━━

## 1. 기업 현황 분석
- 기업 개요 (업종 특성, 업력, 규모)
- 강점: 매칭에 유리한 조건 (예: 설립 3년 이내 → 창업지원 적합)
- 약점: 매칭에 불리한 조건 (예: 매출 1억 미만 → 일부 사업 제외)

## 2. 상담 이력 요약
- 기존 AI 상담에서 확인된 판정 결과 정리
- 상담이 없으면 "아직 개별 공고 상담 이력이 없습니다. 추천 공고별 상세 상담을 진행하시면 더 정확한 판단이 가능합니다." 로 작성

## 3. 맞춤 공고 분석 (추천 TOP 5)
- 각 공고에 대해:
  - 공고명 + 지원금액 + 마감일
  - **왜 이 기업에 적합한지** 2~3문장
  - 주의사항/준비 필요 사항

## 4. 신청 로드맵
- 마감일 순서로 타임라인 작성
- 이번 주 / 다음 주 / 이번 달 구분
- 우선순위 표시 (★★★ / ★★ / ★)

## 5. 필요 서류 체크리스트
- 공통 서류: 사업자등록증, 중소기업확인서, 재무제표 등
- 공고별 추가 서류 (알 수 있는 범위에서)

## 6. 경쟁력 분석
- 이 기업이 선정될 가능성을 높이는 방법
- 사업계획서 작성 팁
- 강조해야 할 포인트

## 7. 종합 의견
- 컨설턴트의 최종 판단
- 즉시 신청 권장 공고 (1~2개)
- 준비 후 신청 권장 공고
- 다음 분기 대비 사항

━━━━━━━━━━━━━━━━━━━━━━━━━━
[형식 규칙] — 매우 중요! 반드시 준수
━━━━━━━━━━━━━━━━━━━━━━━━━━
- **반드시 HTML 태그로 작성** (마크다운 아님)
- 문장 끝맺음은 명사형 (예: "지원 가능", "확인 필요", "신청 권장")
- 줄바꿈 없이 문장 나열하지 말 것. 각 항목은 분리
- **표(table)를 최대한 활용:**
  - 기업 현황 → 표
  - 추천 공고 TOP 5 → 표 (순위/공고명/금액/마감일/적합도/사유)
  - 필요 서류 → 체크리스트 표
- **로드맵은 시각적 타임라인:**
  - div 기반 가로 타임라인 또는 표 형태
  - 주간별 구분, 우선순위 색상 표시
- HTML 스타일:
  - 섹션 헤더: <h2 style="color:#5b21b6;border-bottom:2px solid #c4b5fd;padding-bottom:6px;margin-top:24px;">
  - 표: <table style="width:100%;border-collapse:collapse;margin:12px 0;font-size:13px;">
  - th: style="background:#f5f3ff;color:#5b21b6;padding:8px 12px;border:1px solid #e5e7eb;text-align:left;font-weight:bold;"
  - td: style="padding:8px 12px;border:1px solid #e5e7eb;"
  - 긴급 마감: <span style="color:#dc2626;font-weight:bold;">긴급</span>
  - 우선순위 높음: <span style="color:#7c3aed;">★★★</span>
  - 체크박스: ☐ (빈 체크박스 문자)
- 한국어, 전문 컨설턴트 톤
- 2000~3000자 내외
- <style> 태그 사용 금지 (인라인 스타일만)
- <script> 태그 사용 금지
━━━━━━━━━━━━━━━━━━━━━━━━━━"""

            response = model.generate_content(prompt)
            ai_summary = response.text.strip() if response and response.text else "AI 분석을 생성하지 못했습니다."
            print(f"[report] AI summary generated: {len(ai_summary)} chars")
    except Exception as e:
        ai_summary = f"AI 요약 생성 실패: {str(e)[:200]}"
        print(f"[report] AI summary error: {e}")

    import json as _json
    brief = f"{client['client_name']} 기업 분석 결과: 총 {len(results)}건 매칭, 지원가능 {eligible_count}건, 조건부 {conditional_count}건"
    # summary에 AI 분석 전문 포함 (brief + ai_summary)
    full_summary = f"{brief}\n\n{ai_summary}" if ai_summary else brief

    # 6. DB 저장
    cur.execute(
        """INSERT INTO client_reports
           (client_profile_id, owner_business_number, title, summary, matched_announcements,
            total_eligible, total_conditional, total_ineligible)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (req.client_profile_id, current_user["bn"],
         f"{client['client_name']} 종합 리포트",
         full_summary, _json.dumps(results, ensure_ascii=False),
         eligible_count, conditional_count, ineligible_count)
    )
    try:
        report_id = cur.fetchone()["id"]
        conn.commit()
    except Exception as db_err:
        conn.rollback()
        conn.close()
        print(f"[report] DB error: {db_err}")
        raise HTTPException(status_code=500, detail=f"리포트 저장 실패: {str(db_err)[:100]}")
    conn.close()

    return {
        "status": "SUCCESS",
        "report_id": report_id,
        "summary": brief,
        "ai_analysis": ai_summary,
        "consult_history": consult_summaries[:10],
        "total": len(results),
        "eligible": eligible_count,
        "conditional": conditional_count,
        "ineligible": ineligible_count,
        "announcements": results,
    }


@app.get("/api/pro/reports")
def api_pro_reports(
    client_id: Optional[int] = None,
    current_user: dict = Depends(_get_current_user),
):
    """PRO: 리포트 목록 조회"""
    _require_pro(current_user)
    conn = get_db_connection()
    cur = conn.cursor()

    if client_id:
        cur.execute(
            """SELECT r.id, r.client_profile_id, cp.client_name, r.title, r.summary,
                      r.total_eligible, r.total_conditional, r.total_ineligible, r.created_at
               FROM client_reports r
               JOIN client_profiles cp ON cp.id = r.client_profile_id
               WHERE r.owner_business_number=%s AND r.client_profile_id=%s
               ORDER BY r.created_at DESC""",
            (current_user["bn"], client_id)
        )
    else:
        cur.execute(
            """SELECT r.id, r.client_profile_id, cp.client_name, r.title, r.summary,
                      r.total_eligible, r.total_conditional, r.total_ineligible, r.created_at
               FROM client_reports r
               JOIN client_profiles cp ON cp.id = r.client_profile_id
               WHERE r.owner_business_number=%s
               ORDER BY r.created_at DESC
               LIMIT 50""",
            (current_user["bn"],)
        )

    rows = cur.fetchall()
    conn.close()
    reports = []
    for r in rows:
        d = dict(r)
        d["created_at"] = str(d["created_at"]) if d.get("created_at") else None
        reports.append(d)
    return {"status": "SUCCESS", "reports": reports}


@app.get("/api/pro/reports/{report_id}")
def api_pro_report_detail(report_id: int, current_user: dict = Depends(_get_current_user)):
    """PRO: 리포트 상세 조회"""
    _require_pro(current_user)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT r.*, cp.client_name, cp.address_city, cp.industry_code, cp.industry_name,
                  cp.revenue_bracket, cp.employee_count_bracket, cp.establishment_date
           FROM client_reports r
           JOIN client_profiles cp ON cp.id = r.client_profile_id
           WHERE r.id=%s AND r.owner_business_number=%s""",
        (report_id, current_user["bn"])
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
    d = dict(row)
    d["created_at"] = str(d["created_at"]) if d.get("created_at") else None
    if d.get("establishment_date"):
        d["establishment_date"] = str(d["establishment_date"])
    return {"status": "SUCCESS", "report": d}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API 제휴 관련
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PartnershipInquiry(BaseModel):
    company_name: str
    contact_name: str
    email: str
    phone: Optional[str] = ""
    purpose: str
    expected_volume: Optional[str] = ""
    message: Optional[str] = ""


@app.post("/api/partnership/inquiry")
def api_partnership_inquiry(req: PartnershipInquiry, request: Request):
    """API 제휴 문의 접수"""
    if not req.company_name or not req.email or not req.purpose:
        raise HTTPException(status_code=400, detail="필수 항목을 입력해주세요.")
    # Rate limit: IP당 시간당 3회
    ip = _get_client_ip(request)
    if not _rate_limit_check(f"partnership:ip:{ip}", 3, 3600):
        raise HTTPException(status_code=429, detail="잠시 후 다시 시도해주세요.")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS partnership_inquiries (
                id SERIAL PRIMARY KEY,
                company_name VARCHAR(200) NOT NULL,
                contact_name VARCHAR(100) NOT NULL,
                email VARCHAR(200) NOT NULL,
                phone VARCHAR(50) DEFAULT '',
                purpose TEXT NOT NULL,
                expected_volume VARCHAR(100) DEFAULT '',
                message TEXT DEFAULT '',
                status VARCHAR(20) DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute(
            """INSERT INTO partnership_inquiries (company_name, contact_name, email, phone, purpose, expected_volume, message)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (req.company_name, req.contact_name, req.email, req.phone or "", req.purpose, req.expected_volume or "", req.message or "")
        )
        conn.commit()
        _log_system("partnership_inquiry", "system", f"{req.company_name} ({req.email})", "success")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="문의 접수 중 오류가 발생했습니다.")
    finally:
        conn.close()

    return {"status": "SUCCESS", "message": "제휴 문의가 접수되었습니다. 담당자가 빠르게 연락드리겠습니다."}


@app.get("/api/admin/partnership-inquiries", dependencies=[Depends(_verify_admin)])
def api_get_partnership_inquiries():
    """관리자: 제휴 문의 목록 조회"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM partnership_inquiries ORDER BY created_at DESC LIMIT 50")
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = str(r["created_at"])
        conn.close()
        return {"status": "SUCCESS", "data": rows}
    except Exception:
        conn.close()
        return {"status": "SUCCESS", "data": []}


@app.post("/api/partnership/chat")
def api_partnership_chat(req: dict, request: Request):
    """API 제휴 상담 챗봇 (Gemini 기반)"""
    message = (req.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="메시지를 입력해주세요.")
    # Rate limit
    ip = _get_client_ip(request)
    if not _rate_limit_check(f"pchat:ip:{ip}", 10, 60):
        raise HTTPException(status_code=429, detail="잠시 후 다시 시도해주세요.")

    system_prompt = """당신은 "지원금AI" 서비스의 API 제휴 상담 전문가입니다.
비즈니스 파트너에게 전문적이고 친절하게 응대하세요.

[서비스 정보]
- 서비스명: 지원금AI (govmatch.kr)
- 제공: 17,000+ 정부 지원금 공고 데이터 + AI 매칭 엔진
- 운영: 밸류파인더 (대표 권오성)

[API 제공 데이터]
- 정부지원금/보조금/정책자금 공고 데이터 (기업+개인)
- AI 기반 자격요건 분석 및 매칭
- 공고 상세 정보 (자격요건, 제출서류, 신청방법 등)
- 실시간 새 공고 알림

[API 요금제]
- Free: 일 100건 조회, 기본 공고 데이터
- Basic (월 29만원): 일 1,000건, AI 매칭 포함, 이메일 지원
- Pro (월 99만원): 무제한, AI 매칭+분석, 전담 매니저, SLA 보장
- Enterprise: 맞춤 협의

[연동 방식]
- RESTful API (JSON)
- API Key 인증
- Swagger 문서 제공
- 연동 가이드 및 샘플 코드 제공

[자주 묻는 질문]
- 테스트 API Key는 무료로 발급 가능
- 데이터는 매일 자동 업데이트
- SLA: Basic 99%, Pro 99.9%
- 결제: 월 자동결제 (카드/계좌이체)

답변 규칙:
1. 비즈니스 톤으로 전문적이게 답변
2. 구체적 제휴 논의가 필요하면 문의 폼 작성을 안내
3. 기술적 질문에는 상세하게 답변
4. 모르는 것은 "담당자가 상세히 안내드리겠습니다"로 안내
5. 한국어로 답변"""

    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"status": "SUCCESS", "answer": "현재 상담 서비스 준비 중입니다. 하단 문의 폼을 이용해주세요."}

        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        history = req.get("history", [])
        chat_messages = [{"role": "user", "parts": [system_prompt + "\n\n사용자 질문: " + message]}]
        if history:
            # 이전 대화 컨텍스트 포함 (최근 5건)
            context = "\n".join([f"{'사용자' if h['role']=='user' else 'AI'}: {h['content']}" for h in history[-5:]])
            chat_messages = [{"role": "user", "parts": [system_prompt + f"\n\n[이전 대화]\n{context}\n\n사용자 질문: " + message]}]

        response = model.generate_content(chat_messages[0]["parts"][0])
        answer = response.text.strip()
        return {"status": "SUCCESS", "answer": answer}
    except Exception as e:
        return {"status": "SUCCESS", "answer": "현재 상담이 일시적으로 불가합니다. 하단 문의 폼을 이용해주세요."}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 고객 상담
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SupportInquiry(BaseModel):
    name: str
    email: str
    category: str
    message: str


@app.post("/api/support/inquiry")
def api_support_inquiry(req: SupportInquiry, request: Request):
    """고객 문의 접수"""
    if not req.name or not req.email or not req.message:
        raise HTTPException(status_code=400, detail="필수 항목을 입력해주세요.")
    ip = _get_client_ip(request)
    if not _rate_limit_check(f"support:ip:{ip}", 5, 3600):
        raise HTTPException(status_code=429, detail="잠시 후 다시 시도해주세요.")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS support_inquiries (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(200) NOT NULL,
                category VARCHAR(50) DEFAULT '',
                message TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute(
            "INSERT INTO support_inquiries (name, email, category, message) VALUES (%s, %s, %s, %s)",
            (req.name, req.email, req.category or "", req.message)
        )
        conn.commit()
        _log_system("support_inquiry", "system", f"{req.name} ({req.email}) - {req.category}", "success")
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="문의 접수 중 오류가 발생했습니다.")
    finally:
        conn.close()
    return {"status": "SUCCESS", "message": "문의가 접수되었습니다. 빠르게 답변드리겠습니다."}


@app.get("/api/admin/support-inquiries", dependencies=[Depends(_verify_admin)])
def api_get_support_inquiries():
    """관리자: 고객 문의 목록"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM support_inquiries ORDER BY created_at DESC LIMIT 50")
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = str(r["created_at"])
        conn.close()
        return {"status": "SUCCESS", "data": rows}
    except Exception:
        conn.close()
        return {"status": "SUCCESS", "data": []}


@app.post("/api/support/chat")
def api_support_chat(req: dict, request: Request):
    """고객 상담 AI 챗봇"""
    message = (req.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="메시지를 입력해주세요.")
    ip = _get_client_ip(request)
    if not _rate_limit_check(f"schat:ip:{ip}", 15, 60):
        raise HTTPException(status_code=429, detail="잠시 후 다시 시도해주세요.")

    system_prompt = """당신은 "지원금AI" 고객 상담 챗봇입니다.
친절하고 쉬운 말로 사용자를 도와주세요.

[서비스 안내]
- 지원금AI는 정부 지원금/보조금/정책자금을 AI가 자동 매칭해주는 무료 서비스입니다.
- 기업(사업자)과 개인 모두 이용 가능합니다.
- 17,000+ 공고를 실시간 분석합니다.

[주요 기능]
- 무료 회원가입 → 프로필 설정 → AI 자동 매칭
- 맞춤 공고 알림 (무료)
- AI 상담: 공고별 자격요건/신청방법 상세 안내
- 유료 플랜: LITE(월 2,900~4,900원), PRO(월 49,000원)

[자주 묻는 질문]
- 회원가입: 이메일 또는 소셜(카카오/네이버/구글) 로그인
- 매칭이 안 될 때: 프로필 설정(지역, 업종, 매출 등)을 정확히 입력해야 합니다
- 결제: 현재 오픈 기념 무료 이용 중, 유료 플랜은 곧 오픈 예정
- 알림: 새 공고 등록 시 자동 알림 (이메일/푸시)
- 환불: 결제 후 7일 이내 전액 환불 가능

[답변 규칙]
1. 친근하고 쉬운 말로 답변
2. 해결이 어려운 문제는 "문의 폼을 작성해주시면 담당자가 직접 도와드리겠습니다"로 안내
3. 한국어로 답변
4. 답변은 간결하게 (3~5문장)"""

    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"status": "SUCCESS", "answer": "현재 상담 서비스 준비 중입니다. 하단 문의 폼을 이용해주세요."}

        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        history = req.get("history", [])
        context = ""
        if history:
            context = "\n".join([f"{'사용자' if h['role']=='user' else 'AI'}: {h['content']}" for h in history[-5:]])
            context = f"\n\n[이전 대화]\n{context}"

        response = model.generate_content(f"{system_prompt}{context}\n\n사용자 질문: {message}")
        return {"status": "SUCCESS", "answer": response.text.strip()}
    except Exception:
        return {"status": "SUCCESS", "answer": "일시적으로 상담이 불가합니다. 하단 문의 폼을 이용해주세요."}


# ── SmartDoc 연동 API ──

@app.get("/api/announcements/search")
def api_announcements_search(keyword: str = "", limit: int = 20):
    """SmartDoc용 공고 검색 — title, department, deadline_date, support_amount 반환"""
    limit = min(limit, 100)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if keyword.strip():
            words = keyword.strip().split()
            where_parts = []
            params = []
            for w in words:
                where_parts.append("(title ILIKE %s OR department ILIKE %s OR summary_text ILIKE %s)")
                params.extend([f"%{w}%", f"%{w}%", f"%{w}%"])
            where_sql = " AND ".join(where_parts)
            cur.execute(
                f"""SELECT announcement_id, title, department, deadline_date, support_amount
                    FROM announcements
                    WHERE {where_sql}
                    ORDER BY
                        CASE WHEN deadline_date IS NOT NULL AND deadline_date >= CURRENT_DATE THEN 0 ELSE 1 END,
                        deadline_date ASC NULLS LAST,
                        created_at DESC
                    LIMIT %s""",
                params + [limit],
            )
        else:
            cur.execute(
                """SELECT announcement_id, title, department, deadline_date, support_amount
                   FROM announcements
                   ORDER BY
                       CASE WHEN deadline_date IS NOT NULL AND deadline_date >= CURRENT_DATE THEN 0 ELSE 1 END,
                       deadline_date ASC NULLS LAST,
                       created_at DESC
                   LIMIT %s""",
                [limit],
            )
        rows = cur.fetchall()
        return {"status": "SUCCESS", "data": [dict(r) for r in rows], "total": len(rows)}
    finally:
        conn.close()


@app.get("/api/announcements/{announcement_id}/for-smartdoc")
def api_announcement_for_smartdoc(announcement_id: int):
    """SmartDoc용 공고 상세 — 원문/분석 데이터 반환"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT announcement_id, title, department, deadline_date, support_amount,
                      summary_text, eligibility_logic, origin_url, category, region,
                      target_type, origin_source
               FROM announcements WHERE announcement_id = %s""",
            (announcement_id,),
        )
        ann = cur.fetchone()
        if not ann:
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")

        result = dict(ann)

        # deep_analysis 데이터가 있으면 full_text, evaluation_weights 등 포함
        try:
            from app.services.doc_analysis_service import get_deep_analysis
            analysis = get_deep_analysis(announcement_id, conn)
            if analysis:
                parsed = analysis.get("parsed_sections", {})
                deep = analysis.get("deep_analysis", {})
                result["full_text"] = analysis.get("full_text", "")
                result["evaluation_weights"] = deep.get("evaluation_weights") or parsed.get("evaluation_weights")
                result["form_templates"] = deep.get("form_templates") or parsed.get("form_templates")
                result["eligibility_detail"] = deep.get("eligibility") or parsed.get("eligibility")
                result["budget_info"] = deep.get("budget") or parsed.get("budget")
        except Exception:
            pass

        return {"status": "SUCCESS", "data": result}
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
