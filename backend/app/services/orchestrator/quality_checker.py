"""
quality_checker.py — 에이전트별 상담 품질 평가
ai_consult_logs에서 최근 5건 샘플링 → Gemini 채점 → 결과 반환
"""
import json
import os
import random


SCORE_PROMPT = """
당신은 AI 상담 품질 평가 전문가입니다.
아래 상담 대화를 읽고 5가지 항목을 각각 0~10점으로 채점하세요.

[상담 대화]
{conversation}

[채점 기준]
1. 정확성: 정보가 사실에 기반하며 오류가 없는가
2. 완결성: 질문에 충분히 답변했는가
3. 전문성: 정부지원사업 전문가다운 답변인가
4. 실행가능성: 고객이 실제로 실행할 수 있는 구체적 조언인가
5. 명확성: 이해하기 쉽고 구조화된 답변인가

반드시 아래 JSON 형식으로만 응답하세요:
{"정확성": 숫자, "완결성": 숫자, "전문성": 숫자, "실행가능성": 숫자, "명확성": 숫자, "총평": "한 문장 평가"}
"""


def _call_gemini(prompt: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {}
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            "models/gemini-2.5-flash",
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 512,
                "response_mime_type": "application/json",
            },
        )
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
        if not text:
            print("[Orchestrator/quality] Gemini 응답이 비어있음")
            return {}
        # JSON 추출 (마크다운 감싸기 방어)
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        print(f"[Orchestrator/quality] JSON 파싱 실패: {text[:100]}")
    except Exception as e:
        print(f"[Orchestrator/quality] Gemini 오류: {e}")
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
    score_keys = ["정확성", "완결성", "전문성", "실행가능성", "명확성"]

    for row in sample:
        msgs = row.get("messages") or []
        if isinstance(msgs, str):
            try:
                msgs = json.loads(msgs)
            except Exception:
                msgs = []

        # 대화 텍스트 구성 (최대 6턴)
        conv_lines = []
        for m in msgs[-6:]:
            role = "고객" if m.get("role") == "user" else "AI"
            text = (m.get("text") or "")[:300]
            conv_lines.append(f"{role}: {text}")
        conversation = "\n".join(conv_lines)

        if not conversation.strip():
            continue

        scores = _call_gemini(SCORE_PROMPT.format(conversation=conversation))
        total = sum(scores.get(k, 0) for k in score_keys)
        results.append({
            "session_id": row.get("session_id", ""),
            "updated_at": str(row.get("updated_at", "")),
            "scores": scores,
            "total": total,
        })

    if not results:
        return {"samples": [], "avg_scores": {}, "low_quality_count": 0, "avg_total": 0, "sample_count": 0}

    # 평균 집계
    avg = {}
    for k in score_keys:
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
