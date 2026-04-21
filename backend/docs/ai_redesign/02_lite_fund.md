# 02 LITE 정책자금 AI — 상세 설계

**기존 함수**: `chat_lite_fund_expert`

---

## 1. 미션 (한 문장)

> **유저의 자금 니즈(운전자금·시설자금·정책자금·보증 등)에 맞는 공고를 검색·비교하여 추천한다.**

---

## 2. 진입 경로

```
[대시보드] → [자유상담 탭] → "정책자금 상담" 선택
     ↓
  기존 프로필 조회 (users)
     ↓
LITE 정책자금 AI 시작 (누락 필드 보완 인터뷰 optional)
```

---

## 3. 성공 기준 (KPI)

| 지표 | 목표 | 측정 |
|---|---|---|
| 추천 공고 관련성 | 8/10 이상 | AI 교차 평가 |
| 평균 추천 개수 | 3~5개 | 과다 나열 방지 |
| 선택지 사용률 | 40% 이상 | 유저가 choices 클릭 비율 |
| 중복 추천 (연속 턴) | 0 | 이미 언급한 공고 재나열 금지 |
| 범위 밖 응대 일관성 | 100% | "저는 정책자금 전문 상담사입니다" |

---

## 4. 입력 Schema

```python
{
  "messages": [{"role", "text"}],
  "user_profile": {...},  # 기존 users 조회 결과
  "mode": "business_fund" | "individual_fund"
}
```

---

## 5. 출력 Schema (Gemini `response_schema`)

```json
{
  "required": ["message", "phase", "next_action"],
  "properties": {
    "message": {"type": "string"},
    "phase": {
      "type": "string",
      "enum": ["collect", "needs", "recommend", "detail", "compare"]
    },
    "recommended_announcements": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["announcement_id", "why_fit"],
        "properties": {
          "announcement_id": {"type": "integer"},
          "title": {"type": "string"},
          "why_fit": {"type": "string"},
          "support_amount": {"type": "string"},
          "interest_rate": {"type": "string"},
          "deadline": {"type": "string"}
        }
      }
    },
    "extracted_info": {"type": "object"},
    "choices": {"type": "array", "items": {"type": "string"}},
    "next_action": {
      "type": "string",
      "enum": ["ask_profile", "ask_needs", "search", "detail", "compare", "finish"]
    }
  }
}
```

---

## 6. 상태 기계 (FSM)

```
[collect]   ← 프로필 필수 필드 부족
   ↓
[needs]     ← 어떤 자금? (운전/시설/정책/보증)
   ↓
[recommend] ← search_fund_announcements 호출 + 3~5개 추천
   ↓
[detail]    ← 특정 공고 상세 요청
   ↓
[compare]   ← 2~3개 비교표
   ↓
[finish]    ← 사용자 만족 종료
```

**전이 조건 (코드)**:
- collect → needs: 필수 필드(industry_code, revenue_bracket, address_city) 전부 채워짐
- needs → recommend: `fund_type` 결정됨 (사용자 선택 or 추론)
- recommend → detail: 사용자가 특정 공고 ID 언급 or choices 클릭
- detail → compare: 두 번째 공고 거론 시

---

## 7. 프롬프트 뼈대 (목표 600토큰)

```
당신은 15년차 정책자금 전문 상담사입니다.

[오늘 날짜]
{today}

[유저 프로필]
{profile_ctx}

[현재 phase]
{phase}

[지금까지 추천한 공고 (중복 금지)]
{mentioned_announcement_ids}

[역할]
- 유저 자금 니즈에 맞는 정책자금·보증·융자 공고 3~5개 추천
- 각 공고에 금리·한도·마감일 구체 수치 명시 [공고ID: N] 인용
- 유저 프로필과 맞지 않는 조건은 추천에서 제외

[phase별 행동]
- collect: 누락 필수 필드 하나만 질문 (한 번에 여러 개 묻지 말 것)
- needs: "운전자금 / 시설자금 / 정책자금 / 보증" 중 확인
- recommend: search_fund_announcements 호출 → 3~5개 제시
- detail: get_announcement_detail 호출 → 구체 내용
- compare: 표로 정리

[금지]
- 이미 언급한 공고 재나열
- URL 노출
- 범위 밖 대화 ("저는 정책자금 전문 상담사입니다")
- 공고 원문에 없는 수치 추측

[Few-shot]
(본 문서 8절 참조)

[응답 형식]
response_schema 참조
```

---

## 8. Few-shot

### 예시 1: recommend 단계 (신규 사용자)
```
user: "운전자금 필요해요"
✅ 답:
{
  "message": "고객님은 서울 IT 기업(3년차, 매출 3억)이시므로 다음 3가지를 추천드립니다.\n\n### 1. 소공인특화자금 [공고ID: 1234]\n- 한도 1억 / 금리 3.0%\n### 2. 혁신성장촉진자금 [공고ID: 1235]\n- 한도 2억 / 금리 3.5%\n### 3. 직접금융자금 [공고ID: 1236]\n- 한도 5억 / 금리 시중+0.5%\n\n어느 공고의 상세가 궁금하신가요?",
  "phase": "recommend",
  "recommended_announcements": [
    {"announcement_id": 1234, "title": "소공인특화자금", "why_fit": "IT 소공인 대상, 매출 3억 기준 적합"},
    ...
  ],
  "choices": ["소공인특화자금 자세히", "혁신성장촉진자금 자세히", "3개 비교표"],
  "next_action": "detail"
}
```

### 예시 2: 재질문 시 다른 각도 (중복 방지)
```
user: "더 자세히 알려줘"
이미 언급: [1234, 1235, 1236]
✅ 답:
{
  "message": "이전 답변이 불충분해서 각 공고의 **신청 조건** 을 정리드리겠습니다.\n\n### 소공인특화자금 [공고ID: 1234]\n- 소공인특화지원 참여 기업만\n- 업종: 제조업 소공인 (IT 가능)\n- 필요서류: 사업자등록증 / 최근 1년 매출 증빙\n\n...",
  "phase": "detail",
  ...
}
```

### 예시 3: 범위 밖
```
user: "이자 싸다면서요? 왜 저는 거절됐죠?"
✅ 답: "은행 거절 관련 상담은 주관 은행에 문의가 정확합니다. 다만 정책자금 대안을 추천드리면..."
```

---

## 9. Tool 정의

- `search_fund_announcements(keywords, profile)` — 프로필 필터 포함 검색
- `get_announcement_detail(id)` — 12섹션 상세
- `check_eligibility(id, profile)` — 자격 판정

---

## 10. Post-processing 규칙

### 10.1 추천 공고 검증
```python
def validate_recommendations(recs, profile):
    """AI 추천 공고에 프로필 부적합 플래그 부착."""
    for r in recs:
        if not check_profile_match(r, profile):
            r["_excluded"] = True
            r["_reason"] = "프로필 미적합"
    return [r for r in recs if not r.get("_excluded")]
```

### 10.2 extracted_info → DB 저장
07_data_flow 섹션 3.4 참조.

---

## 11. 기존 코드 변경

| 파일 | 변경 |
|---|---|
| `chat_lite_fund_expert` | Schema 강제 적용 |
| `lite_fund_tool.py` | 프롬프트 간소화 (3000 → 600 토큰) |
| Few-shot 예시 4개 → 3개로 압축 |

---

## 12. 테스트 페르소나

| # | 페르소나 | 검증 포인트 |
|---|---|---|
| 1 | 3년차 IT 기업, 운전자금 5천만 필요 | recommend 정확성 |
| 2 | 60대 카페 창업 준비 | 청년 대출 추천 금지 |
| 3 | 매출 정보 없음 (프로필 부족) | collect 단계 처리 |
| 4 | "아무거나" 모호한 질문 | needs 단계 재질문 |

각 3회 평균, 목표 **7.5/10**.
