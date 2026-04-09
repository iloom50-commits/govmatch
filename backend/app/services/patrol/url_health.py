"""URL 헬스체크 — 손상된 origin_url 자동 감지 + 정규화"""
import re
import logging
from typing import Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def normalize_url(url: str, base_domain: str = "https://www.bizinfo.go.kr") -> str:
    """URL 정규화 — 도메인 중복/상대경로/쓰레기 문자 정리"""
    if not url:
        return ""
    url = str(url).strip()

    # 보안: javascript:/data:/file: 차단
    lower = url.lower()
    if lower.startswith(("javascript:", "data:", "file:", "vbscript:")):
        return ""

    # 도메인 중복 제거 (마지막 http(s)://부터)
    matches = list(re.finditer(r'https?://', url))
    if len(matches) >= 2:
        url = url[matches[-1].start():]

    # 상대 경로 → 도메인 prefix
    if url.startswith("/"):
        url = base_domain + url
    elif not url.startswith("http"):
        url = base_domain + "/" + url

    # trailing 공백/탭/줄바꿈
    url = url.split()[0] if url.split() else url

    # 다중 인코딩 디코딩
    if "%25" in url:
        try:
            from urllib.parse import unquote
            url = unquote(url, errors="ignore")
        except Exception:
            pass

    # host 검증
    try:
        parsed = urlparse(url)
        if not parsed.netloc or "." not in parsed.netloc:
            return ""
    except Exception:
        return ""

    return url


def detect_url_issue(url: str) -> str:
    """URL의 문제 유형 감지 (없으면 빈 문자열)"""
    if not url or not str(url).strip():
        return "empty"
    s = str(url).strip()

    if s.lower().startswith(("javascript:", "data:", "file:", "vbscript:")):
        return "unsafe_scheme"
    if len(re.findall(r'https?://', s)) >= 2:
        return "doubled_domain"
    if not s.startswith("http"):
        return "missing_scheme"
    if any(c in s for c in (" ", "\n", "\t")):
        return "whitespace"
    if "%25" in s:
        return "double_encoded"
    try:
        parsed = urlparse(s)
        if not parsed.netloc or "." not in parsed.netloc:
            return "invalid_host"
    except Exception:
        return "parse_error"
    return ""


def scan_and_fix_urls(db_conn) -> Dict[str, Any]:
    """전체 announcements 테이블 URL 스캔 + 자동 수정

    Returns: {scanned, issues_found, fixed, unfixable, by_type}
    """
    cur = db_conn.cursor()

    # 후보 가져오기 — 손상 가능성 있는 URL 패턴
    cur.execute("""
        SELECT announcement_id, origin_url
        FROM announcements
        WHERE origin_url IS NOT NULL
          AND (origin_url ~ 'https?://.*https?://'
               OR origin_url ~ '\\s'
               OR origin_url LIKE '%%25%%'
               OR origin_url NOT LIKE 'http%%')
    """)
    rows = cur.fetchall()

    by_type: Dict[str, int] = {}
    fixed = 0
    unfixable = 0
    unfixable_ids = []

    for row in rows:
        aid = row["announcement_id"]
        original = row["origin_url"]
        issue = detect_url_issue(original)
        if not issue:
            continue
        by_type[issue] = by_type.get(issue, 0) + 1

        cleaned = normalize_url(original)
        if cleaned and cleaned != original:
            try:
                cur.execute(
                    "UPDATE announcements SET origin_url = %s WHERE announcement_id = %s",
                    (cleaned, aid)
                )
                fixed += 1
            except Exception as e:
                logger.error(f"[URL Patrol] update failed for #{aid}: {e}")
                db_conn.rollback()
                unfixable += 1
                unfixable_ids.append(aid)
        elif not cleaned:
            unfixable += 1
            unfixable_ids.append(aid)

    db_conn.commit()

    return {
        "scanned": len(rows),
        "issues_found": sum(by_type.values()),
        "fixed": fixed,
        "unfixable": unfixable,
        "by_type": by_type,
        "unfixable_ids_sample": unfixable_ids[:20],
    }


def deactivate_unfixable(db_conn, max_count: int = 50) -> int:
    """수정 불가능한 URL은 announcement에 표시 (origin_url을 NULL로 설정)
    너무 많이 한 번에 비활성화하지 않도록 max_count 제한
    """
    cur = db_conn.cursor()
    deactivated = 0
    cur.execute("""
        SELECT announcement_id, origin_url FROM announcements
        WHERE origin_url IS NOT NULL
          AND (origin_url LIKE 'javascript:%%' OR origin_url LIKE 'data:%%' OR origin_url LIKE 'file:%%')
        LIMIT %s
    """, (max_count,))
    rows = cur.fetchall()
    for row in rows:
        try:
            cur.execute(
                "UPDATE announcements SET origin_url = NULL WHERE announcement_id = %s",
                (row["announcement_id"],)
            )
            deactivated += 1
        except Exception:
            db_conn.rollback()
    db_conn.commit()
    return deactivated
