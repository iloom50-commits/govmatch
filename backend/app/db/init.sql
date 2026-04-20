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
    target_type VARCHAR(20) DEFAULT 'business',   -- 'business' | 'individual' | 'both'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 사용자 프로필 테이블 (기업 + 개인 통합)
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
    merit_months INT DEFAULT 0,
    -- 개인/기업 구분
    user_type VARCHAR(20) DEFAULT 'business',   -- 'individual' | 'business' | 'both'
    -- 개인 프로필 필드
    age_range VARCHAR(20),                       -- '20대', '30대', '40대', '50대', '60대 이상'
    income_level VARCHAR(30),                    -- '기초생활', '차상위', '중위50%이하', '중위75%이하', '중위100%이하', '해당없음'
    family_type VARCHAR(30),                     -- '1인가구', '다자녀', '한부모', '신혼부부', '다문화', '일반', '해당없음'
    employment_status VARCHAR(30)                -- '재직자', '구직자', '자영업', '프리랜서', '학생', '해당없음'
);

-- 3. 관리자 수동 수집 URL 테이블
CREATE TABLE IF NOT EXISTS admin_urls (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_scraped TIMESTAMP,
    last_success TIMESTAMP,
    fail_count INT DEFAULT 0,
    last_fail_reason TEXT,
    recovered_url TEXT,
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

-- 8. 공고 원문 + 정밀 분석 (AI 학습 데이터)
CREATE TABLE IF NOT EXISTS announcement_analysis (
    id SERIAL PRIMARY KEY,
    announcement_id INTEGER REFERENCES announcements(announcement_id) ON DELETE CASCADE,
    full_text TEXT,                    -- PDF/HTML에서 추출한 원문 전체
    parsed_sections JSONB,            -- 섹션별 분류 결과
    -- parsed_sections 구조:
    -- {
    --   "eligibility": "신청자격 원문",
    --   "exclusions": "제외대상 원문",
    --   "exceptions": "예외조항 원문",
    --   "bonus_points": "가점항목 원문",
    --   "required_docs": "제출서류 원문",
    --   "evaluation_criteria": "심사기준 원문",
    --   "support_details": "지원내용 원문",
    --   "timeline": "일정 원문",
    --   "application_method": "신청방법 원문"
    -- }
    deep_analysis JSONB,              -- Gemini 정밀 분석 결과
    -- deep_analysis 구조:
    -- {
    --   "eligibility_detail": { 조건별 상세 },
    --   "exclusion_rules": [ 제외 사유 리스트 ],
    --   "exception_rules": [ 예외 조항 리스트 ],
    --   "bonus_items": [ 가점 항목 ],
    --   "required_documents": [ 제출 서류 ],
    --   "evaluation_weights": { 심사 배점 },
    --   "gray_zones": [ 판단 불확실 영역 ],
    --   "key_warnings": [ 주의사항 ]
    -- }
    form_templates JSONB DEFAULT '[]'::jsonb,  -- 신청서 양식 구조 (목차/작성항목)
    -- form_templates 구조:
    -- [
    --   {
    --     "form_name": "사업신청서",
    --     "sections": [
    --       {"title": "기업현황", "fields": ["회사명", "대표자", "설립일"]},
    --       {"title": "사업계획", "fields": ["사업목표", "추진일정"]}
    --     ]
    --   }
    -- ]
    analysis_version INT DEFAULT 1,   -- 분석 버전 (재분석 시 증가)
    source_type VARCHAR(20) DEFAULT 'html',  -- 'pdf' | 'html' | 'hwp'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(announcement_id)
);

-- 9. 검색 동의어 풀 (키워드 확장)
CREATE TABLE IF NOT EXISTS keyword_synonyms (
    id SERIAL PRIMARY KEY,
    group_name TEXT NOT NULL,          -- 대표 키워드 ('수출', '다자녀')
    keyword TEXT NOT NULL,             -- 동의어/유사어 ('해외진출', '다둥이')
    target_type VARCHAR(20) DEFAULT 'both',  -- 'business' | 'individual' | 'both'
    UNIQUE(group_name, keyword)
);

-- 10. AI 상담 로그 (학습 데이터 축적 + 피드백)
CREATE TABLE IF NOT EXISTS ai_consult_logs (
    id SERIAL PRIMARY KEY,
    announcement_id INTEGER REFERENCES announcements(announcement_id),
    business_number VARCHAR(20),
    messages JSONB,                    -- 전체 대화 이력
    conclusion VARCHAR(20),            -- 'eligible' | 'conditional' | 'ineligible' | null
    feedback VARCHAR(20),              -- 'helpful' | 'inaccurate' | null
    feedback_detail TEXT,              -- 부정확 시 사유
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 11. AI 공유 지식 저장소 (수집AI ↔ 공고AI ↔ 공통AI 순환 학습)
CREATE TABLE IF NOT EXISTS knowledge_base (
    id SERIAL PRIMARY KEY,
    source VARCHAR(20) NOT NULL,       -- 'crawler' | 'consult' | 'free_chat'
    knowledge_type VARCHAR(30) NOT NULL,
    -- knowledge_type 값:
    --   'faq'          : 자주 묻는 질문/답변 패턴
    --   'pattern'      : 카테고리별 핵심 질문 패턴 (예: "기술개발 공고는 업력을 가장 많이 물어봄")
    --   'error'        : 오답/부정확 피드백 패턴 (예: "금액 정보 불일치 빈번")
    --   'insight'      : 공고 간 관계/조합 발견 (예: "A공고 신청자는 B공고도 해당 가능")
    --   'trend'        : 사용자 관심 트렌드 (예: "이번 달 '디지털전환' 검색 급증")
    category VARCHAR(100),             -- 공고 카테고리 (기술개발, 수출, 창업 등)
    announcement_id INTEGER REFERENCES announcements(announcement_id) ON DELETE SET NULL,
    content JSONB NOT NULL,            -- 학습된 내용 (구조는 type별로 다름)
    -- content 구조 예시:
    -- faq:     {"question": "...", "answer": "...", "context": "..."}
    -- pattern: {"top_questions": [...], "key_fields": [...], "tips": "..."}
    -- error:   {"wrong_info": "...", "correct_info": "...", "cause": "..."}
    -- insight: {"related_ids": [1,2,3], "relationship": "..."}
    -- trend:   {"keyword": "...", "count": 50, "period": "2026-03"}
    confidence FLOAT DEFAULT 0.5,      -- 신뢰도 (0.0~1.0, 피드백으로 조정)
    use_count INT DEFAULT 0,           -- 활용 횟수 (참조될 때마다 증가)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kb_source ON knowledge_base(source);
CREATE INDEX IF NOT EXISTS idx_kb_type ON knowledge_base(knowledge_type);
CREATE INDEX IF NOT EXISTS idx_kb_category ON knowledge_base(category);
CREATE INDEX IF NOT EXISTS idx_kb_confidence ON knowledge_base(confidence DESC);

-- 12. 골든 답변 (사용자 검증된 고품질 Q&A — Gemini 호출 없이 재활용)
CREATE TABLE IF NOT EXISTS golden_answers (
    id SERIAL PRIMARY KEY,
    announcement_id INTEGER REFERENCES announcements(announcement_id) ON DELETE CASCADE,
    category VARCHAR(100),             -- 공고 카테고리
    question_pattern TEXT NOT NULL,    -- 정규화된 질문 패턴
    question_hash VARCHAR(64) NOT NULL, -- 빠른 매칭용 해시
    answer_text TEXT NOT NULL,         -- 검증된 답변
    choices JSONB DEFAULT '[]'::jsonb, -- 후속 선택지
    conclusion VARCHAR(20),            -- 결론 (eligible/conditional/ineligible/null)
    source_consult_id INTEGER REFERENCES ai_consult_logs(id) ON DELETE SET NULL,
    helpful_count INT DEFAULT 1,       -- "도움됐어요" 횟수
    inaccurate_count INT DEFAULT 0,    -- "부정확해요" 횟수
    quality_score FLOAT GENERATED ALWAYS AS (
        CASE WHEN (helpful_count + inaccurate_count) > 0
             THEN helpful_count::FLOAT / (helpful_count + inaccurate_count)
             ELSE 0.5 END
    ) STORED,                          -- 자동 계산 품질 점수
    is_active BOOLEAN DEFAULT TRUE,    -- 품질 낮으면 비활성화
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_golden_hash ON golden_answers(question_hash);
CREATE INDEX IF NOT EXISTS idx_golden_category ON golden_answers(category);
CREATE INDEX IF NOT EXISTS idx_golden_quality ON golden_answers(quality_score DESC) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_golden_announcement ON golden_answers(announcement_id) WHERE is_active = TRUE;

-- 13. 고객사 프로필 (PRO 전용 — 컨설턴트가 고객사 다건 관리)
CREATE TABLE IF NOT EXISTS client_profiles (
    id SERIAL PRIMARY KEY,
    owner_business_number VARCHAR(20) NOT NULL,  -- PRO 사용자(컨설턴트)의 사업자번호
    client_name VARCHAR(255) NOT NULL,           -- 고객사명
    business_number VARCHAR(20),                 -- 고객사 사업자번호 (선택)
    establishment_date DATE,
    address_city VARCHAR(50),
    industry_code VARCHAR(10),
    industry_name VARCHAR(100),
    revenue_bracket VARCHAR(50),
    employee_count_bracket VARCHAR(50),
    interests TEXT,
    memo TEXT DEFAULT '',                        -- 컨설턴트 메모
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_client_owner ON client_profiles(owner_business_number) WHERE is_active = TRUE;

-- 14. 종합 리포트 (PRO 전용 — 고객별 지원 가능 공고 분석)
CREATE TABLE IF NOT EXISTS client_reports (
    id SERIAL PRIMARY KEY,
    client_profile_id INTEGER REFERENCES client_profiles(id) ON DELETE CASCADE,
    owner_business_number VARCHAR(20) NOT NULL,
    title VARCHAR(255) NOT NULL,                 -- 리포트 제목
    summary TEXT,                                -- 종합 요약
    matched_announcements JSONB DEFAULT '[]'::jsonb,
    -- matched_announcements 구조:
    -- [
    --   {
    --     "announcement_id": 123,
    --     "title": "공고명",
    --     "conclusion": "eligible|conditional|ineligible",
    --     "reason": "판정 근거 요약",
    --     "support_amount": "최대 3억",
    --     "deadline_date": "2026-04-30"
    --   }
    -- ]
    total_eligible INT DEFAULT 0,
    total_conditional INT DEFAULT 0,
    total_ineligible INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_report_client ON client_reports(client_profile_id);
CREATE INDEX IF NOT EXISTS idx_report_owner ON client_reports(owner_business_number);

-- 15. 오케스트레이터 품질 리뷰 (COO가 에이전트별 상담 샘플 Gemini 평가 결과)
CREATE TABLE IF NOT EXISTS orchestrator_reviews (
    id SERIAL PRIMARY KEY,
    review_date DATE NOT NULL DEFAULT CURRENT_DATE,
    agent VARCHAR(40) NOT NULL,                -- lite_business_fund | lite_individual_fund | announce_consult | pro_biz | pro_indiv
    consult_log_id INTEGER,                    -- ai_consult_logs.id (FK 없음 — 샘플링용)
    accuracy FLOAT,                            -- 0~10
    completeness FLOAT,                        -- 0~10
    usefulness FLOAT,                          -- 0~10
    avg_score FLOAT,                           -- 0~10
    issue TEXT,                                -- Gemini가 지적한 문제점 한줄
    needs_review BOOLEAN DEFAULT FALSE,        -- 평균 5점 미만 플래그
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orch_review_date ON orchestrator_reviews(review_date DESC);
CREATE INDEX IF NOT EXISTS idx_orch_review_agent ON orchestrator_reviews(agent);
CREATE INDEX IF NOT EXISTS idx_orch_review_needs ON orchestrator_reviews(needs_review) WHERE needs_review = TRUE;
