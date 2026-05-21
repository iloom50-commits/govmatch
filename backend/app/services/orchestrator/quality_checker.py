"""
quality_checker.py — 에이전트별 역할 적합성 감시

4개 에이전트를 독립 평가:
  - LITE 자금상담 AI   (conclusion = 'free_chat')
  - LITE 전문상담사 AI (conclusion = 'lite_consultant')
  - PRO 전문가 AI      (conclusion LIKE 'pro_fund%')
  - 공고 특화 상담 AI  (announcement_id IS NOT NULL)

평가 항목: 정확성 / 역할적합성 / 유용성 (각 0~10)
결과 저장: orchestrator_reviews 테이블
"""
import json
import os
import random
from datetime import date


# ── 에이전트 정의 ─────────────────────────────────────────────
AGENTS = {
    "lite_fund": {
        "label": "LITE 자금상담 AI",
        "where": "conclusion = 'free_chat'",
        "role": "사용자 질문에 맞는 자금/대출/보증 공고를 찾아 안내하고, 지원 금액·자격·신청 방법을 구체적으로 설명한다.",
    },
    "lite_consultant": {
        "label": "LITE 전문상담사 AI",
        "where": "conclusion = 'lite_consultant'",
        "role": "사용자 프로필(업종·매출·지역 등)을 기반으로 가장 적합한 지원사업을 연결해주고, 간결하게 핵심만 안내한다.",
    },
    "pro_fund": {
        "label": "PRO 전문가 AI",
        "where": "conclusion LIKE 'pro_fund%'",
        "role": "전문가 수준의 심층 분석과 구체적 실행 계획을 제시한다. 공고 ID·지원 금액·자격요건을 정확히 인용하고, 단계별 신청 전략을 제안한다.",
    },
    "announcement": {
        "label": "공고 특화 상담 AI",
        "where": "announcement_id IS NOT NULL AND (conclusion IS NULL OR conclusion NOT LIKE 'pro%')",
        "role": "특정 공고 1건에 대해 자격요건·제출서류·신청방법을 정확하게 안내한다. 사용자의 상황과 공고 조건을 대조해 해당 여부를 명확히 판단한다.",
    },
}

SCORE_PROMPT = """당신은 AI 상담 품질 평가 전문가입니다.

[이 에이전트의 역할]
{role}

아래 상담 대화를 읽고, 에이전트가 역할을 제대로 수행했는지 평가하세요.

평가 기준:
- accuracy(정확성): 제공한 정보가 사실에 부합하는가 (0~10)
- role_fit(역할적합성): 에이전트 본연의 역할을 수행했는가 (0~10)
- helpfulness(유용성): 사용자에게 실질적으로 도움이 됐는가 (0~10)
- issue: 문제점이 있으면 한 줄 한국어로, 없으면 null

반드시 아래 JSON만 반환 (설명 없이):
{{"accuracy":N,"role_fit":N,"helpfulness":N,"issue":"문제점 또는 null"}}

상담 내용:
{conversation}"""


def _ensure_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orchestrator_reviews (
            id SERIAL PRIMARY KEY,
            review_date DATE NOT NULL DEFAULT CURRENT_DATE,
            agent VARCHAR(30) NOT NULL,
            agent_label VARCHAR(50),
            consult_log_id INTEGER,
            accuracy NUMERIC(4,1),
            role_fit NUMERIC(4,1),
            helpfulness NUMERIC(4,1),
            avg_score NUMERIC(4,1),
            issue TEXT,
            needs_review BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 기존 테이블에 누락된 컬럼 추가 (2026-05-21 스키마 불일치 수정)
    for col_def in [
        "agent_label VARCHAR(50)",
        "role_fit NUMERIC(4,1)",
        "helpfulness NUMERIC(4,1)",
    ]:
        cur.execute(f"""
            ALTER TABLE orchestrator_reviews
            ADD COLUMN IF NOT EXISTS {col_def}
        """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_orch_rev_date_agent
        ON orchestrator_reviews (review_date, agent)
    """)


def _call_gemini(prompt: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {}
    try:
        import google.generativeai as genai
        import re as _re
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            os.environ.get("GEMINI_BATCH_MODEL", "gemini-2.5-flash"),
            generation_config={"temperature": 0.1, "max_output_tokens": 512},
        )
        text = (model.generate_content(prompt).text or "").strip()
        text = _re.sub(r"```(?:json)?\s*", "", text).strip()
        s, e = text.find("{"), text.rfind("}") + 1
        if s >= 0 and e > s:
            return json.loads(text[s:e])
    except Exception as ex:
        print(f"[quality] Gemini 오류: {ex}")
    return {}


def _sample_agent(cur, where: str, n: int = 3) -> list:
    """에이전트별 최근 30일 상담 로그 최대 n건 랜덤 샘플링."""
    cur.execute(f"""
        SELECT id, messages
        FROM ai_consult_logs
        WHERE {where}
          AND updated_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
          AND messages IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT 30
    """)
    rows = cur.fetchall()
    return random.sample(rows, min(n, len(rows))) if rows else []


def _build_conversation(msgs_raw) -> str:
    """messages 컬럼(JSON) → 평가용 텍스트 (최근 6턴)."""
    msgs = msgs_raw or []
    if isinstance(msgs, str):
        try:
            msgs = json.loads(msgs)
        except Exception:
            return ""
    lines = []
    for m in msgs[-6:]:
        role = "고객" if m.get("role") == "user" else "AI"
        text = (m.get("text") or m.get("content") or "")[:300].strip()
        if text:
            lines.append(f"{role}: {text}")
    return "\n".join(lines)


def check_quality(db_conn) -> dict:
    """
    에이전트별 상담 품질 평가.
    반환: {
      "agents": {agent_key: {"label", "avg_score", "samples", "issues"}},
      "total_low_quality": int,
      "sample_count": int,
    }
    """
    cur = db_conn.cursor()
    try:
        _ensure_table(cur)
        db_conn.commit()
    except Exception as e:
        db_conn.rollback()
        print(f"[quality] 테이블 생성 오류: {e}")
        return {"error": str(e), "agents": {}}

    today = date.today()
    agent_results = {}
    total_low = 0
    total_samples = 0

    for agent_key, cfg in AGENTS.items():
        label = cfg["label"]
        role = cfg["role"]
        rows = _sample_agent(cur, cfg["where"], n=3)

        scores_list = []
        issues = []

        for row in rows:
            conv = _build_conversation(row.get("messages"))
            if not conv.strip():
                continue

            result = _call_gemini(SCORE_PROMPT.format(role=role, conversation=conv))
            if not result:
                continue

            accuracy    = float(result.get("accuracy", 0))
            role_fit    = float(result.get("role_fit", 0))
            helpfulness = float(result.get("helpfulness", 0))
            avg         = round((accuracy + role_fit + helpfulness) / 3, 1)
            issue_text  = result.get("issue") or None
            if isinstance(issue_text, str) and issue_text.lower() in ("null", "없음", "none", ""):
                issue_text = None
            needs_review = avg < 6.0 or issue_text is not None

            scores_list.append(avg)
            if issue_text:
                issues.append(f"[{label}] {issue_text}")
            if needs_review:
                total_low += 1

            try:
                cur.execute("""
                    INSERT INTO orchestrator_reviews
                        (review_date, agent, agent_label, consult_log_id,
                         accuracy, role_fit, helpfulness, avg_score, issue, needs_review)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (today, agent_key, label, row.get("id"),
                      accuracy, role_fit, helpfulness, avg, issue_text, needs_review))
            except Exception as db_err:
                print(f"[quality] DB 저장 오류 ({agent_key}): {db_err}")
                db_conn.rollback()

        try:
            db_conn.commit()
        except Exception:
            db_conn.rollback()

        avg_score = round(sum(scores_list) / len(scores_list), 1) if scores_list else None
        agent_results[agent_key] = {
            "label": label,
            "avg_score": avg_score,
            "sample_count": len(scores_list),
            "issues": issues,
            "status": (
                "no_data" if avg_score is None
                else "warning" if avg_score < 6.0
                else "ok"
            ),
        }
        total_samples += len(scores_list)

    return {
        "agents": agent_results,
        "total_low_quality": total_low,
        "sample_count": total_samples,
    }
