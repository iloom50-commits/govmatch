# -*- coding: utf-8 -*-
"""작업3: 관심 세부태그가 대분류 키워드를 상속해야 매칭된다.

결함: matcher.py:1005 `INTEREST_KEYWORD_MAP.get(tag, [tag])`. 여기서 tag는 seed의
세부태그("AI도입"·"공장자동화")인데 INTEREST_KEYWORD_MAP의 키는 대분류("디지털전환"·"시설개선").
세부태그는 키에 없어 [tag] 리터럴로 떨어져 거의 매칭 안 됨. "R&D"만 우연히 키로도 존재해 작동.

user_id=1 관심: AI도입,R&D,스마트공장,공장자동화,로봇,DX
실측(수정 전): R&D=222, 스마트공장=4, 로봇=7, DX=1, AI도입=1, 공장자동화=0

실행: cd backend && python -m pytest test_interest_tag_expansion_unit.py -q --no-header
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
import psycopg2
import psycopg2.extras
from collections import Counter


def _user1() -> dict:
    conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = 1")
    u = dict(cur.fetchone())
    conn.close()
    return u


def _matched_interest_counts() -> Counter:
    from app.core.matcher import get_matches_for_user
    res = get_matches_for_user(_user1())
    mi = Counter()
    for r in res:
        for t in (r.get("matched_interests") or []):
            mi[t] += 1
    return mi


def test_detail_tag_inherits_group_keywords():
    """세부태그(공장자동화=시설, AI도입=디지털)가 대분류 키워드를 상속해 실제로 매칭돼야 한다.
    수정 전엔 리터럴이라 각각 0·1건. 상속되면 흔한 키워드(시설/설비/장비, 디지털/AI/스마트)로 다수 매칭."""
    mi = _matched_interest_counts()
    assert mi.get("공장자동화", 0) >= 10, (
        f"'공장자동화'(시설 그룹)가 시설개선 키워드를 상속 못 함 — {mi.get('공장자동화', 0)}건 "
        f"(리터럴 '공장자동화'만 검색 중)"
    )
    assert mi.get("AI도입", 0) >= 10, (
        f"'AI도입'(디지털 그룹)이 디지털전환 키워드를 상속 못 함 — {mi.get('AI도입', 0)}건 "
        f"(리터럴 'AI도입'만 검색 중)"
    )
