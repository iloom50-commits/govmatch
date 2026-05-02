"""
quality_checker.py — 에이전트별 상담 품질 평가
ai_consult_logs에서 최근 5건 샘플링 → Gemini 채점 → 결과 반환
"""
import json
import os
import random


SCORE_PROMPT = """Score this AI consultation. Reply with ONLY this JSON, nothing else:
{{"accuracy":N,"completeness":N,"expertise":N,"actionability":N,"clarity":N}}

Where N is 0-10. Consultation:
{conversation}"""

# 영어 키 → 한글 표시명 매핑
SCORE_KEY_LABELS = {
    "accuracy": "정확성",
    "completeness": "완결성",
    "expertise": "전문성",
    "actionability": "실행가능성",
    "clarity": "명확성",
}


_last_gemini_error = None  # 디버그용: 마지막 에러 저장


def _call_gemini(prompt: str) -> dict:
    global _last_gemini_error
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        _last_gemini_error = "GEMINI_API_KEY 미설정"
        return {}
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model_name = os.environ.get("GEMINI_BATCH_MODEL", "gemini-2.5-flash")
        model = genai.GenerativeModel(
            model_name,
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 1024,
            },
        )
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
        if not text:
            print("[Orchestrator/quality] Gemini 응답 비어있음")
            return {}
        _last_gemini_error = f"len={len(text)} raw={text[:500]}"
        # 마크다운 코드블록 제거 (```json ... ```)
        import re as _re
        text = _re.sub(r"```(?:json)?\s*", "", text).strip()
        # { ... } 블록 추출 후 파싱
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            chunk = text[start:end]
            return json.loads(chunk)
        raise ValueError(f"JSON 블록 없음: {text[:100]}")
    except (json.JSONDecodeError, ValueError) as je:
        if _last_gemini_error and _last_gemini_error.startswith("raw="):
            _last_gemini_error = f"{_last_gemini_error} | err={je}"
        else:
            _last_gemini_error = f"JSONDecodeError: {je}"
        print(f"[Orchestrator/quality] JSON 파싱 실패: {je}")
    except Exception as e:
        _last_gemini_error = f"{type(e).__name__}: {str(e)[:200]}"
        print(f"[Orchestrator/quality] Gemini 오류: {type(e).__name__}: {e}")
    return {}


def check_quality(db_conn) -> dict:
    """
    ai_consult_logs 최근 7일 중 랜덤 5건 샘플링 → Gemini 채점.
    반환: {"samples": [...], "avg_scores": {...}, "low_quality_count": int}
    """
    try:
        cur = db_conn.cursor()
        cur.execute("""
            SELECT id, session_id, messages, conclusion, updated_at
            FROM ai_consult_logs
            WHERE updated_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
              AND messages IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 50
        """)
        rows = cur.fetchall()
    except Exception as e:
        print(f"[Orchestrator/quality] DB 조회 오류: {e}")
        return {"error": str(e), "samples": [], "avg_scores": {}}

    if not rows:
        return {"samples": [], "avg_scores": {}, "low_quality_count": 0, "avg_total": 0, "sample_count": 0}

    sample = random.sample(rows, min(5, len(rows)))
    results = []
    score_keys = list(SCORE_KEY_LABELS.keys())  # ["accuracy", "completeness", ...]
    skipped_empty = 0

    for row in sample:
        msgs = row.get("messages") or []
        if isinstance(msgs, str):
            try:
                msgs = json.loads(msgs)
            except Exception:
                msgs = []

        # 대화 텍스트 구성 (최대 6턴) — "text" 또는 "content" 키 모두 지원
        conv_lines = []
        for m in msgs[-6:]:
            role = "고객" if m.get("role") == "user" else "AI"
            text = (m.get("text") or m.get("content") or "")[:300]
            if text:
                conv_lines.append(f"{role}: {text}")
        conversation = "\n".join(conv_lines)

        if not conversation.strip():
            skipped_empty += 1
            continue

        scores = _call_gemini(SCORE_PROMPT.format(conversation=conversation))
        if not scores:
            continue
        total = sum(scores.get(k, 0) for k in score_keys)
        # 한글 키로 변환하여 저장 (reporter 표시용)
        scores_kr = {SCORE_KEY_LABELS[k]: scores.get(k, 0) for k in score_keys}
        results.append({
            "session_id": row.get("session_id", ""),
            "updated_at": str(row.get("updated_at", "")),
            "scores": scores_kr,
            "total": total,
        })

    if not results:
        return {"samples": [], "avg_scores": {}, "low_quality_count": 0, "avg_total": 0, "sample_count": 0, "skipped_empty": skipped_empty, "last_error": _last_gemini_error}

    # 평균 집계 (한글 키 기준)
    kr_keys = list(SCORE_KEY_LABELS.values())
    avg = {}
    for k in kr_keys:
        vals = [r["scores"].get(k, 0) for r in results if r["scores"]]
        avg[k] = round(sum(vals) / len(vals), 1) if vals else 0

    low_quality_count = sum(1 for r in results if r["total"] < 25)

    return {
        "samples": results,
        "avg_scores": avg,
        "avg_total": round(sum(r["total"] for r in results) / len(results), 1),
        "low_quality_count": low_quality_count,
        "sample_count": len(results),
    }
