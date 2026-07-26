"""메일 신호(인프라 알림) 분류·저장·수집분석 — AI COO 인프라 상태 섹션용.

Apps Script가 넘긴 알림을 mail_signals에 저장(멱등)하고, 일일 supervisor가
규칙 기반으로 진단·조치힌트를 산출. LLM·Gmail 의존 없음(순수 규칙).
"""
from __future__ import annotations
import re
from typing import Dict, Any, List

_SERVICE_DOMAINS = {
    "railway": ("railway.app", "railway.com"),
    "vercel": ("vercel.com",),
    "supabase": ("supabase.io", "supabase.com"),
}
_HIGH_KW = re.compile(
    r"fail|error|outage|past\s*due|billing|exceeded|down|payment|suspend|limit\s*reached",
    re.IGNORECASE,
)
_ACTION = {
    "railway": "Railway 대시보드 배포 로그 확인 · 최근 커밋 롤백 검토(백엔드 자동배포 정상)",
    "vercel": "Vercel 빌드 로그 확인 · 자동배포 정체 이력 있음 → 필요시 CLI 수동배포",
    "supabase": "Supabase 커넥션/egress/과금 확인 · 커넥션풀 점검",
    "other": "발신 서비스·내용 직접 확인 필요",
}

def classify_service(sender: str) -> str:
    s = (sender or "").lower()
    for svc, domains in _SERVICE_DOMAINS.items():
        if any(d in s for d in domains):
            return svc
    return "other"

def estimate_severity(subject: str, snippet: str) -> str:
    text = f"{subject or ''} {snippet or ''}"
    return "high" if _HIGH_KW.search(text) else "info"

def action_hint(service: str) -> str:
    return _ACTION.get(service, _ACTION["other"])

def store_mail_signal(db_conn, payload: Dict[str, Any]) -> bool:
    """Apps Script 페이로드를 mail_signals에 저장(멱등). 신규 True / 중복 False."""
    msg_id = (payload.get("msg_id") or "").strip()
    if not msg_id:
        return False
    sender = payload.get("from") or ""
    subject = payload.get("subject") or ""
    snippet = payload.get("snippet") or ""
    service = classify_service(sender)
    severity = estimate_severity(subject, snippet)
    received_at = payload.get("date") or None
    cur = db_conn.cursor()
    cur.execute(
        """INSERT INTO mail_signals
             (gmail_msg_id, received_at, sender, subject, snippet, service, severity, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
           ON CONFLICT (gmail_msg_id) DO NOTHING
           RETURNING id""",
        (msg_id, received_at, sender[:300], subject[:500], snippet[:1000], service, severity),
    )
    row = cur.fetchone()
    db_conn.commit()
    return bool(row)

def validate_mail_signal(secret_header, body, expected_secret):
    """(ok, http_status, error). 시크릿·필수필드 검증."""
    if not expected_secret or secret_header != expected_secret:
        return (False, 401, "invalid secret")
    if not isinstance(body, dict) or not (body.get("msg_id") and body.get("from")):
        return (False, 400, "missing required fields")
    return (True, 200, None)

def collect_mail_signals(db_conn) -> Dict[str, Any]:
    """최근 24h 미분석 신호 → 규칙 기반 진단. {count, high[], by_service{}}.
    0건이면 분석 스킵. 처리분은 analyzed_at 마킹."""
    cur = db_conn.cursor()
    cur.execute(
        """SELECT id, service, severity, subject, snippet, received_at
           FROM mail_signals
           WHERE analyzed_at IS NULL
             AND created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
           ORDER BY severity DESC, id DESC"""
    )
    rows = cur.fetchall() or []
    if not rows:
        return {"count": 0, "high": [], "by_service": {}}

    high: List[Dict[str, Any]] = []
    by_service: Dict[str, int] = {}
    ids: List[int] = []
    for r in rows:
        rid = r["id"] if isinstance(r, dict) else r[0]
        svc = (r["service"] if isinstance(r, dict) else r[1]) or "other"
        sev = (r["severity"] if isinstance(r, dict) else r[2]) or "info"
        subj = (r["subject"] if isinstance(r, dict) else r[3]) or ""
        ids.append(rid)
        by_service[svc] = by_service.get(svc, 0) + 1
        if sev == "high":
            high.append({"service": svc, "subject": subj[:120], "action": action_hint(svc)})

    if ids:
        cur.execute(
            "UPDATE mail_signals SET analyzed_at = CURRENT_TIMESTAMP WHERE id = ANY(%s)",
            (ids,),
        )
        db_conn.commit()
    return {"count": len(rows), "high": high, "by_service": by_service}
