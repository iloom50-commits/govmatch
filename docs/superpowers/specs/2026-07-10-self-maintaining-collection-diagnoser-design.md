# 자기유지형 수집 시스템 — 진단자(Diagnoser) 설계

작성: 2026-07-10 · 방식: 브레인스토밍 → 이 스펙 → writing-plans → FABLE 설계 → Opus TDD 시공

## 1. 배경 / 문제

정부지원 공고를 여러 공공기관에서 스크랩·수집한다. 부산경제진흥원(BEPA)이 3.5개월간 신규 0건인 것을 계기로 조사한 결과, **수집 소스가 조용히 죽어도 아무도 모르는 구조적 사각지대**가 드러났다.

- 원인 조사(실DB 확인): admin_urls 187개는 전부 활성·fail_count 0이고 스크래퍼도 방문 중이나(last_scraped 07-04~09), **24개 소스가 2026-03 이후 신규 0건**. HTTP 실패가 아니라 **페이지는 열리는데 공고를 못 뽑는 "조용한 추출 실패"**. BEPA가 증거: 등록 URL이 `no=1508`(랜딩)인데 실제 공고는 `no=1502/1505`에 있었음.
- Phase 1(2026-07-10, 커밋 fcb3c49)로 **회귀 감시자**는 구축·배포됨: `announcements.origin_source` 기반 자기교정 회귀감지가 이 24개를 매일 YELLOW로 잡아 COO 메일에 노출.

남은 문제: 회귀 감시자는 "조용해졌다"만 알려준다. **"왜 0건인지" 진단하고, 그 진단이 일회성이 아니라 매주 도는 자기유지 루프**가 필요하다. 이 스펙이 그 루프의 첫 증분(진단자)을 정의한다.

## 2. 확정된 설계 결정 (브레인스토밍)

1. **자율 경계**: 탐지·진단은 프로덕션에서 완전 자동. **수집에 영향을 주는 구조 변경(스크래퍼 코드·신규 기관 등록·URL 교체)은 자동 실행 안 함** — 제안까지만.
2. **수리 주체**: 코드 수리(스크래퍼 수정·신규)는 **Claude 세션에서 TDD로**(FABLE 설계 → Opus 시공). 프로덕션에 자동 코드 생성 에이전트를 두지 않는다("그럴듯하지만 틀린 데이터" 방지).
3. **URL 교체도 제안만**: 잘못된 URL 교체는 엉뚱한 데이터를 긁으므로, 진단자는 "이 URL로 바꾸는 게 좋겠다"를 **제안**하고 적용은 세션/관리자에서.
4. **범위**: 북극성(3역할) 확정 + **첫 증분=진단자만 시공 가능 수준으로 상세화**. 발굴자는 다음 증분.
5. **진단자 v1은 결정적 로직(LLM 미사용)**: 저비용·결정적·테스트 가능. LLM 보강은 v2.

## 3. 북극성 아키텍처 — "자기유지형 수집 시스템"

오케스트레이터(AI COO, `run_daily_supervision`)가 3개 역할을 조율하며 전부 **탐지·진단·제안까지만** 수행한다.

| 역할 | 하는 일 | 주기 | 상태 |
|---|---|---|---|
| **① 회귀 감시자** | origin_source 자기교정으로 "조용해진 소스" 탐지 | 매일 | ✅ 완료(Phase 1) |
| **② 진단자** | 조용한 소스의 등록 URL 재fetch → 0건 원인 유형 분류 + 수리 제안 | 주1회 | 🔨 이 스펙 |
| **③ 발굴자** | 집계API에 자주 뜨는데 우리에 없는 기관 → 신규 후보 | 주1회 | 다음 증분 |

- **보고 채널**: ①②③ 결과를 COO 메일의 "수집 커버리지 & 자기유지" 한 섹션에 모은다. 이 **메일이 작업 큐**.
- **수리 루프**: 사장님이 메일 확인 → 항목을 Claude 세션으로 → FABLE 설계 → Opus TDD 시공 → 배포. 프로덕션은 수집 대상을 말없이 바꾸지 않는다.
- **자동/게이트 경계**: 자동=탐지·진단·발굴·보고. 게이트(세션/승인)=스크래퍼 코드·신규 기관·URL 교체.

## 4. 첫 증분 — 진단자(Diagnoser) 상세설계

### 4.1 목적·범위

회귀 감시자가 YELLOW/RED로 지목한 소스 중 **`admin_urls` 기반(URL 등록형) 소스**의 등록 URL을 재fetch해서 **왜 0건인지 유형을 자동 판별**하고 유형별 수리 제안을 메일에 띄운다.

- **범위 안**: admin_urls 테이블에 URL이 등록된 소스(origin_source `admin-manual:<source_name>`).
- **범위 밖**: 전용 스크래퍼(tier-1, 예 BEPA·CCEI) 코드 문제 — 이건 ①회귀로 노출되고 세션에서 진단·수리. (진단자가 임의 코드를 진단하진 않음.)

### 4.2 진단 로직 (결정적, v1)

소스마다:
1. 등록 URL을 fetch (requests, timeout 15s; SSL 실패 시 verify=False 1회 재시도).
2. 응답 HTML에서 **공고성 링크 수**를 센다 — 기준: 기존 `admin_scraper._DETAIL_URL_PATTERNS`(view/detail/read/notice/board/bbs/seq=/idx=/id=/no=/nttId=/articleId=/bid=/num=/post/content) 중 하나라도 포함하는 `<a href>`.
3. 본문 텍스트 길이(스크립트 제외 가시 텍스트)를 잰다.
4. 순수함수 `classify_diagnosis(http_status, link_count, body_len)` 로 분류:

| 조건 | diag_type | 제안(suggested_action) |
|---|---|---|
| http_status 없음/≥400/타임아웃/SSL실패 | `unreachable` | URL 폐쇄·이전 의심 — 새 URL 확인 |
| 200 & link_count ≥ `LINK_MANY`(=5) | `extract_fail` | 링크는 있으나 미추출 — 파서/전용스크래퍼 점검 |
| 200 & link_count < 5 & body_len < `BODY_STUB`(=800) | `js_only` | JS 전용 렌더링 의심 — Playwright 전용 스크래퍼 |
| 200 & link_count < 5 & body_len ≥ 800 | `wrong_or_empty` | 엉뚱한 URL/빈 게시판 — 올바른 게시판 URL 확인(BEPA형) |

임계값 근거: `LINK_MANY=5`(공고 게시판이면 통상 목록 링크 5+개), `BODY_STUB=800`(정상 렌더 페이지는 가시 텍스트 800자 이상; JS 스텁은 그 미만). 둘 다 모듈 상수 — 실측 후 조정.

### 4.3 저장 (DB 추가만 — 제약 준수)

`coverage_targets`에 컬럼 추가:
```sql
ALTER TABLE coverage_targets ADD COLUMN IF NOT EXISTS diag_type        VARCHAR(30);
ALTER TABLE coverage_targets ADD COLUMN IF NOT EXISTS diag_detail      TEXT;
ALTER TABLE coverage_targets ADD COLUMN IF NOT EXISTS diag_link_count  INTEGER;
ALTER TABLE coverage_targets ADD COLUMN IF NOT EXISTS diag_http_status INTEGER;
ALTER TABLE coverage_targets ADD COLUMN IF NOT EXISTS diag_at          TIMESTAMP;
```
소스별 최신 진단 스냅샷만 upsert(source_name 키). 이력 테이블은 v1 불필요.

### 4.4 배선·주기

- 새 함수 `diagnose_silent_sources(conn)` — 신규 파일 `backend/app/services/orchestrator/source_diagnoser.py` (회귀감지 coverage_checker와 분리: 진단은 외부 fetch를 하는 별개 관심사).
- `run_daily_supervision`에 진단 스텝 추가하되 **주1회만 실행**: KST 월요일에만(그 외 요일은 직전 스냅샷 재사용). 대상은 회귀 감시자 결과의 YELLOW/RED 중 admin_urls에 URL이 있는 소스로 한정(전량 아님 → 부하 최소).
  - **조인 키**: origin_source `admin-manual:<source_name>`에서 `admin-manual:` 접두를 제거한 값 = `admin_urls.source_name`으로 매칭해 URL을 얻는다. (scraper:*/*-api 소스는 admin_urls에 없으므로 진단자 대상에서 자연 제외 — 이들은 전용 스크래퍼/전용 API라 ①회귀+세션 수리로 처리.)
- 외부 fetch는 소스당 try/except; 스텝 전체도 try/except로 격리(메일 내구성).

### 4.5 메일 노출

COO 메일 "수집 커버리지" 섹션 아래 **"🔧 수리 필요"** 하위목록 추가(reporter):
```
🔧 수리 필요 (진단 N건)
  · admin-manual:부산경제진흥원(BEPA) — 엉뚱한URL/빈게시판: 올바른 게시판 URL 확인
  · admin-manual:○○테크노파크 — JS전용: Playwright 전용 스크래퍼 필요
  ...(상위 8건)
```
텍스트/HTML 빌더 둘 다. 진단 없거나 error면 빈 문자열(기존 `_build_coverage_*` 계약과 동일).

### 4.6 첫 사이클 = 23개 스윕

배포 후 첫 월요일(또는 수동 `/api/admin/coo/run`) 실행이 곧 현재 조용한 admin 소스 ~23개의 첫 진단 스윕. 이후 매주 자동 재실행 → 새로 썩는 소스도 계속 진단. **"일회성"이 구조적으로 해소됨.**

## 5. 테스트 (TDD)

- **순수함수 단위테스트** `test_source_diagnoser_unit.py`:
  - `classify_diagnosis` 4개 분기 각각 + 경계(link_count 4 vs 5, body_len 799 vs 800, http 200 vs 404/None).
  - 링크 카운트 파서: 픽스처 HTML(공고링크 다수 / 0 / JS 스텁)로 검증.
- **런타임 검증(단위 불가 — 정직 구분)**: 배포 후 실 23개 URL 1회 실행 → 유형 분포·제안이 실감과 맞는지 육안. BEPA는 `wrong_or_empty`로 잡히는지 확인(이미 전용스크래퍼로 대체됐으므로 뮤트 대상).

## 6. 배포·검증 순서

1. 실패테스트 작성 → FAIL 확인.
2. `classify_diagnosis` + fetch/parse 구현 → 단위 PASS.
3. DB 컬럼 add-only 마이그레이션(main.py init).
4. supervisor 주1회 스텝 + reporter "수리 필요" 섹션.
5. 로컬에서 실 23개 URL 1회 실행 → 유형 분포 육안 검증(임계값 조정 여지).
6. git push → 배포 → `/api/admin/coo/run` 수동 1회 → 메일에 "수리 필요" 노출·이중발송 없음 확인.

## 7. 범위 밖 / 차기 증분

- **③ 발굴자**(신규 기관 API-mining): 다음 스펙.
- **진단자 v2 LLM 보강**: "링크 텍스트 보고 올바른 게시판 URL 추정". 비용·검증 이유로 v1 제외.
- **자동 URL 교체·자동 뮤트**: 하지 않음(제안만). 적용은 세션/관리자.

## 8. 리스크 (정직 고지)

1. `LINK_MANY=5`/`BODY_STUB=800`은 보수적 초기값 — 실측 1회로 1차 보정 필요. 오분류해도 "제안"일 뿐이라 피해 없음.
2. JS 전용 페이지는 requests로는 항상 스텁으로 보여 `js_only`로 잡히나, 서버사이드 렌더 사이트를 오탐할 수 있음(본문 길이 게이트로 완화).
3. 일부 소스는 "진짜로 신규 없음"(정상 휴면)인데 `wrong_or_empty`로 분류될 수 있음 — 사람이 뮤트로 처리(진단자는 의도를 모름).
4. 외부 fetch 주1회 ~24건 = 수십 초~1분대. 스텝 격리로 메일 내구성 확보.
