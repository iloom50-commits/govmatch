"""[Phase 1~3 보강] 지원금액 정규화 유틸리티.

수집/분석 파이프라인 양쪽에서 공용으로 사용.
- 한글 단위 혼합 문자열(예: "최대 3억원", "1억~5억원") → 원(KRW) 단위 int
- 금액 유형 판정 (numeric / text_only / not_specified / unknown)
"""

import re
from typing import Optional, Tuple


# 한글 단위 → 배수 (원 단위 기준)
_UNIT_MAP = {
    "조": 10 ** 12,
    "억": 10 ** 8,
    "천만": 10 ** 7,
    "백만": 10 ** 6,
    "만": 10 ** 4,
    "천": 10 ** 3,
}

# "지정되지 않음" 패턴 (숫자 없는 텍스트만 있을 때)
_NOT_SPECIFIED_PATTERNS = (
    "별첨", "별도 공고", "공고문 참조", "세부사업", "세부사업별", "사업별", "미정",
    "사업 공고 참조", "공고 참조", "별도 안내", "추후 공지", "협의",
)

# 콤마 + 숫자 (예: "1,000,000")
_NUMBER_COMMA = re.compile(r"([\d,]+(?:\.\d+)?)")

# 신청자별 지원금이 아닌 맥락 — 이 키워드가 숫자 근처면 제외
# (직접투자·후속투자, 대출/융자 한도, 펀드 운용규모, 사업 총예산, 미확정 '예정' 등)
_AMOUNT_EXCLUDE_CTX = (
    "투자", "대출", "융자", "출자", "펀드", "예정", "연계",
    "운용", "사업비", "예산", "매출", "보증", "기금", "총사업", "출연금 규모",
)
# 신청자 1건(기업/과제/팀/개인) 단위 지원 신호 — 있으면 우선 채택
_PER_APPLICANT_CTX = (
    "기업당", "사업자당", "1개사", "개사", "과제당", "과제별", "1과제",
    "1인당", "인당", "팀별", "팀당", "1건당", "건당", "1개 기업",
)


def _parse_numeric_with_unit(text: str) -> Optional[int]:
    """단일 숫자 + 한글 단위를 원 단위로 변환.

    예: "3억원" → 300,000,000
        "5천만원" → 50,000,000
        "1억 5천만" → 150,000,000 (복합)
        "1,000,000원" → 1,000,000
    """
    if not text:
        return None

    # 공백 제거 후 "원" 제거
    s = text.replace(" ", "").replace("원", "")

    # 순수 숫자만
    pure = re.fullmatch(r"([\d,]+)", s)
    if pure:
        try:
            return int(pure.group(1).replace(",", ""))
        except Exception:
            return None

    # 복합 단위 파싱: "1억5천만", "3억5000만" 등
    total = 0
    pos = 0
    matched = False
    # "조" → "억" → "천만" → "백만" → "만" → "천" 순서로 스캔
    for unit in ("조", "억", "천만", "백만", "만", "천"):
        # 이 단위가 남은 문자열에 나오는 경우
        ulen = len(unit)
        idx = s.find(unit, pos)
        if idx < 0:
            continue
        # 단위 앞의 숫자 부분
        num_str = s[pos:idx].replace(",", "")
        if not num_str:
            # 숫자 없이 단위만 (예: "억" 단독) — 건너뜀
            pos = idx + ulen
            continue
        try:
            num_val = float(num_str)
            total += int(num_val * _UNIT_MAP[unit])
            matched = True
            pos = idx + ulen
        except Exception:
            return None

    # 남은 뒷부분 (단위 없는 숫자)
    remain = s[pos:].replace(",", "")
    if remain:
        # 남은 부분이 숫자면 더함 (단위 없이)
        tail = re.match(r"(\d+)", remain)
        if tail:
            try:
                total += int(tail.group(1))
                matched = True
            except Exception:
                pass

    return total if matched and total > 0 else None


def parse_support_amount(raw: Optional[str]) -> Tuple[str, Optional[int], Optional[int]]:
    """공고의 지원금액 문자열을 정규화.

    Returns:
        (support_amount_type, max_krw, min_krw)
        - type: 'numeric' | 'text_only' | 'not_specified' | 'unknown'
        - max_krw / min_krw: 원 단위 정수 또는 None

    예시:
        "최대 3억원"       → ('numeric', 300000000, None)
        "1억~5억원"        → ('numeric', 500000000, 100000000)
        "최대 100만원/1인" → ('numeric', 1000000, None)
        "별첨 참조"        → ('not_specified', None, None)
        ""                 → ('unknown', None, None)
        "세부사업별 상이"  → ('not_specified', None, None)
    """
    if not raw or not str(raw).strip():
        return ("unknown", None, None)

    text = str(raw).strip()

    # "지정되지 않음" 패턴 감지 (숫자 있어도 의미 없음)
    lower = text
    if any(p in lower for p in _NOT_SPECIFIED_PATTERNS):
        # 단, 구체적 금액이 함께 있으면 numeric 시도
        if not re.search(r"\d", text):
            return ("not_specified", None, None)

    # 숫자가 없으면 text_only
    if not re.search(r"\d", text):
        return ("text_only", None, None)

    # 대출/융자 전용 공고 — 금액은 '대출 한도'이지 지원금이 아니므로 미산정 (오표시 방지)
    if any(k in text for k in ("대출", "융자")) and not any(
        k in text for k in ("지원금", "보조금", "지급", "장려금", "출연", "보조")
    ):
        return ("text_only", None, None)

    # 범위 표기 감지: "A~B", "A-B", "A부터 B까지" (주의: 2026-01 같은 날짜 패턴 제외)
    # 단위가 포함된 숫자 + ~ + 단위가 포함된 숫자
    range_patterns = [
        r"([\d,]+(?:\.\d+)?\s*(?:조|억|천만|백만|만|천)?\s*원?)\s*[~\-]\s*([\d,]+(?:\.\d+)?\s*(?:조|억|천만|백만|만|천)?\s*원?)",
    ]
    for pat in range_patterns:
        m = re.search(pat, text)
        if m:
            a = _parse_numeric_with_unit(m.group(1))
            b = _parse_numeric_with_unit(m.group(2))
            if a and b:
                mn, mx = sorted([a, b])
                if mx > 0:
                    return ("numeric", mx, mn)

    # 단일 금액 — 신청자별 지원금 후보만 수집 (투자/대출/총예산 맥락은 제외)
    def _ctx(m):
        return text[max(0, m.start() - 16): m.end() + 8]

    candidates = []  # (value, is_per_applicant)

    # 한글 단위 포함 숫자 (복합 허용)
    for m in re.finditer(r"([\d,]+(?:\.\d+)?(?:\s*(?:조|억|천만|백만|만|천))+)\s*원?", text):
        val = _parse_numeric_with_unit(m.group(1).replace(" ", ""))
        if not (val and val > 0):
            continue
        c = _ctx(m)
        if any(k in c for k in _AMOUNT_EXCLUDE_CTX):
            continue  # 투자·대출·총예산 등 — 신청자 지원금 아님
        candidates.append((val, any(k in c for k in _PER_APPLICANT_CTX)))

    # 원 단위 단순 숫자 (만원 이상만)
    for m in re.finditer(r"([\d,]+)\s*원(?![가-힣])", text):
        val = _parse_numeric_with_unit(m.group(1))
        if not (val and val > 10000):
            continue
        c = _ctx(m)
        if any(k in c for k in _AMOUNT_EXCLUDE_CTX):
            continue
        candidates.append((val, any(k in c for k in _PER_APPLICANT_CTX)))

    if candidates:
        # 신청자별(기업당·과제당 등) 신호가 있으면 그 중 최대, 없으면 전체 최대
        per_vals = [v for v, p in candidates if p]
        chosen = max(per_vals) if per_vals else max(v for v, _ in candidates)
        return ("numeric", chosen, None)

    # 숫자는 있으나 모두 제외(투자/대출 등)되거나 단위 해석 실패 → text_only
    return ("text_only", None, None)


def won_to_baekman(v) -> str:
    """원 단위 정수 → '백만원' 단위 표기. 1백만원 미만은 원 그대로."""
    try:
        v = int(v)
    except Exception:
        return ""
    if v <= 0:
        return ""
    man = v / 1_000_000
    if man >= 1:
        return (f"{man:,.0f}백만원" if abs(man - round(man)) < 1e-9 else f"{man:,.1f}백만원")
    return f"{v:,}원"


# 한글단위 금액 토큰 (5억원 / 300만원 / 20억 / 2.5억 / 3천만원 / 1억5천만원 등)
_KR_AMT_TOKEN = re.compile(
    r'\d[\d,\.]*\s*(?:조|억|천만|백만|천|만)(?:\s*\d[\d,]*\s*(?:천만|백만|천|만))*\s*원?'
)


def normalize_amount_text(text) -> str:
    """금액 문자열 내 인식 가능한 금액 토큰을 '백만원' 단위로 통일.

    - 'N KRW' / 'N,NNN KRW' → 백만원
    - 순수숫자+'원'(큰 숫자) → 백만원
    - 한글단위(억/만/천만 등) → 백만원
    값 해석 실패 토큰은 원문 유지(무왜곡). 주변 텍스트(최대/총/내외 등)는 보존.
    """
    s = str(text or "")
    if not s:
        return s
    # 1) 'N KRW'
    s = re.sub(r'([\d,]{4,})\s*KRW',
               lambda m: won_to_baekman(int(m.group(1).replace(',', ''))) or m.group(0), s)
    # 2) 순수숫자 + '원' (한글단위 없는 큰 숫자, 4자리 이상)
    s = re.sub(r'(?<![\d가-힣.])([\d,]{4,})\s*원',
               lambda m: won_to_baekman(int(m.group(1).replace(',', ''))) or m.group(0), s)
    # 2.5) 'N천M백만'(천·백이 만의 하위단위, 예 3천6백만=3,600만) — 일반 파서가 못 읽는 케이스
    s = re.sub(r'(\d+)\s*천\s*(\d+)\s*백\s*만\s*원?',
               lambda m: won_to_baekman((int(m.group(1)) * 1000 + int(m.group(2)) * 100) * 10000), s)
    # 3) 한글단위 금액
    def _kr(m):
        v = _parse_numeric_with_unit(m.group(0).replace('원', '').replace(' ', ''))
        return won_to_baekman(v) if v else m.group(0)
    s = _KR_AMT_TOKEN.sub(_kr, s)
    return s
