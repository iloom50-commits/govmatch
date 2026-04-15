"""오늘의 인기 공고 수집 — 네이버 데이터랩 기반

매일 패트롤 1회 실행:
1. 네이버 데이터랩 API (/v1/datalab/search)로 사전 정의 20개 키워드의 전일 검색지수 조회
2. 검색지수 상위 키워드로 DB 매칭
3. "자금관련 → 마감 유효 → 금액 큰 순"으로 정렬해 상위 2건 선정
4. trending_announcements 테이블에 저장
"""

import json
import os
import re
import requests
from typing import List, Dict, Any, Tuple
from datetime import date, timedelta


# 네이버 데이터랩에 질의할 정부지원사업 관련 키워드 (사업자 10 + 개인 10 = 20개)
_BIZ_KEYWORDS = [
    "정책자금", "청년창업자금", "소상공인 대출", "수출바우처",
    "긴급경영안정자금", "스마트공장 지원", "R&D 지원사업",
    "이노비즈", "벤처확인", "신성장기반자금",
]
_INDIV_KEYWORDS = [
    "버팀목전세자금", "디딤돌대출", "청년도약계좌",
    "국민취업지원제도", "내일배움카드", "기초연금",
    "긴급복지지원", "아이돌봄서비스", "산후조리원 지원", "한부모가족지원",
]
_ALL_KEYWORDS = _BIZ_KEYWORDS + _INDIV_KEYWORDS


def fetch_datalab_ranking() -> List[Tuple[str, float]]:
    """네이버 데이터랩 /v1/datalab/search — 전일까지 7일치 검색지수로 키워드 순위 산출.

    Returns: [(keyword, avg_ratio), ...] — ratio 큰 순으로 정렬.
    환경변수 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 필요.
    """
    cid = os.getenv("NAVER_CLIENT_ID", "")
    csec = os.getenv("NAVER_CLIENT_SECRET", "")
    if not cid or not csec:
        return []

    today = date.today()
    start = (today - timedelta(days=7)).isoformat()
    end = (today - timedelta(days=1)).isoformat()

    # 데이터랩은 한 호출에 최대 5개 keywordGroups 허용 → 4번 나눠 호출
    all_ranks: Dict[str, float] = {}
    for i in range(0, len(_ALL_KEYWORDS), 5):
        batch = _ALL_KEYWORDS[i:i + 5]
        body = {
            "startDate": start,
            "endDate": end,
            "timeUnit": "date",
            "keywordGroups": [
                {"groupName": kw, "keywords": [kw]} for kw in batch
            ],
        }
        try:
            r = requests.post(
                "https://openapi.naver.com/v1/datalab/search",
                headers={
                    "X-Naver-Client-Id": cid,
                    "X-Naver-Client-Secret": csec,
                    "Content-Type": "application/json",
                },
                data=json.dumps(body),
                timeout=15,
            )
            if r.status_code != 200:
                print(f"[Trending][DataLab] HTTP {r.status_code}: {r.text[:200]}")
                continue
            data = r.json()
            for group in data.get("results", []):
                name = group.get("title") or ""
                points = group.get("data") or []
                if not points:
                    continue
                # 최근 3일 평균을 대표 지수로 (전일 하나만 쓰면 변동 큼)
                recent = points[-3:]
                avg = sum(p.get("ratio", 0) for p in recent) / max(1, len(recent))
                all_ranks[name] = round(avg, 2)
        except Exception as e:
            print(f"[Trending][DataLab] batch error: {e}")
            continue

    ranked = sorted(all_ranks.items(), key=lambda x: x[1], reverse=True)
    return ranked


def _fund_related(title: str, category: str) -> bool:
    text = f"{title or ''} {category or ''}".lower()
    return any(k in text for k in [
        "정책자금", "융자", "보증", "대출", "자금", "r&d", "연구개발", "기술개발", "창업자금",
    ])


def _amount_score(amount_str: str) -> int:
    if not amount_str:
        return 0
    try:
        if "억" in amount_str:
            m = re.search(r"(\d+(?:\.\d+)?)\s*억", amount_str)
            if m:
                return int(float(m.group(1)) * 100_000_000)
        if "천만" in amount_str:
            m = re.search(r"(\d+(?:\.\d+)?)\s*천만", amount_str)
            if m:
                return int(float(m.group(1)) * 10_000_000)
        if "만원" in amount_str or "만" in amount_str:
            m = re.search(r"(\d+(?:\.\d+)?)\s*만", amount_str)
            if m:
                return int(float(m.group(1)) * 10_000)
    except Exception:
        pass
    return 0


def select_trending_announcements(db_conn, limit: int = 2) -> List[Dict[str, Any]]:
    """네이버 데이터랩 순위 → DB 매칭 → 버킷 내부 정렬 → 상위 N건."""
    ranked = fetch_datalab_ranking()
    if not ranked:
        # 폴백: API 키 없거나 실패 → 고정 키워드 사용
        print("[Trending] DataLab unavailable, using static fallback keywords")
        ranked = [(kw, 1.0) for kw in _ALL_KEYWORDS]

    cur = db_conn.cursor()
    candidates: List[Dict[str, Any]] = []
    seen_ids = set()

    # 상위 키워드 각각에 대해 DB 매칭 (최대 8개 키워드 × 5건 = 40 후보)
    for kw, ratio in ranked[:10]:
        try:
            cur.execute(
                """
                SELECT announcement_id, title, department, category, support_amount,
                       deadline_date, region, origin_url
                FROM announcements
                WHERE (title ILIKE %s OR category ILIKE %s)
                  AND (deadline_date IS NULL OR deadline_date >= CURRENT_DATE)
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (f"%{kw}%", f"%{kw}%"),
            )
            for row in cur.fetchall():
                aid = row["announcement_id"]
                if aid in seen_ids:
                    continue
                seen_ids.add(aid)
                d = dict(row)
                d["trending_keyword"] = kw
                d["trending_ratio"] = ratio
                d["trending_reason"] = f'"{kw}" 검색 인기'
                candidates.append(d)
        except Exception as e:
            print(f"[Trending] Query error for '{kw}': {e}")
            try: db_conn.rollback()
            except: pass
            continue

    # 버킷 내부 정렬: 자금관련 우선 → 마감 유효 → 금액 큰 순
    def _sort_key(c: Dict[str, Any]) -> Tuple[int, int, int, float]:
        fund_pri = 0 if _fund_related(c.get("title", ""), c.get("category", "")) else 1
        # 마감 유효는 이미 WHERE에서 보장되지만 혹시 모를 NULL 안전성
        has_deadline = 0 if c.get("deadline_date") else 1
        amount = _amount_score(c.get("support_amount", ""))
        # amount 큰 순 = 음수로 변환
        return (fund_pri, has_deadline, -amount, -(c.get("trending_ratio") or 0))

    candidates.sort(key=_sort_key)

    # 카테고리 다양성 (동일 카테고리 연속 방지 — 상위 2건이라 1개만 체크)
    result: List[Dict[str, Any]] = []
    seen_cats: set = set()
    for c in candidates:
        cat = c.get("category") or "일반"
        if cat in seen_cats and len(result) >= 1:
            continue
        result.append(c)
        seen_cats.add(cat)
        if len(result) >= limit:
            break

    return result[:limit]


def save_trending(db_conn, announcements: List[Dict]) -> int:
    """오늘의 인기 공고 저장 — 당일 데이터 재삽입."""
    cur = db_conn.cursor()
    today = date.today().isoformat()

    try:
        cur.execute("DELETE FROM trending_announcements WHERE trending_date = %s", (today,))
    except Exception:
        db_conn.rollback()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trending_announcements (
                id SERIAL PRIMARY KEY,
                trending_date DATE NOT NULL,
                rank INTEGER NOT NULL,
                announcement_id INTEGER NOT NULL,
                trending_keyword TEXT,
                trending_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trending_date ON trending_announcements(trending_date)")

    saved = 0
    for i, ann in enumerate(announcements, 1):
        try:
            cur.execute(
                """
                INSERT INTO trending_announcements (trending_date, rank, announcement_id, trending_keyword, trending_reason)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    today,
                    i,
                    ann["announcement_id"],
                    ann.get("trending_keyword", ""),
                    ann.get("trending_reason", ""),
                ),
            )
            saved += 1
        except Exception as e:
            print(f"[Trending] Save error: {e}")

    db_conn.commit()
    return saved


def run_trending_update(db_conn) -> Dict[str, Any]:
    """인기 공고 업데이트 전체 실행 (패트롤 호출용)."""
    announcements = select_trending_announcements(db_conn, limit=2)
    saved = save_trending(db_conn, announcements)
    titles = [a["title"][:30] for a in announcements]
    keywords = [a.get("trending_keyword", "") for a in announcements]
    print(f"[Trending] Updated: {saved} announcements — keywords={keywords} titles={titles}")
    return {"selected": len(announcements), "saved": saved, "titles": titles, "keywords": keywords}
