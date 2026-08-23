# -*- coding: utf-8 -*-
"""저장한 공고 링크가 실제로 열리는지 확인한다.

url_health.py 와 다르다 — 그쪽은 URL 문자열의 **형태**(도메인 중복·공백·인코딩)를 본다.
여기는 **실제로 열어 본다**. 형태가 완벽해도 열리지 않는 주소가 있기 때문이다.

왜 만들었나 (2026-08-24)
  K-Startup 공고 212건의 링크가 죽어 있었는데 세 검사망을 전부 통과했다.
    수집 성공?      212건 수집됨          → 커버리지 경보 대상 아님
    URL 형태?       흠 없는 주소          → url_health 통과
    수집처 살아있나? 목록 페이지는 정상     → source_diagnoser 통과 (그쪽은 목록 URL만 본다)
    실제로 열리나?  ✗                    → 이걸 보는 눈이 없었다
  대표가 눈으로 발견할 때까지 아무도 몰랐다.

판정 기준 — 전부 실측으로 정했다. 추측한 값이 하나도 없다.
  · 상태코드는 쓸모없다. 죽은 주소도, 없는 번호도 전부 HTTP 200 이었다.
  · 본문 길이도 못 쓴다. 껍데기 크기가 수집처마다 다르다.
  · 통한 것은 하나뿐 — **DB에 저장된 그 공고 제목이 페이지에 있는가.**
      죽은 주소 25% / 살아있는 주소 100% / 없는 번호 12%
  · 판정 단위는 개별 링크가 아니라 **수집처**다. 개별 공고가 내려가는 건 정상이고,
    표본이 전멸해야 코드 문제다. 상위 20개 수집처 실측에서 정상 16곳은 83~100%,
    죽은 3곳은 전부 0% 로 깨끗이 갈렸다.

★ HTML 1차 결과만으로 수리하지 않는다
  JS 렌더링 사이트는 HTML 만 받으면 본문이 비어 죽은 것처럼 보인다. 실측에서
  bokjiro(4,386건)·asancef(366건)가 HTML 0% 였지만 브라우저로 열면 100% 였다.
  1차만 믿었다면 멀쩡한 4,752건을 망가뜨렸다. 그래서 2차 브라우저 확인이 필수다.
"""
from __future__ import annotations

import html as _html
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

# 제목 어절이 이 비율 이상 페이지에 있으면 살아있는 것으로 본다.
# 실측 분포(죽음 0~25% / 삶 83~100%) 한가운데를 넉넉히 잡았다.
ALIVE_THRESHOLD = 0.6

# 수집처 하나를 판정하는 데 필요한 최소 표본. 1~2건으로 단정하지 않는다.
MIN_SAMPLES = 3

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

_TAG_RE = re.compile(r"<[^>]+>")
_DROP_RE = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.S | re.I)
_WS_RE = re.compile(r"\s+")


# ── 순수 함수 (테스트 대상) ────────────────────────────────

def visible_text(html: str) -> str:
    """HTML 에서 눈에 보이는 텍스트만 남긴다.

    script/style 을 먼저 걷어낸다 — 안 그러면 JS 안의 문자열이 본문으로 잡혀
    죽은 페이지가 살아있는 것처럼 보인다.
    """
    if not html:
        return ""
    t = _DROP_RE.sub(" ", html)
    t = _TAG_RE.sub(" ", t)
    return _WS_RE.sub(" ", _html.unescape(t)).strip()


def title_match_ratio(page_text: str, title: str) -> float:
    """공고 제목의 어절 중 몇 할이 페이지에 있는가.

    완전일치는 쓰지 않는다 — 제목은 400자에서 잘려 저장되고, 목록의 「새로운」 같은
    꼬리표가 섞여 들어오기도 한다.
    한 글자 어절(및·등·를)은 아무 페이지에나 있어 판정을 흐리므로 세지 않는다.
    """
    if not page_text or not title:
        return 0.0
    words = [w for w in _WS_RE.split(title) if len(w) >= 2]
    if not words:
        return 0.0
    return sum(1 for w in words if w in page_text) / len(words)


def judge_link(ratio: float) -> str:
    """개별 링크 판정 — alive | dead"""
    return "alive" if ratio >= ALIVE_THRESHOLD else "dead"


def judge_source(ratios: List[float]) -> str:
    """수집처 판정 — ok | suspect | unknown

    표본이 **전부** 죽어야 suspect 다. 하나라도 살아 있으면 그 수집처의 URL 조립
    규칙은 멀쩡하고, 죽은 건 그 공고가 내려간 것이다.
    """
    if len(ratios) < MIN_SAMPLES:
        return "unknown"
    return "suspect" if all(r < ALIVE_THRESHOLD for r in ratios) else "ok"


def needs_browser_recheck(verdict: str) -> bool:
    """1차 HTML 판정이 suspect 면 브라우저로 다시 봐야 한다.

    1차 결과는 확정이 아니라 후보다 — JS 렌더링 사이트가 여기 걸린다.
    """
    return verdict == "suspect"


def host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except Exception:
        return ""


# ── 바깥과 이야기하는 부분 ────────────────────────────────

def _fetch_html(url: str, timeout: int = 15) -> str:
    import requests
    r = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout, allow_redirects=True)
    return r.text or ""


def check_samples_html(samples: List[Dict[str, Any]], workers: int = 8) -> List[float]:
    """표본들의 제목 일치율을 HTML 요청으로 잰다. 실패는 0.0 으로 본다."""
    from concurrent.futures import ThreadPoolExecutor

    def one(s: Dict[str, Any]) -> float:
        try:
            return title_match_ratio(visible_text(_fetch_html(s["origin_url"])), s["title"])
        except Exception:
            return 0.0

    if not samples:
        return []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(one, samples))


def check_samples_browser(samples: List[Dict[str, Any]]) -> List[float]:
    """브라우저로 실제 렌더한 뒤 잰다 — 1차에서 suspect 로 나온 수집처에만 쓴다.

    느리고 무겁다(건당 수 초). 수집처 단위로만 부르기 때문에 감당할 수 있다.
    Playwright 가 없으면 빈 목록을 돌려준다 — 그러면 판정을 보류한다.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return []

    out: List[float] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            ctx = browser.new_context(user_agent=_UA, viewport={"width": 1280, "height": 900})
            for s in samples:
                page = ctx.new_page()
                try:
                    try:
                        page.goto(s["origin_url"], wait_until="networkidle", timeout=30000)
                    except Exception:
                        page.goto(s["origin_url"], wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(2500)
                    text = _WS_RE.sub(" ", page.locator("body").inner_text()).strip()
                    out.append(title_match_ratio(text, s["title"]))
                except Exception:
                    out.append(0.0)
                finally:
                    page.close()
            browser.close()
    except Exception:
        return out
    return out


def _live_samples_by_host(cur, per_host: int, min_total: int) -> Dict[str, Dict[str, Any]]:
    """수집처별 표본 — 마감 전 공고 중 최근 것부터."""
    cur.execute(
        """
        WITH live AS (
          SELECT split_part(split_part(origin_url,'//',2),'/',1) AS host,
                 announcement_id, title, origin_url,
                 row_number() OVER (PARTITION BY split_part(split_part(origin_url,'//',2),'/',1)
                                    ORDER BY announcement_id DESC) AS rn,
                 count(*)   OVER (PARTITION BY split_part(split_part(origin_url,'//',2),'/',1)) AS total
          FROM announcements
          WHERE origin_url LIKE 'http%%'
            AND title IS NOT NULL AND length(title) >= 8
            AND (deadline_date IS NULL OR deadline_date >= CURRENT_DATE)
        )
        SELECT host, announcement_id, title, origin_url, total
        FROM live WHERE rn <= %s AND total >= %s
        ORDER BY total DESC, host, rn
        """,
        (per_host, min_total),
    )
    grouped: Dict[str, Dict[str, Any]] = {}
    for r in cur.fetchall():
        g = grouped.setdefault(r["host"], {"host": r["host"], "total": r["total"], "samples": []})
        g["samples"].append({"announcement_id": r["announcement_id"],
                             "title": r["title"], "origin_url": r["origin_url"]})
    return grouped


def scan_dead_links(
    db_conn,
    per_host: int = 4,
    min_total: int = 8,
    max_browser_hosts: int = 8,
) -> Dict[str, Any]:
    """수집처별로 링크가 살아 있는지 본다.

    1차 HTML → suspect 인 수집처만 2차 브라우저. 2차까지 전멸해야 죽음으로 본다.
    수리는 하지 않는다 — 보고만 한다.

    Returns:
        {checked_hosts, dead: [{host, total, ratios_html, ratios_browser, sample_url}],
         html_only_suspect, skipped_browser}
    """
    cur = db_conn.cursor()
    grouped = _live_samples_by_host(cur, per_host, min_total)

    first_pass = []
    for host, g in grouped.items():
        ratios = check_samples_html(g["samples"])
        if needs_browser_recheck(judge_source(ratios)):
            first_pass.append((g, ratios))

    dead: List[Dict[str, Any]] = []
    skipped = 0
    # 무거운 2차는 상한을 둔다. 넘긴 것은 조용히 버리지 않고 세어서 보고한다.
    for g, ratios in first_pass[:max_browser_hosts]:
        b = check_samples_browser(g["samples"])
        if not b:                      # Playwright 불가 — 판정 보류
            skipped += 1
            continue
        if judge_source(b) == "suspect":
            dead.append({
                "host": g["host"],
                "total": g["total"],
                "ratios_html": [round(x, 2) for x in ratios],
                "ratios_browser": [round(x, 2) for x in b],
                "sample_url": g["samples"][0]["origin_url"],
                "sample_title": g["samples"][0]["title"][:60],
            })
    skipped += max(0, len(first_pass) - max_browser_hosts)

    dead.sort(key=lambda d: -d["total"])
    return {
        "checked_hosts": len(grouped),
        "html_only_suspect": len(first_pass),
        "dead": dead,
        "dead_hosts": len(dead),
        "dead_announcements": sum(d["total"] for d in dead),
        "skipped_browser": skipped,
    }
