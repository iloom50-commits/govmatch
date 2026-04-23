"""Tier 1 기관별 전용 스크래퍼 패키지.

각 스크래퍼는 `BaseScraper`를 상속하고 `name`, `fetch_items()`를 구현.
daily_pipeline이 `run_tier1_scrapers()`를 호출.
"""
from .base import BaseScraper, run_tier1_scrapers, SCRAPER_REGISTRY

__all__ = ["BaseScraper", "run_tier1_scrapers", "SCRAPER_REGISTRY"]
