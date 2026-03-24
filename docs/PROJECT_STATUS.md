# AI 맞춤 정부지원금 매칭 — 목적·개발현황·남은 작업

## 1. 프로그램 목적

**중소기업·소상공인**이 자신의 기업 정보만 입력하면, **5,000개 이상의 정부 지원사업 공고** 중에서 **AI가 맞춤 매칭**하여 추천하고, **알림·일정 관리**까지 제공하는 **유료 SaaS** 서비스입니다.

### 핵심 가치
- **진입 장벽 낮음**: 사업자번호 없이도 개인/법인 선택 + 설립일 + 소재지 등만으로 시작 가능
- **정밀 매칭**: KSIC 업종, 매출·직원 규모, 관심 분야, 설립 연차를 반영한 하이브리드 매칭
- **수익화**: 30일 무료 체험 후 **월 2,900원** 베이직 플랜 정기결제

### 타깃 사용자
- 중소기업 대표·담당자
- 소상공인(음식점, 미용실 등) 사장님
- 정부지원금·정책자금·R&D 공고를 놓치고 싶지 않은 사업자

---

## 2. 개발 현황 (상세)

### 2.1 사용자 플로우

| 단계 | 구현 여부 | 설명 |
|------|-----------|------|
| 첫 방문 | ✅ | 온보딩(기업 정보 입력) → 로그인 없이 진행 |
| Step 1 | ✅ | 개인/법인 선택, 설립일(날짜 선택+직접입력), 소재지(시/도) |
| Step 2 | ✅ | 관심 분야 선택 (업종별 하드코딩 매핑 + 직접입력) |
| Step 3 | ✅ | 매출 구간, 직원 수 구간 |
| Step 4 | ✅ | 업종(KSIC) 검색/추천, 코드 직접 입력 |
| Step 5 | ✅ | 이메일(아이디+@+도메인 선택), 비밀번호, 푸시 알림 토글 → "30일 무료 매칭 시작" |
| 회원가입 | ✅ | Step 5 완료 시 이메일+비밀번호로 가입, 30일 trial 부여 |
| 기존 사용자 | ✅ | 동일 이메일 재가입 시 409 → 자동 로그인 또는 로그인 화면 유도 |
| 로그인 | ✅ | 이메일(아이디+도메인 UI)+비밀번호, JWT 발급 |
| 매칭 결과 | ✅ | 대시보드(전체/소상공인 탭), 정렬(최신등록/마감임박), 카드별 상세·저장 |
| 정보 관리 | ✅ | 프로필 수정(소재지, 매출/직원, 업종, 관심분야), 기존값 프리필 |
| 로그아웃 | ✅ | 토큰 삭제 후 로그인 화면 |

### 2.2 백엔드 API

| 구분 | 엔드포인트 | 상태 |
|------|------------|------|
| **인증** | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` | ✅ |
| **플랜** | `POST /api/plan/upgrade`, `GET /api/plan/status` | ✅ |
| **기업/프로필** | `POST /api/industry-recommend`, `POST /api/fetch-company`, `POST /api/save-profile` | ✅ |
| **매칭** | `POST /api/match` | ✅ |
| **저장 공고** | `POST /api/saved/bulk`, `GET /api/saved/{bn}`, `DELETE /api/saved/{saved_id}` | ✅ |
| **알림** | `GET /api/notification-settings/{bn}`, `POST /api/notification-settings` | ✅ |
| **푸시** | `GET /api/push/vapid-key`, `POST /api/push/subscribe`, `POST /api/push/unsubscribe` | ✅ |
| **관리자** | `/api/admin/*` (auth, users, stats, urls, sync-manual, send-digest, push-test 등) | ✅ |

### 2.3 데이터·AI

| 항목 | 상태 |
|------|------|
| DB | SQLite (`gov_matching.db`), init.sql + ksic_metadata.sql, 마이그레이션(컬럼 추가, announcement_id 보정) | ✅ |
| 공공 API | 공공데이터포털·기업마당 등 연동, public_api_service.py | ✅ |
| 스크래핑 | SBC(중진공), 관리자 수동 URL(admin_urls) | ✅ |
| 동기화 | sync_service, 관리자 수동 sync | ✅ |
| 매칭 엔진 | matcher.py (규칙+KSIC+설립연차 등), 소상공인 확장 키워드 | ✅ |
| AI | Gemini 2.0 Flash (자격요건 추출, 업종 추천, 매칭 설명), ai_service.py | ✅ |

### 2.4 프론트엔드

| 화면/기능 | 상태 |
|-----------|------|
| 메인 플로우 | page.tsx (IDLE/LOGIN/LOADING/PROFILE/RESULTS/ONBOARDING) | ✅ |
| OnboardingWizard | 5단계, EmailInput(아이디+도메인), 날짜 입력 | ✅ |
| AuthPage | 로그인 전용, 무료체험 유도 링크 | ✅ |
| Dashboard | 탭(전체/소상공인), 정렬, 사이드바(프로필·플랜·알림·로그아웃·업그레이드) | ✅ |
| ResultCard | 상세, 저장/해제, 캘린더 연동 | ✅ |
| ProfileSettings | 모달, 기존값 프리필 | ✅ |
| PaymentModal | 베이직 2,900원 안내, 이용약관 동의, 결제 요청(현재 데모) | ✅ |
| Calendar | /calendar, 월별·일별 저장 공고 | ✅ |
| Admin | /admin, 로그인, 사용자 목록, URL 관리, 수동 동기화, 다이제스트 발송 등 | ✅ |
| 푸시 | sw.js, VAPID 구독 | ✅ |

### 2.5 수익화·결제

| 항목 | 상태 |
|------|------|
| 플랜 구조 | 비회원 → FREE → LITE(₩2,900) → PRO(₩19,900) | 설계 확정 (코드 반영 예정) |
| FREE | 맞춤 알림 + 공고AI 상담 1회 | 코드 반영 예정 |
| LITE | 공고AI 상담 무제한 | 코드 반영 예정 |
| PRO | 자유AI + 컨설턴트 무제한 + 전문가 도구(Coming Soon) | 코드 반영 예정 |
| 추천 보상 | 양쪽 LITE 1개월 무료 (최대 5회) | 코드 반영 예정 |
| AI 신청서 작성 | Coming Soon (가격 미정) | 미구현 |
| 토스페이먼츠 SDK | 카드 1회 결제 연동 완료 | ✅ |
| 백엔드 결제 검증 | Toss API confirm + DB 업데이트 | ✅ |
| 자동 갱신 (빌링키) | 미구현 | ❌ |
| 환불/해지 API | 미구현 | ❌ |
| 결제 이력 테이블 | 미구현 | ❌ |

### 2.6 알림

| 항목 | 상태 |
|------|------|
| 이메일 다이제스트 | DIGEST_HOUR(기본 9시) 스케줄, notification_service | ✅ |
| 웹 푸시 | VAPID, subscribe/unsubscribe, push_test (관리자) | ✅ |
| 알림 설정 | 이메일/채널, NotificationModal | ✅ |

### 2.7 테스트·운영

| 항목 | 상태 |
|------|------|
| Selenium E2E | test_selenium.py (온보딩→대시보드→로그아웃→재로그인→결제 플로우→정보관리→409 처리) | ✅ |
| 로컬 실행 | 백엔드 8002, 프론트 3000, .env.local NEXT_PUBLIC_API_URL | ✅ |

---

## 3. 남은 작업

### 3.1 필수 (서비스 오픈 전)

| 작업 | 내용 | 우선순위 |
|------|------|----------|
| **플랜 코드 반영** | LITE(₩2,900)/PRO(₩19,900) 가격·제한·UI 업데이트 (PLAN_LIMITS, PaymentModal 등) | 높음 |
| **비회원 UX** | 비로그인 시 공고 검색/상세만 가능, AI 상담은 가입 유도 CTA | 높음 |
| **추천 보상 업데이트** | 양쪽 LITE 1개월 무료, 최대 5회 제한 | 높음 |
| **환경 변수 정리** | JWT_SECRET, TOSS_CLIENT_KEY(프론트), TOSS_SECRET_KEY(백엔드), 프로덕션 CORS 등 | 높음 |
| **프로덕션 배포** | 백엔드(uvicorn/gunicorn), 프론트(Next build), DB 백업, HTTPS | 높음 |

### 3.2 권장 (안정화·확장)

| 작업 | 내용 |
|------|------|
| **자동 갱신(빌링키)** | 토스 빌링키 연동, 결제 실패 재시도, 해지 플로우 |
| **결제 이력 테이블** | payments 테이블 생성, 결제 내역 조회 API |
| **만료 전 알림** | 만료 7일/3일/1일 전 알림 |
| **이메일 발송 검증** | SMTP 설정 시 다이제스트 실제 수신 테스트, 스팸 방지 |
| **에러 모니터링** | 백엔드/프론트 에러 로깅, 알림(선택) |

### 3.3 선택 (기능 확장 — PRO 가치 강화)

| 작업 | 내용 |
|------|------|
| **고객사 프로필 다건 관리** | client_profiles 테이블 + CRUD API + UI (PRO 전용) |
| **상담 이력 엑셀 다운로드** | ai_consult_logs 조회 + CSV/Excel 내보내기 API (PRO 전용) |
| **종합 리포트** | 고객별 지원 가능 공고 분석 리포트 + PDF 생성 (PRO 전용) |
| **AI 신청서 작성** | Coming Soon — 건별 과금 (가격 미정) |
| **추가 공공 API** | 필요 시 공고 소스 확대 |
| **모바일 대응** | 반응형 추가 점검, PWA/앱 푸시 정책 |

---

## 4. 접속 URL (로컬)

| 용도 | URL |
|------|-----|
| 사용자 앱 | http://localhost:3000 |
| 캘린더 | http://localhost:3000/calendar |
| 관리자 | http://localhost:3000/admin |
| 백엔드 API | http://localhost:8002 |
| API 문서 | http://localhost:8002/docs |

---

## 5. 요약

- **목적**: 중소기업·소상공인 및 전문 컨설턴트 대상 AI 정부지원금 맞춤 매칭 + 알림 + AI 상담, LITE ₩2,900 / PRO ₩19,900 수익화.
- **개발현황**: 사용자 플로우·백엔드 API·DB·AI 상담(공고AI/자유AI/컨설턴트)·순환학습·알림·토스 결제 연동까지 구현 완료.
- **플랜 재설계 완료**: 비회원→FREE→LITE→PRO 4단계 확정 (2026-03-24). 코드 반영 작업 진행 중.
- **남은 작업**: (1) 플랜 코드 반영 (가격/제한/UI), (2) 자동 갱신(빌링키), (3) PRO 전용 기능(다건 프로필/엑셀/리포트), (4) 프로덕션 배포.
