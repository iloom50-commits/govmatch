"""Tier 1 스크래퍼 공통 베이스.

각 개별 스크래퍼는 BaseScraper 상속 후:
  - name: 로그·모니터링 식별자 (예: "seoul_tp")
  - display_name: 사용자 노출용 한글명 (예: "서울테크노파크")
  - origin_url_prefix: 공고 상세 URL prefix (중복 판정용)
  - fetch_items() -> List[dict]: 공고 리스트 추출

BaseScraper.run()이 scraper_runs 로그 자동 기록 + DB 저장 + 중복 처리.
"""
from __future__ import annotations
import time
import datetime
import hashlib
import logging
import json
from typing import List, Dict, Any, Optional
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

SCRAPER_REGISTRY: List["BaseScraper"] = []


def register(cls):
    """데코레이터: 서브클래스를 전역 레지스트리에 등록."""
    instance = cls()
    SCRAPER_REGISTRY.append(instance)
    return cls


class BaseScraper:
    """개별 기관 스크래퍼의 추상 베이스."""

    name: str = "unknown"                 # 식별자 (소문자, 언더스코어)
    display_name: str = "Unknown"         # 한글 표시명 (department로 저장)
    origin_url_prefix: str = ""           # 사이트 도메인

    def fetch_items(self) -> List[Dict[str, Any]]:
        """공고 리스트 추출. 각 item dict는 다음 키를 포함:
          - title (str, 필수)
          - origin_url (str, 필수 — 상세 페이지)
          - deadline_date (str 'YYYY-MM-DD' or None)
          - support_amount (str or None)
          - summary_text (str or None)
          - region (str or None)
          - category (str or None)
          - target_type (str or None: "business"/"individual"/"both")
        """
        raise NotImplementedError

    # ───────────────────────────────────────────────────────────
    # 공통 실행 엔진
    # ───────────────────────────────────────────────────────────
    def run(self, db_conn) -> Dict[str, Any]:
        """스크래퍼 실행 → scraper_runs 기록 + announcements 저장."""
        started = datetime.datetime.now()
        start_ts = time.time()
        cur = db_conn.cursor()
        cur.execute(
            """INSERT INTO scraper_runs (source, started_at, status)
               VALUES (%s, %s, 'running') RETURNING id""",
            (self.name, started),
        )
        run_id = cur.fetchone()["id"]
        db_conn.commit()

        items_found = 0
        items_saved = 0
        status = "ok"
        error_message = None

        try:
            items = self.fetch_items() or []
            items_found = len(items)
            for it in items:
                try:
                    if self._save_item(it, db_conn):
                        items_saved += 1
                except Exception as e:
                    logger.warning(f"[{self.name}] save error on {it.get('title','')[:30]}: {e}")
                    try: db_conn.rollback()
                    except: pass
            if items_found == 0:
                status = "empty"
        except Exception as e:
            status = "error"
            error_message = f"{type(e).__name__}: {str(e)[:500]}"
            logger.error(f"[{self.name}] fetch error: {error_message}")

        elapsed = round(time.time() - start_ts, 2)
        try:
            cur.execute(
                """UPDATE scraper_runs
                   SET ended_at = %s, status = %s, items_found = %s,
                       items_saved = %s, error_message = %s, elapsed_sec = %s
                   WHERE id = %s""",
                (datetime.datetime.now(), status, items_found, items_saved,
                 error_message, elapsed, run_id),
            )
            db_conn.commit()
        except Exception as e:
            logger.error(f"[{self.name}] run log update failed: {e}")
            try: db_conn.rollback()
            except: pass

        return {
            "name": self.name,
            "status": status,
            "items_found": items_found,
            "items_saved": items_saved,
            "elapsed_sec": elapsed,
            "error": error_message,
        }

    def _save_item(self, item: Dict[str, Any], db_conn) -> bool:
        """announcements 테이블에 저장 (origin_url 중복 시 UPDATE)."""
        title = (item.get("title") or "").strip()
        origin_url = (item.get("origin_url") or "").strip()
        if not title or not origin_url:
            return False

        cur = db_conn.cursor()
        # 중복 체크
        cur.execute(
            "SELECT announcement_id FROM announcements WHERE origin_url = %s LIMIT 1",
            (origin_url,),
        )
        existing = cur.fetchone()
        if existing:
            # 기존 공고는 갱신 안 함 (종합 API가 우선 — 여기선 소스 표시만)
            return False

        # 신규 삽입
        cur.execute(
            """INSERT INTO announcements
               (title, origin_url, department, region, category, target_type,
                support_amount, deadline_date, summary_text, origin_source,
                is_archived, analysis_status, deadline_type, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       FALSE, 'pending', %s, CURRENT_TIMESTAMP)
               RETURNING announcement_id""",
            (
                title[:500],
                origin_url,
                self.display_name,
                item.get("region") or None,
                item.get("category") or None,
                item.get("target_type") or "business",
                (item.get("support_amount") or None),
                item.get("deadline_date") or None,
                (item.get("summary_text") or "")[:4000] or None,
                f"scraper:{self.name}",
                "fixed" if item.get("deadline_date") else "unknown",
            ),
        )
        db_conn.commit()
        return True


# ─── 레지스트리 실행 진입점 ──────────────────────────────────
def run_tier1_scrapers(db_conn) -> Dict[str, Any]:
    """daily_pipeline에서 호출. 등록된 모든 Tier 1 스크래퍼 순차 실행."""
    # 서브 모듈 import 시점에 @register가 레지스트리를 채움
    from . import _load_all  # noqa: F401 (사이드이펙트로 모든 scraper 로드)

    results = []
    for scraper in SCRAPER_REGISTRY:
        try:
            r = scraper.run(db_conn)
            results.append(r)
        except Exception as e:
            logger.error(f"[tier1] {scraper.name} crashed: {e}")
            results.append({"name": scraper.name, "status": "crash", "error": str(e)[:200]})

    total_saved = sum(r.get("items_saved", 0) for r in results)
    ok = sum(1 for r in results if r.get("status") == "ok")
    errors = sum(1 for r in results if r.get("status") in ("error", "crash"))

    return {
        "total_scrapers": len(results),
        "ok": ok,
        "errors": errors,
        "total_items_saved": total_saved,
        "details": results,
    }
