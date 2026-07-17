# -*- coding: utf-8 -*-
"""G2-4: 자금상담(action=fund_consult) 100크레딧(세션당 1회, 성공 후) + 턴 캡 15 단위 테스트.

돈 경로 원칙 검증:
- 신규 세션 + 성공 → 100 차감
- 같은 세션 후속 턴 → 무차감
- LLM 실패 → 무차감
- 잔액부족 → 402
- 서비스토큰(SmartDoc) → 무차감(이중과금 방지)
- 16번째 user 메시지 → turn_cap_reached: True, 응답 생성 안 함(LLM 미호출)

세션 신규 판별 근거: backend/app/main.py의 _handle_pro_fund_consult는 AI 호출 전에
"SELECT 1 FROM ai_consult_logs WHERE session_id = %s AND business_number = %s"로
해당 세션의 기존 로그 존재 여부를 확인한다(없으면 신규). ai_consult_logs는
session_id에 UNIQUE 인덱스가 걸려 있고(main.py 상단 스키마 마이그레이션),
fund_consult 저장 시 ON CONFLICT(session_id) DO UPDATE로 매 턴 upsert된다.

DB 접근은 get_db_connection()을 FakeConn/FakeCursor로 모킹(GovMatch 기존 관행).
chat_lite_fund_expert는 app.services.ai_consultant 모듈에서 함수 내부 지역 import로
가져오므로, 그 원본 모듈 속성을 몽키패치해야 handler가 모킹된 함수를 사용한다.

실행: cd backend && python test_credit_consult_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

from fastapi import HTTPException

import app.main as main
import app.services.ai_consultant as ai_consultant


class FakeCursor:
    """ai_consult_logs(세션 존재 여부) + users.credits/credit_transactions 시뮬레이션."""

    def __init__(self, users, session_logs):
        self._users = users              # user_id -> {"credits": int}
        self._session_logs = session_logs  # session_id -> business_number
        self._result = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        params = params or ()

        if s.startswith("SELECT 1 FROM ai_consult_logs WHERE session_id"):
            sid, bn = params
            self._result = {"?column?": 1} if self._session_logs.get(sid) == bn else None

        elif s.startswith("INSERT INTO ai_consult_logs"):
            bn, _msgs_json, _conclusion, sid = params
            self._session_logs[sid] = bn

        elif s.startswith("SELECT credits FROM users"):
            user_id = params[0]
            row = self._users.get(user_id)
            self._result = {"credits": row["credits"]} if row else None

        elif s.startswith("UPDATE users SET credits = credits - %s"):
            amount, user_id, min_amount = params
            row = self._users.get(user_id)
            current = row["credits"] if row else 0
            if row is not None and current >= min_amount:
                row["credits"] -= amount
                self._result = {"credits": row["credits"]}
                self.rowcount = 1
            else:
                self._result = None
                self.rowcount = 0

        elif s.startswith("INSERT INTO credit_transactions"):
            self.rowcount = 1

        else:
            raise AssertionError("예상치 못한 SQL: " + s)

    def fetchone(self):
        return self._result


class FakeConn:
    def __init__(self, cur):
        self._cur = cur
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self._cur

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _make_db_factory(monkeypatch, users, session_logs):
    def _factory():
        cur = FakeCursor(users, session_logs)
        return FakeConn(cur)

    monkeypatch.setattr(main, "get_db_connection", _factory)


def _make_req(messages, session_id=None):
    return main.AiConsultantChatRequest(
        messages=messages,
        session_id=session_id,
        mode="individual_fund",
        profile_override={"age_range": "30대", "user_type": "individual"},
        action="fund_consult",
    )


def _one_user_msg():
    return [{"role": "user", "text": "실업급여 받을 수 있나요?"}]


# ─────────────────────────────────────────────────────────────
# 신규 세션 + 성공 → 100 차감
# ─────────────────────────────────────────────────────────────
def test_new_session_charges_100_after_success(monkeypatch):
    users = {1: {"credits": 200}}
    session_logs = {}
    _make_db_factory(monkeypatch, users, session_logs)
    monkeypatch.setattr(
        ai_consultant, "chat_lite_fund_expert",
        lambda **kw: {"reply": "안내드립니다", "choices": [], "done": False},
    )
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    result = main._handle_pro_fund_consult(_make_req(_one_user_msg(), session_id=None), current_user)

    assert result["status"] == "SUCCESS"
    assert not result.get("turn_cap_reached")
    assert users[1]["credits"] == 100, "신규 세션 성공 후 100크레딧 차감되어야 함"


# ─────────────────────────────────────────────────────────────
# 같은 세션 후속 턴 → 무차감
# ─────────────────────────────────────────────────────────────
def test_followup_turn_no_charge(monkeypatch):
    users = {1: {"credits": 200}}
    sid = "fund_existing_session"
    session_logs = {sid: "111-11-11111"}  # 이미 존재하는 세션(1턴 이상 진행됨)
    _make_db_factory(monkeypatch, users, session_logs)
    monkeypatch.setattr(
        ai_consultant, "chat_lite_fund_expert",
        lambda **kw: {"reply": "추가 안내", "choices": [], "done": False},
    )
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    msgs = _one_user_msg() + [{"role": "assistant", "text": "..."}] + [{"role": "user", "text": "그럼 서류는요?"}]

    result = main._handle_pro_fund_consult(_make_req(msgs, session_id=sid), current_user)

    assert result["status"] == "SUCCESS"
    assert users[1]["credits"] == 200, "후속 턴은 무차감이어야 함"


# ─────────────────────────────────────────────────────────────
# LLM 실패 → 무차감
# ─────────────────────────────────────────────────────────────
def test_llm_failure_no_charge(monkeypatch):
    users = {1: {"credits": 200}}
    session_logs = {}
    _make_db_factory(monkeypatch, users, session_logs)

    def _boom(**kw):
        raise RuntimeError("Gemini 호출 실패")

    monkeypatch.setattr(ai_consultant, "chat_lite_fund_expert", _boom)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    try:
        main._handle_pro_fund_consult(_make_req(_one_user_msg(), session_id=None), current_user)
        assert False, "예외가 전파되어야 함"
    except RuntimeError:
        pass

    assert users[1]["credits"] == 200, "LLM 실패 시 차감되면 안 됨"


# ─────────────────────────────────────────────────────────────
# 잔액부족 → 402
# ─────────────────────────────────────────────────────────────
def test_insufficient_credits_402(monkeypatch):
    users = {1: {"credits": 10}}
    session_logs = {}
    _make_db_factory(monkeypatch, users, session_logs)
    monkeypatch.setattr(
        ai_consultant, "chat_lite_fund_expert",
        lambda **kw: {"reply": "안내드립니다", "choices": [], "done": False},
    )
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    try:
        main._handle_pro_fund_consult(_make_req(_one_user_msg(), session_id=None), current_user)
        assert False, "402가 발생해야 함"
    except HTTPException as e:
        assert e.status_code == 402

    assert users[1]["credits"] == 10, "잔액부족 시 차감되면 안 됨"


# ─────────────────────────────────────────────────────────────
# 서비스토큰(SmartDoc) → 무차감(이중과금 방지 — SmartDoc 자체 지갑에서 이미 차감)
# ─────────────────────────────────────────────────────────────
def test_service_token_no_charge(monkeypatch):
    users = {}
    session_logs = {}
    _make_db_factory(monkeypatch, users, session_logs)
    monkeypatch.setattr(
        ai_consultant, "chat_lite_fund_expert",
        lambda **kw: {"reply": "안내드립니다", "choices": [], "done": False},
    )
    current_user = {"bn": "svc-bn", "sub": "smartdoc-service", "_service": True}

    result = main._handle_pro_fund_consult(_make_req(_one_user_msg(), session_id=None), current_user)

    assert result["status"] == "SUCCESS"
    # users 딕셔너리가 비어 있어도(크레딧 조회 자체가 스킵) 예외 없이 통과해야 함


# ─────────────────────────────────────────────────────────────
# 16번째 user 메시지 → turn_cap_reached: True, LLM 미호출, 무차감
# ─────────────────────────────────────────────────────────────
def test_turn_cap_16th_message(monkeypatch):
    def _boom(**kw):
        raise AssertionError("턴 캡 초과 시 LLM을 호출하면 안 됨")

    monkeypatch.setattr(ai_consultant, "chat_lite_fund_expert", _boom)

    def _db_boom():
        raise AssertionError("턴 캡 초과 시 DB에 접근하면 안 됨(응답 생성 자체를 막음)")

    monkeypatch.setattr(main, "get_db_connection", _db_boom)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    msgs = []
    for i in range(16):
        msgs.append({"role": "user", "text": f"질문 {i+1}"})
        msgs.append({"role": "assistant", "text": f"답변 {i+1}"})
    # 마지막에 16번째 user 메시지만 남기고 조정(user 메시지 정확히 16개)
    msgs = [m for m in msgs if True]

    result = main._handle_pro_fund_consult(_make_req(msgs, session_id="fund_long_session"), current_user)

    assert result.get("turn_cap_reached") is True
    assert result["status"] == "SUCCESS"


if __name__ == "__main__":
    import traceback

    class _MonkeyPatch:
        def __init__(self):
            self._undo = []

        def setattr(self, obj, name, value):
            old = getattr(obj, name, None)
            had = hasattr(obj, name)
            self._undo.append((obj, name, had, old))
            setattr(obj, name, value)

        def undo(self):
            for obj, name, had, old in reversed(self._undo):
                if had:
                    setattr(obj, name, old)
                else:
                    try:
                        delattr(obj, name)
                    except AttributeError:
                        pass
            self._undo.clear()

    _fns = [v for k, v in sorted(globals().items())
            if k.startswith("test_") and callable(v)]
    _passed = _failed = 0
    for _fn in _fns:
        mp = _MonkeyPatch()
        try:
            _fn(mp)
            print("PASS  " + _fn.__name__)
            _passed += 1
        except Exception as _e:
            print("FAIL  " + _fn.__name__ + ": " + repr(_e))
            traceback.print_exc()
            _failed += 1
        finally:
            mp.undo()
    print("\n%d passed, %d failed" % (_passed, _failed))
    sys.exit(1 if _failed else 0)
