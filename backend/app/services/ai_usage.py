"""Gemini 호출 토큰 사용량 로깅 — 흐름별 비용 관측.

구(google.generativeai)·신(google.genai) 응답 공통으로 `usage_metadata`에서
토큰 수(추론 토큰 thoughts 포함)를 추출해 ai_usage_log에 기록한다.
best-effort: 로깅이 실패해도 호출측 로직에 절대 영향 주지 않는다.
"""
import os
from typing import Optional, Tuple

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def extract_usage(resp) -> Optional[Tuple[int, int, int, int]]:
    """응답 usage_metadata → (prompt, output, thought, total). 없으면 None."""
    um = getattr(resp, "usage_metadata", None)
    if um is None:
        return None

    def g(*names) -> int:
        for n in names:
            v = getattr(um, n, None)
            if v is not None:
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return 0
        return 0

    prompt = g("prompt_token_count")
    output = g("candidates_token_count")
    thought = g("thoughts_token_count", "thought_token_count")  # 추론 토큰(2.5, 신SDK)
    total = g("total_token_count")
    return (prompt, output, thought, total)


def log_gemini_usage(flow_tag: str, model: str, resp) -> None:
    """usage_metadata를 ai_usage_log에 1행 기록. 실패는 조용히 무시(호출측 무영향)."""
    try:
        u = extract_usage(resp)
        if u is None:
            return
        prompt, output, thought, total = u
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO ai_usage_log "
                "(flow_tag, model, prompt_tokens, output_tokens, thought_tokens, total_tokens) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (str(flow_tag)[:60], str(model)[:60], prompt, output, thought, total),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
