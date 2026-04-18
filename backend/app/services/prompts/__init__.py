"""AI 상담 프롬프트 모듈 — 에이전트별 프롬프트를 독립 파일로 관리."""

from .pro_business import PROMPT_PRO_BUSINESS
from .pro_individual import PROMPT_PRO_INDIVIDUAL
from .pro_consult_tool import PROMPT_PRO_CONSULT_BIZ_TOOL, PROMPT_PRO_CONSULT_INDIV_TOOL
from .lite_fund_tool import PROMPT_LITE_FUND_BIZ_TOOL, PROMPT_LITE_FUND_INDIV_TOOL

__all__ = [
    "PROMPT_PRO_BUSINESS",
    "PROMPT_PRO_INDIVIDUAL",
    "PROMPT_PRO_CONSULT_BIZ_TOOL",
    "PROMPT_PRO_CONSULT_INDIV_TOOL",
    "PROMPT_LITE_FUND_BIZ_TOOL",
    "PROMPT_LITE_FUND_INDIV_TOOL",
]
