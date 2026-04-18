# 일일 자동 파이프라인 설계

## 개요

매일 한국시간 새벽 03:00에 전체 자동 파이프라인을 **순차적으로 1회** 실행.
사용자가 안 쓰는 시간에 모든 무거운 작업을 완료하여, 아침 접속 시 최신 데이터 제공.

## 실행 시간

- **시작**: 매일 03:00 KST (UTC 18:00)
- **예상 소요**: 30분 ~ 1시간 (Gemini API 속도에 따라 변동)
- **완료 목표**: 07:00 KST 이전

## 파이프라인 순서

```
03:00 KST 시작
  │
  ├─ ① 공고 수집 (외부 API)
  ├─ ② 원본 기관 직접 크롤링
  ├─ ③ DB 정리
  ├─ ④ 공고 분석
  ├─ ⑤ 학습 전파 정리
  ├─ ⑥ 사전매칭 캐시 갱신
  ├─ ⑦ 오케스트레이터 (품질 체크 + 보고서)
  ├─ ⑧ 일일 다이제스트 발송
  ├─ ⑨ 구독/결제 관리
  │
  완료 → 결과 로그 저장
```

## 각 단계 상세

### ① 공고 수집 (외부 API)
- **담당**: `sync_service.sync_all()`
- **내용**: smes24, bizinfo, gov24, 지자체복지 등 API에서 신규 공고 수집
- **보강**: 지자체복지 상세 100건 + gov24 개인 상세 100건
- **소요**: 약 5~10분

### ② 원본 기관 직접 크롤링
- **담당**: `mss_scraper.crawl_and_store()` + `semas_scraper.sync_semas_knowledge()`
- **내용**:
  - 중기부(mss.go.kr) 사업공고 직접 수집 — 20건/일
  - 소진공(semas.or.kr) 공지사항 → knowledge_base 동기화
- **이유**: 기업마당 경유 시 원문 확보 불가 → 원본 기관에서 직접 PDF/HWPX 다운로드
- **소요**: 약 5~10분

### ③ DB 정리
- **담당**: `_cleanup_non_support_announcements()` + `_deduplicate_announcements()` + `_auto_classify_target_type()`
- **내용**:
  - 비지원사업 (정보성 게시물) 제거
  - 제목/URL 중복 공고 제거
  - 기업/개인 자동 분류 (target_type 태깅)
  - 만료 공고 마킹
- **소요**: 약 1~2분

### ④ 공고 분석
- **담당**: `discover_unanalyzed()` + `recover_failed_analyses()`
- **내용**:
  - 미분석 공고 발굴 → 분석 큐 등록 (100건)
  - 분석 큐에서 꺼내 실행 (100건) — PDF 파싱 + Gemini 구조화 분석
  - URL 헬스체크 + 최종 URL 해석
- **소요**: 약 10~20분 (Gemini API 속도 의존)

### ④-1. 원문 URL 추적 (경유지 → 원본)
- **담당**: `url_resolver.batch_resolve_final_urls()`
- **내용**: bizinfo 경유지 URL에서 "바로가기" 원본 URL 추출 → `final_url` 저장
- **대상**: bizinfo 4,169건 중 final_url 미확보 건 (매일 50건씩)
- **소요**: 약 2~3분

### ④-2. 외부 검색 학습
- **담당**: `url_resolver.search_and_learn()`
- **내용**: 분석 안 된 주요 공고 제목으로 Google 검색 → 보도자료/정책자료 → knowledge_base 저장
- **대상**: 자금/정책/R&D/창업 관련 미분석 공고 (매일 10건씩)
- **소요**: 약 3~5분 (Gemini + Google Search Grounding)

### ⑤ 학습 전파 정리
- **담당**: `propagate_learning()` (신규)
- **내용**:
  - 새로 추가된 지식에 source_agent 태그 확인/보정
  - 기업 지식 → 기업 카테고리, 개인 지식 → 개인 카테고리 정리
  - 임베딩 누락 knowledge_base 보강
  - 저품질 지식 (confidence < 0.3) 정리
  - 미활용 지식 (use_count=0, 30일 경과) 정리
- **소요**: 약 2~5분

### ⑥ 사전매칭 캐시 갱신
- **담당**: `_run_prematch_cache()`
- **내용**: 활성 유료 사용자의 매칭 결과를 user_match_cache에 미리 계산
- **이유**: 사용자 접속 시 즉시 결과 표시 (캐시 히트 0.7초)
- **소요**: 약 2~5분

### ⑦ 오케스트레이터 (품질 체크 + 보고서)
- **담당**: `run_daily_supervision()`
- **내용**:
  - 에이전트별 상담 건수/오류율 수집
  - 최근 상담 샘플링 → Gemini 품질 평가
  - 학습 파이프라인 건강 체크
  - 자동 개선 조치 (임베딩 보강 등)
  - 일일 보고서 생성 → 사장님 이메일 전송
- **소요**: 약 2~5분

### ⑧ 일일 다이제스트 발송
- **담당**: `notification_service.generate_daily_digest()`
- **내용**: 사용자별 맞춤 공고 이메일/푸시/카카오 발송 (평일만)
- **소요**: 약 3~5분

### ⑨ 구독/결제 관리
- **담당**: `_auto_renew_subscriptions()`
- **내용**: 만료된 구독의 빌링키 자동 결제 재시도
- **소요**: 약 1분

## 에러 처리

- 각 단계는 **독립적 try/except**로 감싸서, 한 단계 실패해도 다음 단계 실행
- 실패한 단계는 `system_logs`에 기록
- 오케스트레이터 보고서에 실패 단계 명시
- 크리티컬 에러 (DB 연결 불가 등) 시에만 전체 중단

## 구현 위치

| 파일 | 역할 |
|------|------|
| `backend/app/main.py` | 스케줄러 등록 (기존 3개 → 1개 통합) |
| `backend/app/services/patrol/daily_pipeline.py` | **신규** — 전체 파이프라인 실행기 |
| `backend/app/services/patrol/patrol_runner.py` | 기존 patrol 로직 (④에서 호출) |
| `backend/app/services/orchestrator/supervisor.py` | 오케스트레이터 (⑦에서 호출) |
| `backend/app/services/scrapers/mss_scraper.py` | 중기부 크롤러 (②에서 호출) |
| `backend/app/services/scrapers/semas_scraper.py` | 소진공 크롤러 (②에서 호출) |

## 모니터링

- 실행 결과: `system_logs` 테이블에 각 단계별 결과 저장
- 사장님 보고: 오케스트레이터 이메일에 파이프라인 실행 결과 포함
- 실패 알림: 크리티컬 에러 시 즉시 이메일 발송

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-18 | 초기 설계 — 기존 3개 스케줄러 통합 |
