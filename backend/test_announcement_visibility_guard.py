# -*- coding: utf-8 -*-
"""구조적 가드 — 제목 키워드 필터가 '모집중 공고'를 조용히 버리지 않는지 전수 검사.

■ 막는 버그 클래스
   "수집·파싱은 정상인데 사용자에게 안 보인다."
   - 2026-08-16: NOTICE_KEYWORDS의 "수정 공고"가 정본 공고 25건을 제외 (모두의AI·TIPS·정책자금 포함)
   - 이전 이력(CLAUDE.md): 등록일을 마감일로 오인 저장 → 진행중 공고가 전량 사라짐
   개별 사례를 하나씩 고치면 두더지잡기가 된다. 클래스 전체를 불가능하게 만든다.

■ 불변식
   마감일이 아직 남은 기업대상 공고는, '제목에 특정 단어가 들어갔다'는 이유만으로
   하드필터에서 제외되어서는 안 된다. 예외는 ALLOWLIST에 사유와 함께 등재한다.

■ 실행
   cd backend && python -m pytest test_announcement_visibility_guard.py -v
   (DATABASE_URL이 없으면 skip — 로컬 유닛 테스트만 돌릴 때 방해하지 않음)
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# 제외가 '정당한' 공고 — 실제로 신청 대상이 아닌 결과 발표성 공고.
# 새 항목을 넣을 때는 반드시 사유를 함께 적는다.
ALLOWLIST_TITLE_MARKERS = (
    "선정 결과",      # 이미 선정이 끝난 건 — 신청 불가
    "선정결과",
    "결과 발표",      # 발표 공지 — 신청 불가
    "합격자 발표",
)

# 검사 대상 사유 — 제목 키워드로 인한 제외
_KEYWORD_EXCLUSION_MARKERS = ("공지성 공고",)


def _fetch_open_announcements():
    """현재 모집중인 기업대상 공고 전수 (매칭 SQL 1차 필터와 동일 조건)."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL 미설정 — DB 가드 생략")
    conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT announcement_id, title, region, category, department,
                   support_amount, deadline_date, deadline_type, origin_source,
                   created_at, COALESCE(target_type,'business') AS target_type,
                   origin_url, summary_text, eligibility_logic,
                   established_years_limit, revenue_limit, employee_limit
            FROM announcements
            WHERE is_archived = FALSE
              AND deadline_date >= CURRENT_DATE
              AND COALESCE(target_type,'business') IN ('business','both')
        """)
        return [dict(r) for r in cur.fetchall()], conn
    except Exception:
        conn.close()
        raise


# 일반적인 중소기업 프로필 — 특정 자격(여성/장애인/농업 등)에 해당하지 않는 기본형.
# 이 프로필로도 제외되는 공고만 '키워드 때문에 버려진 것'으로 볼 수 있다.
GENERIC_PROFILE = {
    "industry_name": "응용 소프트웨어 개발 및 공급업",
    "industry_code": "58222",
    "address_city": "",           # 소재지 미지정 → 지역 필터 영향 배제
    "certifications": "",
    "revenue_bracket": "1억 미만",
    "employee_count_bracket": "5인~10인",
    "establishment_date": "2019-07-01",
    "interests": "",
}


def test_모집중_공고가_제목키워드로_버려지지_않는다():
    from app.core.matcher import _hard_filter_business

    candidates, conn = _fetch_open_announcements()
    try:
        assert candidates, "모집중 공고가 0건 — 수집 파이프라인 자체를 먼저 확인할 것"
        _passed, excluded = _hard_filter_business(candidates, GENERIC_PROFILE, conn)
    finally:
        conn.close()

    offenders = []
    for e in excluded:
        reasons = e.get("reasons") or []
        if not any(m in r for r in reasons for m in _KEYWORD_EXCLUSION_MARKERS):
            continue  # 지역·업종 등 다른 사유는 이 가드의 대상이 아님
        title = (e.get("ad") or {}).get("title") or ""
        if any(m in title for m in ALLOWLIST_TITLE_MARKERS):
            continue  # 결과 발표성 — 제외가 정당
        offenders.append(f"{title[:70]}  ← {reasons}")

    assert not offenders, (
        f"제목 키워드만으로 제외된 모집중 공고 {len(offenders)}건 "
        f"(전체 {len(candidates)}건 중).\n"
        "신청 가능한 공고라면 필터 키워드를 고치고, 정당한 제외라면 "
        "ALLOWLIST_TITLE_MARKERS에 사유와 함께 등재할 것:\n  "
        + "\n  ".join(sorted(offenders)[:30])
    )


def test_결과발표성_공고는_계속_제외된다():
    """가드가 반대 방향으로 무력화되지 않았는지 — 필터가 아예 안 도는 상태 방지."""
    from app.core.matcher import _hard_filter_business

    ad = {
        "announcement_id": -1,
        "title": "2026년 창업성장기술개발사업 선정 결과 공고",
        "region": "All",
        "summary_text": "",
        "target_type": "business",
    }
    passed, excluded = _hard_filter_business([ad], GENERIC_PROFILE, None)
    assert not passed, "결과 발표성 공고가 통과됨 — 공지성 필터가 동작하지 않는다"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
