"""
공고문 정밀 분석 엔진 (독립 모듈 — 재사용 가능)

파이프라인:
1. 공고 페이지 접속 → 첨부파일(PDF/HWP) 자동 감지 → 다운로드
2. 원문 텍스트 추출 (PDF: pdfplumber, HWP: olefile, HTML: BeautifulSoup)
3. Gemini 정밀 분석 → 9개 섹션 분류 + 구조화
4. DB 저장 (학습 데이터쌍 축적)
5. 축적된 데이터로 향후 자체 모델 학습

재사용: 이 모듈은 다른 서비스에서도 독립적으로 import하여 사용 가능
"""

import os
import io
import json
import re
import time
import requests
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# 환경변수 로드 (독립 실행 시에도 작동하도록)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import olefile
    HAS_OLEFILE = True
except ImportError:
    HAS_OLEFILE = False

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}
_REMOVE_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "iframe"}

# 첨부파일로 인식할 확장자
_ATTACHMENT_EXTS = {".pdf", ".hwp", ".hwpx", ".docx", ".doc", ".zip"}
# 다운로드 URL 패턴 (href에 포함될 키워드)
_DOWNLOAD_PATTERNS = ["filedown", "download", "atchfile", "file_down", "cmm/fms"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1단계: 첨부파일 감지 + 다운로드
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def discover_attachments(page_url: str) -> List[Dict[str, str]]:
    """
    공고 상세 페이지에서 첨부파일 다운로드 링크를 자동 감지.
    Returns: [{"name": "파일명", "url": "다운로드URL", "type": "pdf|hwp|..."}]
    """
    if not page_url:
        return []

    try:
        resp = requests.get(page_url, headers=_HEADERS, timeout=15, allow_redirects=True)
        resp.encoding = "utf-8"
    except Exception as e:
        print(f"[Crawler] Page fetch failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    base_url = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"
    attachments = []
    seen_urls = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        text = a_tag.get_text(strip=True)

        # javascript:void(0) 등은 onclick 체크
        if href.startswith("javascript:"):
            onclick = a_tag.get("onclick", "")
            # onclick에서 URL 추출 시도
            url_match = re.search(r"['\"]([^'\"]*(?:download|fileDown|atchFile)[^'\"]*)['\"]", onclick, re.I)
            if url_match:
                href = url_match.group(1)
            else:
                continue

        # 확장자 또는 다운로드 패턴 매칭
        href_lower = href.lower()
        is_attachment = (
            any(href_lower.endswith(ext) for ext in _ATTACHMENT_EXTS)
            or any(pat in href_lower for pat in _DOWNLOAD_PATTERNS)
        )
        # 텍스트에 "다운로드"가 있으면 추가 체크
        if not is_attachment and ("다운로드" in text or "첨부" in text):
            is_attachment = any(pat in href_lower for pat in ["file", "down", "atch"])

        if not is_attachment:
            continue

        # 절대 URL 변환
        full_url = href if href.startswith("http") else urljoin(base_url, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # 파일 타입 추정
        file_type = _guess_file_type_from_url(href_lower, text)
        attachments.append({
            "name": text[:100] or os.path.basename(urlparse(href).path) or "attachment",
            "url": full_url,
            "type": file_type,
        })

    print(f"[Crawler] Found {len(attachments)} attachments on {page_url[:60]}")
    return attachments


def download_attachment(url: str, timeout: int = 30) -> Tuple[bytes, str]:
    """
    첨부파일 다운로드. Content-Disposition 또는 magic bytes로 실제 타입 판별.
    Returns: (content_bytes, detected_type)
    """
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            return b"", "unknown"

        content = resp.content
        detected = _detect_file_type(content, resp.headers.get("Content-Disposition", ""))
        return content, detected
    except Exception as e:
        print(f"[Crawler] Download failed: {e}")
        return b"", "unknown"


def _guess_file_type_from_url(href: str, text: str) -> str:
    for ext in [".pdf", ".hwp", ".hwpx", ".docx", ".xlsx", ".zip"]:
        if ext in href or ext in text.lower():
            return ext.lstrip(".")
    return "unknown"


def _detect_file_type(content: bytes, content_disposition: str) -> str:
    """Magic bytes 기반 파일 타입 판별"""
    if not content:
        return "unknown"
    if content[:4] == b"%PDF":
        return "pdf"
    if content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        # OLE2 — HWP 또는 DOC
        if b"HWP Document File" in content[:512]:
            return "hwp"
        return "ole"  # DOC 등
    if content[:4] == b"PK\x03\x04":
        # ZIP 기반 — HWPX, DOCX, XLSX, ZIP
        if ".hwpx" in content_disposition.lower():
            return "hwpx"
        if ".docx" in content_disposition.lower():
            return "docx"
        if ".xlsx" in content_disposition.lower():
            return "xlsx"
        return "zip"
    return "unknown"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2단계: 원문 텍스트 추출
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extract_text_from_bytes(content: bytes, file_type: str, max_chars: int = 50000) -> str:
    """바이트 데이터에서 텍스트 추출 (파일 타입별 분기)"""
    if file_type == "pdf":
        return _extract_from_pdf(content, max_chars)
    elif file_type in ("hwp", "ole"):
        return _extract_from_hwp(content, max_chars)
    elif file_type in ("hwpx", "docx"):
        return _extract_from_ooxml(content, max_chars)
    return ""


def extract_text_from_url(url: str, max_chars: int = 50000) -> Tuple[str, str]:
    """URL에서 직접 텍스트 추출 (단순 HTML/PDF 페이지용)"""
    if not url:
        return "", "html"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15, allow_redirects=True)
        content_type = resp.headers.get("Content-Type", "")

        if "pdf" in content_type.lower() or url.lower().endswith(".pdf"):
            return _extract_from_pdf(resp.content, max_chars), "pdf"

        resp.encoding = "utf-8"
        return _extract_from_html(resp.text, max_chars), "html"
    except Exception as e:
        print(f"[DocAnalysis] URL fetch failed: {e}")
        return "", "html"


def extract_full_text(page_url: str, summary_text: str = "", max_chars: int = 50000) -> Tuple[str, str, List[str]]:
    """
    공고 원문을 최대한 수집하는 통합 함수.

    전략:
    1. 공고 페이지에서 첨부파일 감지 → PDF/HWP 다운 → 텍스트 추출
    2. 첨부파일이 없거나 추출 실패 시 → HTML 본문 추출
    3. 그래도 부족하면 → DB의 summary_text를 fallback으로 사용

    Returns: (full_text, source_type, attachment_names)
    """
    all_texts = []
    source_type = "html"
    attachment_names = []

    # 1) 첨부파일에서 텍스트 추출 시도
    attachments = discover_attachments(page_url)
    for att in attachments:
        if att["type"] in ("pdf", "hwp", "hwpx", "docx", "ole", "unknown"):
            content, detected = download_attachment(att["url"])
            if not content:
                continue

            # unknown이면 magic bytes로 재판별
            if att["type"] == "unknown":
                detected = _detect_file_type(content, "")
            else:
                detected = att["type"]

            text = extract_text_from_bytes(content, detected, max_chars)
            if text and len(text) > 100:
                all_texts.append(f"[첨부: {att['name']}]\n{text}")
                source_type = detected
                attachment_names.append(att["name"])
                print(f"[Crawler] Extracted {len(text)} chars from {att['name']} ({detected})")

    # 2) 첨부파일에서 충분한 텍스트를 못 얻으면 HTML 본문도 추가
    total_from_attachments = sum(len(t) for t in all_texts)
    if total_from_attachments < 500:
        html_text, _ = extract_text_from_url(page_url)
        if html_text and len(html_text) > 100:
            all_texts.append(f"[공고 페이지 본문]\n{html_text}")
            if not attachment_names:
                source_type = "html"

    # 3) 그래도 부족하면 summary_text fallback
    total_text = sum(len(t) for t in all_texts)
    if total_text < 200 and summary_text:
        all_texts.append(f"[요약 정보]\n{summary_text}")
        if not attachment_names:
            source_type = "summary"

    full_text = "\n\n".join(all_texts)[:max_chars]
    # PostgreSQL은 NUL 문자를 허용하지 않음 + surrogate 문자 제거
    full_text = full_text.replace("\x00", "")
    full_text = full_text.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
    return full_text, source_type, attachment_names


def _extract_from_html(html: str, max_chars: int) -> str:
    """HTML에서 본문 텍스트 추출"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(_REMOVE_TAGS):
        tag.decompose()

    # 본문 영역 우선 탐색 (정부 사이트 공통 패턴)
    content_selectors = [
        ("div", "view_cont"), ("div", "dataView"), ("div", "view_con"),
        ("div", "bbs_view"), ("div", "content_view"), ("div", "articleView"),
        ("div", "sub_content"), ("div", "board_view"),
    ]
    content_div = None
    for tag_name, class_name in content_selectors:
        content_div = soup.find(tag_name, class_=class_name)
        if content_div:
            break

    target = content_div or soup

    # 표 데이터 보존
    tables_text = []
    for table in target.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            tables_text.append("\n".join(rows))

    text = target.get_text(separator="\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 1]
    body = "\n".join(lines)

    if tables_text:
        body += "\n\n[표 데이터]\n" + "\n---\n".join(tables_text)

    return body[:max_chars]


def _extract_from_pdf(content: bytes, max_chars: int) -> str:
    """PDF에서 텍스트 + 표 추출"""
    if not HAS_PDFPLUMBER:
        print("[DocAnalysis] pdfplumber not installed")
        return ""

    text_parts = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages[:50]:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)

                tables = page.extract_tables()
                for table in tables:
                    if table:
                        for row in table:
                            cells = [str(c or "").strip() for c in row]
                            text_parts.append(" | ".join(cells))
    except Exception as e:
        print(f"[DocAnalysis] PDF parse error: {e}")

    return "\n".join(text_parts)[:max_chars]


def _extract_from_hwp(content: bytes, max_chars: int) -> str:
    """HWP(한글) 파일에서 텍스트 추출 (olefile 기반)"""
    if not HAS_OLEFILE:
        print("[DocAnalysis] olefile not installed — cannot parse HWP")
        return ""

    try:
        ole = olefile.OleFileIO(io.BytesIO(content))
        text_parts = []

        # HWP의 본문은 BodyText/Section* 스트림에 저장
        for stream_name in ole.listdir():
            path = "/".join(stream_name)
            if path.startswith("BodyText/Section"):
                data = ole.openstream(stream_name).read()
                # HWP 본문은 zlib 압축되어 있을 수 있음
                text = _decode_hwp_body(data)
                if text:
                    text_parts.append(text)

        ole.close()
        return "\n".join(text_parts)[:max_chars]
    except Exception as e:
        print(f"[DocAnalysis] HWP parse error: {e}")
        return ""


def _decode_hwp_body(data: bytes) -> str:
    """HWP BodyText 스트림에서 텍스트 추출"""
    import zlib

    # 먼저 zlib 압축 해제 시도
    try:
        data = zlib.decompress(data, -15)
    except zlib.error:
        pass  # 비압축 데이터

    # HWP 바이너리에서 텍스트 추출 (간단한 방식)
    # HWP 본문 레코드에서 UTF-16LE 텍스트를 추출
    text_parts = []
    i = 0
    while i < len(data) - 4:
        # HWP 레코드 헤더: tag(10bit) + level(10bit) + size(12bit) = 4bytes
        header = int.from_bytes(data[i:i+4], "little")
        tag_id = header & 0x3FF
        size = (header >> 20) & 0xFFF

        if size == 0xFFF:
            # 확장 크기
            if i + 8 > len(data):
                break
            size = int.from_bytes(data[i+4:i+8], "little")
            i += 8
        else:
            i += 4

        if i + size > len(data):
            break

        # tag 67 = HWPTAG_PARA_TEXT (본문 텍스트)
        if tag_id == 67:
            try:
                # UTF-16LE로 디코딩, 제어문자 제거
                raw = data[i:i+size]
                chars = []
                j = 0
                while j < len(raw) - 1:
                    code = int.from_bytes(raw[j:j+2], "little")
                    if code == 0:
                        break
                    # HWP 제어문자 범위 건너뛰기
                    if code < 32 and code not in (9, 10, 13):
                        # 특수 제어: 확장 문자는 추가 바이트 건너뛰기
                        if code in (1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23):
                            j += 16  # 인라인 제어 확장
                            continue
                        j += 2
                        continue
                    # surrogate 범위 (0xD800-0xDFFF) 건너뛰기
                    if 0xD800 <= code <= 0xDFFF:
                        j += 2
                        continue
                    chars.append(chr(code))
                    j += 2
                line = "".join(chars).strip()
                if line:
                    text_parts.append(line)
            except Exception:
                pass

        i += size

    return "\n".join(text_parts)


def _extract_from_ooxml(content: bytes, max_chars: int) -> str:
    """HWPX/DOCX (ZIP 기반 XML) 에서 텍스트 추출"""
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            text_parts = []

            # HWPX: Contents/section*.xml
            # DOCX: word/document.xml
            for name in zf.namelist():
                if any(pat in name.lower() for pat in ["section", "document.xml", "content.xml"]):
                    xml_data = zf.read(name)
                    soup = BeautifulSoup(xml_data, "html.parser")
                    text = soup.get_text(separator="\n", strip=True)
                    if text:
                        text_parts.append(text)

            return "\n".join(text_parts)[:max_chars]
    except Exception as e:
        print(f"[DocAnalysis] OOXML parse error: {e}")
        return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3단계: Gemini 정밀 분석
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def analyze_announcement_deep(full_text: str, title: str = "") -> Dict[str, Any]:
    """
    공고 원문을 Gemini로 정밀 분석하여 구조화된 JSON 반환.
    독립적으로 사용 가능 — API 키만 환경변수에 설정하면 됨.
    """
    if not HAS_GENAI or not full_text:
        return {"parsed_sections": {}, "deep_analysis": {}}

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"parsed_sections": {}, "deep_analysis": {}}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("models/gemini-2.0-flash")

    text_for_analysis = full_text[:25000]

    prompt = f"""당신은 대한민국 정부지원사업 공고문 분석 최고 전문가입니다.
아래 공고문 원문을 **극도로 정밀하게** 분석하여 JSON으로 구조화하세요.

[공고 제목]
{title}

[공고 원문]
{text_for_analysis}

[분석 요구사항 — 반드시 이 JSON 구조를 따르세요]
{{
  "parsed_sections": {{
    "eligibility": "신청자격 관련 원문 그대로 발췌 (있는 그대로, 축약하지 말 것)",
    "exclusions": "제외대상/지원제외 관련 원문 발췌",
    "exceptions": "예외조항 원문 발췌 (단서 조항, '다만', '단,' 등)",
    "bonus_points": "가점/우대 항목 원문 발췌",
    "required_docs": "제출서류/구비서류 관련 원문 발췌",
    "evaluation_criteria": "심사기준/평가기준 원문 발췌",
    "support_details": "지원내용/지원금액/지원규모 원문 발췌",
    "timeline": "일정/기간/마감일 관련 원문 발췌",
    "application_method": "신청방법/접수방법 원문 발췌"
  }},
  "deep_analysis": {{
    "eligibility_detail": {{
      "business_types": ["대상 기업 유형 (소상공인, 중소기업, 스타트업 등)"],
      "founding_years": {{"min": null, "max": null, "exceptions": "예외 있으면 기술"}},
      "revenue_limit": {{"max_won": null, "exceptions": "예외 있으면 기술"}},
      "employee_range": {{"min": null, "max": null, "exceptions": "예외 있으면 기술"}},
      "region": "지역 제한 (전국이면 '전국')",
      "industries": ["대상 업종"],
      "required_certs": ["필요 인증 (벤처기업, 이노비즈 등)"],
      "other_conditions": ["기타 자격 조건"]
    }},
    "exclusion_rules": [
      {{"rule": "제외 사유", "detail": "상세 설명"}}
    ],
    "exception_rules": [
      {{"condition": "조건", "exception": "예외 내용", "source_text": "원문 근거"}}
    ],
    "bonus_items": [
      {{"item": "가점 항목", "score": "배점/가점", "condition": "적용 조건"}}
    ],
    "required_documents": [
      {{"doc_name": "서류명", "required": true, "note": "비고"}}
    ],
    "evaluation_weights": [
      {{"criteria": "심사 항목", "weight": "배점", "detail": "세부 기준"}}
    ],
    "gray_zones": [
      "판단이 불확실한 영역 (예: '중소기업이지만 계열사 합산 매출이 기준 초과일 경우')"
    ],
    "key_warnings": [
      "신청자가 반드시 알아야 할 주의사항"
    ],
    "support_summary": {{
      "amount": "지원금액 요약",
      "duration": "지원기간",
      "method": "지원방식 (보조금/융자/바우처 등)"
    }}
  }},
  "form_templates": [
    {{
      "form_name": "신청서/사업계획서 양식 이름",
      "sections": [
        {{
          "title": "섹션 제목 (예: 기업현황, 사업계획 등)",
          "fields": ["작성해야 할 항목1", "작성해야 할 항목2"],
          "description": "이 섹션에서 무엇을 작성해야 하는지 설명"
        }}
      ]
    }}
  ]
}}

[중요 규칙]
1. parsed_sections의 값은 원문 그대로 발췌하세요. AI가 요약하거나 바꾸지 마세요.
2. 공고문에 없는 항목은 빈 문자열 "" 또는 null 또는 빈 배열 []로 설정하세요.
3. 예외조항("단,", "다만,", "~의 경우는 제외" 등)을 절대 놓치지 마세요. 이것이 가장 중요합니다.
4. 금액은 원(KRW) 단위 숫자로 변환하세요 (예: 5억 = 500000000).
5. form_templates: 신청서/사업계획서 양식이 있으면 목차와 작성항목을 추출하세요. 양식이 없으면 빈 배열 []로.
   각 섹션의 fields는 실제로 신청자가 작성해야 하는 항목(빈칸, 기입란)을 추출하세요.
6. 반드시 순수 JSON만 반환하세요. 설명 텍스트 없이."""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        result = json.loads(text)
        return result
    except json.JSONDecodeError as e:
        print(f"[DocAnalysis] JSON parse error: {e}")
        return {"parsed_sections": {}, "deep_analysis": {}, "_parse_error": True}
    except Exception as e:
        print(f"[DocAnalysis] Gemini analysis error: {e}")
        return {"parsed_sections": {}, "deep_analysis": {}}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4단계: 통합 파이프라인 — 수집 → 분석 → 저장
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def analyze_and_store(
    announcement_id: int,
    origin_url: str,
    title: str,
    db_conn,
    summary_text: str = "",
) -> Dict[str, Any]:
    """
    공고 원문 수집 → 분석 → DB 저장 전체 파이프라인.

    Returns: {
        "success": bool,
        "source_type": str,
        "text_length": int,
        "attachments": list,
        "error": str or None
    }
    """
    print(f"[DocAnalysis] ▶ Analyzing #{announcement_id}: {title[:50]}...")
    result_info = {
        "success": False, "source_type": "", "text_length": 0,
        "attachments": [], "error": None,
    }

    # 1) 통합 텍스트 수집 (첨부파일 우선 → HTML → summary fallback)
    full_text, source_type, att_names = extract_full_text(origin_url, summary_text)
    result_info["source_type"] = source_type
    result_info["text_length"] = len(full_text)
    result_info["attachments"] = att_names

    if not full_text or len(full_text) < 50:
        msg = f"Insufficient text ({len(full_text)} chars)"
        print(f"[DocAnalysis] ✗ {msg}")
        result_info["error"] = msg
        return result_info

    # 2) Gemini 정밀 분석
    analysis = analyze_announcement_deep(full_text, title)
    parsed_sections = analysis.get("parsed_sections", {})
    deep_analysis = analysis.get("deep_analysis", {})
    form_templates = analysis.get("form_templates", [])

    if not parsed_sections and not deep_analysis:
        msg = "Analysis returned empty"
        print(f"[DocAnalysis] ✗ {msg}")
        result_info["error"] = msg
        return result_info

    # 3) DB 저장
    try:
        cur = db_conn.cursor()
        cur.execute("""
            INSERT INTO announcement_analysis
                (announcement_id, full_text, parsed_sections, deep_analysis, form_templates, source_type, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (announcement_id) DO UPDATE SET
                full_text = EXCLUDED.full_text,
                parsed_sections = EXCLUDED.parsed_sections,
                deep_analysis = EXCLUDED.deep_analysis,
                form_templates = EXCLUDED.form_templates,
                source_type = EXCLUDED.source_type,
                analysis_version = announcement_analysis.analysis_version + 1,
                updated_at = CURRENT_TIMESTAMP
        """, (
            announcement_id,
            full_text,
            json.dumps(parsed_sections, ensure_ascii=False),
            json.dumps(deep_analysis, ensure_ascii=False),
            json.dumps(form_templates, ensure_ascii=False),
            source_type,
        ))
        db_conn.commit()
        result_info["success"] = True
        print(f"[DocAnalysis] ✓ #{announcement_id} saved ({len(full_text)} chars, {source_type}, {len(att_names)} files)")
        return result_info
    except Exception as e:
        msg = f"DB save error: {e}"
        print(f"[DocAnalysis] ✗ {msg}")
        db_conn.rollback()
        result_info["error"] = msg
        return result_info


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5단계: 조회 + 온디맨드 분석
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_deep_analysis(announcement_id: int, db_conn) -> Optional[Dict[str, Any]]:
    """DB에서 정밀 분석 데이터 조회"""
    try:
        cur = db_conn.cursor()
        cur.execute(
            "SELECT parsed_sections, deep_analysis, form_templates, full_text, source_type FROM announcement_analysis WHERE announcement_id = %s",
            (announcement_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "parsed_sections": row["parsed_sections"] if isinstance(row["parsed_sections"], dict) else json.loads(row["parsed_sections"] or "{}"),
            "deep_analysis": row["deep_analysis"] if isinstance(row["deep_analysis"], dict) else json.loads(row["deep_analysis"] or "{}"),
            "form_templates": row["form_templates"] if isinstance(row["form_templates"], list) else json.loads(row["form_templates"] or "[]"),
            "full_text": row["full_text"],
            "source_type": row["source_type"],
        }
    except Exception as e:
        print(f"[DocAnalysis] Fetch error: {e}")
        return None


def ensure_analysis(announcement_id: int, db_conn) -> Optional[Dict[str, Any]]:
    """
    분석 데이터가 있으면 반환, 없으면 실시간 분석 후 반환.
    상담 시작 전 호출하는 통합 함수.

    Returns: 분석 데이터 dict 또는 None (분석 불가)
    """
    # 1) 이미 분석된 데이터 확인
    existing = get_deep_analysis(announcement_id, db_conn)
    if existing and existing.get("full_text"):
        return existing

    # 2) 공고 정보 조회
    cur = db_conn.cursor()
    cur.execute(
        "SELECT title, origin_url, summary_text FROM announcements WHERE announcement_id = %s",
        (announcement_id,)
    )
    ann = cur.fetchone()
    if not ann:
        return None

    # 3) 실시간 분석 실행
    result = analyze_and_store(
        announcement_id=announcement_id,
        origin_url=ann["origin_url"],
        title=ann["title"],
        db_conn=db_conn,
        summary_text=ann.get("summary_text") or "",
    )

    if result["success"]:
        return get_deep_analysis(announcement_id, db_conn)

    return None
