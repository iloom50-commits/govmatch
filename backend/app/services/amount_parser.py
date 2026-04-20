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

    # 단일 금액 — 가장 큰 숫자+단위 조합 찾기
    # "최대 3억원", "3억원", "최대 100만원/1인" 등
    candidates = []

    # 한글 단위 포함 숫자 (복합 허용)
    for m in re.finditer(r"([\d,]+(?:\.\d+)?(?:\s*(?:조|억|천만|백만|만|천))+)\s*원?", text):
        val = _parse_numeric_with_unit(m.group(1).replace(" ", ""))
        if val and val > 0:
            candidates.append(val)

    # 원 단위 단순 숫자 (예: "1,000,000원", "500만 원" 같은 거 제외하고 숫자+원만)
    for m in re.finditer(r"([\d,]+)\s*원(?![가-힣])", text):
        val = _parse_numeric_with_unit(m.group(1))
        if val and val > 10000:  # 만원 이상만 의미 있음
            candidates.append(val)

    if candidates:
        max_val = max(candidates)
        return ("numeric", max_val, None)

    # 숫자는 있는데 단위 해석 실패 → text_only 로 분류
    return ("text_only", None, None)
