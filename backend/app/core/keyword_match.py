# -*- coding: utf-8 -*-
"""관심/키워드 매칭 공용 헬퍼 — 토큰화 + 동의어 확장.
matcher.py에서 이관할 SYNONYM_MAP의 단일 진실원. DB·IO 없는 순수 함수."""

# 단어 단위 유의어 확장 맵 (커스텀 입력 키워드 → 유사 표현)
SYNONYM_MAP = {
    "컨설팅":   ["컨설팅", "자문", "경영지도", "경영컨설팅", "진단"],
    "전문가":   ["전문가", "멘토", "전문인력", "자문위원", "코치"],
    "수행기관": ["수행기관", "전문기관", "운영기관", "전담기관", "주관기관", "용역", "위탁", "대행", "수탁기관"],
    "용역기관": ["용역기관", "용역", "수행기관", "위탁", "대행"],
    "인증":     ["인증", "인증서", "ISO", "품질인증", "기술인증", "인정"],
    "특허":     ["특허", "지식재산", "IP", "실용신안", "지재권"],
    "바우처":   ["바우처", "쿠폰", "이용권", "지원권"],
    "사업화":   ["사업화", "상용화", "제품화", "양산", "시제품"],
    "입주":     ["입주", "센터입주", "보육", "인큐베이팅", "창업공간"],
    "해외":     ["해외", "수출", "글로벌", "해외진출", "해외시장"],
    "디자인":   ["디자인", "브랜딩", "패키지디자인", "BI", "CI"],
    "홍보":     ["홍보", "마케팅", "광고", "프로모션", "SNS마케팅"],
    "네트워킹": ["네트워킹", "네트워크", "교류", "매칭", "협업"],
    # 기관族 (신규)
    "전문기관": ["전문기관", "수행기관", "운영기관", "전담기관", "주관기관"],
    "운영기관": ["운영기관", "전문기관", "수행기관", "전담기관", "주관기관"],
    "전담기관": ["전담기관", "전문기관", "수행기관", "운영기관", "주관기관"],
    "주관기관": ["주관기관", "전문기관", "수행기관", "운영기관", "전담기관"],
    # 모집族 (신규)
    "모집": ["모집", "지정", "선정", "공모"],
    "지정": ["지정", "모집", "선정", "공모"],
    "선정": ["선정", "모집", "지정", "공모"],
    "공모": ["공모", "모집", "지정", "선정"],
}


def tokenize(keyword):
    """공백 분리, 빈 토큰 제거."""
    return [t for t in (keyword or "").strip().split() if t]


def expand_token(token):
    """동의어 사전에 있으면 동의어 전체, 없으면 자기 자신만."""
    return SYNONYM_MAP.get(token, [token])


def keyword_hit(keywords, text):
    """파이썬용: 키워드 리스트 중 하나라도(OR) 모든 토큰이(AND) 동의어로(OR) text에 매칭되면 True."""
    if not keywords:
        return False
    low = (text or "").lower()
    for kw in keywords:
        toks = tokenize(kw)
        if not toks:
            continue
        if all(any(syn.lower() in low for syn in expand_token(tok)) for tok in toks):
            return True
    return False


def build_match_sql(keywords, field_expr):
    """SQL용: (field ILIKE ...) 조각 + 파라미터. keyword 간 OR / token 간 AND / 동의어 OR.
    keywords 비면 (None, [])."""
    kws = [kw for kw in (keywords or []) if tokenize(kw)]
    if not kws:
        return None, []
    kw_clauses = []
    params = []
    for kw in kws:
        tok_clauses = []
        for tok in tokenize(kw):
            syns = expand_token(tok)
            tok_clauses.append("(" + " OR ".join([f"{field_expr} ILIKE %s" for _ in syns]) + ")")
            params.extend([f"%{s}%" for s in syns])
        kw_clauses.append("(" + " AND ".join(tok_clauses) + ")")
    return "(" + " OR ".join(kw_clauses) + ")", params
