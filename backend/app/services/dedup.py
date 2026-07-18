# -*- coding: utf-8 -*-
"""후처리 중복 아카이브 판정 (순수 로직, DB 비의존).

수집(공식 API + scraper)이 같은 공고를 이중 저장하는 문제의 근본 정리.
main.py 구 _deduplicate_announcements(하드DELETE·지역무시·소스우선순위없음)를 대체.

핵심:
  - 보수적 정규화(괄호 보존) — 지역/날짜/대상이 괄호로 구분되는 별개 공고 오삭제 방지.
  - 개인 공고는 (제목,지역), 기업 공고는 (제목,'*')로 그룹.
  - 소스 우선순위: 공식API(0) < 수기/기관(1) < scraper(2). 우선순위 높은 1건 보존.
  - 동순위는 최신(created_at) 보존.
아카이브는 소프트(is_archived=TRUE) — 하드삭제 금지 정책 준수.
"""
import re as _re

_INDIVIDUAL_SOURCES = ("gov24-individual-api", "local-welfare-api", "gov24-api")
_OFFICIAL_EXTRA = ("mss-direct", "semas_biz")


def normalize_title(title: str) -> str:
    """보수적 제목 정규화: 공백 통일 + 소문자. 괄호는 보존(별개공고 구분자)."""
    t = (title or "").replace("　", " ").strip()
    t = _re.sub(r"\s+", " ", t)
    return t.lower()


def _source_head(origin_source: str) -> str:
    return (origin_source or "").split(":", 1)[0]


def is_individual(target_type, origin_source) -> bool:
    if target_type in ("individual", "both"):
        return True
    return _source_head(origin_source) in _INDIVIDUAL_SOURCES


def source_priority(origin_source) -> int:
    """작을수록 보존 우선. 공식API=0, 수기/기관=1, scraper=2."""
    s = _source_head(origin_source)
    if s.endswith("-api") or s in _OFFICIAL_EXTRA:
        return 0
    if "scrap" in s:
        return 2
    return 1


def select_archive_ids(rows):
    """중복 그룹에서 보존 1건을 뺀 나머지 announcement_id 목록 반환.

    2-패스 그룹핑: ① 제목으로 묶고 ② 그 안에 개인 공고 멤버가 하나라도 있으면
    지역으로 세분한다. scraper 복사본이 target_type=None이라 개인으로 인식되지
    않아 공식(개인)과 다른 키가 되던 누수를 막는다.
    보존 기준: 소스 우선순위(작은 것) → 최신(created_at 큰 것).
    """
    by_title = {}
    for r in rows:
        nt = normalize_title(r.get("title"))
        if len(nt) < 4:
            continue
        by_title.setdefault(nt, []).append(r)

    groups = {}
    for nt, title_members in by_title.items():
        cluster_is_individual = any(
            is_individual(r.get("target_type"), r.get("origin_source")) for r in title_members
        )
        for r in title_members:
            key = (nt, r.get("region")) if cluster_is_individual else (nt, "*")
            groups.setdefault(key, []).append(r)

    archive = []
    for members in groups.values():
        if len(members) < 2:
            continue
        keeper = min(
            members,
            key=lambda r: (source_priority(r.get("origin_source")), -(r.get("created_at") or 0)),
        )
        for r in members:
            if r["announcement_id"] != keeper["announcement_id"]:
                archive.append(r["announcement_id"])
    return archive
