"""정책자금 리포트 섹션 HTML 빌더 단위 테스트 (순수 함수, DB·AI 불필요)."""

from app.services.report_sections import build_fund_section_html


def test_empty_input_returns_empty_string():
    # 추천 본문도 없고 공고도 없으면 섹션 자체를 생략 (빈 문자열)
    assert build_fund_section_html("", []) == ""
    assert build_fund_section_html(None, None) == ""


def test_includes_header_and_announcement_fields():
    anns = [{
        "title": "중진공 신성장기반자금",
        "department": "중소벤처기업진흥공단",
        "support_amount": "최대 60억원",
        "deadline": "2026-08-31",
    }]
    html = build_fund_section_html("이 고객사는 신성장기반자금 신청이 가능합니다.", anns)
    assert "💰 맞춤 정책자금" in html       # 섹션 헤더
    assert "중진공 신성장기반자금" in html   # 공고명
    assert "중소벤처기업진흥공단" in html     # 주관기관
    assert "최대 60억원" in html             # 지원조건
    assert "2026-08-31" in html             # 마감


def test_reply_only_without_announcements_still_renders():
    # 공고는 못 찾았지만 AI 추천 본문이 있으면 섹션은 나와야 함
    html = build_fund_section_html("현재 조건에 맞는 정책자금 추천 내용입니다.", [])
    assert "💰 맞춤 정책자금" in html
    assert "추천 내용" in html


def test_escapes_html_in_reply_text():
    # 추천 본문 내 <, & 는 이스케이프되어야 함 (HTML 깨짐·주입 방지)
    html = build_fund_section_html("자기자본 < 매출 & 업력 조건 확인", [])
    assert "&lt;" in html
    assert "&amp;" in html


def test_markdown_bold_converted():
    html = build_fund_section_html("**핵심:** 운전자금 우선", [])
    assert "<strong>핵심:</strong>" in html


def test_missing_announcement_fields_use_fallbacks():
    # 일부 필드 누락 공고도 안전하게 렌더 (마감 없으면 '상시')
    anns = [{"title": "소상공인 정책자금"}]
    html = build_fund_section_html("추천", anns)
    assert "소상공인 정책자금" in html
    # 마감일·타입 미상 → '상시'로 단정하지 않고 '확인 필요'
    assert "확인 필요" in html


def test_table_includes_disclaimer_linking_to_analysis():
    # 표-본문 모순 완화: 표는 검토 목록, 적합성은 아래 분석 참조
    anns = [{"title": "A자금", "department": "기관", "support_amount": "1억", "deadline": "2026-01-01"}]
    html = build_fund_section_html("분석", anns)
    assert "아래 분석" in html


def test_dedupes_parenthetical_title_variants():
    # 같은 프로그램의 괄호 변형은 1행으로 합침 (중복 제거)
    anns = [
        {"title": "신시장진출지원자금 (중진공 정책자금)", "department": "중진공", "support_amount": "10억"},
        {"title": "신시장진출지원자금(융자)", "department": "중진공", "support_amount": "10억"},
    ]
    html = build_fund_section_html("분석", anns)
    assert html.count("신시장진출지원자금") == 1


def test_fund_deadline_date_shown():
    anns = [{"id": 1, "title": "A", "support_amount": "1억", "deadline": "2026-08-31", "deadline_type": "fixed"}]
    assert "2026-08-31" in build_fund_section_html("x", anns)


def test_fund_deadline_ongoing_shows_sangsi():
    anns = [{"id": 1, "title": "A", "support_amount": "1억", "deadline": "", "deadline_type": "ongoing"}]
    assert "상시" in build_fund_section_html("x", anns)


def test_fund_deadline_unknown_shows_confirm_not_sangsi():
    # 마감일 미상을 '상시'로 단정하지 않고 '확인 필요'로 정직 표시
    anns = [{"id": 1, "title": "A", "support_amount": "1억", "deadline": "", "deadline_type": "unknown"}]
    html = build_fund_section_html("x", anns)
    assert "확인 필요" in html
    assert "상시" not in html


def test_fund_table_links_announcement_when_id_present():
    # 정책자금명을 지원금길잡이 공고 상세(절대경로)로 링크 — PDF/HTML 어디서나 클릭
    anns = [{"id": 12345, "title": "신성장기반자금", "department": "중진공", "support_amount": "10억"}]
    html = build_fund_section_html("분석", anns)
    assert 'href="https://govmatch.kr/announcements/12345"' in html
    assert "신성장기반자금" in html


def test_fund_table_no_link_when_id_missing():
    # id 없으면 링크 없이 텍스트만 (깨진 링크 방지)
    anns = [{"title": "이름만있음", "department": "기관", "support_amount": "1억"}]
    html = build_fund_section_html("분석", anns)
    assert "announcements/" not in html
    assert "이름만있음" in html


def test_amount_clipped_at_clause_boundary():
    # 지원조건이 단어 중간이 아니라 구분자 경계에서 잘려야 함 (40자 초과분 제거)
    anns = [{"title": "보증", "department": "기보",
             "support_amount": "스마트제조: 보증비율 최대 100%, 보증료 최대 0.5%p 감면 / 스마트서비스: 95%"}]
    html = build_fund_section_html("분석", anns)
    assert "…" in html
    # 40자 뒤쪽(스마트서비스)은 잘려 표에 없어야 함
    assert "스마트서비스" not in html


def test_long_support_amount_clipped_with_ellipsis():
    # 긴 지원조건은 말줄임표로 (싹둑 잘림 방지)
    long_amt = ("운전 및 시설자금 보증 스마트제조 보증비율 최대 100퍼센트 보증료 최대 0.5%p 감면 등 "
                "매우 긴 조건 텍스트이며 세부 사업별로 한도와 금리가 상이하므로 공고문을 반드시 확인해야 합니다")
    anns = [{"title": "보증", "department": "기보", "support_amount": long_amt}]
    html = build_fund_section_html("분석", anns)
    assert "…" in html
