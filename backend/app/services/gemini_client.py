"""신 google-genai SDK 기반 flash 호출 — thinking OFF 기본 + 토큰 로깅 통합.

구 google-generativeai(지원 종료)는 thinking을 끌 수 없어, 비용 큰 배치 호출을
이 헬퍼(신 SDK)로 이관한다. gemini-2.5-flash는 추론(thinking) 토큰을 출력으로
과금하므로, 추론이 불필요한 추출·분류·정밀분석은 thinking_budget=0으로 비용을 줄인다.

응답 객체는 구 SDK와 동일하게 `.text` / `.usage_metadata`를 제공하므로 호출측 파싱 로직 유지.
"""
import os
from google import genai
from google.genai import types

from app.services.ai_usage import log_gemini_usage

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_BATCH_API_KEY") or os.environ.get("GEMINI_API_KEY")
        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=120000),  # 120s (정밀분석 등 여유)
        )
    return _client


def generate_flash(
    flow_tag: str,
    prompt,
    *,
    model: str = "gemini-2.5-flash",
    thinking_budget: int = 0,
    max_output_tokens: int = None,
    temperature: float = None,
    response_mime_type: str = None,
    response_schema=None,
    system_instruction=None,
):
    """신 SDK flash 생성. thinking 기본 OFF. 응답(.text/.usage_metadata) 반환.

    로깅은 best-effort 내장. 예외는 호출측으로 전파(기존 폴백·재시도 로직 유지).
    """
    cfg = {"thinking_config": types.ThinkingConfig(thinking_budget=thinking_budget)}
    if max_output_tokens is not None:
        cfg["max_output_tokens"] = max_output_tokens
    if temperature is not None:
        cfg["temperature"] = temperature
    if response_mime_type is not None:
        cfg["response_mime_type"] = response_mime_type
    if response_schema is not None:
        cfg["response_schema"] = response_schema
    if system_instruction is not None:
        cfg["system_instruction"] = system_instruction

    resp = _get_client().models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(**cfg),
    )
    log_gemini_usage(flow_tag, model, resp)
    return resp
