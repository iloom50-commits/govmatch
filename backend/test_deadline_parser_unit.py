# -*- coding: utf-8 -*-
"""parse_deadline 중앙 헬퍼(FABLE 근본설계 2026-07-05, 문제2 P2-2b) — 단위 테스트.

수집단 마감 파싱을 단일 함수로 중앙화: (date_iso|None, deadline_type, raw_text|None).
- 흩어진 마감 파싱 13벌·상시 키워드셋 3벌의 판정 불일치를 제거.
- 원문(raw_text)을 절대 버리지 않음 — 빈값만 None(진짜 부재의 측정 신호).
- 연도 없는 날짜는 날조하지 않음(unknown + raw 보존).

픽스처는 전부 소스 API 실측 표본에서 도출(날조 없음).
실행: cd backend && python test_deadline_parser_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from app.services.deadline_enricher import parse_deadline


# (입력, (기대 date, 기대 type)) — 전부 실측 유래
CASES = [
    ("20260713",                 ("2026-07-13", "fixed")),    # KISED YYYYMMDD
    ("2026-03-09 ~ 2026-03-27",  ("2026-03-27", "fixed")),    # bizinfo 기간→종료일
    ("2025.1.1.~2025.12.10.",    ("2025-12-10", "fixed")),    # gov24 완전기간
    ("예산 소진시까지",            (None, "ongoing")),          # bizinfo 개방형
    ("상시 접수",                 (None, "ongoing")),          # bizinfo
    ("상시신청",                  (None, "ongoing")),          # gov24
    ("○ 정기신청 : 5.1.~5.31.○ 반기신청 - 상반기분 신청 : 9.1.~9.15.",
                                  (None, "unknown")),          # gov24, 연도 없음 → 날조 금지
    ("99991231",                 (None, "ongoing")),          # welfare 무기한 관례
    ("2025- 3- 3",               ("2025-03-03", "fixed")),    # 기존 _normalize_date 회귀 보존
    ("2026-00-00",               (None, "unknown")),          # day/month=0 방어
    ("2024-01-01",               ("2024-01-01", "fixed")),    # 과거는 그대로(expired는 호출측)
    ("2026-07-01 ~",             (None, "unknown")),          # 종료일 없는 개방 범위
    ("2026-07-01 ~ 예산소진시",    (None, "ongoing")),          # 개방형 종료
    ("2026-12-01 ~ 2026-01-05",  (None, "unknown")),          # 역전 범위(이상) → 미상
]


def test_parse_deadline_cases():
    for raw, (exp_date, exp_type) in CASES:
        date, dtype, _raw = parse_deadline(raw)
        assert (date, dtype) == (exp_date, exp_type), \
            "입력 %r → (%r,%r) 기대이나 (%r,%r)" % (raw, exp_date, exp_type, date, dtype)


def test_raw_text_preserved_when_present():
    assert parse_deadline("20260713")[2] == "20260713", "정상 파싱에도 원문 보존해야(귀속)"
    assert parse_deadline("예산 소진시까지")[2] == "예산 소진시까지", "상시 원문 보존 안 됨"
    assert parse_deadline("○ 정기신청 : 5.1.~5.31.")[2] == "○ 정기신청 : 5.1.~5.31.", "미상 원문 보존 안 됨"


def test_raw_text_none_when_absent():
    # 빈값·None → raw_text None (진짜 부재의 측정 신호, n_absent)
    assert parse_deadline("") == (None, "unknown", None), "빈 문자열은 완전 부재로 신호해야"
    assert parse_deadline(None) == (None, "unknown", None), "None은 완전 부재로 신호해야"
    assert parse_deadline("   ") == (None, "unknown", None), "공백만도 완전 부재"


def test_raw_text_truncated_200():
    long_raw = "상" * 250
    _d, _t, raw = parse_deadline(long_raw)
    assert raw is not None and len(raw) == 200, "원문 200자 절단 안 됨: %r" % (None if raw is None else len(raw))


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
