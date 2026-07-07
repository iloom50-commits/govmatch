# 신청서 작성 버튼 게이팅 — 설계 문서

- 작성일: 2026-07-07
- 상태: **게이팅 구현 완료·배포 (94a8ca8)** — 6단계 전부 시공. SmartDoc 엔진(버튼 클릭 후 자동작성)은 미연결(기존 open-smartdoc-modal 유지) — SmartDoc 개발 완료 후 연결. 배포 직후엔 has_application_form이 전부 false라 버튼이 일시적으로 안 보이며, 일일 파이프라인 ④-4 스텝이 돌면서 신청서 있는 공고부터 버튼 노출.

## 1. 배경 / 문제

공고문 카드에 **"AI 신청서 작성"** 버튼이 붙어 있고, 여기에 신청서 자동작성 프로그램(SmartDoc)을 연동한다. 그런데 현재 버튼은 [ResultCard.tsx:489](../../../frontend/src/components/ResultCard.tsx#L489) 에서 **`res.target_type !== "individual"` 조건만** 걸려 있어, 신청서가 없는 기업 공고에도 전부 붙는다. 사용자는 "버튼을 눌렀는데 작성할 신청서가 없는" 혼돈을 겪는다.

**목표**: 버튼을 **"SmartDoc이 실제로 채울 수 있는 신청서 양식이 있는 공고"에만** 노출한다.

## 2. 범위

**In-scope**
- 공고별 "신청서양식 유무" 신호를 넓게 확보(파이프라인 배치)
- 그 신호로 카드 버튼 게이팅
- 신청서양식 분류 규칙 확정(PDF 포함)

**Out-of-scope**
- SmartDoc 본체(자동작성 엔진) 구현 — 버튼 클릭 후 흐름은 기존 `open-smartdoc-modal` 유지
- 첨부 파일 내용 기반 정밀 판별(파일명·포맷 휴리스틱 수준까지만)

## 3. 판별 신호 & 분류 규칙

### 3-1. 신호 (기존 자산 재사용)
`announcements.attachments` (JSONB) — 각 첨부에 `kind` 필드. 분류기·수집기가 이미 존재:
- 분류: [attachments.py `_classify_kind`](../../../backend/app/services/attachments.py#L83)
- 수집: [attachments.py `build_attachments_meta` / `get_or_build`](../../../backend/app/services/attachments.py#L145)

**"신청서 있음" = `attachments`에 `kind == '신청서양식'` 항목이 하나라도 존재.**

### 3-2. 분류 규칙 (확정 — PDF 포함으로 소폭 수정)
SmartDoc이 PDF 신청서도 자동작성 가능(사용자 확정)하므로, PDF도 신청서양식 후보에 포함한다.

1. **파일명 키워드 우선 (기존 유지)**
   - `신청서|신청양식|지원서|참가신청` → **신청서양식**
   - `사업계획` → 사업계획서양식
   - `붙임|별지|서식` → 붙임서식
   - `공고|공고문|안내` → 공고문
2. **키워드 없을 때 (변경점)**: 기존 `편집가능=신청서양식 / PDF=공고문` → **`편집가능(hwp·hwpx·docx·xlsx) + PDF` 모두 신청서양식**
   - 즉 `_classify_kind`에서 `if ext == "pdf": return "공고문"` 을 제거하고, `ext in (_EDITABLE + ("pdf",))` → 신청서양식으로.

**트레이드오프(정직)**: 키워드 없는 **공고문 PDF**가 신청서양식으로 오분류될 수 있다(→ 버튼 오노출). `공고|공고문|안내` 키워드로 상당 부분 걸러지나 100%는 아니다. PDF 포함 방향에선 "놓치기보다 포함"을 택한다. 오노출은 향후 SmartDoc 실사용 데이터로 키워드 보정.

## 4. 데이터 채우기 — 파이프라인 스텝 추가

신청서 판정을 넓게 확보하기 위해, `daily_pipeline`에 스텝을 추가한다(마감일 보강 ④-2와 동일 패턴, P1-3 enricher 방식).

- **함수**: `attachments.py`에 신규 `enrich_attachments(db_conn, limit)` — 내부는 기존 `build_attachments_meta` 재사용(신규 판정 로직 없음).
- **대상**: `is_archived=FALSE AND COALESCE(target_type,'business') IN ('business','both') AND origin_url IS NOT NULL AND (deadline_date IS NULL OR deadline_date >= CURRENT_DATE) AND attachments IS NULL` — 마감된 공고는 카드에 안 뜨므로 크롤 제외(낭비 방지)
- **정렬/상한**: `ORDER BY created_at DESC LIMIT %s`(env `ATTACH_ENRICH_LIMIT`, 기본 150 — 경량 크롤이라 마감보강보다 작게). skip-done: `attachments IS NULL` 조건이 이미 재처리 방지.
- **동작**: 대상별 origin_url 크롤 → 첨부 probe·분류 → `attachments` 컬럼 기록(+ 4-1의 `has_application_form` 동시 기록).
- **결과**: 커버리지가 6건 → 기업 유효공고로 며칠에 걸쳐 확대. 신규 공고도 지속 처리.

> 주: 첨부 수집은 origin_url만 있으면 되며 분석완료 여부와 무관하다(분석과 별개 크롤). 분석 커버리지(기업 50%)는 "판정 가능성"의 근거였을 뿐, 이 스텝의 대상 조건은 origin_url이다.

### 4-1. 저장: `has_application_form` 컬럼 (ADD-only)
API·게이팅 편의를 위해 파생 boolean을 저장한다(리스트 엔드포인트가 많아 JSONB 매 행 파싱보다 컬럼이 단순).
- `ALTER TABLE announcements ADD COLUMN IF NOT EXISTS has_application_form BOOLEAN DEFAULT FALSE`
- **기록 시점**: `attachments`를 쓰는 지점(스텝 + `get_or_build`)에서 `has_application_form = (attachments에 신청서양식 존재)` 를 함께 UPDATE. attachments가 유일 소스이므로 동기화는 그 한 곳뿐.

## 5. API 변경

- 공고 리스트/매칭 응답에 `has_application_form`(boolean) 포함. (공개목록 SELECT에 deadline_type 추가했던 P0-2 패턴과 동일하게 컬럼 추가.)
- 버튼을 렌더하는 카드 경로(매칭 결과, 공개 목록)의 SELECT에 컬럼 포함.

## 6. 프론트 게이팅 (ResultCard)

- 조건 변경: `res.target_type !== "individual"` → `res.target_type !== "individual" && res.has_application_form`
- **모름(미수집=has_application_form FALSE/부재) → 버튼 없음** (사용자 선택 (가): "확인된 것만 표시").
- 인터페이스에 `has_application_form?: boolean` 추가.

## 7. SmartDoc 연동 (기존 유지)

버튼 클릭 → 기존 `window.dispatchEvent("open-smartdoc-modal", {announcement: res})` 유지. SmartDoc은 해당 공고 `attachments`의 신청서양식(hwp·docx·PDF) URL로 작성. **이 설계가 attachments를 채워주므로 SmartDoc이 실제 동작할 재료가 생긴다.**

## 8. 테스트 계획

1. **분류기 단위(RED→GREEN)**: `_classify_kind` — PDF 포함 확정 규칙 픽스처(신청서.pdf→신청서양식, 공고문.pdf→공고문, 키워드없는 x.pdf→신청서양식, 편집문서→신청서양식, 신청서.hwp→신청서양식).
2. **스텝 실DB 소량**: `enrich_attachments(limit=3)` 실행 → 대상 3건 attachments·has_application_form 채워짐 확인(롤백 트랜잭션).
3. **API**: 카드 리스트 응답에 `has_application_form` 포함 확인.
4. **프론트 게이팅**: has_application_form true/false/부재에 따른 버튼 유무 확인.

## 9. 정직한 한계

- `_classify_kind`는 파일명·포맷 휴리스틱 → 오분류 가능(키워드 없는 공고문 PDF false positive). 게이팅엔 충분하나 정밀하지 않음.
- 미수집(스텝 미도달) 공고는 신청서 있어도 버튼 안 뜸 → 스텝이 시간 두고 드레인.
- 경량이지만 origin_url 재크롤 비용 발생 → rate-limit(ATTACH_ENRICH_LIMIT)로 관리.
- 첨부 서버가 파일명을 깨서 보내면(probe의 broken-filename 폴백) 분류 정확도 저하 가능.

## 10. 구현 순서

| 단계 | 내용 | verify |
|---|---|---|
| 1 | `_classify_kind` PDF 포함 수정 + 단위테스트 | RED→GREEN |
| 2 | `has_application_form` 컬럼 마이그레이션(ADD-only) | init 후 information_schema 확인 |
| 3 | `enrich_attachments` 스텝 함수 + attachments·flag 동시기록 | 실DB 소량 실행(롤백) |
| 4 | daily_pipeline에 스텝 배선 | 스텝 호출 확인 |
| 5 | 카드 리스트 SELECT에 `has_application_form` 추가 | API 응답 확인 |
| 6 | ResultCard 게이팅 조건 + 인터페이스 | 프론트 렌더(있음/없음/모름) |
