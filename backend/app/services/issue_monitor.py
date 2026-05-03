"""
issue_monitor.py — 정부 보도자료 스캔 → Hot이슈 자동 생성
주 2회 스케줄러 또는 관리자 수동 실행
"""
import os
import json
import time
import requests
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# 스크래핑 대상 정부 보도자료 RSS/페이지
PRESS_SOURCES = [
    {
        "name": "기획재정부",
        "url": "https://www.moef.go.kr/nw/nes/detailNesDtaView.do?menuNo=4010100&bbsId=MOSFBBS_000000000028&nttId=",
        "rss": "https://www.moef.go.kr/rss/moefRss.do?menuNo=4010100",
        "category": "경제·재정",
    },
    {
        "name": "중소벤처기업부",
        "url": "https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=86",
        "rss": "https://www.mss.go.kr/site/smba/rss/smbaRss.do",
        "category": "중소기업·창업",
    },
    {
        "name": "고용노동부",
        "url": "https://www.moel.go.kr/news/news/newslist.do",
        "rss": "https://www.moel.go.kr/rss/rssMain.do",
        "category": "고용·노동",
    },
    {
        "name": "국토교통부",
        "rss": "https://www.molit.go.kr/portal/rss/rss.do",
        "category": "주거·교통",
    },
    {
        "name": "보건복지부",
        "rss": "https://www.mohw.go.kr/react/al/rss.jsp",
        "category": "복지·보건",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

MAX_ACTIVE = 5  # 동시 활성 이슈 최대 수


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
        items = _fetch_rss_titles(rss, max_items=8)
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


def run_issue_monitoring(auto_activate: bool = False) -> dict:
    """
    보도자료 수집 → AI 분석 → hot_issues 저장
    auto_activate=True: 기존 활성 이슈 유지하면서 새 초안 추가
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return {"error": "GEMINI_API_KEY 미설정"}

    print("[issue_monitor] 보도자료 수집 시작...")
    press_items = _collect_press_releases()
    print(f"[issue_monitor] 수집 완료: {len(press_items)}건")

    if not press_items:
        return {"error": "보도자료 수집 실패", "collected": 0}

    issues = _generate_hot_issues(press_items, api_key, count=5)
    if not issues:
        return {"error": "AI 이슈 생성 실패", "collected": len(press_items)}

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    saved = 0
    for issue in issues:
        try:
            cur.execute(
                """INSERT INTO hot_issues
                       (ticker_text, title, summary, detail, category,
                        source_name, source_url, is_active, auto_generated, sort_order)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, 99)""",
                (
                    issue.get("ticker_text", "")[:30],
                    issue.get("title", "")[:60],
                    issue.get("summary", "")[:120],
                    issue.get("detail", ""),
                    issue.get("category", ""),
                    issue.get("source_name", ""),
                    issue.get("source_url", ""),
                    auto_activate,
                ),
            )
            conn.commit()
            saved += 1
        except Exception as e:
            conn.rollback()
            print(f"  [issue_monitor] 저장 오류: {e}")

    conn.close()
    print(f"[issue_monitor] 완료: {saved}건 저장 (auto_activate={auto_activate})")
    return {"collected": len(press_items), "generated": len(issues), "saved": saved}
