"""
공고 region 필드 데이터 보정 스크립트.

region = '전국' / NULL / '' 인 공고 중
department 또는 title 에 특정 지역명이 포함된 경우 해당 지역으로 업데이트.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── 지역 키워드 매핑 (긴 것 먼저 → 부분 매칭 오류 방지) ──
REGION_PATTERNS = [
    # 공식 전체 명칭 우선
    ("강원특별자치도", "강원"), ("강원도",        "강원"),
    ("경상북도",       "경북"), ("경상남도",       "경남"),
    ("전라북도",       "전북"), ("전북특별자치도", "전북"),
    ("전라남도",       "전남"),
    ("충청북도",       "충북"), ("충청남도",       "충남"),
    ("제주특별자치도", "제주"), ("제주도",         "제주"),
    ("서울특별시",     "서울"), ("인천광역시",     "인천"),
    ("부산광역시",     "부산"), ("대구광역시",     "대구"),
    ("광주광역시",     "광주"), ("대전광역시",     "대전"),
    ("울산광역시",     "울산"), ("세종특별자치시", "세종"),
    ("경기도",         "경기"),
    # 약칭 (단독 등장 시)
    ("강원", "강원"), ("경북", "경북"), ("경남", "경남"),
    ("전북", "전북"), ("전남", "전남"),
    ("충북", "충북"), ("충남", "충남"),
    ("제주", "제주"), ("경기", "경기"),
    ("세종", "세종"),
    # 광역시 약칭 (독립 매칭 — '광주' 같은 모호한 이름 주의)
    ("서울", "서울"), ("인천", "인천"), ("부산", "부산"),
    ("대구", "대구"), ("대전", "대전"), ("울산", "울산"),
    # 광주는 경기 광주와 광역시 구분 — 광역시 명칭 있을 때만 허용 (위에서 처리됨)
]

# 모호성 높은 단독 키워드 — department·title 양쪽에서 정확히 단독 등장 시만 허용
AMBIGUOUS = {"광주"}


def extract_region(text: str) -> str | None:
    """텍스트에서 첫 번째로 매칭되는 지역명 반환."""
    if not text:
        return None
    for keyword, normalized in REGION_PATTERNS:
        if keyword in text:
            if keyword in AMBIGUOUS:
                # "광주광역시" 는 위에서 먼저 처리됨; 단독 "광주"는 스킵
                continue
            return normalized
    return None


def get_region_from_announcement(row: dict) -> str | None:
    """department → title 순으로 지역명 추출."""
    dept = row.get("department") or ""
    title = row.get("title") or ""

    # 1순위: department
    r = extract_region(dept)
    if r:
        return r

    # 2순위: title (단, 단독 약칭은 false-positive 위험 있어 좀 더 엄격하게)
    r = extract_region(title)
    return r


def main(dry_run: bool = True):
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    cur.execute("""
        SELECT announcement_id, title, department, region
        FROM announcements
        WHERE (region IS NULL OR region = '' OR region = '전국' OR region = 'All')
          AND is_archived = FALSE
        ORDER BY announcement_id
    """)
    rows = cur.fetchall()
    print(f"대상 공고: {len(rows)}건")

    updated = 0
    skipped = 0
    for row in rows:
        new_region = get_region_from_announcement(dict(row))
        if not new_region:
            skipped += 1
            continue

        print(f"  [{row['announcement_id']}] '{row['title'][:40]}' → {new_region}  (dept: {(row['department'] or '')[:30]})")
        if not dry_run:
            cur.execute(
                "UPDATE announcements SET region = %s WHERE announcement_id = %s",
                (new_region, row["announcement_id"])
            )
        updated += 1

    print(f"\n결과: 업데이트 {updated}건 / 유지(전국) {skipped}건")
    if not dry_run:
        conn.commit()
        print("DB 커밋 완료")
    else:
        print("[DRY RUN] 실제 변경 없음. 실행하려면: python fix_regions.py --apply")

    cur.close()
    conn.close()


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    main(dry_run=not apply)
