# 오케스트레이터 AI (AI COO) 설계 문서

## 1. 개요

지원금AI(govmatch.kr) 서비스의 전체 운영을 자율 감시하고, 이상 발견 시 사장님에게 보고하며, 승인된 지시를 실행하는 AI 관제 시스템.

```
[오케스트레이터 AI]
    │
    ├─ 자율 감시 (매일 자동)
    ├─ 이상 감지 → 즉시 보고
    ├─ 일일/주간 정기 보고
    ├─ 사장님 지시 수행 (승인 후)
    │
    ├── 자금 상담 AI ──┐
    ├── 공고 상담 AI ──┼── 지식 파이프라인
    └── 전문가 상담 AI ─┘
```

**핵심 원칙**: 자의적 판단으로 실행하지 않음. 반드시 보고 → 승인 → 실행.

---

## 2. 자율 감시 영역 (MECE)

### A. AI 에이전트 품질

| 지표 | 수집 방법 | 임계값 |
|------|----------|--------|
| 일일 상담 건수 | ai_consult_logs COUNT | 0건이면 경고 |
| 평균 응답 시간 | 로그 timestamp 차이 | 10초 초과 경고 |
| 오류 응답 비율 | reply에 "오류" "실패" 포함 건수 / 전체 | 10% 초과 경고 |
| choices 빈 배열 비율 | choices=[] 건수 / 전체 | 30% 초과 경고 |
| 사용자 피드백 점수 | ai_consult_feedback 평균 rating | 3.0 미만 경고 |
| Tool Calling 실패율 | 로그에서 tool error 카운트 | 20% 초과 경고 |

### B. 지식 파이프라인

| 지표 | 수집 방법 | 임계값 |
|------|----------|--------|
| 오늘 수집 공고 수 | announcements WHERE created_at >= today | 3일 연속 0건이면 경고 |
| PDF 크롤링 성공률 | announcement_analysis 존재 / 전체 공고 | 50% 미만 경고 |
| knowledge_base 총 건수 | COUNT(*) | 감소하면 경고 |
| 분석 완료 자금 공고 비율 | 자금 키워드 공고 중 analysis 있는 비율 | 30% 미만 경고 |
| 만료 공고 비율 | deadline < today / 전체 | 50% 초과 경고 |

### C. 인프라/서버

| 지표 | 수집 방법 | 임계값 |
|------|----------|--------|
| /health 응답 시간 | HTTP 체크 | 2초 초과 경고 |
| /api/match 응답 시간 | HTTP 체크 | 5초 초과 경고 |
| DB 커넥션 풀 사용률 | 풀 getconn 실패 로그 | 실패 발생 시 즉시 경고 |
| 에러 로그 건수 | 서버 로그에서 ERROR/Exception 카운트 | 시간당 50건 초과 경고 |
| Railway 배포 상태 | health 엔드포인트 연속 실패 | 3회 연속 실패 시 긴급 |

### D. 보안

| 지표 | 수집 방법 | 임계값 |
|------|----------|--------|
| 차단된 IP 수 | SecurityAgent._blocked_ips 카운트 | 50개 초과 시 보고 |
| 로그인 실패 건수 | event_log WHERE type='login_fail' | 시간당 20건 초과 경고 |
| Rate Limit 발동 건수 | event_log WHERE type='rate_limit' | 시간당 100건 초과 경고 |
| 비정상 스캔 감지 | BOT_BLOCKED 로그 | 일 10건 초과 보고 |

### E. 비즈니스 지표

| 지표 | 수집 방법 | 보고 주기 |
|------|----------|----------|
| 신규 가입 수 | users WHERE created_at >= today | 일일 |
| FREE → LITE 전환 수 | plan 변경 로그 | 일일 |
| LITE → PRO 전환 수 | plan 변경 로그 | 일일 |
| 이탈 (만료 후 미갱신) | plan_expires_at < today AND plan != 'free' | 주간 |
| 총 상담 건수 | ai_consult_logs | 일일 |
| 매출 (결제 건수/금액) | 결제 로그 | 주간 |
| DAU/WAU | event_log 고유 사용자 수 | 일일/주간 |

### F. 사용자 행동

| 지표 | 수집 방법 | 임계값 |
|------|----------|--------|
| 플로팅 버튼 클릭률 | 프론트 이벤트 로그 | 주간 추이 보고 |
| 상담 완료율 | 시작 vs done=true 비율 | 30% 미만 경고 |
| 공고 저장률 | saved_announcements / 조회수 | 주간 추이 |
| 검색 키워드 트렌드 | 검색 로그 집계 | 주간 보고 |
| 맞춤설정 완료율 | 프로필 완성도별 사용자 분포 | 주간 |

### G. 비용

| 지표 | 수집 방법 | 임계값 |
|------|----------|--------|
| Gemini API 호출 수 | 일일 카운트 (로그 집계) | 전주 대비 200% 초과 경고 |
| 예상 Gemini 비용 | 호출 수 × 단가 추정 | 월 예산 80% 도달 시 경고 |
| Railway 사용량 | Railway API (가능 시) | 한도 90% 경고 |
| Supabase DB 용량 | pg_database_size() | 한도 80% 경고 |

### H. 법률/컴플라이언스

| 항목 | 감시 방법 | 주기 |
|------|----------|------|
| 개인정보 저장 현황 | users 테이블 민감필드 카운트 | 월간 |
| 개인정보 접근 로그 | admin API 호출 이력 | 주간 |
| 이용약관 변경 필요 여부 | AI 기능 변경 시 자동 플래그 | 변경 시 |
| 데이터 보관 기간 | 오래된 상담 로그 (1년+) | 월간 |

### I. 외부 의존성

| 서비스 | 감시 방법 | 임계값 |
|--------|----------|--------|
| 카카오 OAuth | /api/auth/social/kakao 응답 코드 | 5xx 발생 시 경고 |
| 네이버 OAuth | /api/auth/social/naver 응답 코드 | 5xx 발생 시 경고 |
| Google OAuth | /api/auth/social/google 응답 코드 | 5xx 발생 시 경고 |
| bizinfo.go.kr | 크롤링 성공률 | 실패율 50% 초과 경고 |
| smes24 API | API 응답 상태 | 연속 실패 시 경고 |

### J. 콘텐츠 신선도

| 지표 | 수집 방법 | 임계값 |
|------|----------|--------|
| 최근 수집일 | MAX(created_at) FROM announcements | 3일 이상 미수집 경고 |
| 만료 공고 비율 | deadline < today / 전체 | 50% 초과 경고 |
| 지역별 공고 커버리지 | 시도별 공고 수 분포 | 특정 지역 0건 경고 |
| 인기공고(trending) 갱신일 | trending_announcements MAX(trending_date) | 3일 미갱신 경고 |

### K. 사장님이 놓칠 수 있는 영역

| 영역 | 설명 | 감시 방법 |
|------|------|----------|
| **재해 복구** | DB 백업 상태, 복구 테스트 | Supabase 백업 설정 확인 (월간) |
| **결제 정합성** | 결제 완료 but 플랜 미업그레이드 | payment 로그 vs users.plan 대조 (일일) |
| **이메일 발송 성공률** | 알림 이메일 반송/차단 | email_logs 성공/실패 비율 (일일) |
| **푸시 알림 도달률** | 구독 만료/토큰 무효 | push_subscriptions 유효성 (주간) |
| **SEO 순위** | 주요 키워드 검색 순위 변동 | Google Search Console (주간) |
| **경쟁사 동향** | 유사 서비스 출시/기능 변경 | 수동 체크 → 보고 (월간) |
| **캐시 무효화** | 사전매칭 캐시 정합성 | user_match_cache 갱신일 vs 공고 변경일 (일일) |
| **인증서/도메인** | SSL 만료, 도메인 갱신 | 만료일 30일 전 경고 |
| **API 키 만료** | Gemini, 카카오, 네이버 API 키 | 만료 예정 30일 전 경고 |

---

## 3. 글로벌 벤치마킹

| 프레임워크 | 핵심 기능 | 장점 | 단점 | 우리 적합성 |
|-----------|----------|------|------|:---:|
| **CrewAI** | 역할 기반 다중 에이전트 | 역할 분담 명확, Python 네이티브 | 오케스트레이션 복잡, 디버깅 어려움 | ⚠️ 과도 |
| **LangGraph** | 상태 기반 워크플로우 | 복잡한 분기/루프 지원, 체크포인트 | 학습 곡선 높음, LangChain 의존 | ⚠️ 과도 |
| **AutoGPT** | 자율 목표 달성 에이전트 | 자율성 높음 | 비용 폭발, 예측 불가, 프로덕션 부적합 | ❌ |
| **MS AutoGen** | 대화형 다중 에이전트 | 에이전트 간 협업 우수 | Azure 의존, 설정 복잡 | ⚠️ |
| **Google Vertex Agent** | 관리형 에이전트 빌더 | Google 생태계 통합, 관리 편함 | 비용 높음, 커스텀 제약 | ⭕ 부분 활용 |
| **Anthropic tool use** | 도구 호출 패턴 | 안정적, 예측 가능 | 자율 에이전트는 아님 | ⭕ |
| **OpenAI Assistants** | 스레드 기반 대화 + 도구 | 간편, 파일 분석 내장 | OpenAI 종속, 비용 | ⚠️ |
| **단순 스케줄러 + Gemini** | cron + DB 쿼리 + AI 요약 | 구현 간단, 비용 낮음, 디버깅 쉬움 | 자율성 낮음 | ✅ **최적** |

### 결론: "단순 스케줄러 + Gemini 분석" 방식이 최적

**이유:**
- 현재 서비스 규모(200명)에 CrewAI/LangGraph는 과도한 설계
- 자율 에이전트(AutoGPT)는 비용 폭발 + 예측 불가 → 프로덕션 부적합
- **현실적 방법: DB 쿼리로 지표 수집 → Gemini가 요약/분석 → 보고서 생성 → 카카오/이메일 전송**
- 서비스 성장 후 필요 시 LangGraph로 업그레이드 가능

---

## 4. 아키텍처 설계

```
[1. 수집]          [2. 분석]         [3. 보고]        [4. 지시]
매일 09:00 KST     Gemini 요약       카카오/이메일     사장님 응답
DB 쿼리 실행  →    이상 감지    →    보고서 전송  →   승인/지시
API 상태 체크      트렌드 비교       긴급 시 즉시     → 실행
로그 파싱          임계값 체크       정기: 일일/주간
```

### 4.1 데이터 수집 (매일 자동)

```python
# 의사 코드
def daily_health_check():
    report = {}
    
    # A. AI 품질
    report["ai"] = {
        "total_consults": db.count("ai_consult_logs WHERE created_at >= today"),
        "error_rate": db.count("errors") / db.count("total"),
        "avg_response_time": db.avg("response_time"),
    }
    
    # B. 파이프라인
    report["pipeline"] = {
        "new_announcements": db.count("announcements WHERE created_at >= today"),
        "analysis_coverage": db.count("announcement_analysis") / db.count("announcements"),
        "knowledge_count": db.count("knowledge_base"),
    }
    
    # C~K. 나머지 영역...
    
    return report
```

### 4.2 이상 감지

**규칙 기반** (Phase 1):
```python
alerts = []
if report["ai"]["error_rate"] > 0.1:
    alerts.append("AI 오류율 10% 초과")
if report["pipeline"]["new_announcements"] == 0:
    alerts.append("오늘 신규 공고 수집 0건")
if report["infra"]["health_response"] > 2.0:
    alerts.append("서버 응답 2초 초과")
```

**트렌드 비교** (Phase 2):
```python
# 전주 대비
if this_week["signups"] < last_week["signups"] * 0.5:
    alerts.append(f"가입 수 전주 대비 50% 감소")
```

### 4.3 보고

**채널:**
- **긴급 (즉시)**: 카카오톡 나에게 보내기 + 이메일
- **일일 (09:30 KST)**: 이메일 보고서
- **주간 (월요일 09:00)**: 종합 분석 보고서

**보고서 생성:**
```python
# 수집된 데이터를 Gemini에게 전달 → 자연어 보고서 생성
prompt = f"""
아래는 지원금AI 서비스의 오늘 운영 데이터입니다.
{json.dumps(report)}

사장님에게 보고할 일일 운영 보고서를 작성하세요.
- 핵심 요약 (3줄)
- 이상 징후 및 권장 조치
- 주요 지표 변화
"""
summary = gemini.generate(prompt)
send_kakao(summary)
send_email(summary)
```

### 4.4 명령 수행

**자동 실행 가능 (승인 불필요):**
- 일일 보고서 생성/발송
- 만료 공고 로그 기록
- 캐시 무효화
- 사전매칭 캐시 갱신

**승인 필요:**
- 프롬프트 수정
- 공고 데이터 삭제
- 사용자 플랜 변경
- 서버 설정 변경
- 비용 관련 변경

---

## 5. 보고서 포맷

### 일일 보고서 (09:30 카카오/이메일)

```
📊 지원금AI 일일 보고 (2026-04-17)

■ 핵심 요약
• 신규가입 3명 (LITE 전환 1명)
• 상담 28건 (전일 대비 +12%)
• 이상 감지 1건: PDF 크롤링 실패율 65%

■ AI 에이전트
• 자금상담 22건 | 공고상담 4건 | PRO상담 2건
• 평균 응답 3.2초 | 오류율 4%

■ 지식 파이프라인
• 신규 공고 12건 수집
• 분석 완료 8건 / 실패 4건 (bizinfo PDF)
• knowledge_base: 31건 (변동 없음)

■ 인프라
• 서버 응답: 평균 0.8초 (정상)
• DB 커넥션: 최대 8/10 사용 (여유)

■ 조치 필요
⚠️ PDF 크롤링 실패율 65% — bizinfo.go.kr 첨부 구조 변경 가능성
   → "크롤러 디버깅 진행할까요?"
```

### 긴급 알림

```
🚨 긴급: 서버 응답 없음

/health 엔드포인트 3회 연속 실패
마지막 응답: 2026-04-17 14:30 KST
Railway 배포 상태 확인 필요

→ "Railway 대시보드 확인하시겠습니까?"
```

### 주간 보고서 (월요일 이메일)

```
📈 주간 운영 보고 (4/11 ~ 4/17)

■ 비즈니스
• DAU 평균 45명 (전주 38명, +18%)
• 신규 가입 18명 | LITE 전환 4명
• 매출: 19,600원 (LITE 4건)

■ AI 품질 트렌드
• 상담 총 156건 (전주 132건, +18%)
• 오류율: 5.2% → 4.1% (개선)
• 사용자 만족도: 3.8/5.0

■ 파이프라인
• 공고 수집 67건 | 분석 완료 42건 (63%)
• PDF 실패: bizinfo 12건, 기타 13건

■ 비용
• Gemini API: ~$12 (전주 $9, +33%)
• 원인: 사전매칭 캐시 + 배치 분석

■ 다음 주 권장 조치
1. PDF 크롤러 수리 (품질 병목)
2. knowledge_base 50건 목표 확장
3. LITE 전환율 개선 (현재 22%)
```

---

## 6. 구현 단계

### Phase 1: MVP (1주)
**목표: 일일 자동 보고**

| 작업 | 내용 |
|------|------|
| health_check 함수 | DB 쿼리로 핵심 지표 수집 (A~E 영역) |
| 일일 스케줄러 | 기존 _daily_digest_loop에 추가 |
| 보고서 생성 | Gemini로 자연어 요약 |
| 카카오 전송 | 기존 send_kakao_message 활용 |
| 이메일 전송 | 기존 send_email 활용 |

**구현 방식:**
```python
# main.py에 추가
async def _daily_coo_report():
    while True:
        # 매일 09:30 KST (UTC 00:30) 실행
        await asyncio.sleep(until_target)
        report = collect_metrics()  # DB 쿼리
        alerts = detect_anomalies(report)  # 임계값 체크
        summary = generate_report(report, alerts)  # Gemini 요약
        await send_kakao(owner_bn, summary)
        send_email(owner_email, summary)
```

### Phase 2: 이상 감지 + 긴급 알림 (2주)
**목표: 실시간 이상 감지 → 즉시 보고**

| 작업 | 내용 |
|------|------|
| 트렌드 비교 | 전일/전주 대비 변화율 계산 |
| 긴급 알림 | 임계값 초과 시 즉시 카카오 전송 |
| 외부 의존성 체크 | OAuth/크롤링 사이트 상태 점검 |
| 비용 모니터링 | API 호출 카운터 + 예산 경고 |

### Phase 3: 명령 수행 + 학습 (1개월)
**목표: 사장님 지시 → 실행**

| 작업 | 내용 |
|------|------|
| 관리자 채팅 인터페이스 | "PDF 크롤러 상태 알려줘" → 즉시 응답 |
| 명령 실행 | "실패한 공고 재분석해" → 배치 실행 |
| 학습 루프 | 상담 피드백 → knowledge_base 자동 보강 |
| 주간 보고서 | 자동 생성 + 개선 제안 |

---

## 7. 빠뜨리기 쉬운 체크리스트

| # | 영역 | 설명 | 감시 필요 |
|---|------|------|:---:|
| 1 | DB 백업 | Supabase 자동 백업 설정 확인 | ✅ |
| 2 | 결제 정합성 | 결제 성공 but 플랜 미적용 케이스 | ✅ |
| 3 | 이메일 반송 | 알림 이메일이 스팸 처리되는 비율 | ✅ |
| 4 | 푸시 토큰 만료 | 구독은 있지만 토큰 무효인 비율 | ✅ |
| 5 | SSL 인증서 | govmatch.kr 인증서 만료일 | ✅ |
| 6 | 도메인 갱신 | 도메인 만료일 (보통 1년) | ✅ |
| 7 | API 키 로테이션 | Gemini/카카오/네이버 키 만료 | ✅ |
| 8 | 로그 용량 | event_log 테이블 크기 증가 추이 | ✅ |
| 9 | 중복 공고 | 같은 공고가 여러 번 수집된 비율 | ✅ |
| 10 | 사용자 데이터 정합성 | 프로필 NULL 비율, 고아 레코드 | ✅ |
| 11 | CORS/보안 헤더 | 프론트-백 통신 보안 설정 | ✅ |
| 12 | 모바일 호환성 | 특정 기기/브라우저 에러 비율 | ⚠️ 수동 |

---

## 8. 기술 선택 근거

**왜 복잡한 에이전트 프레임워크(CrewAI 등)를 쓰지 않는가:**

1. **규모**: 사용자 200명 서비스에 다중 에이전트 오케스트레이션은 과설계
2. **비용**: AutoGPT 방식은 API 비용이 예측 불가
3. **안정성**: 단순한 구조가 오류가 적고 디버깅이 쉬움
4. **확장성**: Phase 1은 cron + DB 쿼리 + Gemini 요약. 성장하면 LangGraph 도입

**현실적 구현:**
- 기존 `_daily_digest_loop` 패턴 재사용 (검증된 구조)
- DB 쿼리로 지표 수집 (새 API 의존 없음)
- Gemini로 보고서 생성 (이미 사용 중)
- 카카오/이메일 발송 (이미 구현됨)

**새로 만들어야 하는 것:**
- `collect_metrics()` 함수 (DB 쿼리 모음)
- `detect_anomalies()` 함수 (임계값 체크)
- `generate_coo_report()` 함수 (Gemini 프롬프트)
- 스케줄러 추가 (기존 패턴 복사)

---

## 9. 예상 효과

| Before | After |
|--------|-------|
| 사장님이 직접 서버/DB/로그 확인 | AI가 매일 자동 보고 |
| 문제 발생 후 사용자 불만으로 인지 | 이상 감지 → 사전 대응 |
| PDF 크롤링 실패를 모름 | 실패율 추적 → 즉시 알림 |
| API 비용 예측 불가 | 일일 비용 추적 + 예산 경고 |
| 상담 품질 측정 불가 | 오류율/만족도 자동 집계 |
