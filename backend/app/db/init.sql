-- PostgreSQL (Supabase) 스키마 정의
-- AUTOINCREMENT(SQLite) → SERIAL(PostgreSQL)
-- INTEGER DEFAULT 1 for boolean → BOOLEAN DEFAULT true

-- 1. 공고 정보 테이블 (지원사업 정보 저장)
CREATE TABLE IF NOT EXISTS announcements (
    announcement_id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    origin_url TEXT UNIQUE NOT NULL,
    region VARCHAR(50),
    target_industry_codes TEXT,
    established_years_limit INT,
    revenue_limit BIGINT,
    employee_limit INT,
    support_amount TEXT,
    deadline_date DATE,
    summary_text TEXT,
    eligibility_logic TEXT,
    department VARCHAR(255),
    category VARCHAR(100),
    origin_source VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 사용자(기업) 프로필 테이블
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    business_number VARCHAR(20) UNIQUE,
    company_name VARCHAR(255),
    address_city VARCHAR(50),
    establishment_date DATE,
    industry_code VARCHAR(10),
    revenue_bracket VARCHAR(50),
    employee_count_bracket VARCHAR(50),
    interests TEXT,
    email VARCHAR(100) UNIQUE,
    kakao_id VARCHAR(100),
    password_hash TEXT,
    plan VARCHAR(20) DEFAULT 'free',
    plan_started_at TIMESTAMP,
    plan_expires_at TIMESTAMP,
    ai_usage_month INT DEFAULT 0,
    ai_usage_reset_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    referral_code VARCHAR(20),
    referred_by VARCHAR(20),
    referral_rewarded BOOLEAN DEFAULT FALSE,
    merit_months INT DEFAULT 0
);

-- 3. 관리자 수동 수집 URL 테이블
CREATE TABLE IF NOT EXISTS admin_urls (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_scraped TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 웹 푸시 구독 테이블
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id SERIAL PRIMARY KEY,
    business_number VARCHAR(20),
    endpoint TEXT UNIQUE NOT NULL,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. 사용자 저장 공고 (일정 관리)
CREATE TABLE IF NOT EXISTS saved_announcements (
    id SERIAL PRIMARY KEY,
    business_number VARCHAR(20) NOT NULL,
    announcement_id INTEGER NOT NULL,
    memo TEXT DEFAULT '',
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(business_number, announcement_id)
);

-- 6. 알림 설정 테이블
CREATE TABLE IF NOT EXISTS notification_settings (
    id SERIAL PRIMARY KEY,
    business_number VARCHAR(20) UNIQUE NOT NULL,
    email VARCHAR(100),
    phone_number VARCHAR(20),
    channel VARCHAR(20) DEFAULT 'email',
    is_active BOOLEAN DEFAULT true,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. 알림 발송 이력 테이블
CREATE TABLE IF NOT EXISTS notification_logs (
    id SERIAL PRIMARY KEY,
    recipient TEXT,
    company_name TEXT,
    channel TEXT,
    status TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
