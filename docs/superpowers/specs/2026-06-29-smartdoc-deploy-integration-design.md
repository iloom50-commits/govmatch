# SmartDoc 배포 + GovMatch 연동 설계 (공유 스펙)

> **목적:** GovMatch 랜딩에서 "정책자금 융자신청서 자동 작성"(SmartDoc) / "정부 지원사업 상담 프로그램"(현 상담툴) 두 카드로 진입. SmartDoc을 클라우드 배포하고 GovMatch와 SSO·과금·컨텍스트로 연동한다.
>
> **이 문서는 두 레포가 공유하는 계약이다.** GovMatch 에이전트와 SmartDoc 에이전트가 각자 파트를 구현하되 **§3 인터페이스 계약**을 동일하게 따른다.

작성일: 2026-06-29

---

## 1. 합의된 결정 (확정)

| # | 항목 | 결정 |
|---|---|---|
| 1 | 산출물 포맷 | **HWPX/DOCX (순수 파이썬)** — 클라우드 배포 가능. native .hwp(HWP COM, Windows 전용)는 **클라우드에서 비활성** |
| 2 | 인증 | **공유 JWT (HS256)** — SmartDoc이 GovMatch 발급 토큰을 같은 `JWT_SECRET`으로 검증 |
| 3 | 과금 | **별도 과금**. **GovMatch가 사용권·결제(PortOne) 관리**. SmartDoc은 "사용권 있나?"만 GovMatch에 조회 |
| 4 | DB | SmartDoc **자체 Postgres**(앱데이터) + ChromaDB 영속화. (현재 SQLite·로컬 → 이전) |
| 5 | 도메인 | **smartdoc.govmatch.kr** (서브도메인) |
| 6 | 진입 UX | GovMatch 랜딩 **2 제품 카드**. 카드 클릭 시 비로그인이면 그 시점 로그인(deferral) |

**역할 분리:** GovMatch = 신원(JWT 발급) + 과금(PortOne) + 사용권 + 공고/기업 데이터 제공. SmartDoc = 문서 생성 + 자체 앱 DB.

---

## 2. 아키텍처 / 데이터 흐름

```
[GovMatch 랜딩 /pro]
   ├─ 카드A "정책자금 융자신청서 자동 작성"
   │     └─(클릭)→ GovMatch가 핸드오프 토큰 발급 → smartdoc.govmatch.kr?ht=<token>&aid=<공고id>
   │                                                  │
   │                              [SmartDoc 프론트(Vercel)]
   │                                 └─ ht 검증요청 → [SmartDoc 백엔드(Railway)]
   │                                       ├─ ht(공유JWT) 검증 → user 식별
   │                                       ├─ GET GovMatch /api/smartdoc/entitlement (사용권 확인)
   │                                       ├─ GET GovMatch /api/announcements/{aid}/for-smartdoc (양식)
   │                                       └─ (필요시) GET GovMatch 기업 프로필
   │                                 → 신청서 자동 작성 (HWPX/DOCX)
   │
   └─ 카드B "정부 지원사업 상담 프로그램"
         └─(클릭)→ 현재 ProSecretary 플로우 (신규사업자/신규개인/기존고객)
```

- 비로그인 사용자가 카드 클릭 → GovMatch 로그인(모달) 후 위 흐름 진행.
- 사용권 없으면 SmartDoc은 GovMatch 결제 화면으로 유도(딥링크).

---

## 3. 인터페이스 계약 ⭐ (두 레포 공통 — 반드시 일치)

### 3.1 공유 JWT
- 두 서비스가 **동일한 `JWT_SECRET`** 환경변수를 가진다. 알고리즘 **HS256**.
- GovMatch 일반 세션 토큰 payload: `{user_id, bn, email, plan, trial_ends_at, exp}` (기존).
- **핸드오프 토큰(handoff token, `ht`)** — GovMatch가 카드A 클릭 시 발급:
  - payload: `{ "sub": <user_id>, "bn": <사업자번호>, "email": <email>, "aud": "smartdoc", "purpose": "handoff", "exp": now+300s }`
  - 단기(5분), `aud:"smartdoc"` 강제. SmartDoc은 `aud`·`exp`·서명 검증 후 user 식별.
- SmartDoc은 검증 성공 시 **자체 세션 토큰**(SmartDoc DB 기반)을 발급해 이후 SmartDoc API에 사용한다. (ht는 1회 진입용)

### 3.2 GovMatch가 제공하는 엔드포인트 (SmartDoc이 호출)

**(a) 핸드오프 토큰 발급** — GovMatch 내부(프론트가 카드A 클릭 시 호출)
```
POST /api/smartdoc/handoff   (Authorization: Bearer <GovMatch 세션 JWT>)
body: { "announcement_id": <int|null> }
resp: { "status":"SUCCESS", "handoff_token": "<ht>", "url": "https://smartdoc.govmatch.kr?ht=<ht>&aid=<id>" }
```

**(b) 사용권 확인** — SmartDoc 백엔드가 호출
```
GET /api/smartdoc/entitlement   (Authorization: Bearer <ht 또는 GovMatch JWT>)
resp: { "status":"SUCCESS",
        "has_access": true|false,
        "plan": "smartdoc_basic"|null,
        "remaining": <int|null>,        // 크레딧제면 잔여, 무제한이면 null
        "expires_at": "2026-12-31"|null,
        "purchase_url": "https://govmatch.kr/pro?buy=smartdoc" }   // 미보유 시 결제 유도
```

**(c) 공고 상세 + 양식** — **이미 존재** (변경 없음)
```
GET /api/announcements/{id}/for-smartdoc   (무인증 화이트리스트)
resp: { 공고 원문/분석 + attachments[]( 양식 프록시 URL ) }   // 기존 계약 유지
```

**(d) 기업(고객) 프로필** — SmartDoc이 신청서 자동작성에 사용 (신규 추가)
```
GET /api/smartdoc/client-profile?client_profile_id=<id>   (Authorization: Bearer <ht|JWT>)
resp: { "status":"SUCCESS",
        "profile": { company_name, business_number, industry_code, industry_name,
                     address_city, establishment_date, revenue_bracket,
                     employee_count_bracket, interests } }
// client_profile_id 없으면 토큰의 user(bn) 본인 기업 정보 반환
```

### 3.3 핸드오프 URL 규약
```
https://smartdoc.govmatch.kr?ht=<handoff_token>&aid=<announcement_id?>
```
- `ht` 필수, `aid` 선택(특정 공고 양식 작성 시).

---

## 4. GovMatch 책임 (현재 레포 — 내가 구현)

1. **2카드 랜딩** (`/pro` 진입화면): "정책자금 융자신청서 자동 작성"(→ 카드A) / "정부 지원사업 상담 프로그램"(→ 기존 ProSecretary). 비로그인 deferral 유지.
2. **사용권 저장(별도 과금)**: GovMatch DB에 SmartDoc 사용권 추가 (컬럼/테이블 — 예: `smartdoc_plan`, `smartdoc_expires_at` 또는 `smartdoc_credits`). **컬럼 추가만, 기존 변경/삭제 금지.**
3. **결제 흐름**: 기존 PortOne 재사용 — SmartDoc 상품 추가(`/pro?buy=smartdoc`). 결제 성공 시 사용권 갱신.
4. **§3.2 엔드포인트 구현**: (a) `POST /api/smartdoc/handoff`, (b) `GET /api/smartdoc/entitlement`, (d) `GET /api/smartdoc/client-profile`. 화이트리스트/CORS 반영.
5. `JWT_SECRET`을 SmartDoc과 공유(동일 값 환경변수).

## 5. SmartDoc 책임 (C:\DevProjects\SmartDoc — SmartDoc 에이전트)

1. **클라우드 배포**: 백엔드 Railway(FastAPI), 프론트 Vercel(Vite/React), 도메인 smartdoc.govmatch.kr.
2. **DB 이전**: SQLite(SQLAlchemy+aiosqlite) → **Postgres**(`DATABASE_URL`). ChromaDB는 **영속 볼륨** 또는 호스티드 벡터로.
3. **HWP COM 비활성**: `api/hwp_com.py`, `services/hwp_com_engine.py`(win32com/pythoncom)는 Linux에서 import/호출 가드(try-except + 기능 플래그). 주 산출물은 HWPX 템플릿엔진 + docxtpl(DOCX).
4. **공유 JWT 검증**: 진입 `ht` 검증(서명·aud·exp, 공유 `JWT_SECRET`) → user 식별 → 자체 세션 발급.
5. **GovMatch 호출 연동** (`api/external.py` 확장):
   - 사용권: `GET {GOVMATCH}/api/smartdoc/entitlement` — 미보유 시 `purchase_url`로 유도.
   - 양식: `GET {GOVMATCH}/api/announcements/{aid}/for-smartdoc` (기존).
   - 기업정보: `GET {GOVMATCH}/api/smartdoc/client-profile`.
6. **CORS**: `https://govmatch.kr`, `https://smartdoc.govmatch.kr` 허용.
7. **환경변수**: `JWT_SECRET`(공유), `DATABASE_URL`(Postgres), `GOVMATCH_BASE=https://govmatch-production.up.railway.app`, `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`GOOGLE_API_KEY`/`TAVILY_API_KEY`.

---

## 6. 배포 메모 / 리스크

- **ChromaDB 영속화**가 Railway에서 까다로움 — 볼륨 마운트 또는 외부 벡터(예: 호스티드)로. (배포 1차 리스크)
- **crawl4ai**(Playwright 기반)·pymupdf 등 무거운 의존성 → 이미지 크기·콜드스타트 주의. 불필요 라우터는 배포에서 제외 검토.
- **HWPX가 native .hwp와 100% 호환**되는지(주관기관 제출 가능 여부)는 별도 검증 필요 — 본 설계는 "HWPX/DOCX 충분" 전제(사용자 확인).
- 별도 과금 UX(가격·플랜)는 미정 — 결제 흐름 구현 전 가격정책 확정 필요.

## 7. 범위 밖(이번 설계 제외)

- SmartDoc 내부 문서생성 품질/프롬프트 개선.
- native .hwp(COM) 클라우드 지원.
- 두 제품 통합 단일 로그인 화면 리디자인(현 GovMatch 로그인 재사용).

---

## 8. 작업 순서(권장)

1. **GovMatch**: §4.1 2카드 랜딩(독립적, 먼저 가능) + §4.2~4.5 엔드포인트/사용권/결제.
2. **SmartDoc**: §5 배포(DB이전·HWP COM가드·CORS) → §5.4~5.5 JWT검증·GovMatch연동.
3. **통합 검증**: 핸드오프 토큰 → SmartDoc 진입 → 사용권 확인 → 양식/기업정보 수신 → 신청서 생성 E2E.

> 두 에이전트는 **§3 인터페이스 계약**을 단일 진실로 삼는다. 계약 변경 시 양측 동시 반영.
