# -*- coding: utf-8 -*-
"""구 카테고리 → 칩 분류(신 택소노미) 결정적 정규화.

배경(2026-07-05 탭 필터 진단): 칩 필터는 category 정확일치인데 유효 공고의 33%가
구분류('창업지원', 'R&D', 'Entrepreneurship' 등)라 어떤 칩에도 노출되지 않음.
원칙: 의미가 확실한 구분류만 매핑, 애매한 값(대상명·부서명·'기타' 등)과 NULL은 유지.

- normalize_category(): 순수 매핑 (None = 변경 없음)
- normalize_all_categories(): 일괄 UPDATE 배치 (일일 파이프라인에서 신규 유입분 자동 편입)
"""
from typing import Optional

# 기업 칩: 자금·지원 / 기술·개발 / 수출·판로 / 인력·교육 / 창업·스케일업 / 경영·법률
_BIZ_MAP = {
    "창업지원": "창업·스케일업", "창업": "창업·스케일업",
    "Entrepreneurship": "창업·스케일업", "Startup": "창업·스케일업",
    "기술": "기술·개발", "기술개발": "기술·개발", "R&D": "기술·개발",
    "Tech": "기술·개발", "ICT": "기술·개발", "디지털전환": "기술·개발",
    "수출": "수출·판로", "수출마케팅": "수출·판로", "Global": "수출·판로",
    "내수": "수출·판로", "판로": "수출·판로", "판로개척": "수출·판로", "마케팅": "수출·판로",
    "정책자금": "자금·지원", "금융": "자금·지원", "대출정보": "자금·지원",
    "자금": "자금·지원", "융자": "자금·지원",
    "경영": "경영·법률", "경영지원": "경영·법률", "법률": "경영·법률",
    "Business Support": "경영·법률", "SME Support": "경영·법률",
    "Small Business Support": "경영·법률",
    "인력": "인력·교육", "인력양성": "인력·교육", "직업훈련": "인력·교육",
    "고용지원": "인력·교육", "교육훈련": "인력·교육", "Education": "인력·교육",
}

# 개인 칩: 복지 / 의료 / 교육 / 주거 / 출산 / 자금·지원
_IND_MAP = {
    "금융": "자금·지원", "정책자금": "자금·지원", "자금": "자금·지원",
    "장애": "복지", "노인": "복지", "저소득": "복지", "생활안정": "복지",
    "육아": "출산", "보육": "출산",
    "장학금": "교육", "직업훈련": "교육",
}


def normalize_category(category, target_type) -> Optional[str]:
    """구분류를 칩 분류로 매핑. 변경 불필요/불가하면 None."""
    if not category:
        return None
    cat = str(category).strip()
    if not cat:
        return None
    tt = (target_type or "business").strip().lower() or "business"
    mapping = _IND_MAP if tt == "individual" else _BIZ_MAP
    new = mapping.get(cat)
    return new if new and new != cat else None


def normalize_all_categories(db_conn) -> dict:
    """구분류 전량 일괄 정규화 (아카이브 포함 — 재활성 대비 일관성).

    Returns: {"updated": 총건수, "by_rule": {(old, tt그룹): 건수}}
    """
    cur = db_conn.cursor()
    updated = 0
    by_rule = {}
    # 기업/미지정/both → BIZ_MAP
    for old, new in _BIZ_MAP.items():
        cur.execute(
            """UPDATE announcements SET category = %s
               WHERE category = %s
                 AND (target_type IS NULL OR target_type IN ('business', 'both'))""",
            (new, old))
        if cur.rowcount:
            by_rule[(old, "biz")] = cur.rowcount
            updated += cur.rowcount
    # 개인 → IND_MAP
    for old, new in _IND_MAP.items():
        cur.execute(
            """UPDATE announcements SET category = %s
               WHERE category = %s AND target_type = 'individual'""",
            (new, old))
        if cur.rowcount:
            by_rule[(old, "ind")] = cur.rowcount
            updated += cur.rowcount
    db_conn.commit()
    return {"updated": updated, "by_rule": by_rule}
