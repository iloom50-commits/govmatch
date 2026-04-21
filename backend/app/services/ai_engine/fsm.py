"""상태 기계 엔진 — 프롬프트가 아닌 코드가 상태 전이를 결정.

사장님 확정 사항 (redesign 00):
  - 프롬프트는 짧고 단일 책임
  - 상태 전이는 코드가 명시

각 AI마다 FSM 정의. 여기선 LITE 공고상담부터 시작.
"""

from enum import Enum
from typing import Optional


class LiteAnnounceState(str, Enum):
    """LITE 공고상담 상태."""
    INITIAL = "initial"                 # 첫 진입 — 공고 분석 + 첫 판정
    ELIGIBLE_DETAIL = "eligible_detail"   # 해당됨 — 심화 질문 대기
    CONDITIONAL_CHECK = "conditional_check"  # 조건부 — 추가 확인 필요
    INELIGIBLE_ALT = "ineligible_alt"     # 미해당 — 대안 탐색
    SEARCHING_ALT = "searching_alt"       # 대안 검색 중
    FINISHED = "finished"                 # 상담 종료


def decide_next_state(
    current: str,
    verdict: str,
    next_action_hint: str,
    user_msg: str,
    alternatives_shown: bool = False,
) -> str:
    """LITE 공고상담 다음 상태 결정.

    Args:
        current: 현재 상태 (LiteAnnounceState 값)
        verdict: AI 판정 (eligible/conditional/ineligible/undetermined)
        next_action_hint: AI가 제안한 next_action
        user_msg: 마지막 사용자 메시지
        alternatives_shown: 대안 이미 보여줬는지

    Returns:
        다음 상태
    """
    # 종료 키워드 감지 — 최우선
    END_WORDS = ("종료", "그만", "감사합니다", "고마워", "됐어요", "그만해")
    if any(w in user_msg for w in END_WORDS):
        return LiteAnnounceState.FINISHED

    # verdict에 따른 자동 전이
    if current == LiteAnnounceState.INITIAL:
        if verdict == "eligible":
            return LiteAnnounceState.ELIGIBLE_DETAIL
        if verdict == "conditional":
            return LiteAnnounceState.CONDITIONAL_CHECK
        if verdict == "ineligible":
            return LiteAnnounceState.INELIGIBLE_ALT
        # undetermined — 그대로 INITIAL 유지 (추가 정보 수집)
        return LiteAnnounceState.INITIAL

    if current == LiteAnnounceState.INELIGIBLE_ALT:
        # 이미 미해당 상태 — 대안 탐색으로 전환
        if not alternatives_shown and next_action_hint == "search_alternatives":
            return LiteAnnounceState.SEARCHING_ALT
        return current

    if current == LiteAnnounceState.SEARCHING_ALT:
        # 대안 제시 후 사용자 피드백 대기
        return current

    if current == LiteAnnounceState.ELIGIBLE_DETAIL:
        # 신청 완료 의향 + 종결 표현 → 종료
        if any(w in user_msg for w in ("알겠", "이해했", "충분")):
            return LiteAnnounceState.FINISHED
        return current

    return current


# LITE 정책자금 FSM (참고용 — 추후 확장)
class LiteFundState(str, Enum):
    COLLECT = "collect"
    NEEDS = "needs"
    RECOMMEND = "recommend"
    DETAIL = "detail"
    COMPARE = "compare"
    FINISHED = "finished"


# PRO 매칭 FSM (참고용)
class ProMatchState(str, Enum):
    FORM_INPUT = "form_input"
    MATCHING = "matching"
    RESULT_SHOWN = "result_shown"
    ANNOUNCE_DETAIL = "announce_detail"
    REPORT_GENERATING = "report_generating"
    FINISHED = "finished"
