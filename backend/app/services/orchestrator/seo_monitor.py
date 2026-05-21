"""
seo_monitor.py — Google Search Console 데이터 수집 + Gemini SEO 분석

매일 오케스트레이터 Step 5로 실행:
  - 어제 클릭수·노출수·CTR·순위 수집
  - 상위 페이지 / 상위 검색어 분석
  - 개선 기회 탐지 (노출 높고 CTR 낮은 페이지)
  - Gemini가 액션 아이템 생성
"""
import json
import os
from datetime import date, timedelta


SITE_URL = "https://www.govmatch.kr/"


def _get_access_token() -> str:
    """Refresh token → access token 발급."""
    import requests
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        json={
            "client_id": os.environ.get("GSC_CLIENT_ID", ""),
            "client_secret": os.environ.get("GSC_CLIENT_SECRET", ""),
            "refresh_token": os.environ.get("GSC_REFRESH_TOKEN", ""),
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"access_token 발급 실패: {data}")
    return token


def _gsc_query(token: str, body: dict) -> dict:
    """Search Console searchAnalytics/query 호출."""
    import requests
    resp = requests.post(
        f"https://www.googleapis.com/webmasters/v3/sites/{SITE_URL}/searchAnalytics/query",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=15,
    )
    return resp.json()


def _call_gemini(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return ""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            os.environ.get("GEMINI_BATCH_MODEL", "gemini-2.5-flash"),
            generation_config={"temperature": 0.3, "max_output_tokens": 1024},
        )
        return (model.generate_content(prompt).text or "").strip()
    except Exception as e:
        print(f"[seo] Gemini 오류: {e}")
        return ""


def check_seo() -> dict:
    """
    Search Console 데이터 수집 + AI 분석.
    반환: {
      "total": {clicks, impressions, ctr, position},
      "top_pages": [...],
      "top_queries": [...],
      "opportunities": [...],
      "ai_suggestions": str,
      "error": str (실패 시)
    }
    """
    required = ["GSC_REFRESH_TOKEN", "GSC_CLIENT_ID", "GSC_CLIENT_SECRET"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"[seo] 환경변수 미설정: {missing} — 스킵")
        return {"skipped": True, "reason": f"env missing: {missing}"}

    try:
        token = _get_access_token()
    except Exception as e:
        print(f"[seo] 토큰 발급 실패: {e}")
        return {"error": str(e)}

    # 날짜 범위: 3일 전 ~ 어제 (Search Console은 최소 2~3일 지연)
    end_date = (date.today() - timedelta(days=2)).isoformat()
    start_date = (date.today() - timedelta(days=3)).isoformat()

    try:
        # ── 전체 요약 (날짜 집계) ──
        summary_resp = _gsc_query(token, {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["date"],
            "rowLimit": 7,
        })
        rows = summary_resp.get("rows", [])
        total_clicks = sum(r.get("clicks", 0) for r in rows)
        total_impressions = sum(r.get("impressions", 0) for r in rows)
        avg_ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions else 0
        avg_position = round(sum(r.get("position", 0) for r in rows) / len(rows), 1) if rows else 0

        # ── 상위 페이지 (클릭 기준 Top 10) ──
        page_resp = _gsc_query(token, {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["page"],
            "rowLimit": 10,
            "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}],
        })
        top_pages = [
            {
                "page": r["keys"][0].replace(SITE_URL, "/"),
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "ctr": round(r.get("ctr", 0) * 100, 1),
                "position": round(r.get("position", 0), 1),
            }
            for r in page_resp.get("rows", [])
        ]

        # ── 상위 검색어 (클릭 기준 Top 10) ──
        query_resp = _gsc_query(token, {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["query"],
            "rowLimit": 10,
            "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}],
        })
        top_queries = [
            {
                "query": r["keys"][0],
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "ctr": round(r.get("ctr", 0) * 100, 1),
                "position": round(r.get("position", 0), 1),
            }
            for r in query_resp.get("rows", [])
        ]

        # ── 개선 기회: 노출 50+ && CTR 3% 미만 ──
        opp_resp = _gsc_query(token, {
            "startDate": (date.today() - timedelta(days=9)).isoformat(),
            "endDate": end_date,
            "dimensions": ["page"],
            "rowLimit": 50,
            "orderBy": [{"fieldName": "impressions", "sortOrder": "DESCENDING"}],
        })
        opportunities = [
            {
                "page": r["keys"][0].replace(SITE_URL, "/"),
                "impressions": r.get("impressions", 0),
                "ctr": round(r.get("ctr", 0) * 100, 1),
                "position": round(r.get("position", 0), 1),
            }
            for r in opp_resp.get("rows", [])
            if r.get("impressions", 0) >= 50 and r.get("ctr", 0) * 100 < 3.0
        ][:5]

    except Exception as e:
        print(f"[seo] API 호출 오류: {e}")
        return {"error": str(e)}

    # ── Gemini SEO 분석 ──
    prompt = f"""당신은 한국 정부지원사업 매칭 서비스(govmatch.kr)의 SEO 전문가입니다.

아래 Google Search Console 데이터를 분석하고 구체적인 개선 액션 3가지를 제안하세요.

[기간: {start_date} ~ {end_date}]
총 클릭: {total_clicks}회 | 총 노출: {total_impressions}회 | 평균 CTR: {avg_ctr}% | 평균 순위: {avg_position}위

상위 검색어 (클릭순):
{json.dumps(top_queries[:5], ensure_ascii=False, indent=2)}

CTR 개선 기회 페이지 (노출 많고 CTR 낮음):
{json.dumps(opportunities[:3], ensure_ascii=False, indent=2)}

요구사항:
- 각 액션은 구체적으로 (어떤 페이지/키워드를, 어떻게 수정할지)
- 한국어로 간결하게 (항목당 2줄 이내)
- 번호 매겨서 3가지만"""

    ai_suggestions = _call_gemini(prompt)

    result = {
        "period": f"{start_date} ~ {end_date}",
        "total": {
            "clicks": total_clicks,
            "impressions": total_impressions,
            "ctr": avg_ctr,
            "position": avg_position,
        },
        "top_pages": top_pages,
        "top_queries": top_queries,
        "opportunities": opportunities,
        "ai_suggestions": ai_suggestions,
    }

    print(f"[seo] 완료 — 클릭 {total_clicks}회, 노출 {total_impressions}회, CTR {avg_ctr}%, 순위 {avg_position}위")
    return result
