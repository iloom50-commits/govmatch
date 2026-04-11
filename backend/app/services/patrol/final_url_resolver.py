"""최종 원본 URL 수집기 — 중간 경유지를 따라가 최종 공고 페이지 URL을 확보

gov.kr → bizinfo → kosmes 같은 다단계 리다이렉트를 따라가서
사용자가 클릭 시 1번에 원본에 도착하도록 final_url을 DB에 저장한다.
"""

import re
import requests
from typing import Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 경유지 도메인 (이 도메인이면 바로가기를 더 따라감)
_RELAY_DOMAINS = ["gov.kr", "bizinfo.go.kr", "smes24.go.kr"]

# 원본 도메인 (여기 도착하면 최종)
_FINAL_DOMAINS = [
    "kosmes.or.kr", "sbiz.or.kr", "ccei.creativekorea.or.kr",
    "kised.or.kr", "kibo.or.kr", "kodit.co.kr",
    "k-startup.go.kr", "mss.go.kr", "smba.go.kr",
]

_REDIRECT_PATTERNS = ["바로가기", "원문보기", "원문 바로가기", "홈페이지 바로가기",
                       "상세보기", "신청 바로가기", "출처 바로가기"]


def resolve_final_url(origin_url: str, max_depth: int = 3) -> Optional[str]:
    """origin_url에서 최종 원본 URL을 찾아 반환

    Args:
        origin_url: DB에 저장된 origin_url
        max_depth: 최대 따라가기 깊이

    Returns:
        최종 URL (찾지 못하면 None)
    """
    if not origin_url:
        return None

    # 이미 원본 도메인이면 그대로
    parsed = urlparse(origin_url)
    if any(d in parsed.netloc for d in _FINAL_DOMAINS):
        return origin_url

    # 경유지가 아니면 그대로
    if not any(d in parsed.netloc for d in _RELAY_DOMAINS):
        return None  # 알 수 없는 도메인 → 변경 안 함

    current_url = origin_url
    visited = {origin_url}

    for depth in range(max_depth):
        next_url = _find_redirect_url(current_url)
        if not next_url or next_url in visited:
            break

        visited.add(next_url)
        print(f"[FinalURL] depth={depth+1}: {current_url[:50]} → {next_url[:80]}")

        # 원본 도메인 도착?
        next_parsed = urlparse(next_url)
        if any(d in next_parsed.netloc for d in _FINAL_DOMAINS):
            return next_url

        # 경유지가 아닌 외부 도메인이면 최종으로 간주
        if not any(d in next_parsed.netloc for d in _RELAY_DOMAINS):
            return next_url

        current_url = next_url

    # 끝까지 못 찾으면 마지막 도달 URL (origin과 다르면)
    if current_url != origin_url:
        return current_url

    return None


def _find_redirect_url(page_url: str) -> Optional[str]:
    """페이지에서 바로가기/원문보기 링크를 찾아 URL 반환"""
    try:
        resp = requests.get(page_url, headers=_HEADERS, timeout=12, allow_redirects=True)
        resp.encoding = "utf-8"

        # HTTP 리다이렉트가 발생했으면
        if resp.url != page_url and urlparse(resp.url).netloc != urlparse(page_url).netloc:
            return resp.url

        soup = BeautifulSoup(resp.text, "html.parser")
        base_url = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"

        # 1. 바로가기 텍스트 링크
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"].strip()

            if any(p in text for p in _REDIRECT_PATTERNS):
                # javascript:onclick 처리
                if href.startswith("javascript:"):
                    onclick = a.get("onclick", "")
                    m = re.search(r"['\"]((https?://[^'\"]+))['\"]", onclick)
                    if m:
                        href = m.group(1)
                    else:
                        continue

                full_url = href if href.startswith("http") else (base_url + href if href.startswith("/") else href)
                # 같은 사이트 내부 링크 제외
                if urlparse(full_url).netloc != urlparse(page_url).netloc:
                    return full_url

        # 2. 본문에서 원본 기관 URL 패턴 매칭
        org_urls = re.findall(
            r'https?://(?:www\.)?(?:kosmes|kised|kibo|kodit|k-startup|sbiz|ccei\.creativekorea)[^\s\'\"\<\>]+',
            resp.text
        )
        for ou in org_urls:
            ou = ou.rstrip("',\")")
            if len(ou) > 25:
                return ou

    except Exception as e:
        print(f"[FinalURL] Error fetching {page_url[:60]}: {e}")

    return None


def resolve_priority_announcements(db_conn, limit: int = 50) -> dict:
    """우선순위 공고의 final_url 수집

    대상:
    - 인기 카테고리 (정책자금/창업/R&D 등)
    - 마감일 남은 공고
    - 경유지 도메인(gov.kr/bizinfo)인 공고
    - final_url이 아직 비어있는 공고
    """
    cur = db_conn.cursor()
    cur.execute("""
        SELECT announcement_id, origin_url, title
        FROM announcements
        WHERE origin_url IS NOT NULL AND origin_url != ''
          AND (final_url IS NULL OR final_url = '')
          AND (
              title ILIKE '%%정책자금%%' OR title ILIKE '%%융자%%' OR title ILIKE '%%보증%%'
              OR title ILIKE '%%창업%%' OR title ILIKE '%%R&D%%' OR title ILIKE '%%기술개발%%'
              OR title ILIKE '%%수출%%' OR title ILIKE '%%고용%%' OR title ILIKE '%%청년%%'
              OR title ILIKE '%%주거%%' OR title ILIKE '%%장학%%' OR title ILIKE '%%복지%%'
              OR category IN ('금융', '창업', '기술', '고용', '수출', '복지', '주거', '교육')
          )
          AND (deadline_date IS NULL OR deadline_date >= CURRENT_DATE)
        ORDER BY
            CASE WHEN origin_url LIKE '%%gov.kr%%' THEN 0
                 WHEN origin_url LIKE '%%bizinfo%%' THEN 1
                 WHEN origin_url LIKE '%%smes24%%' THEN 2
                 ELSE 3 END,
            created_at DESC
        LIMIT %s
    """, (limit,))

    rows = cur.fetchall()
    resolved = 0
    failed = 0

    for row in rows:
        aid = row["announcement_id"]
        origin = row["origin_url"]
        try:
            final = resolve_final_url(origin)
            if final and final != origin:
                cur.execute(
                    "UPDATE announcements SET final_url = %s WHERE announcement_id = %s",
                    (final, aid)
                )
                resolved += 1
                print(f"[FinalURL] #{aid} {row['title'][:30]} → {final[:60]}")
            else:
                # 경유지가 아니거나 이미 최종 → origin 그대로 저장
                cur.execute(
                    "UPDATE announcements SET final_url = %s WHERE announcement_id = %s",
                    (origin, aid)
                )
        except Exception as e:
            failed += 1
            print(f"[FinalURL] #{aid} error: {e}")

    db_conn.commit()
    return {"total": len(rows), "resolved": resolved, "failed": failed}
