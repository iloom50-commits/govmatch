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


# Gemini 2.5 flash 단가(2026-07 기준, per token) — 추론 토큰은 출력 단가로 과금
_USD_KRW = 1535.0
_FLASH_IN = 0.30 / 1_000_000
_FLASH_OUT = 2.50 / 1_000_000


def estimate_cost_krw(prompt: int, output: int, thought: int) -> float:
    """대략 원화 추정(flash 단가). 추론=출력 단가."""
    usd = (prompt or 0) * _FLASH_IN + ((output or 0) + (thought or 0)) * _FLASH_OUT
    return usd * _USD_KRW


def summarize_usage(db_conn, hours: int = 24) -> dict:
    """최근 N시간 ai_usage_log 흐름별 집계 + 추정비용. {total_krw, hours, flows[]}."""
    cur = db_conn.cursor()
    cur.execute(
        """SELECT flow_tag,
                  COUNT(*) calls,
                  COALESCE(SUM(prompt_tokens),0) p,
                  COALESCE(SUM(output_tokens),0) o,
                  COALESCE(SUM(thought_tokens),0) t
           FROM ai_usage_log
           WHERE created_at > NOW() - make_interval(hours => %s)
           GROUP BY flow_tag""",
        (hours,),
    )
    rows = cur.fetchall() or []
    flows = []
    total = 0.0
    for r in rows:
        p = r["p"] if isinstance(r, dict) else r[2]
        o = r["o"] if isinstance(r, dict) else r[3]
        t = r["t"] if isinstance(r, dict) else r[4]
        krw = estimate_cost_krw(p, o, t)
        total += krw
        flows.append({
            "flow": r["flow_tag"] if isinstance(r, dict) else r[0],
            "calls": r["calls"] if isinstance(r, dict) else r[1],
            "prompt": p, "output": o, "thought": t, "krw": round(krw),
        })
    flows.sort(key=lambda x: x["krw"], reverse=True)
    return {"total_krw": round(total), "hours": hours, "flows": flows}


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
