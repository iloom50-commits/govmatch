# -*- coding: utf-8 -*-
"""공지성 필터 오탈락(2026-08-16 발견) — 단위 테스트.

증상: "전 국민 AI 서비스 보편적 활용 지원(모두의 AI) 사업 수정 공고"가
      매칭 결과에서 사라짐. 추적 결과 하드필터가 "공지성 공고 (지원사업 아님)"으로 제외.

원인: NOTICE_KEYWORDS에 "수정 공고"·"변경 공고"·"정정 공고"가 포함됨.
      정부 공고에서 "수정 공고"는 '지원사업이 아님'이 아니라 '이것이 최종 정본'이라는 뜻.
      원본은 is_archived 처리하고 수정본을 살려두는 수집 설계와 정면으로 충돌한다.

경계: "선정 결과"·"결과 발표"는 실제 신청 대상이 아니므로 계속 제외되어야 한다.

실행: cd backend && python -m pytest test_notice_keyword_false_exclusion_unit.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# 케이비즈업 실제 프로필 (부산 / 응용SW 개발업)
P = {
    "industry_name": "응용 소프트웨어 개발 및 공급업",
    "industry_code": "58222",
    "address_city": "전국,부산",
    "certifications": "",
    "revenue_bracket": "1억 미만",
    "employee_count_bracket": "5인~10인",
    "interests": "AI도입,R&D,DX",
}


def _ad(title, ann_id=1):
    """하드필터 입력 최소 형태 (DB 미사용)."""
    return {
        "announcement_id": ann_id,
        "title": title,
        "region": "All",
        "summary_text": "",
        "target_type": "business",
    }


def _run(title):
    from app.core.matcher import _hard_filter_business
    passed, excluded = _hard_filter_business([_ad(title)], P, None)
    reasons = excluded[0]["reasons"] if excluded else []
    return passed, reasons


# ─────────────────────────────────────────────────────────────
# 오탈락: 수정·변경·정정 공고는 신청 가능한 정본이다
# ─────────────────────────────────────────────────────────────
def test_수정공고는_지원사업으로_통과한다():
    passed, reasons = _run("전 국민 AI 서비스 보편적 활용 지원 (모두의 AI) 사업 수정 공고")
    assert len(passed) == 1, f"수정 공고가 제외됨: {reasons}"


def test_변경공고는_지원사업으로_통과한다():
    passed, reasons = _run("2026년 해외규격인증획득지원사업(전략지원) 참여기업 모집 변경 공고")
    assert len(passed) == 1, f"변경 공고가 제외됨: {reasons}"


def test_정정공고는_지원사업으로_통과한다():
    passed, reasons = _run("2026년 창업도약패키지 창업기업 모집 정정 공고")
    assert len(passed) == 1, f"정정 공고가 제외됨: {reasons}"


def test_팁스_수정공고는_지원사업으로_통과한다():
    passed, reasons = _run("2026년 팁스(TIPS) 창업기업 지원계획 수정 공고")
    assert len(passed) == 1, f"팁스 수정 공고가 제외됨: {reasons}"


def test_변경계획_공고는_지원사업으로_통과한다():
    passed, reasons = _run("2026년 중소기업육성자금 융자지원 변경계획 공고")
    assert len(passed) == 1, f"변경계획 공고가 제외됨: {reasons}"


def test_재공고는_지원사업으로_통과한다():
    passed, reasons = _run("2026년 수혜기업 모집 재공고 안내")
    assert len(passed) == 1, f"재공고가 제외됨: {reasons}"


# ─────────────────────────────────────────────────────────────
# 경계 유지: 결과 발표성 공고는 계속 제외되어야 한다
# ─────────────────────────────────────────────────────────────
def test_선정결과_공고는_계속_제외된다():
    passed, reasons = _run("2026년 창업성장기술개발사업 선정 결과 공고")
    assert len(passed) == 0, "선정 결과 공고가 통과됨"
    assert any("공지성" in r for r in reasons), f"공지성 사유가 아님: {reasons}"


def test_결과발표_공고는_계속_제외된다():
    passed, reasons = _run("2026년 지원사업 최종 결과 발표")
    assert len(passed) == 0, "결과 발표 공고가 통과됨"
    assert any("공지성" in r for r in reasons), f"공지성 사유가 아님: {reasons}"


def test_합격자발표_공고는_계속_제외된다():
    passed, reasons = _run("2026년 교육과정 합격자 발표")
    assert len(passed) == 0, "합격자 발표 공고가 통과됨"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
