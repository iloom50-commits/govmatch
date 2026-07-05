"""
issue_monitor.py — 정부 보도자료 스캔 → Hot이슈 자동 생성
주 2회 스케줄러 또는 관리자 수동 실행
"""
import os
import re
import json
import time
import requests
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# 스크래핑 대상 정부 보도자료 RSS
# 2026-07-05 FABLE 실측 교체: 구 5개 피드 전멸(404·HTML오응답·타임아웃) → 생존 검증된 6개.
# {BIZINFO_PORTAL_KEY}는 _resolve_rss_url이 환경변수로 치환(키 없으면 해당 소스 skip).
PRESS_SOURCES = [
    {
        "name": "중소벤처기업부(보도자료)",
        "rss": "https://www.mss.go.kr/rss/smba/board/86.do",
        "category": "중소기업·창업",
    },
    {
        "name": "중소벤처기업부(사업공고)",
        "rss": "https://www.mss.go.kr/rss/smba/board/310.do",
        "category": "중소기업·창업",
    },
    {
        "name": "중소벤처기업부(공지사항)",
        "rss": "https://www.mss.go.kr/rss/smba/board/81.do",
        "category": "중소기업·창업",
    },
    {
        "name": "고용노동부(알려드립니다)",
        "rss": "https://www.moel.go.kr/rss/notice.do",
        "category": "고용·노동",
    },
    {
        "name": "고용노동부(정책자료)",
        "rss": "https://www.moel.go.kr/rss/policy.do",
        "category": "고용·노동",
    },
    {
        "name": "기업마당(지원사업)",
        "rss": "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do?crtfcKey={BIZINFO_PORTAL_KEY}&searchCnt=20",
        "category": "중소기업·창업",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

MAX_ACTIVE = 5  # 동시 활성 이슈 최대 수


def _resolve_rss_url(template: str) -> str | None:
    """RSS URL 템플릿의 {ENV_KEY} placeholder를 환경변수로 치환.
    필수 키가 비어 있으면 None 반환(해당 소스 skip — 인증오류 헛호출 방지)."""
    if "{" not in template:
        return template
    values = {}
    for k in re.findall(r"\{(\w+)\}", template):
        v = os.environ.get(k, "")
        if not v:
            return None  # 필수 키 미설정 → skip
        values[k] = v
    return template.format(**values)


def _count_by_source(items: list[dict]) -> dict:
    """소스별 수집 건수 집계 (관측성 — 소스 사망을 로그에서 조기 식별)."""
    counts: dict = {}
    for it in items:
        name = it.get("source_name") or "?"
        counts[name] = counts.get(name, 0) + 1
    return counts


def _fetch_rss_titles(rss_url: str, max_items: int = 10) -> list[dict]:
    """RSS 피드에서 최신 기사 제목·링크 수집"""
    try:
        resp = requests.get(rss_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.content)
        items = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()
            if title and len(title) > 5:
                items.append({"title": title, "link": link, "desc": desc[:300]})
            if len(items) >= max_items:
                break
        return items
    except Exception as e:
        print(f"  [issue_monitor] RSS 수집 실패 ({rss_url[:50]}): {e}")
        return []


def _collect_press_releases() -> list[dict]:
    """전체 출처에서 보도자료 수집"""
    all_items = []
    for src in PRESS_SOURCES:
        rss = src.get("rss")
        if not rss:
            continue
        resolved = _resolve_rss_url(rss)
        if resolved is None:
            print(f"  [issue_monitor] 키 미설정으로 건너뜀: {src['name']}")
            continue
        items = _fetch_rss_titles(resolved, max_items=8)
        for it in items:
            it["source_name"] = src["name"]
            it["category"] = src["category"]
        all_items.extend(items)
        time.sleep(0.3)
    return all_items


def _generate_hot_issues(press_items: list[dict], api_key: str, count: int = 5) -> list[dict]:
    """Gemini로 핫이슈 선정 + 분석·받는방법 생성"""
    if not press_items:
        return []
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-2.5-flash")

        items_text = "\n".join(
            f"[{i+1}] ({it['source_name']}/{it['category']}) {it['title']}"
            for i, it in enumerate(press_items[:40])
        )

        prompt = f"""당신은 정부 지원금·보조금 전문가입니다.
아래는 최근 정부 보도자료 목록입니다.

{items_text}

이 중에서 소상공인·중소기업·개인이 실질적으로 관심가질 지원금/보조금/정책 이슈 {count}개를 선정하고,
각각에 대해 JSON 배열로 반환하세요.

조건:
- 실제 지원금·보조금·정책자금·혜택이 있는 이슈만 선정
- 유가·에너지·창업·고용 등 시의성 있는 이슈 우선
- 각 이슈마다:
  - ticker_text: 티커에 표시할 짧은 문구 (20자 이내, 이모지 1개 포함)
  - title: 이슈 제목 (30자 이내)
  - summary: 핵심 요약 (60자 이내)
  - detail: 마크다운 형식 상세 내용 (받는 방법, 신청 자격, 기관명 포함, 300자 이내)
  - category: 카테고리 (중소기업/소상공인/개인/창업/고용/주거/에너지 중 하나)
  - source_name: 출처 기관명
  - source_url: 관련 URL (없으면 빈 문자열)

JSON 배열만 반환:
[{{"ticker_text":"...", "title":"...", "summary":"...", "detail":"...", "category":"...", "source_name":"...", "source_url":"..."}}]"""

        response = model.generate_content(prompt)
        text = response.text.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        issues = json.loads(text)
        return [i for i in issues if isinstance(i, dict) and i.get("title")][:count]
    except Exception as e:
        print(f"  [issue_monitor] AI 생성 오류: {e}")
        return []


def _match_announcement(cur, title: str, category: str) -> tuple[int | None, str | None]:
    """
    이슈 제목·카테고리로 우리 공고 DB에서 가장 유사한 공고를 찾는다.
    반환: (announcement_id, deadline_date) or (None, None)
    마감일이 지난 공고는 제외.
    """
    # 제목에서 핵심 키워드 추출 (2자 이상 단어)
    import re
    keywords = [w for w in re.split(r'[\s·\-—,·/]+', title) if len(w) >= 2][:4]
    if not keywords:
        return None, None

    for kw in keywords:
        try:
            cur.execute(
                """SELECT announcement_id, deadline_date::text
                   FROM announcements
                   WHERE title ILIKE %s
                     AND is_archived = FALSE
                     AND (deadline_date IS NULL OR deadline_date >= CURRENT_DATE)
                   ORDER BY deadline_date ASC NULLS LAST
                   LIMIT 1""",
                (f"%{kw}%",),
            )
            row = cur.fetchone()
            if row:
                print(f"  [issue_monitor] 공고 매칭: '{kw}' → id={row['announcement_id']} 마감={row['deadline_date']}")
                return row["announcement_id"], row["deadline_date"]
        except Exception:
            pass
    return None, None


def run_issue_monitoring(auto_activate: bool = False) -> dict:
    """
    보도자료 수집 → AI 분석 → 공고 매칭 → hot_issues 저장
    auto_activate=True: 기존 활성 이슈 유지하면서 새 초안 추가
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return {"error": "GEMINI_API_KEY 미설정"}

    print("[issue_monitor] 보도자료 수집 시작...")
    press_items = _collect_press_releases()
    per_source = _count_by_source(press_items)
    print(f"[issue_monitor] 수집 완료: {len(press_items)}건 (소스별: {per_source})")

    if not press_items:
        return {"error": "보도자료 수집 실패", "collected": 0, "per_source": per_source}

    issues = _generate_hot_issues(press_items, api_key, count=5)
    if not issues:
        return {"error": "AI 이슈 생성 실패", "collected": len(press_items)}

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    saved = 0
    for issue in issues:
        try:
            ann_id, ann_deadline = _match_announcement(
                cur,
                issue.get("title", ""),
                issue.get("category", ""),
            )
            cur.execute(
                """INSERT INTO hot_issues
                       (ticker_text, title, summary, detail, category,
                        source_name, source_url, is_active, auto_generated,
                        sort_order, linked_announcement_id, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, 99, %s, %s)""",
                (
                    issue.get("ticker_text", "")[:30],
                    issue.get("title", "")[:60],
                    issue.get("summary", "")[:120],
                    issue.get("detail", ""),
                    issue.get("category", ""),
                    issue.get("source_name", ""),
                    issue.get("source_url", ""),
                    auto_activate,
                    ann_id,
                    ann_deadline,   # None이면 NULL — 만료일 모르는 경우 영구 표시
                ),
            )
            conn.commit()
            saved += 1
        except Exception as e:
            conn.rollback()
            print(f"  [issue_monitor] 저장 오류: {e}")

    conn.close()
    print(f"[issue_monitor] 완료: {saved}건 저장 (auto_activate={auto_activate})")
    return {"collected": len(press_items), "generated": len(issues), "saved": saved,
            "per_source": per_source}
