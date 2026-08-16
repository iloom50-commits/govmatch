# -*- coding: utf-8 -*-
"""작업1: 점수 컷오프 제거 — 자격은 필터, 점수는 정렬.

결함: get_matches_for_user(matcher.py:1171)가 자격을 전부 통과한 공고를
match_score<60이라는 이유로 결과에서 제외한다. CLAUDE.md 6절 매칭원칙
("자격은 필터, 점수는 적합도. 자격 미달도 완전 제외하지 않고 후순위로")과 충돌.

실행: cd backend && python -m pytest test_score_cutoff_unit.py -q --no-header
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
    """케이비즈업(user_id=1) 프로필 — 읽기전용."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = 1")
    u = dict(cur.fetchone())
    conn.close()
    return u


def test_lowscore_eligible_included():
    """자격을 통과했지만 점수<60인 공고가 결과에 포함돼야 한다(컷오프 제거)."""
    from app.core.matcher import get_matches_for_user
    res = get_matches_for_user(_user1())
    eligible = [r for r in res if r.get("eligibility_status") == "eligible"]
    low = [r for r in eligible if (r.get("match_score") or 0) < 60]
    assert len(low) > 0, (
        f"자격통과·저점(<60) 공고가 컷오프로 제외됨 "
        f"(eligible={len(eligible)}, low={len(low)})"
    )


def test_ineligible_still_present():
    """가드: ineligible은 완전 제외가 아니라 후순위로 포함돼야 한다."""
    from app.core.matcher import get_matches_for_user
    res = get_matches_for_user(_user1())
    inelig = [r for r in res if r.get("eligibility_status") == "ineligible"]
    assert len(inelig) > 0, "ineligible 공고가 완전 제외됨(후순위 포함이어야 함)"
