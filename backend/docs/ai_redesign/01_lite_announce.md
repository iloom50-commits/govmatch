# 01 LITE 공고상담 AI — 상세 설계

**기존 함수**: `chat_consult` (공고 모달에서 진입)

---

## 1. 미션 (한 문장)

> **유저가 선택한 공고에 대해 "나에게 해당되는가?"를 근거 기반으로 판정하고, 해당되지 않으면 대안을 제시한다.**

---

## 2. 진입 경로

```
[공고 목록] → 공고 카드 클릭 → 공고 상세 모달 → [AI 상담 시작] 버튼
                                                    ↓
                                    announcement_id 전달 + 유저 프로필 주입
                                                    ↓
                                           LITE 공고상담 AI 시작
```

---

## 3. 성공 기준 (KPI)

| 지표 | 목표 | 측정 방법 |
|---|---|---|
| 자격 판정 정확도 | 90% 이상 | 판정 결과를 실제 공고 조건과 대조 |
| 근거 명시율 | 95% 이상 | "왜" 설명에 `[공고ID: N]` 인용 포함 비율 |
| 대안 제시율 (미해당 시) | 80% 이상 | 해당 안 되는 공고에 대안 제안 |
| 평균 턴 수 | 3~5턴 | 불필요한 대화 반복 최소화 |
| 범위 밖 질문 응대 일관성 | 100% | "저는 지원사업 전문 상담사입니다" |

---

## 4. 입력 Schema

```python
{
  "announcement_id": int,          # 선택된 공고 ID (필수)
  "user_profile": {                # DB에서 자동 주입
    "user_type": "individual | business | both",
    "address_city": str,
    "interests": str,              # 콤마 구분
    # 기업
    "industry_code": str,
    "establishment_date": str,     # YYYY-MM-DD
    "revenue_bracket": str,
    "employee_count_bracket": str,
    # 개인
    "age_range": str,
    "income_level": str,
    "family_type": str,
    # ...
  },
  "messages": [
    {"role": "user" | "assistant", "text": str}
  ]
}
```

---

## 5. 출력 Schema (Gemini `response_schema` 강제)

```json
{
  "type": "object",
  "required": ["message", "verdict", "next_action"],
  "properties": {
    "message": {
      "type": "string",
      "description": "사용자에게 보여줄 답변 (마크다운)"
    },
    "verdict": {
      "type": "string",
      "enum": ["eligible", "conditional", "ineligible", "undetermined"],
      "description": "자격 판정 결과"
    },
    "reasoning": {
      "type": "object",
      "properties": {
        "matched_conditions": {"type": "array", "items": {"type": "string"}},
        "missing_conditions": {"type": "array", "items": {"type": "string"}},
        "citations": {"type": "array", "items": {"type": "string"}}
      }
    },
    "alternatives": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "announcement_id": {"type": "integer"},
          "reason": {"type": "string"}
        }
      },
      "description": "미해당 시 대안 공고 (최대 3개)"
    },
    "choices": {
      "type": "array",
      "items": {"type": "string"},
      "description": "사용자 다음 질문 제안 (최대 3개)"
    },
    "extracted_info": {
      "type": "object",
      "description": "대화에서 새로 발견한 프로필 정보 (DB 저장용)"
    },
    "next_action": {
      "type": "string",
      "enum": ["wait_user", "search_alternatives", "detail_section", "finish"]
    }
  }
}
```

**핵심**: `verdict`는 enum 강제 → AI가 애매한 답변 불가.

---

## 6. 상태 기계 (FSM)

```
[시작]
   ↓ AI 첫 응답 (공고 분석 + 프로필 대조)
[판정]
   ├─ eligible → [심화 질문 대기]
   ├─ conditional → [조건 확인 질문]
   ├─ ineligible → [대안 제시]
   └─ undetermined → [추가 정보 질문]

[심화 질문 대기]
   ↓ 사용자 질문
[상세 답변] (get_announcement_detail 호출)

[대안 제시]
   ↓ 사용자가 대안 클릭
[대안 공고로 새 세션 시작]
```

**코드에 명시**:
```python
def decide_next_state(verdict, user_msg, ctx):
    if verdict == "eligible" and "어떻게 신청" in user_msg:
        return "detail_section"
    if verdict == "ineligible" and not ctx.alternatives_shown:
        return "search_alternatives"
    # ...
```

---

## 7. 프롬프트 구조 (system_instruction)

### 7.1 뼈대 (목표: 500~700 토큰)

```
당신은 정부 지원사업 상담사 "지원금AI"입니다.

[역할]
유저가 선택한 특정 공고에 대해 "해당 유저가 받을 수 있는가?"를 판정합니다.

[현재 상담 공고]
공고 ID: {announcement_id}
공고명: {announcement_title}
주관기관: {department}

[자격 요건 (공고 원문 기반)]
{parsed_sections.eligibility}

[제외 조건]
{deep_analysis.exclusion_rules}

[유저 프로필]
{profile_ctx}

[오늘 날짜]
{today}

[답변 프로세스]
1. 공고 자격 요건 ↔ 유저 프로필 대조
2. verdict 결정 (eligible/conditional/ineligible/undetermined)
3. 근거를 citations에 명시 ([공고ID: N] 형식)
4. 미해당이면 alternatives에 대안 공고 ID 리스트
5. 자연어 message는 친절·명확하게

[금지]
- 공고 원문에 없는 조건 추측
- URL 노출
- "홈페이지에서 확인" 으로 끝내기
- 범위 밖 대화 (해당 시: "저는 지원사업 전문 상담사입니다")

[반드시]
- 모든 주장은 [공고ID: N] 인용
- 유저 프로필과 맞지 않는 조건은 "missing_conditions"에 명시
```

### 7.2 Few-shot 예시 (프롬프트에 삽입)

**예시 1: eligible**
```
상황: 창업 2년차 IT 기업 + "청년창업사관학교" 공고
user: "저 이거 받을 수 있을까요?"
✅ 모범 응답:
{
  "message": "네, 귀사는 해당 공고 대상입니다.\n\n### 충족 조건\n- 창업 3년 이하: 귀사 2년차 [공고ID: 1234]\n- 업종: IT는 대상 업종 [공고ID: 1234]\n\n다음 단계 안내 드릴까요?",
  "verdict": "eligible",
  "reasoning": {
    "matched_conditions": ["창업 3년 이하", "대상 업종 IT"],
    "missing_conditions": [],
    "citations": ["공고ID: 1234 자격 요건"]
  },
  "choices": ["신청 서류 알려주세요", "언제까지 신청?", "다른 공고도 볼래요"],
  "next_action": "wait_user"
}
```

**예시 2: ineligible + 대안 제시**
```
상황: 매출 100억 중견기업 + "소상공인 정책자금" 공고
user: "저희 이거 신청 가능?"
✅ 모범 응답:
{
  "message": "죄송하지만 귀사는 해당 공고 대상이 아닙니다.\n\n### 미해당 사유\n- 소상공인 전용: 귀사 매출 100억 (소상공인 기준 연매출 10억 이하 초과)[공고ID: 5678]\n\n대안으로 중견기업 대상 공고를 제안드립니다...",
  "verdict": "ineligible",
  "reasoning": {
    "matched_conditions": [],
    "missing_conditions": ["소상공인 매출 기준 10억 이하"],
    "citations": ["공고ID: 5678 지원 대상"]
  },
  "alternatives": [
    {"announcement_id": 9012, "reason": "중견기업 R&D 지원"},
    {"announcement_id": 9013, "reason": "중견기업 수출 바우처"}
  ],
  "next_action": "search_alternatives"
}
```

**예시 3: 범위 밖 질문**
```
user: "오늘 날씨 어때요?"
✅ 모범 응답:
{
  "message": "저는 정부 지원사업 전문 상담사입니다. 지금 보고 계신 공고(청년창업사관학교)에 대해 궁금한 점을 물어봐 주시면 정확히 안내드리겠습니다.",
  "verdict": "undetermined",
  "reasoning": {},
  "choices": ["자격 요건 알려주세요", "신청 절차 알려주세요", "마감일 언제?"],
  "next_action": "wait_user"
}
```

---

## 8. Tool 정의

이 AI는 **공고가 이미 확정됐으므로 검색 도구 불필요**. 다만:

- `get_announcement_detail(id)` — 필요 시 12섹션 상세 조회
- `search_alternatives(profile, excluded_reason)` — 대안 공고 탐색 (verdict=ineligible 시)

**Tool 호출은 최소화** — 대부분 시스템 프롬프트에 이미 공고 정보 주입됨.

---

## 9. Post-processing 규칙

### 9.1 대화에서 프로필 정보 추출

```python
def extract_from_lite_announce(user_text: str, ai_extracted: dict) -> dict:
    result = dict(ai_extracted)
    # "저희 매출 5억" → revenue_bracket
    if "revenue_bracket" not in result:
        if re.search(r"매출\s*(\d+)\s*억", user_text):
            # 구간 매핑
            ...
    # "설립 3년" → establishment_date (역산)
    # "직원 10명" → employee_count_bracket
    return result
```

### 9.2 verdict 검증

**코드 레벨 교차 검증**:
```python
def verify_verdict(verdict, user_profile, announcement):
    """AI 판정을 하드 규칙으로 재확인."""
    # 예: 소상공인 전용인데 매출 10억 초과 → ineligible 강제
    if "소상공인" in announcement["title"]:
        rev = parse_revenue(user_profile["revenue_bracket"])
        if rev and rev > 1_000_000_000:
            return "ineligible"
    # 예: 청년(만34세) 대상인데 프로필 40대 이상
    if "청년" in announcement["title"]:
        if user_profile.get("age_range") in ["40대", "50대", "60대 이상"]:
            return "ineligible"
    return verdict  # AI 판정 그대로
```

**AI 판정과 하드 규칙 결과 다르면 → 하드 규칙 우선**.

---

## 10. 에러·예외 처리

| 상황 | 처리 |
|---|---|
| announcement_id 유효하지 않음 | "공고 정보를 찾을 수 없습니다" + 공고 목록 복귀 |
| `announcement_analysis`에 데이터 없음 | `analyze_and_store` 자동 호출 후 재시도 |
| Gemini schema 위반 | 프롬프트 간소화 재시도 (2회) → OpenAI fallback |
| 사용자 플랜 한도 초과 | 친절한 업그레이드 안내 |

---

## 11. 구현 체크리스트

- [ ] 출력 schema 정의 (`lite_announce_schema.py`)
- [ ] system_instruction 작성 (뼈대 + few-shot 3개)
- [ ] `verify_verdict` 하드 규칙 구현
- [ ] `search_alternatives` tool 구현
- [ ] FSM 상태 전이 로직 (`lite_announce_fsm.py`)
- [ ] Post-processing 추출기 연결
- [ ] 페르소나 테스트 3명

---

## 12. 테스트 페르소나 (제안)

| # | 페르소나 | 시나리오 | 검증 포인트 |
|---|---|---|---|
| 1 | 30대 IT 창업자 (2년차) + 청년창업사관학교 | "이거 저 받을 수 있나요?" | eligible 정확 판정 + 신청 절차 |
| 2 | 60대 카페 주인 + 청년임차보증금 | "저도 받을 수 있죠?" | ineligible + 대안 제시 |
| 3 | 매출 50억 중견 + 소상공인 정책자금 | "신청 가능합니까?" | 하드 규칙으로 ineligible 강제 |

각 페르소나 3회 실행 평균 점수 측정.
