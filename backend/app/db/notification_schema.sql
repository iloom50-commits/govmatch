-- User Profile Table: Stores company info and notification preferences
CREATE TABLE IF NOT EXISTS user_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    biz_no TEXT,                    -- Business Registration Number
    location TEXT,                  -- e.g., "Seoul", "Gyeonggi"
    industry TEXT,                  -- Category or Keywords
    established_date TEXT,          -- "YYYY-MM-DD" to calculate company age
    revenue_range TEXT,             -- e.g., "Below 1B", "1B-5B"
    interests TEXT,                 -- JSON list of keywords
    matching_threshold INTEGER DEFAULT 80, -- Minimum AI score to notify
    notification_time TEXT DEFAULT '10:00',
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Notification Log: Tracks what has been sent to whom to prevent duplicates
CREATE TABLE IF NOT EXISTS notification_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    program_id TEXT,                -- Supports both API IDs and Scraper IDs
    program_title TEXT,
    match_score INTEGER,
    ai_reasoning TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES user_profiles(id)
);

-- Seed an example profile for testing
INSERT INTO user_profiles (company_name, location, industry, email) 
VALUES ('밸류파인더(Test)', '서울', '소프트웨어, AI, 자동화', 'osung94@naver.com');
