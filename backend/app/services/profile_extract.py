"""회사 자료(사업자등록증·크레탑·재무제표·회사소개서 등) → 기본정보 자동 추출.

자료유형 무관(type-agnostic): 각 파일에서 가능한 필드를 뽑아 병합 → PRO 고객 폼 필드로 매핑.
이미지=Gemini Vision, PDF/문서=텍스트 추출 후 Gemini.
"""
import io
import json
import re

_EXTRACT_PROMPT = """당신은 한국 기업 서류 판독 전문가입니다.
주어진 자료(사업자등록증·크레탑·재무제표·회사소개서·법인등기부 등 무엇이든)에서
아래 항목을 **자료에 실제로 적힌 것만** 추출해 JSON으로만 답하세요. 없으면 빈 문자열.
추측·창작 금지. 숫자는 자료의 값 그대로.
※ 개인정보(대표자 성명·주민등록번호·생년월일·개인 연락처)는 **추출하지 마세요.** 법인/사업 정보만.

{
  "doc_type": "사업자등록증|크레탑|재무제표|회사소개서|법인등기부|기타 중 가장 가까운 것",
  "company_name": "상호/법인명",
  "business_number": "사업자등록번호(000-00-00000)",
  "establishment_date": "개업일/설립일 (YYYY-MM-DD 또는 YYYY)",
  "industry": "업종/업태/주요사업 (텍스트, 예: 자동차부품 제조)",
  "revenue_won": "최근 연매출(원 단위 정수, 모르면 빈칸)",
  "employee_count": "상시 직원수(정수, 모르면 빈칸)",
  "address": "사업장 주소",
  "business_content": "사업내용 요약(회사소개서 기준 1~2문장, 없으면 빈칸)"
}
JSON 외 다른 텍스트 금지."""


def _gemini():
    import google.generativeai as genai
    import os
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_BATCH_API_KEY")
    if not key:
        return None
    genai.configure(api_key=key)
    return genai.GenerativeModel(
        "models/gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},  # 깨끗한 JSON 강제
    )


def _parse_json(text: str) -> dict:
    if not text:
        return {}
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def extract_one(content: bytes, ext: str, filename: str = "") -> dict:
    """파일 1건 → 구조화 필드 dict. 실패 시 {}."""
    model = _gemini()
    if not model:
        return {}
    ext = (ext or "").lower()
    try:
        if ext in ("jpg", "jpeg", "png", "webp", "gif", "bmp"):
            from PIL import Image
            img = Image.open(io.BytesIO(content))
            resp = model.generate_content([_EXTRACT_PROMPT, img])
        else:
            from app.services.doc_analysis_service import extract_text_from_bytes
            text = ""
            if ext == "pdf":
                try:
                    import pdfplumber
                    with pdfplumber.open(io.BytesIO(content)) as pdf:
                        text = "\n".join((p.extract_text() or "") for p in pdf.pages[:20])
                except Exception:
                    text = ""
            elif ext in ("txt", "csv", "md"):
                for enc in ("utf-8", "cp949", "euc-kr", "latin-1"):
                    try:
                        text = content.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue
            if not text:
                text = extract_text_from_bytes(content, ext, max_chars=20000) or ""
            if not text.strip():
                return {}
            resp = model.generate_content(_EXTRACT_PROMPT + "\n\n[자료 내용]\n" + text[:20000])
        d = _parse_json(getattr(resp, "text", "") or "")
        if d:
            d["_source_file"] = filename
        return d
    except Exception as e:
        print(f"[profile_extract] {filename}: {e}")
        return {}


_FIELDS = ["company_name", "business_number", "establishment_date",
           "industry", "revenue_won", "employee_count", "address", "business_content"]


def merge(results: list) -> tuple:
    """여러 파일 추출결과 병합 — 필드별 첫 비어있지 않은 값 채택 + 출처 기록."""
    merged, sources = {}, {}
    for r in results:
        if not r:
            continue
        src = r.get("_source_file") or r.get("doc_type") or "자료"
        for f in _FIELDS:
            v = str(r.get(f) or "").strip()
            if v and not merged.get(f):
                merged[f] = v
                sources[f] = r.get("doc_type") or src
    return merged, sources


def _revenue_bracket(won_text: str) -> str:
    digits = re.sub(r"[^\d]", "", won_text or "")
    if not digits:
        return ""
    won = int(digits)
    억 = won / 100_000_000
    if 억 < 1:
        return "1억 미만"
    if 억 < 5:
        return "1억~5억"
    if 억 < 10:
        return "5억~10억"
    if 억 < 50:
        return "10억~50억"
    return "50억 이상"


def _employee_bracket(cnt_text: str) -> str:
    digits = re.sub(r"[^\d]", "", cnt_text or "")
    if not digits:
        return ""
    n = int(digits)
    if n < 5:
        return "5인 미만"
    if n < 10:
        return "5~10인"
    if n < 30:
        return "10~30인"
    if n < 50:
        return "30~50인"
    return "50인 이상"


_CITY = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
         "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]


def to_form_fields(merged: dict) -> dict:
    """병합 결과 → PRO 고객 폼 필드. 업종은 KSIC 임베딩으로 코드 매핑."""
    out = {
        "company_name": merged.get("company_name", ""),
        "business_number": merged.get("business_number", ""),
        "industry": merged.get("industry", ""),
        "industry_code": "",
        "industry_name": "",
        "revenue_bracket": _revenue_bracket(merged.get("revenue_won", "")),
        "employee_bracket": _employee_bracket(merged.get("employee_count", "")),
        "establishment_year": "",
        "establishment_date": "",
        "address_city": "",
        "business_content": merged.get("business_content", ""),
    }
    # 설립연도/설립일
    est = merged.get("establishment_date", "")
    m = re.search(r"(19|20)\d{2}", est)
    if m:
        out["establishment_year"] = m.group(0)
        dm = re.search(r"((?:19|20)\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", est)
        if dm:
            out["establishment_date"] = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
        else:
            out["establishment_date"] = f"{m.group(0)}-01-01"
    # 소재지(시·도)
    addr = merged.get("address", "")
    out["address_city"] = next((c for c in _CITY if c in addr), "")
    # 업종 → KSIC
    ind = merged.get("industry", "")
    if ind:
        try:
            from app.main import _search_ksic_by_embedding
            cands = _search_ksic_by_embedding(ind, top_k=1)
            if cands:
                out["industry_code"] = cands[0].get("code", "")
                out["industry_name"] = cands[0].get("name", "")
        except Exception as e:
            print(f"[profile_extract] ksic map: {e}")
    return out
