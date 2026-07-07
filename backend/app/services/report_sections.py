"""PRO 종합 리포트의 부분 섹션 HTML 빌더 (순수 함수 — DB·AI 호출 없음).

리포트 본체(client_reports.summary)에 끼워넣는 HTML 블록을 생성한다.
AI/DB 의존을 분리해 단위 테스트가 가능하도록 별도 모듈로 둔다.
"""

import re

from app.services.amount_parser import normalize_amount_text

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


_FUND_SPLIT = re.compile(r'(?m)^\s*-{3,}\s*$')


def _strip_md(t) -> str:
    """마크다운 마커 제거 + 한 줄로 정리 (표 셀용)."""
    t = str(t or '')
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)
    t = re.sub(r'(?m)^\s*[-•*]\s+', '', t)
    t = re.sub(r'(?m)^\s*\*\s+', '', t)
    t = re.sub(r'\s*\n\s*', ' ', t)
    return re.sub(r'\s{2,}', ' ', t).strip()


def _fund_grab(blk, label, stops) -> str:
    pat = (rf'\**\s*\[?\s*{label}\s*\]?\s*\**\s*[:：]?\s*(.+?)'
           rf'(?=\n\s*\**\s*\[?\s*(?:{stops})\s*[\]:：]|\Z)')
    m = re.search(pat, blk, re.S)
    return m.group(1).strip() if m else ''


def _fund_sub(guide, label) -> str:
    pat = (rf'(?:{label})\s*\**\s*[:：]\s*\**\s*(.+?)'
           rf'(?=\n\s*-?\s*\**\s*(?:지원한도|대상요건|신청처|마감일?|준비서류|구비서류)\s*\**\s*[:：]|\Z)')
    m = re.search(pat, guide, re.S)
    return _strip_md(m.group(1)) if m else ''


def _parse_fund_rationale(text) -> list:
    """정책자금 엔진 자유서술(마크다운) → 자금별 구조화 dict 목록.

    AI 필수 구조([결론]/[근거]/[실행 가이드]/[다음 액션]) 기반 파싱.
    파싱 실패 시 빈 목록 → 호출부에서 기존 텍스트 렌더로 폴백.
    """
    text = (text or '').strip()
    if not text:
        return []
    funds = []
    for blk in _FUND_SPLIT.split(text):
        blk = blk.strip()
        if '결론' not in blk:
            continue
        head = next((l for l in blk.splitlines() if l.strip()), '')
        name = re.sub(r'^\**\s*\d+[.)]\s*', '', head).strip(' *#').strip()
        guide = _fund_grab(blk, '실행\\s*가이드', '다음\\s*액션')
        funds.append({
            'name': _strip_md(name),
            'conclusion': _strip_md(_fund_grab(blk, '결론', '근거|실행\\s*가이드|다음\\s*액션')),
            'limit': _fund_sub(guide, '지원한도'),
            'target': _fund_sub(guide, '대상요건'),
            'apply': _fund_sub(guide, '신청처'),
            'deadline': _fund_sub(guide, '마감일?'),
            'docs': _fund_sub(guide, '준비서류|구비서류'),
            'action': _strip_md(_fund_grab(blk, '다음\\s*액션', '')),
        })
    return [f for f in funds if f['name'] or f['conclusion']]


_FUND_ROWS = [('conclusion', '결론'), ('limit', '지원한도'), ('target', '대상요건'),
              ('apply', '신청처'), ('deadline', '마감'), ('docs', '준비서류'), ('action', '다음 액션')]


def _norm_title(t) -> str:
    """제목 정규화 — 괄호·공백 제거 후 소문자 (자금명↔공고 매칭용)."""
    return re.sub(r'\s+', '', re.sub(r'\(.*?\)', '', str(t or ''))).lower()


def _render_fund_tables(funds, anns=None) -> str:
    """자금별 dict 목록 → 자금별 2열 표(항목/내용) HTML. 금액은 백만원 통일.

    자금명은 announcements와 매칭되면 ?aid 링크(메인화면 카드)로 연결.
    """
    aid_by = {}
    for a in (anns or []):
        k = _norm_title(a.get("title"))
        aid = a.get("id")
        if k and k not in aid_by and aid is not None and str(aid).strip().lstrip("-").isdigit():
            aid_by[k] = int(aid)
    blocks = []
    for f in funds:
        rows = ""
        for key, label in _FUND_ROWS:
            val = f.get(key) or ""
            if not val:
                continue
            val = normalize_amount_text(val)
            rows += (f'<tr><th style="{_TH}white-space:nowrap;width:84px;vertical-align:top;">{_esc(label)}</th>'
                     f'<td style="{_TD}vertical-align:top;">{_esc(val)}</td></tr>')
        if not rows:
            continue
        name = f.get("name") or "정책자금"
        aid = aid_by.get(_norm_title(name))
        name_html = (
            f'<a href="https://govmatch.kr?aid={aid}" target="_blank" '
            f'style="color:#5b21b6;text-decoration:underline;">{_esc(name)}</a>'
            if aid else _esc(name)
        )
        blocks.append(
            f'<h4 style="margin:16px 0 4px 0;color:#5b21b6;font-size:13px;">{name_html}</h4>'
            f'<table style="{_TABLE}"><tbody>{rows}</tbody></table>'
        )
    return "".join(blocks)


_FUND_STRUCT_ROWS = [('verdict', '결론'), ('support_limit', '지원한도'), ('target', '대상요건'),
                     ('apply', '신청처'), ('deadline', '마감'), ('docs', '준비서류'), ('action', '다음 액션')]


def _render_fund_tables_struct(details, anns=None) -> str:
    """구조화 자금 분석(JSON 목록) → 자금별 2열 표. 프로즈 파싱보다 안정적.

    각 항목: {aid, name, verdict, support_limit, target, apply, deadline, docs, action}
    금액은 백만원 통일, 자금명은 aid(없으면 제목매칭)로 ?aid 링크.
    """
    if not isinstance(details, list) or not details:
        return ""
    aid_by = {}
    for a in (anns or []):
        k = _norm_title(a.get("title"))
        aid = a.get("id")
        if k and k not in aid_by and aid is not None and str(aid).strip().lstrip("-").isdigit():
            aid_by[k] = int(aid)
    blocks = []
    for f in details:
        if not isinstance(f, dict):
            continue
        rows = ""
        for key, label in _FUND_STRUCT_ROWS:
            val = str(f.get(key) or "").strip()
            if not val:
                continue
            val = normalize_amount_text(val)
            rows += (f'<tr><th style="{_TH}white-space:nowrap;width:84px;vertical-align:top;">{_esc(label)}</th>'
                     f'<td style="{_TD}vertical-align:top;">{_esc(val)}</td></tr>')
        if not rows:
            continue
        name = str(f.get("name") or "정책자금").strip()
        aid = f.get("aid")
        if not (aid is not None and str(aid).strip().lstrip("-").isdigit()):
            aid = aid_by.get(_norm_title(name))
        name_html = (
            f'<a href="https://govmatch.kr?aid={int(aid)}" target="_blank" '
            f'style="color:#5b21b6;text-decoration:underline;">{_esc(name)}</a>'
            if aid else _esc(name)
        )
        blocks.append(
            f'<h4 style="margin:16px 0 4px 0;color:#5b21b6;font-size:13px;">{name_html}</h4>'
            f'<table style="{_TABLE}"><tbody>{rows}</tbody></table>'
        )
    return "".join(blocks)


def build_fund_section_html(reply_text, announcements, fund_details=None) -> str:
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
            amount = _esc(_clip_clause(normalize_amount_text(a.get("support_amount") or "공고 참조"), 40))
            # 마감일: 날짜 > 상시(ongoing) > 확인 필요(미상). NULL을 상시로 단정하지 않음.
            _dl = (a.get("deadline") or "").strip()
            if _dl and _dl.lower() not in ("none", "null"):
                deadline, _dcolor = _esc(_dl), "#dc2626"
            elif a.get("deadline_type") == "ongoing":
                deadline, _dcolor = "상시", "#64748b"
            else:
                deadline, _dcolor = "확인 필요", "#ea580c"
            # 정책자금명 → 지원금길잡이 공고 상세(절대경로). id 없으면 텍스트만.
            _aid = a.get("id")
            if _aid is not None and str(_aid).strip().lstrip("-").isdigit():
                title = (
                    f'<a href="https://govmatch.kr?aid={int(_aid)}" target="_blank" '
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

    # 상세 분석: ① 구조화 JSON(가장 안정) → ② 프로즈 파싱 → ③ 원문 텍스트 순으로 폴백.
    struct_html = _render_fund_tables_struct(fund_details, anns) if fund_details else ""
    if struct_html:
        rationale_block = f'<div style="margin-top:10px;">{struct_html}</div>'
    else:
        funds = _parse_fund_rationale(reply_text)
        if funds:
            rationale_block = f'<div style="margin-top:10px;">{_render_fund_tables(funds, anns)}</div>'
        else:
            rationale_html = _markdown_to_html(reply_text) if reply_text else ""
            rationale_block = (
                f'<div style="font-size:13px;color:#334155;line-height:1.7;margin-top:10px;">{rationale_html}</div>'
                if rationale_html else ""
            )

    return header + note + table_html + disclaimer + rationale_block
