"""공고 본문(full_text)에서 마감일 정보를 추출하는 순수 유틸리티.

데이터 파이프라인 레벨에서 announcements.deadline_date / deadline_type 를 보강하는 데 사용.
DB·AI 의존이 없어 단위 테스트가 가능하다.

반환 (deadline_type, deadline_date_iso):
  ('날짜', 'YYYY-MM-DD')  본문에서 접수마감일 추출
  ('상시', None)          상시/연중 서비스 (마감일 없음)
  ('미상', None)          판단 불가 → 호출측에서 '원문 확인'으로 정직 표시
"""

import re
from datetime import date
from typing import Optional, Tuple

# 접수마감 라벨 (사업기간/지원기간 등 '운영 기간'은 제외 — 신청 마감과 다름)
_LABEL = r"(?:접수|신청|모집|공모|제출|등록|참가\s*신청)\s*(?:기간|기한|마감|일정|일자)"
# 날짜: 2026.6.22 / 2026-06-22 / 2026년 6월 22(일)
_DATE = r"(20[0-9]{2})\s*[.\-년/]\s*([0-9]{1,2})\s*[.\-월/]\s*([0-9]{1,2})"

_RANGE = re.compile(_LABEL + r"\s*[:：]?\s*" + _DATE + r"[^0-9]{1,8}" + _DATE)
_SINGLE = re.compile(_LABEL + r"\s*[:：]?\s*(?:~|부터|까지)?\s*" + _DATE)
_UNTIL = re.compile(r"(?:~|부터)\s*" + _DATE + r"\s*까지")

_SANGSI = re.compile(
    r"상시\s*(?:모집|접수|운영)?"
    r"|연중\s*(?:상시|수시|모집|접수)?"
    r"|수시\s*(?:접수|모집)"
    r"|예산\s*소진\s*시?\s*(?:까지|마감)?"
    r"|소진\s*시\s*까지"
    r"|기간\s*내\s*수시"
)

# 정부24 서비스 템플릿 (접수기간 항목이 없는 상시 운영 민원서비스)
_GOV24_TEMPLATE = re.compile(r"\[지원대상\][\s\S]*\[(?:문의처|신청방법)\]")


def _mk_date(y, m, d) -> Optional[str]:
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except (ValueError, TypeError):
        return None


def enrich_deadline(full_text: Optional[str]) -> Tuple[str, Optional[str]]:
    if not full_text:
        return ("unknown", None)
    t = re.sub(r"<[^>]+>", " ", full_text)
    t = re.sub(r"\s+", " ", t)

    # 1) 접수기간 범위 → 종료일(마감)
    m = _RANGE.search(t)
    if m:
        end = _mk_date(m.group(4), m.group(5), m.group(6))
        if end:
            return ("fixed", end)
    # 2) "~DATE 까지"
    m = _UNTIL.search(t)
    if m:
        d = _mk_date(m.group(1), m.group(2), m.group(3))
        if d:
            return ("fixed", d)
    # 3) 라벨 + 단일 날짜
    m = _SINGLE.search(t)
    if m:
        d = _mk_date(m.group(1), m.group(2), m.group(3))
        if d:
            return ("fixed", d)
    # 4) 상시 마커
    if _SANGSI.search(t):
        return ("ongoing", None)
    # 5) 정부24 서비스 템플릿 = 상시 운영 민원서비스
    if _GOV24_TEMPLATE.search(t):
        return ("ongoing", None)
    return ("unknown", None)
