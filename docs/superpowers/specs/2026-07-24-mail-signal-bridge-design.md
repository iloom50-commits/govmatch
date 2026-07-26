# 메일 신호 브리지 (인프라 알림 → AI COO) 설계

- 작성일: 2026-07-24
- 상태: 설계 승인 대기 (대표 리뷰 전)
- 관련: [[project_ai_monitoring]], [[project_orchestrator_ai]], `backend/app/services/orchestrator/`

## 1. 목적

대표 구글메일로 들어오는 **외부 서비스 인프라 알림**(Railway·Vercel·Supabase의 배포실패·장애·과금 경고)을
지원금AI가 자동으로 수집·분석해, 기존 AI COO 일일 보고서에서 **"이상상태 + 조치계획"으로 함께** 보게 한다.

지금의 AI COO는 프로덕션 DB만 본다(내부 관측). 메일함으로 들어오는 **바깥 신호**를 관측 범위에 편입해
인프라 이상을 놓치지 않는 것이 목표다.

### 비목표 (YAGNI — v1에서 안 함)
- 결제/사용자문의/AI COO 자기보고서 메일 처리 (범위=인프라 알림만. 대표가 명시적으로 이 범위 선택).
- 치명적 알림의 즉시 별도 알림(카톡/메일). v1은 **일일 COO 보고서 통합까지**. 실제 어떤 신호가 얼마나
  들어오는지 관측한 뒤 v2에서 판단.
- 메일 원문 전체 저장·검색. 제목·스니펫 요약만 저장한다.

## 2. 접근 방식 결정

**(B) Google Apps Script 브리지 채택.** 대안과 트레이드오프:

- (A) 백엔드 Gmail API 직접 연동(OAuth): 개인 Gmail은 OAuth 앱이 testing 모드라 refresh 토큰 7일 만료 →
  운영 부담. Google Cloud 프로젝트·동의화면·토큰갱신 셋업 최다. **기각**.
- (B) Apps Script 브리지: Gmail 접근이 구글 계정 안에서 일어나 **OAuth 토큰 만료 없음**. 백엔드는 받아서
  분석만. 기존 오케스트레이터 패턴에 스텝 하나 추가. **채택**.
- (C) Claude 예약작업 커넥터: 백엔드 무변경이나 "프로그램 내장" 아님 + 커넥터 인증 불안정. **기각**.

## 3. 아키텍처 & 데이터 흐름

```
[대표 Gmail] ─(인프라 알림: railway/vercel/supabase 발신)
   │
① Google Apps Script (대표 구글계정 내, 시간기반 트리거 1일 1회 · 08~09시 KST = COO 09:30 직전)
   │  Gmail 검색 from:(railway.app OR vercel.com OR supabase.io OR supabase.com) newer_than:1d -label:govmatch-processed
   │  각 메일 요약(msg_id·date·from·subject·snippet) → POST → 성공 시 'govmatch-processed' 라벨
   ▼ HTTPS POST + X-Bridge-Secret
② POST /api/internal/mail-signal (main.py)
   │  시크릿 검증 → 서비스 분류 + 심각도 추정 → mail_signals 저장(gmail_msg_id UNIQUE 멱등)
   ▼
③ mail_signals 테이블 (ADD-only)
   ▼
④ AI COO supervisor.py 신규 스텝: collect_mail_signals(db_conn)
   │  최근 24h 미분석 신호 → 규칙 기반 진단(서비스별 조치힌트·high 노출) → analyzed_at 마킹
   ▼
⑤ reporter.py '🖥 인프라 상태' 섹션(텍스트/HTML). 0건이면 "이상 없음" 한 줄.
```

**단일 책임 경계:**
- Apps Script = 긁어서 넘김(판단 안 함)
- 엔드포인트 = 검증·저장(LLM 안 부름)
- collector = 분석(Gmail 모름)
- reporter = 표시

**읽기 전용 원칙**: 메일 수정·발송·삭제 없음. Apps Script는 처리표시용 라벨만 부착.

## 4. 컴포넌트

### 4.1 Apps Script `govmatch-mail-bridge.gs` (대표 1회 설치, 코드는 제공)
- 스크립트 속성에 백엔드 URL·공유 시크릿 저장.
- 시간기반 트리거 **1일 1회**(08~09시 KST, COO 09:30 전). v1은 일일 보고 통합이라 더 자주 긁어도
  이득 없음 + 쿼터 절약. `newer_than:1d`가 일일 주기와 맞음. (즉시성 필요 시 v2에서 15분+즉시알림.)
- 검색 쿼리로 인프라 알림만, `-label:govmatch-processed`로 미처리분만.
- 각 메시지 → `{msg_id, date, from, subject, snippet}` POST → **성공(2xx) 시에만** 라벨 부착.
- POST 실패 시 **동일 실행 내 2~3회 재시도**(일시 실패 흡수), 그래도 실패면 라벨 미부착 → 다음날
  트리거에서 재시도(하루 1회라 24h 지연 방지용 동일-실행 재시도). 발신자 목록은 스크립트 상단 상수.

### 4.2 엔드포인트 `POST /api/internal/mail-signal` (main.py)
- 헤더 `X-Bridge-Secret` == env `MAIL_BRIDGE_SECRET` 검증(불일치·누락→401).
- body `{msg_id, date, from, subject, snippet}`. 필수 필드 누락→400.
- 서비스 분류: from 도메인 → railway/vercel/supabase/other.
- 심각도 추정: 제목·스니펫 키워드(`failed|error|outage|past due|billing|exceeded|down`)→high, 그외 info.
- `INSERT ... ON CONFLICT (gmail_msg_id) DO NOTHING`(멱등).

### 4.3 테이블 `mail_signals` (init_database에 `_safe_exec`로 ADD-only)
| 컬럼 | 타입 | 용도 |
|---|---|---|
| id | SERIAL PK | |
| gmail_msg_id | VARCHAR UNIQUE | 멱등키 |
| received_at | TIMESTAMP | 메일 수신시각 |
| sender | VARCHAR | from |
| subject | TEXT | 제목 |
| snippet | TEXT | 요약 |
| service | VARCHAR(20) | railway/vercel/supabase/other |
| severity | VARCHAR(10) | high/info |
| analyzed_at | TIMESTAMP NULL | COO 처리 여부 |
| created_at | TIMESTAMP | 레코드 저장시각(서버) |

> 와이어 필드 `msg_id`·`date`는 엔드포인트에서 각각 `gmail_msg_id`·`received_at`으로 매핑.

> `_safe_exec` 필수: init_database 직접 execute는 뒤 statement 실패 시 롤백에 휩쓸림(async-consult 사고 교훈).

### 4.4 collector `mail_signal_collector.py` + supervisor 배선
- `collect_mail_signals(db_conn) -> dict`: 최근 24h `analyzed_at IS NULL` 신호 조회 → **규칙 기반**으로
  서비스별 카운트·high 신호 노출·서비스별 조치힌트(`action_hint`) 산출 → `{count, high[], by_service{}}`
  반환 → analyzed_at 마킹. **0건이면 즉시 `{"count":0}` 반환**(비용 0).
- 규칙 기반 채택 근거: 기존 COO 수집기(coverage/quality)가 전부 규칙 기반, 인프라 알림 저빈도 → LLM
  불필요(결정적·비용 0). 즉시성/서술형 조치가 필요해지면 v2에서 LLM 도입.
- supervisor.py 스텝 흐름에 삽입(현 4스텝 → 5스텝). 기존 스텝별 try/except 격리 패턴 준수.

### 4.5 reporter 섹션
- `reporter.py`에 '🖥 인프라 상태' 섹션(텍스트+HTML). high 신호 강조. 0건이면 "인프라 이상 없음" 한 줄.

## 5. 보안 · 에러처리

### 보안
- 공유 시크릿(`X-Bridge-Secret`) — 공개 URL이라 무인증이면 가짜 신호 주입 가능. 필수.
- `/api/internal/*` 네이밍으로 공개 API와 분리. 관리자 토큰이 아닌 브리지 시크릿(용도 격리).
- 백엔드로 가는 것은 제목·스니펫 요약뿐(본문 전문 아님).

### 에러처리
| 지점 | 실패 시 |
|---|---|
| Apps Script POST 실패 | 동일 실행 내 2~3회 재시도 → 실패 시 라벨 미부착 → 다음날 트리거 재시도(유실 없음) |
| 중복 전송 | gmail_msg_id UNIQUE + ON CONFLICT → 멱등 |
| body 필드 누락 | 400, 저장 안 함 |
| collector 오류 | 스텝 try/except 격리 → 그 섹션만 "분석 실패", 일일 보고서 전체는 정상 발송 |
| 신호 0건 | "이상 없음" 한 줄(비용 0) |

### 되돌리기
- 전부 ADD-only(새 테이블·엔드포인트·스텝·env). 기존 로직 무변경([[project_deployment_policy]]).
- 기능 정지 = Apps Script 트리거만 끄면 됨. COO 스텝은 "0건→이상없음"으로 무해 축소.

## 6. 테스트

| 대상 | 종류 | 케이스 |
|---|---|---|
| 엔드포인트 | 단위(FakeCursor) | 시크릿 401 / 서비스 분류 / 심각도 / 멱등(2회→1행) / 필드누락 400 |
| collector | 단위(DB 모킹) | 24h만 조회 / high 노출·by_service 집계 / 0건→빈 결과 / analyzed_at 마킹 |
| reporter | 단위 | 있음·없음 렌더(텍스트·HTML), high 강조 |
| Apps Script | 자동불가 | 설치 후 실제 알림 1건 도착 = 라이브 스모크 |
| 통합 | 수동 1회 | 알림 1건 도착 → mail_signals 저장 → 다음 COO 메일 섹션 노출 |

**정직한 한계**: Apps Script는 자동테스트 원천 불가 → 백엔드 유닛으로 촘촘히 막고, 연결은 실제 메일 1건
라이브 스모크. (async-consult 교훈: 모킹 유닛은 커밋 취약성 못 잡음 → 라이브 스모크 필수.)

## 7. 배포

1. 백엔드(테이블·엔드포인트·collector·reporter) 배포 — 그 자체로는 신호 0이라 "이상없음"만.
2. 대표: Apps Script 설치 + 트리거 + `MAIL_BRIDGE_SECRET` env(Railway) 설정.
3. 라이브 스모크: 인프라 알림 1건 도착 → 저장 확인 → COO 섹션 노출.
