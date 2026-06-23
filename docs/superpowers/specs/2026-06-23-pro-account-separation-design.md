# PRO 계정 완전 분리 설계 (별도 계정 풀)

> 상태: 설계(검토 대기) · 작성일 2026-06-23

## 1. 목표 (Goal)

지원금AI(일반 소비자 서비스)와 PRO(전문가 상담 도구, `/pro`)를 **완전히 별개의 사용자 풀**로 분리한다. PRO는 자체 가입·로그인·결제로 **독립적으로 사용자를 모집**하며, 소비자 계정과는 신원이 분리된다(같은 이메일이 양쪽 풀에 공존 가능).

## 2. 배경 / 현재 상태

- 단일 `users` 테이블(`business_number` UNIQUE, `email` UNIQUE). PRO 여부는 `plan` 값(pro/biz)으로만 구분.
- 단일 인증: `/api/auth/register` · `/login` · `/social/*`, JWT는 `bn` 기반.
- `/api/pro/*` 엔드포인트(상담 채팅·고객사 CRUD·공고 분석 등)는 `_get_current_user`(bn) + `_require_pro`(users.plan) 사용.
- PRO 도구 데이터(`client_profiles`, `client_reports`, `pro_consult_sessions`)는 `business_number` 키.
- **현재 PRO(plan=pro/biz) 계정은 전부 테스트 ID** → 보존/마이그레이션 불필요.

## 3. 제약 (Constraints)

- **DB 정책: 기존 컬럼·제약 삭제/변경 금지, 추가만 허용** → 새 테이블 + 기존 테이블에 nullable 컬럼 추가만.
- **소비자 인증(`/api/auth/*`)과 `users` 테이블은 일절 수정하지 않는다.**
- 보안 민감(신규 인증 신설) → 단계별 + 테스트 우선.

## 4. 결정 사항 (확정)

| 항목 | 결정 |
|------|------|
| 계정 관계 | 완전 별개 신원 — 별도 `pro_users` 풀, 같은 이메일 양쪽 공존 |
| 기존 PRO | 테스트 ID뿐 → 유예/마이그레이션 없음, 새 풀로 일괄 전환 |
| PRO 인증 | 이메일/비밀번호 + 소셜로그인(카카오·네이버·구글) |
| PRO 도구 데이터 키 | `pro_user_id` |
| 결제 | `/api/pro/subscribe` 신설 |

## 5. 아키텍처

```
[소비자] /  → /api/auth/*        → users (무변경)
[PRO]   /pro → /api/auth/pro/*   → pro_users (신규)
              /api/pro/subscribe → pro_users.plan
              /api/pro/*         → pro 인증 + pro_user_id 키
```

JWT 분리: PRO 토큰은 `account_type:"pro"` + `pro_user_id` 클레임. 가드가 풀을 구분.

## 6. DB 스키마 (추가만)

### 6.1 신규 테이블 `pro_users`
```sql
CREATE TABLE IF NOT EXISTS pro_users (
    pro_user_id      SERIAL PRIMARY KEY,
    email            VARCHAR(100) UNIQUE,        -- 풀 내 UNIQUE (users.email과 무관)
    password_hash    VARCHAR(255),               -- 소셜 전용 계정은 NULL 가능
    business_number  VARCHAR(20),                -- 전문가 사업자번호(선택, 풀 내 비고유 허용)
    company_name     VARCHAR(100),
    kakao_id         VARCHAR(100),
    naver_id         VARCHAR(100),
    google_id        VARCHAR(100),
    plan             VARCHAR(20) DEFAULT 'free', -- free | pro | biz
    plan_started_at  TIMESTAMP,
    plan_expires_at  TIMESTAMP,
    billing_key      VARCHAR(255),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sign_in_at  TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pro_users_email ON pro_users(email);
CREATE INDEX IF NOT EXISTS idx_pro_users_kakao ON pro_users(kakao_id);
```

### 6.2 PRO 도구 데이터 테이블에 `pro_user_id` 추가 (nullable, 추가만)
```sql
ALTER TABLE client_profiles       ADD COLUMN IF NOT EXISTS pro_user_id INTEGER;
ALTER TABLE client_reports        ADD COLUMN IF NOT EXISTS pro_user_id INTEGER;
ALTER TABLE pro_consult_sessions  ADD COLUMN IF NOT EXISTS pro_user_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_client_profiles_prouser ON client_profiles(pro_user_id);
CREATE INDEX IF NOT EXISTS idx_pro_sessions_prouser ON pro_consult_sessions(pro_user_id);
```
- 신규 PRO 데이터는 `pro_user_id`로 저장·조회. 기존 `business_number` 컬럼은 그대로 둠(테스트 잔재).

## 7. 인증 (신규 엔드포인트)

`users`용 헬퍼를 복제·격리한 PRO 전용 헬퍼/엔드포인트:

- `_create_pro_jwt(pro_user_id, email, plan)` → payload `{account_type:"pro", pro_user_id, email, plan, exp}`
- `_get_current_pro_user(authorization)` → 토큰 디코드 후 `account_type=="pro"` 검증, `{pro_user_id, email, plan}` 반환. 아니면 401.
- `_require_pro_plan(current_pro)` → `pro_users`에서 plan∈(pro,biz) + 만료 검사. 아니면 403.

엔드포인트:
| 엔드포인트 | 동작 |
|-----------|------|
| `POST /api/auth/pro/register` | email/pw/(사업자번호·회사명) → pro_users insert + JWT |
| `POST /api/auth/pro/login` | email/pw 검증 → JWT |
| `GET  /api/auth/pro/social/{provider}` | 소셜 인증 리다이렉트(state로 pro 풀 표시) |
| `POST /api/auth/pro/social/callback` | 소셜 콜백 → `_pro_social_login_or_register()` → JWT |
| `GET  /api/auth/pro/me` | 토큰 → pro_users 조회 |

소셜: 기존 `_social_login_or_register`를 본떠 `_pro_social_login_or_register(provider, social_id, email, name)` 신설 — `pro_users`에서 kakao_id/naver_id/google_id로 조회·생성.

## 8. 결제 — `/api/pro/subscribe`

기존 `/api/plan/subscribe`(users.plan 갱신)를 본떠 신설:
- 입력: `billing_key`, `target_plan`("pro"), `key_type`
- 동작: 빌링키 검증(기존 로직 재사용) → **`pro_users`** SET plan='pro', plan_started_at, plan_expires_at(+30d), billing_key
- 응답: `{status, token(새 pro JWT), plan}`

프론트 PaymentModal(`mode="pro"`)는 `/api/pro/subscribe` 호출로 변경.

## 9. `/api/pro/*` 엔드포인트 전환 (작업의 핵심 부피)

현재 `_get_current_user`(bn)+`_require_pro`(users.plan) 사용 중인 PRO 엔드포인트들을
`_get_current_pro_user`+`_require_pro_plan`으로 전환하고, 데이터 키를 `current_pro["pro_user_id"]`로 변경.

대상(확인된 것): `/api/pro/consultant/chat`, `/api/pro/announcements/{id}/analyze`,
고객사 CRUD(`client_profiles`), 세션(`pro_consult_sessions`) 등.
→ 구현 플랜에서 전체 목록을 grep으로 확정해 1:1 전환.

내부 헬퍼 `_load_client`, `_load_or_create_session` 등도 키 인자를 `bn` → `pro_user_id`로 교체.

## 10. 프론트엔드

- `ProPageClient.tsx`: 로그인/회원가입/소셜 호출을 `/api/auth/pro/*`로 변경. `/api/auth/me` → `/api/auth/pro/me`.
- 소셜 redirect의 `social_redirect`/state를 pro 전용으로.
- 소비자앱(HomeClient/Dashboard 등)은 **무변경**.
- (선택, 별도 논의) PRO 전용 랜딩/가치소개 — 본 스펙 범위 밖.

## 11. 테스트 계정

`pro_users`에 테스트 계정 생성(시드 스크립트 또는 register 호출):
- `test-pro@govmatch.kr` / plan=pro
- 무료 PRO(plan=free)도 1개 — 결제 유도 화면 검증용.

## 12. 범위 밖 (Non-goals)

- 기존 `users`의 PRO 흔적 정리(라벨·plan 값) — 테스트뿐이라 후순위.
- PRO 전용 마케팅 랜딩 페이지 — 별도 작업.
- 소비자↔PRO 계정 연동(SSO/링크) — 요구사항은 "완전 별개"이므로 안 함.

## 13. 리스크 / 주의

- **인증 신설 = 보안 민감**: 비밀번호 해싱은 기존 `users`와 동일 방식 재사용, JWT 시크릿 공유하되 `account_type`으로 풀 격리. 토큰 혼용(소비자 토큰으로 /api/pro 접근) 차단 필수 → `_get_current_pro_user`가 `account_type!="pro"`면 거부.
- **데이터 키 전환 누락 시** 고객사/세션이 안 보이거나 섞일 수 있음 → 전환 대상 엔드포인트를 grep으로 전수 확보.
- 기존 `users` 기반 `/api/pro/*`를 쓰던 테스트 토큰은 전환 후 동작 안 함(의도된 cutover).

## 14. 테스트 전략 (TDD)

- pro 인증: register→login→me 왕복, account_type 격리(소비자 토큰으로 /api/pro 403).
- 결제: `/api/pro/subscribe`로 plan 갱신 → `/api/auth/pro/me`가 pro 반영.
- 도구 데이터: pro_user_id로 고객사 생성→조회, 다른 pro 계정 간 격리.
- 실제 AI 상담(2차 expert_insights 포함)이 pro_user_id 기준으로 정상 동작.

## 15. 구현 단계(개요 — 상세는 플랜에서)

1. DB: `pro_users` + 컬럼 추가 (init.sql + 마이그레이션)
2. 백엔드 인증: pro JWT/가드/엔드포인트(register·login·social·me)
3. 결제: `/api/pro/subscribe`
4. `/api/pro/*` 전환 + 내부 헬퍼 키 교체
5. 프론트 `/pro` 인증 연결 + 결제 호출 변경
6. 테스트 계정 시드 + E2E/통합 검증
