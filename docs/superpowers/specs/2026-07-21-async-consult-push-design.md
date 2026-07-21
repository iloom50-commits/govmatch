# AI 상담 비동기화 + 완료 푸시 — 설계서

- 작성일: 2026-07-21
- 대상: 공고 AI상담(`POST /api/ai/consult`)만. `pro_consult` 등 다른 상담 경로는 범위 밖.
- 배경: 상담 응답 생성(LLM)이 느려 사용자가 채팅창에서 대기해야 함. 창을 닫고 나가도 백그라운드에서 완료되면 웹 푸시로 알리고, 푸시를 탭하면 해당 상담을 바로 열어 UX를 개선한다.

## 확정된 제품 결정 (브레인스토밍)

1. **서버 처리 모델**: 항상 백그라운드 작업(제출→job_id 즉시 반환→백그라운드 처리). 닫든 안 닫든 한 경로.
2. **푸시 도착지**: 해당 상담 바로 열기(상담이력 목록이 아니라 복원된 채팅).
3. **푸시 대비책**: 처리 중 창을 닫을 때 권한 없으면 권한 요청 모달로 적극 유도. 거부 시 인앱 배지 + 재접속 알림.
4. **실패 시 과금**: 성공 시에만 50크레딧 차감(제출 시 차감 보류, 백그라운드 성공 후 확정 차감). 실패 시 무차감 → 환불 로직 불필요.

## 실측 전제 (현행 코드)

- 상담 결과는 이미 `ai_consult_logs`에 `session_id` 기준 UPSERT로 저장됨 (`main.py:5605`).
- `chat_consult`는 동기(blocking) 함수 (`ai_consultant.py`). 요청과 분리해 백그라운드로 실행해야 함.
- 신규 세션(공고당 첫 상담) = 50크레딧 과금 단위. 후속 질문(24h 내 기존 세션)은 무차감 (`main.py:5476–5626`).
- 푸시 인프라 존재: `push_subscriptions`(business_number, endpoint, p256dh, auth), `POST /api/push/subscribe`, `send_push`. **단 `send_push`는 마케팅용**이라 ① "맞춤 공고 N건" 모양 고정, ② **KST 09~18시 게이트**(`notification_service.py:523`)가 있어 상담 완료 알림엔 부적합.
- 서비스워커(`frontend/public/sw.js`)에 `push` 수신 + `notificationclick`→`clients.openWindow(data.url)`가 이미 구현됨 → **SW 변경 불필요**.
- 세션 복원 엔드포인트 `GET /api/ai/consult/session/{session_id}` 존재(24h 이내 messages 반환).

## 데이터 모델 — `consult_jobs` (추가만, 삭제·변경 없음)

`CREATE TABLE IF NOT EXISTS`로 기동 시 생성. 배포 정책(컬럼 삭제·변경 금지, 추가만 허용) 준수.

| 컬럼 | 타입 | 용도 |
|---|---|---|
| `job_id` | UUID PK | 상담 턴 1건 = job 1건 |
| `session_id` | VARCHAR(64) | 기존 상담 세션 키(재사용) |
| `business_number` | VARCHAR(50) | 소유자 |
| `announcement_id` | INTEGER | 대상 공고(딥링크용) |
| `status` | VARCHAR(20) | `processing` / `done` / `failed` |
| `result` | JSONB | 완료 응답(reply·choices·done·conclusion·consult_log_id·origin_url). 폴링이 바로 반환 |
| `notify_requested` | BOOLEAN default false | 사용자가 창을 닫고 나가 푸시를 원함 |
| `notified` | BOOLEAN default false | 푸시 발송 완료(중복 방지) |
| `seen` | BOOLEAN default false | 인앱 배지용 — 결과 확인함 |
| `error` | TEXT | 실패 진단 |
| `created_at` / `updated_at` | TIMESTAMP | stale 정리·정렬 |

인덱스: `idx_consult_jobs_bn_status`(business_number, status) — 배지 조회용. `job_id`는 PK.

## 백엔드 흐름

### 1) `POST /api/ai/consult` — 제출형으로 리팩터

동기로 남기는 것(싸고, 게이트여야 하는 것만):
1. 사용자 프로필 로드 (현행 `main.py:5455–5474`).
2. 신규/기존 세션 판별 (현행 `main.py:5479–5493`).
3. **신규 세션 && 비면제 && 잔액 < 50 → 402 즉시 반환**(원가 낭비 방지, 현행 로직 유지).
4. 신규면 `session_id` 발급 + `consult_sessions` insert(현행).
5. `consult_jobs` 행 insert(status=processing, notify_requested=false).
6. `BackgroundTasks.add_task(_run_consult_job, job_id, ...)`.
7. **즉시 반환**: `{status:"PROCESSING", job_id, session_id, is_new_session}`.

> `BackgroundTasks`는 응답 전송 후에도 서버 워커에서 끝까지 실행되며 클라이언트 연결과 무관 → "닫고 나가도 계속" 성립.
>
> **커넥션 주의**: 워커는 제출 요청에서 쓰던 커넥션을 재사용하지 않고 `get_db_connection()`으로 자체 커넥션을 열고 닫는다(요청 스코프 커넥션은 응답과 함께 종료되므로). 제출 핸들러는 단계 1–5용 커넥션을 반환 전에 닫는다. 넘기는 인자(`req`, `current_user`, `session_id`, `is_new_session`)는 순수 데이터라 안전.

### 2) 워커 `_run_consult_job(job_id, req, current_user, session_id, is_new_session)`

현행 `main.py:5516–5644`의 본체를 그대로 이동:
1. 공고 조회 → `ensure_analysis`(deep) → target_type 프로필 필터 → `chat_consult`.
2. done 오버라이드(사용자 메시지 3개 미만이면 done=false) 유지.
3. `ai_consult_logs` UPSERT(현행 `5605`) → `consult_log_id`.
4. **`is_new_session && llm_ok`이면 50크레딧 차감**(현행 `5625`).
5. `result` 구성 → `consult_jobs` 업데이트(status=done, result=…, updated_at).
6. 완료 직후 `notify_requested`를 **다시 조회**. 참 && `notified=false`이면 → `send_transactional_push` + `notified=true`.
7. 예외 시 `consult_jobs.status=failed, error=…`, **무차감**(llm_ok=false).

### 3) `GET /api/ai/consult/job/{job_id}` — 폴링

- 소유자(bn) 검증. 없으면 404.
- **lazy stale 정리**: 조회 시 `status=processing && updated_at < now()-30min`이면 failed로 전환.
- 반환: `{status}`; done이면 `result` 포함, failed면 재시도 안내 메시지.

### 4) `POST /api/ai/consult/job/{job_id}/notify` — 창 닫기 시

- 소유자 검증.
- 현재 status 조회:
  - `processing` → `notify_requested=true` 세팅. `{status:"processing"}`.
  - `done && notified=false` → 즉시 `send_transactional_push` + `notified=true`. `{status:"done", pushed:true}`.
  - `done && notified=true` 또는 `failed` → 상태만 반환.
- 경쟁(닫기 vs 완료)을 양방향 모두 커버.

### 5) `GET /api/ai/consult/pending` — 인앱 배지

- bn 소유의 `status=done && notify_requested=true && seen=false` 목록/개수 반환(최근 7일).
- 상담을 열면 `seen=true`(아래 seen 처리).

### 6) `POST /api/ai/consult/job/{job_id}/seen` — 배지 해제

- 소유자의 job `seen=true`. 배지에서 제거.

## 푸시 — 범용 트랜잭션 함수 신설

`notification_service.send_transactional_push(business_number, title, body, url) -> int`
- `send_push`에서 **09~18시 게이트 제거 + matches 모양 제거**. 임의 title/body/url.
- 대상: 해당 bn의 모든 `push_subscriptions`. 410/404는 기존처럼 구독 삭제.
- 딥링크 `url = /?consult=<session_id>&aid=<announcement_id>`.
- payload: `{title:"상담 분석이 완료됐어요", body:<공고 제목>, url, icon}`.

## 프론트엔드

### AiConsultModal (`frontend/src/components/AiConsultModal.tsx`)

현행 동기 `fetch('/api/ai/consult')`(라인 356)를 제출+폴링으로 교체:
1. 전송 → `POST /api/ai/consult` → `job_id` 저장.
2. **2초 간격 폴링** `GET .../job/{job_id}`(지수백오프 없이 고정 2s, 최대 3분 후 타임아웃 안내).
3. "분석 중… 창을 닫아도 완료되면 알림을 보내드려요" 진행 표시.
4. done → 기존 렌더 경로(reply·choices·done·conclusion)로 표시, 폴링 중단. **열어둔 경우 푸시 없음.**
5. failed → "다시 시도" 안내(무차감).

### 창 닫기(처리 중) 핸들러

- 처리 중 job이 있으면 닫을 때:
  - 푸시 권한 `granted` → 구독 확인 후 `POST .../job/{job_id}/notify`.
  - 권한 `default`(미결정) → **권한 요청 모달** 노출 → 승인 시 구독+notify, 거부 시 인앱 배지 폴백.
  - 권한 `denied` → 바로 인앱 배지 폴백(모달 재노출 안 함).
- 푸시 구독은 기존 `NotificationModal`/`layout.tsx`의 구독 로직 재사용.

### 인앱 배지 + 딥링크

- 앱 로드/상담이력 진입 시 `GET /api/ai/consult/pending` → 상단 종(또는 상담이력 탭)에 "완료된 상담 N건" 배지.
- 배지/푸시 클릭 → `/?consult=<session_id>&aid=<announcement_id>` → HomeClient가 파라미터 감지 → 해당 공고 AiConsultModal을 세션 복원(`GET /api/ai/consult/session/{session_id}`) 상태로 오픈 → 열리면 `POST .../job/{job_id}/seen`으로 배지 해제.

## 안전장치 / 경계

- **서버 재시작 유실**: 폴링(3) 시 lazy로 processing 30분 초과를 failed 처리 → 무차감이라 손해 없음. 별도 기동 정리 배치는 불필요(YAGNI, lazy로 충분).
- **경쟁(닫기 vs 완료)**: notify 엔드포인트가 양쪽 순서 처리(4).
- **다기기**: 해당 bn의 모든 구독에 발송(기존 동작).
- **범위 한정(YAGNI)**: `/api/ai/consult`만. 첫 턴·후속 턴 구분 없이 한 경로. 푸시는 닫고 나갔을 때만 → 후속 질문 스팸 없음.
- **엔드포인트 계약 변경**: `/api/ai/consult` 응답이 바뀌므로 프론트와 **동시 배포**(단일 호출처라 안전). 배포는 로컬 테스트→git push(feature→main ff→push).

## 테스트 (TDD)

### 단위(백엔드)
- `consult_jobs` 상태전이: processing→done, processing→failed.
- lazy stale 정리: updated_at 30분 초과 processing → failed.
- notify 경쟁: (a) notify 먼저→완료 시 발송, (b) 완료 먼저→notify 시 즉시 발송. 둘 다 `notified` 1회만.
- **성공 시에만 차감**: llm 성공→50 차감 1회; llm 실패→무차감; 후속 세션→무차감.
- `send_transactional_push`: 시간대 게이트 없음(야간에도 발송 경로 진입).

### 수동/통합
- 제출→폴링→결과 렌더.
- 처리 중 닫기→푸시 도착→탭→해당 상담 복원.
- 권한 거부→인앱 배지 노출→클릭→복원→배지 해제.

## 미결/후속(범위 밖)
- `pro_consult`·자금상담 등 다른 상담 경로 비동기화는 별도 스펙.
- 배지의 정확한 위치(상단 종 vs 상담이력 탭)는 구현 시 프론트 레이아웃에 맞춰 확정.
