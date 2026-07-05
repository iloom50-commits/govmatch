# -*- coding: utf-8 -*-
"""ongoing 마감 누수(FABLE 진단 2026-07-05, 문제2-B 경로1) — 단위 테스트.

버그: valid_announcement_where의 ongoing 분기가 deadline_date를 안 봐서,
마감일이 과거인 ongoing 공고(2023년 마감 포함 17건 실측)가 계속 노출됨.
아카이브 크론 A(rule 1)도 `<> 'ongoing'`로 ongoing을 명시 제외해 영구 방치.

수정: ① valid_where ongoing 분기에 날짜 가드 ② 크론 A rule1의 ongoing 예외 제거.
진짜 상시(예산 소진까지)는 deadline_date NULL이라 무영향.

실행: cd backend && python test_deadline_ongoing_leak_unit.py
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


def test_valid_where_ongoing_has_date_guard():
    """ongoing 분기가 마감일 가드를 포함해야 함 (구조 — 데이터 무관)."""
    import app.main as m
    sql = m.valid_announcement_where()
    assert "'ongoing' AND (" in sql, \
        "ongoing 분기에 deadline_date 가드 없음 - 마감 지난 상시공고가 노출됨"


def test_ongoing_past_deadline_not_exposed():
    """ongoing인데 마감일이 과거인 공고는 valid 필터를 통과하면 안 됨 (운영 DB 실측)."""
    import psycopg2
    import psycopg2.extras
    import app.main as m
    from app.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(f"""
        SELECT COUNT(*) AS c FROM announcements
        WHERE {m.valid_announcement_where()}
          AND deadline_type = 'ongoing'
          AND deadline_date IS NOT NULL
          AND deadline_date < (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')::DATE
    """)
    leaked = cur.fetchone()["c"]
    conn.close()
    assert leaked == 0, \
        f"ongoing+과거마감 {leaked}건이 valid 필터를 통과(노출) 중 - 마감 표시 안 됨"


def test_archive_cron_no_longer_excludes_ongoing():
    """아카이브 크론 A rule1이 ongoing을 날짜 아카이브에서 제외하지 않아야 함 (구조)."""
    import app.main as m
    # _archive_expired_job은 lifespan 내부 중첩 함수라 lifespan 소스에서 확인
    src = inspect.getsource(m.lifespan)
    # rule1(과거 마감일 아카이브)에서 ongoing을 통째 제외하던 조건이 사라져야 함
    assert "<> 'ongoing'" not in src, \
        "크론 rule1이 여전히 ongoing을 날짜 아카이브에서 제외 - ongoing+과거마감 영구 방치"


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
