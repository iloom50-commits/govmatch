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


# ── 수집단 중앙 마감 파서 (P2-2) ──
# 상시/무기한 키워드 — 기존 3벌의 합집합(enricher _SANGSI + sync _ongoing_patterns
# + public_api always_open_kw). 전부 이미 프로덕션 ongoing 판정에 쓰이던 것이라 통합=무회귀.
_ONGOING_RE = re.compile(
    r"상시|연중|수시"
    r"|예산\s*소진|소진\s*시"
    r"|마감일?\s*없|마감일?\s*미정|기간\s*없"
    r"|해당\s*시|매월|매년|사유\s*발생"
)
# 완전 날짜(연도 포함): YYYYMMDD / YYYY[.-/]M[.-/]D (공백 혼입 허용)
_YMD8_RE = re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")
_YMD_SEP_RE = re.compile(r"(20\d{2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})")


def _extract_full_date(seg: Optional[str]) -> Optional[str]:
    """세그먼트에서 '연도 포함' 완전 날짜 1개를 ISO로. 연도 없으면 None(날조 금지)."""
    if not seg:
        return None
    s = str(seg)
    m = _YMD8_RE.search(s)
    if m:
        d = _mk_date(m.group(1), m.group(2), m.group(3))
        if d:
            return d
    m = _YMD_SEP_RE.search(s)
    if m:
        return _mk_date(m.group(1), m.group(2), m.group(3))
    return None


def parse_deadline(raw) -> Tuple[Optional[str], str, Optional[str]]:
    """수집 마감 원문 → (date_iso|None, deadline_type, raw_text|None).

    수집단 단일 파서(중앙화). 파서는 원본 마감 필드를 그대로 넘기고, 날짜 정규화·상시
    판정·원문 보존을 여기서 일괄 수행 → 파서가 무엇을 흘려도 관문이 잡는다.
    - deadline_type: 'fixed'(유효 종료일) / 'ongoing'(상시·무기한) / 'unknown'
    - raw_text: strip한 원문 앞 200자. 빈값이면 None(= 진짜 부재의 측정 신호).
    - 연도 없는 날짜는 만들지 않는다(unknown + raw 보존). expired 전환은 호출측 책임.
    """
    if raw is None:
        return (None, "unknown", None)
    s = str(raw).strip()
    if not s:
        return (None, "unknown", None)
    raw_text = s[:200]

    # 무기한 관례값(99991231)은 날짜로 오인 전에 먼저 ongoing 처리
    if re.sub(r"\D", "", s) == "99991231":
        return (None, "ongoing", raw_text)

    if "~" in s:
        # '~' 기간: 마지막 '~' 뒤(종료)에서 완전 날짜 추출
        head, tail = s.rsplit("~", 1)
        end_date = _extract_full_date(tail)
        if end_date:
            start_date = _extract_full_date(head)
            if start_date and end_date < start_date:
                return (None, "unknown", raw_text)  # 역전 범위(이상) → 미상
            return (end_date, "fixed", raw_text)
    else:
        d = _extract_full_date(s)
        if d:
            return (d, "fixed", raw_text)

    # 완전 종료일 없음 → 상시 키워드면 ongoing, 아니면 미상(원문 보존)
    if _ONGOING_RE.search(s):
        return (None, "ongoing", raw_text)
    return (None, "unknown", raw_text)


def enrich_pending_deadlines(db_conn, limit: int = 1000) -> dict:
    """NULL 마감일 공고를 full_text로 보강 (파이프라인 단계용).

    - deadline_date: NULL인 것만 채움(추가). deadline_type: 'unknown'/NULL만 교정.
    - 매처 필터에 deadline_type을 안 쓰므로 교정은 무해.
    Returns: {"scanned","fixed","ongoing","unknown"}
    """
    cur = db_conn.cursor()
    # 미검사(NULL) 또는 7일 지난 것만 스캔 — 같은 원문 반복 재스캔(낭비) 방지.
    # 미검사·오래된 것 우선(NULLS FIRST) — 최신순 기아(오래된 NULL 영영 미처리) 해소.
    cur.execute(
        """SELECT a.announcement_id AS id, aa.full_text AS ft
           FROM announcements a
           JOIN announcement_analysis aa ON aa.announcement_id = a.announcement_id
           WHERE a.is_archived = FALSE AND a.deadline_date IS NULL
             AND LENGTH(aa.full_text) > 120
             AND (a.deadline_type IS NULL OR a.deadline_type = 'unknown')
             AND (a.deadline_checked_at IS NULL
                  OR a.deadline_checked_at < CURRENT_TIMESTAMP - INTERVAL '7 days')
           ORDER BY a.deadline_checked_at ASC NULLS FIRST, a.created_at ASC
           LIMIT %s""",
        (limit,),
    )
    rows = cur.fetchall()
    fixed = ongoing = unknown = 0
    for r in rows:
        aid = r["id"] if isinstance(r, dict) else r[0]
        ft = r["ft"] if isinstance(r, dict) else r[1]
        typ, dval = enrich_deadline(ft)
        if typ == "fixed" and dval:
            cur.execute(
                "UPDATE announcements SET deadline_date=%s, deadline_type='fixed', deadline_checked_at=CURRENT_TIMESTAMP WHERE announcement_id=%s AND deadline_date IS NULL",
                (dval, aid),
            )
            fixed += 1
        elif typ == "ongoing":
            cur.execute(
                "UPDATE announcements SET deadline_type='ongoing', deadline_checked_at=CURRENT_TIMESTAMP WHERE announcement_id=%s",
                (aid,),
            )
            ongoing += 1
        else:
            # 파싱 실패(원문에 마감 단서 없음) — checked만 마킹해 재스캔 낭비·기아 차단
            cur.execute(
                "UPDATE announcements SET deadline_checked_at=CURRENT_TIMESTAMP WHERE announcement_id=%s",
                (aid,),
            )
            unknown += 1
    db_conn.commit()
    return {"scanned": len(rows), "fixed": fixed, "ongoing": ongoing, "unknown": unknown}
