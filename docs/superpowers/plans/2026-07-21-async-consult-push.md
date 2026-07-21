# AI 상담 비동기화 + 완료 푸시 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 공고 AI상담(`POST /api/ai/consult`)을 항상 백그라운드 작업으로 돌려, 사용자가 채팅창을 닫아도 완료 시 웹 푸시로 알리고 푸시를 탭하면 해당 상담을 복원해 연다.

**Architecture:** 제출 엔드포인트가 `consult_jobs`(processing) 행을 만들고 `job_id`를 즉시 반환한 뒤 FastAPI `BackgroundTasks`로 기존 상담 로직(`ensure_analysis`+`chat_consult`+`ai_consult_logs` 저장+성공 시 과금)을 워커에서 실행한다. 프론트는 job을 폴링하고, 처리 중 창을 닫으면 `notify` 플래그를 세워 완료 시 트랜잭션 푸시를 받는다. 결과 저장·세션 복원·서비스워커 라우팅 등 기존 인프라를 재사용한다.

**Tech Stack:** FastAPI(sync def + BackgroundTasks), PostgreSQL(psycopg2, RealDictCursor), pywebpush(VAPID), Next.js/React(AiConsultModal), 기존 test 하네스(FakeConn/FakeCursor monkeypatch, `python test_*_unit.py`).

**설계서:** `docs/superpowers/specs/2026-07-21-async-consult-push-design.md`

---

## File Structure

- `backend/app/main.py` — 스키마 마이그레이션(`consult_jobs`), `api_ai_consult` 리팩터(제출), `_run_consult_job` 워커, 신규 엔드포인트 4개(job 상태/notify/pending/seen).
- `backend/app/services/notification_service.py` — `send_transactional_push` 신설.
- `backend/test_async_consult_unit.py` — (신규) 워커·과금·notify 경쟁·stale 단위 테스트.
- `backend/test_transactional_push_unit.py` — (신규) 시간대 게이트 없음 검증.
- `frontend/src/components/AiConsultModal.tsx` — 제출+폴링, 처리 중 닫기 핸들러, 권한 유도.
- `frontend/src/app/HomeClient.tsx` — `?consult=<sid>&aid=<id>` 딥링크 감지→모달 오픈, 인앱 배지.
- `frontend/src/lib/push.ts` — (신규 또는 기존 재사용) 구독 헬퍼. 기존 `NotificationModal`/`layout.tsx` 로직 재사용 가능하면 그것을 export.

> 배포 정책: DB는 추가만(컬럼 삭제·변경 금지). 로컬 테스트→git push. 커밋은 `feature/async-consult-push` 브랜치.

---

## Task 1: `consult_jobs` 테이블 마이그레이션

**Files:**
- Modify: `backend/app/main.py` (스키마 마이그레이션 블록, 대략 `main.py:135` 부근의 `CREATE TABLE IF NOT EXISTS consult_sessions` 뒤)

- [ ] **Step 1: 스키마 생성 SQL 추가**

`consult_sessions` 생성 블록 바로 다음에 삽입:

```python
            CREATE TABLE IF NOT EXISTS consult_jobs (
                job_id UUID PRIMARY KEY,
                session_id VARCHAR(64),
                business_number VARCHAR(50),
                announcement_id INTEGER,
                status VARCHAR(20) NOT NULL DEFAULT 'processing',
                result JSONB,
                notify_requested BOOLEAN NOT NULL DEFAULT FALSE,
                notified BOOLEAN NOT NULL DEFAULT FALSE,
                seen BOOLEAN NOT NULL DEFAULT FALSE,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
```

기존 마이그레이션 블록이 `cursor.execute(""" ... """)`로 여러 CREATE를 실행하는 방식이면 같은 문자열에 추가. 별도 execute 블록이면 아래 인덱스와 함께 새 execute 추가:

```python
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_consult_jobs_bn_status ON consult_jobs(business_number, status)")
```

- [ ] **Step 2: 로컬 기동으로 마이그레이션 무오류 확인**

Run: `cd backend && python -c "import app.main"`
Expected: import 성공, 예외 없음. (DB 연결이 없으면 마이그레이션은 런타임에 실행되므로, 최소한 SQL 문자열 문법 오류가 없어야 함. 실제 테이블 생성은 배포 후 기동 시.)

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(consult): consult_jobs 테이블 마이그레이션 추가"
```

---

## Task 2: 범용 트랜잭션 푸시 `send_transactional_push`

**Files:**
- Modify: `backend/app/services/notification_service.py` (클래스 `NotificationService` 내, `send_push` 다음)
- Test: `backend/test_transactional_push_unit.py` (신규)

- [ ] **Step 1: 실패하는 테스트 작성**

`send_transactional_push`가 **시간대 게이트 없이** 구독을 조회해 발송을 시도하는지 검증(pywebpush를 몽키패치). 야간(UTC 기준 KST 새벽)에도 발송 경로에 진입해야 함.

```python
# -*- coding: utf-8 -*-
"""send_transactional_push: 09~18시 게이트 없음 + 임의 title/body/url 발송 검증."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_URL", "postgresql://t:t@localhost/t")
os.environ.setdefault("VAPID_PRIVATE_KEY", "x")
os.environ.setdefault("VAPID_CLAIMS_EMAIL", "mailto:a@b.c")

import app.services.notification_service as ns


class _Cur:
    def __init__(self, subs): self._subs = subs; self._r = None
    def execute(self, sql, params=None):
        if "FROM push_subscriptions" in sql:
            self._r = self._subs
    def fetchall(self): return self._r or []
    def close(self): pass

class _Conn:
    def __init__(self, subs): self._c = _Cur(subs)
    def cursor(self): return self._c
    def commit(self): pass
    def close(self): pass


def test_transactional_push_no_time_gate(monkeypatch):
    subs = [{"endpoint": "https://e/1", "p256dh": "k", "auth": "a"}]
    monkeypatch.setattr(ns.psycopg2, "connect", lambda *a, **k: _Conn(subs))
    sent_payloads = []
    def _fake_webpush(**kw):
        sent_payloads.append(kw["data"])
    # pywebpush는 함수 내부에서 import되므로 모듈 속성으로 주입
    import types
    fake_mod = types.SimpleNamespace(webpush=_fake_webpush, WebPushException=Exception)
    monkeypatch.setitem(sys.modules, "pywebpush", fake_mod)

    svc = ns.NotificationService()
    sent = svc.send_transactional_push("111-11-11111", "제목", "본문", "/?consult=abc&aid=1")

    assert sent == 1, "시간대와 무관하게 1건 발송되어야 함"
    assert "제목" in sent_payloads[0]
    assert "/?consult=abc&aid=1" in sent_payloads[0]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest test_transactional_push_unit.py -v`
Expected: FAIL — `AttributeError: 'NotificationService' object has no attribute 'send_transactional_push'`

- [ ] **Step 3: 구현**

`send_push` 메서드 바로 다음에 추가(시간대 게이트·matches 모양 제거):

```python
    def send_transactional_push(self, business_number: str, title: str, body: str, url: str) -> int:
        """트랜잭션 알림(상담 완료 등) — 시간대 게이트 없음, 임의 title/body/url."""
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            print("  pywebpush 미설치 -> 트랜잭션 푸시 건너뜀")
            return 0

        vapid_private = os.getenv("VAPID_PRIVATE_KEY", "")
        vapid_claims_email = os.getenv("VAPID_CLAIMS_EMAIL", "")
        if not vapid_private or not vapid_claims_email:
            return 0

        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cursor = conn.cursor()
        cursor.execute("SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE business_number = %s", (business_number,))
        subs = cursor.fetchall()
        conn.close()
        if not subs:
            return 0

        payload = json.dumps({
            "title": title,
            "body": body,
            "url": url,
            "icon": "https://www.govmatch.kr/icon-192.png",
        }, ensure_ascii=False)

        sent = 0
        for sub in subs:
            try:
                webpush(
                    subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                    data=payload,
                    vapid_private_key=vapid_private,
                    vapid_claims={"sub": vapid_claims_email},
                )
                sent += 1
            except WebPushException as e:
                if "410" in str(e) or "404" in str(e):
                    conn2 = psycopg2.connect(DATABASE_URL)
                    cur2 = conn2.cursor()
                    cur2.execute("DELETE FROM push_subscriptions WHERE endpoint = %s", (sub["endpoint"],))
                    conn2.commit()
                    conn2.close()
                print(f"  TxPush error ({sub['endpoint'][:40]}...): {e}")
            except Exception as e:
                print(f"  TxPush error: {e}")

        if sent:
            self._log_notification(business_number, "consult", "push", f"tx_sent:{sent}")
        return sent
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest test_transactional_push_unit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/notification_service.py backend/test_transactional_push_unit.py
git commit -m "feat(push): 시간대 게이트 없는 send_transactional_push 추가"
```

---

## Task 3: `api_ai_consult` 제출형 리팩터 + `_run_consult_job` 워커

**핵심 원칙:** 제출은 싸고 게이트인 것만 동기 처리(프로필 로드·세션 판별·402·session insert·job insert) 후 즉시 반환. 무거운 부분(ensure_analysis·chat_consult·저장·과금·푸시)은 워커.

**Files:**
- Modify: `backend/app/main.py:5445-5644` (`api_ai_consult` 전체)
- Test: `backend/test_async_consult_unit.py` (신규)

- [ ] **Step 1: 실패하는 테스트 작성 (제출 즉시 반환 + 워커 과금)**

```python
# -*- coding: utf-8 -*-
"""api_ai_consult 제출형 + _run_consult_job 워커: 즉시 반환·성공시에만 과금·실패 무차감."""
import os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://t:t@localhost/t")

import app.main as main
import app.services.ai_consultant as ai_consultant


class FakeCursor:
    def __init__(self, state):
        self.s = state; self._r = None; self.rowcount = 0
    def execute(self, sql, params=None):
        q = " ".join(sql.split()); p = params or ()
        if q.startswith("SELECT plan, ai_usage_month"):
            self._r = self.s["user_row"]
        elif "FROM consult_sessions WHERE session_id" in q:
            self._r = {"id": 1} if self.s.get("existing_session") else None
        elif q.startswith("SELECT credits FROM users"):
            self._r = {"credits": self.s["users"].get(p[0], {}).get("credits", 0)}
        elif "SELECT COALESCE(SUM" in q or "wallet" in q.lower():
            self._r = {"credits": self.s["users"].get(p[0], {}).get("credits", 0)}
        elif q.startswith("INSERT INTO consult_sessions"):
            pass
        elif q.startswith("INSERT INTO consult_jobs"):
            self.s["jobs"][p[0]] = {"status": "processing", "notify_requested": False, "notified": False}
        elif q.startswith("UPDATE consult_jobs SET status = 'done'") or "status = 'done'" in q:
            self.s["jobs"][self.s["last_job"]]["status"] = "done"
        elif q.startswith("UPDATE consult_jobs SET status = 'failed'") or "status = 'failed'" in q:
            self.s["jobs"][self.s["last_job"]]["status"] = "failed"
        elif "SELECT announcement_id, title" in q:
            self._r = {"announcement_id": 1, "title": "테스트공고", "origin_url": "http://x", "target_type": "business",
                       "department": "", "category": "", "support_amount": "", "deadline_date": None,
                       "summary_text": "", "region": "", "eligibility_logic": None}
        elif q.startswith("INSERT INTO ai_consult_logs"):
            self._r = {"id": 99}
        elif q.startswith("UPDATE users SET credits = credits - %s"):
            amount, uid, minamt = p
            u = self.s["users"].get(uid)
            if u and u["credits"] >= minamt:
                u["credits"] -= amount; self._r = {"credits": u["credits"]}; self.rowcount = 1
            else:
                self._r = None; self.rowcount = 0
        elif q.startswith("INSERT INTO credit_transactions"):
            self.rowcount = 1
        elif "SELECT notify_requested" in q:
            j = self.s["jobs"].get(p[0], {})
            self._r = {"notify_requested": j.get("notify_requested", False), "notified": j.get("notified", False),
                       "session_id": "sid", "announcement_id": 1}
        else:
            self._r = None
    def fetchone(self): return self._r
    def fetchall(self): return []
    def close(self): pass

class FakeConn:
    def __init__(self, state): self.s = state
    def cursor(self): return FakeCursor(self.s)
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


def _state(credits=200, existing=False):
    return {
        "users": {1: {"credits": credits}},
        "user_row": {"business_number": "111-11-11111", "user_type": "business", "company_name": "테스트",
                     "establishment_date": "", "address_city": "", "industry_code": "",
                     "revenue_bracket": "", "employee_count_bracket": "", "interests": "",
                     "age_range": "", "gender": "", "income_level": "", "family_type": "",
                     "employment_status": "", "housing_status": "", "plan": "free",
                     "ai_usage_month": 0, "ai_usage_reset_at": None, "plan_expires_at": None},
        "existing_session": existing, "jobs": {}, "last_job": None,
    }


def _patch_db(monkeypatch, state):
    monkeypatch.setattr(main, "get_db_connection", lambda: FakeConn(state))


def test_submit_returns_processing_immediately(monkeypatch):
    state = _state()
    _patch_db(monkeypatch, state)
    monkeypatch.setattr(main, "BackgroundTasks", None, raising=False)  # placeholder; use real BackgroundTasks below

    from fastapi import BackgroundTasks
    bt = BackgroundTasks()
    req = main.AiConsultRequest(announcement_id=1, messages=[{"role": "user", "text": "질문"}], session_id=None)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    resp = main.api_ai_consult(req, background_tasks=bt, current_user=current_user)

    assert resp["status"] == "PROCESSING"
    assert resp["job_id"]
    assert resp["session_id"]
    assert len(bt.tasks) == 1, "백그라운드 워커가 1개 예약되어야 함"
    assert state["users"][1]["credits"] == 200, "제출 시점엔 차감 없음"


def test_worker_charges_only_on_success(monkeypatch):
    state = _state()
    _patch_db(monkeypatch, state)
    monkeypatch.setattr(ai_consultant, "chat_consult",
                        lambda **kw: {"reply": "결론", "choices": [], "done": True, "conclusion": "가능"})
    # ensure_analysis 우회
    import app.services.doc_analysis_service as das
    monkeypatch.setattr(das, "ensure_analysis", lambda *a, **k: {})

    job_id = str(uuid.uuid4()); state["last_job"] = job_id
    state["jobs"][job_id] = {"status": "processing", "notify_requested": False, "notified": False}
    req = main.AiConsultRequest(announcement_id=1,
                                messages=[{"role": "user", "text": "1"}, {"role": "assistant", "text": "a"},
                                          {"role": "user", "text": "2"}, {"role": "assistant", "text": "b"},
                                          {"role": "user", "text": "3"}], session_id="sid")
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    main._run_consult_job(job_id, req, current_user, "sid", is_new_session=True)

    assert state["users"][1]["credits"] == 150, "신규 세션 성공 후 50 차감"
    assert state["jobs"][job_id]["status"] == "done"


def test_worker_no_charge_on_failure(monkeypatch):
    state = _state()
    _patch_db(monkeypatch, state)
    def _boom(**kw): raise RuntimeError("LLM 실패")
    monkeypatch.setattr(ai_consultant, "chat_consult", _boom)
    import app.services.doc_analysis_service as das
    monkeypatch.setattr(das, "ensure_analysis", lambda *a, **k: {})

    job_id = str(uuid.uuid4()); state["last_job"] = job_id
    state["jobs"][job_id] = {"status": "processing", "notify_requested": False, "notified": False}
    req = main.AiConsultRequest(announcement_id=1, messages=[{"role": "user", "text": "1"}], session_id="sid")
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    main._run_consult_job(job_id, req, current_user, "sid", is_new_session=True)

    assert state["users"][1]["credits"] == 200, "LLM 실패 시 무차감"
```

> 참고: `chat_consult`가 예외를 던져도 현행 엔드포인트는 폴백 응답을 만들고 `llm_ok=False`로 무차감한다. 워커도 동일하게 `llm_ok` 플래그로 성공을 판정하고, 실패 시 `consult_jobs.status='failed'`로 둔다(폴백 응답을 done으로 저장하지 않음 — 사용자가 재시도하도록).

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest test_async_consult_unit.py -v`
Expected: FAIL — `api_ai_consult() got unexpected keyword 'background_tasks'` / `_run_consult_job` 미정의.

- [ ] **Step 3: 구현 — 제출 엔드포인트**

`api_ai_consult`를 아래로 교체(시그니처에 `background_tasks: BackgroundTasks` 추가). 파일 상단 import에 `from fastapi import BackgroundTasks`가 없으면 추가.

```python
@app.post("/api/ai/consult")
def api_ai_consult(req: AiConsultRequest, background_tasks: BackgroundTasks, current_user: dict = Depends(_get_current_user)):
    """AI 상담 제출 — job 생성 후 즉시 반환, 실제 분석은 백그라운드 워커에서."""
    import uuid as _uuid
    bn = current_user["bn"]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 1) 사용자 존재 확인(프로필은 워커에서 다시 로드 — 커넥션 분리)
        cur.execute("SELECT plan, ai_usage_month, ai_usage_reset_at, plan_expires_at, business_number FROM users WHERE business_number = %s", (bn,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # 2) 신규/기존 세션 판별
        session_id = req.session_id
        is_existing_session = False
        if session_id:
            try:
                cur.execute("""
                    SELECT id FROM consult_sessions
                    WHERE session_id = %s AND business_number = %s AND announcement_id = %s
                      AND created_at > NOW() - INTERVAL '24 hours'
                """, (session_id, bn, req.announcement_id))
                if cur.fetchone():
                    is_existing_session = True
            except Exception:
                pass
        is_new_session = not is_existing_session

        # 3) 신규 세션이면 402 사전 차단 + session 발급
        if is_new_session:
            if not _is_credit_exempt(current_user):
                bal = wallet.wallet_balance(cur, current_user["user_id"])
                if bal < CREDIT_COST_ANALYZE:
                    raise HTTPException(status_code=402, detail={"error": "insufficient_credits", "required": CREDIT_COST_ANALYZE, "balance": bal})
            session_id = str(_uuid.uuid4())
            try:
                cur.execute("INSERT INTO consult_sessions (session_id, business_number, announcement_id) VALUES (%s, %s, %s)",
                            (session_id, bn, req.announcement_id))
                conn.commit()
            except Exception:
                pass

        # 4) job 생성
        job_id = str(_uuid.uuid4())
        cur.execute("""INSERT INTO consult_jobs (job_id, session_id, business_number, announcement_id, status)
                       VALUES (%s, %s, %s, %s, 'processing')""",
                    (job_id, session_id, bn, req.announcement_id))
        conn.commit()
    finally:
        conn.close()

    # 5) 백그라운드 워커 예약 후 즉시 반환
    background_tasks.add_task(_run_consult_job, job_id, req, current_user, session_id, is_new_session)
    return {"status": "PROCESSING", "job_id": job_id, "session_id": session_id, "is_new_session": is_new_session}
```

- [ ] **Step 4: 구현 — 워커 함수**

`api_ai_consult` 바로 아래에 추가. (현행 5516–5644 로직을 이관하되, 결과를 `consult_jobs`에 기록하고 notify_requested를 재조회해 푸시.)

```python
def _run_consult_job(job_id: str, req: "AiConsultRequest", current_user: dict, session_id: str, is_new_session: bool):
    """백그라운드 워커 — ensure_analysis + chat_consult + 저장 + 성공시 과금 + (닫힘시)푸시.
    요청 스코프 커넥션을 재사용하지 않고 자체 커넥션을 열고 닫는다."""
    bn = current_user["bn"]
    result_payload = None
    consult_log_id = None
    llm_ok = False
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # 프로필 로드
        cur.execute(
            """SELECT plan, company_name, establishment_date, address_city, industry_code,
                      revenue_bracket, employee_count_bracket, interests, user_type,
                      age_range, business_number, gender,
                      income_level, family_type, employment_status, housing_status
               FROM users WHERE business_number = %s""", (bn,))
        user = cur.fetchone()
        u = dict(user) if user else {}
        for k in ("company_name", "establishment_date", "address_city", "industry_code",
                  "revenue_bracket", "employee_count_bracket", "interests", "user_type", "age_range",
                  "gender", "income_level", "family_type", "employment_status", "housing_status"):
            if u.get(k) is None:
                u[k] = ""

        # 공고 조회
        cur.execute(
            """SELECT announcement_id, title, department, category, support_amount, deadline_date,
                      summary_text, region, eligibility_logic, origin_url, target_type
               FROM announcements WHERE announcement_id = %s""", (req.announcement_id,))
        ann = cur.fetchone()
        if not ann:
            raise RuntimeError("공고를 찾을 수 없음")
        a = dict(ann)
        conn.close()

        # 정밀 분석 보장
        deep = {}
        try:
            from app.services.doc_analysis_service import ensure_analysis
            aconn = get_db_connection()
            deep = ensure_analysis(req.announcement_id, aconn) or {}
            aconn.close()
        except Exception as e:
            print(f"[ConsultJob] ensure_analysis error #{req.announcement_id}: {e}")

        # 프로필 필터
        _BIZ = {"business_number", "company_name", "industry_code", "revenue_bracket", "employee_count_bracket", "establishment_date", "address_city", "interests", "user_type", "certifications"}
        _INDIV = {"age_range", "income_level", "family_type", "employment_status", "housing_status", "gender", "address_city", "interests", "user_type"}
        _COMMON = {"address_city", "interests", "user_type", "email", "plan"}
        ann_target = (a.get("target_type") or "business").lower()
        if ann_target == "individual":
            consult_profile = {k: v for k, v in u.items() if k in (_INDIV | _COMMON) and v}
        else:
            consult_profile = {k: v for k, v in u.items() if k in (_BIZ | _COMMON) and v}

        # LLM
        from app.services.ai_consultant import chat_consult
        cconn = get_db_connection()
        result = chat_consult(announcement_id=req.announcement_id, messages=req.messages,
                              announcement=a, deep_analysis_data=deep, user_profile=consult_profile, db_conn=cconn)
        cconn.close()
        llm_ok = True

        is_done = result.get("done", False)
        user_msg_count = sum(1 for m in req.messages if m.get("role") == "user")
        if is_done and user_msg_count < 3:
            is_done = False
            result["done"] = False
            result["conclusion"] = None

        # ai_consult_logs 저장
        all_msgs = req.messages + [{"role": "assistant", "text": result.get("reply", "")}]
        lconn = get_db_connection()
        lcur = lconn.cursor()
        lcur.execute("""
            INSERT INTO ai_consult_logs (announcement_id, business_number, messages, conclusion, session_id, updated_at)
            VALUES (%s, %s, %s::jsonb, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (session_id) WHERE session_id IS NOT NULL DO UPDATE SET
                messages = EXCLUDED.messages,
                conclusion = COALESCE(EXCLUDED.conclusion, ai_consult_logs.conclusion),
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """, (req.announcement_id, bn, json.dumps(all_msgs, ensure_ascii=False),
              result.get("conclusion") if is_done else None, session_id))
        row = lcur.fetchone()
        consult_log_id = row["id"] if row else None
        lconn.commit()
        lconn.close()

        # 성공 시에만 과금
        if is_new_session and llm_ok:
            _charge_credits(current_user, CREDIT_COST_ANALYZE, "analyze", ref=session_id)

        final_reply = result.get("reply", "") or f"**{a.get('title', '공고')}** 분석을 시작합니다. 아래 선택지를 눌러 질문해 주세요."
        result_payload = {
            "reply": final_reply,
            "choices": result.get("choices", []),
            "done": is_done,
            "conclusion": result.get("conclusion") if is_done else None,
            "consult_log_id": consult_log_id if is_done else None,
            "session_id": session_id,
            "origin_url": a.get("origin_url", ""),
        }

        # job done 기록
        jconn = get_db_connection()
        jcur = jconn.cursor()
        jcur.execute("""UPDATE consult_jobs SET status = 'done', result = %s::jsonb, updated_at = CURRENT_TIMESTAMP
                        WHERE job_id = %s""", (json.dumps(result_payload, ensure_ascii=False), job_id))
        jconn.commit()

        # notify_requested 재조회 → 닫고 나갔으면 푸시
        jcur.execute("SELECT notify_requested, notified, session_id, announcement_id FROM consult_jobs WHERE job_id = %s", (job_id,))
        jrow = jcur.fetchone()
        if jrow and jrow["notify_requested"] and not jrow["notified"]:
            _maybe_send_consult_push(job_id, bn, session_id, req.announcement_id, a.get("title", "공고"), jcur, jconn)
        jconn.close()

    except Exception as e:
        print(f"[ConsultJob] {job_id} failed: {e}")
        import traceback; traceback.print_exc()
        try:
            fconn = get_db_connection()
            fcur = fconn.cursor()
            fcur.execute("""UPDATE consult_jobs SET status = 'failed', error = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE job_id = %s""", (str(e)[:500], job_id))
            fconn.commit()
            fconn.close()
        except Exception:
            pass


def _maybe_send_consult_push(job_id, bn, session_id, announcement_id, title, cur, conn):
    """consult 완료 푸시 발송 + notified=true. cur/conn은 열린 상태로 전달받는다."""
    try:
        from app.services.notification_service import notification_service
        url = f"/?consult={session_id}&aid={announcement_id}"
        sent = notification_service.send_transactional_push(bn, "상담 분석이 완료됐어요", str(title)[:60], url)
        cur.execute("UPDATE consult_jobs SET notified = TRUE, updated_at = CURRENT_TIMESTAMP WHERE job_id = %s", (job_id,))
        conn.commit()
        return sent
    except Exception as e:
        print(f"[ConsultJob] push error {job_id}: {e}")
        return 0
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd backend && python -m pytest test_async_consult_unit.py -v`
Expected: PASS (3 tests). FakeCursor의 SQL 매칭이 실제 쿼리와 어긋나면 테스트를 실제 쿼리 문자열에 맞춰 조정.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/test_async_consult_unit.py
git commit -m "feat(consult): api_ai_consult 제출형 리팩터 + _run_consult_job 워커 (성공시에만 과금)"
```

---

## Task 4: job 상태 폴링 + lazy stale 정리

**Files:**
- Modify: `backend/app/main.py` (워커 다음)
- Test: `backend/test_async_consult_unit.py` (추가)

- [ ] **Step 1: 실패하는 테스트 추가**

```python
def test_poll_stale_processing_becomes_failed(monkeypatch):
    state = _state()
    # 30분 초과 processing job
    class _C(FakeCursor):
        def execute(self, sql, params=None):
            q = " ".join(sql.split())
            if q.startswith("SELECT job_id, status, result, error, business_number, updated_at"):
                self._r = {"job_id": "j1", "status": "processing", "result": None, "error": None,
                           "business_number": "111-11-11111", "stale": True}
            elif "UPDATE consult_jobs SET status = 'failed'" in q:
                self.s.setdefault("failed", []).append(params)
                self._r = None
            else:
                super().execute(sql, params)
    monkeypatch.setattr(main, "get_db_connection",
                        lambda: type("C", (FakeConn,), {"cursor": lambda s: _C(state)})(state))
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    resp = main.api_ai_consult_job("j1", current_user=current_user)
    assert resp["status"] == "failed"
```

> 이 테스트는 stale 판정을 SQL 쪽에서 `updated_at < NOW() - INTERVAL '30 minutes'` 조건으로 걸 것이므로, 구현 시 폴링 쿼리가 stale이면 그 자리에서 failed UPDATE 후 failed를 반환하는지 확인한다. FakeCursor로 정확히 재현하기 어려우면 이 케이스는 통합(수동) 검증으로 이관하고 단위는 "done이면 result 반환"만 검증한다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest test_async_consult_unit.py::test_poll_stale_processing_becomes_failed -v`
Expected: FAIL — `api_ai_consult_job` 미정의.

- [ ] **Step 3: 구현**

```python
@app.get("/api/ai/consult/job/{job_id}")
def api_ai_consult_job(job_id: str, current_user: dict = Depends(_get_current_user)):
    """job 상태 폴링 — done이면 result 반환. processing 30분 초과는 failed 처리."""
    bn = current_user["bn"]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT job_id, status, result, error, business_number,
                              (updated_at < NOW() - INTERVAL '30 minutes') AS stale
                       FROM consult_jobs WHERE job_id = %s""", (job_id,))
        row = cur.fetchone()
        if not row or row["business_number"] != bn:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
        status = row["status"]
        if status == "processing" and row.get("stale"):
            cur.execute("UPDATE consult_jobs SET status = 'failed', error = 'timeout', updated_at = CURRENT_TIMESTAMP WHERE job_id = %s", (job_id,))
            conn.commit()
            status = "failed"
        if status == "done":
            res = row["result"] or {}
            if isinstance(res, str):
                res = json.loads(res)
            return {"status": "done", **res}
        if status == "failed":
            return {"status": "failed", "reply": "분석 중 오류가 발생했어요. 다시 시도해 주세요."}
        return {"status": "processing"}
    finally:
        conn.close()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest test_async_consult_unit.py -v`
Expected: PASS (또는 stale 케이스는 수동 검증으로 이관 시 나머지 통과)

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/test_async_consult_unit.py
git commit -m "feat(consult): job 폴링 엔드포인트 + lazy stale 정리"
```

---

## Task 5: `notify` 엔드포인트 (닫기 vs 완료 경쟁 처리)

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/test_async_consult_unit.py` (추가)

- [ ] **Step 1: 실패하는 테스트 추가 (양방향 경쟁)**

```python
def test_notify_before_done_sets_flag(monkeypatch):
    state = _state(); jid = "jn1"
    state["jobs"][jid] = {"status": "processing", "notify_requested": False, "notified": False}
    class _C(FakeCursor):
        def execute(self, sql, params=None):
            q = " ".join(sql.split())
            if q.startswith("SELECT status, notified, session_id, announcement_id FROM consult_jobs"):
                j = state["jobs"][params[0]]
                self._r = {"status": j["status"], "notified": j["notified"], "session_id": "sid", "announcement_id": 1}
            elif "SET notify_requested = TRUE" in q:
                state["jobs"][params[0]]["notify_requested"] = True; self._r = None
            elif "business_number" in q and "SELECT" in q:
                self._r = {"business_number": "111-11-11111"}
            else:
                self._r = None
    monkeypatch.setattr(main, "get_db_connection",
                        lambda: type("C", (FakeConn,), {"cursor": lambda s: _C(state)})(state))
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    resp = main.api_ai_consult_job_notify(jid, current_user=current_user)
    assert resp["status"] == "processing"
    assert state["jobs"][jid]["notify_requested"] is True


def test_notify_after_done_pushes_now(monkeypatch):
    state = _state(); jid = "jn2"
    state["jobs"][jid] = {"status": "done", "notify_requested": False, "notified": False}
    pushed = {"n": 0}
    import app.services.notification_service as ns
    monkeypatch.setattr(ns.notification_service, "send_transactional_push",
                        lambda *a, **k: pushed.__setitem__("n", pushed["n"] + 1) or 1)
    class _C(FakeCursor):
        def execute(self, sql, params=None):
            q = " ".join(sql.split())
            if q.startswith("SELECT status, notified, session_id, announcement_id FROM consult_jobs"):
                j = state["jobs"][params[0]]
                self._r = {"status": j["status"], "notified": j["notified"], "session_id": "sid", "announcement_id": 1}
            elif "business_number" in q and "SELECT" in q and "consult_jobs" in q:
                self._r = {"business_number": "111-11-11111"}
            elif "SET notified = TRUE" in q:
                state["jobs"][params[0]]["notified"] = True; self._r = None
            else:
                self._r = None
    monkeypatch.setattr(main, "get_db_connection",
                        lambda: type("C", (FakeConn,), {"cursor": lambda s: _C(state)})(state))
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    resp = main.api_ai_consult_job_notify(jid, current_user=current_user)
    assert resp.get("pushed") is True
    assert pushed["n"] == 1
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest test_async_consult_unit.py::test_notify_before_done_sets_flag test_async_consult_unit.py::test_notify_after_done_pushes_now -v`
Expected: FAIL — `api_ai_consult_job_notify` 미정의.

- [ ] **Step 3: 구현**

```python
@app.post("/api/ai/consult/job/{job_id}/notify")
def api_ai_consult_job_notify(job_id: str, current_user: dict = Depends(_get_current_user)):
    """창을 닫고 나갈 때 호출 — 완료 시 푸시받기. 이미 완료면 즉시 발송."""
    bn = current_user["bn"]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT business_number, status, notified, session_id, announcement_id FROM consult_jobs WHERE job_id = %s", (job_id,))
        row = cur.fetchone()
        if not row or row["business_number"] != bn:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
        if row["status"] == "processing":
            cur.execute("UPDATE consult_jobs SET notify_requested = TRUE, updated_at = CURRENT_TIMESTAMP WHERE job_id = %s", (job_id,))
            conn.commit()
            return {"status": "processing"}
        if row["status"] == "done" and not row["notified"]:
            cur.execute("SELECT title FROM announcements WHERE announcement_id = %s", (row["announcement_id"],))
            trow = cur.fetchone()
            title = (dict(trow).get("title") if trow else "공고") or "공고"
            _maybe_send_consult_push(job_id, bn, row["session_id"], row["announcement_id"], title, cur, conn)
            return {"status": "done", "pushed": True}
        return {"status": row["status"]}
    finally:
        conn.close()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest test_async_consult_unit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/test_async_consult_unit.py
git commit -m "feat(consult): notify 엔드포인트 (닫기 vs 완료 경쟁 처리)"
```

---

## Task 6: 인앱 배지 — `pending` 조회 + `seen` 처리

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: 구현 (배지는 조회/갱신뿐 — 단위 테스트는 경량, 수동 검증 위주)**

```python
@app.get("/api/ai/consult/pending")
def api_ai_consult_pending(current_user: dict = Depends(_get_current_user)):
    """완료됐지만 아직 안 본 상담(닫고 나간 건) 목록 — 인앱 배지용."""
    bn = current_user["bn"]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT j.job_id, j.session_id, j.announcement_id, a.title, j.updated_at
            FROM consult_jobs j
            LEFT JOIN announcements a ON a.announcement_id = j.announcement_id
            WHERE j.business_number = %s AND j.status = 'done'
              AND j.notify_requested = TRUE AND j.seen = FALSE
              AND j.updated_at > NOW() - INTERVAL '7 days'
            ORDER BY j.updated_at DESC
            LIMIT 20
        """, (bn,))
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["updated_at"] = str(r.get("updated_at"))
        return {"status": "SUCCESS", "count": len(rows), "items": rows}
    finally:
        conn.close()


@app.post("/api/ai/consult/job/{job_id}/seen")
def api_ai_consult_job_seen(job_id: str, current_user: dict = Depends(_get_current_user)):
    """배지 해제 — 사용자가 결과를 확인함."""
    bn = current_user["bn"]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE consult_jobs SET seen = TRUE, updated_at = CURRENT_TIMESTAMP WHERE job_id = %s AND business_number = %s", (job_id, bn))
        conn.commit()
        return {"status": "SUCCESS"}
    finally:
        conn.close()
```

- [ ] **Step 2: import 무오류 확인**

Run: `cd backend && python -c "import app.main"`
Expected: 성공.

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(consult): 인앱 배지용 pending 조회 + seen 처리 엔드포인트"
```

---

## Task 7: 프론트 — 제출 + 폴링

**Files:**
- Modify: `frontend/src/components/AiConsultModal.tsx:341-433` (`sendToAI`)

- [ ] **Step 1: `sendToAI`를 제출+폴링으로 교체**

`fetch('/api/ai/consult')` 이후 응답 처리 부분을 아래로 교체. 402/`!res.ok` 분기는 유지하되, 성공 응답이 `{status:"PROCESSING", job_id, session_id}`이면 폴링 시작.

```typescript
      const data = await res.json();
      // 신규: 제출 응답 → 폴링
      if (data.status === "PROCESSING" && data.job_id) {
        if (data.session_id && announcement) {
          sessionIdRef.current = data.session_id;
          setSessionId(data.session_id);
          localStorage.setItem(`consult_session_${announcement.announcement_id}`,
            JSON.stringify({ id: data.session_id, ts: Date.now() }));
        }
        jobIdRef.current = data.job_id;
        await pollJob(data.job_id, chatHistory, controller);
        return;
      }
      // (레거시 즉시 응답 경로는 제거됨)
```

`pollJob` 함수 추가(컴포넌트 내부, `sendToAI` 위):

```typescript
  const pollJob = useCallback(async (jobId: string, chatHistory: ChatMessage[], controller: AbortController) => {
    const token = localStorage.getItem("auth_token");
    const started = Date.now();
    const MAX = 180000; // 3분
    while (Date.now() - started < MAX) {
      if (controller.signal.aborted) return;
      await new Promise((r) => setTimeout(r, 2000));
      let jr: Response;
      try {
        jr = await fetch(`${API}/api/ai/consult/job/${jobId}`, {
          headers: { Authorization: `Bearer ${token}` }, signal: controller.signal,
        });
      } catch (e) {
        if (e instanceof Error && e.name === "AbortError") return;
        continue;
      }
      if (!jr.ok) continue;
      const jd = await jr.json();
      if (jd.status === "processing") continue;
      if (jd.status === "failed") {
        toast(jd.reply || "분석 중 오류가 발생했어요. 다시 시도해 주세요.", "error");
        setLoading(false);
        return;
      }
      // done
      if (jd.origin_url && !originUrl) setOriginUrl(jd.origin_url);
      const aiMsg: ChatMessage = {
        role: "assistant",
        text: jd.reply || "분석 중 오류가 발생했습니다.",
        choices: jd.choices || [],
        done: jd.done || false,
      };
      setMessages([...chatHistory, aiMsg]);
      if (jd.consult_log_id) setConsultLogId(jd.consult_log_id);
      jobIdRef.current = null;
      setLoading(false);
      return;
    }
    toast("분석이 지연되고 있어요. 잠시 후 상담이력에서 확인해 주세요.", "info");
    setLoading(false);
  }, [originUrl, toast]);
```

`jobIdRef` 선언 추가(다른 ref들 옆): `const jobIdRef = useRef<string | null>(null);`

- [ ] **Step 2: 로컬 타입체크/빌드**

Run: `cd frontend && npx tsc --noEmit`
Expected: 타입 에러 없음.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AiConsultModal.tsx
git commit -m "feat(consult-fe): 상담 제출+폴링 방식으로 전환"
```

---

## Task 8: 프론트 — 처리 중 닫기 핸들러 + 푸시 권한 유도

**Files:**
- Modify: `frontend/src/components/AiConsultModal.tsx` (닫기 핸들러 `onClose`/모달 close 로직)

- [ ] **Step 1: 닫기 시 처리 중이면 notify + 권한 유도**

모달 닫기 함수(현행 `onClose` 호출 지점)를 감싸는 `handleClose` 추가:

```typescript
  const requestPushAndNotify = useCallback(async (jobId: string) => {
    const token = localStorage.getItem("auth_token");
    const callNotify = async () => {
      try {
        await fetch(`${API}/api/ai/consult/job/${jobId}/notify`, {
          method: "POST", headers: { Authorization: `Bearer ${token}` },
        });
      } catch { /* 무시 — 인앱 배지 폴백 */ }
    };
    if (typeof Notification === "undefined") { await callNotify(); return; }
    if (Notification.permission === "granted") {
      await ensurePushSubscribed();  // 기존 구독 헬퍼(NotificationModal/layout에서 export)
      await callNotify();
    } else if (Notification.permission === "default") {
      const perm = await Notification.requestPermission();
      if (perm === "granted") { await ensurePushSubscribed(); }
      await callNotify();  // 거부해도 notify는 세팅(배지 폴백)
    } else {
      await callNotify();  // denied → 배지 폴백
    }
  }, []);

  const handleClose = useCallback(async () => {
    if (loading && jobIdRef.current) {
      await requestPushAndNotify(jobIdRef.current);
    }
    if (abortControllerRef.current) abortControllerRef.current.abort();
    onClose?.();
  }, [loading, requestPushAndNotify, onClose]);
```

모달의 닫기 버튼/배경 클릭이 `onClose` 대신 `handleClose`를 부르도록 교체.

> `ensurePushSubscribed`: 기존 `NotificationModal.tsx`/`layout.tsx`의 구독 로직을 `frontend/src/lib/push.ts`로 추출해 재사용. 이미 공용 함수가 있으면 그것을 import. 없으면 이 태스크에서 추출(구독 등록 → `POST /api/push/subscribe`).

- [ ] **Step 2: 타입체크**

Run: `cd frontend && npx tsc --noEmit`
Expected: 통과.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AiConsultModal.tsx frontend/src/lib/push.ts
git commit -m "feat(consult-fe): 처리 중 닫기 시 notify + 푸시 권한 유도"
```

---

## Task 9: 프론트 — 딥링크(`?consult=`) + 인앱 배지

**Files:**
- Modify: `frontend/src/app/HomeClient.tsx`

- [ ] **Step 1: 딥링크 감지 → 해당 공고 상담 모달 오픈**

`HomeClient` 마운트 시 URL 파라미터 감지:

```typescript
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const consultSid = sp.get("consult");
    const aid = sp.get("aid");
    if (consultSid && aid) {
      // 해당 공고를 열고 AiConsultModal을 세션 복원 상태로 오픈
      openConsultForAnnouncement(Number(aid), consultSid);
      // job seen 처리(있으면) — pending 목록에서 job_id 매칭 후 seen 호출
      markConsultSeenBySession(consultSid);
      // URL 정리
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);
```

`openConsultForAnnouncement`: 공고 상세를 fetch(`/api/announcements/{aid}` 또는 기존 방식)해 `AiConsultModal`을 열고, `sessionIdRef`를 `consultSid`로 세팅 → 기존 세션 복원 경로(`GET /api/ai/consult/session/{sid}`, AiConsultModal이 이미 보유)가 대화를 불러온다.

- [ ] **Step 2: 인앱 배지 — pending 조회 + 표시**

앱 로드 시:

```typescript
  const [pendingConsults, setPendingConsults] = useState<{count:number; items:any[]}>({count:0, items:[]});
  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) return;
    fetch(`${API}/api/ai/consult/pending`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d) setPendingConsults({ count: d.count, items: d.items }); })
      .catch(() => {});
  }, []);
```

상단 종/상담이력 진입점에 `pendingConsults.count > 0`이면 뱃지 노출. 클릭 시 첫 항목의 `session_id`+`announcement_id`로 `openConsultForAnnouncement` 호출 후 `POST /job/{job_id}/seen`.

> 배지의 정확한 위치는 현재 헤더 레이아웃(종 아이콘 유무)에 맞춰 확정. 종이 없으면 상담이력 탭 라벨에 카운트.

- [ ] **Step 3: 타입체크/빌드**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: 빌드 성공.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/HomeClient.tsx
git commit -m "feat(consult-fe): 완료 상담 딥링크 오픈 + 인앱 배지"
```

---

## Task 10: 수동/통합 검증

**Files:** 없음(검증만)

- [ ] **Step 1: 로컬 백엔드 단위 테스트 전체 통과**

Run: `cd backend && python -m pytest test_async_consult_unit.py test_transactional_push_unit.py -v`
Expected: 전부 PASS.

- [ ] **Step 2: 기존 크레딧 회귀 테스트 통과**

Run: `cd backend && python -m pytest test_credit_consult_unit.py test_credit_general_consult_unit.py -v`
Expected: 기존 테스트 PASS(리팩터가 기존 과금 규칙을 깨지 않았는지).

- [ ] **Step 3: 배포 후 라이브 시나리오 검증(마스터 계정 master@govmatch.kr)**

1. 공고 상담 시작 → "분석 중" 표시 → 결과 렌더(폴링 동작).
2. 상담 시작 직후 창 닫기 → 권한 허용 → 완료 시 푸시 도착 → 탭 → 해당 상담 복원.
3. 권한 거부 상태로 닫기 → 재방문 시 인앱 배지 노출 → 클릭 → 복원 → 배지 사라짐.
4. 야간(KST 18시 이후)에도 푸시 도착(시간대 게이트 없음 확인).
5. 후속 질문(같은 세션)은 무차감·푸시 없음(열어둔 채 응답).

> 배포: 프론트+백엔드 동시(`/api/ai/consult` 계약 변경). 로컬 확인 후 `feature/async-consult-push` → main ff-merge → push origin main → Vercel/Railway 자동 배포.

---

## Self-Review 메모

- **스펙 커버리지**: ①데이터모델=Task1, ②제출/워커=Task3, ③폴링=Task4, notify=Task5, ④푸시=Task2, ⑤프론트=Task7-9, ⑥안전장치(stale=Task4, 경쟁=Task5, 배지=Task6/9), ⑦테스트=각 Task+Task10. 전부 매핑됨.
- **타입 일관성**: 워커 `_run_consult_job(job_id, req, current_user, session_id, is_new_session)` / 푸시 `_maybe_send_consult_push(job_id, bn, session_id, announcement_id, title, cur, conn)` / 엔드포인트 `api_ai_consult_job`·`api_ai_consult_job_notify`·`api_ai_consult_pending`·`api_ai_consult_job_seen` — 태스크 간 시그니처 일치.
- **주의(구현자)**: FakeCursor 기반 단위 테스트는 실제 SQL 문자열과 매칭을 맞춰야 한다. 매칭이 어긋나면 테스트를 실제 쿼리에 맞춰 조정하거나 해당 케이스를 Task10 수동 검증으로 이관(정직하게 표기).
- **범위 밖**: `pro_consult`·자금상담 비동기화, 배지 정확한 위치 확정(레이아웃 의존).
