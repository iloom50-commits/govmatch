# -*- coding: utf-8 -*-
"""구조적 가드(작업3): 관심 태그 정합성.

막는 클래스: seed(_INTEREST_TAG_SEED_BIZ)에 태그·그룹을 추가했는데 매칭 쪽 별칭
(_INTEREST_GROUP_TO_KEY) 또는 리터럴 허용목록(_INTEREST_LITERAL_GROUPS)에 반영을 빠뜨려,
그 태그가 조용히 리터럴로만 검색되며 사실상 매칭 안 되는 것. (이번 결함이 정확히 이 클래스.)

불변식: _INTEREST_TAG_SEED_BIZ의 모든 태그는 매칭에서 '해석 가능'하다 —
  (1) 태그가 곧 INTEREST_KEYWORD_MAP 키이거나,
  (2) 그룹이 별칭으로 유효한 키에 연결되거나,
  (3) 그룹이 리터럴 허용목록(업종·인증·수요)에 명시적으로 등재.
셋 중 무엇도 아니면 실패 → 새 그룹을 추가할 때 키 연결/리터럴 결정을 강제한다.

실행: cd backend && python -m pytest test_interest_tag_alias_guard.py -q --no-header
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _uninterpretable(group_to_key: dict, literal_groups: set) -> list:
    """주어진 별칭·리터럴 정책으로 해석 불가능한 (태그, 그룹) 목록. 역검증에서 재사용."""
    from app.core.interest_tags import _INTEREST_TAG_SEED_BIZ
    from app.core.matcher import INTEREST_KEYWORD_MAP
    bad = []
    for tag, group in _INTEREST_TAG_SEED_BIZ:
        if tag in INTEREST_KEYWORD_MAP:
            continue
        key = group_to_key.get(group)
        if key and key in INTEREST_KEYWORD_MAP:
            continue
        if group in literal_groups:
            continue
        bad.append((tag, group))
    return bad


def test_every_biz_seed_tag_interpretable():
    """모든 seed 태그가 (직접 키 | 그룹 별칭 | 리터럴 허용) 중 하나로 해석 가능."""
    from app.core.matcher import _INTEREST_GROUP_TO_KEY, _INTEREST_LITERAL_GROUPS
    bad = _uninterpretable(_INTEREST_GROUP_TO_KEY, _INTEREST_LITERAL_GROUPS)
    assert not bad, (
        f"해석 불가능한 seed 태그 {len(bad)}건 — 그룹이 키 별칭도 리터럴 허용목록도 아님. "
        f"새 그룹은 _INTEREST_GROUP_TO_KEY에 키를 연결하거나 _INTEREST_LITERAL_GROUPS에 등재하라:\n"
        + "\n".join(f"  {t} (그룹={g})" for t, g in bad)
    )


def test_alias_values_are_valid_keys():
    """별칭이 가리키는 키가 INTEREST_KEYWORD_MAP에 실제 존재해야 한다(오타 방지)."""
    from app.core.matcher import INTEREST_KEYWORD_MAP, _INTEREST_GROUP_TO_KEY
    bad = {g: k for g, k in _INTEREST_GROUP_TO_KEY.items() if k not in INTEREST_KEYWORD_MAP}
    assert not bad, f"존재하지 않는 키를 가리키는 별칭(오타): {bad}"


def test_no_group_both_aliased_and_literal():
    """한 그룹이 별칭과 리터럴 양쪽에 동시에 들어가지 않는다(정책 모호성 방지)."""
    from app.core.matcher import _INTEREST_GROUP_TO_KEY, _INTEREST_LITERAL_GROUPS
    overlap = set(_INTEREST_GROUP_TO_KEY) & _INTEREST_LITERAL_GROUPS
    assert not overlap, f"별칭·리터럴에 동시 등재된 그룹: {overlap}"
