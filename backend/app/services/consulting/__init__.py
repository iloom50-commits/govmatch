"""분야별 상담 모듈 라우터

공고의 분야를 감지하여 해당 전문 모듈의 지시문/지식을 반환한다.
ai_consultant.py의 chat_consult()에서 호출.
"""

from .base import detect_domain, get_domain_knowledge, DOMAIN_REGISTRY, DOMAIN_STATISTICS
from . import finance, startup, rnd, export_market, employment
from . import youth, housing, welfare, family, education

# 분야 → 모듈 매핑
_DOMAIN_MODULES = {
    "finance": finance,
    "startup": startup,
    "rnd": rnd,
    "export": export_market,
    "employment": employment,
    "youth": youth,
    "housing": housing,
    "welfare": welfare,
    "family": family,
    "education": education,
}


def get_domain_expert_directive(
    domain: str,
    financial_context: str = "",
    cross_ref_context: str = "",
) -> str:
    """분야에 맞는 전문가 지시문 반환

    Args:
        domain: detect_domain()의 결과 ("finance", "startup", ...)
        financial_context: 금융 모듈의 분석 데이터 (finance 전용)
        cross_ref_context: 유사 공고 참조 데이터 (finance 전용)

    Returns:
        str: 시스템 프롬프트에 삽입할 전문가 지시문
    """
    if domain == "finance":
        return finance.get_expert_directive(financial_context, cross_ref_context)

    module = _DOMAIN_MODULES.get(domain)
    if module and hasattr(module, "get_expert_directive"):
        return module.get_expert_directive()

    return ""


def get_domain_label(domain: str) -> str:
    """분야 한글명 반환"""
    if not domain:
        return "일반"
    info = DOMAIN_REGISTRY.get(domain, {})
    return info.get("label", "일반")


__all__ = [
    "detect_domain",
    "get_domain_expert_directive",
    "get_domain_knowledge",
    "get_domain_label",
    "DOMAIN_REGISTRY",
    "DOMAIN_STATISTICS",
]
