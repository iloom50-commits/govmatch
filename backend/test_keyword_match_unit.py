# -*- coding: utf-8 -*-
"""keyword_match: 토큰화+동의어 매칭 헬퍼 단위 테스트."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.keyword_match import tokenize, expand_token, keyword_hit, build_match_sql, SYNONYM_MAP


def test_tokenize():
    assert tokenize("전문기관 모집") == ["전문기관", "모집"]
    assert tokenize("  창업  ") == ["창업"]
    assert tokenize("") == []

def test_expand_token_synonym():
    exp = expand_token("전문기관")
    assert "전문기관" in exp and "수행기관" in exp and "운영기관" in exp
    assert expand_token("바이오") == ["바이오"]

def test_keyword_hit_multiword_and_synonym():
    assert keyword_hit(["전문기관 모집"], "2026 수행기관 지정 공고") is True
    assert keyword_hit(["전문기관 모집"], "수행기관 컨설팅 지원") is False
    assert keyword_hit(["전문기관 모집"], "청년 창업 지원사업") is False

def test_keyword_hit_out_of_dict_word_still_matches():
    assert keyword_hit(["바이오"], "바이오헬스 창업기업 모집") is True
    assert keyword_hit(["바이오"], "제조 자동화 지원") is False

def test_keyword_hit_or_across_keywords():
    assert keyword_hit(["수출", "전문기관 모집"], "수출바우처 지원") is True

def test_keyword_hit_empty():
    assert keyword_hit([], "무엇이든") is False
    assert keyword_hit(["  "], "무엇이든") is False

def test_build_match_sql_structure():
    field = "(title || ' ' || COALESCE(category,''))"
    sql, params = build_match_sql(["전문기관 모집"], field)
    assert sql is not None
    assert " AND " in sql
    assert len(params) == 9  # 전문기관族(5) + 모집족(4)
    assert all(p.startswith("%") and p.endswith("%") for p in params)

def test_build_match_sql_empty():
    sql, params = build_match_sql([], "F")
    assert sql is None and params == []
