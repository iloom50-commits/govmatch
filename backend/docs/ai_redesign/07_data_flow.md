# 07 Data Flow — 정보 수집·저장·활용 플로우

**목적**: 모든 AI가 공유하는 **데이터 계층**을 먼저 확정한다. 각 AI 설계는 이 계층 위에 얹힌다.

---

## 1. 데이터 소스 (DB 테이블)

### 1.1 핵심 테이블

| 테이블 | 역할 | 사용 AI |
|---|---|---|
| `users` | LITE 유저 프로필 | ① LITE 공고상담 / ② LITE 정책자금 |
| `client_profiles` | PRO 고객 프로필 (컨설턴트가 관리) | ④ PRO 매칭 / ⑤ PRO 공고상담 |
| `ai_consult_logs` | 상담 대화 이력 | 전체 |
| `pro_consult_sessions` | PRO 세션 상태 (phase/collected/matched) | ④ PRO 매칭 / ⑤ PRO 공고상담 |
| `announcements` + `announcement_analysis` | 공고 정보·분석 결과 | 전체 |
| `client_reports` | 생성된 보고서 저장 | ③ LITE 보고서 / ⑥ PRO 보고서 |

### 1.2 프로필 스키마

#### `users` (LITE)
```
-- 공통
user_type: 'individual' | 'business' | 'both'
email, address_city, interests (관심분야 콤마 구분)

-- 기업 필드
company_name, business_number, industry_code, establishment_date,
revenue_bracket, employee_count_bracket, certifications, custom_keywords

-- 개인 필드
age_range, income_level, family_type, employment_status, housing_status, gender
```

#### `client_profiles` (PRO)
```
owner_business_number (컨설턴트의 bn),
client_name, business_number (고객사 사업자번호),
establishment_date, address_city, industry_code, industry_name,
revenue_bracket, employee_count_bracket, interests, memo
```

**구조적 차이**:
- `users`는 "나 자신의 프로필"
- `client_profiles`는 "컨설턴트가 관리하는 여러 고객 프로필"

---

## 2. 정보 수집 전략 (LITE vs PRO)

### 2.1 LITE 수집 전략: **기존 프로필 + 대화 보완**

**현황 (이전 조사)**:
- 기업 필드: 52~73% 채움
- 개인 필드: 19~23% 채움
- `interests`: 28% (매칭 핵심인데 낮음)

**전략**:
```
1. 상담 시작 → DB에서 users 조회
2. 채워진 필드는 그대로 활용 (profile_ctx에 주입)
3. 누락 필드 중 [필수] 2~3개만 자연어로 보완 질문
   예: "관심 분야를 알려주세요 (주거/취업/창업 등)"
4. 얻은 답은 즉시 users 테이블에 UPDATE (저장)
5. 다음 상담 시부터는 이미 채워져 있음 (누적)
```

**[필수] 필드 정의**:
- 기업: `industry_code`, `address_city`, `revenue_bracket`, `interests`
- 개인: `age_range`, `address_city`, `interests`, `family_type` 또는 `employment_status`

### 2.2 PRO 수집 전략: **폼 기반 (자연어 대화 없음)**

**이유**:
- 컨설턴트는 고객 정보 외워서 입력 가능
- 자연어 추출 실패 리스크 0
- 빠른 입력 (5초~1분)
- 보고서 정확성 담보

**플로우**:
```
1. 컨설턴트: [신규 고객] 또는 [기존 고객 선택]
2. 폼 노출 (필수 필드 + 선택 필드 구분)
3. 폼 저장 → client_profiles 테이블 INSERT/UPDATE
4. 매칭 트리거 버튼 클릭 → 완성된 프로필로 매칭 진행
```

**폼 필드**:
```
[필수]
- 고객사명
- 업종 (드롭다운)
- 지역 (시도)
- 매출 구간 (드롭다운)
- 직원 수 구간 (드롭다운)
- 설립일 (달력)
- 관심 분야 (복수 선택)

[선택 — 우대/제외 판정에 필요]
- 대표자 연령대
- 여성 기업 여부
- 청년 기업 여부
- 벤처/이노비즈 인증
- 사회적기업 여부
- 재창업 여부
- 메모
```

---

## 3. AI 응답 구조화 파이프라인

### 3.1 3단계 구조

```
AI 응답
   ↓
① Schema 강제 검증 (Gemini API 레벨)
   ↓
② 코드 Post-processing (NER + 정규식)
   ↓
③ DB 저장 (실패 시 재시도)
```

### 3.2 ① Schema 강제 (Gemini API)

**모든 AI 응답에 공통 schema 적용**:

```python
# 예: LITE 자금 상담 응답 schema
{
    "type": "object",
    "required": ["message", "next_action"],
    "properties": {
        "message": {"type": "string"},
        "choices": {"type": "array", "items": {"type": "string"}},
        "extracted_info": {                    # ← AI가 대화에서 발견한 정보
            "type": "object",
            "properties": {
                "age_range": {"type": "string"},
                "address_city": {"type": "string"},
                "interests": {"type": "array", "items": {"type": "string"}},
                "industry_code": {"type": "string"},
                # ...
            }
        },
        "next_action": {
            "type": "string",
            "enum": ["ask_more", "search", "detail", "finish"]
        }
    }
}
```

**효과**:
- `message` 없이 응답 불가 → 빈 응답 방지
- `extracted_info` 필드 강제 → AI가 추출한 정보 무조건 반환
- `next_action` enum 강제 → 상태 전이 결정이 항상 일관

### 3.3 ② 코드 Post-processing

**AI가 놓친 정보를 코드가 보완**:

```python
def extract_info_from_text(user_text: str, ai_extracted: dict) -> dict:
    """AI 추출 정보 + 정규식 추출 병합"""
    result = dict(ai_extracted)

    # 연도 추출
    if "establishment_date" not in result:
        if m := re.search(r"(\d{4})년", user_text):
            result["establishment_date"] = f"{m.group(1)}-01-01"

    # 지역 추출 (주요 키워드)
    REGIONS = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
               "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
    if "address_city" not in result:
        for r in REGIONS:
            if r in user_text:
                result["address_city"] = r
                break

    # 업력/매출/직원 수
    # ...

    return result
```

**원칙**: AI가 추출하면 그대로, 놓치면 코드가 보완. **이중 안전망**.

### 3.4 ③ DB 저장

**대화 중 얻은 정보는 즉시 저장**:
```python
def save_extracted_info(user_bn: str, extracted: dict, db_conn):
    """대화에서 얻은 정보를 users 테이블에 UPDATE"""
    if not extracted:
        return

    # 채워지지 않은 필드만 UPDATE (기존 값 덮어쓰지 않음)
    set_clauses = []
    params = []
    for field, value in extracted.items():
        set_clauses.append(f"{field} = COALESCE({field}, %s)")  # NULL일 때만
        params.append(value)

    if set_clauses:
        params.append(user_bn)
        db_conn.cursor().execute(
            f"UPDATE users SET {', '.join(set_clauses)} WHERE business_number = %s",
            params
        )
        db_conn.commit()
```

**원칙**:
- `COALESCE` 사용 → 기존 값 보존, NULL일 때만 채움
- 사용자가 명시적으로 "수정" 하면 덮어쓰기 (별도 플로우)

---

## 4. 대화 세션 관리

### 4.1 session_id 전략

- **첫 메시지 해시**: `session_id = "lite_" + sha256(bn + first_message)[:16]`
- 같은 질문 재질문 시 같은 session_id → 이어서 대화
- 다른 주제 시작 시 새 session_id

### 4.2 상태 전이 (FSM)

**LITE 정책자금 AI 예**:
```
[수집 전]       (필수 필드 부족)
    ↓  필수 필드 확보
[니즈 파악]     (어떤 자금?)
    ↓  "정책자금/R&D/..." 선택
[검색]          (search_fund_announcements)
    ↓  결과 있음
[제시]          (리스트 표시)
    ↓  사용자 피드백
[심화]          (특정 공고 상세) or [재검색] or [종료]
```

**전이는 코드가 결정**:
```python
def decide_next_state(current_state, user_input, extracted, search_results):
    if current_state == "수집_전":
        if all_required_filled(profile, extracted):
            return "니즈_파악"
        return "수집_전"  # 계속 수집
    # ...
```

**프롬프트에 맡기지 않음**. FSM이 코드에 명시됨.

### 4.3 세션 데이터 저장

**PRO 세션** (`pro_consult_sessions`):
```
session_id, business_number (컨설턴트), client_profile_id (고객),
client_category, current_step, collected (JSON), phase,
matched_snapshot (JSON), messages (JSON), created_at, updated_at
```

**LITE 세션** (`ai_consult_logs`):
```
session_id, business_number, announcement_id (공고상담만),
messages (JSON), conclusion, created_at, updated_at
```

---

## 5. 상담 결과 → 보고서 데이터 파이프라인

### 5.1 보고서 생성에 필요한 데이터

**③ LITE 보고서 / ⑥ PRO 보고서 공통 소스**:
- 사용자/고객 프로필 (users 또는 client_profiles)
- 상담 대화 (ai_consult_logs.messages 또는 pro_consult_sessions.messages)
- 언급된 공고들 (announcements + announcement_analysis)
- 매칭 결과 (pro_consult_sessions.matched_snapshot)
- AI 결론 (ai_consult_logs.conclusion)

### 5.2 보고서 생성 플로우

```
1. 사용자 "📄 보고서 만들기" 버튼 클릭
2. API: POST /api/{lite|pro}/reports/generate
3. 백엔드:
   a) 세션 ID로 대화·프로필·공고 정보 모음
   b) 템플릿 선택 (lite_brief.j2 또는 pro_full.j2)
   c) Gemini로 요약·정리 (단일 호출, 수 초)
   d) PDF 변환 (weasyprint/puppeteer)
   e) client_reports 테이블 저장
4. 사용자에게 다운로드 링크 or 이메일 발송
```

### 5.3 LITE vs PRO 보고서 차이

| 항목 | LITE (brief) | PRO (full) |
|---|---|---|
| 페이지 | 1~2장 | 5~10장 |
| 섹션 | 간단 요약만 | 12섹션 보고서급 |
| 수신자 | 본인 | 고객 (컨설턴트 → 고객) |
| 브랜딩 | govmatch 로고 | 컨설턴트 회사 로고 옵션 |
| 출력 | 웹 페이지 + PDF | PDF 전용 |
| 편집 가능 | 불가 | 가능 (컨설턴트가 수정 후 전달) |

---

## 6. 프로필 완성도 추적 (LITE 전용)

### 6.1 완성도 계산

```python
def calculate_profile_completeness(user: dict) -> float:
    """0.0 ~ 1.0"""
    is_biz = user.get("user_type") in ("business", "both")
    required = (
        ["industry_code", "address_city", "revenue_bracket", "interests"]
        if is_biz else
        ["age_range", "address_city", "interests", "family_type"]
    )
    filled = sum(1 for f in required if user.get(f))
    return filled / len(required)
```

### 6.2 완성도 기반 UX

**대시보드 배지**:
- < 50%: 🚨 "프로필 완성도 {N}% — 정확한 매칭을 위해 입력 필요"
- 50~80%: ⚠️ "프로필 {N}% — 몇 가지만 더!"
- > 80%: ✅ "프로필 완성"

**상담 시작 시**:
- < 50%: 상담 시작 전 **필수 2~3 필드 인터뷰**
- 50~80%: 상담 중 자연스럽게 수집
- > 80%: 바로 상담 시작

---

## 7. 데이터 일관성 보장

### 7.1 대화 중 갱신된 정보의 전파

**시나리오**: 유저가 상담 중 "저희 이제 매출 5억 됐어요" → 프로필 업데이트

```
1. AI 응답에 extracted_info.revenue_bracket = "1억~5억" 포함
2. Post-processing으로 확인·보완
3. users 테이블 UPDATE (기존 값이 다르면 덮어쓰기)
4. 이번 상담부터 새 매출로 검색
5. 다음 상담 시작 시 새 값 자동 주입
```

### 7.2 충돌 해결

**기존 DB 값 vs 새 대화 값이 다를 때**:
- 사용자가 "수정" 명시 → 덮어쓰기
- 단순 언급 → 기존 값 우선 (COALESCE)
- 애매 → 사용자에게 확인 질문

---

## 8. 에러·예외 처리

### 8.1 AI 응답 schema 위반
- Gemini가 schema 거부 시: 프롬프트 간소화해서 재시도 (최대 2회)
- 계속 실패: OpenAI fallback

### 8.2 DB 저장 실패
- 대화는 계속 (사용자 경험 우선)
- 로그 남김 (`system_logs.category = 'data_save_fail'`)
- 다음 상담 시 동일 정보 재수집 시도

### 8.3 프로필 불일치
- 가입 시 기업 → 상담에서 개인 얘기: 안내 후 유형 전환 제안

---

## 9. 이 데이터 플로우가 해결하는 문제

| 문제 | 해결 방법 |
|---|---|
| B1: "2019년 설립" 저장 실패 | Schema `extracted_info` 강제 + 정규식 post-processing |
| B2: 60대 → 청년 대출 추천 | Tool 레벨 필터 (기존 Level 1+2, 유지) |
| LITE 프로필 28%만 interests | 상담 중 수집 + DB 즉시 저장 → 누적 |
| PRO 정보 수집 불안정 | 폼 도입 → 100% 구조화 |
| 세션 중간 종료·재개 | session_id 해시 기반 + DB persist |
| 보고서 생성 데이터 소스 불명확 | 본 문서 5절에 명시 |

---

## 10. 구현 우선순위

### Level 0: 기반 (필수)
- [ ] `ai_schemas.py` — 공통 Schema 정의
- [ ] `profile_extractor.py` — NER/정규식 추출기
- [ ] `profile_updater.py` — DB 저장 헬퍼 (COALESCE 기반)
- [ ] `fsm.py` — 상태 기계 엔진

### Level 1: LITE 통합
- [ ] 프로필 완성도 API (`GET /api/user/profile/completeness`)
- [ ] 대시보드 배지 UI
- [ ] LITE 상담 시작 시 필수 필드 체크
- [ ] 대화 중 `extracted_info` → DB 저장 연결

### Level 2: PRO 폼
- [ ] 고객 프로필 폼 UI 강화 (필수/선택 구분)
- [ ] 기존 고객 불러오기 개선
- [ ] 폼 제출 → client_profiles 저장 검증
- [ ] PRO 매칭 엔트리포인트 → 자연어 수집 제거

### Level 3: 보고서 연동
- [ ] 보고서 데이터 수집기 (`report_data_collector.py`)
- [ ] Jinja2 템플릿 (`lite_brief.j2`, `pro_full.j2`)
- [ ] PDF 변환 통합

---

**다음 문서**: 각 AI별 상세 설계 (01_lite_announce, 02_lite_fund, 04_pro_match, 05_pro_announce)
