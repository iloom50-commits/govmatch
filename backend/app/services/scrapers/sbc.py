from .base_enhanced import EnhancedBaseScraper
from typing import List, Dict
from datetime import datetime
try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None
    PlaywrightTimeout = Exception
    PLAYWRIGHT_AVAILABLE = False
from bs4 import BeautifulSoup
from app.services.ai_service import ai_service
from app.services.scrapers.smart_html_parser import SmartHTMLParser

MAX_ITEMS = 10


class SBCScraper(EnhancedBaseScraper):
    """중소벤처기업진흥공단 (SBC) 스크래퍼"""
    BASE_URL = "https://www.sbc.or.kr"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parser = SmartHTMLParser()

    async def scrape(self) -> List[Dict]:
        print(f"[{datetime.now()}] Starting SBC Scrape...")
        results: List[Dict] = []
        pw = None
        browser = None

        try:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })

            list_url = f"{self.BASE_URL}/nsh/svc/svcInfo.do"
            print(f"  Loading SBC list page: {list_url}")
            await page.goto(list_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)

            announcements = self._extract_links(await page.content())

            if not announcements:
                print("  No links from HTML, trying DOM click navigation...")
                rows = page.locator("table tbody tr a, .board-list a, .list-area a")
                count = await rows.count()
                for i in range(min(count, MAX_ITEMS)):
                    text = (await rows.nth(i).text_content() or "").strip()
                    if len(text) > 10:
                        announcements.append({"title": text, "url": "", "click_idx": i})

            print(f"  Found {len(announcements)} links. Processing top {MAX_ITEMS}...")

            for ann in announcements[:MAX_ITEMS]:
                try:
                    if ann.get("click_idx") is not None:
                        row_link = rows.nth(ann["click_idx"])
                        async with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                            await row_link.click()
                        await page.wait_for_timeout(1500)
                    else:
                        await page.goto(ann["url"], wait_until="domcontentloaded", timeout=30000)

                    actual_url = page.url
                    if "main.do" in actual_url or actual_url.rstrip("/") == self.BASE_URL.rstrip("/"):
                        print(f"  ⏩ Skipped (main page): {ann['title'][:30]}")
                        await self._go_back(page, list_url)
                        continue

                    detail_html = await page.content()
                    parsed_info = self.parser.parse(detail_html, actual_url)

                    program_data = {
                        "title": ann["title"],
                        "description": parsed_info.get("main_content", "")[:3000],
                        "department": "중소벤처기업부",
                        "category": "Loan/Investment",
                        "region": "All",
                        "url": actual_url,
                        "status": "Open",
                        "origin_source": "sbc",
                    }

                    eligibility = await ai_service.extract_structured_eligibility(program_data["description"])
                    if eligibility:
                        program_data["eligibility_logic"] = eligibility

                    results.append(program_data)
                    print(f"  ✅ Scraped: {ann['title'][:40]}")

                except PlaywrightTimeout:
                    print(f"  ⏱ Timeout: {ann['title'][:30]}")
                except ConnectionError as e:
                    print(f"  🔌 Connection error: {e}")
                except Exception as e:
                    print(f"  ❌ Error: {type(e).__name__}: {e}")
                finally:
                    await self._go_back(page, list_url)

        except PlaywrightTimeout:
            print("❌ SBC list page timeout — skipping scraper")
        except Exception as e:
            print(f"❌ SBCScraper fatal: {type(e).__name__}: {e}")
        finally:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()

        print(f"  SBC scrape done — {len(results)} items collected")
        return results

    def _extract_links(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        keywords = ("공고", "지원", "사업", "모집", "융자", "정책자금")
        seen_urls: set = set()
        items: List[Dict] = []

        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True)
            href = link["href"]
            if href.startswith("#") or href == "javascript:void(0)" or "main.do" in href:
                continue
            if not any(kw in text for kw in keywords) or len(text) <= 10:
                continue
            if not href.startswith("http"):
                href = self.BASE_URL + (href if href.startswith("/") else f"/{href}")
            if href in seen_urls:
                continue
            seen_urls.add(href)
            items.append({"title": text, "url": href})

        return items

    @staticmethod
    async def _go_back(page, list_url: str) -> None:
        try:
            await page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(800)
        except Exception:
            pass
