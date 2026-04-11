"""오늘의 인기 공고 수집 — 검색 트렌드 + DB 조회수 기반

매일 패트롤에서 실행:
1. 네이버/구글 검색 트렌드에서 정부지원사업 관련 키워드 추출
2. 해당 키워드로 DB 매칭 → 상위 3건 선정
3. trending_announcements 테이블에 저장
"""

import json
import requests
from typing import List, Dict, Any
from datetime import date


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# 정부지원사업 관련 기본 인기 키워드 (트렌드 크롤링 실패 시 폴백)
_FALLBACK_KEYWORDS = [
    "정책자금", "소상공인 대출", "창업지원금", "청년 지원",
    "고용장려금", "R&D 지원", "수출바우처", "전세자금",
]


def fetch_trending_keywords(limit: int = 10) -> List[str]:
    """네이버 DataLab 또는 Google Trends에서 정부지원 관련 인기 키워드 수집"""
    keywords = []

    # 네이버 실시간 검색어 (비공식 — 실패해도 무방)
    try:
        r = requests.get(
            "https://www.google.com/trending/rss?geo=KR",
            headers=_HEADERS, timeout=10
        )
        if r.status_code == 200:
            import re
            titles = re.findall(r"<title>([^<]+)</title>", r.text)
            gov_keywords = [
                t for t in titles
                if any(kw in t for kw in ["지원", "자금", "대출", "보조금", "창업", "청년", "소상공인", "정책", "고용", "R&D"])
            ]
            keywords.extend(gov_keywords[:limit])
    except Exception:
        pass

    # 부족하면 폴백 키워드 사용
    if len(keywords) < 3:
        keywords.extend(_FALLBACK_KEYWORDS)

    return keywords[:limit]


def select_trending_announcements(db_conn, limit: int = 3) -> List[Dict[str, Any]]:
    """인기 키워드 + DB 매칭으로 오늘의 인기 공고 선정"""
    keywords = fetch_trending_keywords()
    cur = db_conn.cursor()

    candidates = []
    seen_ids = set()

    for kw in keywords:
        cur.execute("""
            SELECT announcement_id, title, department, category, support_amount,
                   deadline_date, region, origin_url, final_url
            FROM announcements
            WHERE (title ILIKE %s OR category ILIKE %s)
              AND (deadline_date IS NULL OR deadline_date >= CURRENT_DATE)
            ORDER BY
                CASE WHEN deadline_date IS NOT NULL THEN 0 ELSE 1 END,
                deadline_date ASC NULLS LAST,
                created_at DESC
            LIMIT 3
        """, (f"%{kw}%", f"%{kw}%"))

        for row in cur.fetchall():
            aid = row["announcement_id"]
            if aid not in seen_ids:
                seen_ids.add(aid)
                candidates.append({
                    **dict(row),
                    "trending_keyword": kw,
                    "trending_reason": f'"{kw}" 검색 인기',
                })

    # 점수 기반 정렬: 금액 큰 순 + 마감 임박 + 다양성
    def _score(c):
        score = 0
        amt = c.get("support_amount") or ""
        if "억" in amt:
            score += 50
        elif "만" in amt:
            score += 10
        if c.get("deadline_date"):
            score += 20
        return score

    candidates.sort(key=_score, reverse=True)

    # 카테고리 중복 방지 (다양성)
    result = []
    seen_cats = set()
    for c in candidates:
        cat = c.get("category", "")
        if cat not in seen_cats or len(result) < limit:
            result.append(c)
            seen_cats.add(cat)
        if len(result) >= limit:
            break

    return result[:limit]


def save_trending(db_conn, announcements: List[Dict]) -> int:
    """오늘의 인기 공고 저장"""
    cur = db_conn.cursor()
    today = date.today().isoformat()

    # 오늘 데이터 삭제 후 재삽입
    try:
        cur.execute("DELETE FROM trending_announcements WHERE trending_date = %s", (today,))
    except Exception:
        db_conn.rollback()
        # 테이블이 없으면 생성
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trending_announcements (
                id SERIAL PRIMARY KEY,
                trending_date DATE NOT NULL,
                rank INTEGER NOT NULL,
                announcement_id INTEGER NOT NULL,
                trending_keyword TEXT,
                trending_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trending_date ON trending_announcements(trending_date)")

    saved = 0
    for i, ann in enumerate(announcements, 1):
        try:
            cur.execute("""
                INSERT INTO trending_announcements (trending_date, rank, announcement_id, trending_keyword, trending_reason)
                VALUES (%s, %s, %s, %s, %s)
            """, (today, i, ann["announcement_id"], ann.get("trending_keyword", ""), ann.get("trending_reason", "")))
            saved += 1
        except Exception as e:
            print(f"[Trending] Save error: {e}")

    db_conn.commit()
    return saved


def run_trending_update(db_conn) -> Dict[str, Any]:
    """인기 공고 업데이트 전체 실행"""
    announcements = select_trending_announcements(db_conn, limit=3)
    saved = save_trending(db_conn, announcements)
    titles = [a["title"][:30] for a in announcements]
    print(f"[Trending] Updated: {saved} announcements — {titles}")
    return {"selected": len(announcements), "saved": saved, "titles": titles}
