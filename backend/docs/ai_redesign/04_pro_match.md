# 04 PRO 매칭 AI — 상세 설계

**기존 함수**: `chat_pro_consultant` (Mode A + Mode B 통합)
**핵심 변경**: **Mode A (정보 수집) 제거 → 폼으로 대체**. Mode B (매칭 후 상담)만 유지·강화.

---

## 1. 미션 (한 문장)

> **컨설턴트가 입력한 고객 프로필로 맞춤 공고를 매칭하고, 각 공고에 대한 심화 상담을 연속 수행하여 종합 보고서까지 이어준다.**

---

## 2. 진입 경로 (재설계)

```
[PRO 대시보드] → "🏢 지원사업 매칭 상담" 카드
                      ↓
            ┌─────────┴──────────┐
         [신규 고객]          [기존 고객 선택]
            │                     │
            ▼                     ▼
      [프로필 폼]          [client_profiles 조회]
            │                     │
            └──────┬──────────────┘
                   ▼
            [매칭 실행 버튼]
                   ↓
         [매칭 결과 리스트 표시]
                   ↓
      사용자가 공고 클릭 → [연속 상세 상담] (같은 세션)
                   ↓
         [📄 보고서 생성 버튼]
```

**기존 자연어 정보 수집 단계 제거** — 폼이 확정적으로 프로필 완성.

---

## 3. 성공 기준 (KPI)

| 지표 | 목표 | 측정 방법 |
|---|---|---|
| 매칭 공고 수 (평균) | 10건 이상 | 매칭 결과 COUNT |
| 매칭 관련성 (AI 평가) | 8/10 이상 | Gemini + OpenAI 이중 평가 |
| 세션당 상세 상담 공고 수 | 평균 2~3건 | messages에서 공고 전환 카운트 |
| 보고서 생성률 | 40% 이상 | 세션 중 보고서 생성 버튼 클릭 비율 |
| 정보 수집 실패율 | 0% | 폼 저장 검증 통과율 |
| 공고 추천 이유 명시율 | 100% | alternatives의 reason 필드 존재 |

---

## 4. 입력 Schema

### 4.1 신규 고객 (폼)

```python
{
  "action": "create_client_and_match",
  "client_profile": {
    # 필수
    "client_name": str,
    "industry_code": str,
    "address_city": str,           # 시도 (서울/경기/...)
    "revenue_bracket": str,
    "employee_count_bracket": str,
    "establishment_date": str,     # YYYY-MM-DD
    "interests": [str],            # 복수 선택
    # 선택 (우대·제외 판정)
    "business_number": str,
    "representative_age_range": str,
    "is_women_enterprise": bool,
    "is_youth_enterprise": bool,
    "certifications": [str],       # "벤처", "이노비즈", "사회적기업" 등
    "is_restart": bool,
    "memo": str
  }
}
```

### 4.2 기존 고객 (선택)

```python
{
  "action": "match_existing_client",
  "client_profile_id": int
}
```

### 4.3 매칭 후 상세 상담

```python
{
  "action": "consult_announcement",
  "session_id": str,
  "announcement_id": int,
  "messages": [{"role": "user" | "assistant", "text": str}]
}
```

---

## 5. 출력 Schema

### 5.1 매칭 결과 (action=match)

```json
{
  "type": "object",
  "required": ["session_id", "matched_announcements", "summary"],
  "properties": {
    "session_id": {"type": "string"},
    "client_profile_id": {"type": "integer"},
    "matched_announcements": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["announcement_id", "title", "match_reason", "bucket"],
        "properties": {
          "announcement_id": {"type": "integer"},
          "title": {"type": "string"},
          "department": {"type": "string"},
          "support_amount": {"type": "string"},
          "deadline_date": {"type": "string"},
          "match_reason": {"type": "string"},
          "bucket": {
            "type": "string",
            "enum": ["interest_match", "deadline_urgent", "qualified_other"]
          },
          "matched_interests": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "summary": {"type": "string", "description": "컨설턴트에게 매칭 결과 한 줄 요약"}
  }
}
```

### 5.2 상세 상담 응답 (action=consult)

```json
{
  "type": "object",
  "required": ["message", "verdict_for_client"],
  "properties": {
    "message": {"type": "string"},
    "verdict_for_client": {
      "type": "string",
      "enum": ["eligible", "conditional", "ineligible"]
    },
    "expert_insights": {
      "type": "object",
      "properties": {
        "selection_rate_estimate": {"type": "string"},
        "key_evaluation_points": {"type": "array", "items": {"type": "string"}},
        "common_pitfalls": {"type": "array", "items": {"type": "string"}},
        "similar_programs": {"type": "array", "items": {"type": "integer"}}
      }
    },
    "citations": {"type": "array", "items": {"type": "string"}},
    "choices": {"type": "array", "items": {"type": "string"}},
    "next_action": {
      "type": "string",
      "enum": ["wait_user", "next_announcement", "generate_report", "finish"]
    }
  }
}
```

**PRO 특화**: `expert_insights` 필드 — LITE에는 없음. 선정률·평가 포인트·실패 사례 등 전문가 레벨 정보.

---

## 6. 상태 기계 (FSM)

```
[폼 입력]
    ↓ 저장 완료
[매칭 실행]
    ↓ AI 매칭
[결과 제시]
    │
    ├── 공고 클릭 ───→ [상세 상담 모드]
    │                       │
    │                       ├── 다른 공고 클릭 ──→ [상세 상담 모드 (공고 전환)]
    │                       │
    │                       └── "보고서 만들기" ───→ [보고서 생성]
    │
    └── "재매칭" ────→ [조건 수정] → [매칭 실행] (반복)

[보고서 생성]
    ↓ PDF 완성
[종료 or 계속]
```

**Mode 전환은 action 파라미터로 명시**:
- `match`: 매칭 실행
- `consult`: 상세 상담
- `generate_report`: 보고서 생성

---

## 7. 프롬프트 구조 (consult 액션 시)

```
당신은 15년차 정부지원사업 전문 컨설턴트 "지원금AI"입니다.
컨설턴트가 고객을 위해 상담 중입니다 (답변 대상은 컨설턴트, 설명 주체는 고객사).

[오늘 날짜]
{today}

[고객 프로필]
{client_profile_formatted}

[현재 상담 공고]
공고 ID: {announcement_id}
공고명: {announcement_title}
자격 요건: {parsed_sections.eligibility}
지원 내용: {parsed_sections.support_details}
필수 서류: {parsed_sections.required_docs}
제외 조건: {deep_analysis.exclusion_rules}

[매칭된 다른 공고 (참고)]
{other_matched_summary}

[역할]
- 컨설턴트(사용자)에게 고객사에 대한 전문 답변
- 일반 정보 아닌 "실전 선정 관점"의 심화 정보 제공
- 답변에 expert_insights 필수

[답변 원칙]
1. 결론 먼저 (eligible/conditional/ineligible)
2. 근거는 [공고ID: N] 인용
3. 선정률·경쟁률·평가 포인트·흔한 실수 명시
4. 유사 사업 비교·대안 제시
5. 신청서 작성 꿀팁 (자격 심사 가중치 있는 섹션)

[답변 구조]
## 결론 — 한 줄
## 근거 — 공고 조건 vs 고객사 대조표
## 전문가 인사이트 (expert_insights 기반)
- 선정률 추정
- 평가 가중치 높은 항목
- 흔한 실수 / 함정
## 추천 다음 액션
- 신청서 작성 시 강조할 점
- 필요한 추가 자료
- 유사 대안 공고 (필요 시)

[금지]
- URL 노출
- "홈페이지 확인" 으로 끝
- 일반 상식으로 추측 (공고 원문 기반만)
- 범위 밖 대화
```

### 7.1 Few-shot (PRO 공고상담의 차별점)

**예시 1: 전문가 레벨 판정 + 인사이트**
```
user: "저희 고객 창업 2년차 IT 기업인데 창업성장기술개발사업 가능?"
✅ 모범 응답:
{
  "message": "## 결론\n**조건부 해당 (eligible, 단 준비 필수)** [공고ID: 3456]\n\n## 근거\n| 조건 | 기준 | 고객사 | 판정 |\n|---|---|---|---|\n| 창업 7년 이내 | ≤7년 | 2년 | ✅ |\n| 매출 10억 미만 | ≤10억 | 5억 | ✅ |\n| 기술개발 분야 | IT/SW | IT | ✅ |\n\n## 전문가 인사이트\n- 선정률 추정: 약 20% (2024년 기준, 신청 대비)\n- 평가 가중치 높은 섹션: '기술성(40%)' > '시장성(25%)'\n- 흔한 실수: 사업화 계획을 너무 모호하게 쓰면 탈락\n- 함정: 연차별 목표를 구체적 수치로 제시 안 하면 감점\n\n## 추천 액션\n- 신청서 '사업화 전략' 섹션에 3개년 매출 계획 구체화\n- 보유 특허·기술 인증 첨부 강력 권장\n- 유사 대안: 디딤돌 R&D [공고ID: 3457], 창업도약 [공고ID: 3458]",
  "verdict_for_client": "conditional",
  "expert_insights": {
    "selection_rate_estimate": "약 20%",
    "key_evaluation_points": ["기술성 40%", "시장성 25%", "사업화 전략 20%"],
    "common_pitfalls": ["모호한 사업화 계획", "연차 목표 미제시"],
    "similar_programs": [3457, 3458]
  },
  "citations": ["공고ID: 3456 자격 요건", "공고ID: 3456 평가 기준"],
  "choices": ["신청서 작성 팁 더 알려줘", "필요 서류 리스트", "디딤돌과 차이는?"],
  "next_action": "wait_user"
}
```

---

## 8. Tool 정의

### 8.1 매칭 단계 Tool
- `match_announcements(profile)` — 내부 매칭 엔진 (기존 `core/matcher.py`)
- `filter_by_profile(results, profile)` — 제외 규칙 적용

### 8.2 상세 상담 단계 Tool
- `get_announcement_detail(id)` — 12섹션 상세
- `analyze_announcement(id)` — 공고 원문 재분석 (데이터 부족 시)
- `check_eligibility(id, profile)` — 자격 판정 하드 규칙
- `search_similar_programs(announcement_id, profile)` — 유사 사업 탐색
- `estimate_selection_rate(announcement_id)` — 선정률 추정 (ai_consult_logs 통계 기반)

---

## 9. Post-processing 규칙

### 9.1 매칭 결과 후검증

```python
def validate_matches(results, profile):
    """AI 매칭 결과에 프로필 부적합 플래그 부착 (기존 Level 2 로직 유지)"""
    for r in results:
        # age/업력/매출 조건 위반 자동 탐지
        r["_profile_match"] = check_match(r, profile)
        if not r["_profile_match"]:
            r["_exclusion_reason"] = ...
    return sorted(results, key=lambda x: not x["_profile_match"])
```

### 9.2 expert_insights 보완

AI가 `selection_rate_estimate` 비우면 → DB 통계 기반 자동 생성:
```python
if not insights.get("selection_rate_estimate"):
    stats = estimate_selection_rate(announcement_id)
    insights["selection_rate_estimate"] = f"약 {stats['rate']}%"
```

---

## 10. 에러·예외 처리

| 상황 | 처리 |
|---|---|
| 폼 필수 필드 누락 | 저장 거부 + 어떤 필드 누락인지 반환 |
| 매칭 결과 0건 | "조건 완화 제안" + 인접 공고 제시 |
| `announcement_analysis` 데이터 없음 | 자동 분석 트리거 → 완료 후 재시도 |
| 기존 고객 ID 잘못 | 폼으로 폴백 |
| Schema 위반 반복 | OpenAI fallback |

---

## 11. 프런트엔드 UI 변화

### 11.1 진입 화면 (현재 2카드 유지)
- 🏢 지원사업 매칭 상담
- 📋 특정 공고 상담

### 11.2 🏢 클릭 시 — 고객 선택
```
[신규 고객 등록]  [기존 고객 목록]
```

### 11.3 신규 고객 폼 (신규 화면)
```
┌─────────────────────────────────────┐
│ 고객사 정보 입력                     │
├─────────────────────────────────────┤
│ 필수                                 │
│   고객사명: [______]                 │
│   업종:     [드롭다운]               │
│   지역:     [드롭다운]               │
│   매출:     [드롭다운]               │
│   직원수:   [드롭다운]               │
│   설립일:   [달력]                   │
│   관심분야: [☑ 정책자금 ☑ R&D ...]   │
│                                      │
│ 선택 (우대·제외 판정)                │
│   대표 연령: [드롭다운]              │
│   여성기업: [☑]                      │
│   청년기업: [☑]                      │
│   인증:     [☑ 벤처 ☑ 이노비즈 ...]  │
│   재창업:   [☑]                      │
│   메모:     [______]                 │
│                                      │
│       [저장 및 매칭 실행]            │
└─────────────────────────────────────┘
```

### 11.4 기존 고객 목록
```
- 홍길동컴퍼니 (IT, 경기, 매출 5억)  [선택] [편집]
- ABC전자 (제조, 서울, 매출 50억)    [선택] [편집]
- XYZ유통 (도소매, 부산, 매출 20억) [선택] [편집]
```

### 11.5 매칭 결과 화면 (기존 유지)
- 버킷별 그룹 (🎯 관심 일치 / ⏰ 마감 임박 / ✅ 참고)
- 각 공고 카드 클릭 → 상세 상담 모드

### 11.6 상세 상담 모드 (기존 유지)
- 채팅 UI
- 좌측 탭으로 현재 상담 중인 공고 표시
- 공고 전환 시 자연스럽게 맥락 이어짐

### 11.7 보고서 생성 버튼 (추가)
- 상담 모드 상단 고정: `📄 종합 보고서 생성`
- 클릭 → PDF 생성 후 다운로드

---

## 12. 구현 체크리스트

- [ ] 폼 UI 컴포넌트 (`NewClientForm.tsx`)
- [ ] `POST /api/pro/clients` 폼 저장 API 검증 강화
- [ ] Mode A 제거 (`chat_pro_consultant` 정보 수집 로직 삭제)
- [ ] `match_announcements(profile)` 단독 API 분리
- [ ] Mode B 응답 schema 강제
- [ ] `expert_insights` 생성 로직 (DB 통계 기반)
- [ ] 보고서 생성 버튼 + 연동 API
- [ ] 페르소나 테스트 3~5명

---

## 13. 테스트 페르소나 (제안)

| # | 페르소나 | 시나리오 | 검증 포인트 |
|---|---|---|---|
| 1 | 3년차 IT 기업 (기본) | 매칭 + R&D 공고 상담 | expert_insights 충실도 |
| 2 | 5년차 제조업 (다중 관심) | 매칭 + 3개 공고 연속 상담 | 공고 전환 시 맥락 유지 |
| 3 | 매출 200억 중견기업 | 매칭 (소상공인 제외 확인) | 제외 규칙 정확성 |
| 4 | 사회적기업 전환 중 | 특수 제도 상담 | 도메인 지식 깊이 |
| 5 | 재창업 + 예비인증 | 자격 복잡 케이스 | 조건부 판정 + 대안 |

각 페르소나 3회 실행 평균. 기존 5.4 대비 **7.0 목표**.

---

## 14. 기존 코드 변경 범위

| 파일 | 변경 |
|---|---|
| `chat_pro_consultant` (ai_consultant.py) | Mode A 제거, Mode B 강화 |
| `prompts/pro_business.py` | Mode A 섹션 삭제 → 최소 시스템 프롬프트로 |
| `prompts/pro_consult_tool.py` | expert_insights 섹션 추가 |
| `main.py` `/api/pro/consultant/chat` | action 파라미터 분기 |
| `main.py` `/api/pro/clients` | 폼 필드 확장 |
| `ProSecretary.tsx` | Mode A 자연어 수집 UI 제거, 폼 강화 |

---

## 15. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| 기존 사용자가 자연어 수집에 익숙 | 폼에 "바로 매칭 실행" 큰 버튼 + 빠른 입력 힌트 |
| 폼 필드가 너무 많아 입력 포기 | 필수 7개 / 선택 6개로 분리, 선택은 접기 |
| expert_insights DB 통계 부족 | "통계 데이터 축적 중" 대체 문구 + 공고 원문 기반 추론 |
| Schema 복잡도 증가 | 단계적 적용 (먼저 match 결과, 나중에 consult 응답) |

---

**다음 문서**: 05_pro_announce.md (PRO 공고상담 AI, LITE 공고상담의 PRO 버전)
