"""PRO 공고상담 AI (재설계 05) — LITE 공고상담과 완전 분리된 전문가 전용 엔진.

미션:
    컨설턴트가 알고 있는 특정 공고에 대해 고객을 위한 전문가 레벨 심화 분석·판정 제공.

LITE 공고상담(chat_consult)과의 차이:
    - 답변 대상: 고객(제3자) — 답변 톤은 컨설턴트용
    - 깊이: 심사 가중치·선정률·흔한 실수·신청 꿀팁
    - 대안: 비교표 (조건/금액/난이도)
    - 출력: 문서화 가능한 구조 (보고서 연계)

Feature flag: USE_PRO_ANNOUNCE_V2=true 일 때 활성
"""

import os
import json
import logging
import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


# Gemini response_schema — 2차 이후 expert_insights 포함
_PRO_ANNOUNCE_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "verdict_for_client": {
            "type": "string",
            "enum": ["eligible", "conditional", "ineligible"],
        },
        "expert_insights": {
            "type": "object",
            "properties": {
                "selection_rate_estimate": {"type": "string"},
                "key_evaluation_points": {"type": "array", "items": {"type": "string"}},
                "common_pitfalls": {"type": "array", "items": {"type": "string"}},
                "application_tips": {"type": "array", "items": {"type": "string"}},
                "similar_programs": {"type": "array", "items": {"type": "integer"}},
                "document_checklist": {"type": "array", "items": {"type": "string"}},
            },
        },
        "citations": {"type": "array", "items": {"type": "string"}},
        "choices": {"type": "array", "items": {"type": "string"}},
    },
}

# 1차 턴(공고 클릭 직후) 전용 Schema — 구조화된 공고 분석 + 간결 verdict
_PRO_BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "verdict_for_client": {
            "type": "string",
            "enum": ["eligible", "conditional", "ineligible"],
        },
        "citations": {"type": "array", "items": {"type": "string"}},
    },
}


def _build_client_context(selected_client: Optional[Dict]) -> str:
    """고객 프로필을 시스템 프롬프트용 텍스트 블록으로 변환."""
    if not selected_client:
        return "(고객 정보 없음 — 일반적 판정만 가능)"

    lines = []
    for label, key in [
        ("고객사명", "client_name"),
        ("업종코드", "industry_code"),
        ("업종명", "industry_name"),
        ("지역", "address_city"),
        ("매출", "revenue_bracket"),
        ("직원수", "employee_count_bracket"),
        ("설립일", "establishment_date"),
        ("관심분야", "interests"),
        ("대표 연령대", "representative_age"),
        ("보유 인증", "certifications"),
    ]:
        v = selected_client.get(key)
        if v:
            lines.append(f"- {label}: {v}")

    # Boolean 플래그
    for label, key in [
        ("여성기업", "is_women_enterprise"),
        ("청년기업(만39세↓)", "is_youth_enterprise"),
        ("재창업", "is_restart"),
    ]:
        if selected_client.get(key):
            lines.append(f"- {label}: 예")

    if selected_client.get("memo"):
        lines.append(f"- 메모: {selected_client['memo'][:200]}")

    # 업력 자동 계산
    try:
        est = selected_client.get("establishment_date")
        if est:
            if hasattr(est, "year"):
                est_y = est.year
            else:
                est_y = int(str(est)[:4])
            today = datetime.date.today()
            years = today.year - est_y
            if years > 0:
                lines.append(f"- **현재 업력: {years}년차**")
    except Exception:
        pass

    return "\n".join(lines) if lines else "(고객 정보 비어있음)"


def _build_announcement_context(ann: Dict, deep: Dict, parsed: Dict) -> str:
    """공고 데이터를 시스템 프롬프트용 텍스트 블록으로 변환."""
    lines = [
        f"공고 ID: {ann.get('announcement_id')}",
        f"공고명: {ann.get('title', '')}",
        f"주관기관: {ann.get('department', '미상')}",
        f"지원금액: {ann.get('support_amount', '미상')}",
        f"마감일: {ann.get('deadline_date', '미상')}",
    ]

    # parsed_sections
    if parsed:
        for section_name, key in [
            ("신청 자격", "eligibility"),
            ("지원 내용", "support_details"),
            ("심사 기준", "evaluation_criteria"),
            ("필수 서류", "required_docs"),
            ("신청 방법", "application_method"),
            ("일정", "timeline"),
        ]:
            content = parsed.get(key)
            if content:
                if isinstance(content, dict):
                    content = " / ".join(str(v) for v in content.values() if v)
                lines.append(f"\n[{section_name}]\n{str(content)[:800]}")

    # deep_analysis
    if deep:
        excl = deep.get("exclusion_rules") or []
        if excl:
            lines.append(f"\n[제외 조건]\n" + "\n".join(f"- {e}" for e in excl[:5]))

    return "\n".join(lines)


def _build_matched_context(matched_snapshot: Optional[List[Dict]], current_id: int) -> str:
    """이전 매칭 결과를 컨텍스트로 주입 (유사 대안 비교용)."""
    if not matched_snapshot:
        return ""

    others = [m for m in matched_snapshot if (m.get("announcement_id") or m.get("id")) != current_id]
    if not others:
        return ""

    lines = ["(같은 매칭 세션의 다른 공고 — 필요 시 비교·대안으로 언급)"]
    for m in others[:8]:
        aid = m.get("announcement_id") or m.get("id")
        title = (m.get("title") or m.get("program_title") or "")[:60]
        amount = (m.get("support_amount") or "")[:30]
        deadline = str(m.get("deadline_date") or "")[:10]
        lines.append(f"- ID {aid} | {title} | {amount} | ~{deadline}")
    return "\n".join(lines)


_SYSTEM_PROMPT_TMPL = """당신은 15년차 정부지원사업 전문 컨설턴트 "지원금AI"입니다.
컨설턴트(사용자)가 고객사를 위해 특정 공고에 대한 **전문가 레벨 심화 분석**을 요청합니다.

[오늘 날짜]
{today}

[고객 프로필]
{client_ctx}

[상담 공고]
{announcement_ctx}

[같은 세션의 다른 매칭 공고]
{matched_ctx}

[★ 전문가 레벨 답변 원칙 — 반드시 준수 ★]
1. **결론 먼저** — verdict_for_client (eligible/conditional/ineligible)
2. **근거 인용** — "[공고ID: N] 자격 요건" 형식으로 citations에 기재
3. **심사 가중치·선정률** — key_evaluation_points + selection_rate_estimate
4. **흔한 실수·함정** — common_pitfalls (3~5개)
5. **신청서 꿀팁** — application_tips (2~4개)
6. **유사 대안** — similar_programs (매칭 세션의 다른 공고 ID)
7. **필요 서류 체크리스트** — document_checklist

[차별화 — LITE 대비 +α]
- 일반 유저용 "쉬운 설명" 금지 — **컨설턴트가 고객에게 자료로 전달 가능한 수준**
- 추측 아닌 근거 기반 (공고 원문 + 유사 사업 패턴)
- 답변 대상: 컨설턴트(사용자), 설명 주체: 고객사

[금지]
- URL 노출 금지
- 공고 원문에 없는 구체 수치 추측 금지
- 범위 밖 대화 ("저는 지원사업 전문 컨설턴트입니다.")

[답변 구조 — message 필드]
## 결론
**{{eligible/conditional/ineligible}}**

## 근거 — 고객사 vs 공고 조건
| 조건 | 기준 | 고객사 | 판정 |
|---|---|---|---|

## 전문가 인사이트
**선정률 추정**: ...
**심사 가중치**:
**흔한 실수**:
**신청서 꿀팁**:

## 추천 액션
**필수 서류**: ...
**유사 대안**: [공고ID: N] 제목
**다음 단계**: ...

모든 필드(verdict_for_client, expert_insights, citations)를 반드시 채워서 JSON으로 응답."""


# [재설계 04 — 1차 턴 공고 분석 전용] 구조화된 12섹션 분석 + 하단 간결 verdict
_BRIEF_SYSTEM_PROMPT_TMPL = """당신은 15년차 정부지원사업 전문 컨설턴트 "지원금AI"입니다.
컨설턴트(사용자)가 매칭된 공고 중 하나를 선택해 **상세 상담을 방금 시작**했습니다.
첫 응답은 **공고 자체의 객관적 구조화 분석**부터 시작하세요.
전문가 인사이트(선정률·감점·팁·유사프로그램)는 사용자가 후속 질문할 때 제공합니다.

[오늘 날짜]
{today}

[고객 프로필]
{client_ctx}

[상담 공고]
{announcement_ctx}

[★ 1차 응답 원칙 ★]
1. 공고 원문에서 **객관적 사실만** 추출해 12섹션 구조로 정리
2. 해당 섹션 정보가 공고에 없으면 "(공고 원문 미기재)" 표기 — 추측·일반화 금지
3. 답변 마지막에 **고객사 기준 초기 검토** 표기
   - 공고의 핵심 자격 요건(지역, 업력, 매출, 직원수, 업종 등)을 고객 프로필 실제 값과 1:1 비교
   - 형식: "요건명: [공고 기준] vs [고객 실제 값] → ✅충족 / ❌미충족 / ⚠️확인필요"
   - 고객 프로필에 해당 값이 없으면 "⚠️ 확인 필요 (프로필 미입력)"로 표기 — 절대 추측하지 말 것
   - 마지막 줄: verdict_for_client 기반 종합 판정 한 줄
     * eligible  → "✅ 신청 가능 — 주요 조건 충족"
     * conditional → "⚠️ 조건부 가능 — [❌/⚠️ 항목명] 확인 후 신청 가능"
     * ineligible → "⊘ 신청 불가 — [❌ 항목명]: [공고 기준] (고객: [실제 값])"
4. citations: 공고 근거 항목 2~4개

[금지]
- 선정률·감점포인트·평가가중치·신청서팁·유사프로그램 **언급 금지** (2차 이후 질문에서 제공)
- URL 노출
- 공고에 없는 수치 추측

[답변 구조 — message 필드 (마크다운)]
## 📋 공고 개요
- 공고명 / 주관기관 / 접수기간 / 지원 한도 (공고 원문 기준)

## 🎯 사업 목적
공고가 명시한 목적 (간결히)

## 💰 지원 내용
지원 항목·규모·비율 (원문 수치 그대로)

## ✅ 신청 자격
대상 유형·업종·지역·기타 필수 조건

## 📝 필수 서류
공고에 명시된 제출 서류 목록

## ⏰ 심사 절차 및 일정
접수→평가→결과 단계와 일정

## ⚠️ 제외 대상 / 유의사항
배제 요건, 중복지원 제한 등

## 📞 문의처
주관기관 담당부서·연락처 (공고에 있으면)

---
**고객사 기준 초기 검토**

| 요건 | 공고 기준 | 고객 실제 값 | 판정 |
|---|---|---|---|
{{공고 자격 요건 항목들을 고객 프로필과 1:1 비교 — 예: 지역, 업력, 매출, 직원수, 업종 등}}

**종합**: {{eligible/conditional/ineligible 기반 한 줄 결론}}

출력은 **마크다운 텍스트만** 작성하세요. JSON, 코드블록, 백틱 등 금지."""


def chat_pro_announce(
    messages: List[Dict],
    announcement_id: int,
    db_conn,
    selected_client: Optional[Dict] = None,
    matched_snapshot: Optional[List[Dict]] = None,
    collected: Optional[Dict] = None,
    force_first_turn: bool = False,
) -> Dict[str, Any]:
    """PRO 공고상담 — 전문가 레벨 심화 분석.

    force_first_turn: True면 매칭 결과 안내 assistant 메시지가 섞여있어도 1차 턴으로 강제.
    (카드 클릭 직후 호출 시 반드시 True로 전달해야 12섹션 분석이 나옴)
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return _fallback("AI 서비스가 설정되지 않았습니다.")

    # 1) 공고 데이터 조회 + 분석 필요 시 자동 트리거
    try:
        cur = db_conn.cursor()
        cur.execute("""
            SELECT a.*, aa.parsed_sections, aa.deep_analysis, aa.full_text
            FROM announcements a
            LEFT JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
            WHERE a.announcement_id = %s
        """, (announcement_id,))
        row = cur.fetchone()
        if not row:
            return _fallback(f"공고 #{announcement_id}를 찾을 수 없습니다.")
        ann = dict(row)
        parsed = ann.get("parsed_sections") or {}
        deep = ann.get("deep_analysis") or {}

        # 분석 데이터 없으면 온디맨드 트리거
        if not parsed and not deep:
            try:
                from app.services.doc_analysis_service import ensure_analysis
                fresh = ensure_analysis(announcement_id, db_conn)
                if fresh:
                    parsed = fresh.get("parsed_sections") or {}
                    deep = fresh.get("deep_analysis") or {}
                    cur.execute("SELECT * FROM announcements WHERE announcement_id = %s", (announcement_id,))
                    r2 = cur.fetchone()
                    if r2:
                        ann.update(dict(r2))
            except Exception as ee:
                logger.warning(f"[pro_announce] on-demand analysis failed: {ee}")
    except Exception as e:
        logger.error(f"[pro_announce] DB load error: {e}")
        return _fallback("공고 정보 조회 중 오류가 발생했습니다.")

    # 2) 1차 턴 판정 — 명시적 override 우선, 없으면 assistant 메시지 유무
    is_first_turn = bool(force_first_turn) or not any(m.get("role") == "assistant" for m in messages)

    # 3) 시스템 프롬프트 구축 (1차 vs 2차+ 분기)
    today = datetime.date.today().isoformat()
    client_ctx = _build_client_context(selected_client)
    announcement_ctx = _build_announcement_context(ann, deep, parsed)

    if is_first_turn:
        # [재설계 04] 1차: LITE chat_consult 벤치마킹 — Schema 없이 자연어 마크다운
        system_prompt = _BRIEF_SYSTEM_PROMPT_TMPL.format(
            today=today,
            client_ctx=client_ctx,
            announcement_ctx=announcement_ctx,
        )
        last_msg = messages[-1].get("text", "") if messages else "이 공고를 분석해주세요."
        reply_text = ""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                "models/gemini-2.5-flash",
                system_instruction=system_prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 16384,
                },
            )
            response = model.generate_content(last_msg)
            reply_text = (response.text or "").strip()
        except Exception as e:
            logger.warning(f"[pro_announce brief] Gemini error: {e}, trying OpenAI")
            try:
                reply_text = _openai_fallback_text(system_prompt, messages)
            except Exception as oe:
                logger.error(f"[pro_announce brief] OpenAI fallback error: {oe}")
                return _fallback(f"AI 응답 생성 실패: {str(e)[:100]}")
        if not reply_text:
            # Gemini 빈 응답 → OpenAI로 재시도
            try:
                reply_text = _openai_fallback_text(system_prompt, messages)
            except Exception as oe:
                logger.error(f"[pro_announce brief] OpenAI retry error: {oe}")
        if not reply_text:
            return _fallback("공고 분석 응답이 비어있습니다. 잠시 후 다시 시도해주세요.")

        # 안전장치: 응답이 ```json { "message": "..." } ``` 블록이면 message만 추출
        stripped = reply_text.strip()
        if stripped.startswith("```"):
            try:
                # 코드블록 제거
                inner = stripped.split("```", 2)
                if len(inner) >= 2:
                    body = inner[1]
                    if body.lower().startswith("json"):
                        body = body[4:].lstrip()
                    parsed = json.loads(body)
                    if isinstance(parsed, dict) and parsed.get("message"):
                        reply_text = parsed["message"]
            except Exception:
                pass
        elif stripped.startswith("{"):
            # 순수 JSON 응답
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict) and parsed.get("message"):
                    reply_text = parsed["message"]
            except Exception:
                pass

        verdict = _extract_verdict_from_text(reply_text)
        return {
            "reply": reply_text,
            "choices": [],
            "verdict_for_client": verdict,
            "expert_insights": {},  # 1차엔 비움 — 프론트 패널 자동 숨김
            "citations": [],
            "done": False,
        }

    # 2차 이후: 전문가 인사이트 전면 제공 (Schema 강제 유지)
    matched_ctx = _build_matched_context(matched_snapshot, announcement_id)
    system_prompt = _SYSTEM_PROMPT_TMPL.format(
        today=today,
        client_ctx=client_ctx,
        announcement_ctx=announcement_ctx,
        matched_ctx=matched_ctx or "(없음)",
    )
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            "models/gemini-2.5-flash",
            system_instruction=system_prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": _PRO_ANNOUNCE_SCHEMA,
                "temperature": 0.3,
                "max_output_tokens": 8192,
            },
        )
        chat = model.start_chat(history=[
            {"role": "user", "parts": [m.get("text", "")]} if m.get("role") == "user"
            else {"role": "model", "parts": [m.get("text", "")]}
            for m in messages[:-1]
        ] if len(messages) > 1 else [])
        last_msg = messages[-1].get("text", "") if messages else "이 공고에 대해 전문가 분석해 주세요."
        response = chat.send_message(last_msg)
        raw = response.text or "{}"
        data = json.loads(raw)
    except Exception as e:
        logger.error(f"[pro_announce expert] Gemini error: {e}")
        try:
            data = _openai_fallback(system_prompt, messages)
        except Exception as oe:
            logger.error(f"[pro_announce expert] OpenAI fallback error: {oe}")
            return _fallback(f"AI 응답 생성 실패: {str(e)[:100]}")

    reply = data.get("message") or "분석을 생성하지 못했습니다."
    choices = data.get("choices") or [
        "유사 사업과 비교표 보기",
        "신청서 작성 가이드",
        "서류별 세부 요건",
    ]
    expert_insights = data.get("expert_insights") or {}
    if not expert_insights.get("document_checklist") and parsed.get("required_docs"):
        try:
            docs = parsed["required_docs"]
            if isinstance(docs, str):
                docs = [d.strip() for d in docs.split(",") if d.strip()][:10]
            elif isinstance(docs, list):
                docs = [str(d)[:60] for d in docs[:10]]
            if docs:
                expert_insights["document_checklist"] = docs
        except Exception:
            pass

    return {
        "reply": reply,
        "choices": choices,
        "verdict_for_client": data.get("verdict_for_client") or "undetermined",
        "expert_insights": expert_insights,
        "citations": data.get("citations") or [],
        "done": False,
    }


def _fallback(msg: str) -> Dict[str, Any]:
    return {
        "reply": msg,
        "choices": [],
        "verdict_for_client": "undetermined",
        "expert_insights": {},
        "citations": [],
        "done": False,
    }


def _openai_fallback(system_prompt: str, messages: List[Dict]) -> Dict:
    """Gemini 실패 시 OpenAI gpt-4o-mini로 JSON 응답 생성."""
    import httpx
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 미설정")

    oai_msgs = [{"role": "system", "content": system_prompt}]
    for m in messages:
        role = "user" if m.get("role") == "user" else "assistant"
        oai_msgs.append({"role": role, "content": m.get("text", "")})

    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "messages": oai_msgs,
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": 4096,
        },
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    return json.loads(text)


def _openai_fallback_text(system_prompt: str, messages: List[Dict]) -> str:
    """Gemini 실패 시 OpenAI gpt-4o-mini로 자연어 텍스트 응답 (1차 턴용)."""
    import httpx
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 미설정")
    oai_msgs = [{"role": "system", "content": system_prompt}]
    for m in messages:
        role = "user" if m.get("role") == "user" else "assistant"
        oai_msgs.append({"role": role, "content": m.get("text", "")})
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "messages": oai_msgs,
            "temperature": 0.3,
            "max_tokens": 6000,
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"] or ""


def _extract_verdict_from_text(text: str) -> str:
    """1차 턴 자연어 응답의 마지막 부분에서 verdict 판별.

    프롬프트는 마지막에 "고객사 기준 초기 검토: ⊘/⚠️/✅ ..." 형식을 지시함.
    """
    if not text:
        return "undetermined"
    # 마지막 200자만 검사
    tail = text[-300:]
    # 명시적 기호 우선
    if "⊘" in tail or "신청 불가" in tail or "부적합" in tail:
        return "ineligible"
    if "⚠️" in tail or "조건부" in tail:
        return "conditional"
    if "✅ 신청 가능" in tail or "신청 가능" in tail:
        return "eligible"
    return "undetermined"


def is_v2_enabled() -> bool:
    """Feature flag 확인."""
    return os.environ.get("USE_PRO_ANNOUNCE_V2", "false").lower() == "true"
