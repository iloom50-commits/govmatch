# 메일 신호 브리지 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대표 Gmail의 인프라 알림(railway/vercel/supabase)을 Apps Script로 백엔드에 수집해, AI COO 일일 보고서에 '인프라 상태' 섹션으로 통합한다.

**Architecture:** Apps Script(구글 계정 내, 1일 1회)가 인프라 알림을 `POST /api/internal/mail-signal`로 넘김 → `mail_signals` 저장(멱등) → supervisor 신규 스텝 `collect_mail_signals`가 **규칙 기반**으로 진단·조치힌트 산출 → reporter가 섹션 렌더. 전부 ADD-only·읽기전용.

**Tech Stack:** FastAPI(main.py), psycopg2(RealDictCursor), 기존 orchestrator 패턴, Google Apps Script(GmailApp).

> **스펙 대비 변경(핸드오프에서 확정)**: 스펙 §4.4의 "LLM 분석"을 **규칙 기반 진단**으로 단순화. 근거: 기존 COO 수집기(coverage/quality)가 전부 규칙 기반, 인프라 알림 저빈도 → LLM 불필요(비용 0·결정적).

---

## 파일 구조

- Create `backend/app/services/orchestrator/mail_signal_collector.py` — 분류(순수)·저장(멱등)·수집분석. 단일 책임: 메일 신호 도메인.
- Create `backend/test_mail_signal_unit.py` — 위 모듈 + 검증기 + 리포터 렌더 단위테스트(FakeCursor).
- Modify `backend/app/main.py` — ① init_database에 `mail_signals` 테이블(`_safe_exec`) ② `POST /api/internal/mail-signal` 라우트(얇은 래퍼).
- Modify `backend/app/services/orchestrator/supervisor.py` — 신규 스텝: `collect_mail_signals` 호출 → results에 담고 reporter로 전달.
- Modify `backend/app/services/orchestrator/reporter.py` — '🖥 인프라 상태' 섹션(텍스트·HTML) 렌더.
- Create `docs/ops/govmatch-mail-bridge.gs` — Apps Script(대표 설치용, 자동테스트 없음).

---

## Task 1: 분류 로직 (순수 함수)

**Files:**
- Create: `backend/app/services/orchestrator/mail_signal_collector.py`
- Test: `backend/test_mail_signal_unit.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/test_mail_signal_unit.py
# -*- coding: utf-8 -*-
"""메일 신호 브리지 — 분류/저장/수집/렌더 단위 테스트. 실행: cd backend && python test_mail_signal_unit.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass
from app.services.orchestrator.mail_signal_collector import (
    classify_service, estimate_severity,
)

def test_classify_service():
    assert classify_service("noreply@railway.app") == "railway"
    assert classify_service("alerts@vercel.com") == "vercel"
    assert classify_service("no-reply@supabase.io") == "supabase"
    assert classify_service("team@supabase.com") == "supabase"
    assert classify_service("someone@example.com") == "other"

def test_estimate_severity():
    assert estimate_severity("Deployment failed", "build error") == "high"
    assert estimate_severity("Your project", "You have exceeded your quota") == "high"
    assert estimate_severity("Weekly summary", "all good") == "info"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python test_mail_signal_unit.py`
Expected: FAIL — `ModuleNotFoundError: mail_signal_collector`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/orchestrator/mail_signal_collector.py
"""메일 신호(인프라 알림) 분류·저장·수집분석 — AI COO 인프라 상태 섹션용.

Apps Script가 넘긴 알림을 mail_signals에 저장(멱등)하고, 일일 supervisor가
규칙 기반으로 진단·조치힌트를 산출. LLM·Gmail 의존 없음(순수 규칙).
"""
from __future__ import annotations
import re
from typing import Dict, Any, List

_SERVICE_DOMAINS = {
    "railway": ("railway.app", "railway.com"),
    "vercel": ("vercel.com",),
    "supabase": ("supabase.io", "supabase.com"),
}
_HIGH_KW = re.compile(
    r"fail|error|outage|past\s*due|billing|exceeded|down|payment|suspend|limit\s*reached",
    re.IGNORECASE,
)
# 서비스별 조치 힌트(규칙 기반). 실측 운영지식 반영.
_ACTION = {
    "railway": "Railway 대시보드 배포 로그 확인 · 최근 커밋 롤백 검토(백엔드 자동배포 정상)",
    "vercel": "Vercel 빌드 로그 확인 · 자동배포 정체 이력 있음 → 필요시 CLI 수동배포",
    "supabase": "Supabase 커넥션/egress/과금 확인 · 커넥션풀 점검",
    "other": "발신 서비스·내용 직접 확인 필요",
}

def classify_service(sender: str) -> str:
    s = (sender or "").lower()
    for svc, domains in _SERVICE_DOMAINS.items():
        if any(d in s for d in domains):
            return svc
    return "other"

def estimate_severity(subject: str, snippet: str) -> str:
    text = f"{subject or ''} {snippet or ''}"
    return "high" if _HIGH_KW.search(text) else "info"

def action_hint(service: str) -> str:
    return _ACTION.get(service, _ACTION["other"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python test_mail_signal_unit.py`
Expected: PASS (test_classify_service, test_estimate_severity)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/orchestrator/mail_signal_collector.py backend/test_mail_signal_unit.py
git commit -m "feat(coo): 메일 신호 분류 로직(서비스·심각도) + 테스트"
```

---

## Task 2: 저장 (멱등) + mail_signals 테이블

**Files:**
- Modify: `backend/app/services/orchestrator/mail_signal_collector.py` (add `store_mail_signal`)
- Modify: `backend/app/main.py` (init_database에 테이블)
- Test: `backend/test_mail_signal_unit.py`

- [ ] **Step 1: Write the failing test**

```python
# append to backend/test_mail_signal_unit.py
from app.services.orchestrator.mail_signal_collector import store_mail_signal

class _FakeCur:
    def __init__(self): self.sql = []; self._ret = {"id": 1}
    def execute(self, sql, params=None): self.sql.append((" ".join(sql.split()), params))
    def fetchone(self): return self._ret
class _FakeConn:
    def __init__(self): self.cur = _FakeCur(); self.committed = False
    def cursor(self): return self.cur
    def commit(self): self.committed = True

def test_store_uses_on_conflict_and_classifies():
    conn = _FakeConn()
    ok = store_mail_signal(conn, {
        "msg_id": "abc123", "date": "2026-07-24T09:00:00",
        "from": "noreply@railway.app", "subject": "Deployment failed", "snippet": "build error",
    })
    joined = " | ".join(s for s, _ in conn.cur.sql)
    assert "ON CONFLICT" in joined and "gmail_msg_id" in joined
    # 분류 결과가 params에 포함
    allparams = [p for _, p in conn.cur.sql if p]
    flat = str(allparams)
    assert "railway" in flat and "high" in flat and "abc123" in flat
    assert conn.committed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python test_mail_signal_unit.py`
Expected: FAIL — `ImportError: cannot import name 'store_mail_signal'`

- [ ] **Step 3: Write minimal implementation**

Add to `mail_signal_collector.py`:

```python
def store_mail_signal(db_conn, payload: Dict[str, Any]) -> bool:
    """Apps Script 페이로드를 mail_signals에 저장(멱등). 신규 True / 중복 False."""
    msg_id = (payload.get("msg_id") or "").strip()
    if not msg_id:
        return False
    sender = payload.get("from") or ""
    subject = payload.get("subject") or ""
    snippet = payload.get("snippet") or ""
    service = classify_service(sender)
    severity = estimate_severity(subject, snippet)
    received_at = payload.get("date") or None
    cur = db_conn.cursor()
    cur.execute(
        """INSERT INTO mail_signals
             (gmail_msg_id, received_at, sender, subject, snippet, service, severity, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
           ON CONFLICT (gmail_msg_id) DO NOTHING
           RETURNING id""",
        (msg_id, received_at, sender[:300], subject[:500], snippet[:1000], service, severity),
    )
    row = cur.fetchone()
    db_conn.commit()
    return bool(row)
```

Add table to `main.py` init_database (near other `_safe_exec` schema calls, e.g. after coverage_targets block ~line 685). Use `_safe_exec`:

```python
    _safe_exec("""
        CREATE TABLE IF NOT EXISTS mail_signals (
            id SERIAL PRIMARY KEY,
            gmail_msg_id VARCHAR(200) UNIQUE NOT NULL,
            received_at TIMESTAMP,
            sender VARCHAR(300),
            subject TEXT,
            snippet TEXT,
            service VARCHAR(20),
            severity VARCHAR(10),
            analyzed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """, "mail_signals table")
```

> 확인: `_safe_exec`의 정확한 시그니처는 init_database 내 기존 호출부를 그대로 따를 것(sql, label 순). 직접 `cursor.execute` 금지(async-consult 롤백 사고 교훈).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python test_mail_signal_unit.py`
Expected: PASS. 또한 `python -c "import app.main"` 임포트 무결성 확인.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/orchestrator/mail_signal_collector.py backend/app/main.py backend/test_mail_signal_unit.py
git commit -m "feat(coo): mail_signals 테이블 + 멱등 저장(store_mail_signal)"
```

---

## Task 3: 수신 엔드포인트 검증기 + 라우트

**Files:**
- Modify: `backend/app/services/orchestrator/mail_signal_collector.py` (add `validate_mail_signal`)
- Modify: `backend/app/main.py` (route)
- Test: `backend/test_mail_signal_unit.py`

- [ ] **Step 1: Write the failing test**

```python
# append to backend/test_mail_signal_unit.py
from app.services.orchestrator.mail_signal_collector import validate_mail_signal

def test_validate_secret_and_fields():
    body = {"msg_id":"a","date":"d","from":"f","subject":"s","snippet":"n"}
    # 시크릿 불일치 → 401
    ok, status, _ = validate_mail_signal("wrong", body, expected_secret="right")
    assert ok is False and status == 401
    # 필드 누락 → 400
    ok, status, _ = validate_mail_signal("right", {"date":"d"}, expected_secret="right")
    assert ok is False and status == 400
    # 정상 → 200
    ok, status, _ = validate_mail_signal("right", body, expected_secret="right")
    assert ok is True and status == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python test_mail_signal_unit.py`
Expected: FAIL — `ImportError: validate_mail_signal`

- [ ] **Step 3: Write minimal implementation**

Add to `mail_signal_collector.py`:

```python
def validate_mail_signal(secret_header, body, expected_secret):
    """(ok, http_status, error). 시크릿·필수필드 검증."""
    if not expected_secret or secret_header != expected_secret:
        return (False, 401, "invalid secret")
    if not isinstance(body, dict) or not (body.get("msg_id") and body.get("from")):
        return (False, 400, "missing required fields")
    return (True, 200, None)
```

Add route to `main.py` (near other 라우트 정의부, 예: 다른 `@app.post("/api/internal/...")` 근처. 없으면 관리자 라우트 인접):

```python
from fastapi import Request
from app.services.orchestrator.mail_signal_collector import validate_mail_signal, store_mail_signal

@app.post("/api/internal/mail-signal")
async def api_mail_signal(request: Request):
    secret = request.headers.get("X-Bridge-Secret")
    body = await request.json()
    ok, status, err = validate_mail_signal(secret, body, os.getenv("MAIL_BRIDGE_SECRET", ""))
    if not ok:
        return JSONResponse(status_code=status, content={"error": err})
    conn = _get_db_connection()  # 기존 헬퍼 사용(main.py의 DB 연결 헬퍼명에 맞출 것)
    try:
        created = store_mail_signal(conn, body)
    finally:
        conn.close()
    return {"stored": bool(created)}
```

> 확인: `_get_db_connection`·`JSONResponse` import는 main.py 기존 것을 재사용(이름이 다르면 파일 내 실제 헬퍼로 교체). psycopg2 연결은 RealDictCursor 가정.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python test_mail_signal_unit.py`
Expected: PASS. `python -c "import app.main"` 통과.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/orchestrator/mail_signal_collector.py backend/app/main.py backend/test_mail_signal_unit.py
git commit -m "feat(coo): /api/internal/mail-signal 수신 엔드포인트(시크릿·필드 검증)"
```

---

## Task 4: 수집·진단 (collect_mail_signals, 규칙 기반)

**Files:**
- Modify: `backend/app/services/orchestrator/mail_signal_collector.py`
- Test: `backend/test_mail_signal_unit.py`

- [ ] **Step 1: Write the failing test**

```python
# append to backend/test_mail_signal_unit.py
from app.services.orchestrator.mail_signal_collector import collect_mail_signals

class _FakeCurRows:
    def __init__(self, rows): self.rows = rows; self.updated = []
    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.upper().startswith("SELECT"): self._mode = "sel"
        else: self.updated.append((s, params))
    def fetchall(self): return self.rows
class _FakeConnRows:
    def __init__(self, rows): self.cur = _FakeCurRows(rows); self.committed=False
    def cursor(self): return self.cur
    def commit(self): self.committed=True

def test_collect_zero_returns_ok_no_analysis():
    out = collect_mail_signals(_FakeConnRows([]))
    assert out["count"] == 0 and out["high"] == []

def test_collect_surfaces_high_and_marks_analyzed():
    rows = [
        {"id":1,"service":"railway","severity":"high","subject":"Deployment failed","snippet":"x","received_at":None},
        {"id":2,"service":"vercel","severity":"info","subject":"summary","snippet":"y","received_at":None},
    ]
    conn = _FakeConnRows(rows)
    out = collect_mail_signals(conn)
    assert out["count"] == 2
    assert len(out["high"]) == 1 and out["high"][0]["service"] == "railway"
    assert "action" in out["high"][0]
    assert out["by_service"]["railway"] == 1 and out["by_service"]["vercel"] == 1
    # analyzed_at 마킹 UPDATE 발생
    assert any("analyzed_at" in s for s, _ in conn.cur.updated)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python test_mail_signal_unit.py`
Expected: FAIL — `ImportError: collect_mail_signals`

- [ ] **Step 3: Write minimal implementation**

Add to `mail_signal_collector.py`:

```python
def collect_mail_signals(db_conn) -> Dict[str, Any]:
    """최근 24h 미분석 신호 → 규칙 기반 진단. {count, high[], by_service{}, }.
    0건이면 분석 스킵. 처리분은 analyzed_at 마킹."""
    cur = db_conn.cursor()
    cur.execute(
        """SELECT id, service, severity, subject, snippet, received_at
           FROM mail_signals
           WHERE analyzed_at IS NULL
             AND created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
           ORDER BY severity DESC, id DESC"""
    )
    rows = cur.fetchall() or []
    if not rows:
        return {"count": 0, "high": [], "by_service": {}}

    high: List[Dict[str, Any]] = []
    by_service: Dict[str, int] = {}
    ids: List[int] = []
    for r in rows:
        rid = r["id"] if isinstance(r, dict) else r[0]
        svc = (r["service"] if isinstance(r, dict) else r[1]) or "other"
        sev = (r["severity"] if isinstance(r, dict) else r[2]) or "info"
        subj = (r["subject"] if isinstance(r, dict) else r[3]) or ""
        ids.append(rid)
        by_service[svc] = by_service.get(svc, 0) + 1
        if sev == "high":
            high.append({"service": svc, "subject": subj[:120], "action": action_hint(svc)})

    if ids:
        cur.execute(
            "UPDATE mail_signals SET analyzed_at = CURRENT_TIMESTAMP WHERE id = ANY(%s)",
            (ids,),
        )
        db_conn.commit()
    return {"count": len(rows), "high": high, "by_service": by_service}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python test_mail_signal_unit.py`
Expected: PASS (전체 테스트).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/orchestrator/mail_signal_collector.py backend/test_mail_signal_unit.py
git commit -m "feat(coo): collect_mail_signals 규칙기반 진단(24h·high 노출·마킹)"
```

---

## Task 5: supervisor 배선 + reporter 섹션

**Files:**
- Modify: `backend/app/services/orchestrator/supervisor.py`
- Modify: `backend/app/services/orchestrator/reporter.py`
- Test: `backend/test_mail_signal_unit.py`

- [ ] **Step 1: Write the failing test (reporter 렌더)**

```python
# append to backend/test_mail_signal_unit.py
from app.services.orchestrator.reporter import render_mail_signal_section

def test_reporter_section_empty():
    txt, html = render_mail_signal_section({"count":0,"high":[],"by_service":{}})
    assert "이상 없음" in txt and "이상 없음" in html

def test_reporter_section_high():
    data = {"count":2,"high":[{"service":"railway","subject":"Deployment failed","action":"로그 확인"}],
            "by_service":{"railway":1,"vercel":1}}
    txt, html = render_mail_signal_section(data)
    assert "railway" in txt and "Deployment failed" in txt and "로그 확인" in txt
    assert "railway" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python test_mail_signal_unit.py`
Expected: FAIL — `ImportError: render_mail_signal_section`

- [ ] **Step 3: Write minimal implementation**

Add to `reporter.py`:

```python
def render_mail_signal_section(data: dict) -> tuple:
    """(text, html) — '🖥 인프라 상태' 섹션. data=collect_mail_signals 반환."""
    count = (data or {}).get("count", 0)
    high = (data or {}).get("high", [])
    if not count:
        t = "🖥 인프라 상태 — 이상 없음"
        h = '<h3>🖥 인프라 상태</h3><p>이상 없음</p>'
        return t, h
    by = (data or {}).get("by_service", {})
    by_str = ", ".join(f"{k} {v}" for k, v in by.items())
    lines = [f"🖥 인프라 상태 — 알림 {count}건 ({by_str})"]
    for it in high:
        lines.append(f"  ⚠️ [{it['service']}] {it['subject']} → {it['action']}")
    t = "\n".join(lines)
    h_items = "".join(
        f"<li>⚠️ <b>[{it['service']}]</b> {it['subject']} → {it['action']}</li>" for it in high
    )
    h = (f"<h3>🖥 인프라 상태</h3><p>알림 {count}건 ({by_str})</p>"
         f"<ul>{h_items}</ul>" if high else
         f"<h3>🖥 인프라 상태</h3><p>알림 {count}건 ({by_str}) — high 없음</p>")
    return t, h
```

Wire into `supervisor.py` (기존 스텝 흐름, 예: Step 3 학습 감시 뒤에 삽입). 기존 try/except 격리 패턴 준수:

```python
        # ── N. 메일 신호(인프라 알림) 수집·진단 ──
        print("[AI COO] Step: 인프라 메일 신호 수집 중...")
        try:
            from .mail_signal_collector import collect_mail_signals
            mail_sig = collect_mail_signals(db_conn)
            results["mail_signals"] = mail_sig
            print(f"  → 인프라 알림 {mail_sig.get('count',0)}건 (high {len(mail_sig.get('high',[]))})")
        except Exception as e:
            results["mail_signals"] = {"error": str(e)}
            print(f"  → 메일 신호 수집 오류: {e}")
```

그리고 reporter가 보고서 조립 시 `render_mail_signal_section(results.get("mail_signals", {}))`를 호출해 텍스트·HTML에 삽입(기존 섹션 조립부 패턴에 맞춰 배치).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python test_mail_signal_unit.py`
Expected: PASS 전체. `python -c "import app.services.orchestrator.supervisor, app.services.orchestrator.reporter"` 통과.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/orchestrator/supervisor.py backend/app/services/orchestrator/reporter.py backend/test_mail_signal_unit.py
git commit -m "feat(coo): 인프라 상태 섹션 렌더 + supervisor 배선"
```

---

## Task 6: Apps Script 브리지 파일

**Files:**
- Create: `docs/ops/govmatch-mail-bridge.gs`

- [ ] **Step 1: 스크립트 작성** (자동테스트 없음 — 구글 환경)

```javascript
// govmatch-mail-bridge.gs — 대표 구글계정에 설치. 인프라 알림을 지원금AI 백엔드로 전송.
// 설치: script.google.com 새 프로젝트에 붙여넣기 → 스크립트 속성 BACKEND_URL, BRIDGE_SECRET 설정
//       → 트리거: scanInfraAlerts 시간기반 1일 1회(오전 8~9시).
var LABEL = 'govmatch-processed';
var SENDERS = 'from:(railway.app OR vercel.com OR supabase.io OR supabase.com)';

function scanInfraAlerts() {
  var props = PropertiesService.getScriptProperties();
  var url = props.getProperty('BACKEND_URL');
  var secret = props.getProperty('BRIDGE_SECRET');
  var label = GmailApp.getUserLabelByName(LABEL) || GmailApp.createLabel(LABEL);
  var threads = GmailApp.search(SENDERS + ' newer_than:1d -label:' + LABEL, 0, 20);
  threads.forEach(function (th) {
    var msgs = th.getMessages();
    var allOk = true;
    msgs.forEach(function (m) {
      var payload = {
        msg_id: m.getId(),
        date: m.getDate().toISOString(),
        from: m.getFrom(),
        subject: m.getSubject(),
        snippet: m.getPlainBody().slice(0, 300),
      };
      if (!postWithRetry(url, secret, payload)) allOk = false;
    });
    if (allOk) th.addLabel(label); // 전송 성공한 스레드만 처리표시
  });
}

function postWithRetry(url, secret, payload) {
  for (var i = 0; i < 3; i++) { // 동일 실행 내 2~3회 재시도(일시 실패 흡수)
    try {
      var res = UrlFetchApp.fetch(url, {
        method: 'post', contentType: 'application/json',
        headers: { 'X-Bridge-Secret': secret },
        payload: JSON.stringify(payload), muteHttpExceptions: true,
      });
      if (res.getResponseCode() >= 200 && res.getResponseCode() < 300) return true;
    } catch (e) {}
    Utilities.sleep(1500);
  }
  return false;
}
```

- [ ] **Step 2: Commit**

```bash
git add docs/ops/govmatch-mail-bridge.gs
git commit -m "docs(ops): Apps Script 메일 브리지 스크립트(대표 설치용)"
```

---

## Task 7: 배포 + 라이브 스모크 (대표 협업)

- [ ] **Step 1:** 백엔드 배포 — `git push origin main` → Railway 자동배포. (테이블은 init_database가 기동 시 생성)
- [ ] **Step 2:** Railway env `MAIL_BRIDGE_SECRET` 설정(임의 강한 문자열) — 대표.
- [ ] **Step 3:** 대표: `docs/ops/govmatch-mail-bridge.gs`를 script.google.com에 설치, 스크립트 속성(BACKEND_URL=`https://govmatch-production.up.railway.app/api/internal/mail-signal`, BRIDGE_SECRET=위 값) 설정, 트리거 1일 1회.
- [ ] **Step 4:** 라이브 스모크: Apps Script `scanInfraAlerts` 수동 1회 실행 → 프로덕션 `mail_signals`에 행 생기는지 확인(스크래치 SELECT) → 다음/수동 COO 실행 보고서에 '🖥 인프라 상태' 섹션 노출 확인.

---

## Self-Review (작성자 점검 결과)

- **Spec coverage**: §4.1 Apps Script→Task 6, §4.2 엔드포인트→Task 3, §4.3 테이블→Task 2, §4.4 collector→Task 4, §4.5 reporter→Task 5, §5 보안(시크릿)→Task 3, 멱등→Task 2, §6 테스트→각 Task, §7 배포→Task 7. 전 항목 커버.
- **Placeholder scan**: "기존 헬퍼명에 맞출 것" 3곳은 플레이스홀더가 아니라 **실제 코드베이스 헬퍼 재사용 지시**(main.py DB연결 헬퍼·JSONResponse·_safe_exec 시그니처) — 구현자가 파일 내 실물로 확인. 코드 본문은 전부 구체적.
- **Type consistency**: `store_mail_signal(conn, payload)`·`collect_mail_signals(conn)→{count,high,by_service}`·`render_mail_signal_section(data)→(text,html)`·`validate_mail_signal(secret,body,expected_secret)→(ok,status,err)` — 전 Task에서 시그니처 일관.
- **변경점**: 스펙의 LLM 분석 → 규칙 기반(핸드오프에서 확정 + 스펙 동기화 필요).
