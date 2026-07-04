# -*- coding: utf-8 -*-
"""메인화면 탭/칩 필터 total 버그(2026-07-05 진단) — 단위 테스트.

버그: /api/announcements/public 필터 경로에서 COUNT 결과를 fetch하기 전에
RESET statement_timeout을 실행 → 'no results to fetch' 예외 → 항상 reltuples
근사치(29,065)로 폴백. 행 필터링은 정상이나 총계·페이지네이션 분모가 오염.

실행: cd backend && python test_tab_filter_unit.py
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


class _FakeClient:
    host = "127.0.0.1"


class _FakeReq:
    client = _FakeClient()
    headers = {}


def test_count_fetch_before_reset():
    """COUNT 결과 fetch가 RESET보다 먼저 와야 한다 (순서 버그 회귀 방지)."""
    import app.main as m
    src = inspect.getsource(m.api_announcements_public)
    i = src.find("SELECT COUNT(*) AS cnt FROM announcements WHERE {where_sql}")
    assert i > 0
    seg = src[i:i + 400]
    assert "fetchone" in seg and "RESET statement_timeout" in seg
    assert seg.find("fetchone") < seg.find("RESET statement_timeout"), \
        "fetchone이 RESET 뒤에 있음 — 'no results to fetch'로 총계가 항상 근사치 폴백됨"


def test_public_total_matches_real_count():
    """카테고리 칩 선택 시 total이 실제 건수와 일치해야 한다 (운영 DB 실측 대조)."""
    import psycopg2
    import psycopg2.extras
    import app.main as m
    from app.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        f"""SELECT COUNT(*) AS c FROM announcements
            WHERE {m.valid_announcement_where()}
              AND (target_type = 'business' OR target_type = 'both' OR target_type IS NULL)
              AND category = %s""",
        ("자금·지원",),
    )
    expected = cur.fetchone()["c"]
    conn.close()

    r = m.api_announcements_public(
        request=_FakeReq(), page=1, size=5, region=None,
        category="자금·지원", search=None, target_type="business",
        tab=None, authorization=None,
    )
    assert r["total"] == expected, f"API total={r['total']} vs 실제 {expected} (근사치 폴백 의심)"
    assert len(r.get("data") or []) > 0


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
