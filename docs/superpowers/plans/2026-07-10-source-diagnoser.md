# 소스 진단자(Diagnoser) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 회귀 감시자가 지목한 "조용한" admin_urls 소스의 등록 URL을 주1회 재fetch해 0건 원인을 4유형으로 자동 분류하고, COO 메일에 "🔧 수리 필요" 제안으로 띄운다.

**Architecture:** 신규 `source_diagnoser.py`에 순수 분류함수 + fetch/parse + DB 진단 함수를 두고, 오케스트레이터(supervisor)가 주1회(월,KST) 호출해 `coverage_targets`의 diag_* 컬럼을 갱신한다. reporter는 매일 그 스냅샷을 읽어 "수리 필요" 섹션을 렌더. 프로덕션은 진단·제안만 하고 수리는 Claude 세션 TDD.

**Tech Stack:** Python, FastAPI, psycopg2(RealDictCursor), requests, BeautifulSoup. 테스트는 코드베이스 관례(자체 러너 `python test_x.py`, 순수함수 대상).

**Spec:** `docs/superpowers/specs/2026-07-10-self-maintaining-collection-diagnoser-design.md`

---

## File Structure

- **Create** `backend/app/services/orchestrator/source_diagnoser.py` — 진단자 전부(순수 분류 + fetch/parse + DB 함수). 회귀감지(coverage_checker)와 분리: 진단은 외부 fetch라는 별개 관심사.
- **Create** `backend/test_source_diagnoser_unit.py` — 순수함수 단위테스트.
- **Modify** `backend/app/main.py` — coverage_targets init 블록(~616행)에 diag_* 컬럼 add-only 마이그레이션.
- **Modify** `backend/app/services/orchestrator/reporter.py` — `_build_coverage_text`/`_build_coverage_html`에 "🔧 수리 필요" 렌더 추가.
- **Modify** `backend/app/services/orchestrator/supervisor.py` — 커버리지 스텝에 주1회 진단 호출 + repair_list 부착.

---

### Task 1: 순수 분류함수 `classify_diagnosis`

**Files:**
- Create: `backend/app/services/orchestrator/source_diagnoser.py`
- Test: `backend/test_source_diagnoser_unit.py`

- [ ] **Step 1: Write the failing test**

`backend/test_source_diagnoser_unit.py`:
```python
# -*- coding: utf-8 -*-
"""소스 진단자 — 순수함수 단위 테스트. 실행: cd backend && python test_source_diagnoser_unit.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass


def _t(http, links, body):
    from app.services.orchestrator.source_diagnoser import classify_diagnosis
    return classify_diagnosis(http, links, body)["diag_type"]


def test_unreachable_on_none_status():
    assert _t(None, 0, 0) == "unreachable"

def test_unreachable_on_4xx_5xx():
    assert _t(404, 10, 5000) == "unreachable"
    assert _t(500, 10, 5000) == "unreachable"

def test_extract_fail_when_many_links():
    # 200 + 링크 5개 이상 → 추출 실패(링크는 있는데 못 뽑음)
    assert _t(200, 5, 5000) == "extract_fail"
    assert _t(200, 4, 5000) != "extract_fail"

def test_js_only_when_no_links_and_short_body():
    assert _t(200, 0, 799) == "js_only"
    assert _t(200, 4, 799) == "js_only"

def test_wrong_or_empty_when_no_links_and_normal_body():
    assert _t(200, 0, 800) == "wrong_or_empty"
    assert _t(200, 4, 5000) == "wrong_or_empty"

def test_returns_suggested_action():
    from app.services.orchestrator.source_diagnoser import classify_diagnosis
    r = classify_diagnosis(200, 0, 800)
    assert r["diag_type"] == "wrong_or_empty"
    assert isinstance(r["suggested_action"], str) and len(r["suggested_action"]) > 3


if __name__ == "__main__":
    import traceback
    _fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    _p = _f = 0
    for _fn in _fns:
        try:
            _fn(); print("PASS  " + _fn.__name__); _p += 1
        except Exception as _e:
            print("FAIL  " + _fn.__name__ + ": " + repr(_e)); traceback.print_exc(); _f += 1
    print("\n%d passed, %d failed" % (_p, _f)); sys.exit(1 if _f else 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python test_source_diagnoser_unit.py`
Expected: FAIL — `ImportError: cannot import name 'classify_diagnosis'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/services/orchestrator/source_diagnoser.py`:
```python
"""소스 진단자 — 조용한 admin_urls 소스의 등록 URL을 재fetch해 0건 원인 분류.

프로덕션은 진단·제안까지만(수리는 Claude 세션 TDD). 회귀감지(coverage_checker)와
분리: 진단은 외부 HTTP fetch라는 별개 관심사.
"""
from __future__ import annotations
import re
import warnings
import datetime
from typing import Dict, Any, List, Optional

LINK_MANY = 5      # 공고 게시판이면 통상 목록 링크 5개 이상
BODY_STUB = 800    # 정상 렌더 페이지 가시 텍스트 하한(미만이면 JS 스텁 의심)

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# 공고 상세 링크로 볼 URL 패턴(admin_scraper._DETAIL_URL_PATTERNS와 동일 취지, 독립 정의)
_DETAIL_URL_RE = re.compile(
    r"(view|detail|read|notice|board|bbs|seq=|idx=|id=|no=|nttId=|articleId=|bid=|num=|post|content)",
    re.IGNORECASE,
)

_SUGGEST = {
    "unreachable":    "URL 폐쇄·이전 의심 — 새 URL 확인",
    "extract_fail":   "링크는 있으나 미추출 — 파서/전용 스크래퍼 점검",
    "js_only":        "JS 전용 렌더링 의심 — Playwright 전용 스크래퍼 필요",
    "wrong_or_empty": "엉뚱한 URL/빈 게시판 — 올바른 게시판 URL 확인",
}


def classify_diagnosis(http_status: Optional[int], link_count: int, body_len: int) -> Dict[str, str]:
    """순수함수. (HTTP상태, 공고링크수, 본문길이) → {diag_type, suggested_action}."""
    if http_status is None or http_status >= 400:
        t = "unreachable"
    elif link_count >= LINK_MANY:
        t = "extract_fail"
    elif body_len < BODY_STUB:
        t = "js_only"
    else:
        t = "wrong_or_empty"
    return {"diag_type": t, "suggested_action": _SUGGEST[t]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python test_source_diagnoser_unit.py`
Expected: PASS (6 passed, 0 failed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/orchestrator/source_diagnoser.py backend/test_source_diagnoser_unit.py
git commit -m "feat(diagnoser): classify_diagnosis 순수 분류함수 + 테스트"
```

---

### Task 2: 링크 카운트 파서 + fetch/measure

**Files:**
- Modify: `backend/app/services/orchestrator/source_diagnoser.py`
- Test: `backend/test_source_diagnoser_unit.py`

- [ ] **Step 1: Write the failing test** (기존 파일에 함수 추가)

`backend/test_source_diagnoser_unit.py` 의 `if __name__` 위에 추가:
```python
from bs4 import BeautifulSoup

_FIX_MANY = """<table><tbody>
  <tr><td><a href="/board/view.do?no=1&idx=10">지원사업 A 모집</a></td></tr>
  <tr><td><a href="/board/view.do?no=1&idx=11">지원사업 B 공고</a></td></tr>
  <tr><td><a href="/board/view.do?no=1&idx=12">지원사업 C 모집</a></td></tr>
  <tr><td><a href="/board/view.do?no=1&idx=13">지원사업 D 공고</a></td></tr>
  <tr><td><a href="/board/view.do?no=1&idx=14">지원사업 E 모집</a></td></tr>
  <tr><td><a href="/about">기관소개</a></td></tr>
</tbody></table>"""

_FIX_NONE = """<div><a href="/about">기관소개</a><a href="/login">로그인</a></div>"""

def test_count_article_links_counts_only_detail_links():
    from app.services.orchestrator.source_diagnoser import count_article_links
    assert count_article_links(BeautifulSoup(_FIX_MANY, "html.parser")) == 5
    assert count_article_links(BeautifulSoup(_FIX_NONE, "html.parser")) == 0

def test_visible_text_len_excludes_scripts():
    from app.services.orchestrator.source_diagnoser import visible_text_len
    html = "<html><script>var x=123456789012345;</script><body>짧은본문</body></html>"
    n = visible_text_len(BeautifulSoup(html, "html.parser"))
    assert n == len("짧은본문")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python test_source_diagnoser_unit.py`
Expected: FAIL — `cannot import name 'count_article_links'`

- [ ] **Step 3: Write minimal implementation** (source_diagnoser.py 에 추가)

```python
def count_article_links(soup) -> int:
    """공고 상세 링크로 볼 <a href> 개수."""
    n = 0
    for a in soup.select("a[href]"):
        if _DETAIL_URL_RE.search(a.get("href", "")):
            n += 1
    return n


def visible_text_len(soup) -> int:
    """script/style 제외 가시 텍스트 길이."""
    for tag in soup(["script", "style"]):
        tag.extract()
    return len(soup.get_text(strip=True))


def _fetch_and_measure(url: str) -> tuple:
    """(http_status, link_count, body_len). 실패 시 (None, 0, 0). SSL 실패면 verify=False 재시도."""
    import requests
    from bs4 import BeautifulSoup
    def _do(verify):
        return requests.get(url, headers=_HEADERS, timeout=15, verify=verify)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            try:
                resp = _do(True)
            except requests.exceptions.SSLError:
                resp = _do(False)
            soup = BeautifulSoup(resp.text, "html.parser")
            return resp.status_code, count_article_links(soup), visible_text_len(soup)
        except Exception:
            return None, 0, 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python test_source_diagnoser_unit.py`
Expected: PASS (8 passed, 0 failed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/orchestrator/source_diagnoser.py backend/test_source_diagnoser_unit.py
git commit -m "feat(diagnoser): 링크 카운트 파서 + fetch/measure"
```

---

### Task 3: DB 마이그레이션 (coverage_targets diag_* 컬럼)

**Files:**
- Modify: `backend/app/main.py` (coverage_targets init 블록, Phase1 ALTER들 바로 뒤)

- [ ] **Step 1: Add migration** (테스트 불필요 — DDL. Task 4의 런타임에서 검증)

`backend/app/main.py` 에서 Phase 1의 `days_quiet` ALTER 다음 줄에 추가:
```python
            cursor.execute("ALTER TABLE coverage_targets ADD COLUMN IF NOT EXISTS diag_type        VARCHAR(30)")
            cursor.execute("ALTER TABLE coverage_targets ADD COLUMN IF NOT EXISTS diag_detail      TEXT")
            cursor.execute("ALTER TABLE coverage_targets ADD COLUMN IF NOT EXISTS diag_link_count  INTEGER")
            cursor.execute("ALTER TABLE coverage_targets ADD COLUMN IF NOT EXISTS diag_http_status INTEGER")
            cursor.execute("ALTER TABLE coverage_targets ADD COLUMN IF NOT EXISTS diag_at          TIMESTAMP")
```

- [ ] **Step 2: Verify compile**

Run: `cd backend && python -m py_compile app/main.py`
Expected: no error (COMPILE_OK)

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(diagnoser): coverage_targets diag_* 컬럼 추가(add-only)"
```

---

### Task 4: DB 진단 함수 `diagnose_silent_sources` + `build_repair_list`

**Files:**
- Modify: `backend/app/services/orchestrator/source_diagnoser.py`

DB 접근이라 단위테스트 대신 Task 7 런타임으로 검증. 구현만.

- [ ] **Step 1: Write implementation** (source_diagnoser.py 에 추가)

```python
def _admin_source_name(origin_source: str) -> Optional[str]:
    """origin_source 'admin-manual:X' → admin_urls.source_name 'X'. 그 외 접두는 None(진단 대상 아님)."""
    if origin_source and origin_source.startswith("admin-manual:"):
        return origin_source[len("admin-manual:"):]
    return None


def diagnose_silent_sources(conn, silent_origin_sources: List[str]) -> int:
    """주1회. 조용한 admin-manual 소스의 admin_urls URL을 재fetch·분류해 coverage_targets diag_* 갱신.
    반환: 진단한 소스 수."""
    cur = conn.cursor()
    diagnosed = 0
    for origin in silent_origin_sources or []:
        name = _admin_source_name(origin)
        if not name:
            continue  # scraper:*/*-api 는 admin_urls에 없음 → 대상 아님
        try:
            cur.execute("SELECT url FROM admin_urls WHERE source_name = %s AND is_active = 1 LIMIT 1", (name,))
            row = cur.fetchone()
            if not row or not row.get("url"):
                continue
            status, links, body = _fetch_and_measure(row["url"])
            d = classify_diagnosis(status, links, body)
            cur.execute("""
                UPDATE coverage_targets
                   SET diag_type=%s, diag_detail=%s, diag_link_count=%s,
                       diag_http_status=%s, diag_at=NOW()
                 WHERE source_name = %s
            """, (d["diag_type"], d["suggested_action"], links, status, origin))
            conn.commit()
            diagnosed += 1
        except Exception:
            try: conn.rollback()
            except Exception: pass
    return diagnosed


def build_repair_list(conn, silent_origin_sources: List[str]) -> List[Dict[str, Any]]:
    """매일. 현재 조용한 소스들의 저장된 diag_* 스냅샷을 읽어 수리 목록 구성."""
    if not silent_origin_sources:
        return []
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT source_name, diag_type, diag_detail, diag_at
            FROM coverage_targets
            WHERE source_name = ANY(%s) AND diag_type IS NOT NULL
            ORDER BY diag_at DESC NULLS LAST
        """, (list(silent_origin_sources),))
        return [{"source": r["source_name"], "diag_type": r["diag_type"],
                 "suggested_action": r["diag_detail"],
                 "diag_at": r["diag_at"].strftime("%Y-%m-%d") if r.get("diag_at") else None}
                for r in cur.fetchall()]
    except Exception:
        try: conn.rollback()
        except Exception: pass
        return []
```

- [ ] **Step 2: Verify compile + import**

Run: `cd backend && python -c "import app.services.orchestrator.source_diagnoser; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/orchestrator/source_diagnoser.py
git commit -m "feat(diagnoser): diagnose_silent_sources + build_repair_list (DB 진단)"
```

---

### Task 5: reporter "🔧 수리 필요" 렌더

**Files:**
- Modify: `backend/app/services/orchestrator/reporter.py` (`_build_coverage_text`, `_build_coverage_html`)
- Test: `backend/test_coverage_report_unit.py` (기존 파일에 추가)

- [ ] **Step 1: Write the failing test**

`backend/test_coverage_report_unit.py` 의 `if __name__` 위에 추가:
```python
_REPAIR_COV = {
    "total_sources": 30, "green": 27, "yellow": 3, "red": 0, "na": 0, "muted": 0,
    "red_list": [], "yellow_list": [], "scraper_alerts": [],
    "repair_list": [
        {"source": "admin-manual:부산경제진흥원(BEPA)", "diag_type": "wrong_or_empty",
         "suggested_action": "엉뚱한 URL/빈 게시판 — 올바른 게시판 URL 확인", "diag_at": "2026-07-13"},
    ],
}

def test_coverage_text_shows_repair():
    from app.services.orchestrator.reporter import _build_coverage_text
    txt = _build_coverage_text(_REPAIR_COV)
    assert "수리 필요" in txt
    assert "부산경제진흥원" in txt
    assert "올바른 게시판" in txt

def test_coverage_html_shows_repair():
    from app.services.orchestrator.reporter import _build_coverage_html
    html = _build_coverage_html(_REPAIR_COV)
    assert "수리 필요" in html and "부산경제진흥원" in html

def test_coverage_text_no_repair_key_ok():
    # repair_list 없어도 기존 동작(회귀 없음) 유지
    from app.services.orchestrator.reporter import _build_coverage_text
    cov = {"total_sources": 10, "green": 10, "yellow": 0, "red": 0, "na": 0,
           "muted": 0, "red_list": [], "yellow_list": [], "scraper_alerts": []}
    assert "회귀 없음" in _build_coverage_text(cov)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python test_coverage_report_unit.py`
Expected: FAIL — `test_coverage_text_shows_repair` (수리 필요 문자열 없음)

- [ ] **Step 3: Write implementation**

`reporter.py` `_build_coverage_text`에서, `for a in sa[:5]:` 루프 다음(그리고 `if not red and not yellow and not sa:` 앞)에 삽입:
```python
    repair = coverage.get("repair_list", []) or []
    if repair:
        lines += f"  🔧 수리 필요 (진단 {len(repair)}건):\n"
        for x in repair[:8]:
            lines += f"    · {x['source']} — {x['diag_type']}: {x.get('suggested_action')}\n"
```
그리고 같은 함수의 마지막 `if not red and not yellow and not sa:` 조건을 다음으로 교체(수리목록도 없을 때만 "회귀 없음"):
```python
    if not red and not yellow and not sa and not repair:
        lines += "  ✅ 회귀 없음 — 전 소스 평시 주기 내 수집 중\n"
```

`reporter.py` `_build_coverage_html`에서, `box += f'<p ...>{summary}</p></div>'` 바로 앞에 삽입:
```python
    repair = coverage.get("repair_list", []) or []
    if repair:
        r_items = "".join(
            f'<li style="margin-bottom:2px">{x["source"]} — <b>{x["diag_type"]}</b>: {x.get("suggested_action")}</li>'
            for x in repair[:8])
        box += ('<div style="margin-top:8px"><div style="font-weight:bold;color:#b45309;font-size:13px">'
                f'&#128295; 수리 필요 {len(repair)}건</div>'
                f'<ul style="margin:2px 0 0;padding-left:18px;color:#b45309;font-size:12px">{r_items}</ul></div>')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python test_coverage_report_unit.py`
Expected: PASS (11 passed, 0 failed — 기존 8 + 신규 3)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/orchestrator/reporter.py backend/test_coverage_report_unit.py
git commit -m "feat(diagnoser): COO 메일 '수리 필요' 섹션 렌더"
```

---

### Task 6: supervisor 주1회 진단 배선

**Files:**
- Modify: `backend/app/services/orchestrator/supervisor.py` (커버리지 스텝)

- [ ] **Step 1: Write implementation**

`supervisor.py` 의 커버리지 스텝(`coverage = check_source_coverage(db_conn)` 성공 블록)에서, `results["coverage"] = coverage` 다음에 삽입:
```python
            # 주1회(월요일 KST) 조용한 소스 진단 갱신 + 매일 수리목록 부착
            try:
                from app.services.orchestrator.source_diagnoser import (
                    diagnose_silent_sources, build_repair_list)
                silent = [x["source"] for x in
                          (coverage.get("yellow_list", []) + coverage.get("red_list", []))]
                kst_weekday = (datetime.utcnow() + __import__("datetime").timedelta(hours=9)).weekday()
                if kst_weekday == 0 and silent:   # 월요일
                    n = diagnose_silent_sources(db_conn, silent)
                    print(f"  → 진단 갱신 {n}건")
                coverage["repair_list"] = build_repair_list(db_conn, silent)
            except Exception as _de:
                print(f"  → 진단 스텝 오류(무시): {_de}")
```
주의: `supervisor.py` 상단은 `from datetime import datetime` 사용 중이므로 `datetime.utcnow()`가 유효. `timedelta`는 위처럼 인라인 import로 처리(상단 import 변경 없이 surgical).

- [ ] **Step 2: Verify compile**

Run: `cd backend && python -m py_compile app/services/orchestrator/supervisor.py`
Expected: COMPILE_OK

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/orchestrator/supervisor.py
git commit -m "feat(diagnoser): supervisor 주1회 진단 + repair_list 부착"
```

---

### Task 7: 런타임 검증 + 배포

**Files:** 없음(검증·배포)

- [ ] **Step 1: 전체 단위테스트**

Run: `cd backend && python test_source_diagnoser_unit.py && python test_coverage_report_unit.py && python test_coverage_regression_unit.py`
Expected: 각각 all passed

- [ ] **Step 2: 실 URL 진단 스윕 (프로덕션 DB, 읽기+diag_* 쓰기)**

`.env` 로드 후 로컬에서:
```python
# scratchpad 스크립트: check_source_coverage로 silent 목록 → diagnose_silent_sources → build_repair_list 출력
```
Run 후 확인: 조용한 admin 소스들의 diag_type 분포가 실감과 맞는지(예: BEPA=wrong_or_empty), 제안 문구가 적절한지 육안. 오분류 많으면 `LINK_MANY`/`BODY_STUB` 조정 후 재실행.

- [ ] **Step 3: push + 배포**

```bash
git push origin main
```
Expected: Railway 자동 배포

- [ ] **Step 4: 수동 COO 실행 검증**

배포 후 `/api/admin/coo/run` 1회(관리자) → 메일에 "🔧 수리 필요" 섹션 노출 + 이중발송 없음 확인.

- [ ] **Step 5: (후속) 진단 결과로 세션 수리**

메일의 수리 목록을 보고, `wrong_or_empty`/`js_only` 소스를 Claude 세션에서 FABLE 설계 → Opus TDD로 개별 수리(BEPA 선례).

---

## Self-Review

**Spec coverage:**
- §3 북극성 3역할 → ①완료, ②이 계획(Task 1~7), ③범위밖(명시). ✅
- §4.2 진단 4유형 분류 → Task 1 `classify_diagnosis` 4분기 + 경계 테스트. ✅
- §4.3 DB 컬럼 add-only → Task 3. ✅
- §4.4 배선·주1회(월)·조인키 → Task 4(`_admin_source_name` 접두제거) + Task 6(월요일 게이트). ✅
- §4.5 메일 "수리 필요" → Task 5. ✅
- §4.6 첫 사이클=23개 스윕 → Task 7 Step 2. ✅
- §5 TDD(분류 경계·파서 픽스처) → Task 1·2 테스트. DB함수는 런타임(Task 7)로 정직 구분. ✅
- §8 임계값 보정 → Task 7 Step 2에 조정 여지 명시. ✅

**Placeholder scan:** Task 7 Step 2의 scratchpad 스크립트는 실행 시 작성(런타임 검증 절차라 코드 고정 불필요). 그 외 모든 코드 완비. 플레이스홀더 없음.

**Type consistency:** `classify_diagnosis`(Task1) 반환 `{diag_type, suggested_action}` → Task4 `diagnose_silent_sources`가 그대로 사용 → Task4 `build_repair_list` 반환 `{source, diag_type, suggested_action, diag_at}` → Task5 reporter가 동일 키 사용. `coverage["repair_list"]`(Task6) → reporter `coverage.get("repair_list")`(Task5) 일치. ✅
