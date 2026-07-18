# -*- coding: utf-8 -*-
"""임베딩 섀도우 관측 하네스 — 단위 테스트 (TDD).

A안(얇은 관측): mode=shadow면 규칙 결과를 그대로 반환하고, 임베딩을 병행 실행해
[emb_shadow] 구조화 로그만 남긴다(반환값 불변). 전체 하이브리드 합집합은 다음 단계.
실행: cd backend && python test_embedding_shadow_unit.py
"""
import os, sys, io, contextlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

from app.core import matcher as m

P = {"user_type": "business", "region": "전국", "industry_name": "", "interests": ""}
RULE = [
    {"announcement_id": 10, "title": "청년 창업 지원사업", "region": "전국"},
    {"announcement_id": 11, "title": "소상공인 경영개선 지원", "region": "전국"},
]


def _patch(rule_ret, emb_ret):
    orig = (m.get_matches_for_user, m.get_individual_matches_for_user,
            m.get_matches_by_embedding, m.get_db_connection)
    m.get_matches_for_user = lambda profile: [dict(r) for r in rule_ret]
    m.get_individual_matches_for_user = lambda profile: [dict(r) for r in rule_ret]
    m.get_matches_by_embedding = lambda profile, top_k=50, target_type_filter=None: [dict(c) for c in emb_ret]
    def _no_db(*a, **k):
        raise RuntimeError("no db in unit test")
    m.get_db_connection = _no_db
    return orig


def _restore(orig):
    (m.get_matches_for_user, m.get_individual_matches_for_user,
     m.get_matches_by_embedding, m.get_db_connection) = orig
    os.environ.pop("EMBEDDING_MATCHING_MODE", None)
    os.environ.pop("USE_EMBEDDING_MATCHING", None)


def test_off_mode_is_default_rule_path():
    orig = _patch(RULE, [])
    try:
        os.environ.pop("EMBEDDING_MATCHING_MODE", None)
        res = m.get_matches_hybrid(P, is_individual=False, skip_bucket=True)
        assert res == RULE, res
    finally:
        _restore(orig)


def test_shadow_mode_returns_rule_results_unchanged():
    emb = [{"announcement_id": 99, "title": "전혀 다른 공고", "region": "전국", "similarity": 0.71}]
    orig = _patch(RULE, emb)
    try:
        os.environ["EMBEDDING_MATCHING_MODE"] = "shadow"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            res = m.get_matches_hybrid(P, is_individual=False, skip_bucket=True)
        out = buf.getvalue()
        assert res == RULE, res                 # 규칙 결과 그대로(딥비교)
        assert "[emb_shadow]" in out, out       # 관측 로그 발생
    finally:
        _restore(orig)


def test_shadow_log_has_structured_fields():
    emb = [
        {"announcement_id": 99, "title": "전혀 다른 공고", "region": "전국", "similarity": 0.82},
        {"announcement_id": 11, "title": "소상공인 경영개선 지원", "region": "전국", "similarity": 0.75},
    ]
    orig = _patch(RULE, emb)
    try:
        os.environ["EMBEDDING_MATCHING_MODE"] = "shadow"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m.get_matches_hybrid(P, is_individual=False, skip_bucket=True)
        line = [l for l in buf.getvalue().splitlines() if l.startswith("[emb_shadow]")][0]
        payload = json.loads(line[len("[emb_shadow] "):])
        for k in ("rule_n", "emb_n", "top20_overlap", "sim_p50", "sim_p90", "ms"):
            assert k in payload, (k, payload)
        assert payload["rule_n"] == 2 and payload["emb_n"] == 2
        assert payload["top20_overlap"] == 1  # "소상공인 경영개선 지원" 겹침
    finally:
        _restore(orig)


def test_shadow_embedding_failure_does_not_break_return():
    orig = _patch(RULE, [])
    try:
        m.get_matches_by_embedding = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("emb api down"))
        os.environ["EMBEDDING_MATCHING_MODE"] = "shadow"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            res = m.get_matches_hybrid(P, is_individual=False, skip_bucket=True)
        assert res == RULE, res  # 임베딩이 죽어도 규칙 결과 정상 반환
    finally:
        _restore(orig)


def test_use_embedding_flag_still_means_on():
    # 하위호환: 구 USE_EMBEDDING_MATCHING=true는 on 별칭 → 임베딩 후보로 대체
    emb = [{"announcement_id": 99, "title": "임베딩 후보", "region": "전국", "similarity": 0.9}]
    orig = _patch(RULE, emb)
    try:
        os.environ.pop("EMBEDDING_MATCHING_MODE", None)
        os.environ["USE_EMBEDDING_MATCHING"] = "true"
        res = m.get_matches_hybrid(P, is_individual=False, skip_bucket=True)
        ids = {r["announcement_id"] for r in res}
        assert ids == {99}, res  # 규칙(10,11)이 아니라 임베딩(99)
    finally:
        _restore(orig)


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p = f = 0
    for fn in fns:
        try:
            fn(); print("PASS  " + fn.__name__); p += 1
        except Exception as e:
            print("FAIL  " + fn.__name__ + ": " + repr(e)); traceback.print_exc(); f += 1
    print("\n%d passed, %d failed" % (p, f))
    sys.exit(1 if f else 0)
