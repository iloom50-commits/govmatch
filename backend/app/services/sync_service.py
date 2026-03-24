import asyncio
import psycopg2
import psycopg2.extras
import json
import requests
from bs4 import BeautifulSoup
from app.services.scrapers.sbc import SBCScraper
from app.services.public_api_service import gov_api_service, GovernmentAPIService
from app.services.admin_scraper import admin_scraper
from app.services.ai_service import ai_service
from app.config import DATABASE_URL

import re as _re

def _normalize_title(title: str) -> str:
    """제목 정규화: 미세한 표기 차이를 통일하여 중복 비교에 사용."""
    t = title.strip()
    t = t.replace("년도", "년").replace("　", " ")  # 전각 공백 → 반각
    t = _re.sub(r'\s+', '', t)  # 모든 공백 제거
    t = _re.sub(r'[\[\]()（）【】]', '', t)  # 괄호류 제거
    return t.lower()


DOMAIN_ONLY_BLOCKLIST = {
    "https://www.k-startup.go.kr",
    "http://www.k-startup.go.kr",
    "https://www.mss.go.kr",
    "https://www.sbc.or.kr",
    "https://www.bizinfo.go.kr",
    "https://www.msit.go.kr",
    "https://www.foodpolis.kr",
    "https://fanfandaero.kr",
    "https://www.exportvoucher.com",
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

            # 보조금24 (정부24 공공서비스) - 지자체·구청·도청 포함
            gov24_results = await gov_api_service.fetch_gov24_services()
            all_results.extend(gov24_results)

            # 판판대로 (판로지원 사업)
            fanfan_results = await gov_api_service.fetch_fanfandaero_programs()
            all_results.extend(fanfan_results)

            # 수출바우처 (수출지원기반활용사업)
            export_results = await gov_api_service.fetch_exportvoucher_programs()
            all_results.extend(export_results)

            # 개인 복지서비스: 주 1회(월요일)만 전체 동기화, 나머지 날은 스킵
            import datetime as _dt
            if _dt.date.today().weekday() == 0:  # 0 = Monday
                print("  [Weekly] 개인 복지서비스 전체 동기화 (월요일)...")
                individual_results = await gov_api_service.fetch_gov24_individual_services()
                all_results.extend(individual_results)

                local_welfare_results = await gov_api_service.fetch_local_gov_welfare()
                all_results.extend(local_welfare_results)
            else:
                print("  [Skip] 개인 복지서비스 — 주 1회(월요일)만 전체 동기화")
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

        # 순환 학습: 수집 결과에서 카테고리별 트렌드 지식 저장
        try:
            self._save_crawl_knowledge(all_results)
        except Exception as e:
            print(f"  [Knowledge] crawl knowledge save error (non-critical): {e}")

    async def _save_to_db(self, results, use_ai=False):
        """DB 저장. use_ai=False면 API 기본 데이터만 빠르게 저장."""
        # Supabase Direct 연결 (Transaction Pooler 6543 -> Direct 5432)
        db_url = self.database_url.replace(":6543/", ":5432/")
        conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute("SET statement_timeout = '60000'")  # 60초
        saved, skipped, errors = 0, 0, 0

        # 기존 제목 정규화 캐시 로드 (중복 방지용)
        cursor.execute("SELECT title, region, target_type, origin_source FROM announcements")
        existing_titles: set[str] = set()
        for row in cursor.fetchall():
            nt = _normalize_title(row['title'])
            is_ind = row.get('target_type') in ('individual', 'both') or row.get('origin_source', '') in ('gov24-individual-api', 'local-welfare-api', 'gov24-api')
            if is_ind:
                existing_titles.add(f"{nt}|{row.get('region') or 'All'}")
            else:
                existing_titles.add(nt)
        print(f"    Loaded {len(existing_titles)} existing title keys for dedup")

        for item in results:
            try:
                if not _is_valid_detail_url(item.get('url', '')):
                    skipped += 1
                    continue

                # AI 분석 모드: 상세 페이지 + AI 분석
                if use_ai:
                    detail_text = _fetch_detail_text(item['url'])
                    if detail_text and len(detail_text) > 100:
                        full_text = f"제목: {item['title']}\n\n[상세 페이지 본문]\n{detail_text}"
                    else:
                        full_text = f"제목: {item['title']}\n내용: {item.get('description', '')}"
                    details = await ai_service.extract_program_details(full_text)

                    if details:
                        existing_eligibility = item.get("eligibility_logic")
                        ai_eligibility = details.get("eligibility_logic", {})
                        if not isinstance(ai_eligibility, dict):
                            ai_eligibility = {}
                        if details.get("business_type"):
                            ai_eligibility["business_type"] = details["business_type"]
                        if details.get("target_keywords"):
                            ai_eligibility["target_keywords"] = details["target_keywords"]
                        if existing_eligibility and isinstance(existing_eligibility, dict) and existing_eligibility:
                            merged_elig = {**ai_eligibility, **existing_eligibility}
                        else:
                            merged_elig = ai_eligibility

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

                target_type = item.get('target_type', 'business')

                # 제목 정규화 기반 중복 방지
                norm_title = _normalize_title(item['title'])
                region_val = item.get('region', 'All') or 'All'
                is_individual = target_type in ('individual', 'both') or item.get('origin_source', '') in ('gov24-individual-api', 'local-welfare-api', 'gov24-api')

                if is_individual:
                    dedup_key = f"{norm_title}|{region_val}"
                else:
                    dedup_key = norm_title

                if dedup_key in existing_titles:
                    skipped += 1
                    continue
                existing_titles.add(dedup_key)

                # 날짜 안전 정규화 (공백, day=0 등 처리)
                raw_deadline = item.get('deadline_date')
                deadline_safe = GovernmentAPIService._normalize_date(raw_deadline) if raw_deadline else None
                # day=00 같은 비정상 날짜 최종 방어
                if deadline_safe and deadline_safe.endswith("-00"):
                    deadline_safe = None

                query = """
                INSERT INTO announcements (title, origin_url, summary_text, eligibility_logic, department, category, origin_source, region, deadline_date, established_years_limit, revenue_limit, employee_limit, target_industry_codes, target_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (origin_url) DO UPDATE SET
                    deadline_date = COALESCE(EXCLUDED.deadline_date, announcements.deadline_date),
                    established_years_limit = COALESCE(EXCLUDED.established_years_limit, announcements.established_years_limit),
                    revenue_limit = COALESCE(EXCLUDED.revenue_limit, announcements.revenue_limit),
                    employee_limit = COALESCE(EXCLUDED.employee_limit, announcements.employee_limit),
                    eligibility_logic = CASE
                        WHEN EXCLUDED.eligibility_logic IS NOT NULL AND EXCLUDED.eligibility_logic != '{}' AND EXCLUDED.eligibility_logic != ''
                        THEN EXCLUDED.eligibility_logic
                        ELSE COALESCE(announcements.eligibility_logic, EXCLUDED.eligibility_logic)
                    END,
                    summary_text = CASE
                        WHEN announcements.summary_text IS NULL OR announcements.summary_text = ''
                        THEN EXCLUDED.summary_text
                        ELSE announcements.summary_text
                    END,
                    target_type = COALESCE(EXCLUDED.target_type, announcements.target_type)
                """
                cursor.execute(query, (
                    item['title'], item['url'], item.get('description', ''), eligibility_json,
                    item.get('department', ''), item.get('category', ''), item.get('origin_source', ''),
                    item.get('region', 'All'), deadline_safe,
                    years_limit, revenue_limit, employee_limit, industry_codes, target_type
                ))
                saved += 1
                if saved % 100 == 0:
                    print(f"    ... {saved} saved so far")
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"Error saving item {item.get('title','?')[:30]}: {e}")

        conn.close()
        print(f"  DB Save: {saved} saved, {skipped} skipped, {errors} errors")

    def _save_crawl_knowledge(self, results):
        """
        수집AI → 지식 저장소: 수집 결과에서 카테고리별 트렌드/패턴 저장.
        공고AI, 공통AI가 이 지식을 참조하여 상담 품질 향상.
        """
        from app.services.ai_consultant import save_knowledge
        import datetime as _dt

        db_url = self.database_url.replace(":6543/", ":5432/")
        conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)

        # 카테고리별 수집 통계
        category_stats = {}
        for item in results:
            cat = item.get("category", "기타") or "기타"
            if cat not in category_stats:
                category_stats[cat] = {"count": 0, "titles": [], "departments": set()}
            category_stats[cat]["count"] += 1
            category_stats[cat]["titles"].append(item.get("title", "")[:60])
            dept = item.get("department", "")
            if dept:
                category_stats[cat]["departments"].add(dept)

        period = _dt.date.today().strftime("%Y-%m")

        for cat, stats in category_stats.items():
            if stats["count"] < 2:
                continue  # 소수 공고는 트렌드 가치 낮음

            save_knowledge(
                source="crawler",
                knowledge_type="trend",
                content={
                    "keyword": cat,
                    "count": stats["count"],
                    "period": period,
                    "sample_titles": stats["titles"][:5],
                    "departments": list(stats["departments"])[:5],
                },
                db_conn=conn,
                category=cat,
                confidence=0.6,
            )

        # 오류 패턴이 많은 카테고리 정보도 지식화 (knowledge_base에서 조회)
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT category, COUNT(*) as error_count
                FROM knowledge_base
                WHERE knowledge_type = 'error' AND confidence >= 0.5
                  AND created_at >= NOW() - INTERVAL '30 days'
                GROUP BY category
                HAVING COUNT(*) >= 3
                ORDER BY error_count DESC
                LIMIT 5
            """)
            for row in cur.fetchall():
                r = dict(row)
                save_knowledge(
                    source="crawler",
                    knowledge_type="insight",
                    content={
                        "relationship": f"'{r['category']}' 카테고리에서 최근 30일간 부정확 피드백 {r['error_count']}건 발생. 이 카테고리 상담 시 특히 정확한 데이터 확인 필요.",
                        "error_count": r["error_count"],
                        "period": period,
                    },
                    db_conn=conn,
                    category=r["category"],
                    confidence=0.8,
                )
        except Exception as e:
            print(f"  [Knowledge] error pattern analysis failed: {e}")

        conn.close()
        print(f"  [Knowledge] Saved crawl trends for {len(category_stats)} categories")


sync_service = SyncService()
