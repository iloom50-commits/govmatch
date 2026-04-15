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


def _fetch_candidates_for_keywords(
    cur, keywords: List[str], ranked_map: Dict[str, float], target_filter: str
) -> List[Dict[str, Any]]:
    """주어진 키워드 목록으로 공고 후보 수집 (target_type 필터 포함)."""
    candidates: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for kw in keywords:
        ratio = ranked_map.get(kw, 0.0)
        try:
            cur.execute(
                f"""
                SELECT announcement_id, title, department, category, support_amount,
                       deadline_date, region, origin_url, target_type
                FROM announcements
                WHERE (title ILIKE %s OR category ILIKE %s)
                  AND (deadline_date IS NULL OR deadline_date >= CURRENT_DATE)
                  AND COALESCE(target_type, 'business') IN ({target_filter})
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
            try: cur.connection.rollback()
            except: pass
            continue
    return candidates


def _sort_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """자금관련 → 마감 유효 → 금액 큰 순 → 검색지수."""
    def _key(c: Dict[str, Any]) -> Tuple[int, int, int, float]:
        fund_pri = 0 if _fund_related(c.get("title", ""), c.get("category", "")) else 1
        has_deadline = 0 if c.get("deadline_date") else 1
        amount = _amount_score(c.get("support_amount", ""))
        return (fund_pri, has_deadline, -amount, -(c.get("trending_ratio") or 0))
    return sorted(candidates, key=_key)


def select_trending_announcements(db_conn, limit_per_type: int = 2) -> List[Dict[str, Any]]:
    """사업자 키워드 2건 + 개인 키워드 2건 = 총 4건 선정.

    프론트에서 사용자 user_type에 따라 필터링 후 상위 2건만 표시.
    """
    ranked = fetch_datalab_ranking()
    if not ranked:
        print("[Trending] DataLab unavailable, using static fallback keywords")
        ranked = [(kw, 1.0) for kw in _ALL_KEYWORDS]
    ranked_map = {kw: r for kw, r in ranked}

    # 데이터랩 순위로 키워드 재정렬 (우선순위 보존)
    biz_sorted = sorted(_BIZ_KEYWORDS, key=lambda k: -ranked_map.get(k, 0))
    indiv_sorted = sorted(_INDIV_KEYWORDS, key=lambda k: -ranked_map.get(k, 0))

    cur = db_conn.cursor()

    # 사업자 후보: target_type in (business, both)
    biz_candidates = _fetch_candidates_for_keywords(
        cur, biz_sorted, ranked_map, "'business', 'both'"
    )
    biz_sorted_cand = _sort_candidates(biz_candidates)

    # 개인 후보: target_type in (individual, both)
    indiv_candidates = _fetch_candidates_for_keywords(
        cur, indiv_sorted, ranked_map, "'individual', 'both'"
    )
    indiv_sorted_cand = _sort_candidates(indiv_candidates)

    # 카테고리 다양성 적용하며 각 유형에서 limit_per_type 건씩 선정
    def _pick_diverse(cands: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
        picked: List[Dict[str, Any]] = []
        seen_cats: set = set()
        for c in cands:
            cat = c.get("category") or "일반"
            if cat in seen_cats and len(picked) >= 1:
                continue
            picked.append(c)
            seen_cats.add(cat)
            if len(picked) >= n:
                break
        # 다양성 필터로 부족하면 나머지로 채움
        if len(picked) < n:
            for c in cands:
                if c in picked:
                    continue
                picked.append(c)
                if len(picked) >= n:
                    break
        return picked[:n]

    biz_picked = _pick_diverse(biz_sorted_cand, limit_per_type)
    indiv_picked = _pick_diverse(indiv_sorted_cand, limit_per_type)

    # 사업자 먼저 / 개인 다음 순서로 합침 (저장 rank는 순번대로)
    return biz_picked + indiv_picked


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
    """인기 공고 업데이트 전체 실행 (패트롤 호출용) — 사업자 2 + 개인 2 = 4건."""
    announcements = select_trending_announcements(db_conn, limit_per_type=2)
    saved = save_trending(db_conn, announcements)
    titles = [a["title"][:30] for a in announcements]
    keywords = [a.get("trending_keyword", "") for a in announcements]
    print(f"[Trending] Updated: {saved} announcements — keywords={keywords} titles={titles}")
    return {"selected": len(announcements), "saved": saved, "titles": titles, "keywords": keywords}
