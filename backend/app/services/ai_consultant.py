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

from .prompts import (
    PROMPT_PRO_BUSINESS,
    PROMPT_PRO_INDIVIDUAL,
    PROMPT_PRO_CONSULT_BIZ_TOOL,
    PROMPT_PRO_CONSULT_INDIV_TOOL,
    PROMPT_LITE_FUND_BIZ_TOOL,
    PROMPT_LITE_FUND_INDIV_TOOL,
)

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 공통 유틸리티 — choices 파싱, 도구 코드 제거
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_TOOL_FUNC_NAMES = [
    "search_fund_announcements", "get_announcement_detail",
    "search_knowledge_base", "check_eligibility",
    "search_pro_sections",
]


def _parse_choices_marker(text: str) -> tuple:
    """'---choices---' 마커에서 choices를 추출하고 본문에서 제거.
    Returns: (cleaned_text, choices_list)
    """
    if "---choices---" not in text:
        return text, []
    parts = text.split("---choices---", 1)
    cleaned = parts[0].rstrip()
    raw = parts[1].strip().split("\n", 1)[0]
    choices = [c.strip() for c in raw.split("|") if c.strip()][:5]
    return cleaned, choices


def _remove_tool_code_leaks(text: str) -> str:
    """AI 응답에서 도구 함수 호출 코드 노출을 제거."""
    for fn in _TOOL_FUNC_NAMES:
        text = re.sub(rf"`?{fn}\([^)]*\)`?", "", text)
    text = re.sub(r"```[a-z]*\s*```", "", text)
    return text.strip()


def classify_question_intent(query: str) -> List[str]:
    """질문에서 관심 section_type을 추출 (간단한 키워드 기반 — LLM 호출 없이 50ms).
    여러 의도를 동시에 반환할 수 있음. 빈 리스트면 전 섹션 검색.
    """
    q = (query or "").lower()
    intents: List[str] = []
    rules = [
        (["자격", "신청 자격", "대상", "할 수 있", "되나요", "해당되"], ["eligibility", "target"]),
        (["서류", "제출", "준비", "필요한 거", "필요한것"], ["required_documents"]),
        (["신청 방법", "어떻게 신청", "절차", "신청해", "어디서", "어디에"], ["application_method"]),
        (["얼마", "지원금", "지원 금액", "한도", "보조금", "최대"], ["support_amount", "support_content"]),
        (["내용", "혜택", "지원하는 게", "뭐 받"], ["support_content"]),
        (["언제", "마감", "기간", "일정", "신청기간"], ["schedule"]),
        (["문의", "전화", "연락", "담당자"], ["contact"]),
        (["주의", "유의", "벌칙", "감점"], ["notes"]),
        (["전략", "팁", "포인트", "꿀팁", "어떻게 하면"], ["insight_key_points", "insight_strategy"]),
    ]
    for kws, types in rules:
        if any(kw in q for kw in kws):
            for t in types:
                if t not in intents:
                    intents.append(t)
    return intents


def search_sections_for_rag(
    query: str,
    db_conn,
    top_k: int = 6,
    user_profile: Optional[Dict] = None,
    section_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """섹션 단위 RAG — 질문 의도(section_type) + 사용자 프로필(메타 사전필터) + 임베딩 유사도.

    Returns: {"sections": [...], "text_block": "..."}
    """
    result: Dict[str, Any] = {"sections": [], "text_block": ""}
    if not query or len(query.strip()) < 2 or not db_conn or not HAS_GENAI:
        return result
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return result

    # 1) 질문 의도 → section_type 필터
    if not section_types:
        section_types = classify_question_intent(query)

    # 2) 임베딩 생성
    try:
        genai.configure(api_key=api_key)
        res = genai.embed_content(
            model="models/gemini-embedding-001",
            content=query,
            task_type="retrieval_query",
            output_dimensionality=768,
        )
        vec = res.get("embedding") if isinstance(res, dict) else res["embedding"]
        if not vec:
            return result
        vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    except Exception as e:
        logger.warning(f"[Sec-RAG embed] {e}")
        return result

    # 3) 메타 사전 필터 — user_profile에서 region/industry/마감 적용
    where_parts = ["s.embedding IS NOT NULL"]
    params: list = [vec_str]
    if section_types:
        placeholders = ",".join(["%s"] * len(section_types))
        where_parts.append(f"s.section_type IN ({placeholders})")
        params.extend(section_types)
    # 마감 안 된 공고만
    where_parts.append("(a.deadline_date IS NULL OR a.deadline_date >= CURRENT_DATE)")
    # region 필터 (공고 region이 사용자 지역과 일치하거나 전국)
    if user_profile and user_profile.get("address_city"):
        city = user_profile["address_city"][:20]
        where_parts.append("(a.region IS NULL OR a.region ILIKE %s OR a.region ILIKE '%%전국%%')")
        params.append(f"%{city}%")
    where_sql = " AND ".join(where_parts)
    params.append(top_k)

    # M: section_feedback 평균 평점을 가중치로 사용 (3.0이 중립, >3.0 boost, <3.0 demote)
    sql = f"""
        SELECT s.id, s.announcement_id, s.section_type, s.section_title, s.section_text,
               a.title AS ann_title, a.department, a.support_amount, a.deadline_date,
               (1 - (s.embedding <=> %s::vector)) *
               COALESCE((SELECT 1.0 + ((AVG(rating) - 3.0) / 10.0) FROM section_feedback sf WHERE sf.section_id = s.id), 1.0)
               AS similarity
        FROM announcement_sections s
        LEFT JOIN announcements a ON s.announcement_id = a.announcement_id
        WHERE {where_sql}
        ORDER BY similarity DESC
        LIMIT %s
    """
    try:
        cur = db_conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
    except Exception as e:
        logger.warning(f"[Sec-RAG query] {e}")
        try: db_conn.rollback()
        except: pass
        return result

    parts = []
    parts.append("\n\n[★★ 섹션 단위 RAG — 사용자 질문에 정확히 매칭되는 공고 섹션]")
    if section_types:
        parts.append(f"(필터: {', '.join(section_types)})")
    accepted = 0
    for r in rows:
        d = dict(r)
        sim = float(d.get("similarity") or 0)
        if sim < 0.5:
            continue
        accepted += 1
        result["sections"].append({
            "id": d.get("id"),
            "announcement_id": d.get("announcement_id"),
            "ann_title": d.get("ann_title"),
            "department": d.get("department"),
            "section_type": d.get("section_type"),
            "section_title": d.get("section_title"),
            "section_text": d.get("section_text"),
            "support_amount": d.get("support_amount"),
            "deadline_date": str(d.get("deadline_date") or ""),
            "similarity": round(sim, 3),
        })
        line = f"\n#{accepted} [{int(sim*100)}%] 『{d.get('ann_title','')[:80]}』"
        if d.get("department"):
            line += f" — {d['department'][:40]}"
        parts.append(line)
        parts.append(f"  [{d.get('section_title','')}] {(d.get('section_text','') or '')[:600]}")
        if d.get("support_amount"):
            parts.append(f"  💰 {d['support_amount']}")
        if d.get("deadline_date") and str(d.get("deadline_date")) != "None":
            parts.append(f"  📅 마감: {str(d['deadline_date'])[:10]}")
    if accepted == 0:
        result["text_block"] = ""
        return result
    parts.append("\n[지시] 위 섹션의 본문 문장을 그대로 인용하여 답변. 공고명과 부처를 반드시 명시.")
    result["text_block"] = "\n".join(parts)
    return result


def extract_and_store_insights(messages: List[Dict], db_conn, source: str = "pro_consult") -> int:
    """상담 종료 시 AI에게 재요청 — FAQ/인사이트 추출 후 knowledge_base에 저장.

    반환: 저장된 항목 수
    """
    if not HAS_GENAI or not db_conn or not messages or len(messages) < 4:
        return 0
    api_key = _get_batch_api_key()
    if not api_key:
        return 0

    # 대화를 자연어로 펼치기
    convo = "\n".join(
        f"{'컨설턴트' if m.get('role')=='user' else 'AI'}: {m.get('text','')[:500]}"
        for m in messages if m.get("text")
    )[:8000]

    prompt = f"""다음은 정부 지원사업 컨설턴트와 AI의 상담 기록입니다.
이 대화에서 **향후 다른 상담에서도 재사용 가능한 일반화된 지식**을 추출하세요.

[상담 기록]
{convo}

[추출 규칙]
1. 최대 3개까지. 대화에 국한된 사적 정보는 제외.
2. 아래 3가지 타입 중 해당되는 것만 생성:
   - faq: 다른 사용자가 동일하게 물어볼 법한 질문과 일반화된 답변
   - insight: 지원사업 신청 전략/팁/주의사항 (공고 이름이나 부처 명시)
   - error: 흔한 오해나 잘못된 정보 → 올바른 사실

[응답 형식 — 순수 JSON]
{{
  "items": [
    {{"type": "faq", "category": "정책자금", "question": "...", "answer": "...", "confidence": 0.8}},
    {{"type": "insight", "category": "스마트공장", "relationship": "...", "confidence": 0.75}},
    {{"type": "error", "category": "창업지원", "wrong_info": "...", "correct_info": "...", "confidence": 0.7}}
  ]
}}

추출할 가치가 없으면 items: [] 반환. 마크다운 코드블록 금지."""

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            BATCH_MODEL,
            generation_config={"max_output_tokens": 2048, "response_mime_type": "application/json", "temperature": 0.3}
        )
        resp = model.generate_content(prompt)
        data = json.loads(resp.text)
        items = data.get("items") or []
    except Exception as e:
        logger.warning(f"[insights extract] {e}")
        return 0

    if not items:
        return 0

    # 저품질 필터 — 회피성 답변은 저장하지 않음
    _LOW_QUALITY_PATTERNS = [
        "홈페이지에서 확인", "홈페이지 확인", "직접 문의", "문의하시는 것",
        "확인이 필요합니다", "확인해야 합니다", "알려주시면 안내",
        "정보가 필요합니다", "구체적으로 알려주", "다시 시도",
        "어떤 정책자금에 관심", "종류에 따라 조건",
    ]

    stored = 0
    for it in items[:3]:
        ktype = it.get("type", "insight")
        cat = (it.get("category") or "")[:60]
        conf = min(1.0, max(0.0, float(it.get("confidence") or 0.5)))
        content = {k: v for k, v in it.items() if k not in ("type", "category", "confidence")}

        # 저품질 필터: 답변이 회피성이면 저장 스킵
        answer_text = str(content.get("answer", content.get("relationship", "")))
        if any(p in answer_text for p in _LOW_QUALITY_PATTERNS):
            logger.info(f"[insights] Skipped low-quality: {answer_text[:60]}")
            continue

        try:
            save_knowledge(
                source=source,
                knowledge_type=ktype,
                content=content,
                db_conn=db_conn,
                category=cat,
                confidence=conf,
                source_agent=source.split("_")[0] if "_" in source else source,
            )
            stored += 1
        except Exception as ie:
            logger.warning(f"[kb insert] {ie}")
    return stored


def search_knowledge_for_rag(query: str, db_conn, top_k_ann: int = 5, top_k_kb: int = 3) -> Dict[str, Any]:
    """RAG — 사용자 질문 의미에 맞는 공고 + 지식을 pgvector로 검색.

    Returns: {
        "announcements": [{code, title, summary, amount, deadline, similarity, ...}],
        "knowledge": [{type, content, similarity}],
        "text_block": "프롬프트 주입용 자연어 블록"
    }
    """
    result: Dict[str, Any] = {"announcements": [], "knowledge": [], "text_block": ""}
    if not query or len(query.strip()) < 2 or not db_conn:
        return result

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not HAS_GENAI:
        return result

    try:
        genai.configure(api_key=api_key)
        res = genai.embed_content(
            model="models/gemini-embedding-001",
            content=query,
            task_type="retrieval_query",
            output_dimensionality=768,
        )
        vec = res.get("embedding") if isinstance(res, dict) else res["embedding"]
        if not vec:
            return result
        vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    except Exception as e:
        logger.warning(f"[RAG embed] {e}")
        return result

    # 1) announcement_embeddings에서 Top K 공고 검색 (유사도 >= 0.65만 채택)
    try:
        cur = db_conn.cursor()
        cur.execute("""
            SELECT a.announcement_id, a.title, a.department, a.category,
                   a.support_amount, a.region, a.summary_text,
                   a.deadline_date, a.target_type,
                   1 - (e.embedding <=> %s::vector) AS similarity
            FROM announcement_embeddings e
            JOIN announcements a ON e.announcement_id = a.announcement_id
            WHERE (a.deadline_date IS NULL OR a.deadline_date >= CURRENT_DATE)
            ORDER BY e.embedding <=> %s::vector
            LIMIT %s
        """, (vec_str, vec_str, top_k_ann))
        rows = cur.fetchall()
        for r in rows:
            d = dict(r)
            sim = float(d.get("similarity") or 0)
            if sim < 0.55:  # 품질 하한선 — 너무 관련 없으면 제외
                continue
            result["announcements"].append({
                "id": d.get("announcement_id"),
                "title": (d.get("title") or "")[:150],
                "dept": (d.get("department") or "")[:60],
                "category": d.get("category"),
                "amount": (d.get("support_amount") or "")[:60],
                "region": (d.get("region") or "")[:30],
                "summary": (d.get("summary_text") or "")[:400],
                "deadline": str(d.get("deadline_date") or "")[:10],
                "target_type": d.get("target_type"),
                "similarity": round(sim, 3),
            })
    except Exception as e:
        logger.warning(f"[RAG ann search] {e}")
        try: db_conn.rollback()
        except: pass

    # 2) knowledge_base에서 관련 지식 검색 (임베딩 없는 경우 텍스트 매칭 폴백)
    try:
        cur = db_conn.cursor()
        # knowledge_base에 embedding 컬럼이 있으면 사용, 없으면 키워드 매칭
        try:
            # N: PRO 출처(source='pro_consult')는 가중치 boost (similarity * 1.15)
            cur.execute("""
                SELECT id, knowledge_type, category, content, confidence, source,
                       (1 - (embedding <=> %s::vector)) *
                       CASE WHEN source = 'pro_consult' THEN 1.15 ELSE 1.0 END AS similarity
                FROM knowledge_base
                WHERE embedding IS NOT NULL AND confidence >= 0.4
                ORDER BY similarity DESC
                LIMIT %s
            """, (vec_str, top_k_kb))
            rows = cur.fetchall()
        except Exception:
            # embedding 컬럼 없으면 키워드 기반 LIKE
            try: db_conn.rollback()
            except: pass
            keywords = [w for w in re.split(r'\s+', query) if len(w) >= 2][:3]
            if keywords:
                like_patterns = [f"%{k}%" for k in keywords]
                cur.execute("""
                    SELECT id, knowledge_type, category, content, confidence
                    FROM knowledge_base
                    WHERE confidence >= 0.4
                      AND (content::text ILIKE ANY(%s))
                    ORDER BY confidence DESC, use_count DESC
                    LIMIT %s
                """, (like_patterns, top_k_kb))
                rows = cur.fetchall()
            else:
                rows = []
        for r in rows:
            d = dict(r)
            content = d.get("content")
            if isinstance(content, str):
                try: content = json.loads(content)
                except: content = {"raw": content}
            result["knowledge"].append({
                "id": d.get("id"),
                "type": d.get("knowledge_type"),
                "category": d.get("category"),
                "content": content,
                "confidence": float(d.get("confidence") or 0),
                "similarity": round(float(d.get("similarity") or 0), 3) if d.get("similarity") else None,
            })
            # use_count 증가
            try:
                cur.execute("UPDATE knowledge_base SET use_count = use_count + 1 WHERE id = %s", (d.get("id"),))
            except Exception:
                pass
        try: db_conn.commit()
        except: pass
    except Exception as e:
        logger.warning(f"[RAG kb search] {e}")
        try: db_conn.rollback()
        except: pass

    # 3) 프롬프트 주입용 텍스트 블록 생성
    parts = []
    if result["announcements"]:
        parts.append("\n\n[★ RAG 참고 — 사용자 질문과 관련된 공고 (실시간 DB 검색)]")
        for i, a in enumerate(result["announcements"][:5], 1):
            line = f"{i}. [{int(a['similarity']*100)}%] {a['title']}"
            if a.get("dept"): line += f" · {a['dept']}"
            if a.get("amount"): line += f" · 💰 {a['amount']}"
            if a.get("deadline") and a['deadline'] != "None": line += f" · 📅 {a['deadline']}"
            parts.append(line)
            if a.get("summary"):
                parts.append(f"   요약: {a['summary'][:200]}")
    if result["knowledge"]:
        parts.append("\n[★ RAG 참고 — 관련 지식/FAQ]")
        for i, k in enumerate(result["knowledge"][:3], 1):
            c = k.get("content") or {}
            if isinstance(c, dict):
                if k.get("type") == "faq":
                    q = c.get("question", "")[:120]
                    ans = c.get("answer", "")[:300]
                    parts.append(f"{i}. Q: {q}")
                    parts.append(f"   A: {ans}")
                elif k.get("type") == "insight":
                    parts.append(f"{i}. 인사이트: {str(c.get('relationship', c))[:300]}")
                else:
                    parts.append(f"{i}. {k.get('type')}: {str(c)[:300]}")
    if parts:
        parts.append("\n[지시] 위 참고 자료를 근거로 답변에 활용. 실제 공고명/부처/금액/마감일을 인용할 것.")
    result["text_block"] = "\n".join(parts)
    return result


def _clean_summary_text(text: str) -> str:
    """공고 원문에서 HTML 태그 제거·공백 정리. 프롬프트에 깔끔히 주입하기 위함."""
    if not text:
        return ""
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', ' ', text)
    # HTML 엔티티 치환
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#\d+;', ' ', text)
    # 연속 공백 압축
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


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
# 주의: "자격/대상/조건"은 단순 템플릿 응답이 아닌 "사용자 프로필과의 대조 분석"이 필요하므로
# 여기서 제외. Gemini로 넘겨서 분석 수행하도록 함.
_SIMPLE_QUERY_PATTERNS = {
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

    # 금리/이자/상환/담보/보증 등 금융 질문 — DB에 모호한 답변만 있을 가능성 → Gemini로 검색
    financial_query_keywords = ["금리", "이자", "이자율", "상환", "거치", "담보", "보증", "신용등급", "우대"]
    if any(fk in query_lower for fk in financial_query_keywords):
        return None  # Gemini로 넘김 (검색 활성화)

    # 패턴은 매칭되었지만 DB에 데이터가 없는 경우
    # → 조기 반환 금지. Gemini로 넘겨서 제목/요약/사용자 프로필/검색으로 분석하도록.
    # (기존에는 "정보 없음"으로 조기 포기 → 사용자 프로필과의 대조 분석이 아예 안 됨)
    if not matched_fields and matched_but_empty:
        return None  # Gemini로 넘김 — 분석 시도

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


# PRO Mode B / LITE Tool Calling 프롬프트는 prompts/ 패키지에서 import됨


def _tool_search_pro_sections(db_conn, query: str, target_type: str = "business", limit: int = 6) -> List[Dict]:
    """PRO 상담용 섹션 검색 — search_sections_for_rag 래퍼 (target_type 고정)."""
    if not db_conn or not query:
        return []
    try:
        sec = search_sections_for_rag(query, db_conn, top_k=limit)
        rows = sec.get("sections", []) or []
        # target_type 필터는 프롬프트가 강제하는 개념이라 여기선 전체 반환
        out = []
        for r in rows:
            out.append({
                "id": r.get("id"),
                "announcement_id": r.get("announcement_id"),
                "title": r.get("ann_title"),
                "department": r.get("department"),
                "section_type": r.get("section_type"),
                "section_title": r.get("section_title"),
                "section_text": (r.get("section_text") or "")[:800],
                "support_amount": r.get("support_amount"),
                "deadline": r.get("deadline_date"),
                "similarity": r.get("similarity"),
            })
        return out
    except Exception as e:
        logger.warning(f"[pro tool sec] {e}")
        return []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LITE — 자금 전문 상담 (Tool Calling 기반, 기업/개인 자동 라우팅)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# LITE 프롬프트는 prompts/ 패키지에서 import됨


def _tool_search_fund_announcements(db_conn, keywords: str, target_type: str = "business", limit: int = 5) -> List[Dict]:
    """자금/대출/보증 관련 공고 DB 검색 (임베딩 + 키워드)."""
    if not db_conn or not keywords:
        return []
    results = []
    try:
        # 1) 임베딩 검색 시도
        try:
            import google.generativeai as _genai
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                _genai.configure(api_key=api_key)
                res = _genai.embed_content(
                    model="models/gemini-embedding-001",
                    content=f"자금 대출 {keywords}",
                    task_type="retrieval_query",
                    output_dimensionality=768,
                )
                vec = res.get("embedding") if isinstance(res, dict) else res["embedding"]
                if vec:
                    vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
                    cur = db_conn.cursor()
                    # target_type 필터 + 자금·보증 관련 키워드 포함
                    fund_keywords = "정책자금|융자|대출|보증|자금|금리|한도|보조금"
                    tt_filter = "business" if target_type == "business" else "individual"
                    cur.execute("""
                        SELECT a.announcement_id, a.title, a.department,
                               a.support_amount, a.deadline_date, a.region,
                               a.summary_text, a.category,
                               1 - (e.embedding <=> %s::vector) AS similarity
                        FROM announcement_embeddings e
                        JOIN announcements a ON e.announcement_id = a.announcement_id
                        WHERE COALESCE(a.target_type, 'business') IN (%s, 'both')
                          AND (a.deadline_date IS NULL OR a.deadline_date >= CURRENT_DATE)
                          AND (
                              a.title ~* %s OR a.summary_text ~* %s
                              OR a.category ~* %s
                          )
                        ORDER BY e.embedding <=> %s::vector
                        LIMIT %s
                    """, (vec_str, tt_filter, fund_keywords, fund_keywords, fund_keywords, vec_str, limit))
                    for r in cur.fetchall():
                        d = dict(r)
                        results.append({
                            "id": d.get("announcement_id"),
                            "title": (d.get("title") or "")[:150],
                            "department": (d.get("department") or "")[:60],
                            "support_amount": (d.get("support_amount") or "")[:60],
                            "deadline": str(d.get("deadline_date") or "")[:10],
                            "region": (d.get("region") or "")[:30],
                            "summary": (d.get("summary_text") or "")[:300],
                            "category": d.get("category"),
                            "similarity": round(float(d.get("similarity") or 0), 3),
                        })
        except Exception as e:
            logger.warning(f"[tool fund emb] {e}")
            try: db_conn.rollback()
            except: pass

        # 2) 임베딩 없거나 결과 없으면 키워드 LIKE 폴백
        if not results:
            try:
                cur = db_conn.cursor()
                tt_filter = "business" if target_type == "business" else "individual"
                like_kw = f"%{keywords[:50]}%"
                cur.execute("""
                    SELECT announcement_id, title, department, support_amount,
                           deadline_date, region, summary_text, category
                    FROM announcements
                    WHERE COALESCE(target_type, 'business') IN (%s, 'both')
                      AND (deadline_date IS NULL OR deadline_date >= CURRENT_DATE)
                      AND (title ILIKE %s OR summary_text ILIKE %s)
                      AND (
                          title ~* '정책자금|융자|대출|보증|자금|금리|한도'
                          OR category ~* '금융|보증|자금'
                      )
                    ORDER BY deadline_date ASC NULLS LAST
                    LIMIT %s
                """, (tt_filter, like_kw, like_kw, limit))
                for r in cur.fetchall():
                    d = dict(r)
                    results.append({
                        "id": d.get("announcement_id"),
                        "title": (d.get("title") or "")[:150],
                        "department": (d.get("department") or "")[:60],
                        "support_amount": (d.get("support_amount") or "")[:60],
                        "deadline": str(d.get("deadline_date") or "")[:10],
                        "region": (d.get("region") or "")[:30],
                        "summary": (d.get("summary_text") or "")[:300],
                        "category": d.get("category"),
                    })
            except Exception as e:
                logger.warning(f"[tool fund like] {e}")
                try: db_conn.rollback()
                except: pass
    except Exception as e:
        logger.warning(f"[tool fund] {e}")
    return results


def _tool_get_announcement_detail(db_conn, announcement_id: int) -> Dict:
    """특정 공고의 상세 정보 (원문, 자격요건, 서류, 신청방법)."""
    if not db_conn or not announcement_id:
        return {"error": "invalid id"}
    try:
        cur = db_conn.cursor()
        cur.execute("""
            SELECT a.title, a.department, a.support_amount, a.deadline_date,
                   a.region, a.summary_text, a.category, a.origin_url,
                   aa.parsed_sections, aa.deep_analysis
            FROM announcements a
            LEFT JOIN announcement_analysis aa ON a.announcement_id = aa.announcement_id
            WHERE a.announcement_id = %s
        """, (announcement_id,))
        r = cur.fetchone()
        if not r:
            return {"error": "not found"}
        d = dict(r)
        ps = d.get("parsed_sections")
        da = d.get("deep_analysis")
        if isinstance(ps, str):
            try: ps = json.loads(ps)
            except: ps = {}
        if isinstance(da, str):
            try: da = json.loads(da)
            except: da = {}
        out = {
            "id": announcement_id,
            "title": d.get("title"),
            "department": d.get("department"),
            "support_amount": d.get("support_amount"),
            "deadline": str(d.get("deadline_date") or ""),
            "region": d.get("region"),
            "summary": (d.get("summary_text") or "")[:800],
            "origin_url": d.get("origin_url"),
        }
        if isinstance(ps, dict):
            for key in ("eligibility", "target", "required_documents", "application_method", "support_content", "schedule", "contact"):
                v = ps.get(key)
                if isinstance(v, str) and v:
                    out[key] = v[:600]
        if isinstance(da, dict):
            for key in ("key_points", "strategy", "summary"):
                v = da.get(key)
                if isinstance(v, str) and v:
                    out[key] = v[:400]
        return out
    except Exception as e:
        logger.warning(f"[tool detail] {e}")
        try: db_conn.rollback()
        except: pass
        return {"error": str(e)[:200]}


def _tool_search_knowledge_base(db_conn, query: str, limit: int = 5) -> List[Dict]:
    """knowledge_base에서 금융/보증 관련 FAQ/인사이트 검색."""
    if not db_conn or not query:
        return []
    results = []
    try:
        cur = db_conn.cursor()
        # category 우선, 키워드 LIKE 병행
        keywords = [w for w in re.split(r'\s+', query) if len(w) >= 2][:3]
        patterns = [f"%{k}%" for k in keywords] if keywords else [f"%{query}%"]
        cur.execute("""
            SELECT id, knowledge_type, category, content, confidence
            FROM knowledge_base
            WHERE (category IN ('금융', '보증') OR knowledge_type IN ('faq', 'insight'))
              AND confidence >= 0.4
              AND content::text ILIKE ANY(%s)
            ORDER BY confidence DESC, use_count DESC
            LIMIT %s
        """, (patterns, limit))
        for r in cur.fetchall():
            d = dict(r)
            c = d.get("content")
            if isinstance(c, str):
                try: c = json.loads(c)
                except: c = {"raw": c}
            results.append({
                "id": d.get("id"),
                "type": d.get("knowledge_type"),
                "category": d.get("category"),
                "content": c,
                "confidence": float(d.get("confidence") or 0),
            })
            try:
                cur.execute("UPDATE knowledge_base SET use_count = use_count + 1 WHERE id = %s", (d.get("id"),))
            except: pass
        db_conn.commit()
    except Exception as e:
        logger.warning(f"[tool kb] {e}")
        try: db_conn.rollback()
        except: pass
    return results


def _tool_check_eligibility(db_conn, announcement_id: int, profile: dict) -> Dict:
    """공고의 deep_analysis.eligibility_detail과 사용자 프로필 대조 → 자격 판정.

    Args:
        announcement_id: 판정 대상 공고 ID
        profile: 사용자 프로필 (age, business_years, revenue_won, employees, region, industry, certs)
    Returns:
        {eligible, score, passed: [...], failed: [...], uncertain: [...], exceptions: [...]}
    """
    if not db_conn or not announcement_id:
        return {"error": "invalid input"}
    try:
        cur = db_conn.cursor()
        cur.execute(
            "SELECT deep_analysis FROM announcement_analysis WHERE announcement_id = %s",
            (announcement_id,),
        )
        r = cur.fetchone()
        if not r:
            return {"error": "공고 분석 데이터 없음 — 자격 판정 불가", "eligible": None}
        da = r.get("deep_analysis") if hasattr(r, "get") else r[0]
        if isinstance(da, str):
            try: da = json.loads(da)
            except: da = {}
        if not isinstance(da, dict):
            return {"error": "분석 데이터 형식 오류", "eligible": None}

        ed = da.get("eligibility_detail") or {}
        exceptions_list = da.get("exception_rules") or []
        exclusions_list = da.get("exclusion_rules") or []

        p = profile or {}
        passed, failed, uncertain = [], [], []

        # 1) founding_years
        fy = ed.get("founding_years") or {}
        pmin, pmax = fy.get("min"), fy.get("max")
        byears = p.get("business_years")
        if (pmin is not None or pmax is not None):
            if byears is None:
                uncertain.append("업력 정보 미제공")
            else:
                ok = True
                if pmin is not None and byears < pmin: ok = False
                if pmax is not None and byears > pmax: ok = False
                (passed if ok else failed).append(
                    f"업력 {byears}년 (조건: {pmin or 0}~{pmax or '무제한'}년)"
                    + (f" · 예외: {fy.get('exceptions')}" if fy.get("exceptions") else "")
                )

        # 2) revenue_limit
        rl = ed.get("revenue_limit") or {}
        rmax = rl.get("max_won")
        rev = p.get("revenue_won")
        if rmax is not None:
            if rev is None:
                uncertain.append("매출 정보 미제공")
            else:
                ok = rev <= rmax
                (passed if ok else failed).append(
                    f"매출 {rev:,}원 (한도: {rmax:,}원)"
                    + (f" · 예외: {rl.get('exceptions')}" if rl.get("exceptions") else "")
                )

        # 3) employee_range
        er = ed.get("employee_range") or {}
        emin, emax = er.get("min"), er.get("max")
        emp = p.get("employees")
        if emin is not None or emax is not None:
            if emp is None:
                uncertain.append("직원 수 미제공")
            else:
                ok = True
                if emin is not None and emp < emin: ok = False
                if emax is not None and emp > emax: ok = False
                (passed if ok else failed).append(f"직원 {emp}명 (조건: {emin or 0}~{emax or '무제한'})")

        # 4) region
        reg_cond = ed.get("region")
        u_reg = p.get("region") or p.get("address_city")
        if reg_cond and reg_cond not in ("전국", "무관", None, ""):
            if not u_reg:
                uncertain.append("지역 정보 미제공")
            else:
                ok = (reg_cond in u_reg) or (u_reg in reg_cond)
                (passed if ok else failed).append(f"지역 {u_reg} (조건: {reg_cond})")

        # 5) industries
        inds = ed.get("industries") or []
        u_ind = p.get("industry") or p.get("industry_code")
        if inds and len(inds) > 0 and not (len(inds) == 1 and inds[0] in ("전업종", "무관")):
            if not u_ind:
                uncertain.append("업종 정보 미제공")
            else:
                ok = any((i in u_ind) or (u_ind in i) for i in inds if i)
                (passed if ok else failed).append(f"업종 {u_ind} (대상: {', '.join(inds[:3])})")

        # 6) required_certs
        certs = ed.get("required_certs") or []
        u_certs = p.get("certs") or []
        if certs:
            if not u_certs:
                uncertain.append(f"필요 인증 미확인 ({', '.join(certs[:3])})")
            else:
                missing = [c for c in certs if not any(c in uc for uc in u_certs)]
                if missing:
                    failed.append(f"필요 인증 누락: {', '.join(missing)}")
                else:
                    passed.append(f"인증 충족: {', '.join(certs[:3])}")

        # 판정
        eligible = (len(failed) == 0) if (len(passed) + len(failed)) > 0 else None
        score = len(passed) / max(1, len(passed) + len(failed)) if (len(passed) + len(failed)) > 0 else None

        exc_short = []
        for e in exceptions_list[:3]:
            if isinstance(e, dict):
                exc_short.append(f"{e.get('condition','')} → {e.get('exception','')}")
        exl_short = []
        for e in exclusions_list[:3]:
            if isinstance(e, dict):
                exl_short.append(f"{e.get('rule','')}: {e.get('detail','')}")

        return {
            "announcement_id": announcement_id,
            "eligible": eligible,
            "score": round(score, 2) if score is not None else None,
            "passed": passed,
            "failed": failed,
            "uncertain": uncertain,
            "exceptions": exc_short,
            "exclusions": exl_short,
            "note": "판정은 자동 대조 결과이며, 예외 조항·단서·최종 심사는 공고 원문 확인 필요.",
        }
    except Exception as e:
        logger.warning(f"[tool eligibility] {e}")
        try: db_conn.rollback()
        except: pass
        return {"error": str(e)[:200], "eligible": None}


def chat_lite_fund_expert(
    messages: List[Dict],
    db_conn=None,
    user_profile: dict = None,
    mode: str = None,  # "business_fund" | "individual_fund" | None (자동 판별)
) -> Dict[str, Any]:
    """LITE 자금 전문 상담. mode 명시 → 사용자 선택 우선.
    mode=None이면 user_profile.user_type + 시드 메시지로 자동 판별.
    """
    if not HAS_GENAI:
        return {"reply": "AI 서비스를 사용할 수 없습니다.", "choices": []}
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"reply": "AI 서비스가 설정되지 않았습니다.", "choices": []}

    # 모드 판별 — 명시적 mode 파라미터가 최우선
    if mode == "individual_fund":
        is_individual = True
    elif mode == "business_fund":
        is_individual = False
    else:
        # mode 미지정 → user_type + 시드 메시지 자동 판별
        user_type = (user_profile or {}).get("user_type", "both").lower()
        first_user_text = ""
        if messages:
            for m in messages:
                if m.get("role") == "user":
                    first_user_text = m.get("text", "")
                    break
        if user_type == "both":
            if any(k in first_user_text for k in ["기업", "법인", "사업자", "중소기업", "창업", "회사"]):
                user_type = "business"
            elif any(k in first_user_text for k in ["개인", "주거", "전세", "월세", "학자금", "생계"]):
                user_type = "individual"
        is_individual = user_type == "individual"

    # 프로필 컨텍스트 (짧게 — tool calling이 주축)
    profile_ctx = ""
    if user_profile:
        u = user_profile
        if is_individual:
            parts = []
            for label, k in [("연령대", "age_range"), ("지역", "address_city"), ("소득", "income_level"),
                             ("가구", "family_type"), ("고용", "employment_status"), ("주거", "housing_status")]:
                if u.get(k):
                    parts.append(f"{label} {u[k]}")
            if parts:
                profile_ctx = f"\n[사용자] {' · '.join(parts)}"
        else:
            parts = []
            for label, k in [("업종", "industry_code"), ("지역", "address_city"),
                             ("매출", "revenue_bracket"), ("직원", "employee_count_bracket"),
                             ("설립", "establishment_date")]:
                if u.get(k):
                    parts.append(f"{label} {u[k]}")
            if parts:
                profile_ctx = f"\n[사용자] {' · '.join(parts)}"

    # 프롬프트 선택
    if is_individual:
        base_prompt = PROMPT_LITE_FUND_INDIV_TOOL
        tt = "individual"
    else:
        base_prompt = PROMPT_LITE_FUND_BIZ_TOOL
        tt = "business"

    # ── 학습된 지식 주입 (knowledge_base → 프롬프트) ──
    knowledge_ctx = ""
    if db_conn:
        try:
            last_user_text = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    last_user_text = m.get("text", "")
                    break
            if last_user_text:
                kb_items = get_relevant_knowledge(
                    category=None,  # 카테고리 제한 없이 의미검색 우선
                    db_conn=db_conn,
                    query=last_user_text,
                    limit=5,
                )
                if kb_items:
                    parts = ["\n\n[★★★ 축적된 전문 지식 — 도구 결과에 수치가 없으면 아래 지식의 수치를 반드시 인용하세요]"]
                    for item in kb_items:
                        c = item.get("content", {})
                        ktype = item.get("knowledge_type", "")
                        if ktype == "faq" and c.get("question"):
                            parts.append(f"• Q: {c['question'][:100]}\n  A: {c.get('answer', '')[:200]}")
                        elif ktype == "insight":
                            parts.append(f"• 실무팁: {c.get('relationship', c.get('tips', str(c)))[:200]}")
                        elif ktype == "error":
                            parts.append(f"• 주의: {c.get('wrong_info', '')[:80]} → 올바른 정보: {c.get('correct_info', '')[:150]}")
                        elif ktype == "pattern":
                            parts.append(f"• 패턴: {c.get('tips', str(c))[:200]}")
                    knowledge_ctx = "\n".join(parts)
        except Exception as kb_err:
            logger.warning(f"[LITE kb inject] {kb_err}")

    system_prompt = base_prompt + profile_ctx + knowledge_ctx

    # ── Tool 정의 (OpenAI / Gemini 공용) ──
    def _exec_tool(name: str, args: dict) -> dict:
        """도구 실행 — 이름으로 라우팅"""
        if name == "search_fund_announcements":
            rows = _tool_search_fund_announcements(db_conn, args.get("keywords", ""), args.get("target_type", tt), limit=5)
            return {"count": len(rows), "results": rows}
        elif name == "get_announcement_detail":
            return _tool_get_announcement_detail(db_conn, int(args.get("announcement_id", 0)))
        elif name == "search_knowledge_base":
            rows = _tool_search_knowledge_base(db_conn, args.get("query", ""), limit=5)
            return {"count": len(rows), "results": rows}
        elif name == "check_eligibility":
            _p = dict(user_profile or {})
            try:
                from datetime import datetime
                est = _p.get("establishment_date")
                if est and "business_years" not in _p:
                    dt = datetime.strptime(str(est)[:10], "%Y-%m-%d")
                    _p["business_years"] = (datetime.now() - dt).days // 365
            except Exception: pass
            return _tool_check_eligibility(db_conn, int(args.get("announcement_id", 0)), _p)
        return {}

    OPENAI_TOOLS = [
        {"type": "function", "function": {"name": "search_fund_announcements", "description": "자금/대출/보증 관련 공고를 DB에서 검색", "parameters": {"type": "object", "properties": {"keywords": {"type": "string", "description": "검색 키워드"}, "target_type": {"type": "string", "enum": ["business", "individual"], "description": "기업 또는 개인"}}, "required": ["keywords"]}}},
        {"type": "function", "function": {"name": "get_announcement_detail", "description": "특정 공고의 상세 정보 조회", "parameters": {"type": "object", "properties": {"announcement_id": {"type": "integer", "description": "공고 ID"}}, "required": ["announcement_id"]}}},
        {"type": "function", "function": {"name": "search_knowledge_base", "description": "금융/보증 관련 FAQ·실무 팁 검색", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "검색어"}}, "required": ["query"]}}},
        {"type": "function", "function": {"name": "check_eligibility", "description": "사용자 프로필과 공고 자격 조건 대조 판정", "parameters": {"type": "object", "properties": {"announcement_id": {"type": "integer", "description": "공고 ID"}}, "required": ["announcement_id"]}}},
    ]

    reply_text = ""
    parsed_choices: List[str] = []
    tool_calls = []
    _engine_used = "none"

    # ── 1차: OpenAI (기본) ──
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)

            oai_messages = [{"role": "system", "content": system_prompt}]
            for m in messages[:-1]:
                role = "user" if m.get("role") == "user" else "assistant"
                oai_messages.append({"role": role, "content": m.get("text", "")})
            oai_messages.append({"role": "user", "content": messages[-1].get("text", "시작") if messages else "시작"})

            # Tool Calling 루프 (최대 3회 도구 호출)
            for _ in range(4):
                # 첫 호출에서 반드시 도구를 사용하도록 강제
                _tc = {"type": "function", "function": {"name": "search_fund_announcements"}} if _ == 0 else "auto"
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=oai_messages,
                    tools=OPENAI_TOOLS,
                    tool_choice=_tc,
                    max_tokens=4096,
                    temperature=0.5,
                )
                msg = resp.choices[0].message

                if msg.tool_calls:
                    oai_messages.append(msg)
                    for tc in msg.tool_calls:
                        fn_name = tc.function.name
                        fn_args = json.loads(tc.function.arguments)
                        tool_calls.append(fn_name)
                        result = _exec_tool(fn_name, fn_args)
                        oai_messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, ensure_ascii=False)[:3000],
                        })
                else:
                    reply_text = msg.content or ""
                    break

            reply_text, parsed_choices = _parse_choices_marker(reply_text)
            reply_text = _remove_tool_code_leaks(reply_text)
            _engine_used = "openai"

        except Exception as oai_err:
            logger.warning(f"[LITE OpenAI] {oai_err}")
            reply_text = ""  # 폴백으로 넘어감

    # ── 2차: Gemini (폴백) ──
    if not reply_text:
        try:
            genai.configure(api_key=api_key)

            def search_fund_announcements(keywords: str, target_type: str = tt) -> dict:
                """자금/대출/보증 관련 공고를 DB에서 검색합니다."""
                rows = _tool_search_fund_announcements(db_conn, keywords, target_type, limit=5)
                return {"count": len(rows), "results": rows}
            def get_announcement_detail(announcement_id: int) -> dict:
                """특정 공고의 상세 정보를 조회합니다."""
                return _tool_get_announcement_detail(db_conn, int(announcement_id))
            def search_knowledge_base(query: str) -> dict:
                """금융/보증 관련 FAQ·실무 팁을 검색합니다."""
                rows = _tool_search_knowledge_base(db_conn, query, limit=5)
                return {"count": len(rows), "results": rows}
            def check_eligibility(announcement_id: int) -> dict:
                """사용자 프로필과 공고 자격 조건을 대조합니다."""
                _p = dict(user_profile or {})
                try:
                    from datetime import datetime
                    est = _p.get("establishment_date")
                    if est and "business_years" not in _p:
                        dt = datetime.strptime(str(est)[:10], "%Y-%m-%d")
                        _p["business_years"] = (datetime.now() - dt).days // 365
                except Exception: pass
                return _tool_check_eligibility(db_conn, int(announcement_id), _p)

            tools = [search_fund_announcements, get_announcement_detail, search_knowledge_base, check_eligibility]
            model = genai.GenerativeModel(
                "models/gemini-2.0-flash", tools=tools, system_instruction=system_prompt,
                generation_config={"max_output_tokens": 4096, "temperature": 0.5},
            )
            chat = model.start_chat(enable_automatic_function_calling=True)
            for m in messages[:-1]:
                if m.get("role") == "user":
                    chat.send_message(m.get("text", ""))
            last_msg = messages[-1].get("text", "") if messages else "시작"
            response = chat.send_message(last_msg)
            reply_text = response.text if hasattr(response, "text") else str(response)
            reply_text, parsed_choices = _parse_choices_marker(reply_text)
            reply_text = _remove_tool_code_leaks(reply_text)
            _engine_used = "gemini"
            try:
                for h in chat.history:
                    for part in getattr(h, "parts", []):
                        fc = getattr(part, "function_call", None)
                        if fc and fc.name:
                            tool_calls.append(fc.name)
            except Exception: pass

        except Exception as e:
            logger.warning(f"[LITE Gemini fallback] {e}")
            return {
                "reply": "일시적으로 응답 생성에 실패했습니다. 다시 시도해주세요.",
                "choices": ["✏️ 다시 시도"],
            }

    return {
        "reply": reply_text,
        "choices": parsed_choices,
        "announcements": [],
        "done": False,
        "mode": "individual_fund" if is_individual else "business_fund",
        "tool_calls": tool_calls,
        "engine": _engine_used,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 공고 특화 상담 모드 (1개 공고 정밀 상담)
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

    # 골든 답변 시스템 제거됨 — 통째 캐시는 컨텍스트/시점 변화 반영 불가
    # 대신 announcement_analysis + knowledge_base를 AI에게 참고 자료로 전달

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

    # 기업/사용자 정보
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
관심분야: {user_profile.get('interests', '')}
사용자 유형: {user_profile.get('user_type', 'business')}"""

    # ── 사용자 유형 ↔ 공고 대상 미스매치 감지 ──
    user_type_raw = (user_profile.get('user_type') if user_profile else '') or 'business'
    target_type_raw = (a.get('target_type') or 'business').lower().strip()
    type_mismatch_directive = ""
    if user_type_raw == 'business' and target_type_raw == 'individual':
        type_mismatch_directive = """
[★★★ 사용자 유형 미스매치 감지 ★★★]
- 현재 사용자: **법인/사업자(business)** 로 가입한 회원
- 이 공고 대상: **개인(individual)** — 일반 시민/장애인/청년/노인 등 자연인 대상
- ★ 첫 턴 응답 규칙 (절대 준수) ★
  1) conclusion="ineligible"로 명확히 결론 (절대 conditional/확인 필요로 회피 금지)
  2) message 본문에:
     • "이 공고는 **개인**(자연인)을 대상으로 하므로 귀사(법인)는 직접 신청 대상이 아닙니다" 라고 단정
     • 단, 친절하게 우회 경로 안내: "다만, 귀사의 임직원이 개인 자격으로 신청 가능할 수 있으며, 복지 차원에서 직원에게 안내해드리는 것은 가능합니다"
  3) "임직원 중 장애인이 있나요?" 같은 정보 수집 질문 절대 금지 (법인 페르소나에 무례함)"""
    elif user_type_raw == 'individual' and target_type_raw == 'business':
        type_mismatch_directive = """
[★★★ 사용자 유형 미스매치 감지 ★★★]
- 현재 사용자: **개인(individual)**
- 이 공고 대상: **법인/사업자(business)**
- 첫 턴 응답 규칙: conclusion="ineligible"로 명확히 결론. "이 공고는 법인/사업자 대상이며, 개인은 직접 신청 대상이 아닙니다"라고 단정. 단, 본인이 사업자 등록을 했거나 향후 창업 계획이 있으면 신청 가능할 수 있다는 안내 추가."""

    # 후속 질문 강화 컨텍스트
    followup_directive = ""
    if is_followup:
        followup_directive = """
[중요: 후속 질문 응답 규칙]
사용자가 추가 질문을 했습니다. 다음 원칙을 반드시 지키세요:
1. **첫 응답에서 답한 내용을 단순 반복하지 마세요.** 사용자는 이미 그 답을 봤습니다.
2. 사용자 질문에 **직접적이고 깊이 있게** 답하세요. 형식적인 헤더(📋💰📝)나 불필요한 인사 생략.
3. 공고 데이터에 없는 일반 지식 질문은 **Google 검색으로 정확한 정보를 찾아** 답변하세요.
4. **숫자/비율/기간**으로 답할 수 있는 질문에는 반드시 숫자를 포함하세요.
5. **확인할 수 없는 정보는 추측하지 마세요.** "정확한 정보를 확인하지 못했습니다. 담당기관에 문의하세요."로 답하세요.
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
{type_mismatch_directive}{followup_directive}{expert_directive}{loan_directive}

[데이터 활용 우선순위] ★ 답변 시 아래 순서대로 정보 우선 사용 ★
  1순위) 공고 기본 정보 (지원금액·마감일·지역) — 절대 "명시되지 않음" 금지
  2순위) 정밀 분석 결과 (parsed_sections + deep_analysis) — 사실 답변의 핵심 근거
  3순위) 공고 원문 전체 — 위 1·2가 부족할 때만 보조 자료로 사용
  ※ 정밀 분석 데이터에 답이 있는데 원문에서 다른 표현으로 추측 답변 금지

[공고 기본 정보] ★ 이 정보는 절대 "명시되지 않음"이라고 답하지 마세요. 아래 값을 그대로 사용하세요.
제목: {a.get('title', '')}
부처: {a.get('department', '')}
카테고리: {a.get('category', '')}
지원금액: {main_amount or '(공고 원문 참조 필요)'}
마감일: {main_deadline or '상시 모집'}
지역: {a.get('region', '전국')}
자격요건(기본): {json.dumps(elig, ensure_ascii=False)[:500]}
{support_info}

[정밀 분석 — 핵심 근거 자료] ← 답변의 1차 근거
신청자격 원문: {(ps.get('eligibility') or '')[:2000]}
제외대상 원문: {(ps.get('exclusions') or '')[:1000]}
예외조항 원문: {(ps.get('exceptions') or '')[:1000]}
가점항목 원문: {(ps.get('bonus_points') or '')[:500]}
제출서류 원문: {(ps.get('required_docs') or '')[:1000]}
심사기준 원문: {(ps.get('evaluation_criteria') or '')[:1000]}
지원내용 원문: {(ps.get('support_details') or '')[:1000]}
일정 원문: {(ps.get('timeline') or '')[:500]}
신청방법 원문: {(ps.get('application_method') or '')[:500]}

[공고 원문 전체 — 보조 자료] ← 위 분석에 없는 내용만 여기서 보충
{_clean_summary_text(a.get('summary_text') or '')[:2000]}

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

[★★★ 최상위 원칙 — 반드시 준수]
A. **어떤 질문에도 반드시 답변을 시도하세요.** 엉뚱한 질문, 공고와 무관한 질문이라도 회피하지 말고 분석·안내하세요. "데이터가 없습니다"만 반복하는 것은 금지입니다.
B. **그러나 사실이 아닌 정보는 절대 만들지 마세요.** 모르면 "확실하지 않음"이라고 솔직히 답하되, 그 뒤에라도 **분석 가능한 범위는 반드시 수행**하세요.
C. **"분석"과 "날조"는 다릅니다.** 사용자 기업 정보와 공고 자격요건을 객관적으로 대조하는 것은 분석이며 권장됩니다. 숫자·조건·일정 등을 지어내는 것이 날조이며 금지입니다.

[핵심 규칙]
1. **첫 응답은 반드시 "자격 대조 분석"을 포함하세요.** 사용자가 공고를 선택하고 질문(자격요건/지원대상/조건 등)을 하면, 공고 데이터가 부족하더라도 아래를 반드시 수행:
   - 공고 제목·요약·카테고리에서 **대상 업종·기업규모·지역·특수자격**을 추출
   - [기업 정보] 섹션의 사용자 프로필(업종/업력/매출/지역/certifications)과 **객관적 대조**
   - 각 항목별로 `✅ 충족 / ⚠️ 확인 필요 / ❌ 미충족` 중 하나 판정
   - 데이터가 없어서 판단 불가한 항목은 `⚠️ 확인 필요`로 표시하고 사용자에게 질문
   - **"데이터에 없습니다"만 말하고 끝내지 마세요.** 반드시 분석 결과를 먼저 제시한 뒤 보완 질문.

2. **공고 데이터에 명시된 내용이 있으면 그것을 최우선 사실로 사용.** 없는 금액·조건·일정·서류를 지어내지 마세요.

3. **구체 수치(금리/보증료율/한도)는 반드시 Google 검색(google_search)으로 확인.** 공고 원문에 "기준금리 적용", "변동금리", "별도 안내" 같은 모호한 표현만 있으면 **"공고에 정보 없음"으로 간주하고 반드시 검색**하세요.
   예시:
   - 공고: "정책자금 기준금리 적용" → 검색: "2026년 중소기업 정책자금 기준금리" → 답변: "현재 기준금리 약 2.5~3.5%"
   - 공고: "변동금리" → 검색: "2026년 중진공 정책자금 금리" → 답변: "현재 연 2.0~3.5% 수준"
   검색으로도 확인 못하면 "정확한 수치는 확인 필요"라고 답하되 **분석은 계속** 진행.

4. **모호한 표현 금지 대신 단정·판정형으로 말하세요.** "~일 것으로 예상됩니다", "~일 가능성이 높습니다" 같은 추측성 표현은 쓰지 말고, 대신 **`확인된 사실 / 대조 결과 / 확인이 필요한 부분`** 3가지로 명확히 구분해서 답변하세요.

5. **"이 부분은 담당기관 확인 필요"는 전체 답변의 마지막에 딱 한 번만** 짧게 덧붙이세요. 매 문단마다 반복하지 마세요.

6. **출처 표기 금지.** "(출처: ...)", "([공고 원문] 참고)" 같은 문구는 붙이지 마세요.

7. **첫 응답(messages 배열 길이 1~2)의 구조** — 반드시 아래 순서로 작성:
   ```
   📌 공고 요약
     • 대상 / 지원금액 / 마감일 / 주관기관 (4줄 이내, 공고 데이터에서 추출)

   🔍 자격 대조 (귀사 기준)    ← [기업 정보] 있을 때만 출력
     ✅ 업종: ... → 가능
     ✅ 기업규모: ... → 가능
     ⚠️ ... → 확인 필요
     ❌ ... → 미충족 (있으면)
     👉 종합: 신청 가능 / 조건부 가능 / 대상 아님 (1~2줄 근거)

   💡 추가로 물어볼 만한 것들     ← choices 필드로도 동일 버튼 제공
   ```
   - [기업 정보]가 없거나 핵심 필드(업종/지역/매출)가 비어있으면: 자격 대조 섹션 대신 "자격 대조를 원하시면 귀사 정보를 알려주세요" + choices로 업종 선택 버튼 제시
   - 공고 데이터가 부족한 섹션은 "명시되지 않음" 반복 대신 통째로 생략. 중요한 1~2개만 누락이면 마지막에 "💡 금액·마감은 공고 원문 참조" 한 줄.

8. **2턴 이후(후속 질문)는 사용자 리드 따라가기**:
   - 사용자가 "서류 알려줘" → 바로 서류 답변 (자격 재분석/정보 수집 강요 금지)
   - 사용자가 "금액 얼마야" → 금액만 답변
   - 사용자가 "우리 매출 30억" 같은 정보를 흘리면 → 속으로 기억하고 다음 자격 판정 때 활용 (같은 정보 재질문 금지)
   - 사용자가 "지원 가능해?"/"자격 돼?"/"받을 수 있어?" 같이 **판정 요청**을 명시하면 → 그때 판정 수행 (done=true, conclusion 설정)

9. **질문은 꼭 필요할 때만**:
   - 판정 요청이 있는데 핵심 필드가 부족 → 부족한 1~2개만 한번에 질문
   - 판정 요청이 없으면 프로필 질문 강요 금지
   - 같은 정보를 두 번 묻지 마세요 (대화 히스토리 확인 필수)

10. **예외조항·제외대상 체크**: 공고 데이터에 제외조항이 있으면 첫 응답의 자격 대조에 반영. 사용자가 해당되는지 확인 필요 시 ⚠️로 표시.

11. **판정 시 원칙**:
    - "지원 가능(eligible)" / "조건부 가능(conditional)" / "지원 불가(ineligible)" 3가지 중 명확히 선택
    - 불확실한 부분이 있으면 무조건 "conditional"
    - 2~3턴 이내 결론 가능. 완벽한 정보가 없어도 "조건부 가능"으로 결론 내고 확인 필요 항목만 명시
    - 무한 질문 금지

12. **가점·심사기준·양식 정보**가 공고 데이터에 있으면 해당 주제를 물어볼 때 활용. 없으면 일반 조언은 생략.

13. **톤**: 한국어, 친절하고 전문적. 답변은 충분히 상세하되 군더더기 없이.

14. **법적 효력 없음 고지**: 판정(conclusion) 낼 때 message 마지막에 "※ 최종 결과는 주관기관의 심사에 따릅니다"를 한 번만 짧게 덧붙이세요.

[응답 형식 — 반드시 이 JSON 형식으로만 응답]
**중요: 아래 필드 순서를 반드시 지키세요 (done → conclusion → choices → message 순서)**
{{
  "done": false,
  "conclusion": null,
  "choices": ["선택지1", "선택지2", "선택지3"],
  "message": "AI의 답변 텍스트 (충분히 상세하게, 마크다운 사용 가능)"
}}
- done: **[최우선 규칙] 입력 messages 배열 길이가 1~2개면 무조건 done=false입니다. 절대 예외 없음.** 첫 응답은 공고 정보 안내 + 후속 질문 유도만 하세요. done=true는 사용자가 구체적 조건을 제공하고 자격 판단을 요청한 경우(최소 3턴 이상, messages 5개 이상)에만 설정하세요.
- conclusion: done=true일 때 반드시 설정. "eligible"(지원 가능) | "conditional"(조건부 가능) | "ineligible"(지원 불가).
  **★★★ conclusion은 message 본문의 최종 판정과 반드시 정확히 일치해야 합니다. ★★★**
  - message에 "미충족 / 지원 불가 / 대상 아님 / 신청 자격 없음" → conclusion="ineligible" (절대 eligible 금지)
  - message에 "조건부 / 확인 필요 / 일부 보완 필요" → conclusion="conditional"
  - message에 "지원 가능 / 자격 충족" + 부정 표현 없음 → conclusion="eligible"
  - 불확실하면 "conditional". 본문과 JSON 필드가 다르면 심각한 데이터 오염입니다.
- choices: 사용자가 **AI에게 이 공고에 대해 추가로 물어볼 만한 후속 질문** 2~4개 (3개 권장).
  ★★★ choices 작성 절대 규칙 ★★★
  1) 반드시 **물음표(?)로 끝나는 의문문**일 것
  2) 반드시 **"이 공고"에 대한 추가 질문**일 것 (사용자 본인 정보를 묻는 게 아님!)
  3) 액션/네비게이션 금지: "저장하기", "알아보기", "문의하기", "닫기" 등의 동사형 절대 금지
  4) 사용자에게 묻는 질문 금지: "업종이 뭔가요?", "언제 가입했나요?" 같은 정보 수집 질문 금지
  5) 한 줄당 25자 이내, 자연스러운 한국어
  ✅ 좋은 예: "지원금은 정확히 얼마인가요?", "신청 기간은 언제까지인가요?", "필요한 서류는 무엇인가요?", "선정 가능성을 높이려면 어떻게 해야 하나요?", "비슷한 다른 지원사업도 있나요?"
  ❌ 나쁜 예: "상담 내용 저장하기", "다른 지원사업도 알아보기", "담당기관에 문의하기", "사업장 업종은 무엇인가요?"
  done=true여도 빈 배열이 아닌 후속 질문 선택지를 제공하세요.
- message: 답변 텍스트. **이 필드를 가장 마지막에 배치하세요.**

반드시 순수 JSON만 반환하세요. JSON 외의 텍스트를 포함하지 마세요."""

    # ── 새 SDK (google.genai) + Google Search Grounding ──
    _sdk_used = "unknown"
    try:
        from google import genai as genai_new
        from google.genai import types as genai_types
        _sdk_used = "google-genai (new)"
        print(f"[AIConsultant] Using new SDK: google-genai")

        _client = genai_new.Client(api_key=api_key)

        # 대화 히스토리 구성
        chat_history = [
            genai_types.Content(role="user", parts=[genai_types.Part(text=system_prompt)]),
            genai_types.Content(role="model", parts=[genai_types.Part(text='{"done": false, "conclusion": null, "choices": [], "message": "understood"}')]),
        ]
        for msg in messages[:-1]:
            role = "user" if msg.get("role") == "user" else "model"
            chat_history.append(genai_types.Content(role=role, parts=[genai_types.Part(text=msg.get("text", ""))]))

        _chat = _client.chats.create(
            model="gemini-2.0-flash",
            history=chat_history,
            config=genai_types.GenerateContentConfig(
                tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
                max_output_tokens=4096,
            ),
        )
        last_msg = messages[-1].get("text", "시작") if messages else "시작"
        response = _chat.send_message(last_msg)
    except Exception as sdk_err:
        # 새 SDK 실패 → 기존 SDK 폴백
        _sdk_used = f"google-generativeai (fallback: {type(sdk_err).__name__}: {str(sdk_err)[:100]})"
        print(f"[AIConsultant] New SDK failed: {sdk_err}, falling back to old SDK")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-2.0-flash", generation_config={"max_output_tokens": 4096})
        gemini_messages = []
        for msg in messages:
            role = "user" if msg.get("role") == "user" else "model"
            gemini_messages.append({"role": role, "parts": [msg.get("text", "")]})
        _chat = model.start_chat(history=[
            {"role": "user", "parts": [system_prompt]},
            {"role": "model", "parts": ['{"done": false, "conclusion": null, "choices": [], "message": "understood"}']},
            *gemini_messages[:-1]
        ])
        response = _chat.send_message(gemini_messages[-1]["parts"][0] if gemini_messages else "시작")

    try:
        print(f"[AIConsultant] SDK used: {_sdk_used}")
        logger.info(f"[Gemini raw response length] {len(response.text)} chars")
        result = _parse_gemini_json(response.text)

        # ── 방어적 후처리: AI가 message에 raw JSON 키를 흘렸을 때 강제 절단 ──
        msg_text = result.get("message", "")
        for json_key in ['"choices":', '"done":', '"conclusion":', '"profile":', '"message":']:
            idx = msg_text.find(json_key)
            if idx > 0:
                msg_text = msg_text[:idx].rstrip(' \t\n,;{')

        # 패턴: "choices: [...]" 박혀있으면 분리
        choices_pattern = re.search(r'choices\s*[:：]\s*\[([^\]]+)\]', msg_text, re.IGNORECASE)
        ai_choices_inline = []
        if choices_pattern:
            try:
                raw = "[" + choices_pattern.group(1) + "]"
                raw = raw.replace("'", '"')
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    ai_choices_inline = parsed
                msg_text = re.sub(r'\n*\s*choices\s*[:：]\s*\[[^\]]+\]\s*', '', msg_text, flags=re.IGNORECASE).strip()
            except Exception:
                pass

        # 패턴: "선택지:" / "옵션:" 라벨 라인 제거
        msg_text = re.sub(r'\n*\s*(선택지|옵션)\s*[:：].*$', '', msg_text, flags=re.MULTILINE).strip()
        msg_text = msg_text.rstrip('",\n\t ;{}[]')

        result["message"] = msg_text
        if ai_choices_inline and not result.get("choices"):
            result["choices"] = ai_choices_inline

        # 교차 검증: Gemini 응답을 DB 데이터와 대조
        verified_reply = _verify_response(
            result.get("message", ""), announcement, deep_analysis_data
        )

        done = result.get("done", False)
        conclusion = result.get("conclusion")

        # ── conclusion 교차 검증·자동 감지 ──
        # Gemini가 message 본문과 conclusion JSON 필드를 불일치시키는 버그가 빈번.
        # 예: message에 "미충족/지원 불가"라고 써놓고 conclusion="eligible"로 설정.
        # → message 본문에서 키워드 스캔하여 정답 conclusion을 추정하고 필드 보정.
        def _detect_conclusion_from_text(text: str) -> Optional[str]:
            """message 본문에서 가장 강한 판정 키워드를 찾아 conclusion 추정"""
            if not text:
                return None
            clean = re.sub(r'[*_`#]', '', text.lower())
            # 우선순위 순서: ineligible > conditional > eligible
            # (ineligible 키워드가 있으면 무조건 ineligible로. conditional은 그 다음. eligible은 가장 약함)
            ineligible_patterns = [
                "지원 불가", "지원이 어렵", "자격을 충족하지 못", "지원 대상이 아", "지원이 불가",
                "해당되지 않", "해당하지 않", "미충족", "대상 아님", "대상이 아니", "신청 자격이 없",
                "신청하실 수 없", "지원하실 수 없", "자격 요건을 갖추지", "자격 미달",
            ]
            if any(p in clean for p in ineligible_patterns):
                return "ineligible"
            conditional_patterns = [
                "조건부 가능", "조건부 지원 가능", "조건부로 가능", "조건부로 지원", "조건부",
                "추가 확인이 필요", "일부 충족", "조건에 따라", "확인 필요",
            ]
            if any(p in clean for p in conditional_patterns):
                return "conditional"
            eligible_patterns = [
                "지원 가능합니다", "지원 가능으로 판단", "자격을 충족합니다",
                "지원이 가능합니다", "지원 자격을 충족", "지원 가능 여부: 가능",
                "충족합니다", "해당됩니다", "신청 가능합니다",
            ]
            if any(p in clean for p in eligible_patterns):
                return "eligible"
            return None

        detected = _detect_conclusion_from_text(verified_reply)

        # Case 1: Gemini가 done=false인데 본문엔 결론이 있음 → 자동 감지 후 보정
        if not done and detected:
            logger.info(f"[Auto-detect] done=false, detected conclusion '{detected}' in reply")
            done = True
            conclusion = detected

        # Case 2: Gemini가 done=true인데 conclusion이 본문과 불일치 → 본문 기준으로 교정
        # (Gemini의 자기 일관성 버그 방지 — 숫자 통계 왜곡 방지)
        elif done and detected and conclusion != detected:
            logger.warning(f"[Conclusion override] Gemini said '{conclusion}' but text indicates '{detected}'. Overriding.")
            conclusion = detected

        # Case 3: Gemini가 done=true인데 conclusion이 없거나 유효하지 않음 → 본문으로 채움
        elif done and conclusion not in ("eligible", "conditional", "ineligible"):
            if detected:
                conclusion = detected
                logger.info(f"[Auto-fill] done=true but conclusion invalid, filled from text: '{detected}'")

        # choices 정리 — AI 응답 sanitize + 빈/불량 fallback
        raw_choices = result.get("choices", []) or []
        # 액션·네비게이션·정보수집 질문 키워드 (사용자가 AI에게 묻는 질문이 아닌 것)
        _bad_keywords = (
            "저장", "닫기", "알아보기", "문의하기", "출력", "이동", "보기",
            "등록", "설정", "선택해", "입력해", "알려주세요", "어디", "언제 가입",
            "업종은 무엇", "회사명", "사업장 ", "귀사 ",
        )
        cleaned: list[str] = []
        for c in raw_choices:
            s = str(c).strip()
            if not s or len(s) > 35:
                continue
            # 의문문 보장: 물음표가 없으면 제외 (단, ✏️ 직접 입력은 예외)
            if "?" not in s and "직접" not in s:
                continue
            # 액션/정보 수집 키워드 차단
            if any(k in s for k in _bad_keywords):
                continue
            cleaned.append(s)
        choices = cleaned[:6]
        # ── 이미 사용자가 물어본 질문은 choices에서 제거 (중복 방지) ──
        prior_user_texts = " ".join(
            (m.get("text") or "") for m in messages if m.get("role") == "user"
        ).lower()
        def _already_asked(c: str) -> bool:
            cs = str(c).strip().lower()
            # 핵심 키워드 추출 (조사/어미 제거)
            keywords = []
            for kw in ["지원금", "지원 금액", "얼마", "마감", "신청 기간", "신청기간",
                       "서류", "신청 방법", "신청방법", "어디서", "지원 가능", "신청 가능",
                       "자격", "대상", "자부담"]:
                if kw in cs:
                    keywords.append(kw)
            if not keywords:
                return False
            # 사용자가 이미 그 키워드로 질문했으면 중복으로 간주
            return any(kw in prior_user_texts for kw in keywords)
        choices = [c for c in choices if not _already_asked(c)][:4]
        if len(choices) < 2:
            # fallback도 이미 질문한 것 제외
            pool = [
                "지원금은 정확히 얼마인가요?",
                "신청 기간은 언제까지인가요?",
                "필요한 서류는 무엇인가요?",
                "선정 가능성을 높이려면 어떻게 해야 하나요?",
                "비슷한 다른 지원사업도 있나요?",
                "심사 기준은 무엇인가요?",
                "가점 항목은 어떤 것이 있나요?",
            ]
            choices = [c for c in pool if not _already_asked(c)][:3]
            if len(choices) < 2:
                # 그래도 부족하면 필수 fallback (드문 케이스)
                choices = ["선정 가능성을 높이려면 어떻게 해야 하나요?", "비슷한 다른 지원사업도 있나요?"]
        # 직접 입력 옵션이 없으면 마지막에 추가 (사용자 자유 입력 보장)
        if not any("직접" in str(c) or "기타" in str(c) for c in choices):
            choices = list(choices) + ["✏️ 직접 입력"]

        # 추측 표현 후처리 — "~일 것입니다" 등을 "~입니다"로 변환하지 않고, 불확실 명시로 교체
        import re as _re
        if verified_reply:
            verified_reply = _re.sub(r'(\S+)일 것으로 예상됩니다', r'\1 여부는 담당기관에 확인이 필요합니다', verified_reply)
            verified_reply = _re.sub(r'(\S+)일 가능성이 높습니다', r'\1 여부는 담당기관에 확인이 필요합니다', verified_reply)

        response_data = {
            "reply": verified_reply,
            "choices": choices,
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
# (레거시 chat_consultant 제거됨 — chat_pro_consultant로 대체)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONSULTANT_REQUIRED_FIELDS = [
    "company_name", "establishment_date", "industry_code",
    "revenue_bracket", "employee_count_bracket", "address_city", "interests"
]

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


def _get_batch_api_key() -> Optional[str]:
    """배치 작업용 API 키 반환 — 상담용 키와 분리하여 quota 보호."""
    return os.environ.get("GEMINI_BATCH_API_KEY") or os.environ.get("GEMINI_API_KEY")


BATCH_MODEL = os.environ.get("GEMINI_BATCH_MODEL", "gemini-2.5-flash")


def _generate_knowledge_embedding(content: dict, category: str = None) -> Optional[list]:
    """지식 콘텐츠에서 임베딩용 텍스트를 추출하고 768차원 벡터 생성."""
    if not HAS_GENAI:
        return None
    api_key = _get_batch_api_key()
    if not api_key:
        return None

    # 콘텐츠에서 임베딩용 텍스트 조합
    parts = []
    if category:
        parts.append(category)
    for key in ("question", "answer", "tips", "relationship", "wrong_info", "correct_info", "cause"):
        val = content.get(key)
        if val and isinstance(val, str):
            parts.append(val[:300])
    if not parts:
        parts.append(json.dumps(content, ensure_ascii=False)[:500])
    text = " ".join(parts)

    try:
        genai.configure(api_key=api_key)
        res = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text,
            task_type="retrieval_document",
            output_dimensionality=768,
        )
        vec = res.get("embedding") if isinstance(res, dict) else res["embedding"]
        return vec if vec else None
    except Exception as e:
        logger.warning(f"[Knowledge embed] {e}")
        return None


def save_knowledge(
    source: str,
    knowledge_type: str,
    content: dict,
    db_conn,
    category: str = None,
    announcement_id: int = None,
    confidence: float = 0.5,
    source_agent: str = None,
):
    """공유 지식 저장소에 학습 결과 저장 + 임베딩 자동 생성 + source_agent 태그."""
    try:
        # 임베딩 생성
        embedding = _generate_knowledge_embedding(content, category)
        embed_str = None
        if embedding:
            embed_str = "[" + ",".join(f"{v:.6f}" for v in embedding) + "]"

        cur = db_conn.cursor()
        cur.execute("""
            INSERT INTO knowledge_base (source, knowledge_type, category, announcement_id, content, confidence, embedding, source_agent)
            VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s)
        """, (source, knowledge_type, category, announcement_id,
              json.dumps(content, ensure_ascii=False), confidence, embed_str, source_agent))
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
    query: str = None,
    allowed_agents: list = None,
) -> List[Dict]:
    """
    상담 시 관련 지식을 조회하여 프롬프트에 주입.
    query가 있으면 임베딩 의미 검색 우선, 없으면 카테고리 매칭 폴백.
    allowed_agents: 허용 source_agent 목록 (학습 전파 격리용). None이면 전체 허용.
    """
    if not category and not query:
        return []

    results = []
    ids = []

    try:
        cur = db_conn.cursor()

        # ── 1) 임베딩 의미 검색 (query가 있고 임베딩 데이터가 있을 때) ──
        if query and HAS_GENAI:
            try:
                api_key = os.environ.get("GEMINI_API_KEY")
                if api_key:
                    genai.configure(api_key=api_key)
                    res = genai.embed_content(
                        model="models/gemini-embedding-001",
                        content=query,
                        task_type="retrieval_query",
                        output_dimensionality=768,
                    )
                    vec = res.get("embedding") if isinstance(res, dict) else res["embedding"]
                    if vec:
                        vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
                        type_filter = ""
                        agent_filter = ""
                        params = [vec_str]
                        if knowledge_types:
                            placeholders = ",".join(["%s"] * len(knowledge_types))
                            type_filter = f"AND knowledge_type IN ({placeholders})"
                            params.extend(knowledge_types)
                        if allowed_agents:
                            placeholders_a = ",".join(["%s"] * len(allowed_agents))
                            agent_filter = f"AND (source_agent IS NULL OR source_agent IN ({placeholders_a}))"
                            params.extend(allowed_agents)
                        params.append(limit)
                        cur.execute(f"""
                            SELECT id, source, knowledge_type, content, confidence, use_count,
                                   1 - (embedding <=> %s::vector) AS similarity
                            FROM knowledge_base
                            WHERE embedding IS NOT NULL AND confidence >= 0.4
                            {type_filter}
                            {agent_filter}
                            ORDER BY similarity DESC
                            LIMIT %s
                        """, params)
                        rows = cur.fetchall()
                        for row in rows:
                            r = dict(row)
                            sim = float(r.get("similarity") or 0)
                            if sim < 0.5:
                                continue
                            content = r["content"]
                            if isinstance(content, str):
                                try:
                                    content = json.loads(content)
                                except Exception:
                                    pass
                            r["content"] = content
                            r["similarity"] = round(sim, 3)
                            results.append(r)
                            ids.append(r["id"])
            except Exception as embed_err:
                logger.warning(f"[Knowledge embed search] {embed_err}")

        # ── 2) 임베딩 검색 결과 부족 시 카테고리 매칭 폴백 ──
        if len(results) < limit and category:
            existing_ids = set(ids)
            type_filter = ""
            agent_filter = ""
            params = [category]
            if knowledge_types:
                placeholders = ",".join(["%s"] * len(knowledge_types))
                type_filter = f"AND knowledge_type IN ({placeholders})"
                params.extend(knowledge_types)
            if allowed_agents:
                placeholders_a = ",".join(["%s"] * len(allowed_agents))
                agent_filter = f"AND (source_agent IS NULL OR source_agent IN ({placeholders_a}))"
                params.extend(allowed_agents)
            params.append(limit - len(results))
            cur.execute(f"""
                SELECT id, source, knowledge_type, content, confidence, use_count
                FROM knowledge_base
                WHERE category = %s AND confidence >= 0.4
                {type_filter}
                {agent_filter}
                ORDER BY confidence DESC, use_count DESC
                LIMIT %s
            """, params)
            for row in cur.fetchall():
                r = dict(row)
                if r["id"] in existing_ids:
                    continue
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

def chat_pro_consultant(messages: List[Dict], announcement_id: int = None, db_conn=None, explicit_match: bool = False, session_state: Dict = None, selected_client: Dict = None) -> Dict[str, Any]:
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

    # ━━━ 모드 결정: 사업자 vs 개인 ━━━
    _cat = ""
    if session_state:
        _cat = (session_state.get("client_category") or "").lower()
    if not _cat and selected_client:
        _cat = (selected_client.get("client_type") or "").lower()
    if not _cat and messages:
        _first = (messages[0].get("text") or "") if messages[0].get("role") == "user" else ""
        if "개인" in _first and ("사업자" not in _first and "법인" not in _first):
            _cat = "individual"
    # "individual"만 개인(복지) 모드. "individual_biz"(개인사업자) / "corporate"(법인) / "unknown" → 사업자 모드
    _is_individual_mode = (_cat == "individual")

    # ━━━ 선택된 고객의 유형에 맞지 않는 필드 필터링 (혼선 방지) ━━━
    if selected_client:
        if _is_individual_mode:
            # 개인 상담에서 사업자 전용 필드 제거
            for k in ("industry_code", "industry_name", "revenue_bracket", "employee_count_bracket", "business_number"):
                selected_client.pop(k, None)
        else:
            # 사업자 상담에서 개인 전용 필드 제거
            for k in ("age_range", "income_level", "family_type", "employment_status", "housing_status", "special_conditions"):
                selected_client.pop(k, None)

    # ━━━ 모드별 완전 독립 프롬프트 ━━━
    if _is_individual_mode:
        system_prompt = PROMPT_PRO_INDIVIDUAL.replace("{FINANCIAL_BLOCK}", financial_knowledge_block)
    else:
        system_prompt = PROMPT_PRO_BUSINESS.replace("{FINANCIAL_BLOCK}", financial_knowledge_block)
    # I: 선택된 고객 프로필 주입
    client_hint = ""
    if selected_client:
        cp = selected_client
        client_hint = "\n\n[★★ 선택된 고객 프로파일 — 이 고객을 위한 상담입니다]\n"
        fields = [
            ("고객명", cp.get("client_name")),
            ("유형", cp.get("client_type")),
            ("사업자번호", cp.get("business_number")),
            ("업종코드", cp.get("industry_code")),
            ("소재지", cp.get("address_city")),
            ("설립일", cp.get("establishment_date")),
            ("매출", cp.get("revenue_bracket")),
            ("직원수", cp.get("employee_count_bracket")),
            ("관심분야", cp.get("interests")),
            ("연락처", cp.get("contact_phone")),
            ("담당자", cp.get("contact_name")),
            ("메모", cp.get("memo")),
        ]
        for label, val in fields:
            if val:
                client_hint += f"- {label}: {val}\n"
        client_hint += "\n[★★★ 절대 규칙] 위 고객 정보는 이미 확보된 것이다. 절대 다시 묻지 말 것.\n"
        client_hint += "- collected JSON에 자동 반영하라.\n"
        client_hint += "- 부족한 정보만 한 번에 하나씩 질문하라. 빈 양식을 통째로 보여주지 말 것.\n"
        client_hint += "- 예: 업종/지역/매출이 이미 있으면 → 관심분야만 질문.\n"

    # ── 시드 메시지에서 고객 유형 사전 추출 → system_prompt에 강한 힌트 주입 ──
    seed_hint = ""
    if messages:
        first_user = next((m.get("text", "") for m in messages if m.get("role") == "user"), "")
        if "[새 케이스 시작]" in first_user:
            if "사업자" in first_user or "법인" in first_user or "기업" in first_user:
                seed_hint = "\n\n[현재 케이스] 사업자/법인 고객. 고객 유형은 이미 확정. 1단계 건너뛰고 2단계(니즈 파악)부터 시작하세요."
            elif "예비창업" in first_user or "예비 창업" in first_user:
                seed_hint = "\n\n[현재 케이스] 예비창업자. 고객 유형은 이미 확정. 1단계 건너뛰고 2단계부터 시작하세요."
            elif "개인" in first_user:
                seed_hint = "\n\n[현재 케이스] 개인 고객. 고객 유형은 이미 확정. 1단계 건너뛰고 개인 모드 2단계(니즈 파악)부터 시작하세요. choices는 개인용 카테고리를 제시하세요."

    # ── 세션 상태 주입 — 현재 단계 + 이미 수집된 정보를 명시적으로 알림 ──
    state_hint = ""
    matched_hint = ""
    if session_state:
        cur_step = session_state.get("current_step", 1)
        collected_so_far = session_state.get("collected", {}) or {}
        cat = session_state.get("client_category", "")
        phase = session_state.get("phase", "collecting")
        matched_snap = session_state.get("matched_snapshot") or []
        max_step = 7 if cat == "individual" else 5

        state_hint = f"\n\n[★★★ 세션 상태 — 매우 중요]\n"
        state_hint += f"- 상담 페이즈: {phase}  (collecting=정보수집 / consulting=매칭 후 상담 심화)\n"
        state_hint += f"- 고객 유형: {cat or '미정'}\n"
        state_hint += f"- 현재 진행 단계: {cur_step}단계 / {max_step}단계\n"
        if collected_so_far:
            state_hint += f"- 이미 수집된 정보 (절대 다시 묻지 말 것):\n"
            for k, v in collected_so_far.items():
                if v:
                    state_hint += f"  • {k}: {v}\n"
        else:
            state_hint += "- 아직 수집된 정보 없음\n"
        if phase == "consulting":
            state_hint += "\n[지시] 이 세션은 이미 매칭을 완료한 상태입니다. 정보 수집 단계로 되돌아가지 말 것.\n"
            state_hint += "사용자 질문을 그대로 이해해서 [매칭 결과] 기반으로 답변하세요.\n"
            state_hint += "done=true를 유지하고, choices에 ['📄 보고서 생성', '✏️ 조건 수정', '🔍 특정 공고 상세'] 등 행동형을 허용.\n"
        else:
            state_hint += f"\n[지시] 이번 응답에서 반드시 {cur_step + 1}단계로 진행하세요. 같은 단계에 머물지 말 것.\n"
            state_hint += "이미 받은 정보로 다음 질문을 하세요. 이미 답한 카테고리 재질문 금지.\n"
            state_hint += "응답 JSON의 \"current_step\"에 다음 단계 번호를 명시하세요.\n"

        # D+G: 매칭 결과 + 상위 3개 상세분석 프롬프트 주입
        if matched_snap:
            matched_hint = "\n\n[매칭 결과 — 상담 근거로 사용]\n"
            for i, m in enumerate(matched_snap[:10], 1):
                if not isinstance(m, dict):
                    continue
                title = (m.get("title") or "")[:80]
                dept = (m.get("department") or "")[:40]
                amount = (m.get("support_amount") or "")[:40]
                deadline = str(m.get("deadline_date") or "")[:10]
                score = m.get("match_score") or 0
                matched_hint += f"{i}. [{score}점] {title}\n"
                if dept: matched_hint += f"   • 부처: {dept}\n"
                if amount: matched_hint += f"   • 지원금: {amount}\n"
                if deadline and deadline != "None": matched_hint += f"   • 마감: {deadline}\n"
                # G: 상세분석 필드 (상위 3개만)
                if i <= 3:
                    if m.get("eligibility"):
                        matched_hint += f"   • 자격요건: {m['eligibility'][:300]}\n"
                    if m.get("required_docs"):
                        matched_hint += f"   • 제출서류: {m['required_docs'][:300]}\n"
                    if m.get("how_to_apply"):
                        matched_hint += f"   • 신청방법: {m['how_to_apply'][:200]}\n"
                    if m.get("key_points"):
                        matched_hint += f"   • 핵심포인트: {m['key_points'][:200]}\n"

    # 매 턴 RAG — 섹션 단위 우선 + 공고/지식 보조
    rag_hint = ""
    _rag_sources_for_response = []  # E: 답변에 함께 반환할 출처 카드 데이터
    try:
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("text", "")
                break
        if last_user_msg and db_conn and "[새 케이스 시작]" not in last_user_msg:
            # 사용자 프로필 합성 (collected + selected_client → 메타필터용)
            user_profile_for_rag = {}
            if selected_client:
                user_profile_for_rag.update({
                    "address_city": selected_client.get("address_city"),
                    "industry_code": selected_client.get("industry_code"),
                    "revenue_bracket": selected_client.get("revenue_bracket"),
                })
            if session_state and session_state.get("collected"):
                col = session_state["collected"]
                for k in ("address_city", "industry_code", "revenue_bracket", "age_range"):
                    if col.get(k) and not user_profile_for_rag.get(k):
                        user_profile_for_rag[k] = col[k]

            # 1) 섹션 단위 RAG (라우팅 + 메타필터 적용)
            sec_rag = search_sections_for_rag(
                last_user_msg, db_conn, top_k=6,
                user_profile=user_profile_for_rag if user_profile_for_rag else None,
            )
            if sec_rag.get("text_block"):
                rag_hint += sec_rag["text_block"]
            # 결과를 함수 외부에서 접근할 수 있게 closure 변수에 저장
            _rag_sources_for_response = sec_rag.get("sections", [])

            # 2) 보조: 공고/지식 단위 RAG (섹션이 부족할 때만)
            if not sec_rag.get("sections") or len(sec_rag.get("sections", [])) < 3:
                query_parts = [last_user_msg[:400]]
                if session_state and session_state.get("collected"):
                    col = session_state["collected"]
                    for k in ("interests", "industry_code", "address_city", "age_range"):
                        v = col.get(k)
                        if v:
                            query_parts.append(str(v)[:60])
                rag_query = " ".join(query_parts)
                rag = search_knowledge_for_rag(rag_query, db_conn, top_k_ann=4, top_k_kb=2)
                if rag.get("text_block"):
                    rag_hint += rag["text_block"]
    except Exception as rag_err:
        logger.warning(f"[RAG inject] {rag_err}")

    system_prompt = system_prompt + client_hint + seed_hint + state_hint + matched_hint + rag_hint

    # ═══════════════════════════════════════════════════════════════
    # Mode B (consulting) Tool Calling 분기 — phase가 consulting이면 자연어+도구 기반
    # ═══════════════════════════════════════════════════════════════
    _is_consulting_phase = bool(
        session_state and session_state.get("phase") == "consulting"
    ) or bool(
        session_state and session_state.get("matched_snapshot")
    )
    # 디버그 정보 (응답에 포함되어 테스트에서 확인 가능)
    _mode_b_debug = {
        "session_exists": bool(session_state),
        "phase": session_state.get("phase") if session_state else None,
        "matched_snap_len": len(session_state.get("matched_snapshot") or []) if session_state else 0,
        "tool_calling_entered": _is_consulting_phase,
    }
    if _is_consulting_phase and db_conn and messages:
        try:
            # Mode B 전용 프롬프트 선택 (사업자/개인 분리)
            tool_prompt = PROMPT_PRO_CONSULT_INDIV_TOOL if _is_individual_mode else PROMPT_PRO_CONSULT_BIZ_TOOL
            # 선택된 고객/수집 정보 덧붙임
            tool_prompt_full = tool_prompt + (client_hint or "") + (matched_hint or "")

            genai.configure(api_key=api_key)
            _tt_for_tools = "individual" if _is_individual_mode else "business"

            def search_pro_sections(query: str) -> dict:
                """매칭된 공고의 섹션(자격요건·서류·신청방법·지원내용 등)을 DB에서 검색합니다.

                Args:
                    query: 검색 키워드 (예: "자격요건", "제출서류", "스마트공장")
                """
                rows = _tool_search_pro_sections(db_conn, query, _tt_for_tools, limit=6)
                return {"count": len(rows), "results": rows}

            def get_announcement_detail(announcement_id: int) -> dict:
                """특정 공고의 전체 상세(원문, 자격요건, 서류, 신청방법, 지원내용)를 조회합니다.

                Args:
                    announcement_id: 공고 ID
                """
                return _tool_get_announcement_detail(db_conn, int(announcement_id))

            def search_knowledge_base(query: str) -> dict:
                """과거 상담·FAQ·실무 팁·인사이트를 검색합니다.

                Args:
                    query: 검색어
                """
                rows = _tool_search_knowledge_base(db_conn, query, limit=4)
                return {"count": len(rows), "results": rows}

            def check_eligibility(announcement_id: int) -> dict:
                """선택된 고객 프로필과 특정 공고의 자격 조건을 대조해 자동 판정합니다.
                사용 시점: "이 공고 저희 고객 되나요?", "자격 대상 여부" 판단이 필요할 때.

                Args:
                    announcement_id: 판정 대상 공고 ID
                """
                _p = {}
                cp = selected_client or {}
                if cp:
                    _p["region"] = cp.get("address_city")
                    _p["industry"] = cp.get("industry_code")
                    # 매출/직원 bracket → 중앙값 추정
                    rb = (cp.get("revenue_bracket") or "").strip()
                    if "억" in rb:
                        try:
                            import re as _re
                            nums = [int(x) for x in _re.findall(r"\d+", rb)]
                            if nums: _p["revenue_won"] = int(nums[0]) * 100_000_000
                        except Exception: pass
                    eb = (cp.get("employee_count_bracket") or "").strip()
                    try:
                        import re as _re
                        nums = [int(x) for x in _re.findall(r"\d+", eb)]
                        if nums: _p["employees"] = nums[0]
                    except Exception: pass
                    est = cp.get("establishment_date")
                    if est:
                        try:
                            from datetime import datetime as _dt
                            dt = _dt.strptime(str(est)[:10], "%Y-%m-%d")
                            _p["business_years"] = (_dt.now() - dt).days // 365
                        except Exception: pass
                return _tool_check_eligibility(db_conn, int(announcement_id), _p)

            tools_b = [search_pro_sections, get_announcement_detail, search_knowledge_base, check_eligibility]
            model_b = genai.GenerativeModel(
                "models/gemini-2.0-flash",
                tools=tools_b,
                system_instruction=tool_prompt_full,
                generation_config={"max_output_tokens": 4096, "temperature": 0.5},
            )
            chat_b = model_b.start_chat(enable_automatic_function_calling=True)
            # 이전 대화는 history 인자로 한 번에 (재생 금지 — 타임아웃·중복 방지)
            # 최근 user 메시지만 단발 호출
            last_user_msg_b = messages[-1].get("text", "") if messages else ""
            # 이전 대화 요약을 시스템 프롬프트에 살짝 곁들임
            prev_user_count = sum(1 for m in messages if m.get("role") == "user")
            if prev_user_count >= 2:
                last_user_msg_b = f"[이 상담은 {prev_user_count}번째 질문입니다 — 매칭 이미 완료됨]\n{last_user_msg_b}"
            resp_b = chat_b.send_message(last_user_msg_b)
            reply_b = resp_b.text if hasattr(resp_b, "text") else str(resp_b)

            # choices 파싱 + 도구 코드 노출 제거
            reply_b, parsed_choices_b = _parse_choices_marker(reply_b)
            reply_b = _remove_tool_code_leaks(reply_b)

            return {
                "reply": reply_b,
                "choices": parsed_choices_b,
                "done": True,  # consulting phase 유지
                "profile": None,
                "collected": (session_state.get("collected") if session_state else {}) or {},
                "current_step": (session_state.get("current_step") if session_state else None),
                "rag_sources": _rag_sources_for_response,
                "phase": "consulting",
                "mode_b_debug": _mode_b_debug,
            }
        except Exception as tool_err:
            import traceback as _tb
            tb_str = _tb.format_exc()[-500:]
            logger.warning(f"[PRO Mode B tool calling] {tool_err}\n{tb_str}")
            _mode_b_debug["tool_error"] = f"{type(tool_err).__name__}: {str(tool_err)[:200]}"
            _mode_b_debug["tool_tb"] = tb_str
            # 실패 시 기존 JSON 경로로 폴백

    # ── Mode A 또는 Mode B Tool Calling 실패 시: 기존 JSON 경로 ──
    _pro_init_response = '{"message": "고객 유형을 선택해 주시면 상담을 시작하겠습니다.", "choices": ["사업자(기업)입니다", "개인 고객입니다"], "done": false, "collected": {}, "profile": null}'
    try:
        from google import genai as genai_new
        from google.genai import types as genai_types

        _client = genai_new.Client(api_key=api_key)

        chat_history = [
            genai_types.Content(role="user", parts=[genai_types.Part(text=system_prompt)]),
            genai_types.Content(role="model", parts=[genai_types.Part(text=_pro_init_response)]),
        ]
        for msg in messages[:-1]:
            role = "user" if msg.get("role") == "user" else "model"
            chat_history.append(genai_types.Content(role=role, parts=[genai_types.Part(text=msg.get("text", ""))]))

        _chat = _client.chats.create(
            model="gemini-2.0-flash",
            history=chat_history,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=4096,
                temperature=0.7,
            ),
        )
        last_msg = messages[-1].get("text", "시작") if messages else "시작"
        response = _chat.send_message(last_msg)
    except ImportError:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            "models/gemini-2.0-flash",
            generation_config={
                "max_output_tokens": 4096,
                "response_mime_type": "application/json",
                "temperature": 0.7,
            },
        )
        gemini_messages = []
        for msg in messages:
            role = "user" if msg.get("role") == "user" else "model"
            gemini_messages.append({"role": role, "parts": [msg.get("text", "")]})
        _chat = model.start_chat(history=[
            {"role": "user", "parts": [system_prompt]},
            {"role": "model", "parts": [_pro_init_response]},
            *gemini_messages[:-1]
        ])
        response = _chat.send_message(gemini_messages[-1]["parts"][0] if gemini_messages else "시작")

    try:
        result = _parse_gemini_json(response.text)

        collected = result.get("collected", {})
        done = result.get("done", False)
        profile = result.get("profile")

        REQUIRED = ["company_name", "establishment_date", "industry_code", "revenue_bracket", "employee_count_bracket", "address_city", "interests"]
        if not done and collected and all(collected.get(k) for k in REQUIRED):
            done = True
            profile = {k: collected[k] for k in REQUIRED}
        # 개인 모드 자동 완료: 기본 3 필드 + 복지 필터 최소 2개 (소득/가구/고용/주거/특수 중)
        INDIV_MIN = ["age_range", "address_city", "interests"]
        INDIV_WELFARE = ["income_level", "family_type", "employment_status", "housing_status", "special_conditions"]
        is_individual_flow = bool(
            collected.get("age_range") or collected.get("income_level") or collected.get("family_type")
        )
        welfare_count = sum(1 for k in INDIV_WELFARE if collected.get(k))
        # 자동 완료 조건: AI가 명시적 동의를 감지한 경우(done=true)만 허용, 또는 사용자가 마지막 메시지에서 매칭을 명시 요청
        last_user_text_auto = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_text_auto = m.get("text", "")
                break
        user_asked_match = any(kw in last_user_text_auto for kw in ["매칭 진행", "매칭해", "이 조건으로", "찾아주", "진행해"])
        if (not done and is_individual_flow and all(collected.get(k) for k in INDIV_MIN)
                and welfare_count >= 2 and user_asked_match):
            done = True
            profile = {
                "company_name": collected.get("company_name") or "개인",
                "establishment_date": collected.get("establishment_date") or "1990-01-01",
                "industry_code": "",
                "revenue_bracket": "1억 미만",
                "employee_count_bracket": "5인 미만",
                "address_city": collected.get("address_city", ""),
                "interests": collected.get("interests", ""),
                "age_range": collected.get("age_range", ""),
                "income_level": collected.get("income_level", ""),
                "family_type": collected.get("family_type", ""),
                "employment_status": collected.get("employment_status", ""),
                "housing_status": collected.get("housing_status", ""),
                "special_conditions": collected.get("special_conditions", ""),
            }

        # ★ 매칭 키워드 강제 트리거: 사용자가 매칭 요청 시 done=True
        last_user_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_text = msg.get("text", "")
                break
        # 자동 매칭 트리거 폐기 — explicit_match 파라미터로만 매칭
        # 단, 명시적으로 매칭 버튼을 눌렀을 때(explicit_match=True)는 즉시 매칭 모드
        if explicit_match:
            # 전체 대화에서 관심분야 자동 추출
            all_text = " ".join(m.get("text", "") for m in messages if m.get("role") == "user")
            _detected_interests = []
            _interest_detect = {
                "창업지원": ["창업", "스타트업", "벤처", "예비창업"],
                "기술개발": ["R&D", "기술개발", "연구개발", "기술"],
                "고용지원": ["고용", "채용", "일자리", "인력", "장려금", "인건비"],
                "정책자금": ["정책자금", "융자", "대출", "자금"],
                "수출마케팅": ["수출", "해외", "글로벌", "바우처"],
                "소상공인": ["소상공인", "자영업", "골목상권"],
                "디지털전환": ["디지털", "스마트", "IT", "AI"],
            }
            for tag, kws in _interest_detect.items():
                if any(kw in all_text for kw in kws):
                    _detected_interests.append(tag)
            auto_interests = ",".join(_detected_interests) if _detected_interests else ""

            # 대화에서 구체적 키워드 추출 (카테고리에 매핑 안 되는 원본 키워드)
            _specific_keywords = []
            _specific_patterns = [
                "스마트공장", "스마트팜", "스마트시티", "전기차", "수소", "반도체",
                "바이오", "의료기기", "로봇", "드론", "메타버스", "블록체인",
                "탄소중립", "ESG", "친환경", "재생에너지", "2차전지",
                "콘텐츠", "게임", "웹툰", "K-뷰티", "K-푸드", "한류",
                "프랜차이즈", "물류", "택배", "배달", "공유경제",
            ]
            for kw in _specific_patterns:
                if kw in all_text:
                    _specific_keywords.append(kw)
            # 사용자가 직접 언급한 2글자 이상 명사도 추출 (간단 휴리스틱)
            for word in all_text.replace(",", " ").replace(".", " ").split():
                if len(word) >= 3 and word not in _specific_keywords and not any(word in tag for tag in _detected_interests):
                    if any(kw in word for kw in ["공장", "산업", "사업", "기술", "서비스", "플랫폼", "솔루션"]):
                        _specific_keywords.append(word)

            auto_custom = ",".join(_specific_keywords) if _specific_keywords else ""

            DEFAULTS = {
                "company_name": "고객사",
                "establishment_date": "2024-01-01",
                "industry_code": "",
                "revenue_bracket": "1억 미만",
                "employee_count_bracket": "5인 미만",
                "address_city": "",
                "interests": auto_interests,
            }
            profile = {k: (collected.get(k) or DEFAULTS[k]) for k in REQUIRED}
            # 구체적 키워드를 custom_keywords로 추가
            if auto_custom:
                profile["custom_keywords"] = collected.get("custom_keywords") or auto_custom
            done = True
            logger.info(f"[chat_pro_consultant] Match keyword trigger → done=True with profile")

        # ── 방어적 후처리: AI가 message에 JSON 조각/choices를 흘렸을 때 강제 정리 ──
        msg_text = result.get("message", "")
        ai_choices = result.get("choices", [])

        # 패턴 0: message 안에 raw JSON 키가 등장하면 그 위치 이전까지만 사용
        # (JSON 파싱이 성공했으니 드문 케이스지만 안전장치)
        for json_key in ['"choices":', '"done":', '"collected":', '"profile":']:
            idx = msg_text.find(json_key)
            if idx > 0:
                msg_text = msg_text[:idx].rstrip(' \t\n,;{"')

        # 패턴 1: "choices: [...]" 정확 매칭만 (코드블록/JSON 누출 방어)
        choices_pattern = re.search(r'"?choices"?\s*[:：]\s*\[([^\]]{1,300})\]', msg_text, re.IGNORECASE)
        if choices_pattern:
            try:
                raw = "[" + choices_pattern.group(1) + "]"
                raw = raw.replace("'", '"')
                parsed = json.loads(raw)
                if isinstance(parsed, list) and not ai_choices:
                    ai_choices = parsed
                msg_text = msg_text.replace(choices_pattern.group(0), "").strip()
            except Exception:
                pass

        # 패턴 2: 빈 괄호/따옴표로 끝나면 잘라냄
        msg_text = msg_text.rstrip('",\n\t ;{}[]')

        # 패턴 4: 빈 reply 폴백
        if not msg_text.strip():
            msg_text = "고객 케이스에 대해 좀 더 알려주세요."

        # 첫 인사 직접 입력 옵션 강제 추가 (없으면)
        if ai_choices and not any("직접" in str(c) or "기타" in str(c) for c in ai_choices):
            ai_choices = list(ai_choices) + ["✏️ 직접 입력"]

        # C: 하드코딩 reply 제거 — AI가 생성한 실제 응답 그대로 사용
        # done=true여도 AI의 정리 메시지 유지
        return {
            "reply": msg_text,
            "choices": ai_choices if not done else [],
            "done": done,
            "profile": profile,
            "collected": collected,
            "current_step": result.get("current_step"),
            "rag_sources": _rag_sources_for_response,  # E: 출처 카드 (UI 표시용)
            "mode_b_debug": _mode_b_debug,
        }
    except json.JSONDecodeError:
        # JSON 파싱 실패 — raw text에서 message/choices를 구제 추출 시도
        raw = response.text.strip() if 'response' in dir() else ""
        recovered_msg = raw
        recovered_choices: List[str] = []
        # message 필드 패턴 추출
        m = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
        if m:
            try:
                recovered_msg = json.loads('"' + m.group(1) + '"')
            except Exception:
                recovered_msg = m.group(1)
        # choices 배열 패턴 추출
        c = re.search(r'"choices"\s*:\s*\[(.*?)\]', raw, re.DOTALL)
        if c:
            try:
                recovered_choices = json.loads("[" + c.group(1) + "]")
                if not isinstance(recovered_choices, list):
                    recovered_choices = []
            except Exception:
                recovered_choices = []
        # 세션 상태 보존 — 이전 collected 유지
        prev_collected = (session_state or {}).get("collected", {}) if session_state else {}
        prev_step = (session_state or {}).get("current_step", 1) if session_state else 1
        if not recovered_msg or len(recovered_msg) < 5:
            recovered_msg = "앞선 응답을 정리 중입니다. 다음 정보를 알려주시겠어요?"
        return {
            "reply": recovered_msg,
            "choices": recovered_choices[:6] if recovered_choices else ["✏️ 직접 입력"],
            "done": False,
            "profile": None,
            "collected": prev_collected,
            "current_step": prev_step,
        }
    except Exception as e:
        logger.error(f"[PRO] chat_pro_consultant error: {e}")
        prev_collected = (session_state or {}).get("collected", {}) if session_state else {}
        prev_step = (session_state or {}).get("current_step", 1) if session_state else 1
        return {
            "reply": "일시적으로 응답 생성에 실패했습니다. 같은 내용을 한 번만 더 말씀해 주시거나 ‘직접 입력’을 눌러 주세요.",
            "choices": ["✏️ 직접 입력", "🔄 다시 시도"],
            "done": False,
            "profile": None,
            "collected": prev_collected,
            "current_step": prev_step,
        }
