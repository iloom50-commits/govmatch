import asyncio
import psycopg2
import psycopg2.extras
import json
import requests
from bs4 import BeautifulSoup
from app.services.scrapers.sbc import SBCScraper
from app.services.public_api_service import gov_api_service
from app.services.admin_scraper import admin_scraper
from app.services.ai_service import ai_service
from app.config import DATABASE_URL

DOMAIN_ONLY_BLOCKLIST = {
    "https://www.k-startup.go.kr",
    "http://www.k-startup.go.kr",
    "https://www.mss.go.kr",
    "https://www.sbc.or.kr",
    "https://www.bizinfo.go.kr",
    "https://www.msit.go.kr",
    "https://www.foodpolis.kr",
}

def _is_valid_detail_url(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    if "#" in url and url.split("#")[1] in ("", "view"):
        return False
    if "main.do" in url:
        return False
    stripped = url.rstrip("/")
    if stripped in DOMAIN_ONLY_BLOCKLIST:
        return False
    return True


_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

_REMOVE_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "iframe"}


def _fetch_detail_text(url: str, max_chars: int = 8000) -> str:
    """상세 페이지 HTML에서 본문 텍스트를 추출. 실패 시 빈 문자열 반환."""
    try:
        resp = requests.get(url, headers=_FETCH_HEADERS, timeout=12, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        if resp.status_code != 200:
            return ""

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all(_REMOVE_TAGS):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 1]
        body = "\n".join(lines)
        return body[:max_chars]
    except Exception as e:
        print(f"    Detail fetch failed ({url[:50]}): {e}")
        return ""


class SyncService:
    """모든 스크래퍼 및 공식 API를 총괄하고 데이터를 동기화하는 서비스"""

    def __init__(self, database_url=DATABASE_URL):
        self.database_url = database_url
        self.scrapers = [
            SBCScraper(),
        ]

    async def sync_all(self):
        print("Starting Global Sync (APIs + Scrapers + Admin Targets)...")
        all_results = []

        # 1. Official Government API Ingestion
        try:
            print("  Ingesting from Official Government APIs...")
            ks_results = await gov_api_service.fetch_kstartup_programs()
            all_results.extend(ks_results)

            # MSIT R&D: 여러 페이지 수집 (최신 공고 50건)
            for pg in range(1, 6):
                msit_page = await gov_api_service.fetch_msit_programs(page=pg, per_page=10)
                if not msit_page:
                    break
                all_results.extend(msit_page)

            bizinfo_results = await gov_api_service.fetch_bizinfo_programs()
            all_results.extend(bizinfo_results)

            # 중소벤처24 공고정보 (기정원 토큰 필요)
            smes24_results = await gov_api_service.fetch_smes24_programs()
            all_results.extend(smes24_results)

            # 한국식품산업클러스터진흥원
            foodpolis_results = await gov_api_service.fetch_foodpolis_programs()
            all_results.extend(foodpolis_results)
        except Exception as e:
            print(f"  Government API error: {e}")

        # 2. Admin Targeted URLs (Dynamic AI Scraping)
        try:
            print("  Processing Admin Targeted URLs...")
            await admin_scraper.run_all()
        except Exception as e:
            print(f"  Admin Scraper error: {e}")

        # 3. Scrapers (Fallback or Additional)
        for scraper in self.scrapers:
            try:
                results = await scraper.scrape()
                all_results.extend(results)
            except Exception as e:
                print(f"Error running scraper {scraper.__class__.__name__}: {e}")

        # 데이터베이스 저장
        await self._save_to_db(all_results)
        print(f"Sync complete. Total {len(all_results)} items processed.")

    async def _save_to_db(self, results):
        conn = psycopg2.connect(self.database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        cursor = conn.cursor()

        for item in results:
            try:
                if not _is_valid_detail_url(item.get('url', '')):
                    print(f"  Skipping invalid URL: {item.get('title', '')[:30]} -> {item.get('url', '')}")
                    continue

                cursor.execute("SELECT announcement_id FROM announcements WHERE origin_url = %s", (item['url'],))
                exists = cursor.fetchone()

                if exists:
                    # 이미 존재하는 공고는 스킵 (사용자 요청: 수집된 공고문 제외)
                    print(f"  Skipping duplicate: {item['title'][:20]}...")
                    continue

                # 2. 신규 공고: 상세 페이지 본문을 가져와서 AI에 전달
                print(f"  AI Analyzing NEW item: {item['title'][:30]}...")
                detail_text = _fetch_detail_text(item['url'])
                if detail_text and len(detail_text) > 100:
                    full_text = f"제목: {item['title']}\n\n[상세 페이지 본문]\n{detail_text}"
                    print(f"    Detail page fetched: {len(detail_text)} chars")
                else:
                    full_text = f"제목: {item['title']}\n내용: {item.get('description', '')}"
                details = await ai_service.extract_program_details(full_text)

                if details:
                    existing_eligibility = item.get("eligibility_logic")
                    ai_eligibility = details.get("eligibility_logic", {})
                    if not isinstance(ai_eligibility, dict):
                        ai_eligibility = {}
                    # business_type, target_keywords를 eligibility_logic에 포함
                    if details.get("business_type"):
                        ai_eligibility["business_type"] = details["business_type"]
                    if details.get("target_keywords"):
                        ai_eligibility["target_keywords"] = details["target_keywords"]
                    if existing_eligibility and isinstance(existing_eligibility, dict) and existing_eligibility:
                        merged_elig = {**ai_eligibility, **existing_eligibility}
                    else:
                        merged_elig = ai_eligibility

                    # AI 생성 순수 텍스트 요약 우선 (HTML 원문 대체)
                    ai_summary = (
                        details.get("summary_text")
                        or details.get("description")
                        or item.get("description", "")
                    )

                    item.update({
                        "title": details.get("title") or item['title'],
                        "department": details.get("department") or item.get("department"),
                        "category": details.get("category") or item.get("category"),
                        "eligibility_logic": merged_elig,
                        "description": ai_summary,
                        "deadline_date": details.get("deadline_date") or item.get("deadline_date")
                    })

                elig = item.get('eligibility_logic', {})
                if not isinstance(elig, dict):
                    elig = {}
                eligibility_json = json.dumps(elig, ensure_ascii=False)

                years_limit = elig.get("max_founding_years") or elig.get("maxAblbiz")
                revenue_limit = elig.get("max_revenue") or elig.get("maxSalsAmt")
                employee_limit = elig.get("max_employees") or elig.get("mixEmplyCnt")
                industry_codes = elig.get("industry") or elig.get("target_industry_codes")
                if isinstance(industry_codes, list):
                    industry_codes = ",".join(str(c) for c in industry_codes)

                query = """
                INSERT INTO announcements (title, origin_url, summary_text, eligibility_logic, department, category, origin_source, region, deadline_date, established_years_limit, revenue_limit, employee_limit, target_industry_codes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    item['title'], item['url'], item.get('description', ''), eligibility_json,
                    item.get('department', ''), item.get('category', ''), item.get('origin_source', ''),
                    item.get('region', 'All'), item.get('deadline_date'),
                    years_limit, revenue_limit, employee_limit, industry_codes
                ))
            except Exception as e:
                print(f"Error saving item {item.get('title','?')}: {e}")

        conn.commit()
        conn.close()

sync_service = SyncService()
