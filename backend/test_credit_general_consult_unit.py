# -*- coding: utf-8 -*-
"""G2.5: 일반 유저 상담 크레딧 전환 + 저장/알림 무료 + PRO 잔재 정리 단위 테스트.

돈 경로 원칙(모든 상담 경로 공통):
- 잔액부족은 LLM 호출 전에 402(원가 낭비 방지)
- 차감은 LLM 성공 이후, 신규 세션에만
- LLM 실패 시 무차감
- 면제 계정(서비스토큰/허용목록) 무차감

DB 접근은 get_db_connection()을 FakeConn/FakeCursor로 모킹(GovMatch 기존 관행).
LLM은 원본 서비스 모듈 속성을 몽키패치(핸들러가 함수 내부 지역 import로 가져오므로).

실행: cd backend && PYTHONIOENCODING=utf-8 python test_credit_general_consult_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("GEMINI_API_KEY", "")  # 실제 네트워크 호출 방지

from fastapi import HTTPException

import app.main as main
import app.services.ai_consultant as ai_consultant


# ─────────────────────────────────────────────────────────────
# 공용 Fake DB
# ─────────────────────────────────────────────────────────────
def _default_profile(bn):
    return {
        "business_number": bn,
        "plan": "free",
        "user_type": "business",
        "email": "u@example.com",
        "ai_usage_month": 0,
        "ai_usage_reset_at": None,
        "plan_expires_at": None,
        "company_name": "테스트기업",
        "industry_code": "62",
        "address_city": "서울",
        "interests": "창업",
        "age_range": "",
        "revenue_bracket": "",
        "employee_count_bracket": "",
        "establishment_date": "",
        "gender": "",
        "income_level": "",
        "family_type": "",
        "employment_status": "",
        "housing_status": "",
        "certifications": "",
        "custom_keywords": "",
    }


def _default_ann():
    return {
        "announcement_id": 123,
        "title": "테스트 공고",
        "department": "중기부",
        "category": "정책자금",
        "support_amount": "1억",
        "deadline_date": None,
        "summary_text": "요약",
        "region": "서울",
        "eligibility_logic": "",
        "origin_url": "http://example.com",
        "target_type": "business",
    }


class FakeCursor:
    """credits/consult_sessions/announcements/ai_consult_logs 등을 관대하게 시뮬레이션.

    - credit 관련 SQL은 정확히 처리(차감 검증의 정확성 확보).
    - 그 외는 관대한 기본값(None/[]) 반환 — 대형 엔드포인트의 부수 쿼리를 통과시킴.
    """

    def __init__(self, state):
        self.state = state
        self._result = None
        self._rows = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        p = params or ()

        if s.startswith("SELECT credits FROM users"):
            uid = p[0]
            row = self.state["users"].get(uid)
            self._result = {"credits": row["credits"]} if row else None

        elif s.startswith("UPDATE users SET credits = credits - %s"):
            amount, uid, min_amount = p
            row = self.state["users"].get(uid)
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

        elif s.startswith("SELECT * FROM users WHERE business_number") or \
                s.startswith("SELECT plan, ai_usage_month") or \
                s.startswith("SELECT plan, ai_usage_reset_at") or \
                s.startswith("SELECT plan, plan_expires_at FROM users"):
            self._result = dict(self.state["profile"])

        elif s.startswith("SELECT id FROM consult_sessions"):
            sid = p[0]
            self._result = {"id": 1} if sid in self.state.get("existing_sessions", set()) else None

        elif s.startswith("INSERT INTO consult_sessions"):
            self.rowcount = 1

        elif s.startswith("SELECT announcement_id, title, department, category"):
            self._result = dict(self.state.get("ann", _default_ann()))

        elif s.startswith("INSERT INTO ai_consult_logs"):
            self.rowcount = 1
            self._result = {"id": 1}

        elif s.startswith("INSERT INTO saved_announcements"):
            self.rowcount = 1

        elif s.startswith("UPDATE users SET ai_usage_month"):
            self.rowcount = 1

        else:
            # 관대한 기본값 (mention search, pro_consult_sessions update 등)
            self._result = None
            self._rows = []

    def fetchone(self):
        return self._result

    def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, state):
        self._state = state
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return FakeCursor(self._state)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _patch_db(monkeypatch, state):
    monkeypatch.setattr(main, "get_db_connection", lambda: FakeConn(state))


def _ok_reply(*a, **k):
    return {"reply": "안내드립니다", "choices": [], "announcements": [], "matched": [], "done": False}


def _boom(*a, **k):
    raise RuntimeError("LLM 호출 실패")


# ═════════════════════════════════════════════════════════════
# Task G2.5-1: /api/ai/chat 자금상담 → 100크레딧
# ═════════════════════════════════════════════════════════════
def _chat_req(messages, session_id=None):
    return main.AiChatRequest(messages=messages, mode="business_fund", session_id=session_id)


def _one_user():
    return [{"role": "user", "text": "창업 지원금 뭐가 있나요?"}]


def test_ai_chat_new_session_charges_100_after_success(monkeypatch):
    state = {"users": {1: {"credits": 300}}, "profile": _default_profile("111-11-11111")}
    _patch_db(monkeypatch, state)
    monkeypatch.setattr(ai_consultant, "chat_lite_fund_expert", _ok_reply)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    result = main.api_ai_chat(_chat_req(_one_user()), current_user)

    assert result["status"] == "SUCCESS"
    assert state["users"][1]["credits"] == 200, "첫 메시지·성공 후 100크레딧 차감되어야 함"


def test_ai_chat_followup_no_charge(monkeypatch):
    state = {"users": {1: {"credits": 300}}, "profile": _default_profile("111-11-11111")}
    _patch_db(monkeypatch, state)
    monkeypatch.setattr(ai_consultant, "chat_lite_fund_expert", _ok_reply)
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    msgs = _one_user() + [{"role": "assistant", "text": "..."}] + [{"role": "user", "text": "그럼 서류는요?"}]

    result = main.api_ai_chat(_chat_req(msgs), current_user)

    assert result["status"] == "SUCCESS"
    assert state["users"][1]["credits"] == 300, "후속 턴(is_first_message=False)은 무차감이어야 함"


def test_ai_chat_insufficient_402_before_llm(monkeypatch):
    state = {"users": {1: {"credits": 50}}, "profile": _default_profile("111-11-11111")}
    _patch_db(monkeypatch, state)

    def _must_not_call(*a, **k):
        raise AssertionError("잔액부족 시 LLM을 호출하면 안 됨")

    monkeypatch.setattr(ai_consultant, "chat_lite_fund_expert", _must_not_call)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    try:
        main.api_ai_chat(_chat_req(_one_user()), current_user)
        assert False, "402가 발생해야 함"
    except HTTPException as e:
        assert e.status_code == 402

    assert state["users"][1]["credits"] == 50, "잔액부족 시 차감되면 안 됨"


def test_ai_chat_llm_failure_no_charge(monkeypatch):
    state = {"users": {1: {"credits": 300}}, "profile": _default_profile("111-11-11111")}
    _patch_db(monkeypatch, state)
    monkeypatch.setattr(ai_consultant, "chat_lite_fund_expert", _boom)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    try:
        main.api_ai_chat(_chat_req(_one_user()), current_user)
        assert False, "예외가 전파되어야 함"
    except RuntimeError:
        pass

    assert state["users"][1]["credits"] == 300, "LLM 실패 시 차감되면 안 됨"


def test_ai_chat_turn_cap_15(monkeypatch):
    state = {"users": {1: {"credits": 300}}, "profile": _default_profile("111-11-11111")}
    _patch_db(monkeypatch, state)

    def _must_not_call(*a, **k):
        raise AssertionError("턴 캡 초과 시 LLM을 호출하면 안 됨")

    monkeypatch.setattr(ai_consultant, "chat_lite_fund_expert", _must_not_call)
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    msgs = []
    for i in range(16):
        msgs.append({"role": "user", "text": f"질문{i+1}"})
        msgs.append({"role": "assistant", "text": f"답변{i+1}"})

    result = main.api_ai_chat(_chat_req(msgs, session_id="chat_long"), current_user)

    assert result.get("turn_cap_reached") is True
    assert result["status"] == "SUCCESS"
    assert state["users"][1]["credits"] == 300, "턴 캡 도달 시 무차감"


def test_ai_chat_exempt_account_no_charge(monkeypatch):
    state = {"users": {}, "profile": _default_profile("svc-bn")}
    _patch_db(monkeypatch, state)
    monkeypatch.setattr(ai_consultant, "chat_lite_fund_expert", _ok_reply)
    current_user = {"bn": "svc-bn", "sub": "smartdoc-service", "_service": True}

    result = main.api_ai_chat(_chat_req(_one_user()), current_user)

    assert result["status"] == "SUCCESS"  # users 비어도 크레딧 조회 스킵으로 통과


# ═════════════════════════════════════════════════════════════
# Task G2.5-2: /api/ai/consult 공고상담 → 50크레딧
# ═════════════════════════════════════════════════════════════
import app.services.doc_analysis_service as doc_analysis_service


def _consult_req(messages, session_id=None, announcement_id=123):
    return main.AiConsultRequest(announcement_id=announcement_id, messages=messages, session_id=session_id)


def _patch_consult_llm(monkeypatch, fn=None):
    monkeypatch.setattr(doc_analysis_service, "ensure_analysis", lambda *a, **k: {})
    monkeypatch.setattr(
        ai_consultant, "chat_consult",
        fn or (lambda **k: {"reply": "지원 가능성이 있습니다", "choices": [], "done": False, "conclusion": None}),
    )


def test_ai_consult_new_session_charges_50(monkeypatch):
    state = {"users": {1: {"credits": 300}}, "profile": _default_profile("111-11-11111"), "existing_sessions": set()}
    _patch_db(monkeypatch, state)
    _patch_consult_llm(monkeypatch)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    result = main.api_ai_consult(_consult_req(_one_user(), session_id=None), current_user)

    assert result["status"] == "SUCCESS"
    assert state["users"][1]["credits"] == 250, "신규 세션·성공 후 50크레딧 차감되어야 함"


def test_ai_consult_existing_session_no_charge(monkeypatch):
    sid = "sess-existing"
    state = {"users": {1: {"credits": 300}}, "profile": _default_profile("111-11-11111"),
             "existing_sessions": {sid}}
    _patch_db(monkeypatch, state)
    _patch_consult_llm(monkeypatch)
    current_user = {"user_id": 1, "bn": "111-11-11111"}
    msgs = _one_user() + [{"role": "assistant", "text": "..."}] + [{"role": "user", "text": "추가 질문"}]

    result = main.api_ai_consult(_consult_req(msgs, session_id=sid), current_user)

    assert result["status"] == "SUCCESS"
    assert state["users"][1]["credits"] == 300, "기존 세션(추가 질문)은 무차감이어야 함"


def test_ai_consult_insufficient_402_before_llm(monkeypatch):
    state = {"users": {1: {"credits": 30}}, "profile": _default_profile("111-11-11111"), "existing_sessions": set()}
    _patch_db(monkeypatch, state)

    def _must_not_call(**k):
        raise AssertionError("잔액부족 시 chat_consult를 호출하면 안 됨")

    _patch_consult_llm(monkeypatch, fn=_must_not_call)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    try:
        main.api_ai_consult(_consult_req(_one_user(), session_id=None), current_user)
        assert False, "402가 발생해야 함"
    except HTTPException as e:
        assert e.status_code == 402

    assert state["users"][1]["credits"] == 30, "잔액부족 시 차감되면 안 됨"


def test_ai_consult_llm_failure_no_charge(monkeypatch):
    state = {"users": {1: {"credits": 300}}, "profile": _default_profile("111-11-11111"), "existing_sessions": set()}
    _patch_db(monkeypatch, state)

    def _boom_consult(**k):
        raise RuntimeError("chat_consult 실패")

    _patch_consult_llm(monkeypatch, fn=_boom_consult)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    result = main.api_ai_consult(_consult_req(_one_user(), session_id=None), current_user)

    # 엔드포인트는 예외를 내부에서 삼키고 폴백 응답을 반환하지만 과금은 하지 않아야 함
    assert result["status"] == "SUCCESS"
    assert state["users"][1]["credits"] == 300, "LLM 실패 시 차감되면 안 됨"


def test_ai_consult_exempt_no_charge(monkeypatch):
    state = {"users": {}, "profile": _default_profile("svc-bn"), "existing_sessions": set()}
    _patch_db(monkeypatch, state)
    _patch_consult_llm(monkeypatch)
    current_user = {"bn": "svc-bn", "sub": "smartdoc-service", "_service": True}

    result = main.api_ai_consult(_consult_req(_one_user(), session_id=None), current_user)

    assert result["status"] == "SUCCESS"


# ═════════════════════════════════════════════════════════════
# 러너
# ═════════════════════════════════════════════════════════════
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
