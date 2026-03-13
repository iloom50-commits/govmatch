try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import asyncio
import logging

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    def __init__(self, max_retries: int = 3, retry_delay: float = 2.0):
        self.browser = None
        self.playwright = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def start_browser(self):
        """브라우저 시작 (재시도 로직 포함)"""
        import sys
        if sys.platform == 'win32':
            import asyncio
            try:
                if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except Exception as e:
                logger.debug(f"Event loop policy set failed: {e}")

        for attempt in range(self.max_retries):
            try:
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                return
            except Exception as e:
                logger.warning(f"브라우저 시작 실패 (시도 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise

    async def close_browser(self):
        """브라우저 종료"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"브라우저 종료 중 오류: {e}")
        finally:
            self.browser = None
            self.playwright = None

    async def fetch_with_retry(self, page, url: str, max_retries: int = None, timeout: int = 60000) -> str:
        """페이지 가져오기 (재시도 로직 포함)"""
        max_retries = max_retries or self.max_retries
        
        for attempt in range(max_retries):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                await page.wait_for_timeout(1000)  # 추가 대기
                return await page.content()
            except Exception as e:
                logger.warning(f"페이지 로드 실패 (시도 {attempt + 1}/{max_retries}): {url[:80]} - {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))  # 지수 백오프
                else:
                    raise

    @abstractmethod
    async def scrape(self) -> List[Dict]:
        """스크래핑 메인 메서드"""
        pass
