# -*- coding: utf-8 -*-
"""비지원 공고(행정처분·검사결과 등) 제목 판정 — 단위 테스트 (TDD, DB 불필요).

_cleanup_non_support_announcements의 인라인 판정을 순수함수로 분리하고
행정처분 계열 고정밀 키워드를 추가한다. EXCEPTIONS(모집·신청 등)는 지원공고 보호.
실행: cd backend && python test_content_filter_unit.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

from app.services.content_filter import is_non_support_title


def test_admin_disposition_is_non_support():
    assert is_non_support_title("종합건설사업자 행정처분(영업정지) 공고문(제2026-1959호)") is True


def test_penalty_is_non_support():
    assert is_non_support_title("가맹사업법 위반 과태료 독촉고지 공시송달 공고") is True


def test_radiation_check_is_non_support():
    assert is_non_support_title("제주산 수산물 방사능 일일 검사 결과(6.15.)") is True


def test_berth_allocation_is_non_support():
    assert is_non_support_title("2026년 국제크루즈 선석배정 변경내역 알림(‘26. 6. 15.)") is True


def test_support_program_kept():
    assert is_non_support_title("2026년 중소기업 육성자금 지원사업 모집 공고") is False


def test_exception_overrides_pattern():
    # 행정처분이 들어가도 '모집'(지원공고 신호)이 있으면 보호
    assert is_non_support_title("행정처분 관련 소상공인 재기 지원 참여기업 모집") is False


def test_existing_pattern_still_matches():
    assert is_non_support_title("2025년 업무추진비 사용내역 공개") is True


def test_normal_support_no_false_positive():
    assert is_non_support_title("청년 창업 패키지 참여기업 모집") is False


def test_empty_title_is_not_non_support():
    assert is_non_support_title("") is False
    assert is_non_support_title(None) is False


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
