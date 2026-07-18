# -*- coding: utf-8 -*-
"""후처리 중복 아카이브 판정 로직 — 단위 테스트 (TDD, DB 불필요 순수 함수).

교체 대상: main.py _deduplicate_announcements (하드DELETE·지역무시·소스우선순위없음).
새 판정: select_archive_ids(rows) → 아카이브할 announcement_id 목록.
규칙:
  - 정규화 키 = 보수적 제목(공백정규화+소문자, 괄호 보존) + (개인은 지역, 기업은 '*')
  - 그룹 내 소스 우선순위: 공식API(0) < 수기/기관(1) < scraper(2) → 우선순위 높은(작은) 1건 보존
  - 동순위는 최신(created_at 큰) 보존, 나머지 아카이브
실행: cd backend && python test_dedup_unit.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

from app.services.dedup import select_archive_ids


def _row(id, title, src, region="전국", tt=None, created_at=0):
    return {"announcement_id": id, "title": title, "origin_source": src,
            "region": region, "target_type": tt, "created_at": created_at}


def test_official_and_scraper_same_title_region_archives_scraper_only():
    rows = [
        _row(1, "대상포진 예방접종 지원", "gov24-individual-api", region="서울", created_at=10),
        _row(2, "대상포진 예방접종 지원", "scraper:seoul", region="서울", created_at=20),
    ]
    assert select_archive_ids(rows) == [2], "공식 보존·scraper만 아카이브여야 함"


def test_same_title_different_region_keeps_both():
    rows = [
        _row(1, "대상포진 예방접종 지원", "gov24-individual-api", region="서울"),
        _row(2, "대상포진 예방접종 지원", "gov24-individual-api", region="부산"),
    ]
    assert select_archive_ids(rows) == [], "지역이 다르면 별개 공고 — 아무것도 아카이브하지 않음"


def test_single_row_no_archive():
    rows = [_row(1, "청년 월세 지원", "scraper:x", region="인천")]
    assert select_archive_ids(rows) == []


def test_two_scrapers_same_key_archives_older_keeps_newest():
    rows = [
        _row(1, "종합건설 행정처분 공고", "scraper:a", region="전국", tt="business", created_at=5),
        _row(2, "종합건설 행정처분 공고", "scraper:a", region="전국", tt="business", created_at=9),
    ]
    assert select_archive_ids(rows) == [1], "동일 소스 중복은 최신 보존, 옛것 아카이브"


def test_business_ignores_region_in_key():
    rows = [
        _row(1, "창업 지원사업", "bizinfo-portal-api", region="서울", tt="business", created_at=10),
        _row(2, "창업 지원사업", "scraper:b", region="부산", tt="business", created_at=20),
    ]
    # 기업은 지역 무시 → 같은 그룹 → 공식 보존, scraper 아카이브
    assert select_archive_ids(rows) == [2]


def test_brackets_preserved_not_merged():
    rows = [
        _row(1, "소송대리 서비스(보호대상아동)", "gov24-individual-api", region="서울"),
        _row(2, "소송대리 서비스(저소득층)", "gov24-individual-api", region="서울"),
    ]
    assert select_archive_ids(rows) == [], "괄호 내용이 다르면 별개 — 병합/삭제 금지(구 버그 방지)"


def test_admin_manual_beats_scraper():
    rows = [
        _row(1, "메이커스페이스 장비 지원", "admin-manual", region="대전", tt="business", created_at=10),
        _row(2, "메이커스페이스 장비 지원", "scraper:c", region="대전", tt="business", created_at=20),
    ]
    assert select_archive_ids(rows) == [2], "수기/기관 등록이 scraper보다 우선 — scraper 아카이브"


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p = f = 0
    for fn in fns:
        try:
            fn(); print("PASS  " + fn.__name__); p += 1
        except Exception as e:
            print("FAIL  " + fn.__name__ + ": " + repr(e)); traceback.print_exc(); f += 1
    print("\n%d passed, %d failed" % (p, f))
    sys.exit(1 if f else 0)
