# PRO 계정 완전 분리 구현 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 또는 superpowers:executing-plans 로 task별 구현. 체크박스(`- [ ]`)로 추적.

**Goal:** PRO를 별도 `pro_users` 풀로 완전 분리 — 자체 인증/결제, `pro_user_id` 키.

**Architecture:** 신규 `pro_users` 테이블 + `/api/auth/pro/*` 인증(JWT `account_type:"pro"`) + `/api/pro/subscribe` + 기존 `/api/pro/*` 28개를 pro 인증·`pro_user_id`로 전환. 소비자 인증/`users`는 무변경.

**Tech Stack:** FastAPI, PostgreSQL(psycopg2 RealDictCursor), bcrypt, PyJWT(HS256), Next.js.

**검증 방식:** 이 프로젝트엔 pytest 하베스가 없음 → 각 task는 **직접 HTTP 호출 + DB 쿼리 스크립트**로 검증(기존 프로젝트 관행). 로컬 백엔드는 `python -m uvicorn app.main:app --port 8001`, 호출 시 브라우저 UA 필요(봇 차단).

**참조:** 설계 스펙 `docs/superpowers/specs/2026-06-23-pro-account-separation-design.md`

---

## Phase 1 — DB 스키마 (추가만)

### Task 1: pro_users 테이블 + pro_user_id 컬럼 추가

**Files:**
- Modify: `backend/app/db/init.sql` (CREATE TABLE 블록 끝에 추가)
- Modify: `backend/app/main.py` (startup 마이그레이션 — 기존 `ADD COLUMN IF NOT EXISTS` 패턴이 있는 곳에 추가)

- [ ] **Step 1: init.sql에 테이블/컬럼 추가**

```sql
CREATE TABLE IF NOT EXISTS pro_users (
    pro_user_id      SERIAL PRIMARY KEY,
    email            VARCHAR(100) UNIQUE,
    password_hash    VARCHAR(255),
    business_number  VARCHAR(20),
    company_name     VARCHAR(100),
    kakao_id         VARCHAR(100),
    naver_id         VARCHAR(100),
    google_id        VARCHAR(100),
    plan             VARCHAR(20) DEFAULT 'free',
    plan_started_at  TIMESTAMP,
    plan_expires_at  TIMESTAMP,
    billing_key      VARCHAR(255),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sign_in_at  TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pro_users_email ON pro_users(email);
CREATE INDEX IF NOT EXISTS idx_pro_users_kakao ON pro_users(kakao_id);

ALTER TABLE client_profiles      ADD COLUMN IF NOT EXISTS pro_user_id INTEGER;
ALTER TABLE client_reports       ADD COLUMN IF NOT EXISTS pro_user_id INTEGER;
ALTER TABLE pro_consult_sessions ADD COLUMN IF NOT EXISTS pro_user_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_client_profiles_prouser ON client_profiles(pro_user_id);
CREATE INDEX IF NOT EXISTS idx_pro_sessions_prouser ON pro_consult_sessions(pro_user_id);
```

- [ ] **Step 2: 운영 DB에 동일 DDL 적용** (init.sql은 신규 DB만 적용되므로 기존 DB엔 마이그레이션 필요)

직접 실행 스크립트(.env DATABASE_URL 사용)로 위 DDL을 운영 DB에 실행.

- [ ] **Step 3: 검증** — `SELECT to_regclass('pro_users')` not null, 세 테이블에 `pro_user_id` 컬럼 존재 확인.

- [ ] **Step 4: 커밋** `feat(pro-auth): pro_users 테이블 + pro_user_id 컬럼 추가`

---

## Phase 2 — PRO 인증 백엔드

> 모든 신규 코드는 `backend/app/main.py`에 기존 인증 블록 인근(2555~4340) 뒤에 추가. 기존 함수는 수정하지 않고 `_pro_` 접두 신규 함수로 격리.

### Task 2: PRO JWT + 가드

**Files:** Modify `backend/app/main.py`

- [ ] **Step 1: 헬퍼 추가** (기존 `_create_jwt` 인근)

```python
def _create_pro_jwt(pro_user_id: int, email: str, plan: str) -> str:
    payload = {
        "account_type": "pro",
        "pro_user_id": pro_user_id,
        "email": email,
        "plan": plan,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _get_current_pro_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    payload = _decode_jwt(authorization.split(" ", 1)[1])
    if payload.get("account_type") != "pro":
        raise HTTPException(status_code=403, detail="PRO 전용 인증이 필요합니다.")
    return payload  # {account_type, pro_user_id, email, plan, exp}


def _require_pro_plan(current_pro: dict) -> dict:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT plan, plan_expires_at FROM pro_users WHERE pro_user_id = %s",
                (current_pro["pro_user_id"],))
    u = cur.fetchone()
    conn.close()
    if not u:
        raise HTTPException(status_code=404, detail="PRO 사용자를 찾을 수 없습니다.")
    if (u["plan"] or "free") not in ("pro", "biz"):
        raise HTTPException(status_code=403, detail="PRO 플랜 전용 기능입니다.")
    if u.get("plan_expires_at"):
        try:
            if datetime.datetime.fromisoformat(str(u["plan_expires_at"])) < datetime.datetime.utcnow():
                raise HTTPException(status_code=403, detail="플랜이 만료되었습니다. 갱신 후 이용하세요.")
        except ValueError:
            pass
    return current_pro
```

- [ ] **Step 2: 검증** — 단위 호출: `account_type` 없는 토큰 → `_get_current_pro_user` 403. 잘못된 토큰 → 401.
- [ ] **Step 3: 커밋** `feat(pro-auth): PRO JWT + 가드(_get_current_pro_user/_require_pro_plan)`

### Task 3: /api/auth/pro/register

**Files:** Modify `backend/app/main.py`

- [ ] **Step 1: 요청 모델 + 핸들러 추가**

```python
class ProRegisterRequest(BaseModel):
    email: str
    password: str
    business_number: Optional[str] = ""
    company_name: Optional[str] = ""

@app.post("/api/auth/pro/register")
def api_pro_register(req: ProRegisterRequest, request: Request):
    ip = _get_client_ip(request)
    if not _rate_limit_check(f"proreg:ip:{ip}", 5, 3600):
        raise HTTPException(status_code=429, detail="가입 시도가 너무 많습니다. 잠시 후 다시 시도해주세요.")
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=400, detail="올바른 이메일을 입력해 주세요.")
    if not req.password or len(req.password) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 8자 이상이어야 합니다.")
    hashed = _hash_password(req.password)
    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT pro_user_id FROM pro_users WHERE email = %s", (req.email,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다.")
        cur.execute(
            """INSERT INTO pro_users (email, password_hash, business_number, company_name, plan, created_at)
               VALUES (%s, %s, %s, %s, 'free', CURRENT_TIMESTAMP) RETURNING pro_user_id""",
            (req.email, hashed, (req.business_number or "").replace("-", "") or None, req.company_name or ""),
        )
        pid = cur.fetchone()["pro_user_id"]
        conn.commit()
        token = _create_pro_jwt(pid, req.email, "free")
        return {"status": "SUCCESS", "token": token, "plan": _get_plan_status("free", None, 0)}
    finally:
        conn.close()
```

- [ ] **Step 2: 검증** — register → 200 + token, account_type=="pro". 중복 이메일 → 409. **소비자 users.email과 같은 이메일도 가입 가능**함을 확인(별도 풀).
- [ ] **Step 3: 커밋** `feat(pro-auth): /api/auth/pro/register`

### Task 4: /api/auth/pro/login

- [ ] **Step 1: 핸들러 추가**

```python
@app.post("/api/auth/pro/login")
def api_pro_login(req: LoginRequest, request: Request):
    ip = _get_client_ip(request)
    if not _rate_limit_check(f"prologin:ip:{ip}", 10, 60):
        raise HTTPException(status_code=429, detail="로그인 시도가 너무 많습니다.")
    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM pro_users WHERE email = %s", (req.email,))
        u = cur.fetchone()
        if not u or not u.get("password_hash") or not _verify_password(req.password, u["password_hash"]):
            raise HTTPException(status_code=401, detail="이메일 또는 비밀번호를 확인해주세요.")
        cur.execute("UPDATE pro_users SET last_sign_in_at = CURRENT_TIMESTAMP WHERE pro_user_id = %s", (u["pro_user_id"],))
        conn.commit()
        plan = u["plan"] or "free"
        token = _create_pro_jwt(u["pro_user_id"], u["email"], plan)
        return {"status": "SUCCESS", "token": token,
                "plan": _get_plan_status(plan, str(u["plan_expires_at"]) if u["plan_expires_at"] else None, 0)}
    finally:
        conn.close()
```

- [ ] **Step 2: 검증** — 올바른 자격 → token, 틀린 비번 → 401, 소셜전용(password_hash NULL) → 401.
- [ ] **Step 3: 커밋** `feat(pro-auth): /api/auth/pro/login`

### Task 5: /api/auth/pro/me

- [ ] **Step 1: 핸들러 추가**

```python
@app.get("/api/auth/pro/me")
def api_pro_me(current_pro: dict = Depends(_get_current_pro_user)):
    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT pro_user_id, email, business_number, company_name, plan, plan_expires_at FROM pro_users WHERE pro_user_id = %s",
                    (current_pro["pro_user_id"],))
        u = cur.fetchone()
        if not u:
            raise HTTPException(status_code=404, detail="PRO 사용자를 찾을 수 없습니다.")
        plan = u["plan"] or "free"
        return {"status": "SUCCESS",
                "plan": _get_plan_status(plan, str(u["plan_expires_at"]) if u["plan_expires_at"] else None, 0),
                "user": {"pro_user_id": u["pro_user_id"], "email": u["email"],
                         "business_number": u["business_number"], "company_name": u["company_name"],
                         "user_type": "business"}}
    finally:
        conn.close()
```

- [ ] **Step 2: 검증** — register 토큰으로 /me → 사용자 반환. 소비자 토큰(account_type 없음) → 403.
- [ ] **Step 3: 커밋** `feat(pro-auth): /api/auth/pro/me`

### Task 6: PRO 소셜로그인

**Files:** Modify `backend/app/main.py`

- [ ] **Step 1: `_pro_social_login_or_register` 추가** (기존 `_social_login_or_register` 본뜨되 pro_users 대상, kakao_id/naver_id/google_id 컬럼 사용)

```python
def _pro_social_login_or_register(provider: str, social_id: str, email: str, name: str):
    col = {"kakao": "kakao_id", "naver": "naver_id", "google": "google_id"}[provider]
    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM pro_users WHERE {col} = %s OR email = %s", (social_id, email))
        u = cur.fetchone()
        if u:
            cur.execute(f"UPDATE pro_users SET {col} = %s, last_sign_in_at = CURRENT_TIMESTAMP WHERE pro_user_id = %s",
                        (social_id, u["pro_user_id"]))
            conn.commit()
            pid, plan = u["pro_user_id"], (u["plan"] or "free")
            exp = str(u["plan_expires_at"]) if u["plan_expires_at"] else None
            is_new = False
        else:
            cur.execute(f"""INSERT INTO pro_users (email, company_name, {col}, plan, created_at, last_sign_in_at)
                           VALUES (%s, %s, %s, 'free', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) RETURNING pro_user_id""",
                        (email, name or "", social_id))
            pid = cur.fetchone()["pro_user_id"]; conn.commit()
            plan, exp, is_new = "free", None, True
        token = _create_pro_jwt(pid, email, plan)
        return token, _get_plan_status(plan, exp, 0), {"pro_user_id": pid, "email": email}, is_new
    finally:
        conn.close()
```

- [ ] **Step 2: 콜백 엔드포인트 추가** `/api/auth/pro/social/callback` — 기존 `/api/auth/social/callback`의 코드교환부(카카오/네이버/구글 토큰→유저정보)를 동일 재사용하되, 마지막에 `_pro_social_login_or_register` 호출. (리다이렉트는 기존 `/api/auth/social/{provider}`를 재사용하고 프론트가 `state`로 pro 풀 표시 → 콜백만 분리)

> 주의: 코드교환 로직(카카오/네이버/구글)이 기존 콜백에 길게 있음 → 공통 함수 `_exchange_social_code(provider, code) -> (social_id, email, name)`로 **추출 리팩터** 후 두 콜백이 공유. (기존 동작 보존 확인 필수)

- [ ] **Step 3: 검증** — 모킹 어려우므로 최소: 콜백 라우트 등록 확인 + `_pro_social_login_or_register` 단위 테스트(가짜 social_id로 insert→재호출 시 동일 pid 반환, email 충돌 처리).
- [ ] **Step 4: 커밋** `feat(pro-auth): PRO 소셜로그인(_pro_social + 콜백, 코드교환 공통화)`

---

## Phase 3 — 결제

### Task 7: /api/pro/subscribe

**Files:** Modify `backend/app/main.py`

- [ ] **Step 1: 핸들러 추가** (기존 `/api/plan/subscribe`의 빌링키 검증 로직 재사용, UPDATE 대상만 pro_users)

```python
@app.post("/api/pro/subscribe")
def api_pro_subscribe(req: SubscribeRequest, current_pro: dict = Depends(_get_current_pro_user)):
    # 빌링키 검증: 기존 _verify_billing_key 로직 재사용 (없으면 /api/plan/subscribe의 검증부를 공통 함수로 추출)
    _verify_billing_key(req.billing_key, req.key_type)  # 실패 시 내부에서 HTTPException
    now = datetime.datetime.utcnow()
    expires_at = (now + datetime.timedelta(days=30)).isoformat()
    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("""UPDATE pro_users SET plan='pro', plan_started_at=%s, plan_expires_at=%s, billing_key=%s
                       WHERE pro_user_id=%s""",
                    (now.isoformat(), expires_at, req.billing_key, current_pro["pro_user_id"]))
        conn.commit()
    finally:
        conn.close()
    token = _create_pro_jwt(current_pro["pro_user_id"], current_pro["email"], "pro")
    return {"status": "SUCCESS", "token": token,
            "plan": _get_plan_status("pro", expires_at, 0),
            "message": "PRO 구독이 시작되었습니다."}
```

> 선행: `/api/plan/subscribe`(4529~)의 PortOne 빌링키 검증부를 `_verify_billing_key(billing_key, key_type)`로 추출(기존 동작 보존). 추출이 위험하면 검증 코드를 인라인 복제.

- [ ] **Step 2: 검증** — pro 토큰 + (테스트용 우회 또는 실제 빌링키)로 호출 → pro_users.plan='pro', /me가 pro 반영.
- [ ] **Step 3: 커밋** `feat(pro-pay): /api/pro/subscribe (pro_users.plan 갱신)`

---

## Phase 4 — /api/pro/* 28개 엔드포인트 전환

> 패턴(모든 대상 동일 적용):
> 1. 시그니처: `current_user: dict = Depends(_get_current_user)` → `current_pro: dict = Depends(_get_current_pro_user)`
> 2. 본문 첫 줄 `_require_pro(current_user)` → `_require_pro_plan(current_pro)`
> 3. PRO 도구 테이블(`client_profiles`, `client_reports`, `pro_consult_sessions`, client_files) 접근 시 `current_user["bn"]` / `owner_business_number` → `current_pro["pro_user_id"]` / `pro_user_id`
> 4. 공유 테이블(announcements 등)은 변경 없음

**대상 28개 (라인은 변동 가능, 함수명 기준):**
`api_pro_announcement_analyze(5360)`, `api_pro_consultant_chat(5434)`, `api_pro_section_feedback(8503)`, `api_pro_insights_recent(8534)`, `api_pro_clients(12322)`, `api_pro_clients_with_history(12359)`, `api_pro_clients_export(12386)`, `api_pro_client_create(12426)`, `api_pro_client_update(12450)`, `api_pro_client_delete(12477)`, `api_pro_client_upload_file(12496)`, `api_pro_client_files(12547)`, `api_pro_client_file_download(12567)`, `api_pro_client_file_delete(12590)`, `api_pro_consult_history(12609)`, `api_pro_consult_history_export(12735)`, `api_pro_report_generate(12821)`, `api_pro_reports(13326)`, `api_pro_report_detail(13368)`, `api_pro_report_edit_section(13398)`, `api_pro_report_update(13481)`, `api_pro_report_pdf(13501)`, `api_pro_file_analyze(13579)`, `api_pro_announcement_stats(13595)`, `api_pro_clients_batch_match(13685)`, `api_pro_business_plan_review(13750)`, `api_pro_file_upload_analyze(13857)`, `api_pro_email_send(14121)`

### Task 8: 헬퍼 키 전환 (_load_client, _load_or_create_session, 상담 핸들러)

**Files:** Modify `backend/app/main.py`

- [ ] **Step 1: `_load_client(db, client_id, key)` — `owner_business_number` 조건을 `pro_user_id`로**

변경: `WHERE id=%s AND owner_business_number=%s AND is_active=TRUE` → `WHERE id=%s AND pro_user_id=%s AND is_active=TRUE`. 호출부 인자 `current_user["bn"]` → `current_pro["pro_user_id"]`.

- [ ] **Step 2: `_load_or_create_session(db, current_pro, req_session_id, client_category)`** — WHERE/INSERT의 `business_number` → `pro_user_id`. (SELECT: `WHERE session_id=%s AND pro_user_id=%s`, INSERT 컬럼에 `pro_user_id`)

- [ ] **Step 3: 상담 핸들러 4종**(`_handle_pro_chat`, `_handle_pro_match`, `_handle_pro_fund_consult`, `_handle_pro_consult`) — `current_user` 인자를 `current_pro`로, 내부 `current_user["bn"]` → `current_pro["pro_user_id"]`.

- [ ] **Step 4: 검증** — Task 9 이후 통합검증에서 함께.
- [ ] **Step 5: 커밋** `refactor(pro): PRO 헬퍼/상담핸들러 키를 pro_user_id로`

### Task 9: 상담·인사이트 엔드포인트 전환 (5360, 5434, 8503, 8534)

- [ ] **Step 1:** 위 패턴으로 4개 엔드포인트 + `pro_consult_sessions`/`client_profiles` 접근 전환.
- [ ] **Step 2: 검증** — Task 13(테스트 계정) 후 실제 상담(match/consult) pro_user_id 기준 동작 + 2차 expert_insights 정상.
- [ ] **Step 3: 커밋** `refactor(pro): 상담/인사이트 엔드포인트 pro 인증 전환`

### Task 10: 고객사(clients) CRUD + 파일 전환 (12322~12597)

- [ ] **Step 1:** 10개 엔드포인트를 패턴 적용. `client_profiles.owner_business_number`/`client_files.owner_business_number` → `pro_user_id`. INSERT 시 `pro_user_id` 채움.
- [ ] **Step 2: 검증** — 고객사 생성→조회→수정→삭제, **다른 pro 계정 간 격리**(A가 만든 고객사 B가 못 봄).
- [ ] **Step 3: 커밋** `refactor(pro): 고객사 CRUD/파일 pro_user_id 전환`

### Task 11: 상담이력 + 리포트 전환 (12609~13512, 13501)

- [ ] **Step 1:** 8개 엔드포인트 패턴 적용. `client_reports.owner_business_number` → `pro_user_id`.
- [ ] **Step 2: 검증** — 리포트 생성→조회→PDF, 계정 격리.
- [ ] **Step 3: 커밋** `refactor(pro): 상담이력/리포트 pro_user_id 전환`

### Task 12: 나머지 PRO 엔드포인트 전환 (13579, 13595, 13685, 13750, 13857, 14121)

- [ ] **Step 1:** 6개 엔드포인트 패턴 적용(파일분석, 통계, 배치매칭, 사업계획검토, 업로드분석, 이메일발송).
- [ ] **Step 2: 검증** — 각 엔드포인트 pro 토큰으로 200, 소비자 토큰으로 403.
- [ ] **Step 3: 커밋** `refactor(pro): 나머지 PRO 엔드포인트 전환`

---

## Phase 5 — 프론트엔드

### Task 13: /pro 인증 연결 + 결제 호출 변경

**Files:** Modify `frontend/src/app/pro/ProPageClient.tsx`, `frontend/src/components/PaymentModal.tsx`

- [ ] **Step 1: ProPageClient** — `/api/auth/me`→`/api/auth/pro/me`, `/api/auth/login`→`/api/auth/pro/login`, `/api/auth/register`→`/api/auth/pro/register`, 소셜 `social_redirect`/콜백 경로를 pro용으로. signup 폼은 email/pw/(사업자번호·회사명).
- [ ] **Step 2: PaymentModal** — `mode==="pro"`일 때 subscribe 호출을 `/api/plan/subscribe`→`/api/pro/subscribe`로 분기. (lite 모드는 기존 유지)
- [ ] **Step 3: 검증** — 프론트 컴파일(홈/`/pro` 200), 소비자앱 무영향.
- [ ] **Step 4: 커밋** `feat(pro-fe): /pro 인증·결제를 PRO 풀 엔드포인트로 연결`

---

## Phase 6 — 테스트 계정 + 통합 검증

### Task 14: pro_users 테스트 계정 시드 + E2E 통합

- [ ] **Step 1:** `pro_users`에 테스트 계정 2개 생성(스크립트): `test-pro@govmatch.kr`(plan=pro, plan_expires 미래), `test-free-pro@govmatch.kr`(plan=free). 비번 bcrypt 해시.
- [ ] **Step 2: 통합 검증 스크립트** — 로컬 백엔드(:8001) 기동 후:
  - pro login → token(account_type=pro)
  - `/api/auth/pro/me` → pro 반영
  - 고객사 생성/조회 (pro_user_id 키), 다른 pro 계정 격리
  - `/api/pro/consultant/chat` action=consult 2차 → expert_insights 정상
  - 소비자 토큰으로 `/api/pro/*` → 403
- [ ] **Step 3: 커밋** `test(pro): 테스트 계정 시드 + 통합 검증`

### Task 15: 최종 리뷰 + 배포

- [ ] 전체 PRO 플로우(가입→결제→상담) 수동 점검, 소비자앱 회귀 없음 확인 → main push.

---

## Self-Review 체크
- 스펙 커버리지: pro_users(T1)·인증(T2-6)·결제(T7)·엔드포인트전환(T8-12)·프론트(T13)·테스트(T14) 모두 포함 ✓
- 미정의 의존성: `_verify_billing_key`, `_exchange_social_code`는 **기존 코드에서 추출**하는 선행 step 명시 ✓ (추출 위험 시 인라인 복제 허용)
- 키 일관성: 모든 PRO 테이블 접근을 `pro_user_id`로 통일 ✓
