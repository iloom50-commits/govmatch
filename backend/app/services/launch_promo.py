"""선착순 런칭 프로모션 — 가입 선착순 N명에게 PRO 1개월 무료 부여 (순수 로직).

DB·과금 없이, "이미 부여된 인원수"만 받아 부여 여부/페이로드를 결정한다.
상한 enforce(동시성)는 호출 측에서 트랜잭션 + advisory lock으로 처리한다.
"""

import datetime
import os

# 선착순 상한·기간 — 정책 변경 시 여기만 수정
LAUNCH_PROMO_TAG = "launch10"
LAUNCH_PROMO_CAP = 10
LAUNCH_PROMO_DAYS = 30


def launch_promo_code() -> str:
    """파일럿 프로모션 코드. Railway env `LAUNCH_PROMO_CODE`로 변경 가능(기본 2222)."""
    return os.getenv("LAUNCH_PROMO_CODE", "2222")


def launch_promo_redeem(submitted_code, now: datetime.datetime) -> dict | None:
    """제출 코드가 프로모션 코드와 일치하면 PRO 부여 페이로드, 아니면 None.
    상한 없음 — 코드 보유 여부가 곧 제한(랜덤 가입 누수 차단).

    Returns: {"plan": "pro", "expires_at": <isoformat>, "tag": LAUNCH_PROMO_TAG} | None
    """
    if not submitted_code or str(submitted_code).strip() != launch_promo_code():
        return None
    expires = now + datetime.timedelta(days=LAUNCH_PROMO_DAYS)
    return {"plan": "pro", "expires_at": expires.isoformat(), "tag": LAUNCH_PROMO_TAG}


def partner_promo_redeem(row, submitted_code, now: datetime.datetime) -> dict | None:
    """promo_codes 테이블 행(row) 기반 파트너 코드 판정 (순수 로직 — DB 조회는 호출 측).

    row: {"code","partner_name","plan_days","max_uses","used_count","expires_at","active"} | None
    expires_at은 datetime 또는 ISO 문자열 허용. max_uses/expires_at이 None이면 무제한/무기한.

    Returns: {"plan": "pro", "expires_at": <isoformat>, "tag": "partner:<파트너명|코드>"} | None
    """
    if not row or not submitted_code:
        return None
    if str(submitted_code).strip() != str(row.get("code") or "").strip():
        return None
    if not row.get("active"):
        return None
    exp = row.get("expires_at")
    if exp is not None:
        if isinstance(exp, str):
            exp = datetime.datetime.fromisoformat(exp)
        if now > exp:
            return None
    max_uses = row.get("max_uses")
    if max_uses is not None and (row.get("used_count") or 0) >= max_uses:
        return None
    days = int(row.get("plan_days") or 30)
    expires = now + datetime.timedelta(days=days)
    tag = f"partner:{row.get('partner_name') or row.get('code')}"
    return {"plan": "pro", "expires_at": expires.isoformat(), "tag": tag}


def launch_promo_grant(current_count: int, now: datetime.datetime) -> dict | None:
    """이미 부여된 인원(current_count)이 상한 미만이면 부여 페이로드, 아니면 None.

    Returns: {"plan": "pro", "expires_at": <isoformat>, "tag": LAUNCH_PROMO_TAG} | None
    """
    if current_count >= LAUNCH_PROMO_CAP:
        return None
    expires = now + datetime.timedelta(days=LAUNCH_PROMO_DAYS)
    return {"plan": "pro", "expires_at": expires.isoformat(), "tag": LAUNCH_PROMO_TAG}
