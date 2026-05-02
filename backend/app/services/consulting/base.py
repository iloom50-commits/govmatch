"""분야별 상담 모듈 공통 베이스

각 분야 모듈이 상속/사용하는 공통 유틸리티.
- 분야 감지
- 시스템 프롬프트 빌더
- knowledge_base 조회
- 공통 통계 데이터
"""

import json
import os
from typing import Dict, List, Optional


# ── 분야 정의 ──
DOMAIN_REGISTRY = {
    "finance": {
        "label": "정책자금/융자/보증",
        "keywords": ["정책자금", "융자", "대출", "보증", "금융", "자금지원", "운전자금", "시설자금",
                     "사업전환자금", "긴급경영", "신용보증", "기술보증", "이차보전", "창업자금"],
        "categories": ["금융", "보증", "융자"],
    },
    "startup": {
        "label": "창업지원",
        "keywords": ["창업", "예비창업", "초기창업", "창업패키지", "창업도약", "TIPS", "액셀러레이터",
                     "창업사관학교", "창업보육", "벤처", "스타트업"],
        "categories": ["창업"],
    },
    "rnd": {
        "label": "R&D/기술개발",
        "keywords": ["R&D", "기술개발", "연구개발", "기술혁신", "기술사업화", "산학연",
                     "특허", "지식재산", "기술이전", "나노", "바이오", "AI", "디지털"],
        "categories": ["기술", "기술개발", "R&D"],
    },
    "export": {
        "label": "수출/판로개척",
        "keywords": ["수출", "해외진출", "글로벌", "무역", "FTA", "바이어", "전시회",
                     "판로", "마케팅", "온라인수출", "이커머스"],
        "categories": ["수출", "마케팅", "판로"],
    },
    "employment": {
        "label": "고용/인력",
        "keywords": ["고용", "채용", "일자리", "직업훈련", "인력양성", "고용유지",
                     "워크넷", "청년고용", "장애인고용", "사회적기업"],
        "categories": ["고용", "인력"],
    },
    # ── 개인 대상 ──
    "youth": {
        "label": "청년",
        "keywords": ["청년", "MZ", "청년도약", "청년내일", "청년월세", "청년전세",
                     "국민취업지원", "청년수당", "청년구직"],
        "categories": ["청년"],
    },
    "housing": {
        "label": "주거",
        "keywords": ["주거", "전세", "월세", "임대", "주택", "행복주택", "매입임대",
                     "주거급여", "보증금", "이사비"],
        "categories": ["주거", "임대"],
    },
    "welfare": {
        "label": "복지/생활안정",
        "keywords": ["복지", "기초생활", "생계급여", "의료급여", "장애인", "노인",
                     "긴급복지", "자활", "차상위", "기초연금", "장애인연금"],
        "categories": ["복지", "생활안정", "장애"],
    },
    "family": {
        "label": "출산/육아/가족",
        "keywords": ["출산", "육아", "임신", "다자녀", "신혼", "부모급여", "아동수당",
                     "양육", "산모", "어린이집", "돌봄", "한부모"],
        "categories": ["출산", "육아", "가족"],
    },
    "education": {
        "label": "교육/장학금",
        "keywords": ["장학금", "학자금", "등록금", "내일배움", "직업훈련", "평생교육",
                     "자격증", "디지털트레이닝", "국가장학", "근로장학"],
        "categories": ["교육", "장학금", "훈련"],
    },
}


def detect_domain(title: str, category: str, text: str = "") -> Optional[str]:
    """공고 제목/카테고리/텍스트에서 분야 감지

    Returns:
        str: 분야 키 ("finance", "startup", ...) 또는 None (일반)
    """
    combined = f"{title} {category} {text}".lower()

    # 키워드 매칭 우선 (점수 기반) — 카테고리보다 제목 키워드가 더 정확
    scores = {}
    for domain_key, domain in DOMAIN_REGISTRY.items():
        score = sum(1 for kw in domain["keywords"] if kw.lower() in combined)
        if score > 0:
            scores[domain_key] = score

    if scores:
        return max(scores, key=scores.get)

    # 키워드 매칭 없으면 카테고리로 폴백
    for domain_key, domain in DOMAIN_REGISTRY.items():
        if category in domain["categories"]:
            return domain_key

    return None


def get_domain_knowledge(domain: str, db_conn, allowed_agents: list = None) -> str:
    """해당 분야의 knowledge_base 지식을 프롬프트용 텍스트로 반환.

    allowed_agents: 허용 source_agent 목록. None이면 전체 허용.
    예) ["consult", "pro"] → fund_biz/fund_indiv 지식 제외
    """
    if not db_conn:
        return ""

    domain_info = DOMAIN_REGISTRY.get(domain, {})
    categories = domain_info.get("categories", [])
    label = domain_info.get("label", "일반")

    try:
        cur = db_conn.cursor()
        # 에이전트 격리 필터 구성
        agent_filter = ""
        agent_params = ()
        if allowed_agents:
            placeholders_a = ",".join(["%s"] * len(allowed_agents))
            agent_filter = f"AND (source_agent IS NULL OR source_agent IN ({placeholders_a}))"
            agent_params = tuple(allowed_agents)

        placeholders = ",".join(["%s"] * len(categories)) if categories else "''"
        cur.execute(f"""
            SELECT id, knowledge_type, content, confidence
            FROM knowledge_base
            WHERE (category IN ({placeholders}) OR category = %s)
              AND confidence >= 0.5
              {agent_filter}
            ORDER BY confidence DESC, use_count DESC
            LIMIT 10
        """, (*categories, label, *agent_params))

        rows = cur.fetchall()
        if not rows:
            return ""

        parts = [f"\n[{label} 전문 지식 — 축적된 학습 데이터]"]
        for r in rows:
            content = r["content"] if isinstance(r["content"], dict) else json.loads(r["content"])
            ktype = r["knowledge_type"]

            if ktype == "faq":
                parts.append(f"• Q: {content.get('question','')} → A: {content.get('answer','')[:300]}")
            elif ktype == "pattern":
                tips = content.get("tips", "")
                if tips:
                    parts.append(f"• 패턴: {tips[:200]}")
            elif ktype == "insight":
                parts.append(f"• 인사이트: {content.get('relationship','')[:200]}")
            elif ktype == "error":
                parts.append(f"• 주의: {content.get('wrong_info','')[:80]} → {content.get('correct_info','')[:150]}")

            # use_count 증가
            try:
                cur.execute("UPDATE knowledge_base SET use_count = use_count + 1 WHERE id = %s", (r["id"],))
            except Exception:
                pass

        db_conn.commit()
        return "\n".join(parts) if len(parts) > 1 else ""

    except Exception as e:
        print(f"[DomainKnowledge] Error: {e}")
        return ""


# ── 분야별 공통 통계 데이터 ──
DOMAIN_STATISTICS = {
    "finance": {
        "evaluation": "신용평가 40%, 사업타당성 30%, 자금소요계획 20%, 상환능력 10%",
        "competition": "청년 정책자금 3~8:1, 소상공인 2~5:1",
        "tip": "정책자금은 융자(상환의무)이며, 보조금(무상)과 다릅니다. 금리 연 2.0~3.5%, 우대금리 적용 시 1.0~2.5%.",
    },
    "startup": {
        "evaluation": "사업모델 35%, 실현가능성 30%, 시장성 20%, 대표역량 15%",
        "competition": "예비창업패키지 8~15:1, 초기창업패키지 20~25% 선정률, TIPS 약 8%",
        "tip": "창업지원은 사업계획서가 핵심. 기술/시장 차별점을 명확히 하고, 팀 역량과 마일스톤을 구체화하세요.",
    },
    "rnd": {
        "evaluation": "사업성 30%, 기술성 30%, 경영능력 20%, 정책부합성 20%",
        "competition": "정부 R&D 평균 3~7:1, 선정률 30~40%",
        "tip": "R&D 과제는 기술 차별성과 사업화 전략이 핵심. 특허/논문 등 기술력 근거 확보 필요.",
    },
    "export": {
        "evaluation": "수출 잠재력 35%, 제품 경쟁력 30%, 추진계획 20%, 기업역량 15%",
        "competition": "수출바우처 5~10:1",
        "tip": "수출지원은 바이어 매칭, 전시회 참가, 인증 취득 등이 주요 지원 내용. 해외 시장조사 결과가 중요.",
    },
    "employment": {
        "evaluation": "고용창출 효과 40%, 기업 안정성 30%, 교육계획 20%, 정책부합 10%",
        "competition": "청년추가고용장려금 2~4:1",
        "tip": "고용지원은 채용 후 유지기간이 핵심. 6개월~1년 고용유지 의무가 일반적.",
    },
}
