"""공고 본문 마감일 추출기 단위 테스트 (순수 함수, DB·AI 불필요)."""

from app.services.deadline_enricher import enrich_deadline


def test_extracts_end_of_range():
    # 접수기간 범위 → 종료일(마감) 반환
    assert enrich_deadline("○ 접수기간 : 2026.6.22 ~ 2026.7.10") == ("fixed", "2026-07-10")


def test_extracts_single_submit_date():
    assert enrich_deadline("제출기간 : 2026.06.26 까지 제출") == ("fixed", "2026-06-26")


def test_extracts_until_date():
    assert enrich_deadline("신청기한 ~2026.4.30") == ("fixed", "2026-04-30")


def test_korean_unit_date():
    assert enrich_deadline("모집기간: 2026년 6월 24일") == ("fixed", "2026-06-24")


def test_sangsi_marker():
    assert enrich_deadline("신청은 예산 소진 시까지 가능합니다") == ("ongoing", None)
    assert enrich_deadline("연중 상시 모집합니다") == ("ongoing", None)


def test_gov24_service_template_is_sangsi():
    # 정부24 서비스 템플릿(접수기간 항목 없음 = 상시 운영 민원서비스)
    t = "[지원대상] ○ 한우 농가, 법인 [지원내용] ○ 시설 장비 [신청방법] ○ 방문 신청 [문의처] 064-710-2122"
    assert enrich_deadline(t) == ("ongoing", None)


def test_unknown_when_no_signal():
    assert enrich_deadline("본 사업은 우수 기업을 선정하여 지원합니다.") == ("unknown", None)


def test_empty():
    assert enrich_deadline("") == ("unknown", None)
    assert enrich_deadline(None) == ("unknown", None)


def test_date_beats_sangsi_marker():
    # 마감일이 명시돼 있으면 상시 마커보다 우선
    assert enrich_deadline("상시 모집이나 접수기간 : 2026.5.1 ~ 2026.5.31") == ("fixed", "2026-05-31")


def test_ignores_invalid_date():
    # 13월 같은 잘못된 날짜는 무시 → 미상
    assert enrich_deadline("접수기간 : 2026.13.40") == ("unknown", None)
