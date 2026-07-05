# -*- coding: utf-8 -*-
"""P2-2 수집단 마감정보 손실 근본해결 — 배선(정적) 테스트.

FABLE 근본설계(scratchpad/p2_2_collection_design.md) 2026-07-05.
수집단에 '마감 원문' 개념이 없어 파서가 실패하면 원문을 버린 채 NULL 저장하던 것을,
중앙 헬퍼 parse_deadline + 저장 관문 일원화 + 원문/기록자 보존으로 근본 차단.

이 파일은 단계별로 확장된다(P2-2a..f). 각 단계 구현 전 해당 assert가 RED여야 한다.

실행: cd backend && python test_deadline_capture_wiring_unit.py
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

import app.main as m
import app.services.sync_service as ss
import app.services.public_api_service as pas


# ── P2-2a: 컬럼 2개 추가 (ADD-only) ──
def test_migration_adds_raw_text_and_source_columns():
    src = inspect.getsource(m.init_database)
    assert "ADD COLUMN IF NOT EXISTS deadline_raw_text VARCHAR(200)" in src, \
        "deadline_raw_text 컬럼 마이그레이션 없음(원문 보존 불가)"
    assert "ADD COLUMN IF NOT EXISTS deadline_source VARCHAR(20)" in src, \
        "deadline_source 컬럼 마이그레이션 없음(기록자 귀속 불가)"


# ── P2-2c: sync 관문 통합 + kised 필드명 + gov24/bizinfo raw ──
def test_sync_gateway_uses_parse_deadline_and_stores_raw():
    src = inspect.getsource(ss)
    assert "parse_deadline" in src, "sync 관문이 중앙 파서 미사용(제각각 파싱 잔존)"
    assert "deadline_raw_text, deadline_source" in src, "INSERT에 원문/기록자 컬럼 없음"
    assert "'collect'" in src, "deadline_source='collect' 기록 없음"
    assert "deadline_raw_text = CASE" in src, "업서트 원문 보존(CASE) 없음"
    assert "deadline_source = COALESCE" in src, "업서트 기록자 보존(COALESCE) 없음"


def test_kised_real_field_name_wired():
    src = inspect.getsource(pas)
    assert "pbanc_rcpt_end_dt" in src, "kised 실제 마감 필드명 미연결(99% NULL 지속)"


def test_gov24_bizinfo_kised_pass_deadline_raw():
    src = inspect.getsource(pas)
    n = src.count('"deadline_raw"')
    assert n >= 4, "파서 raw 전달 부족: %d곳(kised2+bizinfo+gov24x2 기대)" % n


# ── P2-2d: tier1 저장부 통합 + gov24_scraper 수리 ──
def test_tier1_base_uses_parse_deadline():
    import app.services.scrapers.tier1.base as t1base
    src = inspect.getsource(t1base.BaseScraper._save_item)
    assert "parse_deadline" in src, "tier1 base가 중앙 파서 미사용(이분법 잔존)"
    assert "deadline_raw_text" in src and "deadline_source" in src, "tier1 INSERT에 원문/기록자 없음"
    assert '"fixed" if item.get("deadline_date") else "unknown"' not in src, "tier1 이분법 deadline_type 잔존"


def test_gov24_scraper_reads_deadline_field():
    import app.services.scrapers.tier1.gov24_scraper as gov24s
    src = inspect.getsource(gov24s)
    assert "신청기한" in src, "gov24_scraper가 신청기한 미판독(98.9% NULL 지속)"
    assert "gov24는 마감일 필드 없음" not in src, "틀린 주석 잔존"


# ── P2-2e: admin_scraper 되돌림 가드 (P0-1 패턴 현존 버그 수리) ──
def test_admin_scraper_deadline_reversal_guard():
    import app.services.admin_scraper as adm
    src = inspect.getsource(adm.AdminScraper._save_to_db)
    assert "deadline_date=COALESCE(%s, deadline_date)" in src, \
        "admin UPDATE 되돌림 가드 없음(AI None이 기존 마감 파괴)"


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
