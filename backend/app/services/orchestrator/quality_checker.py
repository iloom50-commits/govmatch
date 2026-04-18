"""상담 품질 체커 — 최근 상담 샘플링 → Gemini 평가."""

import os
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def check_agent_quality(db_conn, samples_per_agent: int = 3) -> Dict[str, Any]:
    """에이전트별 최근 상담을 샘플링하여 Gemini로 품질 평가.

    Returns: {
        "agent_scores": {"lite_biz": {"avg_score": 7.2, "samples": 3}, ...},
        "low_quality_samples": [...],
        "summary": "..."
    }
    """
    result: Dict[str, Any] = {"agent_scores": {}, "low_quality_samples": [], "summary": ""}

    try:
        cur = db_conn.cursor()

        # 에이전트별 최근 상담 샘플링 (messages JSON에서 추출)
        cur.execute(f"""
            SELECT id, mode, conclusion, messages, created_at
            FROM ai_consult_logs
            WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
              AND messages IS NOT NULL
            ORDER BY RANDOM()
            LIMIT {samples_per_agent * 4}
        """)
        raw_samples = cur.fetchall()

        # messages JSON에서 마지막 user/assistant 추출
        samples = []
        for r in raw_samples:
            msgs = r.get("messages") or []
            if isinstance(msgs, str):
                try:
                    msgs = json.loads(msgs)
                except Exception:
                    continue
            user_msgs = [m.get("text", "") for m in msgs if m.get("role") == "user"]
            asst_msgs = [m.get("text", "") for m in msgs if m.get("role") == "assistant"]
            if user_msgs and asst_msgs:
                samples.append({
                    "id": r["id"],
                    "mode": r.get("mode") or r.get("conclusion") or "unknown",
                    "query": user_msgs[-1],
                    "reply": asst_msgs[-1],
                    "created_at": r["created_at"],
                })

        if not samples:
            result["summary"] = "최근 24시간 상담 로그 없음"
            return result

        # Gemini로 품질 평가
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            result["summary"] = "GEMINI_API_KEY 미설정 — 품질 평가 불가"
            return result

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                "models/gemini-2.0-flash",
                generation_config={"max_output_tokens": 2048, "temperature": 0.2, "response_mime_type": "application/json"},
            )
        except Exception as e:
            result["summary"] = f"Gemini 초기화 실패: {e}"
            return result

        agent_scores: Dict[str, List[float]] = {}

        for sample in samples:
            agent = sample.get("mode") or "unknown"
            query = (sample.get("query") or "")[:300]
            reply = (sample.get("reply") or "")[:500]

            if not query or not reply:
                continue

            prompt = f"""다음은 정부 지원사업 AI 상담의 질문과 답변입니다.
품질을 0~10점으로 평가하세요.

[질문] {query}
[답변] {reply}

평가 기준:
- 정확성: 근거 없는 추측이 있는가? (0=완전 추측, 10=모두 근거 있음)
- 완결성: 질문에 충분히 답했는가? (0=전혀, 10=완벽)
- 유용성: 실제 도움이 되는 정보인가? (0=무의미, 10=매우 유용)

JSON 형식으로 응답:
{{"accuracy": 0, "completeness": 0, "usefulness": 0, "avg": 0, "issue": "문제점 한줄"}}"""

            try:
                resp = model.generate_content(prompt)
                scores = json.loads(resp.text)
                avg = scores.get("avg", 0)

                if agent not in agent_scores:
                    agent_scores[agent] = []
                agent_scores[agent].append(avg)

                if avg < 5:
                    result["low_quality_samples"].append({
                        "log_id": sample.get("id"),
                        "agent": agent,
                        "score": avg,
                        "issue": scores.get("issue", ""),
                    })
            except Exception:
                continue

        # 에이전트별 평균
        for agent, scores_list in agent_scores.items():
            result["agent_scores"][agent] = {
                "avg_score": round(sum(scores_list) / len(scores_list), 1) if scores_list else 0,
                "samples": len(scores_list),
            }

        # 전체 요약
        all_scores = [s for sl in agent_scores.values() for s in sl]
        overall = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
        result["summary"] = f"전체 평균 {overall}/10 ({len(all_scores)}건 평가)"

    except Exception as e:
        logger.error(f"[QualityChecker] Error: {e}")
        result["summary"] = f"품질 체크 오류: {e}"

    return result
