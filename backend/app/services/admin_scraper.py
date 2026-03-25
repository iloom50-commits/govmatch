import re
import psycopg2
import psycopg2.extras
import asyncio
from datetime import datetime
from urllib.parse import urljoin, urlparse
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None
    PLAYWRIGHT_AVAILABLE = False
from bs4 import BeautifulSoup
from app.services.ai_service import ai_service
from app.config import DATABASE_URL
import json

# 연속 실패 임계값: 이 횟수 이상이면 자동 복구 시도
_FAIL_THRESHOLD = 3

# 공고 목록에서 개별 링크로 보기 어려운 텍스트 패턴
_SKIP_LINK_TEXTS = {
    "홈", "home", "로그인", "회원가입", "마이페이지", "검색", "닫기", "이전", "다음",
    "처음", "끝", "목록", "더보기", "top", "위로", "사이트맵", "개인정보", "이용약관",
    "공지사항", "새창", "새 창", "pdf", "인쇄", "공유", "좋아요", "스크랩",
}

# 공고 상세 링크일 가능성이 높은 URL 패턴
_DETAIL_URL_PATTERNS = [
    r"view", r"detail", r"read", r"notice", r"board", r"bbs",
    r"seq=", r"idx=", r"id=", r"no=", r"nttId=", r"articleId=",
    r"bid=", r"num=", r"post", r"content",
]

# 공고 페이지를 찾기 위한 키워드 (자동 복구 시 사용)
_ANNOUNCEMENT_KEYWORDS = [
    "사업공고", "공고", "공지", "모집", "지원사업", "입찰", "안내",
    "notice", "board", "announcement",
]


def _is_likely_detail_link(href: str, text: str) -> bool:
    """공고 상세 페이지 링크 여부 판별"""
    if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
        return False
    text_clean = text.strip().lower()
    if text_clean in _SKIP_LINK_TEXTS or len(text_clean) < 4:
        return False
    # 공고 제목처럼 보이는 텍스트 (보통 10자 이상)
    if len(text.strip()) >= 8:
        return True
    # URL 패턴으로 판별
    return any(re.search(p, href, re.I) for p in _DETAIL_URL_PATTERNS)


def _extract_detail_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """목록 페이지에서 개별 공고 상세 링크 추출"""
    base_domain = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    seen = set()
    links = []

    # 테이블 안의 링크 우선 (대부분의 공고 목록은 table 구조)
    for table in soup.find_all("table"):
        for a in table.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(separator=" ", strip=True)
            if not _is_likely_detail_link(href, text):
                continue
            full_url = href if href.startswith("http") else urljoin(base_url, href)
            if full_url not in seen:
                seen.add(full_url)
                links.append(full_url)

    # 테이블 없으면 li/div 구조 탐색
    if not links:
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(separator=" ", strip=True)
            if not _is_likely_detail_link(href, text):
                continue
            full_url = href if href.startswith("http") else urljoin(base_url, href)
            # 같은 도메인 링크만
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                if full_url not in seen and full_url != base_url:
                    seen.add(full_url)
                    links.append(full_url)

    return links[:15]  # 한 목록당 최대 15건


_REMOVE_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "iframe"}


async def _fetch_page_text(page, url: str) -> str:
    """Playwright 페이지로 URL 접속 후 본문 텍스트 반환"""
    try:
        await page.goto(url, wait_until="networkidle", timeout=45000)
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup.find_all(_REMOVE_TAGS):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 1]
        return "\n".join(lines)[:10000]
    except Exception as e:
        print(f"      페이지 접속 실패 ({url[:50]}): {e}")
        return ""


class AdminScraper:
    """관리자가 등록한 URL을 AI로 분석하여 수집하는 동적 스크래퍼

    - 목록 페이지 URL → 개별 공고 링크 추출 → 각 공고 AI 분석 저장
    - 단일 공고 URL → 바로 AI 분석 저장 (기존 동작)
    - 헬스체크: 접속 실패 시 fail_count 증가, 연속 실패 시 자동 복구 시도
    """

    def __init__(self, database_url=DATABASE_URL):
        self.database_url = database_url

    async def run_all(self):
        if not PLAYWRIGHT_AVAILABLE:
            print("Playwright not installed - skipping admin scrape (cloud mode)")
            return

        conn = psycopg2.connect(self.database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM admin_urls WHERE is_active = 1")
        targets = cursor.fetchall()
        print(f"Starting Admin Targeted Scrape for {len(targets)} URLs...")

        failed_targets = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for target in targets:
                target_id = target["id"]
                url = target.get("recovered_url") or target["url"]
                source_name = target["source_name"]
                print(f"\n  [{source_name}] {url[:60]}")

                # --- 헬스체크: 접속 시도 ---
                success, error_reason, items = await self._try_scrape(url, browser)

                if success:
                    # 성공: fail_count 리셋, last_success 기록
                    saved = 0
                    for item in items:
                        if self._save_to_db(item, source_name, conn):
                            saved += 1
                    print(f"     -> {len(items)}건 분석 / {saved}건 신규 저장")
                    cursor.execute(
                        """UPDATE admin_urls SET
                            last_scraped = %s, last_success = %s,
                            fail_count = 0, last_fail_reason = NULL
                        WHERE id = %s""",
                        (datetime.now().isoformat(), datetime.now().isoformat(), target_id),
                    )
                    conn.commit()
                else:
                    # 실패: fail_count 증가
                    new_fail_count = (target.get("fail_count") or 0) + 1
                    cursor.execute(
                        """UPDATE admin_urls SET
                            last_scraped = %s, fail_count = %s, last_fail_reason = %s
                        WHERE id = %s""",
                        (datetime.now().isoformat(), new_fail_count, error_reason[:500], target_id),
                    )
                    conn.commit()
                    print(f"     실패 (연속 {new_fail_count}회): {error_reason[:80]}")

                    if new_fail_count >= _FAIL_THRESHOLD:
                        failed_targets.append({**target, "fail_count": new_fail_count, "last_fail_reason": error_reason})

            # --- 자동 복구 시도: 연속 실패 URL들 ---
            if failed_targets:
                print(f"\n{'='*50}")
                print(f"  자동 복구 시도: {len(failed_targets)}개 URL (연속 {_FAIL_THRESHOLD}회 이상 실패)")
                print(f"{'='*50}")
                for target in failed_targets:
                    recovered = await self._try_recover_url(target, browser, cursor, conn)
                    if not recovered:
                        print(f"     [{target['source_name']}] 자동 복구 실패 — 관리자 확인 필요")

            await browser.close()
        conn.close()

    async def _try_scrape(self, url: str, browser) -> tuple[bool, str, list]:
        """URL 스크래핑 시도. (성공여부, 에러사유, 결과목록) 반환"""
        try:
            items = await self._scrape_target(url, browser)
            return True, "", items
        except Exception as e:
            return False, str(e), []

    async def _try_recover_url(self, target: dict, browser, cursor, conn) -> bool:
        """루트 도메인에서 새 공고 페이지 URL을 자동 탐색"""
        original_url = target["url"]
        source_name = target["source_name"]
        parsed = urlparse(original_url)
        root_url = f"{parsed.scheme}://{parsed.netloc}"

        print(f"\n  [{source_name}] 루트 도메인 탐색: {root_url}")

        try:
            page = await browser.new_page()
            try:
                await page.goto(root_url, wait_until="networkidle", timeout=60000)
                content = await page.content()
            finally:
                await page.close()

            soup = BeautifulSoup(content, "html.parser")
            candidate_urls = []

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text(separator=" ", strip=True).lower()

                # 공고/모집/게시판 관련 링크 찾기
                if any(kw in text for kw in _ANNOUNCEMENT_KEYWORDS):
                    full_url = href if href.startswith("http") else urljoin(root_url, href)
                    if urlparse(full_url).netloc == parsed.netloc:
                        candidate_urls.append((full_url, text))

            if not candidate_urls:
                print(f"     공고 페이지 후보 없음")
                return False

            print(f"     공고 페이지 후보 {len(candidate_urls)}개 발견")

            # 각 후보 URL을 시도하여 공고 목록이 있는지 확인
            for candidate_url, link_text in candidate_urls[:5]:
                print(f"     시도: {link_text} → {candidate_url[:70]}")
                try:
                    test_page = await browser.new_page()
                    try:
                        await test_page.goto(candidate_url, wait_until="networkidle", timeout=30000)
                        test_content = await test_page.content()
                    finally:
                        await test_page.close()

                    test_soup = BeautifulSoup(test_content, "html.parser")
                    detail_links = _extract_detail_links(test_soup, candidate_url)

                    if len(detail_links) >= 3:
                        # 공고 목록 페이지 발견!
                        print(f"     복구 성공! {len(detail_links)}개 공고 링크 발견 → {candidate_url[:70]}")
                        cursor.execute(
                            """UPDATE admin_urls SET
                                recovered_url = %s, fail_count = 0,
                                last_fail_reason = %s
                            WHERE id = %s""",
                            (
                                candidate_url,
                                f"자동 복구 완료 ({datetime.now().strftime('%Y-%m-%d')}): {original_url[:100]} → {candidate_url[:100]}",
                                target["id"],
                            ),
                        )
                        conn.commit()
                        return True

                except Exception as e:
                    print(f"     후보 접속 실패: {e}")
                    continue

            return False

        except Exception as e:
            print(f"     루트 도메인 접속 실패: {e}")
            return False

    async def _scrape_target(self, url: str, browser) -> list[dict]:
        """목록 페이지이면 개별 링크를 수집하고, 단일 공고이면 직접 분석"""
        list_page = await browser.new_page()
        try:
            await list_page.goto(url, wait_until="networkidle", timeout=60000)
            content = await list_page.content()
        finally:
            await list_page.close()

        soup = BeautifulSoup(content, "html.parser")
        detail_links = _extract_detail_links(soup, url)

        if detail_links:
            print(f"     목록 페이지: {len(detail_links)}개 개별 공고 링크 발견")
            return await self._scrape_detail_pages(detail_links, browser, url)
        else:
            # 단일 공고 페이지로 처리
            print(f"     단일 공고 페이지로 처리")
            for tag in soup.find_all(_REMOVE_TAGS):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)[:10000]
            details = await ai_service.extract_program_details(f"제목: (페이지분석)\n\n{text}")
            if details:
                details["url"] = url
                return [details]
            return []

    async def _scrape_detail_pages(self, links: list[str], browser, list_url: str) -> list[dict]:
        """개별 공고 상세 페이지들을 순회하며 AI 분석"""
        results = []
        detail_page = await browser.new_page()
        try:
            for link in links:
                try:
                    text = await _fetch_page_text(detail_page, link)
                    if not text or len(text) < 100:
                        continue
                    details = await ai_service.extract_program_details(text)
                    if details and details.get("title"):
                        details["url"] = link
                        results.append(details)
                        print(f"      {details['title'][:45]}")
                    await asyncio.sleep(0.5)  # 요청 간격
                except Exception as e:
                    print(f"      상세 페이지 오류 ({link[:40]}): {e}")
        finally:
            await detail_page.close()
        return results

    def _save_to_db(self, item: dict, source_name: str, conn) -> bool:
        """AI가 추출한 데이터를 announcements 테이블에 저장. 신규 저장 시 True 반환."""
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT announcement_id FROM announcements WHERE origin_url = %s", (item["url"],)
            )
            exists = cursor.fetchone()

            elig = item.get("eligibility_logic", {})
            if not isinstance(elig, dict):
                elig = {}
            # business_type, target_keywords 통합
            if item.get("business_type"):
                elig["business_type"] = item["business_type"]
            if item.get("target_keywords"):
                elig["target_keywords"] = item["target_keywords"]
            eligibility_json = json.dumps(elig, ensure_ascii=False)

            ai_summary = item.get("summary_text") or item.get("description", "")

            if exists:
                cursor.execute(
                    """UPDATE announcements SET
                        title=%s, summary_text=%s, eligibility_logic=%s,
                        department=%s, category=%s, origin_source=%s, deadline_date=%s
                    WHERE origin_url=%s""",
                    (
                        item.get("title", ""), ai_summary, eligibility_json,
                        item.get("department", ""), item.get("category", ""),
                        f"admin-manual:{source_name}", item.get("deadline_date"), item["url"],
                    ),
                )
                conn.commit()
                return False  # 업데이트는 False
            else:
                cursor.execute(
                    """INSERT INTO announcements
                        (title, origin_url, summary_text, eligibility_logic,
                         department, category, origin_source, deadline_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        item.get("title", ""), item["url"], ai_summary, eligibility_json,
                        item.get("department", ""), item.get("category", ""),
                        f"admin-manual:{source_name}", item.get("deadline_date"),
                    ),
                )
                conn.commit()
                return True  # 신규 저장
        except Exception as e:
            print(f"      DB 저장 오류: {e}")
            return False

    # --- 관리자용 헬스 리포트 ---

    def get_health_report(self) -> dict:
        """전체 admin_urls 상태 요약 반환 (관리자 대시보드용)"""
        conn = psycopg2.connect(self.database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as cnt FROM admin_urls WHERE is_active = 1")
        total = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM admin_urls WHERE is_active = 1 AND fail_count >= %s", (_FAIL_THRESHOLD,))
        critical = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM admin_urls WHERE is_active = 1 AND fail_count > 0 AND fail_count < %s", (_FAIL_THRESHOLD,))
        warning = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM admin_urls WHERE is_active = 1 AND recovered_url IS NOT NULL")
        recovered = cursor.fetchone()["cnt"]

        cursor.execute(
            """SELECT id, source_name, url, recovered_url, fail_count, last_fail_reason, last_success
            FROM admin_urls WHERE is_active = 1 AND fail_count >= %s ORDER BY fail_count DESC""",
            (_FAIL_THRESHOLD,),
        )
        critical_list = cursor.fetchall()

        conn.close()
        return {
            "total_active": total,
            "healthy": total - critical - warning,
            "warning": warning,
            "critical": critical,
            "recovered": recovered,
            "critical_urls": [dict(row) for row in critical_list],
        }


admin_scraper = AdminScraper()
