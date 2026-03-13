-- 1. 공고 정보 테이블 (지원사업 정보 저장)
CREATE TABLE IF NOT EXISTS announcements (
    announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(255) NOT NULL,            -- 공고 제목
    origin_url TEXT UNIQUE NOT NULL,         -- 원본 URL (중복 체크 키)
    region VARCHAR(50),                     -- 지역 (부산, 서울 등)
    target_industry_codes TEXT,              -- 대상 업종 코드 (KSIC)
    established_years_limit INT,             -- 설립 연차 제한 (예: 7년)
    revenue_limit BIGINT,                   -- 매출액 상한선
    employee_limit INT,                     -- 근로자 수 조건
    support_amount TEXT,                    -- 지원 금액 및 내용 요약
    deadline_date DATE,                     -- 마감일
    summary_text TEXT,                      -- AI가 요약한 핵심 내용
    eligibility_logic TEXT,                 -- AI 추출 자격요건 JSON
    department VARCHAR(255),                -- 소관 부처/기관
    category VARCHAR(100),                  -- 분류 (Tech, Loan 등)
    origin_source VARCHAR(100),             -- 데이터 출처 (kstartup, bizinfo 등)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 사용자(기업) 프로필 테이블
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_number VARCHAR(10) UNIQUE,      -- 사업자번호
    company_name VARCHAR(255),               -- 기업명
    address_city VARCHAR(50),               -- 소재지(시/도)
    establishment_date DATE,                -- 설립일
    industry_code VARCHAR(10),               -- 주업종 코드
    revenue_bracket VARCHAR(50),            -- 매출액 구간
    employee_count_bracket VARCHAR(50),     -- 근로자 수 구간
    interests TEXT,                         -- 관심 키워드 (R&D, 마케팅 등)
    email VARCHAR(100) UNIQUE,
    kakao_id VARCHAR(100),
    password_hash TEXT,                     -- bcrypt 해시
    plan VARCHAR(20) DEFAULT 'trial',       -- trial / basic / expired
    trial_ends_at TIMESTAMP,                -- 무료체험 종료일
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. 관리자 수동 수집 URL 테이블
CREATE TABLE IF NOT EXISTS admin_urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,                -- 수집 대상 URL
    source_name VARCHAR(255) NOT NULL,       -- 출처 명칭 (예: '부산시 일자리 정보망')
    is_active INTEGER DEFAULT 1,             -- 활성화 여부 (1=활성, 0=비활성)
    last_scraped TIMESTAMP,                  -- 마지막 수집 시간
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 웹 푸시 구독 테이블
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_number VARCHAR(10),
    endpoint TEXT UNIQUE NOT NULL,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. 사용자 저장 공고 (일정 관리)
CREATE TABLE IF NOT EXISTS saved_announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_number VARCHAR(10) NOT NULL,
    announcement_id INTEGER NOT NULL,
    memo TEXT DEFAULT '',
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(business_number, announcement_id)
);

-- 6. 알림 설정 테이블
CREATE TABLE IF NOT EXISTS notification_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_number VARCHAR(10) UNIQUE NOT NULL,  -- 사업자번호 (FK)
    email VARCHAR(100),                           -- 이메일 주소
    phone_number VARCHAR(20),                     -- 전화번호
    channel VARCHAR(20) DEFAULT 'email',          -- 알림 채널 (email, kakao, BOTH)
    is_active INTEGER DEFAULT 1,                  -- 알림 활성화 여부
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
