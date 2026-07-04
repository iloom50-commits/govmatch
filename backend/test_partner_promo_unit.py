# -*- coding: utf-8 -*-
"""파트너 프로모션 코드(promo_codes 테이블) 리딤 — 순수 로직 단위 테스트.

실행(스크립트 스타일, pytest 불필요):
    cd backend && python test_partner_promo_unit.py
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

NOW = datetime.datetime(2026, 7, 4, 12, 0, 0)


def _row(**kw):
    base = {
        "code": "INS2026", "partner_name": "보험사A", "plan_days": 30,
        "max_uses": None, "used_count": 0, "expires_at": None, "active": True,
    }
    base.update(kw)
    return base


# ─────────────────────────────────────────────────────────────
# partner_promo_redeem — promo_codes 행 기반 부여 판정
# ─────────────────────────────────────────────────────────────
def test_partner_valid_grant():
    from app.services.launch_promo import partner_promo_redeem
    g = partner_promo_redeem(_row(), "INS2026", NOW)
    assert g is not None
    assert g["plan"] == "pro"
    assert g["tag"] == "partner:보험사A"
    assert g["expires_at"] == (NOW + datetime.timedelta(days=30)).isoformat()


def test_partner_plan_days_respected():
    from app.services.launch_promo import partner_promo_redeem
    g = partner_promo_redeem(_row(plan_days=90), "INS2026", NOW)
    assert g["expires_at"] == (NOW + datetime.timedelta(days=90)).isoformat()


def test_partner_code_whitespace_tolerant():
    from app.services.launch_promo import partner_promo_redeem
    assert partner_promo_redeem(_row(), "  INS2026  ", NOW) is not None


def test_partner_wrong_code_rejected():
    from app.services.launch_promo import partner_promo_redeem
    assert partner_promo_redeem(_row(), "WRONG", NOW) is None


def test_partner_inactive_rejected():
    from app.services.launch_promo import partner_promo_redeem
    assert partner_promo_redeem(_row(active=False), "INS2026", NOW) is None


def test_partner_expired_rejected():
    from app.services.launch_promo import partner_promo_redeem
    assert partner_promo_redeem(
        _row(expires_at=NOW - datetime.timedelta(days=1)), "INS2026", NOW) is None


def test_partner_not_yet_expired_ok():
    from app.services.launch_promo import partner_promo_redeem
    assert partner_promo_redeem(
        _row(expires_at=NOW + datetime.timedelta(days=1)), "INS2026", NOW) is not None


def test_partner_expires_at_iso_string_ok():
    from app.services.launch_promo import partner_promo_redeem
    assert partner_promo_redeem(
        _row(expires_at=(NOW + datetime.timedelta(days=1)).isoformat()), "INS2026", NOW) is not None


def test_partner_max_uses_reached_rejected():
    from app.services.launch_promo import partner_promo_redeem
    assert partner_promo_redeem(_row(max_uses=10, used_count=10), "INS2026", NOW) is None


def test_partner_max_uses_under_ok():
    from app.services.launch_promo import partner_promo_redeem
    assert partner_promo_redeem(_row(max_uses=10, used_count=9), "INS2026", NOW) is not None


def test_partner_none_row_rejected():
    from app.services.launch_promo import partner_promo_redeem
    assert partner_promo_redeem(None, "INS2026", NOW) is None


def test_partner_empty_code_rejected():
    from app.services.launch_promo import partner_promo_redeem
    assert partner_promo_redeem(_row(), "", NOW) is None
    assert partner_promo_redeem(_row(), None, NOW) is None


def test_partner_tag_falls_back_to_code():
    """partner_name 비어있으면 코드로 태그 구성 (추적 가능성 유지)."""
    from app.services.launch_promo import partner_promo_redeem
    g = partner_promo_redeem(_row(partner_name=""), "INS2026", NOW)
    assert g["tag"] == "partner:INS2026"


# ─────────────────────────────────────────────────────────────
# 레거시 env 코드(launch_promo_redeem) 회귀 — 기존 보험사 코드 계속 동작
# ─────────────────────────────────────────────────────────────
def test_legacy_env_code_still_works():
    os.environ["LAUNCH_PROMO_CODE"] = "9999"
    from app.services.launch_promo import launch_promo_redeem, LAUNCH_PROMO_TAG
    g = launch_promo_redeem("9999", NOW)
    assert g is not None and g["plan"] == "pro" and g["tag"] == LAUNCH_PROMO_TAG
    assert launch_promo_redeem("0000", NOW) is None


# ─────────────────────────────────────────────────────────────
# 스크립트 러너
# ─────────────────────────────────────────────────────────────
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
