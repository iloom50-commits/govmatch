"""K-Startup 공고 제목 재정비

문제:
  - 기존 스크래퍼가 <a> 전체 텍스트를 저장 →
    "카테고리 D-N 마감일자 날짜 실제제목 실제제목(반복) 기관명 조회N" 형태
  - 새 스크래퍼는 <p class="tit"> 만 추출하므로 신규는 정상

수정:
  1. K-Startup 리스팅 페이지에서 현재 공고 재스크랩
  2. pbancSn으로 DB 기존 항목과 매칭 → 제목 교체
  3. 리스팅에 없는 기존 항목은 간단한 중복 제거 로직으로 정리
"""
import html as html_lib
import os
import re
import sys
import time

# Windows 터미널 인코딩 강제 UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import psycopg2
import requests

# ── DB 연결 ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── 스크래퍼 상수 ──────────────────────────────────────────────────────────────
_BASE = "https://www.k-startup.go.kr"
_LIST = f"{_BASE}/web/contents/bizpbanc-ongoing.do?schPageSize=10&page={{page}}"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}
_BLOCK_RE = re.compile(r"go_view\((\d+)\).*?</a>", re.DOTALL)
_TIT_RE = re.compile(r'<p[^>]+class="tit"[^>]*>(.*?)</p>', re.DOTALL)


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _clean(raw: str) -> str:
    return re.sub(r"\s+", " ", _strip_tags(raw)).strip()


def scrape_fresh_titles(max_pages: int = 15) -> dict[str, str]:
    """K-Startup 리스팅에서 {pbancSn: 제목} 매핑 수집"""
    result: dict[str, str] = {}
    for page in range(1, max_pages + 1):
        try:
            resp = requests.get(_LIST.format(page=page), headers=_HEADERS, timeout=20)
            resp.raise_for_status()
            page_html = resp.text
        except Exception as e:
            print(f"  페이지 {page} 오류: {e}")
            break

        found = False
        for m in _BLOCK_RE.finditer(page_html):
            sn = m.group(1)
            if sn in result:
                continue
            block = m.group(0)
            tit_m = _TIT_RE.search(block)
            if not tit_m:
                continue
            title = html_lib.unescape(_clean(tit_m.group(1)))
            if title:
                result[sn] = title
                found = True

        print(f"  페이지 {page}: {len([k for k in result])}건 누적")
        if not found:
            break
        time.sleep(0.3)

    return result


# ── 리스팅에 없는 기존 항목: 중복 텍스트 제거 ──────────────────────────────────
_JUNK_SUFFIX_RE = re.compile(r"\s+조회\s+\d+.*$")


def deduplicate_title(title: str) -> str:
    """제목 중복 패턴 제거: 'X X 기관 조회N' → 'X'"""
    # 1. 후미 "조회 N ..." 제거
    title = _JUNK_SUFFIX_RE.sub("", title).strip()
    # 2. 중복 prefix 탐지: 앞부분 i글자가 뒤에 다시 나타나면 앞부분만 유지
    n = len(title)
    for i in range(max(5, n // 4), n // 2 + 1):
        prefix = title[:i]
        rest = title[i:].lstrip()
        if rest.startswith(prefix[:min(15, len(prefix))]):
            return prefix.rstrip()
    return title


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # K-Startup 전체 DB 항목 조회
    cur.execute("""
        SELECT announcement_id, title, origin_url
        FROM announcements
        WHERE origin_url LIKE '%%k-startup.go.kr%%'
        ORDER BY announcement_id
    """)
    rows = cur.fetchall()
    print(f"K-Startup DB 항목: {len(rows)}건")

    # pbancSn 추출
    sn_to_row: dict[str, tuple] = {}
    for ann_id, title, url in rows:
        m = re.search(r"pbancSn=(\d+)", url or "")
        if m:
            sn_to_row[m.group(1)] = (ann_id, title)

    # 리스팅 재스크랩
    print("\nK-Startup 리스팅 재스크랩 중...")
    fresh = scrape_fresh_titles(max_pages=15)
    print(f"신선 제목 수집: {len(fresh)}건\n")

    updated = 0

    # 1. 리스팅에서 가져온 신선 제목으로 교체
    for sn, new_title in fresh.items():
        if sn not in sn_to_row:
            continue
        ann_id, old_title = sn_to_row[sn]
        if new_title != old_title:
            cur.execute(
                "UPDATE announcements SET title = %s WHERE announcement_id = %s",
                (new_title[:400], ann_id),
            )
            print(f"  [재스크랩] [{ann_id}]\n    전: {old_title[:70]!r}\n    후: {new_title[:70]!r}")
            updated += 1

    # 2. 리스팅에 없는 항목 (만료·비게재) → 중복 제거 로직으로 정리
    fresh_sns = set(fresh.keys())
    for sn, (ann_id, old_title) in sn_to_row.items():
        if sn in fresh_sns:
            continue
        new_title = html_lib.unescape(deduplicate_title(old_title))
        if new_title != old_title:
            cur.execute(
                "UPDATE announcements SET title = %s WHERE announcement_id = %s",
                (new_title[:400], ann_id),
            )
            print(f"  [중복제거] [{ann_id}]\n    전: {old_title[:70]!r}\n    후: {new_title[:70]!r}")
            updated += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"\n완료: {updated}건 업데이트")


if __name__ == "__main__":
    main()
