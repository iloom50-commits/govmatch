# -*- coding: utf-8 -*-
"""send_transactional_push: 09~18시 게이트 없음 + 임의 title/body/url 발송 검증."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_URL", "postgresql://t:t@localhost/t")
os.environ.setdefault("VAPID_PRIVATE_KEY", "x")
os.environ.setdefault("VAPID_CLAIMS_EMAIL", "mailto:a@b.c")

import app.services.notification_service as ns


class _Cur:
    def __init__(self, subs): self._subs = subs; self._r = None
    def execute(self, sql, params=None):
        if "FROM push_subscriptions" in sql:
            self._r = self._subs
    def fetchall(self): return self._r or []
    def close(self): pass

class _Conn:
    def __init__(self, subs): self._c = _Cur(subs)
    def cursor(self): return self._c
    def commit(self): pass
    def close(self): pass


def test_transactional_push_no_time_gate(monkeypatch):
    subs = [{"endpoint": "https://e/1", "p256dh": "k", "auth": "a"}]
    monkeypatch.setattr(ns.psycopg2, "connect", lambda *a, **k: _Conn(subs))
    sent_payloads = []
    def _fake_webpush(**kw):
        sent_payloads.append(kw["data"])
    import types
    fake_mod = types.SimpleNamespace(webpush=_fake_webpush, WebPushException=Exception)
    monkeypatch.setitem(sys.modules, "pywebpush", fake_mod)

    svc = ns.NotificationService()
    sent = svc.send_transactional_push("111-11-11111", "제목", "본문", "/?consult=abc&aid=1")

    assert sent == 1, "시간대와 무관하게 1건 발송되어야 함"
    assert "제목" in sent_payloads[0]
    assert "/?consult=abc&aid=1" in sent_payloads[0]
