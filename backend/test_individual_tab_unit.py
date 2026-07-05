# -*- coding: utf-8 -*-
"""개인탭 기업공고 혼입 차단(FABLE 진단 2026-07-05, 문제3) — 단위 테스트.

B-2b: 출처 강제규칙(bokjiro/gov24 개인피드 → 내용무관 individual)에 기업성 가드 추가.
      제목이 명백히 사업자 대상(소상공인/중소기업/스타트업 등)이면 강제 않고 Gemini로.
B-2c: 'both'(제품결정=사업자)를 개인탭에서 제외. matcher/공개목록 필터 통일.

실행: cd backend && python test_individual_tab_unit.py
"""
import os
import sys
import inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from app.services.patrol.target_type_classifier import _apply_source_override


class _FakeClient:
    host = "127.0.0.1"


class _FakeReq:
    client = _FakeClient()
    headers = {}


# ── B-2b: 출처 강제에 기업성 가드 ──
def test_welfare_source_business_title_not_forced_individual():
    items = [{"id": 1, "origin_source": "scraper:bokjiro_central",
              "department": "중소벤처기업부", "title": "소상공인지원(융자)"}]
    forced, remaining = _apply_source_override(items)
    assert 1 not in forced, "기업성 제목(소상공인)인데 individual 강제됨"
    assert any(it["id"] == 1 for it in remaining), "Gemini로 안 넘김"


def test_welfare_source_startup_title_not_forced_individual():
    items = [{"id": 2, "origin_source": "gov24-individual-api",
              "department": "중소벤처기업부", "title": "도전! K-스타트업"}]
    forced, _ = _apply_source_override(items)
    assert 2 not in forced, "기업성 제목(스타트업)인데 individual 강제됨"


def test_welfare_source_genuine_individual_still_forced():
    # 기업성 신호 없는 진짜 복지 → individual 유지 (기존 동작 보존)
    items = [{"id": 3, "origin_source": "scraper:bokjiro_local",
              "department": "보건복지부", "title": "청년 월세 한시 특별지원"}]
    forced, _ = _apply_source_override(items)
    assert forced.get(3) == "individual", "진짜 개인복지가 individual 강제 안 됨"


# ── B-2c: 개인탭 both 제외 ──
def test_matcher_individual_query_excludes_both():
    import app.core.matcher as mt
    src = inspect.getsource(mt)
    assert "IN ('individual', 'both')" not in src, \
        "매처 개인 매칭 쿼리가 여전히 both 포함(사업자 공고가 개인 매칭에 노출)"


def test_public_individual_total_excludes_both():
    """비로그인 개인탭 total이 individual-only 건수와 일치해야 함 (both 미포함, 운영 DB)."""
    import psycopg2
    import psycopg2.extras
    import app.main as m
    from app.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        f"SELECT COUNT(*) AS c FROM announcements "
        f"WHERE {m.valid_announcement_where()} AND target_type = 'individual'"
    )
    individual_only = cur.fetchone()["c"]
    conn.close()

    r = m.api_announcements_public(
        request=_FakeReq(), page=1, size=5, region=None,
        category=None, search=None, target_type="individual",
        tab=None, authorization=None,
    )
    assert r["total"] == individual_only, \
        f"개인탭 total={r['total']} != individual-only {individual_only} (both 포함 의심)"


def test_unclear_fallback_is_null_not_both():
    """판단불가(신뢰도<70·응답누락) 폴백이 both가 아니라 NULL이어야 함 (의미 오염 차단, 재분류 대기)."""
    from app.services.patrol import target_type_classifier as tc
    src = inspect.getsource(tc._classify_and_update)
    assert 'new_type = "both"' not in src, \
        "판단불가 폴백이 여전히 both로 의미 오염(NULL로 두고 재분류해야 함)"


if __name__ == "__main__":
    import traceback
    _fns = [v for k, v in sorted(globals().items())
            if k.startswith("test_") and callable(v)]
    _passed = _failed = 0
    for _fn in _fns:
        try:
            _fn()
            print("PASS  " + _fn.__name__)
            _passed += 1
        except Exception as _e:
            print("FAIL  " + _fn.__name__ + ": " + repr(_e))
            traceback.print_exc()
            _failed += 1
    print("\n%d passed, %d failed" % (_passed, _failed))
    sys.exit(1 if _failed else 0)
