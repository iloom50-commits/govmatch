# 05 PRO 공고상담 AI — 상세 설계 (신규)

**기존**: 없음. 현재는 `chat_consult`를 LITE와 공유.
**새 전략**: LITE 공고상담과 **분리된 엔진** + 전문가 세부 내용 추가.

---

## 1. 미션 (한 문장)

> **컨설턴트가 알고 있는 특정 공고에 대해 고객을 위한 전문가 레벨 심화 분석·판정을 제공한다.**

---

## 2. LITE 공고상담과의 차이

| 측면 | LITE 공고상담 (①) | PRO 공고상담 (⑤) |
|---|---|---|
| 답변 대상 | 유저 자신 | **고객** (제3자) |
| 톤 | 친절·쉽게 | 전문·간결 |
| 깊이 | 핵심 조건 대조 | **심사 가중치·선정률·경쟁률·꿀팁** |
| 근거 인용 | 공고 원문 | 공고 원문 + 평가 기준 + 유사 사업 |
| 대안 제시 | 단순 추천 | **비교표** (조건/금액/난이도) |
| 출력 | 대화 응답 | **문서화 가능한 분석** (보고서 연계) |

---

## 3. 진입 경로

```
[PRO 대시보드] → "📋 특정 공고 상담" 카드
     ↓
[공고 검색] (공고명·기관·키워드)
     ↓
  공고 선택 → (필요 시 고객 선택)
     ↓
PRO 공고상담 AI 시작
```

---

## 4. 성공 기준 (KPI)

| 지표 | 목표 |
|---|---|
| 전문가 세부 내용 (expert_insights) 완성도 | 9/10 |
| 근거 인용률 | 100% |
| 답변 길이 (LITE 대비 +50%) | 깊이 지표 |
| 컨설턴트 편집 없이 고객 전달 가능율 | 60% 이상 |

---

## 5. 입출력 Schema (04 PRO 매칭과 동일 구조)

**출력 Schema 공유**: `verdict_for_client` / `expert_insights` / `citations` / `next_action`

**차이점**: PRO 매칭은 `matched_announcements` 배열, PRO 공고상담은 `announcement_id` 단일 타겟.

```json
{
  "required": ["message", "verdict_for_client", "expert_insights"],
  "properties": {
    "message": {"type": "string"},
    "verdict_for_client": {
      "type": "string",
      "enum": ["eligible", "conditional", "ineligible"]
    },
    "expert_insights": {
      "type": "object",
      "required": ["selection_rate_estimate", "key_evaluation_points"],
      "properties": {
        "selection_rate_estimate": {"type": "string"},
        "key_evaluation_points": {"type": "array", "items": {"type": "string"}},
        "common_pitfalls": {"type": "array", "items": {"type": "string"}},
        "application_tips": {"type": "array", "items": {"type": "string"}},
        "similar_programs": {"type": "array", "items": {"type": "integer"}},
        "document_checklist": {"type": "array", "items": {"type": "string"}}
      }
    },
    "comparison_table": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "announcement_id": {"type": "integer"},
          "title": {"type": "string"},
          "support_amount": {"type": "string"},
          "difficulty": {"type": "string"}
        }
      }
    },
    "citations": {"type": "array", "items": {"type": "string"}},
    "choices": {"type": "array", "items": {"type": "string"}},
    "next_action": {
      "type": "string",
      "enum": ["wait_user", "compare_similar", "generate_report", "finish"]
    }
  }
}
```

---

## 6. 프롬프트 뼈대

```
당신은 15년차 정부지원사업 전문 컨설턴트입니다.
컨설턴트가 고객사를 위해 특정 공고에 대한 전문가 분석을 요청합니다.

[오늘 날짜]
{today}

[고객 프로필]
{client_profile_formatted}

[상담 공고]
공고 ID: {announcement_id}
공고명: {announcement_title}
자격 요건: {parsed_sections.eligibility}
지원 내용: {parsed_sections.support_details}
심사 기준: {parsed_sections.evaluation_criteria}
필수 서류: {parsed_sections.required_docs}
제외 조건: {deep_analysis.exclusion_rules}

[전문가 레벨 답변 원칙]
1. 결론 먼저 (verdict)
2. 심사 가중치 높은 항목 명시 (key_evaluation_points)
3. 선정률 추정 (selection_rate_estimate)
4. 흔한 실수 · 함정 (common_pitfalls)
5. 신청서 작성 꿀팁 (application_tips)
6. 유사 대안 사업 (similar_programs)
7. 필요 서류 체크리스트 (document_checklist)

[차별화 — LITE 대비 +α]
- 일반 유저용 "쉬운 설명" 금지
- 컨설턴트가 고객에게 **자료로 전달 가능한** 수준의 분석
- 추측 아닌 근거 기반 (원문 + 과거 유사 사업 패턴)

[금지]
- URL 노출
- 범위 밖 대화 (해당 시: "저는 지원사업 전문 컨설턴트입니다. 이 공고 관련 질문을 해주시면...")
- 공고 원문에 없는 구체 수치 추측

[응답 구조]
## 결론 (verdict)
## 근거 — 고객사 vs 공고 조건 대조표
## 전문가 인사이트
  - 심사 가중치
  - 선정률 추정
  - 흔한 실수
  - 신청서 꿀팁
## 추천 액션
  - 필요 서류
  - 유사 대안
  - 다음 단계
```

### Few-shot 예시 (LITE ②와 다른 톤 비교용)

**예시 1: eligible + 전문가 인사이트**
```
user: "창업성장기술개발사업 디딤돌 공고, 고객사 3년차 IT 기업인데 어떨까요?"
✅ 답:
{
  "message": "## 결론\n**조건부 해당 (eligible, 준비 필수)** [공고ID: 3456]\n\n## 근거\n| 조건 | 기준 | 고객사 | 판정 |\n|---|---|---|---|\n| 창업 3년 초과 7년 이내 | 필수 | 3년 | ✅ |\n| 매출 10억 미만 | ≤10억 | 5억 | ✅ |\n\n## 전문가 인사이트\n**선정률 추정**: 약 18% (2024년 통계)\n**심사 가중치**:\n- 기술성 40%\n- 시장성 25%\n- 사업화 전략 20%\n- 대표자·팀 역량 15%\n\n**흔한 실수**:\n1. 사업화 계획을 '향후 확보 예정'으로 모호하게 기재 → 감점 큼\n2. 연차별 매출 목표를 구체 수치 없이 제시\n3. 타 지원사업 수혜 이력 누락 → 가점 놓침\n\n**신청서 꿀팁**:\n- 기술성 섹션에 특허·인증 증빙 별첨\n- 시장성 섹션에 실제 잠재 고객사 레퍼런스\n- 대표자 역량에 창업 전 유관 경력 강조\n\n## 추천 액션\n**필수 서류**: 사업자등록증 / 재무제표 / 특허(있으면) / 기술개발계획서\n**유사 대안**: 창업도약패키지 [공고ID: 3458], 산학연Collabo R&D [공고ID: 3459]\n**다음 단계**: 기술개발계획서 초안 작성 → 컨설턴트 검토",
  "verdict_for_client": "conditional",
  "expert_insights": {
    "selection_rate_estimate": "약 18%",
    "key_evaluation_points": [
      "기술성 40%",
      "시장성 25%",
      "사업화 전략 20%",
      "대표자·팀 역량 15%"
    ],
    "common_pitfalls": [
      "사업화 계획 모호",
      "연차별 매출 목표 수치 없음",
      "타 지원사업 수혜 이력 누락"
    ],
    "application_tips": [
      "특허·인증 증빙 별첨",
      "실제 잠재 고객사 레퍼런스 제시",
      "대표자 유관 경력 강조"
    ],
    "similar_programs": [3458, 3459],
    "document_checklist": [
      "사업자등록증",
      "재무제표 3개년",
      "특허·인증서 사본",
      "기술개발계획서"
    ]
  },
  "citations": ["공고ID: 3456 자격 요건", "공고ID: 3456 평가 기준"],
  "choices": [
    "유사 사업과 비교표 보기",
    "기술개발계획서 작성 가이드",
    "서류별 세부 요건"
  ],
  "next_action": "wait_user"
}
```

---

## 7. Tool 정의

- `get_announcement_detail(id)`
- `analyze_announcement(id)` — 원문 데이터 부족 시 재분석
- `check_eligibility(id, client_profile)`
- `search_similar_programs(id, client_profile)` — 유사 대안
- `estimate_selection_rate(id)` — DB 통계 기반 추정
- `search_knowledge_base(query)` — 실무 팁

---

## 8. Post-processing

### expert_insights 보완
```python
def enrich_insights(insights: dict, announcement_id: int, db_conn):
    # selection_rate 비었으면 DB 통계로 보충
    if not insights.get("selection_rate_estimate"):
        stats = estimate_selection_rate(announcement_id, db_conn)
        if stats:
            insights["selection_rate_estimate"] = f"약 {stats['rate']}% (추정)"

    # document_checklist 비었으면 parsed_sections.required_docs에서 추출
    if not insights.get("document_checklist"):
        docs = get_required_docs(announcement_id, db_conn)
        insights["document_checklist"] = docs
    return insights
```

---

## 9. 프론트엔드 UI

### 9.1 진입
```
[PRO 대시보드] → "📋 특정 공고 상담"
     ↓
[공고 검색 바]  ← 공고명·기관·키워드
[빠른 필터 칩: 정책자금/R&D/창업/...]
     ↓
검색 결과 → 공고 클릭
     ↓
[고객 선택 옵션]
  - 신규 고객 (폼)
  - 기존 고객
  - 고객 없이 공고 자체만 분석
     ↓
상담 시작
```

### 9.2 상담 화면
- 상단: 공고 제목 + 핵심 정보 (요약)
- 중앙: 대화
- 우측 패널: **expert_insights 시각화** (선정률 차트, 가중치 막대, 체크리스트)

---

## 10. 테스트 페르소나

| # | 페르소나 | 시나리오 |
|---|---|---|
| 1 | 3년차 IT (R&D 공고) | 선정 전략 질의 — insights 충실도 |
| 2 | 재창업 (예비창업 공고) | 업력 논란 케이스 — 하드 규칙 |
| 3 | 중견기업 (소상공인 공고) | 명확한 ineligible + 대안 |
| 4 | 사회적기업 전환 (특수 공고) | 도메인 깊이 |

각 3회 평균, 목표 **7.5/10** (LITE 대비 +0.5 — 전문가 레벨 차별화).

---

## 11. 기존 코드와의 관계

- **`chat_consult` 분기 추가**: `mode="pro"`일 때 전문가 프롬프트 + `expert_insights` schema
- 또는 **별도 함수 `chat_pro_announce`** 신설 (권장, 책임 분리)

---

**다음 문서**: 03_lite_report.md + 06_pro_report.md (보고서 설계)
