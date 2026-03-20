-- 요금제 v2 마이그레이션: trial/premium → free, FREE 영구무료
-- 실행 전 반드시 백업 권장: pg_dump -t users > users_backup.sql

-- 1. trial/premium 사용자를 free로 변환
UPDATE users SET plan = 'free', plan_expires_at = NULL
WHERE plan IN ('trial', 'premium');

-- 2. 기존 free 사용자의 만료일 제거 (영구 무료)
UPDATE users SET plan_expires_at = NULL
WHERE plan = 'free' AND plan_expires_at IS NOT NULL;

-- 3. 만료된 유료 플랜 사용자를 free로 다운그레이드
UPDATE users SET plan = 'free', plan_expires_at = NULL
WHERE plan IN ('basic', 'biz')
  AND plan_expires_at IS NOT NULL
  AND plan_expires_at < CURRENT_TIMESTAMP;
