# -*- coding: utf-8 -*-
"""상담 엔드포인트 서비스 토큰 인증(_get_consult_user) 단위 테스트 — DB/LLM 불필요.

SmartDoc이 GovMatch PRO 자금상담을 서버-투-서버로 호출할 때 쓰는
aud 스코프 서비스 토큰(aud=pro-consult, purpose=service, bn 포함)을 검증한다.

핵심 보안 속성: aud=pro-consult 토큰은 일반 유저 경로(_get_current_user/_decode_jwt,
aud 미검증)에서 InvalidAudienceError로 탈락 → 다른 사용자 엔드포인트 재생 불가.

실행: cd backend && python test_consult_service_auth.py  (pytest로도 가능)
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import jwt as _jwt


def _svc_token(secret, aud="pro-consult", purpose="service", bn="1234500001",
               sub="smartdoc-service", ttl=120, exp=None):
    now = datetime.datetime.utcnow()
    payload = {
        "aud": aud, "purpose": purpose, "sub": sub, "bn": bn,
        "iat": now,
        "exp": exp if exp is not None else now + datetime.timedelta(seconds=ttl),
    }
    return _jwt.encode(payload, secret, algorithm="HS256")


def _user_token(secret, bn="9876500002"):
    """일반 유저 세션 토큰(aud 없음) — _create_jwt 형태 모사."""
    now = datetime.datetime.utcnow()
    payload = {
        "user_id": 7, "bn": bn, "email": "u@example.com", "plan": "pro",
        "trial_ends_at": None, "exp": now + datetime.timedelta(hours=1),
    }
    return _jwt.encode(payload, secret, algorithm="HS256")


def _expect_401(fn):
    from fastapi import HTTPException
    try:
        fn()
    except HTTPException as e:
        assert e.status_code == 401, f"expected 401, got {e.status_code}"
        return
    raise AssertionError("expected HTTPException(401), none raised")


def test_service_token_accepted():
    from app.main import _get_consult_user, JWT_SECRET
    u = _get_consult_user(f"Bearer {_svc_token(JWT_SECRET)}")
    assert u["bn"] == "1234500001", u
    assert u.get("_service") is True, u


def test_normal_user_token_accepted():
    from app.main import _get_consult_user, JWT_SECRET
    u = _get_consult_user(f"Bearer {_user_token(JWT_SECRET)}")
    assert u["bn"] == "9876500002", u
    assert not u.get("_service"), u


def test_service_token_rejected_on_normal_path():
    # 핵심 보안: 서비스 토큰(aud=pro-consult)은 일반 유저 인증 경로에서 탈락해야 함
    from app.main import _get_current_user, JWT_SECRET
    _expect_401(lambda: _get_current_user(f"Bearer {_svc_token(JWT_SECRET)}"))


def test_service_token_wrong_aud_rejected():
    from app.main import _get_consult_user, JWT_SECRET
    _expect_401(lambda: _get_consult_user(f"Bearer {_svc_token(JWT_SECRET, aud='smartdoc')}"))


def test_service_token_wrong_purpose_rejected():
    from app.main import _get_consult_user, JWT_SECRET
    _expect_401(lambda: _get_consult_user(f"Bearer {_svc_token(JWT_SECRET, purpose='handoff')}"))


def test_service_token_missing_bn_rejected():
    from app.main import _get_consult_user, JWT_SECRET
    _expect_401(lambda: _get_consult_user(f"Bearer {_svc_token(JWT_SECRET, bn='')}"))


def test_expired_service_token_rejected():
    from app.main import _get_consult_user, JWT_SECRET
    past = datetime.datetime.utcnow() - datetime.timedelta(seconds=30)
    _expect_401(lambda: _get_consult_user(f"Bearer {_svc_token(JWT_SECRET, exp=past)}"))


def test_wrong_secret_rejected():
    from app.main import _get_consult_user
    _expect_401(lambda: _get_consult_user(f"Bearer {_svc_token('a-different-secret')}"))


def test_no_or_malformed_token_rejected():
    from app.main import _get_consult_user
    _expect_401(lambda: _get_consult_user(None))
    _expect_401(lambda: _get_consult_user("Token abc"))
    _expect_401(lambda: _get_consult_user("Bearer not-a-jwt"))


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
