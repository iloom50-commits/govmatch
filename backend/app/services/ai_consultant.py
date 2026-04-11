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
import logging

logger = logging.getLogger(__name__)


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

    # 사용자 유형에 따라 target_type 필터 (기업 사용자면 business 우선)
    if user_profile and user_profile.get("business_number"):
        sql += " AND a.target_type = 'business'"

    # 키워드 검색 (제목 + 요약 + deep_analysis에서)
    # 공백 유무 변형도 함께 검색 (예: "AI 바우처" → "AI바우처"도 매칭)
    keywords = search_params.get("keywords", [])
    if keywords:
        keyword_conditions = []
        for kw in keywords[:5]:  # 최대 5개 키워드
            kw_nospace = kw.replace(" ", "")
            variants = [kw]
            if kw_nospace != kw:
                variants.append(kw_nospace)
            variant_conds = []
            for v in variants:
                variant_conds.append(
                    "(a.title ILIKE %s OR a.summary_text ILIKE %s OR a.department ILIKE %s OR COALESCE(aa.deep_analysis::text, '') ILIKE %s)"
                )
                params.extend([f"%{v}%", f"%{v}%", f"%{v}%", f"%{v}%"])
            keyword_conditions.append("(" + " OR ".join(variant_conds) + ")")
        if keyword_conditions:
            sql += " AND (" + " OR ".join(keyword_conditions) + ")"

    # 지역/카테고리는 ORDER BY 가점으로 처리 (AND 필수 조건에서 제외)
    # → 키워드 매칭이 핵심, 지역/카테고리 일치 시 상위 노출
    region = search_params.get("region")
    category = search_params.get("category")

    # 카테고리 한영 매핑
    _cat_map = {
        "기술": ["기술", "Tech", "기술개발", "R&D"],
        "창업": ["창업", "Entrepreneurship", "고용·창업"],
        "수출": ["수출", "수출지원", "Global"],
        "인력": ["인력", "인력지원", "고용", "Employment"],
        "금융": ["금융", "정책자금", "Finance"],
        "경영": ["경영", "소상공인", "Management"],
        "교육": ["교육", "Education", "교육훈련"],
    }

    # ORDER BY: 지역 일치 가점 + 카테고리 일치 가점 + 마감일 순
    order_parts = []
    order_params = []

    if region and region != "전국":
        order_parts.append("CASE WHEN a.region ILIKE %s THEN 0 ELSE 1 END")
        order_params.append(f"%{region}%")

    if category:
        cat_variants = _cat_map.get(category, [category])
        cat_case = " OR ".join(["a.category ILIKE %s"] * len(cat_variants))
        order_parts.append(f"CASE WHEN ({cat_case}) THEN 0 ELSE 1 END")
        order_params.extend([f"%{v}%" for v in cat_variants])

    order_parts.append("a.deadline_date ASC NULLS LAST")
    sql += " ORDER BY " + ", ".join(order_parts) + " LIMIT %s"
    params.extend(order_params)
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

    system_prompt = f"""당신은 대한민국 정부지원사업 전문 상담 AI입니다. 중소기업 지원뿐 아니라 개인 대상 복지·지원사업(청년, 출산·육아, 주거, 취업, 장학금, 의료, 장애, 저소득 등)도 전문적으로 상담합니다.
아래의 지식 베이스(분석된 공고 데이터)를 기반으로 사용자의 질문에 정확하고 상세하게 답변하세요.

{profile_context}

[지식 베이스 — 검색된 관련 공고 {len(matched)}건]
{announcements_context}
{_build_knowledge_context_from_announcements(matched, db_conn)}

[핵심 규칙 — 할루시네이션 방지]
1. **오직 위 지식 베이스에 명시된 내용만으로 답변하세요.** 지식 베이스에 없는 금액, 자격요건, 일정 등을 절대 추측하거나 지어내지 마세요.
2. 답변의 각 핵심 정보에 **근거 공고명을 명시**하세요. 예: "「OO지원사업」에 따르면..."
3. 관련 공고가 있으면 구체적인 공고명, 지원금액, 자격요건, 마감일을 포함하여 안내하세요.
4. 사용자가 기업 정보를 제공하면 기업에 맞는 공고를, 개인 조건(나이, 지역, 가구 상황 등)을 제공하면 개인 복지·지원사업을 우선 추천하고 자격 충족 여부를 판단하세요.
5. **지식 베이스에 해당 정보가 없으면** 절대 추측하지 말고 솔직하게 "현재 보유한 공고 데이터에는 해당 내용이 없습니다."라고 답변한 뒤, 확인 가능한 담당기관 연락처를 안내하세요. 정부 지원사업 통합 문의: 📞 1357 (중소기업 통합콜센터), 개인 복지 문의: 📞 129 (정부민원안내콜센터)
6. 대화를 이어가며 추가 질문을 통해 더 정확한 추천을 해주세요.
7. 한국어로 답변하세요. 친절하고 전문적인 톤을 유지하세요.
8. 답변에 관련 공고의 announcement_id를 포함하여 사용자가 상세 상담으로 이동할 수 있게 하세요.
9. **법적 효력이 있는 판단(지원금 확정, 선정 보장 등)은 하지 마세요.** "최종 판단은 주관기관의 심사에 따릅니다"를 안내하세요.

[응답 형식 — 반드시 이 JSON 형식으로만 응답. 필드 순서를 지키세요.]
{{
  "done": false,
  "announcement_ids": [관련 공고 ID 배열],
  "choices": ["후속 질문 선택지1", "선택지2"],
  "message": "AI의 답변 텍스트 (마크다운 사용 가능, 충분히 상세하게)"
}}
- done: 상담 종료 시 true
- announcement_ids: 답변에서 언급한 공고들의 ID
- choices: 사용자에게 제시할 추천 후속 질문 (2~4개)
- message: 답변 텍스트 (가장 마지막 필드로 배치)

반드시 순수 JSON만 반환하세요. JSON 외의 텍스트를 포함하지 마세요."""

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        "models/gemini-2.0-flash",
        generation_config={"max_output_tokens": 4096}
    )

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
        def _to_related(m):
            return {
                "announcement_id": m["announcement_id"], "title": m["title"],
                "support_amount": m.get("support_amount"), "deadline_date": str(m.get("deadline_date", "")),
                "department": m.get("department"), "category": m.get("category"),
                "summary_text": (m.get("summary_text") or "")[:120],
            }

        related = [_to_related(m) for m in matched if m["announcement_id"] in ann_ids]

        # Gemini가 announcement_ids를 비운 경우, 검색된 상위 공고를 fallback으로 첨부
        if not related and matched:
            related = [_to_related(m) for m in matched[:5]]

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
    db_conn=None,
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

    # 후속 질문 여부 (사용자 메시지가 2개 이상이면 후속)
    user_msg_count = sum(1 for m in messages if m.get("role") == "user")
    is_followup = user_msg_count >= 2

    # 전문가 패턴 감지: 배점/경쟁률/중복수혜/심사위원 등 깊이 있는 질문
    expert_keywords = ["배점", "가중치", "경쟁률", "선정률", "중복수혜", "중복 가능", "심사위원",
                       "평가지표", "평가표", "역대", "작년", "전년", "최근 선정", "유사 사례", "타사", "성공 사례",
                       "금리", "이자", "상환", "담보", "보증료", "한도", "융자", "대출", "자부담", "보증서",
                       "신용등급", "신보", "기보", "신용보증", "기술보증", "연체"]
    is_expert_question = any(kw in last_user_msg for kw in expert_keywords)

    # 1차: FAQ 캐시 확인 (같은 공고 + 유사 질문)
    # 중요: 캐시는 컨텍스트 의존성이 낮은 단순 질문에만 적용
    # (대화 1턴 + 짧은 일반 질문 + 페르소나 컨텍스트 없음)
    has_context_keywords = any(kw in last_user_msg for kw in [
        "매출", "직원", "년차", "업종", "지역", "예비창업", "1인", "창업자", "스타트업",
        "구직자", "청년", "분식집", "소상공인", "중견", "법인", "개인", "고객사", "우리"
    ])
    is_short_question = len(last_user_msg) < 60
    can_use_cache = (
        last_user_msg
        and len(messages) == 1  # 첫 질문만 (이전 대화 없음)
        and is_short_question
        and not has_context_keywords  # 페르소나/컨텍스트 정보 없는 일반 질문만
    )
    if can_use_cache:
        cached = _faq_cache.get(announcement_id, last_user_msg)
        if cached:
            cached["source"] = "faq_cache"
            return cached

    # 2차: 골든 답변 검색 (사용자 검증된 고품질 답변)
    if db_conn and last_user_msg and len(messages) > 1:
        golden = find_golden_answer(
            announcement_id, last_user_msg, db_conn,
            category=announcement.get("category")
        )
        if golden:
            return golden

    # 3차: 단순 질문이면 Gemini 호출 없이 DB에서 직접 응답
    # 컨텍스트 키워드 없는 단순 질문에만 적용 (페르소나/대화 컨텍스트 무시 방지)
    if len(messages) > 1 and last_user_msg and not has_context_keywords and is_short_question:
        direct = _try_direct_response(last_user_msg, announcement, deep_analysis_data)
        if direct:
            if can_use_cache:
                _faq_cache.put(announcement_id, last_user_msg, direct)
            return direct

    if not HAS_GENAI:
        return {"reply": "AI 서비스를 사용할 수 없습니다.", "choices": [], "done": True, "conclusion": None}

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"reply": "AI 서비스가 설정되지 않았습니다.", "choices": [], "done": True, "conclusion": None}

    a = announcement or {}
    deep = deep_analysis_data or {}
    da = deep.get("deep_analysis") or {}
    ps = dict(deep.get("parsed_sections") or {})
    ft = deep.get("form_templates") or []

    # ── 누락 필드 메인 DB 폴백 ──
    # parsed_sections가 비어있어도 메인 announcements 테이블 필드가 있으면 채움
    if not ps.get("eligibility") and a.get("eligibility_logic"):
        try:
            elig_logic = a["eligibility_logic"]
            if isinstance(elig_logic, str):
                elig_logic = json.loads(elig_logic)
            if isinstance(elig_logic, dict):
                ps["eligibility"] = json.dumps(elig_logic, ensure_ascii=False)[:1500]
        except Exception: pass

    if not ps.get("support_details") and a.get("summary_text"):
        ps["support_details"] = a.get("summary_text", "")[:1500]

    # 마감일/지원금은 항상 메인 DB에서 보장 (parsed에 없어도)
    main_deadline = str(a.get("deadline_date") or "").strip()
    main_amount = str(a.get("support_amount") or "").strip()

    # 자격요건 기본 정보
    elig = {}
    if a.get("eligibility_logic"):
        try:
            raw_elig = a["eligibility_logic"]
            elig = json.loads(raw_elig) if isinstance(raw_elig, str) else (raw_elig if isinstance(raw_elig, dict) else {})
        except Exception:
            elig = {}

    # 지원 요약
    support_summary = da.get("support_summary") or {}
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

    # 후속 질문 강화 컨텍스트
    followup_directive = ""
    if is_followup:
        followup_directive = """
[중요: 후속 질문 응답 규칙]
사용자가 추가 질문을 했습니다. 다음 원칙을 반드시 지키세요:
1. **첫 응답에서 답한 내용을 단순 반복하지 마세요.** 사용자는 이미 그 답을 봤습니다.
2. 사용자 질문에 **직접적이고 깊이 있게** 답하세요. 형식적인 헤더(📋💰📝)나 불필요한 인사 생략.
3. 공고 데이터에 명시 없으면, **유사 정부지원사업의 일반 패턴/통계**를 근거로 추정 답변을 제공하세요.
   예: "이 공고에는 자부담 비율이 명시되지 않았지만, 유사한 R&D 지원사업은 대개 25~30% 자부담을 요구합니다."
4. **숫자/비율/기간**으로 답할 수 있는 질문에는 반드시 숫자를 포함하세요.
5. "명시되지 않습니다"만 답하지 말고, 반드시 **추정/일반론/대안 방향**을 함께 제시하세요.
"""

    expert_directive = ""
    if is_expert_question:
        expert_directive = """
[중요: 전문가 질문 감지 — 컨설턴트/시니어 사용자]
사용자가 전문가 수준의 깊이 있는 질문을 했습니다 (배점/경쟁률/중복수혜/유사사례 등).

**필수 답변 원칙:**
1. "명시되지 않음"으로만 끝내지 마세요. 반드시 아래 구조로 답변하세요:
   ① 공고 데이터 확인 결과 (있으면 명시)
   ② 정부지원사업 일반 패턴/통계 (없으면 아래 데이터 활용)
   ③ 컨설턴트가 활용할 실무 팁

2. **활용 가능한 일반 통계 (이 데이터를 적극 인용하세요):**

   [평가 배점 일반 패턴]
   - 정부 R&D 지원사업: 사업성 30%, 기술성 30%, 경영능력 20%, 정책부합성 20%
   - 창업지원사업: 사업모델 35%, 실현가능성 30%, 시장성 20%, 대표역량 15%
   - 정책자금/융자: 신용평가 40%, 사업타당성 30%, 자금소요계획 20%, 상환능력 10%
   - 수출지원: 수출 잠재력 35%, 제품 경쟁력 30%, 추진계획 20%, 기업역량 15%

   [경쟁률 일반]
   - 중기부 창업지원: 평균 5~12:1 (예비창업패키지 8~15:1)
   - 정부 R&D 신청: 평균 3~7:1
   - 지자체 소상공인: 평균 2~5:1
   - 청년 정책자금: 평균 3~8:1

   [선정률]
   - TIPS: 약 8%
   - 창업도약패키지: 약 15~20%
   - 초기창업패키지: 약 20~25%
   - 정부 R&D 평균: 30~40%

   [중복수혜 일반 원칙]
   - 동일 회계연도 내 동일 사업 중복 불가
   - 동일 비목(인건비/장비비 등) 중복 불가
   - 다른 부처/다른 사업은 대부분 가능 (예: 중기부 R&D + 산업부 사업)
   - 정부지원금 + 지자체 보조금은 대부분 병행 가능

   [정책자금/융자 상세 — 사용자가 가장 많이 묻는 항목]
   - 금리: 정책자금 기준금리 연 2.0~3.5% (고정/변동 선택), 우대금리 적용 시 1.0~2.5%
   - 우대 조건: 청년기업(-0.3~0.5%p), 여성기업(-0.2~0.3%p), 혁신성장기업(-0.5%p), 사회적경제기업(-0.5%p)
   - 대출 한도: 개인사업자 1~5억, 중소기업 5~100억 (사업별 상이)
   - 상환 기간: 시설자금 8~10년(거치 3년), 운전자금 5~6년(거치 2년)
   - 담보: 신용보증서(신보/기보) 또는 부동산, 신용등급 BB 이상 권장
   - 자부담: 통상 10~30% (융자 비율 70~90%)
   - 심사 소요: 접수 후 2~4주, 보증서 발급 1~2주 추가
   - 연체 시: 연체이율 기본금리 + 3%p, 3회 이상 연체 시 기한이익 상실

   [보증 관련]
   - 신용보증기금(신보): 보증비율 85~100%, 보증료 연 0.5~2.0%
   - 기술보증기금(기보): 기술력 중심 평가, 보증비율 85~100%, 보증료 연 0.5~1.5%
   - 지역신용보증재단: 소상공인 위주, 보증한도 2~8억, 보증료 연 0.5~1.0%
   - 보증 심사기준: 신용등급(40%) + 기술/사업성(30%) + 재무건전성(20%) + 경영능력(10%)

   [융자 vs 보조금 차이 — 반드시 구분하여 안내]
   - 융자: 상환 의무 있음, 이자 발생, 담보/보증 필요, 한도 큼
   - 보조금: 상환 의무 없음(무상), 자부담 비율 있음, 정산 의무, 한도 작음
   - 바우처: 특정 용도 사용권, 자부담 10~30%, 기간 내 사용 필수

3. 가능하면 숫자와 구체 사례를 포함하세요. "유사 사업과 비교 시 강점은 X, 약점은 Y" 형태로.

4. 마지막에 "정확한 수치는 담당기관 확인 권장"을 한 줄로만 추가하세요.
"""

    # ── 분야별 전문 모듈 라우터 ──
    _title = a.get('title', '')
    _cat = a.get('category', '')
    _support = (ps.get('support_details') or '')

    domain_directive = ""
    domain_knowledge = ""
    financial_context = ""
    cross_ref_context = ""
    try:
        from app.services.consulting import detect_domain, get_domain_expert_directive, get_domain_knowledge

        detected_domain = detect_domain(_title, _cat, _support)

        if detected_domain:
            # 분야별 knowledge_base 지식 조회
            domain_knowledge = get_domain_knowledge(detected_domain, db_conn)

            # 금융 분야: 추가로 financial_analysis 모듈에서 상세 데이터 로드
            if detected_domain == "finance":
                try:
                    from app.services.financial_analysis import (
                        build_financial_context, ensure_financial_analysis,
                        get_similar_financial_announcements, build_cross_reference_context,
                    )
                    financial_details = ensure_financial_analysis(
                        announcement_id=announcement_id,
                        title=_title,
                        full_text=da.get("full_text") or "",
                        parsed_sections=ps,
                        deep_analysis=da,
                        db_conn=db_conn,
                    )
                    financial_context = build_financial_context(financial_details)
                    similar = get_similar_financial_announcements(
                        announcement_id=announcement_id,
                        category=_cat,
                        title=_title,
                        db_conn=db_conn,
                        limit=3,
                    )
                    cross_ref_context = build_cross_reference_context(similar)
                except Exception as fin_err:
                    print(f"[FinancialModule] Error: {fin_err}")

            # 분야별 전문가 지시문
            domain_directive = get_domain_expert_directive(
                detected_domain,
                financial_context=financial_context,
                cross_ref_context=cross_ref_context,
            )
    except Exception as dom_err:
        print(f"[DomainRouter] Error: {dom_err}")

    # domain_knowledge + domain_directive 결합
    loan_directive = ""
    if domain_directive:
        loan_directive = f"{domain_knowledge}\n{domain_directive}"

    system_prompt = f"""당신은 대한민국 정부 지원사업 자격 상담 전문 AI입니다. 기업 대상 보조금뿐 아니라 개인 대상 복지·지원사업(청년, 출산·육아, 주거, 취업, 장학금 등)도 전문적으로 상담합니다.
아래 공고의 모든 정밀 분석 데이터를 기반으로 상세하고 정확한 상담을 제공하세요.
{followup_directive}{expert_directive}{loan_directive}

[공고 기본 정보] ★ 이 정보는 절대 "명시되지 않음"이라고 답하지 마세요. 아래 값을 그대로 사용하세요.
제목: {a.get('title', '')}
부처: {a.get('department', '')}
카테고리: {a.get('category', '')}
지원금액: {main_amount or '(공고 원문 참조 필요)'}
마감일: {main_deadline or '상시 모집'}
지역: {a.get('region', '전국')}
자격요건(기본): {json.dumps(elig, ensure_ascii=False)[:500]}
{support_info}

[정밀 분석 — 공고 원문 기반]
신청자격 원문: {(ps.get('eligibility') or '')[:2000]}
제외대상 원문: {(ps.get('exclusions') or '')[:1000]}
예외조항 원문: {(ps.get('exceptions') or '')[:1000]}
가점항목 원문: {(ps.get('bonus_points') or '')[:500]}
제출서류 원문: {(ps.get('required_docs') or '')[:1000]}
심사기준 원문: {(ps.get('evaluation_criteria') or '')[:1000]}
지원내용 원문: {(ps.get('support_details') or '')[:1000]}
일정 원문: {(ps.get('timeline') or '')[:500]}
신청방법 원문: {(ps.get('application_method') or '')[:500]}

[구조화된 분석]
자격 상세: {json.dumps(da.get('eligibility_detail') or {}, ensure_ascii=False)[:1000]}
제외 사유: {json.dumps(da.get('exclusion_rules') or [], ensure_ascii=False)[:800]}
예외 조항: {json.dumps(da.get('exception_rules') or [], ensure_ascii=False)[:800]}
가점 항목: {json.dumps(da.get('bonus_items') or [], ensure_ascii=False)[:500]}
제출 서류: {json.dumps(da.get('required_documents') or [], ensure_ascii=False)[:800]}
판단 불확실 영역: {json.dumps(da.get('gray_zones') or [], ensure_ascii=False)[:500]}
주의사항: {json.dumps(da.get('key_warnings') or [], ensure_ascii=False)[:500]}
{eval_info}
{form_info}
{company_info}
{_build_knowledge_context(a.get('category', ''), db_conn)}

[핵심 규칙 — 할루시네이션 방지 & 응답 품질]
1. **오직 위에 제공된 공고 분석 데이터에 명시된 내용만으로 답변하세요.** 공고 데이터에 없는 금액, 조건, 일정, 서류를 절대 추측하거나 지어내지 마세요.
2. **출처 표기를 하지 마세요.** "(출처: ...)", "([공고 원문] 참고)", "(자격요건 항목 참고)" 같은 출처·참조 문구를 붙이지 마세요. 모든 정보는 공고 원문 기반이므로 별도 표기가 불필요합니다. 깔끔하게 정보만 전달하세요.
3. **첫 응답(대화 시작)**: 핵심 정보를 구조화하여 한 번에 제공하되, **빈 섹션은 표시하지 마세요**:
   - **📋 지원요건**: 지원 대상(업종, 기업규모, 설립연수, 지역 등), 제외대상
   - **💰 지원내용**: 지원금액/방식, 지원분야/트랙
   - **📝 신청방법**: 온라인/오프라인 접수처, 주요 제출서류, 마감일
   - **데이터에 정보가 없는 섹션은 통째로 생략**하세요. "명시되지 않습니다"를 매번 적지 마세요. 단 1~2개 핵심 정보(금액/마감)만 누락된 경우 마지막 줄에 한 번에 "💡 지원금액·마감일은 공고 원문 참조" 형태로 짧게 안내.
   - 정보가 너무 부족한 경우(2개 미만), 형식 헤더 없이 자연스러운 문장으로 핵심만 전달.
4. **사용자가 이미 기업 정보를 제공한 경우** (대화 중 또는 [기업 정보] 섹션에 있는 경우): 일반 안내를 생략하고, 해당 기업의 자격 충족 여부를 즉시 판단하여 답변하세요. 충족/미충족/불확실 각 항목을 구체적으로 근거와 함께 설명하세요.
5. 항상 **추천 선택지 2~4개**를 제시하세요.
6. 기업 정보와 공고 자격요건을 비교하여 지원 가능 여부를 판단하되, 불확실한 부분은 반드시 추가 질문하세요.
7. **예외조항과 제외대상을 반드시 체크하세요.** 예외조항이 있으면 해당 여부를 질문하세요.
8. 최종 판단 시 "지원 가능", "조건부 가능", "지원 불가" 중 하나로 명확히 결론 + 근거 설명. **반드시 done=true, conclusion 값을 설정하세요.**
9. **사용자가 기업 정보(업종, 설립연수, 매출, 직원수 등)를 제공하고 자격 판단을 요청하면, 2~3턴 이내에 결론을 내리세요.** 모든 정보가 100% 확인되지 않더라도, 확인된 항목 기반으로 "조건부 가능(conditional)" 등의 결론을 내리고 done=true로 설정하세요. 무한히 추가 질문만 하지 마세요.
10. **공고 데이터에 해당 정보가 없거나 판단이 어려운 경우**, 절대 추측하지 말고 솔직하게 "이 내용은 공고문에 명시되어 있지 않아 정확한 답변이 어렵습니다."라고 답변한 뒤, 담당기관 연락처를 안내하세요: {_get_department_contact(a.get('department', ''))}
11. 가점 항목이 있으면 해당 여부도 안내하세요.
12. 심사기준/배점이 있으면 합격 가능성을 높이는 팁을 제공하세요.
13. 신청서 양식 정보가 있으면 작성 시 핵심 포인트를 안내하세요.
14. 한국어로, 친절하고 전문적인 톤. **답변은 충분히 상세하게** 작성하세요.
15. **법적 효력이 있는 판단(선정 보장, 지원금 확정)은 하지 마세요.** "최종 결과는 주관기관의 심사에 따릅니다"를 안내하세요.

[응답 형식 — 반드시 이 JSON 형식으로만 응답]
**중요: 아래 필드 순서를 반드시 지키세요 (done → conclusion → choices → message 순서)**
{{
  "done": false,
  "conclusion": null,
  "choices": ["선택지1", "선택지2", "선택지3"],
  "message": "AI의 답변 텍스트 (충분히 상세하게, 마크다운 사용 가능)"
}}
- done: **[최우선 규칙] 입력 messages 배열 길이가 1~2개면 무조건 done=false입니다. 절대 예외 없음.** 첫 응답은 공고 정보 안내 + 후속 질문 유도만 하세요. done=true는 사용자가 구체적 조건을 제공하고 자격 판단을 요청한 경우(최소 3턴 이상, messages 5개 이상)에만 설정하세요.
- conclusion: done=true일 때 반드시 설정. "eligible"(지원 가능) | "conditional"(조건부 가능) | "ineligible"(지원 불가). **불확실한 부분이 있으면 "conditional"로 설정하고, 확인이 필요한 부분은 message에서 안내하세요.**
- choices: 사용자에게 제시할 추천 선택지 (2~4개). **done=true여도 빈 배열이 아닌 후속 안내 선택지를 제공하세요.**
- message: 답변 텍스트. **이 필드를 가장 마지막에 배치하세요.**

반드시 순수 JSON만 반환하세요. JSON 외의 텍스트를 포함하지 마세요."""

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        "models/gemini-2.0-flash",
        generation_config={"max_output_tokens": 4096}
    )

    gemini_messages = []
    for msg in messages:
        role = "user" if msg.get("role") == "user" else "model"
        gemini_messages.append({"role": role, "parts": [msg.get("text", "")]})

    try:
        chat = model.start_chat(history=[
            {"role": "user", "parts": [system_prompt]},
            {"role": "model", "parts": ['{"done": false, "conclusion": null, "choices": [], "message": "understood"}']},
            *gemini_messages[:-1]
        ])
        response = chat.send_message(gemini_messages[-1]["parts"][0] if gemini_messages else "시작")

        logger.info(f"[Gemini raw response length] {len(response.text)} chars")
        result = _parse_gemini_json(response.text)

        # 교차 검증: Gemini 응답을 DB 데이터와 대조
        verified_reply = _verify_response(
            result.get("message", ""), announcement, deep_analysis_data
        )

        done = result.get("done", False)
        conclusion = result.get("conclusion")

        # 후처리: AI가 텍스트에서 결론을 내렸지만 done/conclusion JSON 필드를 안 쓴 경우 자동 감지
        if not done and verified_reply:
            reply_lower = verified_reply.lower()
            # 마크다운 제거 후 매칭
            clean_reply = re.sub(r'[*_`#]', '', reply_lower)
            conclusion_keywords = {
                "conditional": ["조건부 가능", "조건부 지원 가능", "조건부로 가능", "조건부로 지원",
                                "조건부", "추가 확인이 필요", "일부 충족"],
                "eligible": ["지원 가능합니다", "지원 가능으로 판단", "자격을 충족합니다",
                             "지원이 가능합니다", "지원 자격을 충족", "지원 가능 여부: 가능",
                             "충족합니다", "해당됩니다"],
                "ineligible": ["지원 불가", "지원이 어렵", "자격을 충족하지 못",
                               "지원 대상이 아닙니다", "지원이 불가", "해당되지 않습니다"],
            }
            for conc_value, patterns in conclusion_keywords.items():
                if any(p in clean_reply for p in patterns):
                    logger.info(f"[Auto-detect] Found conclusion '{conc_value}' in reply text")
                    done = True
                    conclusion = conc_value
                    break
            if not done:
                logger.debug(f"[Auto-detect] No conclusion keywords found in reply (first 200 chars): {clean_reply[:200]}")

        response_data = {
            "reply": verified_reply,
            "choices": result.get("choices", []),
            "done": done,
            "conclusion": conclusion,
        }

        # Gemini 응답도 캐시에 저장 — 단순 일반 질문일 때만 (컨텍스트 의존성 없음)
        if can_use_cache:
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

    system_prompt = """당신은 대한민국 정부지원사업 전문 컨설턴트 AI입니다.
사용자의 조건을 파악하여 지원사업 매칭에 필요한 프로필을 생성합니다.
사업자(기업)와 개인(복지·생활지원) 모두 대응합니다.

[사용자 유형 판별]
- 사용자가 "기업", "사업자", "창업", "법인", "상호" 등을 언급하면 → **사업자 모드**
- 사용자가 "개인", "청년", "학생", "주부", "구직자", "출산", "육아", "주거" 등을 언급하면 → **개인 모드**
- 불분명하면 먼저 "사업자(기업)이신가요, 개인이신가요?" 질문

[사업자 모드 — 수집할 정보]
1. company_name: 기업명 (상호명)
2. establishment_date: 설립일 (YYYY-MM-DD 형식)
3. industry_code: 업종코드 (KSIC 5자리) — 업종명→자동 변환
4. revenue_bracket: 매출규모 ("1억 미만", "1억~5억", "5억~10억", "10억~50억", "50억 이상")
5. employee_count_bracket: 직원수 ("5인 미만", "5인~10인", "10인~30인", "30인~50인", "50인 이상")
6. address_city: 소재지 (시/도)
7. interests: 관심분야 (창업지원, 기술개발, 수출마케팅, 고용지원, 시설개선, 정책자금, 디지털전환, 판로개척, 교육훈련, 에너지환경, 소상공인, R&D)

[개인 모드 — 수집할 정보]
1. company_name: 이름 또는 "개인"
2. establishment_date: 생년월일 (YYYY-MM-DD) — 나이를 말하면 대략적 날짜로 변환
3. industry_code: 빈 문자열 ""
4. revenue_bracket: "1억 미만" (고정)
5. employee_count_bracket: "5인 미만" (고정)
6. address_city: 거주지 (시/도)
7. interests: 관심분야 (취업, 주거, 교육, 청년, 출산, 육아, 다자녀, 장학금, 의료, 장애, 저소득, 노인, 문화)

[핵심 대화 규칙]
1. **사용자가 이미 제공한 정보는 즉시 collected에 반영하세요.** 절대 다시 묻지 마세요.
2. 첫 메시지에서 여러 정보를 한꺼번에 제공하면, 모두 추출하여 collected에 저장하세요.
3. **개인 모드에서는 industry_code, revenue_bracket, employee_count_bracket을 자동 설정하세요.** 절대 묻지 마세요.
4. **업종명 한글 → KSIC 코드 자동 변환**, 매출/직원수 숫자 → bracket 자동 분류.
5. **모든 필드를 추정/변환 가능하면 즉시 done=true와 profile을 반환하세요.**
6. 정말 추정 불가능한 정보만 한 번에 물어보세요.
7. 한국어로, 전문적이면서 간결하게. 불필요한 인사/확인 질문 생략.

[업종코드 참고 — 사업자 모드 전용]
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
    model = genai.GenerativeModel(
        "models/gemini-2.0-flash",
        generation_config={"max_output_tokens": 4096}
    )

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

        collected = result.get("collected", {})
        done = result.get("done", False)
        profile = result.get("profile")

        # AI가 done=false인데 7개 필드가 모두 수집된 경우 → 강제 done=true
        REQUIRED = ["company_name", "establishment_date", "industry_code", "revenue_bracket", "employee_count_bracket", "address_city", "interests"]
        if not done and collected and all(collected.get(k) for k in REQUIRED):
            done = True
            profile = {k: collected[k] for k in REQUIRED}

        return {
            "reply": result.get("message", "") if not done else "모든 정보가 확인되었습니다. 매칭을 시작합니다!",
            "choices": result.get("choices", []) if not done else [],
            "done": done,
            "profile": profile,
            "collected": collected,
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

    # 4) 잘린 JSON 복구 시도 — Gemini가 긴 응답에서 JSON을 완성하지 못한 경우
    if first_brace != -1:
        partial = text[first_brace:]
        logger.warning(f"[_parse_gemini_json] Truncated JSON detected, length={len(partial)}")

        # done 추출 (새 순서에서는 맨 앞에 위치)
        done_match = re.search(r'"done"\s*:\s*(true|false)', partial)
        done = done_match.group(1) == "true" if done_match else False
        # conclusion 추출
        conc_match = re.search(r'"conclusion"\s*:\s*"(\w+)"', partial)
        conclusion = conc_match.group(1) if conc_match else None
        # choices 추출 시도 — 중첩 대괄호 없는 단순 문자열 배열
        choices_match = re.search(r'"choices"\s*:\s*\[(.*?)\]', partial, re.DOTALL)
        choices = []
        if choices_match:
            try:
                choices = json.loads("[" + choices_match.group(1) + "]")
            except Exception:
                pass
        # message 필드 추출 — "message": " 이후 마지막 " 까지 (잘린 경우도 최대한 복구)
        msg_match = re.search(r'"message"\s*:\s*"', partial)
        message_text = ""
        if msg_match:
            msg_start = msg_match.end()
            # message 내용 끝: 마지막 닫는 따옴표 찾기 (이스케이프된 따옴표 스킵)
            remaining = partial[msg_start:]
            # 정상 종료: "로 끝나는 경우
            end_match = re.search(r'(?<!\\)"', remaining)
            if end_match:
                message_text = remaining[:end_match.start()]
            else:
                # 잘린 경우: 남은 텍스트 전체를 message로 사용
                message_text = remaining.rstrip().rstrip('}').rstrip(',').rstrip()
            # JSON 이스케이프 해제
            message_text = message_text.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
        else:
            message_text = text

        logger.info(f"[_parse_gemini_json] Recovered: done={done}, conclusion={conclusion}, choices_count={len(choices)}, msg_len={len(message_text)}")
        return {"message": message_text, "choices": choices, "done": done, "conclusion": conclusion}

    # 5) 완전 실패 — 원문 텍스트를 message로 감싸서 반환
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. 순환 학습 시스템 — 지식 저장/조회 + 골든 답변
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _normalize_question(text: str) -> str:
    """질문을 정규화하여 유사 질문 매칭에 사용"""
    q = text.strip().lower()
    # 조사/어미 제거
    for suffix in ["요", "요?", "?", "해줘", "알려줘", "알려주세요",
                    "궁금해요", "궁금합니다", "인가요", "인가", "은요", "는요",
                    "하나요", "인지요", "입니다", "합니다", "하세요", "해주세요"]:
        if q.endswith(suffix):
            q = q[:-len(suffix)]
            break
    return q.strip()


def _question_hash(text: str) -> str:
    """질문의 해시값 생성 (골든 답변 매칭용)"""
    normalized = _normalize_question(text)
    return hashlib.md5(normalized.encode()).hexdigest()


def find_golden_answer(announcement_id: int, question: str, db_conn, category: str = None) -> Optional[Dict]:
    """
    골든 답변 검색: 같은 공고(또는 같은 카테고리)에서 검증된 답변을 찾음.

    검색 우선순위:
    1. 같은 공고 + 같은 질문 해시 (정확 매칭)
    2. 같은 카테고리 + 같은 질문 해시 (유사 공고 매칭)

    Returns: {"answer_text": ..., "choices": ..., "conclusion": ...} or None
    """
    q_hash = _question_hash(question)
    cur = db_conn.cursor()

    try:
        # 1순위: 같은 공고 + 질문 해시
        cur.execute("""
            SELECT id, answer_text, choices, conclusion
            FROM golden_answers
            WHERE announcement_id = %s AND question_hash = %s
              AND is_active = TRUE AND quality_score >= 0.6
            ORDER BY quality_score DESC, helpful_count DESC
            LIMIT 1
        """, (announcement_id, q_hash))
        row = cur.fetchone()

        if row:
            # use_count 증가는 하지 않음 (golden_answers에는 없음)
            r = dict(row)
            return {
                "reply": r["answer_text"],
                "choices": r["choices"] if isinstance(r["choices"], list) else json.loads(r["choices"] or "[]"),
                "done": False,
                "conclusion": r.get("conclusion"),
                "source": "golden_exact",
            }

        # 2순위: 같은 카테고리 + 질문 해시 (다른 공고의 검증된 답변)
        if category:
            cur.execute("""
                SELECT id, answer_text, choices, conclusion
                FROM golden_answers
                WHERE category = %s AND question_hash = %s
                  AND is_active = TRUE AND quality_score >= 0.8
                  AND announcement_id != %s
                ORDER BY quality_score DESC, helpful_count DESC
                LIMIT 1
            """, (category, q_hash, announcement_id))
            row = cur.fetchone()

            if row:
                r = dict(row)
                return {
                    "reply": r["answer_text"] + "\n\n※ 유사 공고의 검증된 답변을 참고하였습니다. 정확한 내용은 해당 공고를 확인해 주세요.",
                    "choices": r["choices"] if isinstance(r["choices"], list) else json.loads(r["choices"] or "[]"),
                    "done": False,
                    "conclusion": None,  # 다른 공고 답변이므로 결론은 제외
                    "source": "golden_category",
                }
    except Exception as e:
        logger.warning(f"[GoldenAnswer] search error: {e}")

    return None


def save_golden_answer(
    consult_log_id: int,
    announcement_id: int,
    category: str,
    messages: list,
    conclusion: str,
    db_conn,
):
    """
    상담 완료 + "도움됐어요" 피드백 → 골든 답변으로 저장.
    대화에서 주요 Q&A 쌍을 추출하여 저장.
    """
    try:
        cur = db_conn.cursor()

        # 대화에서 Q&A 쌍 추출 (user 질문 → 다음 assistant 답변)
        pairs = []
        for i, msg in enumerate(messages):
            if msg.get("role") == "user" and i + 1 < len(messages):
                next_msg = messages[i + 1]
                if next_msg.get("role") == "assistant":
                    pairs.append((msg["text"], next_msg["text"]))

        if not pairs:
            return

        for question, answer in pairs:
            q_hash = _question_hash(question)
            normalized = _normalize_question(question)

            # 이미 같은 공고+질문 골든 답변이 있으면 helpful_count만 증가
            cur.execute("""
                SELECT id FROM golden_answers
                WHERE announcement_id = %s AND question_hash = %s
            """, (announcement_id, q_hash))
            existing = cur.fetchone()

            if existing:
                cur.execute("""
                    UPDATE golden_answers
                    SET helpful_count = helpful_count + 1, updated_at = NOW()
                    WHERE id = %s
                """, (existing["id"],))
            else:
                cur.execute("""
                    INSERT INTO golden_answers
                    (announcement_id, category, question_pattern, question_hash,
                     answer_text, conclusion, source_consult_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (announcement_id, category, normalized, q_hash,
                      answer, conclusion, consult_log_id))

        db_conn.commit()
        logger.info(f"[GoldenAnswer] Saved {len(pairs)} Q&A pairs for announcement {announcement_id}")
    except Exception as e:
        logger.warning(f"[GoldenAnswer] save error: {e}")
        try:
            db_conn.rollback()
        except Exception:
            pass


def mark_golden_inaccurate(consult_log_id: int, db_conn):
    """
    "부정확해요" 피드백 → 해당 상담에서 파생된 골든 답변의 inaccurate_count 증가.
    quality_score가 0.4 미만이면 자동 비활성화.
    """
    try:
        cur = db_conn.cursor()
        cur.execute("""
            UPDATE golden_answers
            SET inaccurate_count = inaccurate_count + 1, updated_at = NOW()
            WHERE source_consult_id = %s
        """, (consult_log_id,))

        # 품질 낮은 답변 자동 비활성화
        cur.execute("""
            UPDATE golden_answers
            SET is_active = FALSE
            WHERE source_consult_id = %s
              AND (helpful_count::FLOAT / GREATEST(helpful_count + inaccurate_count, 1)) < 0.4
        """, (consult_log_id,))

        db_conn.commit()
    except Exception as e:
        logger.warning(f"[GoldenAnswer] mark_inaccurate error: {e}")


def save_knowledge(
    source: str,
    knowledge_type: str,
    content: dict,
    db_conn,
    category: str = None,
    announcement_id: int = None,
    confidence: float = 0.5,
):
    """공유 지식 저장소에 학습 결과 저장"""
    try:
        cur = db_conn.cursor()
        cur.execute("""
            INSERT INTO knowledge_base (source, knowledge_type, category, announcement_id, content, confidence)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (source, knowledge_type, category, announcement_id,
              json.dumps(content, ensure_ascii=False), confidence))
        db_conn.commit()
    except Exception as e:
        logger.warning(f"[Knowledge] save error: {e}")
        try:
            db_conn.rollback()
        except Exception:
            pass


def get_relevant_knowledge(
    category: str,
    db_conn,
    knowledge_types: list = None,
    limit: int = 5,
) -> List[Dict]:
    """
    상담 시 관련 지식을 조회하여 프롬프트에 주입.
    높은 신뢰도 + 많이 활용된 지식을 우선 반환.
    """
    if not category:
        return []

    try:
        cur = db_conn.cursor()
        type_filter = ""
        params = [category]

        if knowledge_types:
            placeholders = ",".join(["%s"] * len(knowledge_types))
            type_filter = f"AND knowledge_type IN ({placeholders})"
            params.extend(knowledge_types)

        params.append(limit)
        cur.execute(f"""
            SELECT id, source, knowledge_type, content, confidence, use_count
            FROM knowledge_base
            WHERE category = %s AND confidence >= 0.4
            {type_filter}
            ORDER BY confidence DESC, use_count DESC
            LIMIT %s
        """, params)

        rows = cur.fetchall()
        results = []
        ids = []
        for row in rows:
            r = dict(row)
            content = r["content"]
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except Exception:
                    pass
            r["content"] = content
            results.append(r)
            ids.append(r["id"])

        # use_count 증가
        if ids:
            cur.execute(f"""
                UPDATE knowledge_base SET use_count = use_count + 1
                WHERE id IN ({",".join(["%s"] * len(ids))})
            """, ids)
            db_conn.commit()

        return results
    except Exception as e:
        logger.warning(f"[Knowledge] query error: {e}")
        return []


def extract_knowledge_from_consult(
    announcement_id: int,
    category: str,
    messages: list,
    conclusion: str,
    feedback: str,
    db_conn,
):
    """
    상담 완료 후 대화에서 지식을 추출하여 knowledge_base에 저장.
    수집AI, 공통AI가 활용할 수 있는 패턴/인사이트를 생성.
    """
    if not messages or len(messages) < 3:
        return  # 너무 짧은 대화는 학습 가치 낮음

    # 사용자가 물어본 질문 패턴 추출
    user_questions = [m["text"] for m in messages if m.get("role") == "user"]

    if user_questions:
        # FAQ 패턴 저장
        save_knowledge(
            source="consult",
            knowledge_type="pattern",
            content={
                "top_questions": user_questions[:5],
                "conclusion": conclusion,
                "feedback": feedback,
                "question_count": len(user_questions),
            },
            db_conn=db_conn,
            category=category,
            announcement_id=announcement_id,
            confidence=0.7 if feedback == "helpful" else 0.3,
        )

    # 부정확 피드백이면 오류 패턴 저장
    if feedback == "inaccurate":
        # 마지막 AI 답변이 문제가 된 것으로 추정
        ai_answers = [m["text"] for m in messages if m.get("role") == "assistant"]
        if ai_answers:
            save_knowledge(
                source="consult",
                knowledge_type="error",
                content={
                    "wrong_answer_snippet": ai_answers[-1][:500],
                    "user_question": user_questions[-1] if user_questions else "",
                    "feedback": "inaccurate",
                },
                db_conn=db_conn,
                category=category,
                announcement_id=announcement_id,
                confidence=0.8,  # 사용자가 직접 지적한 오류는 신뢰도 높음
            )


def _format_knowledge_for_prompt(knowledge_items: List[Dict]) -> str:
    """조회된 지식을 프롬프트에 삽입할 텍스트로 변환"""
    if not knowledge_items:
        return ""

    parts = ["\n[축적된 학습 지식 — 이전 상담에서 학습한 내용]"]
    for item in knowledge_items:
        content = item["content"]
        ktype = item["knowledge_type"]
        conf = item["confidence"]

        if ktype == "pattern":
            questions = content.get("top_questions", [])
            if questions:
                parts.append(f"• 이 카테고리에서 자주 묻는 질문: {', '.join(questions[:3])} (신뢰도: {conf:.0%})")

        elif ktype == "error":
            wrong = content.get("wrong_answer_snippet", "")[:200]
            parts.append(f"⚠️ 주의: 이전에 부정확 판정을 받은 답변 패턴이 있습니다. 유사 답변을 하지 않도록 주의하세요: \"{wrong}...\" (신뢰도: {conf:.0%})")

        elif ktype == "insight":
            parts.append(f"💡 인사이트: {content.get('relationship', '')} (신뢰도: {conf:.0%})")

        elif ktype == "faq":
            parts.append(f"• FAQ: Q: {content.get('question', '')} → A: {content.get('answer', '')[:200]} (신뢰도: {conf:.0%})")

    return "\n".join(parts) if len(parts) > 1 else ""


def _build_knowledge_context_from_announcements(matched: List[Dict], db_conn) -> str:
    """매칭된 공고들의 카테고리에서 관련 지식을 수집"""
    if not db_conn or not matched:
        return ""
    categories = list({a.get("category", "") for a in matched if a.get("category")})
    all_items = []
    for cat in categories[:3]:  # 최대 3개 카테고리
        try:
            items = get_relevant_knowledge(cat, db_conn, limit=3)
            all_items.extend(items)
        except Exception:
            pass
    return _format_knowledge_for_prompt(all_items[:5])


def _build_knowledge_context(category: str, db_conn) -> str:
    """카테고리 관련 축적 지식을 프롬프트용 텍스트로 변환"""
    if not db_conn or not category:
        return ""
    try:
        items = get_relevant_knowledge(
            category, db_conn,
            knowledge_types=["pattern", "error", "insight", "faq"],
            limit=5,
        )
        return _format_knowledge_for_prompt(items)
    except Exception:
        return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 프롬프트 유틸리티
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRO 전문가 전용 상담 채팅
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def chat_pro_consultant(messages: List[Dict], announcement_id: int = None, db_conn=None) -> Dict[str, Any]:
    """
    PRO 전문가 전용 상담 채팅.
    컨설턴트가 고객사 정보를 전달 → AI가 정보 수집 → 매칭 프로필 생성.
    일반 상담(chat_consultant)과 완전 분리된 프롬프트 사용.

    announcement_id 전달 시 → 특정 공고 상담 모드 (공고 데이터 자동 주입)
    """
    if not HAS_GENAI:
        return {"reply": "AI 서비스를 사용할 수 없습니다.", "choices": [], "done": False, "profile": None}

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"reply": "AI 서비스가 설정되지 않았습니다.", "choices": [], "done": False, "profile": None}

    # ── 특정 공고 상담 모드: announcement_id가 있으면 chat_consult로 위임 ──
    # 공고 데이터를 주입한 깊이 있는 답변을 위해 일반 공고 상담 엔진 활용
    if announcement_id and db_conn:
        try:
            cur = db_conn.cursor()
            cur.execute("""
                SELECT a.*, aa.parsed_sections, aa.deep_analysis, aa.full_text
                FROM announcements a
                LEFT JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
                WHERE a.announcement_id = %s
            """, (announcement_id,))
            row = cur.fetchone()
            if row:
                ann = dict(row)
                deep = {
                    "parsed_sections": ann.get("parsed_sections") or {},
                    "deep_analysis": ann.get("deep_analysis") or {},
                }
                # PRO 컨설턴트 컨텍스트 추가 (첫 사용자 메시지에 prepend)
                pro_messages = []
                pro_prefix = "[전문가 상담 — 컨설턴트가 고객을 대신해 질문 중] 답변을 컨설턴트에게 전문적으로 제공하세요. "
                for i, m in enumerate(messages):
                    if i == 0 and m.get("role") == "user":
                        pro_messages.append({"role": "user", "text": pro_prefix + m.get("text", "")})
                    else:
                        pro_messages.append(m)

                result = chat_consult(
                    announcement_id=announcement_id,
                    messages=pro_messages,
                    announcement=ann,
                    deep_analysis_data=deep,
                    user_profile=None,
                    db_conn=db_conn,
                )
                return {
                    "reply": result.get("reply", ""),
                    "choices": result.get("choices", []),
                    "done": False,  # PRO 모드에서는 종료 로직 다름
                    "profile": None,
                    "collected": {},
                }
        except Exception as e:
            logger.error(f"[chat_pro_consultant] specific ann mode error: {e}")
            # fall through to general mode

    # ── 금융 상담 모드 감지: 사용자가 "자금 상담", "보증 상담" 선택 시 knowledge_base 주입 ──
    financial_knowledge_block = ""
    _in_financial_mode = False
    if messages and db_conn:
        for m in messages:
            if m.get("role") == "user":
                t = m.get("text", "")
                if any(kw in t for kw in ["자금 상담", "융자 상담", "자금/융자 상담", "보증 상담", "정책자금 상담"]):
                    _in_financial_mode = True
                    break
        if _in_financial_mode:
            try:
                kb_cur = db_conn.cursor()
                kb_cur.execute("""
                    SELECT id, knowledge_type, content, confidence
                    FROM knowledge_base
                    WHERE (category IN ('금융', '보증') OR knowledge_type = 'faq')
                      AND confidence >= 0.5
                    ORDER BY confidence DESC, use_count DESC
                    LIMIT 8
                """)
                kb_rows = kb_cur.fetchall()
                if kb_rows:
                    parts = ["\n[금융 전문 지식 — 자금/보증 상담 모드 활성화. 아래 데이터를 활용하여 정확하게 답변하세요]"]
                    for r in kb_rows:
                        content = r["content"] if isinstance(r["content"], dict) else __import__("json").loads(r["content"])
                        ktype = r["knowledge_type"]
                        if ktype == "faq":
                            parts.append(f"• Q: {content.get('question','')} → A: {content.get('answer','')[:300]}")
                        elif ktype == "insight":
                            parts.append(f"• 실무팁: {content.get('relationship','')[:200]}")
                        elif ktype == "error":
                            parts.append(f"• 주의: {content.get('wrong_info','')[:100]} → 올바른 정보: {content.get('correct_info','')[:200]}")
                    financial_knowledge_block = "\n".join(parts)
                    for r in kb_rows:
                        try:
                            kb_cur.execute("UPDATE knowledge_base SET use_count = use_count + 1 WHERE id = %s", (r.get("id"),))
                        except Exception:
                            pass
                    db_conn.commit()
            except Exception as fk_err:
                print(f"[PRO-FinKnowledge] Error: {fk_err}")

    system_prompt = f"""당신은 지원사업 컨설턴트의 AI 어시스턴트입니다.
컨설턴트가 고객사(또는 개인 고객) 정보를 당신에게 전달하면, 정보를 수집하여 지원사업 매칭 프로필을 생성합니다.
{financial_knowledge_block}

[핵심 역할]
- 당신의 사용자는 **컨설턴트(전문가)**입니다. 고객 본인이 아닙니다.
- 컨설턴트에게 존댓말로 질문하세요.
- 고객사 서류(사업계획서, 재무제표 등)가 첨부되면 거기서 정보를 추출하세요.

[대화 규칙]
1. 정보가 부족하면 반드시 **구체적 질문**을 하세요. "정보가 필요합니다"로만 끝내지 마세요.
2. 한 번에 1~2개 질문만 하세요. 너무 많으면 부담됩니다.
3. **choices에 항상 2~3개의 추천 응답**을 포함하세요. 컨설턴트가 빠르게 선택할 수 있도록.
4. 이미 제공된 정보는 즉시 collected에 반영하고, 절대 다시 묻지 마세요.
5. 첨부 파일 분석 결과가 대화에 포함되면, 거기서 추출 가능한 정보를 모두 collected에 반영하세요.

[고객 유형 판별]
- "사업자", "기업", "법인", "창업" → **사업자 모드** → 즉시 "고객사의 기업명을 알려주세요."
- "개인", "청년", "구직자" → **개인 모드** → 즉시 "고객의 성함과 거주 지역을 알려주세요."
- 불분명하면: "고객이 사업자(기업)인가요, 개인인가요?" + choices: ["사업자(기업)입니다", "개인 고객입니다"]

[사업자 모드 — 수집할 정보]
1. company_name: 기업명 (상호명)
2. establishment_date: 설립일 (YYYY-MM-DD 형식)
3. industry_code: 업종코드 (KSIC 5자리) — 업종명→자동 변환
4. revenue_bracket: 매출규모 ("1억 미만", "1억~5억", "5억~10억", "10억~50억", "50억 이상")
5. employee_count_bracket: 직원수 ("5인 미만", "5인~10인", "10인~30인", "30인~50인", "50인 이상")
6. address_city: 소재지 (시/도)
7. interests: 관심분야 (창업지원, 기술개발, 수출마케팅, 고용지원, 시설개선, 정책자금, 디지털전환, 판로개척, 교육훈련, 에너지환경, 소상공인, R&D)

[개인 모드 — 수집할 정보]
1. company_name: 이름 또는 "개인"
2. establishment_date: 생년월일 (YYYY-MM-DD) — 나이를 말하면 대략적 날짜로 변환
3. industry_code: 빈 문자열 ""
4. revenue_bracket: "1억 미만" (고정)
5. employee_count_bracket: "5인 미만" (고정)
6. address_city: 거주지 (시/도)
7. interests: 관심분야 (취업, 주거, 교육, 청년, 출산, 육아, 다자녀, 장학금, 의료, 장애, 저소득, 노인, 문화)

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
- 농업/스마트팜: 01000
- 헬스/스포츠: 93000

[자동 추론 규칙]
- 업종명 → KSIC 코드 자동 변환 (물어보지 말 것)
- "매출 5억" → revenue_bracket: "5억~10억"
- "직원 15명" → employee_count_bracket: "10인~30인"
- 개인 모드에서 industry_code, revenue_bracket, employee_count_bracket은 자동 설정 (물어보지 말 것)
- 모든 필드를 추정/변환 가능하면 즉시 done=true와 profile을 반환하세요.

[★ 매칭 트리거 — 매우 중요]
- 컨설턴트가 **명시적으로** "매칭해줘", "추천해줘", "찾아줘", "보여줘", "매칭 시작" 등 **매칭 실행을 직접 요청**하면:
  → 수집된 정보가 일부만 있어도 즉시 done=true 반환
  → 누락된 필드는 합리적 기본값으로 채우기
    - industry_code: 빈 문자열로 설정 (전체 검색)
    - revenue_bracket: "1억 미만" (가장 보수적)
    - employee_count_bracket: "5인 미만" (가장 보수적)
    - establishment_date: "2024-01-01" (최근 창업으로 가정)
    - address_city: "서울" (가장 보편)
    - interests: 컨설턴트 언급 키워드 또는 "창업지원,기술개발,정책자금"
- **이 규칙은 위의 모든 추가 질문 규칙보다 우선합니다.** 컨설턴트가 매칭을 요청하면 더 묻지 마세요.

[★★ 금융 관련 키워드 감지 시 → 선택지 제공]
- 대화 중 정책자금, 융자, 대출, 보증, 자금, 금리, 담보 등 금융 관련 키워드가 나오면:
  → **매칭으로 넘기지 말고**, 아래 선택지를 choices에 포함하세요:
    ["자금/융자 상담", "보증 상담", "매칭 진행"]
  → message에는 "자금/보증 관련 상담을 원하시면 선택해주세요." 안내
  → done=false 유지
- 컨설턴트가 "자금 상담", "자금/융자 상담", "보증 상담", "정책자금 상담"을 선택하면:
  → 위 [금융 전문 지식] 데이터가 자동 주입됩니다
  → 해당 주제에 대해 전문적으로 답변하세요 (금리/한도/담보/신청요건 등)
  → 상담이 끝나면 "매칭을 진행할까요?" 선택지를 다시 제시하세요

[응답 형식 — 반드시 이 JSON 형식으로만 응답]
{{
  "message": "AI의 대화 메시지 (마크다운 사용 가능)",
  "choices": ["추천 응답1", "추천 응답2"],
  "done": false,
  "collected": {{"지금까지 수집된 필드명": "값", ...}},
  "profile": null
}}

done=true일 때 (모든 정보 수집 완료):
{{
  "message": "고객사 프로필이 완성되었습니다. 매칭을 시작하겠습니다.",
  "choices": [],
  "done": true,
  "collected": {{...모든 필드...}},
  "profile": {{
    "company_name": "...",
    "establishment_date": "YYYY-MM-DD",
    "industry_code": "XXXXX",
    "revenue_bracket": "...",
    "employee_count_bracket": "...",
    "address_city": "...",
    "interests": "관심1,관심2"
  }}
}}

반드시 순수 JSON만 반환하세요."""

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        "models/gemini-2.0-flash",
        generation_config={"max_output_tokens": 4096}
    )

    gemini_messages = []
    for msg in messages:
        role = "user" if msg.get("role") == "user" else "model"
        gemini_messages.append({"role": role, "parts": [msg.get("text", "")]})

    try:
        chat = model.start_chat(history=[
            {"role": "user", "parts": [system_prompt]},
            {"role": "model", "parts": ['{"message": "고객 유형을 선택해 주시면 상담을 시작하겠습니다.", "choices": ["사업자(기업)입니다", "개인 고객입니다"], "done": false, "collected": {}, "profile": null}']},
            *gemini_messages[:-1]
        ])
        response = chat.send_message(gemini_messages[-1]["parts"][0] if gemini_messages else "시작")

        result = _parse_gemini_json(response.text)

        collected = result.get("collected", {})
        done = result.get("done", False)
        profile = result.get("profile")

        REQUIRED = ["company_name", "establishment_date", "industry_code", "revenue_bracket", "employee_count_bracket", "address_city", "interests"]
        if not done and collected and all(collected.get(k) for k in REQUIRED):
            done = True
            profile = {k: collected[k] for k in REQUIRED}

        # ★ 매칭 키워드 강제 트리거: 사용자가 매칭 요청 시 done=True
        last_user_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_text = msg.get("text", "")
                break
        match_keywords = ["매칭", "추천", "찾아줘", "보여줘", "맞춤", "지원사업 알려", "리스트", "부탁"]
        if not done and last_user_text and any(kw in last_user_text for kw in match_keywords):
            DEFAULTS = {
                "company_name": "고객사",
                "establishment_date": "2024-01-01",
                "industry_code": "",
                "revenue_bracket": "1억 미만",
                "employee_count_bracket": "5인 미만",
                "address_city": "서울",
                "interests": "창업지원,기술개발,정책자금",
            }
            profile = {k: (collected.get(k) or DEFAULTS[k]) for k in REQUIRED}
            done = True
            logger.info(f"[chat_pro_consultant] Match keyword trigger → done=True with profile")

        return {
            "reply": result.get("message", "") if not done else "수집된 정보를 바탕으로 매칭을 실행합니다.",
            "choices": result.get("choices", []) if not done else [],
            "done": done,
            "profile": profile,
            "collected": collected,
        }
    except json.JSONDecodeError:
        return {"reply": response.text.strip() if 'response' in dir() else "응답 처리 오류", "choices": [], "done": False, "profile": None, "collected": {}}
    except Exception as e:
        logger.error(f"[PRO] chat_pro_consultant error: {e}")
        return {"reply": "AI 응답 생성 중 오류가 발생했습니다. 다시 시도해 주세요.", "choices": [], "done": False, "profile": None, "collected": {}}
