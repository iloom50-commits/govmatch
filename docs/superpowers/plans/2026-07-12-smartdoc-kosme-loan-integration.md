# SmartDoc 중진공 정책자금 융자신청서 연동 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GovMatch 공고 카드의 "AI 신청서 작성" 버튼을 중진공 정책자금 융자 공고 15건에 노출하고, 클릭 시 이미 구축된 SmartDoc 핸드오프(SSO+기업프로필+공고)로 연결해 실사용 가능하게 한다.

**Architecture:** 배관(핸드오프 SSO·entitlement·client-profile·for-smartdoc)은 GovMatch·SmartDoc 양쪽에 이미 구현됨. 남은 것은 (Phase A, 이 저장소) 게이팅+버튼연결+entitlement 통과, (Phase B, SmartDoc 저장소) 크레딧→건별 결제 전환+통일 브랜딩. 결제는 SmartDoc이 전담(GovMatch는 유입만), 첫 건 무료로 혼란 최소화.

**Tech Stack:** Next.js(React)/Vercel 프론트, FastAPI/psycopg2/Railway 백엔드, 공유 JWT_SECRET 핸드오프. SmartDoc = 별도 FastAPI+React(SaaS 배포).

---

## Scope Note (2개 하위 프로젝트)

이 계획은 **Phase A(GovMatch, 이 저장소)** 를 실행 가능한 완결 단위로 상세화한다. **Phase B(SmartDoc 저장소의 건별 결제 전환·브랜딩)** 는 별도 코드베이스라, 이 문서에선 범위·인터페이스만 확정하고 **SmartDoc 코드 탐색 후 별도 계획서**로 상세화한다. Phase A만 배포해도 SmartDoc의 기존 증정 크레딧(첫 건 무료)으로 **작동하는 v1**이 된다. `NEXT_PUBLIC_SMARTDOC_READY` 플래그로 노출 시점을 통제한다.

## File Structure

- Create: `frontend/src/lib/smartdocGating.ts` — 중진공 융자 공고 판별 순수함수(카드 게이팅 단일 소스)
- Modify: `frontend/src/components/ResultCard.tsx:482` — `hasForm`에 중진공 융자 조건 합류
- Modify: `frontend/src/components/ResultCard.tsx:499-513` — formBtn onClick을 placeholder→핸드오프 리다이렉트로 교체
- Modify: `backend/app/main.py:15764-15784` — `/api/smartdoc/entitlement` 통과 정책(로그인 사용자 has_access=true)
- Test: `backend/test_smartdoc_entitlement_unit.py` — entitlement 통과 단위 테스트

---

## Phase A — GovMatch (이 저장소)

### Task 1: 중진공 융자 게이팅 순수함수

**Files:**
- Create: `frontend/src/lib/smartdocGating.ts`

판별 조건(검증 완료, 활성 15건 정확히 매칭): `(부서~중진공 OR 제목="중소기업 정책자금") AND (제목에 자금 OR 융자) AND NOT 소상공인`.

- [ ] **Step 1: 함수 작성**

```typescript
// frontend/src/lib/smartdocGating.ts
// 중진공(중소벤처기업진흥공단) 정책자금 융자 공고 판별 — 'AI 신청서 작성' 버튼 게이팅.
// SmartDoc 신청서 자동작성이 중진공 융자신청서 전용이므로 이 집합에만 노출한다.
export function isKosmePolicyLoan(a: { title?: string | null; department?: string | null }): boolean {
  const title = (a.title || "");
  const dept = (a.department || "");
  if (title.includes("소상공인")) return false;                 // 소진공 정책자금은 별개(양식 다름)
  const isKosme = dept.includes("중소벤처기업진흥공단")
    || dept.includes("중소기업진흥공단")
    || title.includes("중소기업 정책자금");
  const isLoan = title.includes("자금") || title.includes("융자");
  return isKosme && isLoan;
}
```

- [ ] **Step 2: tsx 단언으로 검증(프론트 유닛 러너 없음)**

Run:
```bash
cd frontend && npx tsx -e "import {isKosmePolicyLoan as f} from './src/lib/smartdocGating.ts'; \
const T=(o:any,e:boolean)=>{if(f(o)!==e)throw new Error(JSON.stringify(o)+' expected '+e)}; \
T({title:'신성장기반자금(융자)',department:'중소벤처기업진흥공단'},true); \
T({title:'2026년 중소기업 정책자금 융자계획 변경 공고',department:'기타'},true); \
T({title:'진로제시컨설팅',department:'중소벤처기업진흥공단'},false); \
T({title:'2026년 3분기 일반경영안정자금(대리대출)',department:'소상공인시장진흥공단'},false); \
T({title:'청년 전세자금 대출이자 지원',department:'서울시'},false); \
console.log('OK')"
```
Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/lib/smartdocGating.ts
git commit -m "feat(smartdoc): 중진공 정책자금 융자 공고 판별 게이팅 함수"
```

### Task 2: 카드 버튼 노출 조건에 중진공 융자 합류

**Files:**
- Modify: `frontend/src/components/ResultCard.tsx:482`

- [ ] **Step 1: import 추가 + hasForm 확장**

`ResultCard.tsx` 상단 import 블록에 추가:
```typescript
import { isKosmePolicyLoan } from "@/lib/smartdocGating";
```

482행 교체:
```typescript
// (기존) const hasForm = res.target_type !== "individual" && res.has_application_form;
const hasForm = res.target_type !== "individual"
  && (res.has_application_form || isKosmePolicyLoan(res));
```

- [ ] **Step 2: 빌드 검증**

Run: `cd frontend && npm run build`
Expected: 컴파일 통과(에러 없음)

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/components/ResultCard.tsx
git commit -m "feat(card): 중진공 융자 공고에 'AI 신청서 작성' 버튼 노출(게이팅)"
```

### Task 3: 버튼 클릭 → SmartDoc 핸드오프 리다이렉트

**Files:**
- Modify: `frontend/src/components/ResultCard.tsx:499-513`

현재 formBtn onClick은 `open-smartdoc-modal`(플레이스홀더)를 띄운다. ProPageClient의 검증된 핸드오프 패턴으로 교체하되, `NEXT_PUBLIC_SMARTDOC_READY`가 아니면 안내만 띄운다.

- [ ] **Step 1: onClick 교체**

formBtn의 onClick(503~507행 영역)을 아래로 교체:
```typescript
onClick={async (e) => {
  e.stopPropagation();
  if (isPublic) { onLoginRequired?.(); return; }
  if (isExpired) { onUpgrade?.(); return; }
  if (process.env.NEXT_PUBLIC_SMARTDOC_READY !== "true") {
    toast("AI 신청서 작성은 곧 시작됩니다. 조금만 기다려 주세요!", "info");
    return;
  }
  try {
    const token = localStorage.getItem("auth_token");
    const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/smartdoc/handoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ announcement_id: res.announcement_id }),
    });
    const data = await r.json();
    if (data?.url) window.location.href = data.url;
    else toast("SmartDoc 연결에 실패했습니다.", "error");
  } catch { toast("SmartDoc 연결에 실패했습니다.", "error"); }
}}
```

> 주의: `${process.env.NEXT_PUBLIC_API_URL}` 를 컴포넌트가 이미 쓰는 API 상수로 맞춘다(파일 상단에 API base가 있으면 그걸 사용). `toast`는 이 컴포넌트가 이미 props로 받는 함수(ShareMenu 등에서 사용 중).

- [ ] **Step 2: 빌드 검증**

Run: `cd frontend && npm run build`
Expected: 컴파일 통과

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/components/ResultCard.tsx
git commit -m "feat(card): 'AI 신청서 작성' → SmartDoc 핸드오프 리다이렉트(READY 게이트)"
```

### Task 4: entitlement 통과 정책 (백엔드)

**Files:**
- Modify: `backend/app/main.py:15764-15784`
- Test: `backend/test_smartdoc_entitlement_unit.py`

결제는 SmartDoc이 전담하므로, GovMatch entitlement는 **로그인(핸드오프 토큰 유효) 사용자면 has_access=true**로 통과시킨다. smartdoc_plan 게이트는 제거(향후 PRO 포함 정책이 생기면 재도입).

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/test_smartdoc_entitlement_unit.py
# -*- coding: utf-8 -*-
"""entitlement 통과 정책: 유효 사용자면 has_access=true (결제는 SmartDoc 전담)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_entitlement_passthrough_for_valid_user():
    from app.main import _entitlement_response
    # smartdoc_plan 없어도 통과
    out = _entitlement_response(row={"smartdoc_plan": None, "smartdoc_expires_at": None})
    assert out["has_access"] is True, out
    assert out["billed_by"] == "smartdoc", out
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && PYTHONIOENCODING=utf-8 python test_smartdoc_entitlement_unit.py`
Expected: FAIL — `_entitlement_response` 미존재(ImportError)

- [ ] **Step 3: 순수함수 추출 + 통과 정책 구현**

`backend/app/main.py`에 순수함수 추가(엔드포인트 근처, 15763행 위):
```python
def _entitlement_response(row: dict | None) -> dict:
    """entitlement 응답(순수). 결제는 SmartDoc 전담 → 유효 사용자면 통과.
    row는 users.smartdoc_plan/expires_at(향후 PRO 포함 정책 대비 보존)."""
    return {
        "status": "SUCCESS",
        "has_access": True,
        "billed_by": "smartdoc",          # SmartDoc이 건별 결제 담당(첫 건 무료)
        "plan": (row or {}).get("smartdoc_plan"),
        "remaining": None,
        "expires_at": None,
        "purchase_url": None,
    }
```

엔드포인트(15764~15784) 본문을 교체:
```python
@app.get("/api/smartdoc/entitlement")
def api_smartdoc_entitlement(authorization: Optional[str] = Header(None)):
    """SmartDoc 사용권 — 결제는 SmartDoc 전담. 유효 사용자면 통과."""
    u = _smartdoc_bearer(authorization)  # 토큰 검증(무효면 예외)
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT smartdoc_plan, smartdoc_expires_at FROM users WHERE business_number=%s", (u["bn"],))
        row = cur.fetchone()
    finally:
        conn.close()
    return _entitlement_response(row)
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && PYTHONIOENCODING=utf-8 python test_smartdoc_entitlement_unit.py`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/main.py backend/test_smartdoc_entitlement_unit.py
git commit -m "feat(smartdoc): entitlement 통과 정책(결제 SmartDoc 전담) + 단위테스트"
```

### Task 5: Phase A 통합 검증 + 배포

- [ ] **Step 1: 백엔드 회귀** — Run: `cd backend && PYTHONIOENCODING=utf-8 python test_smartdoc_entitlement_unit.py` → PASS
- [ ] **Step 2: 프론트 빌드** — Run: `cd frontend && npm run build` → 통과
- [ ] **Step 3: push(배포)** — `git push origin main`. `NEXT_PUBLIC_SMARTDOC_READY`는 **미설정 유지**(버튼 노출되나 클릭 시 "곧 시작" 안내 → SmartDoc Phase B 준비 후 true 전환)
- [ ] **Step 4: 라이브 확인** — 중진공 융자 공고 카드(#125757 등)에 "AI 신청서 작성" 버튼 노출 확인. 클릭 시 "곧 시작" 안내 확인

---

## Phase B — SmartDoc (별도 저장소 `C:\DevProjects\SmartDoc`, 별도 상세계획)

Phase A 후 SmartDoc 코드 탐색 → 아래 범위를 별도 계획서로 상세화한다. 인터페이스는 이미 합의됨(handoff/external.py).

1. **크레딧 → 건별 결제 전환** — `wallet_api`/문서생성 시점: 충전·잔액·팩 UX 제거, "이 신청서 = ○○원" 단건 결제(기존 `record_charge`+payment_id 재사용). 문서 생성/내보내기 관문에서 무료분 없으면 단건 결제.
2. **첫 건 무료** — 기존 증정 크레딧(`redeem_pilot_credits`/`signup_bonus_credits`)을 "첫 N건 무료"로 재프레이밍.
3. **통일 브랜딩** — SmartDoc 화면을 "지원금AI 신청서 작성"으로. 핸드오프 진입 사용자에게 GovMatch 연속감.
4. **핸드오프 세션 처리** — `/handoff` 진입(entitlement 통과) 세션은 SmartDoc 로그인 재요구 없이 작성 진행(이미 세션토큰 발급 구조 있음).
5. **배포 후** — GovMatch에 `NEXT_PUBLIC_SMARTDOC_READY=true` 설정 → 버튼 실연결 활성화.

---

## 검증 · 롤아웃

- Phase A는 `SMARTDOC_READY` 미설정으로 **버튼만 노출**(안전). Phase B 완료 후 플래그 true로 실연결.
- 중진공 융자 집합(현재 15건)은 시간에 따라 변동 — 게이팅은 조건 기반이라 신규 공고 자동 포함.
- 데이터 유의: `#116xxx`/`#76xxx`/기타 계열에 유사 자금명 **중복 공고**가 있음(별건 dedup 대상, 이 계획 범위 밖).

## Open Items

1. `ResultCard`의 API base 상수 실제 이름 확인(Task 3에서 `NEXT_PUBLIC_API_URL` 직접참조 vs 기존 상수).
2. Phase B 착수 전 SmartDoc의 크레딧 차감이 문서생성 흐름 어디서 일어나는지 확정(현재 wallet엔 구매/증정만 확인, 차감 지점 미확인).
3. 향후 옵션: PRO 구독에 "신청서 N건 포함"(entitlement에 plan 반영) — 지금은 범위 밖.
