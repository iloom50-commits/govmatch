"""
통합 AI 상담 엔진 — 중소기업 지원사업 전문 AI

두 가지 모드:
1. 자유 상담: 사용자가 아무 질문이나 → 전체 DB 검색 → 종합 답변
2. 공고 특화 상담: 특정 공고 선택 → 해당 공고 정밀 상담

공통: 동일한 지식 베이스(announcement_analysis)와 AI 엔진 사용
"""

import os
import json
import re
from typing import Optional, Dict, Any, List

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from collections import OrderedDict
import hashlib
import time


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FAQ 캐시 (같은 공고 + 유사 질문 → 캐시된 응답 재활용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _FAQCache:
    """공고별 FAQ 캐시. LRU 방식, TTL 1시간."""

    def __init__(self, max_size=500, ttl_seconds=3600):
        self._cache = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds

    def _normalize_query(self, query: str) -> str:
        """질문을 정규화하여 유사 질문을 같은 키로 매핑"""
        q = query.strip().lower()
        # 조사/어미 제거하여 유사 질문 매칭률 향상
        for suffix in ["요", "요?", "?", "해줘", "알려줘", "알려주세요",
                        "궁금해요", "궁금합니다", "인가요", "인가", "은요", "는요"]:
            if q.endswith(suffix):
                q = q[:-len(suffix)]
                break
        return q.strip()

    def _make_key(self, announcement_id: int, query: str) -> str:
        normalized = self._normalize_query(query)
        raw = f"{announcement_id}:{normalized}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, announcement_id: int, query: str) -> Optional[Dict]:
        key = self._make_key(announcement_id, query)
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["ts"] < self._ttl:
                self._cache.move_to_end(key)
                return entry["data"]
            else:
                del self._cache[key]
        return None

    def put(self, announcement_id: int, query: str, data: Dict):
        key = self._make_key(announcement_id, query)
        self._cache[key] = {"data": data, "ts": time.time()}
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)


_faq_cache = _FAQCache()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 지식 베이스 검색 (DB에서 관련 공고 찾기)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def search_announcements(query: str, db_conn, user_profile: dict = None, limit: int = 15) -> List[Dict]:
    """
    자연어 질문에서 관련 공고를 DB에서 검색.
    deep_analysis + announcements 테이블을 조인하여 검색.

    검색 전략:
    1단계: Gemini로 질문에서 검색 키워드/조건 추출
    2단계: SQL 검색 (키워드 매칭 + 자격요건 필터)
    3단계: 결과를 관련도 순으로 정렬
    """
    # 1단계: 질문에서 검색 조건 추출
    search_params = _extract_search_params(query, user_profile)

    # 2단계: DB 검색
    cur = db_conn.cursor()

    # 기본 SQL: 분석 미완료 공고도 포함 (LEFT JOIN)
    sql = """
        SELECT a.announcement_id, a.title, a.department, a.category,
               a.support_amount, a.deadline_date, a.region,
               a.summary_text, a.eligibility_logic, a.origin_url,
               aa.deep_analysis, aa.parsed_sections, aa.form_templates
        FROM announcements a
        LEFT JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
        WHERE 1=1
    """
    params = []

    # 마감되지 않은 공고 우선 (마감일 없는 것도 포함)
    sql += " AND (a.deadline_date IS NULL OR a.deadline_date >= CURRENT_DATE)"

    # 키워드 검색 (제목 + 요약 + deep_analysis에서)
    keywords = search_params.get("keywords", [])
    if keywords:
        keyword_conditions = []
        for kw in keywords[:5]:  # 최대 5개 키워드
            keyword_conditions.append(
                "(a.title ILIKE %s OR a.summary_text ILIKE %s OR a.department ILIKE %s OR COALESCE(aa.deep_analysis::text, '') ILIKE %s)"
            )
            params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%", f"%{kw}%"])
        if keyword_conditions:
            sql += " AND (" + " OR ".join(keyword_conditions) + ")"

    # 지역 필터
    region = search_params.get("region")
    if region and region != "전국":
        sql += " AND (a.region IS NULL OR a.region = '' OR a.region = '전국' OR a.region ILIKE %s)"
        params.append(f"%{region}%")

    # 카테고리 필터
    category = search_params.get("category")
    if category:
        sql += " AND a.category ILIKE %s"
        params.append(f"%{category}%")

    sql += " ORDER BY a.deadline_date ASC NULLS LAST LIMIT %s"
    params.append(limit)

    cur.execute(sql, params)
    rows = cur.fetchall()

    results = []
    for row in rows:
        r = dict(row)
        # JSONB 필드 파싱
        for field in ("deep_analysis", "parsed_sections", "form_templates", "eligibility_logic"):
            if r.get(field) and isinstance(r[field], str):
                try:
                    r[field] = json.loads(r[field])
                except (json.JSONDecodeError, TypeError):
                    r[field] = {}
        results.append(r)

    return results


def _extract_search_params(query: str, user_profile: dict = None) -> Dict[str, Any]:
    """질문에서 검색 파라미터 추출 (Gemini 사용)"""
    if not HAS_GENAI:
        return {"keywords": _simple_keyword_extract(query)}

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"keywords": _simple_keyword_extract(query)}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("models/gemini-2.0-flash")

    user_context = ""
    if user_profile:
        user_context = f"""
사용자 기업 정보:
- 업종: {user_profile.get('industry_code', '')}
- 매출: {user_profile.get('revenue_bracket', '')}
- 직원수: {user_profile.get('employee_count_bracket', '')}
- 소재지: {user_profile.get('address_city', '')}
- 관심분야: {user_profile.get('interests', '')}
"""

    prompt = f"""사용자가 중소기업 지원사업에 대해 질문했습니다. 이 질문에서 DB 검색에 사용할 파라미터를 추출하세요.
{user_context}
[질문]
{query}

[추출할 JSON]
{{
  "keywords": ["검색 키워드1", "키워드2"],
  "region": "지역 (없으면 null)",
  "category": "카테고리 (기술/창업/수출/인력/금융/경영 중 해당 시, 없으면 null)",
  "business_type": "기업유형 (소상공인/중소기업/스타트업 등, 없으면 null)",
  "intent": "질문 의도 요약 (한 줄)"
}}

반드시 순수 JSON만 반환하세요."""

    try:
        response = model.generate_content(prompt)
        return _parse_gemini_json(response.text)
    except Exception:
        return {"keywords": _simple_keyword_extract(query)}


def _simple_keyword_extract(query: str) -> List[str]:
    """Gemini 없이 간단한 키워드 추출 (fallback)"""
    stop_words = {"있어", "있나요", "뭐가", "어떤", "알려줘", "찾아줘", "있을까",
                  "수", "것", "거", "좀", "할", "하는", "받을", "되는", "지원",
                  "사업", "정부", "보조금", "가능", "해당", "대해"}
    words = re.findall(r'[가-힣a-zA-Z0-9]+', query)
    return [w for w in words if w not in stop_words and len(w) >= 2][:5]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 부처별 대표 연락처 매핑
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_DEPARTMENT_CONTACTS = {
    "중소벤처기업부": "📞 중소기업 통합콜센터: 1357",
    "중소기업": "📞 중소기업 통합콜센터: 1357",
    "소상공인시장진흥공단": "📞 소상공인 콜센터: 1588-5302",
    "소상공인": "📞 소상공인 콜센터: 1588-5302",
    "기술보증기금": "📞 기술보증기금: 1544-1120",
    "신용보증기금": "📞 신용보증기금: 1588-6565",
    "한국산업기술진흥원": "📞 KIAT: 1688-2518",
    "산업통상자원부": "📞 산업부 콜센터: 1577-0900",
    "과학기술정보통신부": "📞 과기부 콜센터: 1335",
    "고용노동부": "📞 고용노동부: 1350",
    "국토교통부": "📞 국토부: 1599-0001",
    "환경부": "📞 환경부: 1577-8866",
    "농림축산식품부": "📞 농림부: 1533-1315",
    "해양수산부": "📞 해수부: 044-200-5442",
    "문화체육관광부": "📞 문체부: 1600-0064",
    "교육부": "📞 교육부: 02-6222-6060",
    "국세청": "📞 국세청: 126",
    "특허청": "📞 특허청: 1544-8080",
    "관세청": "📞 관세청: 125",
}


def _get_department_contact(department: str) -> str:
    """부처명에서 대표 연락처를 찾아 반환"""
    if not department:
        return "📞 정부24 콜센터: 110"

    for key, contact in _DEPARTMENT_CONTACTS.items():
        if key in department:
            return contact

    return f"📞 정부24 콜센터: 110 (주관기관: {department})"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1.5. 단순 질문 직접 응답 (Gemini 호출 없이 DB 데이터로 응답)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 단순 질문 패턴 → DB 필드 매핑
_SIMPLE_QUERY_PATTERNS = {
    "자격": ("eligibility", "📋 자격요건"),
    "대상": ("eligibility", "📋 지원대상"),
    "조건": ("eligibility", "📋 자격요건"),
    "누가": ("eligibility", "📋 지원대상"),
    "지원금": ("support_details", "💰 지원내용"),
    "지원액": ("support_details", "💰 지원내용"),
    "금액": ("support_details", "💰 지원내용"),
    "얼마": ("support_details", "💰 지원내용"),
    "혜택": ("support_details", "💰 지원내용"),
    "마감": ("timeline", "📅 일정"),
    "기한": ("timeline", "📅 일정"),
    "언제까지": ("timeline", "📅 일정"),
    "신청기간": ("timeline", "📅 일정"),
    "일정": ("timeline", "📅 일정"),
    "서류": ("required_docs", "📎 제출서류"),
    "준비물": ("required_docs", "📎 제출서류"),
    "제출": ("required_docs", "📎 제출서류"),
    "신청방법": ("application_method", "📝 신청방법"),
    "어떻게 신청": ("application_method", "📝 신청방법"),
    "접수": ("application_method", "📝 신청방법"),
    "제외": ("exclusions", "⚠️ 제외대상"),
    "못 받": ("exclusions", "⚠️ 제외대상"),
    "불가": ("exclusions", "⚠️ 제외대상"),
    "가점": ("bonus_points", "⭐ 가점항목"),
    "우대": ("bonus_points", "⭐ 가점항목"),
    "심사": ("evaluation_criteria", "📊 심사기준"),
    "평가": ("evaluation_criteria", "📊 심사기준"),
    "배점": ("evaluation_criteria", "📊 심사기준"),
}


def _try_direct_response(query: str, announcement: Dict, deep_analysis_data: Dict) -> Optional[Dict]:
    """
    단순 질문이면 DB 데이터에서 직접 응답 (Gemini 호출 없이).
    복잡한 질문이면 None 반환 → Gemini로 넘김.
    """
    query_lower = query.strip()
    ps = (deep_analysis_data or {}).get("parsed_sections", {}) or {}

    # 매칭되는 패턴 찾기
    matched_fields = []
    matched_but_empty = []  # 패턴은 매칭되었지만 DB에 값이 없는 경우
    for keyword, (field, label) in _SIMPLE_QUERY_PATTERNS.items():
        if keyword in query_lower:
            value = ps.get(field, "")
            if value:
                matched_fields.append((label, value))
            else:
                matched_but_empty.append(label)

    # 매칭 없거나 복잡한 질문 (비교/판단 필요)
    complex_keywords = ["가능할까", "가능한가", "해당되", "받을 수 있", "비교", "추천", "어떤 것이", "우리 회사"]
    if any(ck in query_lower for ck in complex_keywords):
        return None  # Gemini로 넘김

    # 패턴은 매칭되었지만 DB에 데이터가 없는 경우 → "모르겠다" 응답
    if not matched_fields and matched_but_empty:
        a = announcement
        dept = a.get("department", "")
        contact = _get_department_contact(dept)
        missing_labels = ", ".join(set(matched_but_empty))
        message = (
            f"죄송합니다. **{a.get('title', '해당 공고')}**의 {missing_labels} 정보가 "
            f"현재 데이터에 포함되어 있지 않습니다.\n\n"
            f"정확한 내용은 아래 담당기관에 직접 확인하시기 바랍니다.\n\n"
            f"{contact}\n"
        )
        if a.get("origin_url"):
            message += f"🔗 공고 원문: {a['origin_url']}\n"

        return {
            "reply": message,
            "choices": ["다른 질문이 있어요", "이 공고에 지원 가능한지 알려주세요"],
            "done": False,
            "conclusion": None,
            "source": "db_direct_unknown",
        }

    if not matched_fields:
        return None  # Gemini로 넘김

    # 중복 제거
    seen = set()
    unique_fields = []
    for label, value in matched_fields:
        if label not in seen:
            seen.add(label)
            unique_fields.append((label, value))

    # 템플릿 기반 자연어 응답 생성
    a = announcement
    header = f"**{a.get('title', '공고')}** 정보입니다.\n\n"
    body = ""
    for label, value in unique_fields:
        # 값이 너무 길면 줄바꿈으로 가독성 확보
        body += f"### {label}\n{value}\n\n"

    footer = ""
    deadline = a.get("deadline_date")
    if deadline:
        footer += f"📅 마감일: **{deadline}**\n\n"

    message = header + body + footer + "더 자세한 상담이 필요하시면 아래 선택지를 눌러주세요."

    choices = ["이 공고에 우리 회사가 지원 가능할까요?", "제출서류 목록을 알려주세요", "신청 방법이 궁금해요"]
    # 이미 답한 내용은 선택지에서 제거
    answered_labels = {label for label, _ in unique_fields}
    if "📎 제출서류" in answered_labels:
        choices = [c for c in choices if "제출서류" not in c]
    if "📝 신청방법" in answered_labels:
        choices = [c for c in choices if "신청 방법" not in c]

    return {
        "reply": message,
        "choices": choices[:3],
        "done": False,
        "conclusion": None,
        "source": "db_direct",  # 프론트에서 "DB 기반 응답" 표시 가능
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 자유 상담 모드 (크로스 공고 검색 + 종합 답변)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def chat_free(
    messages: List[Dict],
    db_conn,
    user_profile: dict = None,
) -> Dict[str, Any]:
    """
    자유 상담: 사용자의 질문에 대해 전체 DB를 검색하여 종합 답변.

    Returns: {
        "reply": str,
        "announcements": [관련 공고 리스트],
        "done": bool
    }
    """
    if not HAS_GENAI:
        return {"reply": "AI 서비스를 사용할 수 없습니다.", "announcements": [], "done": True}

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"reply": "AI 서비스가 설정되지 않았습니다.", "announcements": [], "done": True}

    # 최신 사용자 메시지로 검색
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("text", "")
            break

    # DB에서 관련 공고 검색
    matched = search_announcements(last_user_msg, db_conn, user_profile, limit=15)

    # 검색 결과를 컨텍스트로 구성
    announcements_context = _format_announcements_for_prompt(matched)

    # 사용자 프로필 컨텍스트
    profile_context = ""
    if user_profile:
        profile_context = f"""
[사용자 기업 정보]
기업명: {user_profile.get('company_name', '미입력')}
업종코드: {user_profile.get('industry_code', '미입력')}
매출규모: {user_profile.get('revenue_bracket', '미입력')}
직원수: {user_profile.get('employee_count_bracket', '미입력')}
소재지: {user_profile.get('address_city', '미입력')}
설립일: {user_profile.get('establishment_date', '미입력')}
관심분야: {user_profile.get('interests', '미입력')}
"""

    system_prompt = f"""당신은 대한민국 중소기업 정부지원사업 전문 상담 AI입니다.
아래의 지식 베이스(분석된 공고 데이터)를 기반으로 사용자의 질문에 정확하고 상세하게 답변하세요.

{profile_context}

[지식 베이스 — 검색된 관련 공고 {len(matched)}건]
{announcements_context}

[핵심 규칙 — 할루시네이션 방지]
1. **오직 위 지식 베이스에 명시된 내용만으로 답변하세요.** 지식 베이스에 없는 금액, 자격요건, 일정 등을 절대 추측하거나 지어내지 마세요.
2. 답변의 각 핵심 정보에 **근거 공고명을 명시**하세요. 예: "「OO지원사업」에 따르면..."
3. 관련 공고가 있으면 구체적인 공고명, 지원금액, 자격요건, 마감일을 포함하여 안내하세요.
4. 사용자 기업 정보가 있으면 해당 기업에 맞는 공고를 우선 추천하고, 자격 충족 여부를 판단하세요.
5. **지식 베이스에 해당 정보가 없으면** 절대 추측하지 말고 솔직하게 "현재 보유한 공고 데이터에는 해당 내용이 없습니다."라고 답변한 뒤, 확인 가능한 담당기관 연락처를 안내하세요. 정부 지원사업 통합 문의: 📞 1357 (중소기업 통합콜센터)
6. 대화를 이어가며 추가 질문을 통해 더 정확한 추천을 해주세요.
7. 한국어로 답변하세요. 친절하고 전문적인 톤을 유지하세요.
8. 답변에 관련 공고의 announcement_id를 포함하여 사용자가 상세 상담으로 이동할 수 있게 하세요.
9. **법적 효력이 있는 판단(지원금 확정, 선정 보장 등)은 하지 마세요.** "최종 판단은 주관기관의 심사에 따릅니다"를 안내하세요.

[응답 형식 — 반드시 이 JSON 형식으로만 응답]
{{
  "message": "AI의 답변 텍스트 (마크다운 사용 가능, 충분히 상세하게)",
  "choices": ["후속 질문 선택지1", "선택지2"],
  "announcement_ids": [관련 공고 ID 배열],
  "done": false
}}
- choices: 사용자에게 제시할 추천 후속 질문 (2~4개)
- announcement_ids: 답변에서 언급한 공고들의 ID
- done: 상담 종료 시 true

반드시 순수 JSON만 반환하세요."""

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("models/gemini-2.0-flash")

    # 대화 히스토리 구성
    gemini_messages = []
    for msg in messages:
        role = "user" if msg.get("role") == "user" else "model"
        gemini_messages.append({"role": role, "parts": [msg.get("text", "")]})

    try:
        chat = model.start_chat(history=[
            {"role": "user", "parts": [system_prompt]},
            {"role": "model", "parts": ['{"message": "understood", "choices": [], "announcement_ids": [], "done": false}']},
            *gemini_messages[:-1]
        ])
        response = chat.send_message(gemini_messages[-1]["parts"][0] if gemini_messages else "시작")

        result = _parse_gemini_json(response.text)

        # 관련 공고 정보 첨부
        ann_ids = result.get("announcement_ids", [])
        related = [{"announcement_id": m["announcement_id"], "title": m["title"],
                     "support_amount": m.get("support_amount"), "deadline_date": str(m.get("deadline_date", "")),
                     "department": m.get("department")}
                    for m in matched if m["announcement_id"] in ann_ids]

        return {
            "reply": result.get("message", ""),
            "choices": result.get("choices", []),
            "announcements": related,
            "done": result.get("done", False),
        }
    except json.JSONDecodeError:
        return {"reply": response.text.strip() if 'response' in dir() else "응답 처리 오류", "choices": [], "announcements": [], "done": False}
    except Exception as e:
        print(f"[AIConsultant] chat_free error: {e}")
        return {"reply": "AI 응답 생성 중 오류가 발생했습니다.", "choices": [], "announcements": [], "done": False}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 공고 특화 상담 모드 (1개 공고 정밀 상담)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def chat_consult(
    announcement_id: int,
    messages: List[Dict],
    announcement: Dict,
    deep_analysis_data: Dict,
    user_profile: dict = None,
) -> Dict[str, Any]:
    """
    공고 특화 상담: 1개 공고에 대한 정밀 자격요건 상담.

    Returns: {
        "reply": str,
        "choices": list,
        "done": bool,
        "conclusion": str or None
    }
    """
    # 최신 사용자 메시지 추출
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("text", "")
            break

    # 1차: FAQ 캐시 확인 (같은 공고 + 유사 질문)
    if last_user_msg and len(messages) <= 2:  # 단일 질문일 때만 캐시 활용
        cached = _faq_cache.get(announcement_id, last_user_msg)
        if cached:
            cached["source"] = "faq_cache"
            return cached

    # 2차: 단순 질문이면 Gemini 호출 없이 DB에서 직접 응답
    if len(messages) > 1 and last_user_msg:  # 첫 메시지는 제외 (인사/안내 필요)
        direct = _try_direct_response(last_user_msg, announcement, deep_analysis_data)
        if direct:
            # 캐시에 저장
            _faq_cache.put(announcement_id, last_user_msg, direct)
            return direct

    if not HAS_GENAI:
        return {"reply": "AI 서비스를 사용할 수 없습니다.", "choices": [], "done": True, "conclusion": None}

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"reply": "AI 서비스가 설정되지 않았습니다.", "choices": [], "done": True, "conclusion": None}

    a = announcement
    deep = deep_analysis_data or {}
    da = deep.get("deep_analysis", {})
    ps = deep.get("parsed_sections", {})
    ft = deep.get("form_templates", [])

    # 자격요건 기본 정보
    elig = {}
    if a.get("eligibility_logic"):
        try:
            elig = json.loads(a["eligibility_logic"]) if isinstance(a["eligibility_logic"], str) else a["eligibility_logic"]
        except Exception:
            pass

    # 지원 요약
    support_summary = da.get("support_summary", {})
    support_info = ""
    if support_summary:
        support_info = f"""
지원금액: {support_summary.get('amount', '미상')}
지원방식: {support_summary.get('method', '미상')}
지원기간: {support_summary.get('duration', '미상')}"""

    # 심사기준
    eval_weights = da.get("evaluation_weights", [])
    eval_info = ""
    if eval_weights:
        eval_items = []
        for ew in eval_weights[:10]:
            w = ew if isinstance(ew, dict) else {}
            eval_items.append(f"- {w.get('criteria', '?')}: {w.get('weight', '?')} ({w.get('detail', '')})")
        eval_info = "\n[심사기준/배점]\n" + "\n".join(eval_items)

    # 신청서 양식
    form_info = ""
    if ft:
        form_parts = []
        for f in ft[:3]:
            if isinstance(f, dict):
                form_parts.append(f"▸ {f.get('form_name', '양식')}")
                for sec in f.get("sections", [])[:8]:
                    if isinstance(sec, dict):
                        fields_str = ", ".join(sec.get("fields", [])[:6])
                        form_parts.append(f"  - {sec.get('title', '')}: {fields_str}")
        if form_parts:
            form_info = "\n[신청서 양식 구조]\n" + "\n".join(form_parts)

    # 기업 정보
    company_info = ""
    if user_profile:
        company_info = f"""
[기업 정보]
사업자번호: {user_profile.get('business_number', '')}
기업명: {user_profile.get('company_name', '')}
설립일: {user_profile.get('establishment_date', '')}
소재지: {user_profile.get('address_city', '')}
업종코드: {user_profile.get('industry_code', '')}
매출규모: {user_profile.get('revenue_bracket', '')}
직원수: {user_profile.get('employee_count_bracket', '')}
관심분야: {user_profile.get('interests', '')}"""

    system_prompt = f"""당신은 대한민국 정부보조금 지원 자격 상담 전문 AI입니다.
아래 공고의 모든 정밀 분석 데이터를 기반으로 상세하고 정확한 상담을 제공하세요.

[공고 기본 정보]
제목: {a.get('title', '')}
부처: {a.get('department', '')}
카테고리: {a.get('category', '')}
지원금액: {a.get('support_amount', '')}
마감일: {a.get('deadline_date', '상시')}
지역: {a.get('region', '전국')}
자격요건(기본): {json.dumps(elig, ensure_ascii=False)[:500]}
{support_info}

[정밀 분석 — 공고 원문 기반]
신청자격 원문: {ps.get('eligibility', '')[:2000]}
제외대상 원문: {ps.get('exclusions', '')[:1000]}
예외조항 원문: {ps.get('exceptions', '')[:1000]}
가점항목 원문: {ps.get('bonus_points', '')[:500]}
제출서류 원문: {ps.get('required_docs', '')[:1000]}
심사기준 원문: {ps.get('evaluation_criteria', '')[:1000]}
지원내용 원문: {ps.get('support_details', '')[:1000]}
일정 원문: {ps.get('timeline', '')[:500]}
신청방법 원문: {ps.get('application_method', '')[:500]}

[구조화된 분석]
자격 상세: {json.dumps(da.get('eligibility_detail', {}), ensure_ascii=False)[:1000]}
제외 사유: {json.dumps(da.get('exclusion_rules', []), ensure_ascii=False)[:800]}
예외 조항: {json.dumps(da.get('exception_rules', []), ensure_ascii=False)[:800]}
가점 항목: {json.dumps(da.get('bonus_items', []), ensure_ascii=False)[:500]}
제출 서류: {json.dumps(da.get('required_documents', []), ensure_ascii=False)[:800]}
판단 불확실 영역: {json.dumps(da.get('gray_zones', []), ensure_ascii=False)[:500]}
주의사항: {json.dumps(da.get('key_warnings', []), ensure_ascii=False)[:500]}
{eval_info}
{form_info}
{company_info}

[핵심 규칙 — 할루시네이션 방지 & 응답 품질]
1. **오직 위에 제공된 공고 분석 데이터에 명시된 내용만으로 답변하세요.** 공고 데이터에 없는 금액, 조건, 일정, 서류를 절대 추측하거나 지어내지 마세요.
2. 답변의 각 핵심 정보에 **출처를 명시**하세요. 예: "공고 원문에 따르면...", "자격요건 항목에 명시된 바와 같이..."
3. **첫 응답(대화 시작)**: 반드시 아래 3가지 핵심 정보를 구조화하여 한 번에 제공하세요:
   - **📋 지원요건**: 지원 대상(업종, 기업규모, 설립연수, 지역 등), 제외대상
   - **💰 지원내용**: 지원금액/방식, 지원분야/트랙
   - **📝 신청방법**: 온라인/오프라인 접수처, 주요 제출서류, 마감일
   사용자가 별도로 물어보지 않아도 이 정보를 먼저 제공하세요.
4. **사용자가 이미 기업 정보를 제공한 경우** (대화 중 또는 [기업 정보] 섹션에 있는 경우): 일반 안내를 생략하고, 해당 기업의 자격 충족 여부를 즉시 판단하여 답변하세요. 충족/미충족/불확실 각 항목을 구체적으로 근거와 함께 설명하세요.
5. 항상 **추천 선택지 2~4개**를 제시하세요.
6. 기업 정보와 공고 자격요건을 비교하여 지원 가능 여부를 판단하되, 불확실한 부분은 반드시 추가 질문하세요.
7. **예외조항과 제외대상을 반드시 체크하세요.** 예외조항이 있으면 해당 여부를 질문하세요.
8. 최종 판단 시 "지원 가능", "조건부 가능", "지원 불가" 중 하나로 명확히 결론 + 근거 설명.
9. **공고 데이터에 해당 정보가 없거나 판단이 어려운 경우**, 절대 추측하지 말고 솔직하게 "이 내용은 공고문에 명시되어 있지 않아 정확한 답변이 어렵습니다."라고 답변한 뒤, 담당기관 연락처를 안내하세요: {_get_department_contact(a.get('department', ''))}
10. 가점 항목이 있으면 해당 여부도 안내하세요.
11. 심사기준/배점이 있으면 합격 가능성을 높이는 팁을 제공하세요.
12. 신청서 양식 정보가 있으면 작성 시 핵심 포인트를 안내하세요.
13. 한국어로, 친절하고 전문적인 톤. **답변은 충분히 상세하게** 작성하세요.
14. **법적 효력이 있는 판단(선정 보장, 지원금 확정)은 하지 마세요.** "최종 결과는 주관기관의 심사에 따릅니다"를 안내하세요.

[응답 형식 — 반드시 이 JSON 형식으로만 응답]
{{
  "message": "AI의 답변 텍스트 (충분히 상세하게, 마크다운 사용 가능)",
  "choices": ["선택지1", "선택지2", "선택지3"],
  "done": false,
  "conclusion": null
}}
- choices: 사용자에게 제시할 추천 선택지 (2~4개). 대화 종료 시 빈 배열 [].
- done: 최종 결론을 내렸으면 true.
- conclusion: done이 true일 때만 "eligible" | "conditional" | "ineligible" 중 하나.

반드시 순수 JSON만 반환하세요."""

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("models/gemini-2.0-flash")

    gemini_messages = []
    for msg in messages:
        role = "user" if msg.get("role") == "user" else "model"
        gemini_messages.append({"role": role, "parts": [msg.get("text", "")]})

    try:
        chat = model.start_chat(history=[
            {"role": "user", "parts": [system_prompt]},
            {"role": "model", "parts": ['{"message": "understood", "choices": [], "done": false, "conclusion": null}']},
            *gemini_messages[:-1]
        ])
        response = chat.send_message(gemini_messages[-1]["parts"][0] if gemini_messages else "시작")

        result = _parse_gemini_json(response.text)

        # 교차 검증: Gemini 응답을 DB 데이터와 대조
        verified_reply = _verify_response(
            result.get("message", ""), announcement, deep_analysis_data
        )

        response_data = {
            "reply": verified_reply,
            "choices": result.get("choices", []),
            "done": result.get("done", False),
            "conclusion": result.get("conclusion"),
        }

        # Gemini 응답도 캐시에 저장 (단일 질문일 때)
        if last_user_msg and len(messages) <= 2:
            _faq_cache.put(announcement_id, last_user_msg, response_data)

        return response_data
    except json.JSONDecodeError:
        return {"reply": response.text.strip() if 'response' in dir() else "응답 처리 오류", "choices": [], "done": False, "conclusion": None}
    except Exception as e:
        print(f"[AIConsultant] chat_consult error: {e}")
        return {"reply": "AI 응답 생성 중 오류가 발생했습니다.", "choices": [], "done": False, "conclusion": None}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 컨설턴트 모드 (고객사 조건 수집 → 가상 프로필 생성)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONSULTANT_REQUIRED_FIELDS = [
    "company_name", "establishment_date", "industry_code",
    "revenue_bracket", "employee_count_bracket", "address_city", "interests"
]

def chat_consultant(
    messages: List[Dict],
) -> Dict[str, Any]:
    """
    컨설턴트 모드: 대화형으로 고객사 조건을 수집하여 가상 프로필을 생성.

    AI가 대화를 통해 조건을 하나씩 수집하고, 충분히 수집되면
    structured profile JSON을 반환.

    Returns: {
        "reply": str,
        "choices": list,
        "done": bool,
        "profile": dict or None  — done=True일 때 가상 프로필
    }
    """
    if not HAS_GENAI:
        return {"reply": "AI 서비스를 사용할 수 없습니다.", "choices": [], "done": False, "profile": None}

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"reply": "AI 서비스가 설정되지 않았습니다.", "choices": [], "done": False, "profile": None}

    system_prompt = """당신은 중소기업 정부보조금 컨설턴트 AI입니다.
고객사의 기업 조건을 대화형으로 수집하여 지원사업 매칭에 필요한 프로필을 생성합니다.

[수집해야 할 필수 정보]
1. company_name: 기업명 (상호명)
2. establishment_date: 설립일 (YYYY-MM-DD 형식)
3. industry_code: 업종코드 (KSIC 5자리, 예: 62010) — 업종명을 말하면 적절한 코드로 변환
4. revenue_bracket: 매출규모 ("1억 미만", "1억~5억", "5억~10억", "10억~50억", "50억 이상" 중 하나)
5. employee_count_bracket: 직원수 ("5인 미만", "5인~10인", "10인~30인", "30인~50인", "50인 이상" 중 하나)
6. address_city: 소재지 (시/도 단위, 예: "서울", "경기", "부산")
7. interests: 관심분야 (쉼표 구분, 가능한 값: 창업지원, 기술개발, 수출마케팅, 고용지원, 시설개선, 정책자금, 디지털전환, 판로개척, 교육훈련, 에너지환경, 소상공인, R&D)

[대화 규칙]
1. 처음에는 간단히 인사하고, 기업명과 업종부터 물어보세요.
2. 한 번에 1~2개 항목씩 자연스럽게 질문하세요. 한꺼번에 모든 정보를 요구하지 마세요.
3. 사용자가 업종을 한글로 말하면 적절한 KSIC 코드로 변환하세요.
4. 이미 수집한 정보는 다시 묻지 마세요.
5. 모든 필수 정보가 수집되면 확인 요약을 보여주고 매칭을 시작할지 물어보세요.
6. 사용자가 확인하면 done=true로 profile을 반환하세요.
7. 한국어로, 친절하고 전문적인 톤으로 대화하세요.

[업종코드 참고]
- IT/소프트웨어: 62010
- 음식점: 56111
- 소매업: 47190
- 제조업(식품): 10000
- 제조업(전자): 26000
- 건설업: 41000
- 숙박업: 55000
- 교육서비스: 85000
- 전문서비스/컨설팅: 70000
- 디자인: 74000

[응답 형식 — 반드시 이 JSON 형식으로만 응답]
{
  "message": "AI의 대화 메시지 (마크다운 사용 가능)",
  "choices": ["추천 응답 선택지1", "선택지2"],
  "done": false,
  "collected": {"지금까지 수집된 필드명": "값", ...},
  "profile": null
}

done=true일 때 (모든 정보 수집 + 사용자 확인 완료):
{
  "message": "매칭을 시작하겠습니다!",
  "choices": [],
  "done": true,
  "collected": {...모든 필드...},
  "profile": {
    "company_name": "...",
    "establishment_date": "YYYY-MM-DD",
    "industry_code": "XXXXX",
    "revenue_bracket": "...",
    "employee_count_bracket": "...",
    "address_city": "...",
    "interests": "관심1,관심2"
  }
}

반드시 순수 JSON만 반환하세요."""

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("models/gemini-2.0-flash")

    gemini_messages = []
    for msg in messages:
        role = "user" if msg.get("role") == "user" else "model"
        gemini_messages.append({"role": role, "parts": [msg.get("text", "")]})

    try:
        chat = model.start_chat(history=[
            {"role": "user", "parts": [system_prompt]},
            {"role": "model", "parts": ['{"message": "understood", "choices": [], "done": false, "collected": {}, "profile": null}']},
            *gemini_messages[:-1]
        ])
        response = chat.send_message(gemini_messages[-1]["parts"][0] if gemini_messages else "시작")

        result = _parse_gemini_json(response.text)

        return {
            "reply": result.get("message", ""),
            "choices": result.get("choices", []),
            "done": result.get("done", False),
            "profile": result.get("profile"),
            "collected": result.get("collected", {}),
        }
    except json.JSONDecodeError:
        return {"reply": response.text.strip() if 'response' in dir() else "응답 처리 오류", "choices": [], "done": False, "profile": None, "collected": {}}
    except Exception as e:
        print(f"[AIConsultant] chat_consultant error: {e}")
        return {"reply": "AI 응답 생성 중 오류가 발생했습니다.", "choices": [], "done": False, "profile": None, "collected": {}}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 유틸리티
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _parse_gemini_json(text: str) -> dict:
    """Gemini 응답에서 JSON을 안전하게 추출. 코드블록, 앞뒤 텍스트 등 모두 처리."""
    text = text.strip()

    # 1) ```json ... ``` 블록 추출
    if "```json" in text:
        text = text.split("```json")[-1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # 2) 바로 파싱 시도
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3) 첫 번째 { ... 마지막 } 추출
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    # 4) 실패 — 원문 텍스트를 message로 감싸서 반환
    return {"message": text, "choices": [], "done": False, "conclusion": None}


def _verify_response(reply_text: str, announcement: Dict, deep_analysis_data: Dict) -> str:
    """
    Gemini 응답을 DB 데이터와 교차 검증.
    금액/마감일 등 핵심 수치가 DB와 다르면 경고 문구 + 담당기관 연락처 추가.
    """
    warnings = []
    a = announcement or {}
    dept_contact = _get_department_contact(a.get("department", ""))
    ps = (deep_analysis_data or {}).get("parsed_sections", {}) or {}

    # 마감일 검증
    db_deadline = str(a.get("deadline_date", "")) if a.get("deadline_date") else ""
    if db_deadline and db_deadline not in reply_text:
        # AI가 다른 마감일을 언급했는지 체크
        import re as _re
        date_patterns = _re.findall(r'\d{4}[-.]\d{1,2}[-.]\d{1,2}', reply_text)
        for dp in date_patterns:
            normalized = dp.replace(".", "-")
            if normalized != db_deadline and "마감" in reply_text:
                warnings.append(f"※ 정확한 마감일은 **{db_deadline}**입니다. (공고 DB 기준)")
                break

    # 지원금액 검증 — DB에 금액이 있는데 AI가 다른 금액을 언급한 경우
    db_amount = a.get("support_amount", "")
    if db_amount and db_amount not in reply_text:
        # AI 응답에 금액 관련 숫자가 있는지 간단 체크
        amount_keywords = ["억", "만원", "천만"]
        if any(kw in reply_text for kw in amount_keywords) and db_amount:
            if not any(part in reply_text for part in db_amount.split()):
                warnings.append(f"※ 공고 DB 기준 지원금액: **{db_amount}**")

    if warnings:
        warnings.append(f"정확한 확인이 필요하시면 {dept_contact}")
        return reply_text + "\n\n---\n" + "\n".join(warnings)
    return reply_text


def _format_announcements_for_prompt(announcements: List[Dict]) -> str:
    """검색된 공고 리스트를 프롬프트용 텍스트로 포맷"""
    if not announcements:
        return "(관련 공고를 찾지 못했습니다)"

    parts = []
    for i, ann in enumerate(announcements, 1):
        da = ann.get("deep_analysis", {}) or {}
        ps = ann.get("parsed_sections", {}) or {}
        support = da.get("support_summary", {})
        elig = da.get("eligibility_detail", {})

        part = f"""──── 공고 {i} (ID: {ann['announcement_id']}) ────
제목: {ann.get('title', '')}
부처: {ann.get('department', '')}
지원금액: {ann.get('support_amount', '') or (support.get('amount', '') if support else '')}
마감일: {ann.get('deadline_date', '상시')}
지역: {ann.get('region', '전국')}
대상: {', '.join(elig.get('business_types', [])) if elig else ''}
업종: {', '.join(elig.get('industries', [])[:5]) if elig else ''}
자격 원문: {ps.get('eligibility', '')[:500]}
지원내용: {ps.get('support_details', '')[:300]}
제외대상: {json.dumps(da.get('exclusion_rules', []), ensure_ascii=False)[:300]}"""
        parts.append(part)

    return "\n\n".join(parts)
