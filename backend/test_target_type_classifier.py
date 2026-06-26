"""target_type 분류기 — 소관기관(department) 기반 사업자 판정 단위 테스트.

사업자 전담기관(소진공·중진공·기보·신보) 소관 공고는 출처가 개인피드(gov24-individual-api)
여도 business로 확정한다. 복지기관·서민금융은 individual 유지.
"""

from app.services.patrol.target_type_classifier import _apply_source_override


def test_business_agency_dept_overrides_individual_feed():
    # 소상공인시장진흥공단 = 사업자 전담 → 개인피드여도 business (소상공인=사업자)
    items = [{"id": 1, "origin_source": "gov24-individual-api",
              "department": "소상공인시장진흥공단", "title": "혁신성장촉진자금"}]
    forced, remaining = _apply_source_override(items)
    assert forced.get(1) == "business"
    assert remaining == []


def test_kibo_business_agency():
    items = [{"id": 3, "origin_source": "gov24-api",
              "department": "기술보증기금", "title": "예비창업자 사전보증"}]
    forced, _ = _apply_source_override(items)
    assert forced.get(3) == "business"


def test_welfare_dept_stays_individual():
    # 복지기관 소관 + 개인피드 → individual 유지 (비사업자 개인)
    items = [{"id": 2, "origin_source": "gov24-individual-api",
              "department": "보건복지부", "title": "장애인 자립자금 대여"}]
    forced, remaining = _apply_source_override(items)
    assert forced.get(2) == "individual"


def test_seomin_finance_stays_individual():
    # 서민금융진흥원(개인 생활자금) → individual 유지
    items = [{"id": 5, "origin_source": "gov24-individual-api",
              "department": "서민금융진흥원", "title": "햇살론119"}]
    forced, _ = _apply_source_override(items)
    assert forced.get(5) == "individual"


def test_broad_ministry_goes_to_gemini():
    # 중기부(범위 넓음)는 결정적 강제 대상 아님 → Gemini 판단(remaining)으로 넘김
    items = [{"id": 4, "origin_source": "scraper:gov24",
              "department": "중소벤처기업부", "title": "해외인력 취업매칭 지원"}]
    forced, remaining = _apply_source_override(items)
    assert 4 not in forced
    assert len(remaining) == 1


def test_missing_department_falls_back_to_source_rules():
    # department 없을 때 기존 출처 규칙 그대로 동작 (하위호환)
    items = [{"id": 6, "origin_source": "bizinfo-api", "title": "중소기업 R&D"}]
    forced, _ = _apply_source_override(items)
    assert forced.get(6) == "business"
