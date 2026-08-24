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
from typing import Any, Dict, List, NamedTuple, Optional
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


class Probe(NamedTuple):
    """표본 하나를 열어본 결과.

    status
      ok      — 페이지를 받아 읽었다. ratio 로 생사를 판정한다.
      blocked — 서버가 우리를 막았다(403·429·5xx). 링크의 생사와 무관하다.
      error   — 연결 자체가 안 됐다(타임아웃·리셋·DNS). 역시 판정 근거가 못 된다.
    """
    ratio: float
    status: str


def classify_status(http_status: Optional[int]) -> str:
    """HTTP 상태코드를 판정 가능/불가로 나눈다.

    404 는 ok 로 둔다 — 「없는 페이지」는 링크가 죽었다는 진짜 신호다.
    403·429·5xx 는 우리 쪽이 막힌 것이라 링크의 생사를 말해주지 않는다.
    """
    if http_status is None:
        return "error"
    if http_status in (403, 429) or http_status >= 500:
        return "blocked"
    return "ok"


def judge_source_probes(probes: List[Probe]) -> str:
    """수집처 판정 — 차단·연결실패 표본은 빼고 본다.

    2026-08-24 사고: 이 구분이 없어 www.jeju.go.kr 106건을 죽었다고 보고했다.
    Railway 서버가 차단당했을 뿐 링크는 멀쩡했다(다른 곳에서 재니 100%).
    **우리 서버에서 안 열리는 것과 링크가 죽은 것은 다르다.**
    """
    usable = [p.ratio for p in probes if p.status == "ok"]
    return judge_source(usable)


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

def check_samples_html(samples: List[Dict[str, Any]], workers: int = 8) -> List[Probe]:
    """표본들을 HTTP 로 열어 본다.

    연결 실패를 0.0 으로 뭉개면 안 된다 — 차단당한 수집처가 죽은 것으로 둔갑한다.
    상태를 함께 돌려줘서 판정에서 뺄 수 있게 한다.
    """
    from concurrent.futures import ThreadPoolExecutor
    import requests

    def one(s: Dict[str, Any]) -> Probe:
        try:
            r = requests.get(s["origin_url"], headers={"User-Agent": _UA},
                             timeout=15, allow_redirects=True)
        except Exception:
            return Probe(0.0, "error")
        st = classify_status(r.status_code)
        if st != "ok":
            return Probe(0.0, st)
        return Probe(title_match_ratio(visible_text(r.text or ""), s["title"]), "ok")

    if not samples:
        return []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(one, samples))


def check_samples_browser(samples: List[Dict[str, Any]]) -> List[Probe]:
    """브라우저로 실제 렌더한 뒤 잰다 — 1차에서 suspect 로 나온 수집처에만 쓴다.

    느리고 무겁다(건당 수 초). 수집처 단위로만 부르기 때문에 감당할 수 있다.
    Playwright 가 없으면 빈 목록을 돌려준다 — 그러면 판정을 보류한다.
    여기서도 응답 상태를 본다. 차단(403·429·5xx)이나 연결 실패는 죽음이 아니다.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return []

    out: List[Probe] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            ctx = browser.new_context(user_agent=_UA, viewport={"width": 1280, "height": 900})
            for s in samples:
                page = ctx.new_page()
                code: Optional[int] = None

                def _grab(resp, _u=s["origin_url"]):
                    nonlocal code
                    if code is None and resp.url.rstrip("/") == _u.rstrip("/"):
                        code = resp.status

                page.on("response", _grab)
                try:
                    try:
                        page.goto(s["origin_url"], wait_until="networkidle", timeout=30000)
                    except Exception:
                        page.goto(s["origin_url"], wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(2500)
                    st = classify_status(code if code is not None else 200)
                    if st != "ok":
                        out.append(Probe(0.0, st))
                    else:
                        text = _WS_RE.sub(" ", page.locator("body").inner_text()).strip()
                        out.append(Probe(title_match_ratio(text, s["title"]), "ok"))
                except Exception:
                    # 렌더 자체가 안 됐다 — 판정 근거가 못 된다
                    out.append(Probe(0.0, "error"))
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
    blocked_hosts = 0
    for host, g in grouped.items():
        probes = check_samples_html(g["samples"])
        verdict = judge_source_probes(probes)
        if verdict == "unknown" and probes:
            # 열린 표본이 모자란다 — 차단이거나 접속 불가. 죽음이 아니다.
            blocked_hosts += 1
        if needs_browser_recheck(verdict):
            first_pass.append((g, probes))

    dead: List[Dict[str, Any]] = []
    skipped = 0
    # 무거운 2차는 상한을 둔다. 넘긴 것은 조용히 버리지 않고 세어서 보고한다.
    for g, probes in first_pass[:max_browser_hosts]:
        b = check_samples_browser(g["samples"])
        if not b:                      # Playwright 불가 — 판정 보류
            skipped += 1
            continue
        if judge_source_probes(b) != "suspect":
            continue                   # 살아있거나(오탐) 판정 불가(차단)
        dead.append({
            "host": g["host"],
            "total": g["total"],
            "ratios_html": [round(p.ratio, 2) for p in probes],
            "ratios_browser": [round(p.ratio, 2) for p in b],
            "status_browser": [p.status for p in b],
            "sample_url": g["samples"][0]["origin_url"],
            "sample_title": g["samples"][0]["title"][:60],
        })
    skipped += max(0, len(first_pass) - max_browser_hosts)

    dead.sort(key=lambda d: -d["total"])
    return {
        "checked_hosts": len(grouped),
        "html_only_suspect": len(first_pass),
        "unjudgeable_hosts": blocked_hosts,
        "dead": dead,
        "dead_hosts": len(dead),
        "dead_announcements": sum(d["total"] for d in dead),
        "skipped_browser": skipped,
    }
