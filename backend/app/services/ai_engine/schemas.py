"""Gemini response_schema 정의 — AI가 양식 어기면 API가 거부.

핵심: 프롬프트에 '저장해주세요'가 아니라 API 수준에서 구조 강제.
"""

# 공통: 대화에서 추출한 프로필 정보 (모든 AI 공용)
EXTRACTED_INFO_SCHEMA = {
    "type": "object",
    "description": "대화에서 발견한 프로필 정보 — 빈 필드는 생략 가능",
    "properties": {
        # 공통
        "address_city": {"type": "string", "description": "시도 (예: 서울, 경기)"},
        "interests": {"type": "array", "items": {"type": "string"}},

        # 기업
        "company_name": {"type": "string"},
        "industry_code": {"type": "string"},
        "establishment_date": {
            "type": "string",
            "description": "설립일 YYYY-MM-DD. 연도만 알면 YYYY-01-01로.",
        },
        "revenue_bracket": {"type": "string"},
        "employee_count_bracket": {"type": "string"},

        # 개인
        "age_range": {"type": "string", "description": "20대, 30대, 40대, 50대, 60대 이상"},
        "income_level": {"type": "string"},
        "family_type": {"type": "string"},
        "employment_status": {"type": "string"},
        "housing_status": {"type": "string"},
    },
}


# ① LITE 공고상담 응답 schema
LITE_ANNOUNCE_SCHEMA = {
    "type": "object",
    "required": ["message", "verdict", "next_action"],
    "properties": {
        "message": {
            "type": "string",
            "description": "사용자에게 보여줄 답변 (마크다운)",
        },
        "verdict": {
            "type": "string",
            "enum": ["eligible", "conditional", "ineligible", "undetermined"],
            "description": "자격 판정 결과 — 반드시 이 중 하나",
        },
        "reasoning": {
            "type": "object",
            "properties": {
                "matched_conditions": {"type": "array", "items": {"type": "string"}},
                "missing_conditions": {"type": "array", "items": {"type": "string"}},
                "citations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "근거 인용 '[공고ID: N] 자격 요건' 형식",
                },
            },
        },
        "alternatives": {
            "type": "array",
            "description": "verdict=ineligible일 때 대안 공고",
            "items": {
                "type": "object",
                "properties": {
                    "announcement_id": {"type": "integer"},
                    "reason": {"type": "string"},
                },
            },
        },
        "choices": {
            "type": "array",
            "items": {"type": "string"},
            "description": "후속 질문 제안 (최대 3개)",
        },
        "extracted_info": EXTRACTED_INFO_SCHEMA,
        "next_action": {
            "type": "string",
            "enum": ["wait_user", "search_alternatives", "detail_section", "finish"],
        },
    },
}


# ② LITE 정책자금 응답 schema
LITE_FUND_SCHEMA = {
    "type": "object",
    "required": ["message", "phase", "next_action"],
    "properties": {
        "message": {"type": "string"},
        "phase": {
            "type": "string",
            "enum": ["collect", "needs", "recommend", "detail", "compare"],
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
                    "deadline": {"type": "string"},
                },
            },
        },
        "extracted_info": EXTRACTED_INFO_SCHEMA,
        "choices": {"type": "array", "items": {"type": "string"}},
        "next_action": {
            "type": "string",
            "enum": ["ask_profile", "ask_needs", "search", "detail", "compare", "finish"],
        },
    },
}


# ⑤ PRO 공고상담 — expert_insights 포함
EXPERT_INSIGHTS_SCHEMA = {
    "type": "object",
    "required": ["selection_rate_estimate", "key_evaluation_points"],
    "properties": {
        "selection_rate_estimate": {"type": "string"},
        "key_evaluation_points": {"type": "array", "items": {"type": "string"}},
        "common_pitfalls": {"type": "array", "items": {"type": "string"}},
        "application_tips": {"type": "array", "items": {"type": "string"}},
        "similar_programs": {"type": "array", "items": {"type": "integer"}},
        "document_checklist": {"type": "array", "items": {"type": "string"}},
    },
}

PRO_ANNOUNCE_SCHEMA = {
    "type": "object",
    "required": ["message", "verdict_for_client", "expert_insights"],
    "properties": {
        "message": {"type": "string"},
        "verdict_for_client": {
            "type": "string",
            "enum": ["eligible", "conditional", "ineligible"],
        },
        "expert_insights": EXPERT_INSIGHTS_SCHEMA,
        "citations": {"type": "array", "items": {"type": "string"}},
        "choices": {"type": "array", "items": {"type": "string"}},
        "next_action": {
            "type": "string",
            "enum": ["wait_user", "compare_similar", "generate_report", "finish"],
        },
    },
}
