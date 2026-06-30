"""선착순 런칭 프로모션 부여 로직 단위 테스트 (순수 함수, DB 불필요)."""

import datetime

from app.services.launch_promo import (
    launch_promo_grant,
    LAUNCH_PROMO_CAP,
    LAUNCH_PROMO_TAG,
    LAUNCH_PROMO_DAYS,
)

NOW = datetime.datetime(2026, 6, 30, 9, 0, 0)


def test_grants_pro_when_no_one_redeemed_yet():
    g = launch_promo_grant(0, NOW)
    assert g is not None
    assert g["plan"] == "pro"
    assert g["tag"] == LAUNCH_PROMO_TAG
    # 만료는 가입 시점 + LAUNCH_PROMO_DAYS
    assert g["expires_at"] == (NOW + datetime.timedelta(days=LAUNCH_PROMO_DAYS)).isoformat()


def test_grants_at_the_last_available_slot():
    # 이미 CAP-1명 부여됨 → 마지막 1명은 받아야 함
    assert launch_promo_grant(LAUNCH_PROMO_CAP - 1, NOW) is not None


def test_no_grant_when_cap_exactly_reached():
    assert launch_promo_grant(LAUNCH_PROMO_CAP, NOW) is None


def test_no_grant_when_cap_exceeded():
    assert launch_promo_grant(LAUNCH_PROMO_CAP + 3, NOW) is None
