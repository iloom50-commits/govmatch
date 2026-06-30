"""선착순 런칭 프로모션 — 가입 선착순 N명에게 PRO 1개월 무료 부여 (순수 로직).

DB·과금 없이, "이미 부여된 인원수"만 받아 부여 여부/페이로드를 결정한다.
상한 enforce(동시성)는 호출 측에서 트랜잭션 + advisory lock으로 처리한다.
"""

import datetime

# 선착순 상한·기간 — 정책 변경 시 여기만 수정
LAUNCH_PROMO_TAG = "launch10"
LAUNCH_PROMO_CAP = 10
LAUNCH_PROMO_DAYS = 30


def launch_promo_grant(current_count: int, now: datetime.datetime) -> dict | None:
    """이미 부여된 인원(current_count)이 상한 미만이면 부여 페이로드, 아니면 None.

    Returns: {"plan": "pro", "expires_at": <isoformat>, "tag": LAUNCH_PROMO_TAG} | None
    """
    if current_count >= LAUNCH_PROMO_CAP:
        return None
    expires = now + datetime.timedelta(days=LAUNCH_PROMO_DAYS)
    return {"plan": "pro", "expires_at": expires.isoformat(), "tag": LAUNCH_PROMO_TAG}
