"""PRO 종합 리포트의 부분 섹션 HTML 빌더 (순수 함수 — DB·AI 호출 없음).

리포트 본체(client_reports.summary)에 끼워넣는 HTML 블록을 생성한다.
AI/DB 의존을 분리해 단위 테스트가 가능하도록 별도 모듈로 둔다.
"""

import re

# 리포트 공통 섹션 헤더 스타일 (main.py의 다른 섹션과 일관)
_H2 = 'color:#5b21b6;border-bottom:2px solid #c4b5fd;padding-bottom:6px;margin-top:24px;'
_TABLE = 'width:100%;border-collapse:collapse;margin:12px 0;font-size:13px;'
_TH = 'background:#f5f3ff;color:#5b21b6;padding:8px 12px;border:1px solid #e5e7eb;text-align:left;font-weight:bold;'
_TD = 'padding:8px 12px;border:1px solid #e5e7eb;'


def _esc(text) -> str:
    """HTML 특수문자 이스케이프 (AI/공고 텍스트의 태그 깨짐·주입 방지)."""
    return (str(text) if text is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _clip(text, n: int) -> str:
    """n자 초과면 말줄임표(…)로 마무리 (보고서 표의 싹둑 잘림 방지)."""
    s = str(text) if text is not None else ""
    return s if len(s) <= n else s[:n].rstrip() + "…"


def _clip_clause(text, n: int) -> str:
    """n자 초과면 구분자(/ , 공백) 경계에서 잘라 …로 마무리 (단어/구 중간 끊김 방지)."""
    s = str(text) if text is not None else ""
    if len(s) <= n:
        return s
    cut = s[:n]
    best = -1
    for sep in ("/", ",", " "):
        idx = cut.rfind(sep)
        if idx > best:
            best = idx
    if best >= n // 2:  # 너무 앞이면 그냥 n에서 자름
        cut = cut[:best]
    return cut.rstrip(" /,") + "…"


def _dedupe_announcements(anns: list) -> list:
    """같은 정책자금의 표기 변형 제거. 괄호·공백 제거한 제목을 키로 첫 항목만 유지.

    예: '신시장진출지원자금 (중진공 정책자금)' 와 '신시장진출지원자금(융자)' → 1건.
    """
    seen = set()
    out = []
    for a in anns:
        raw = (a.get("title") or "").strip()
        key = re.sub(r"\s+", "", re.sub(r"\(.*?\)", "", raw))
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(a)
    return out


def _markdown_to_html(text: str) -> str:
    """AI 추천 본문(마크다운)을 리포트용 인라인 HTML로 변환.

    먼저 전체를 이스케이프한 뒤, 마크다운 마커만 태그로 치환한다.
    (이스케이프 후이므로 추천 본문 내 실제 <,> 는 태그가 되지 않음)
    """
    out = _esc(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"^###\s+(.+)$", r"<h4 style='margin:10px 0 4px 0;color:#334155;font-size:13px;'>\1</h4>", out, flags=re.M)
    out = re.sub(r"^##\s+(.+)$", r"<h3 style='margin:12px 0 6px 0;color:#5b21b6;font-size:14px;'>\1</h3>", out, flags=re.M)
    out = re.sub(r"^[-•*]\s+(.+)$", r"<li>\1</li>", out, flags=re.M)
    out = re.sub(r"(<li>.*?</li>(?:\s*<li>.*?</li>)*)", r"<ul style='margin:6px 0;padding-left:20px;'>\1</ul>", out, flags=re.S)
    # 리스트 항목 사이 줄바꿈은 제거(중복 <br/> 방지), 그 외 줄바꿈만 <br/>
    out = re.sub(r"</li>\s*<li>", "</li><li>", out)
    out = out.replace("\n\n", "<br/><br/>").replace("\n", "<br/>")
    return out


def build_fund_section_html(reply_text, announcements) -> str:
    """'💰 맞춤 정책자금' 섹션 HTML 생성.

    Args:
        reply_text: 정책자금 엔진(chat_lite_fund_expert)의 추천 본문(마크다운)
        announcements: 매칭된 정책자금 공고 리스트
            (각 항목: id/title/department/support_amount/deadline/region 등)

    Returns:
        HTML 문자열. 추천 본문도 공고도 없으면 "" (섹션 생략).
    """
    reply_text = (reply_text or "").strip()
    anns = announcements or []
    if not reply_text and not anns:
        return ""

    header = f'<h2 style="{_H2}">💰 맞춤 정책자금</h2>'
    note = (
        '<p style="font-size:12px;color:#64748b;margin:8px 0;">'
        '고객사 조건(업력·매출·지역)에 맞춰 자동 선별된 정책자금입니다. '
        '실제 한도·금리·승인 여부는 기관 심사에 따릅니다.</p>'
    )

    table_html = ""
    disclaimer = ""
    if anns:
        rows = ""
        for a in _dedupe_announcements(anns):
            title = _esc(_clip(a.get("title") or "", 80))
            dept = _esc(_clip(a.get("department") or "기관 미상", 40))
            amount = _esc(_clip_clause(a.get("support_amount") or "공고 참조", 40))
            # 마감일: 날짜 > 상시(ongoing) > 확인 필요(미상). NULL을 상시로 단정하지 않음.
            _dl = (a.get("deadline") or "").strip()
            if _dl and _dl.lower() not in ("none", "null"):
                deadline, _dcolor = _esc(_dl), "#dc2626"
            elif a.get("deadline_type") == "ongoing":
                deadline, _dcolor = "상시", "#64748b"
            else:
                deadline, _dcolor = "확인 필요", "#ea580c"
            # 정책자금명 → 지원금AI 공고 상세(절대경로). id 없으면 텍스트만.
            _aid = a.get("id")
            if _aid is not None and str(_aid).strip().lstrip("-").isdigit():
                title = (
                    f'<a href="https://govmatch.kr/announcements/{int(_aid)}" target="_blank" '
                    f'style="color:#5b21b6;text-decoration:underline;">{title}</a>'
                )
            rows += (
                "<tr>"
                f'<td style="{_TD}width:40%;">{title}</td>'
                f'<td style="{_TD}width:22%;">{dept}</td>'
                f'<td style="{_TD}width:26%;color:#16a34a;font-weight:bold;">{amount}</td>'
                f'<td style="{_TD}width:12%;color:{_dcolor};">{deadline}</td>'
                "</tr>"
            )
        table_html = (
            f'<table style="{_TABLE}"><thead><tr>'
            f'<th style="{_TH}">정책자금</th>'
            f'<th style="{_TH}">주관기관</th>'
            f'<th style="{_TH}">지원조건</th>'
            f'<th style="{_TH}">마감</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>'
        )
        # 표-본문 모순 완화: 표는 검토 목록일 뿐, 적합성 판정은 아래 분석을 보라고 명시
        disclaimer = (
            '<p style="font-size:11px;color:#94a3b8;margin:4px 0 0 0;">'
            '※ 위 표는 검토 대상 정책자금 목록이며, 고객사별 적합성'
            '(신청 가능·확인 필요·해당 없음) 판정은 아래 분석을 참조하세요.</p>'
        )

    rationale_html = _markdown_to_html(reply_text) if reply_text else ""
    rationale_block = (
        f'<div style="font-size:13px;color:#334155;line-height:1.7;margin-top:10px;">{rationale_html}</div>'
        if rationale_html else ""
    )

    return header + note + table_html + disclaimer + rationale_block
