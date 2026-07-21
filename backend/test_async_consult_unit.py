# -*- coding: utf-8 -*-
"""api_ai_consult 제출형 + _run_consult_job 워커: 즉시 반환·성공시에만 과금·실패 무차감."""
import os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://t:t@localhost/t")

import app.main as main
import app.services.ai_consultant as ai_consultant


class FakeCursor:
    def __init__(self, state):
        self.s = state; self._r = None; self.rowcount = 0
    def execute(self, sql, params=None):
        q = " ".join(sql.split()); p = params or ()
        if q.startswith("SELECT plan, ai_usage_month"):
            self._r = self.s["user_row"]
        elif q.startswith("SELECT plan, company_name"):
            self._r = self.s["user_row"]
        elif "FROM consult_sessions WHERE session_id" in q:
            self._r = {"id": 1} if self.s.get("existing_session") else None
        elif q.startswith("SELECT credits FROM users"):
            self._r = {"credits": self.s["users"].get(p[0], {}).get("credits", 0)}
        elif q.startswith("INSERT INTO consult_sessions"):
            pass
        elif q.startswith("INSERT INTO consult_jobs"):
            self.s["jobs"][p[0]] = {"status": "processing", "notify_requested": False, "notified": False}
            self.s["last_job"] = p[0]
        elif q.startswith("UPDATE consult_jobs SET status = 'done'"):
            jid = p[-1]; self.s["jobs"].setdefault(jid, {})["status"] = "done"
        elif q.startswith("UPDATE consult_jobs SET status = 'failed'"):
            jid = p[-1]; self.s["jobs"].setdefault(jid, {})["status"] = "failed"
        elif q.startswith("SELECT notify_requested"):
            j = self.s["jobs"].get(p[0], {})
            self._r = {"notify_requested": j.get("notify_requested", False), "notified": j.get("notified", False),
                       "session_id": "sid", "announcement_id": 1}
        elif "SELECT announcement_id, title" in q:
            self._r = {"announcement_id": 1, "title": "테스트공고", "origin_url": "http://x", "target_type": "business",
                       "department": "", "category": "", "support_amount": "", "deadline_date": None,
                       "summary_text": "", "region": "", "eligibility_logic": None}
        elif q.startswith("INSERT INTO ai_consult_logs"):
            self._r = {"id": 99}
        elif q.startswith("UPDATE users SET credits = credits - %s"):
            amount, uid, minamt = p
            u = self.s["users"].get(uid)
            if u and u["credits"] >= minamt:
                u["credits"] -= amount; self._r = {"credits": u["credits"]}; self.rowcount = 1
            else:
                self._r = None; self.rowcount = 0
        elif q.startswith("INSERT INTO credit_transactions"):
            self.rowcount = 1
        else:
            self._r = None
    def fetchone(self): return self._r
    def fetchall(self): return []
    def close(self): pass

class FakeConn:
    def __init__(self, state): self.s = state
    def cursor(self): return FakeCursor(self.s)
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


def _state(credits=200, existing=False):
    return {
        "users": {1: {"credits": credits}},
        "user_row": {"business_number": "111-11-11111", "user_type": "business", "company_name": "테스트",
                     "establishment_date": "", "address_city": "", "industry_code": "",
                     "revenue_bracket": "", "employee_count_bracket": "", "interests": "",
                     "age_range": "", "gender": "", "income_level": "", "family_type": "",
                     "employment_status": "", "housing_status": "", "plan": "free",
                     "ai_usage_month": 0, "ai_usage_reset_at": None, "plan_expires_at": None},
        "existing_session": existing, "jobs": {}, "last_job": None,
    }


def _patch_db(monkeypatch, state):
    monkeypatch.setattr(main, "get_db_connection", lambda: FakeConn(state))


def test_submit_returns_processing_immediately(monkeypatch):
    state = _state()
    _patch_db(monkeypatch, state)
    from fastapi import BackgroundTasks
    bt = BackgroundTasks()
    req = main.AiConsultRequest(announcement_id=1, messages=[{"role": "user", "text": "질문"}], session_id=None)
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    resp = main.api_ai_consult(req, background_tasks=bt, current_user=current_user)

    assert resp["status"] == "PROCESSING"
    assert resp["job_id"]
    assert resp["session_id"]
    assert len(bt.tasks) == 1, "백그라운드 워커가 1개 예약되어야 함"
    assert state["users"][1]["credits"] == 200, "제출 시점엔 차감 없음"


def test_worker_charges_only_on_success(monkeypatch):
    state = _state()
    _patch_db(monkeypatch, state)
    monkeypatch.setattr(ai_consultant, "chat_consult",
                        lambda **kw: {"reply": "결론", "choices": [], "done": True, "conclusion": "가능"})
    import app.services.doc_analysis_service as das
    monkeypatch.setattr(das, "ensure_analysis", lambda *a, **k: {})

    job_id = str(uuid.uuid4()); state["last_job"] = job_id
    state["jobs"][job_id] = {"status": "processing", "notify_requested": False, "notified": False}
    req = main.AiConsultRequest(announcement_id=1,
                                messages=[{"role": "user", "text": "1"}, {"role": "assistant", "text": "a"},
                                          {"role": "user", "text": "2"}, {"role": "assistant", "text": "b"},
                                          {"role": "user", "text": "3"}], session_id="sid")
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    main._run_consult_job(job_id, req, current_user, "sid", is_new_session=True)

    assert state["users"][1]["credits"] == 150, "신규 세션 성공 후 50 차감"
    assert state["jobs"][job_id]["status"] == "done"


def test_worker_no_charge_on_failure(monkeypatch):
    state = _state()
    _patch_db(monkeypatch, state)
    def _boom(**kw): raise RuntimeError("LLM 실패")
    monkeypatch.setattr(ai_consultant, "chat_consult", _boom)
    import app.services.doc_analysis_service as das
    monkeypatch.setattr(das, "ensure_analysis", lambda *a, **k: {})

    job_id = str(uuid.uuid4()); state["last_job"] = job_id
    state["jobs"][job_id] = {"status": "processing", "notify_requested": False, "notified": False}
    req = main.AiConsultRequest(announcement_id=1, messages=[{"role": "user", "text": "1"}], session_id="sid")
    current_user = {"user_id": 1, "bn": "111-11-11111"}

    main._run_consult_job(job_id, req, current_user, "sid", is_new_session=True)

    assert state["users"][1]["credits"] == 200, "LLM 실패 시 무차감"
