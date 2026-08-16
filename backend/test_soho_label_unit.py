# -*- coding: utf-8 -*-
"""작업2: "소상공인 전용" 오표기 수정 — 문구만 정확하게.

결함: matcher.py:988이 ad_targets_soho(본문에 "소규모" 한 단어만 있어도 True)일 때
"소상공인 전용 지원사업"을 붙인다. 이건 '관련/대상'이지 '전용'이 아니다. 실제 배타
판정(_mark_ineligible, matcher.py:856 "소상공인 전용 (사용자 비해당)")과 혼동을 준다.

실행: cd backend && python -m pytest test_soho_label_unit.py -q --no-header
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


def _user1() -> dict:
    """케이비즈업(user_id=1) — 매출 1억~5억·5인 미만이라 is_soho=True. 읽기전용."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = 1")
    u = dict(cur.fetchone())
    conn.close()
    return u


def test_soho_match_label_not_exclusive():
    """소상공인 매칭 라벨이 '전용'이 아니라 '대상/관련'이어야 한다."""
    from app.core.matcher import get_matches_for_user
    res = get_matches_for_user(_user1())
    bad = [r for r in res if "소상공인 전용 지원사업" in (r.get("recommendation_reason") or "")]
    assert len(bad) == 0, (
        f"'소상공인 전용 지원사업' 라벨이 {len(bad)}건에 붙음 "
        f"— ad_targets_soho는 '전용'이 아니라 '대상/관련'이어야 함"
    )
