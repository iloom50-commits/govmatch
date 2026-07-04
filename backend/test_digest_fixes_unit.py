# -*- coding: utf-8 -*-
"""다이제스트 발송 결함 수정(FABLE 진단 2026-07-05, P1·P2·P3·P6) — 단위 테스트.

P1: 후보 SQL에 아카이브/마감불명 방어
P2: 공고 선정을 매칭 정본(get_matches_hybrid)으로 전환 (+both 사용자 병합)
P3: 수신거부 토큰/라우트/푸터 링크 + 옵트아웃 시 push·kakao도 중단
P6: notification-settings POST 인증

실행: cd backend && python test_digest_fixes_unit.py
"""
import os
import sys
import inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# ─────────────────────────────────────────────────────────────
# P1 — 후보 SQL 방어 (아카이브·마감불명)
# ─────────────────────────────────────────────────────────────
def test_p1_sql_has_archive_guard():
    from app.services import notification_service as ns
    src = inspect.getsource(ns.NotificationService.get_filtered_programs)
    assert "is_archived = FALSE" in src, "아카이브 공고 발송 방어 없음 (C-2)"
    assert "3 months" in src, "마감불명 공고 3개월 제한 없음 (C-2)"


# ─────────────────────────────────────────────────────────────
# P2 — 매칭 정본 전환
# ─────────────────────────────────────────────────────────────
def _matcher_row(aid, title="공고", status="eligible", score=80, **kw):
    base = {
        "announcement_id": aid, "title": title, "match_score": score,
        "eligibility_status": status, "recommendation_reason": "지원 자격 충족",
        "origin_url": f"https://x/{aid}", "support_amount": "1억",
        "deadline_date": "2026-08-01", "target_type": "business",
        "category": "정책자금", "department": "중기부",
    }
    base.update(kw)
    return base


def test_p2_cards_mapping():
    from app.services.notification_service import notification_service as svc
    cards = svc._matches_to_digest_cards([_matcher_row(1, title="테스트 공고")])
    assert len(cards) == 1
    c = cards[0]
    assert c["program_title"] == "테스트 공고"
    assert c["announcement_id"] == 1
    assert c["score"] == 80
    assert c["url"] == "https://x/1"
    assert c["deadline_date"] == "2026-08-01"


def test_p2_cards_exclude_ineligible_and_limit():
    from app.services.notification_service import notification_service as svc
    rows = [_matcher_row(i) for i in range(1, 15)]
    rows[2]["eligibility_status"] = "ineligible"
    cards = svc._matches_to_digest_cards(rows)
    assert len(cards) == 10, len(cards)
    assert all(c["announcement_id"] != 3 for c in cards), "ineligible 공고가 카드에 포함됨"


def test_p2_cards_skip_missing_id():
    from app.services.notification_service import notification_service as svc
    rows = [_matcher_row(None), _matcher_row(7)]
    cards = svc._matches_to_digest_cards(rows)
    assert [c["announcement_id"] for c in cards] == [7]


def test_p2_select_uses_matcher_and_merges_both():
    from app.services.notification_service import notification_service as svc
    from app.core import matcher as m
    calls = []
    orig = m.get_matches_hybrid
    try:
        def fake_hybrid(profile, is_individual=False, skip_bucket=False):
            calls.append(is_individual)
            if is_individual:
                return [_matcher_row(101, target_type="individual"), _matcher_row(1)]  # 1은 기업과 중복
            return [_matcher_row(1), _matcher_row(2)]
        m.get_matches_hybrid = fake_hybrid
        cards = svc._select_matches_via_matcher({"user_type": "both", "business_number": "999"})
        ids = [c["announcement_id"] for c in cards]
        assert calls == [False, True], calls          # 기업 + 개인 모두 호출 (M-4)
        assert ids == [1, 2, 101], ids                 # 중복(1) 제거·순서 유지
    finally:
        m.get_matches_hybrid = orig


def test_p2_select_business_only():
    from app.services.notification_service import notification_service as svc
    from app.core import matcher as m
    calls = []
    orig = m.get_matches_hybrid
    try:
        def fake_hybrid(profile, is_individual=False, skip_bucket=False):
            calls.append(is_individual)
            return [_matcher_row(5)]
        m.get_matches_hybrid = fake_hybrid
        cards = svc._select_matches_via_matcher({"user_type": "business"})
        assert calls == [False]
        assert len(cards) == 1
    finally:
        m.get_matches_hybrid = orig


def test_p2_digest_no_longer_uses_legacy_filter():
    from app.services import notification_service as ns
    src = inspect.getsource(ns.NotificationService.generate_daily_digest)
    assert "_select_matches_via_matcher" in src, "다이제스트가 매칭 정본을 사용하지 않음 (C-1)"
    assert "get_filtered_programs" not in src, "구 자체 SQL 선정 로직 잔존 (C-1)"
    assert "match_program_with_user" not in src, "구 점수 휴리스틱 잔존 (C-1)"


# ─────────────────────────────────────────────────────────────
# P3 — 수신거부
# ─────────────────────────────────────────────────────────────
def test_p3_token_roundtrip():
    from app.services.notification_service import make_unsubscribe_token, verify_unsubscribe_token
    t = make_unsubscribe_token("1234567890")
    assert isinstance(t, str) and len(t) >= 16
    assert verify_unsubscribe_token("1234567890", t) is True
    assert verify_unsubscribe_token("1234567890", "wrong") is False
    assert verify_unsubscribe_token("9999999999", t) is False
    assert verify_unsubscribe_token("", "") is False


def test_p3_footer_has_tokenized_link():
    from app.services import notification_service as ns
    src = inspect.getsource(ns.NotificationService._build_email_html)
    assert "unsubscribe?bn=" in src, "푸터 수신거부 링크가 토큰화되지 않음 (H-1: 기존 링크는 404)"


def test_p3_optout_kills_push_too():
    """is_active=0(명시적 수신거부)이면 push 구독이 있어도 대상에서 제외."""
    from app.services import notification_service as ns
    src = inspect.getsource(ns.NotificationService.get_target_users)
    assert "COALESCE(ns.is_active, 1) = 1" in src, "옵트아웃이 push/kakao 채널에 미적용"


def test_p3_unsubscribe_route_exists():
    import app.main as m
    assert hasattr(m, "api_unsubscribe"), "수신거부 라우트 없음 (H-1)"
    src = inspect.getsource(m.api_unsubscribe)
    assert "verify_unsubscribe_token" in src
    assert "is_active" in src


# ─────────────────────────────────────────────────────────────
# P6 — notification-settings POST 인증
# ─────────────────────────────────────────────────────────────
def test_p6_settings_post_requires_auth():
    import app.main as m
    sig = inspect.signature(m.api_save_notification_settings)
    assert "current_user" in sig.parameters, "무인증 잔존 (H-4)"
    src = inspect.getsource(m.api_save_notification_settings)
    assert "403" in src, "타인 bn 변조 차단 없음 (H-4)"


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
