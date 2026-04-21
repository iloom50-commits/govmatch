"""AI 재설계 Phase 2 — 기반 계층.

설계 원칙 (docs/ai_redesign/00_overview.md):
  1. LLM 최소화, 코드 최대화
  2. Schema 우선 (response_schema 강제)
  3. 프롬프트 짧고 단일 책임
  4. FSM 명시 (상태 전이는 코드가 결정)

이 패키지:
  - schemas: Gemini response_schema 정의
  - extractor: 정규식/키워드 기반 엔티티 추출
  - updater: DB 저장 헬퍼 (COALESCE)
  - fsm: 상태 기계 엔진
"""

from .schemas import LITE_ANNOUNCE_SCHEMA, EXTRACTED_INFO_SCHEMA
from .extractor import extract_profile_info, extract_mentioned_announcement_ids
from .updater import save_extracted_to_users, save_extracted_to_client, calculate_profile_completeness
from .fsm import decide_next_state, LiteAnnounceState, LiteFundState, ProMatchState

__all__ = [
    "LITE_ANNOUNCE_SCHEMA",
    "EXTRACTED_INFO_SCHEMA",
    "extract_profile_info",
    "extract_mentioned_announcement_ids",
    "save_extracted_to_users",
    "save_extracted_to_client",
    "calculate_profile_completeness",
    "decide_next_state",
    "LiteAnnounceState",
    "LiteFundState",
    "ProMatchState",
]
