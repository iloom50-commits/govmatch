"""정책자금/융자/보증 공고 전용 정밀 분석기

기존 doc_analysis_service.py의 일반 분석과 병렬로 동작하며,
금융 공고에서 금리/한도/담보/신청요건 등을 추가 추출하여 DB에 저장한다.
"""

import json
import os
import traceback

import google.generativeai as genai

from .schema import FINANCIAL_EXTRACTION_SCHEMA


def analyze_financial_announcement(
    announcement_id: int,
    title: str,
    full_text: str,
    existing_parsed: dict | None = None,
    existing_deep: dict | None = None,
) -> dict | None:
    """금융 공고 전용 정밀 분석 — Gemini로 금리/한도/담보/요건 추출

    Returns:
        dict: financial_details JSON (DB의 deep_analysis.financial_details에 저장)
        None: 분석 실패 시
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    # 분석 소스: full_text 우선, 없으면 기존 parsed_sections 활용
    source_text = full_text or ""
    if not source_text and existing_parsed:
        parts = []
        for key in ["eligibility", "support_details", "evaluation_criteria",
                     "required_docs", "timeline", "application_method",
                     "exclusions", "exceptions"]:
            val = existing_parsed.get(key, "")
            if val:
                parts.append(f"[{key}]\n{val}")
        source_text = "\n\n".join(parts)

    if not source_text or len(source_text) < 50:
        return None

    # 스키마를 프롬프트용 텍스트로 변환
    schema_text = _build_schema_prompt()

    prompt = f"""당신은 대한민국 정부 정책자금/융자/보증 공고를 분석하는 금융 전문가입니다.
아래 공고문에서 다음 정보를 **최대한 정확하게** 추출하세요.

공고 제목: {title}

[공고 원문]
{source_text[:12000]}

[추출 항목]
{schema_text}

[규칙]
1. 공고 원문에 명시된 내용만 추출하세요. 추측하지 마세요.
2. 명시되지 않은 항목은 null로 설정하세요.
3. 금리, 한도, 기간 등 숫자가 있으면 반드시 포함하세요.
4. 금리가 "정책자금 기준금리"처럼 참조형이면 그대로 적되, 괄호로 (현재 약 2.0~3.5% 수준) 추정값도 함께 기재하세요.
5. 신청자격의 제외대상, 제한조건은 빠짐없이 추출하세요.

반드시 순수 JSON만 반환하세요. JSON 외의 텍스트를 포함하지 마세요.
"""

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            "models/gemini-2.0-flash",
            generation_config={"max_output_tokens": 4096, "temperature": 0.1}
        )
        response = model.generate_content(prompt)
        raw = response.text.strip()

        # JSON 파싱 (마크다운 코드블록 제거)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        financial_details = json.loads(raw)
        return financial_details

    except Exception as e:
        print(f"[FinancialAnalyzer] ID={announcement_id} error: {e}")
        traceback.print_exc()
        return None


def store_financial_details(announcement_id: int, financial_details: dict, db_conn) -> bool:
    """금융 분석 결과를 DB에 저장 (deep_analysis.financial_details에 병합)"""
    try:
        cur = db_conn.cursor()

        # 기존 deep_analysis 로드
        cur.execute(
            "SELECT deep_analysis FROM announcement_analysis WHERE announcement_id = %s",
            (announcement_id,)
        )
        row = cur.fetchone()
        if not row:
            return False

        existing_deep = row.get("deep_analysis") or {}
        if isinstance(existing_deep, str):
            existing_deep = json.loads(existing_deep)

        # financial_details 병합
        existing_deep["financial_details"] = financial_details

        cur.execute(
            "UPDATE announcement_analysis SET deep_analysis = %s WHERE announcement_id = %s",
            (json.dumps(existing_deep, ensure_ascii=False), announcement_id)
        )
        db_conn.commit()
        return True

    except Exception as e:
        print(f"[FinancialAnalyzer] Store error ID={announcement_id}: {e}")
        return False


def ensure_financial_analysis(
    announcement_id: int,
    title: str,
    full_text: str,
    parsed_sections: dict | None,
    deep_analysis: dict | None,
    db_conn,
) -> dict | None:
    """금융 분석이 없으면 실행, 있으면 캐시 반환"""

    # 이미 분석 완료된 경우
    if deep_analysis and deep_analysis.get("financial_details"):
        return deep_analysis["financial_details"]

    # 분석 실행
    result = analyze_financial_announcement(
        announcement_id=announcement_id,
        title=title,
        full_text=full_text,
        existing_parsed=parsed_sections,
        existing_deep=deep_analysis,
    )

    if result and db_conn:
        store_financial_details(announcement_id, result, db_conn)

    return result


def _build_schema_prompt() -> str:
    """스키마를 프롬프트용 텍스트로 변환"""
    lines = []
    for section_key, section in FINANCIAL_EXTRACTION_SCHEMA.items():
        lines.append(f"\n## {section['description']} ({section_key})")
        for field_key, field_desc in section["fields"].items():
            lines.append(f"  - {field_key}: {field_desc}")
    return "\n".join(lines)
