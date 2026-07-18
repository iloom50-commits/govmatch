# -*- coding: utf-8 -*-
"""공개 목록 정렬 보조 (순수 로직, DB 비의존).

로그인 사용자가 지역·카테고리·검색 필터를 걸면 개인화가 꺼지고 마감순으로 떨어지던
문제를 위해, 관심분야 매칭 공고를 먼저 오게 하는 ORDER BY 조각을 만든다.
"""


def interest_priority_order(interests):
    """관심 우선 정렬 조각 생성. 반환: (order_fragment, params).

    관심 매칭(title/category ILIKE) 공고는 0, 아니면 1 → ASC로 매칭 우선.
    조각은 ORDER BY 중간에 끼우도록 콤마로 끝난다. 관심 없으면 ('', []).
    """
    kws = [k.strip() for k in (interests or []) if k and k.strip()]
    if not kws:
        return "", []
    conds = " OR ".join("title ILIKE %s OR category ILIKE %s" for _ in kws)
    fragment = f"CASE WHEN {conds} THEN 0 ELSE 1 END,"
    params = []
    for kw in kws:
        like = f"%{kw}%"
        params += [like, like]
    return fragment, params
