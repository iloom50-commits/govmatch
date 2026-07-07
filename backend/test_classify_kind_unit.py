# -*- coding: utf-8 -*-
"""첨부 kind 분류 — PDF 포함 확정 규칙 (신청서 버튼 게이팅 스펙 2026-07-07) 단위 테스트.

SmartDoc이 PDF 신청서도 자동작성 가능 → 키워드 없는 PDF도 신청서양식 후보.
기존엔 PDF=공고문이라 키워드 없는 PDF 신청서를 놓쳤음.

실행: cd backend && python test_classify_kind_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from app.services.attachments import _classify_kind


# (filename, ext, 기대 kind) — 전부 실제 공고 첨부 명명 패턴
CASES = [
    ("2026년 사업 신청서.pdf", "pdf", "신청서양식"),   # 키워드 PDF (기존도 통과)
    ("신청서.hwp", "hwp", "신청서양식"),                # 키워드 hwp
    ("모집공고문.pdf", "pdf", "공고문"),                # 공고 키워드 → 공고문
    ("붙임1.hwp", "hwp", "붙임서식"),                   # 붙임 키워드
    ("사업계획서.hwp", "hwp", "사업계획서양식"),          # 사업계획 키워드
    ("document.pdf", "pdf", "신청서양식"),              # ★ 키워드 없는 PDF → 신청서양식 (기존엔 공고문=RED)
    ("서식모음.hwp", "hwp", "붙임서식"),                # 서식 키워드
    ("template.docx", "docx", "신청서양식"),            # 키워드 없는 편집문서 (기존도 통과)
]


def test_classify_kind_pdf_included():
    for fn, ext, expected in CASES:
        got = _classify_kind(fn, ext)
        assert got == expected, "입력 (%r, %r) → %r 기대이나 %r" % (fn, ext, expected, got)


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
