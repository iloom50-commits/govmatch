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
from app.services.rule_engine import (
    normalize_region_for_save,
    normalize_category,
    infer_category_from_title,
    extract_region_from_text,
)

logger = logging.getLogger(__name__)

SCRAPER_REGISTRY: List["BaseScraper"] = []

# 저장 차단 도메인 — AI 생성 페이지, 비정부 양식 플랫폼 등
BLOCKED_ORIGIN_DOMAINS = {
    "gensparkspace.com",  # Genspark AI 생성 페이지
}

# 지원사업이 아닌 행정·공지·명단·결과 공고 — 저장 차단 (보도현황·위원회명단·이용중지 등)
_NON_SUPPORT_TITLE_KW = (
    "보도 현황", "보도자료", "해명자료",
    "위원회 명단", "위원 명단", "심의위원 명단", "도시계획위원회", "건축위원회",
    "이용 중지", "이용중지", "휴관", "휴무", "운영 중지", "운영중지",
    "공청회", "간담회 개최", "회의 개최",
    "낙찰", "입찰 결과", "계약 체결",
    "인사발령", "위촉식", "당첨자", "합격자 발표",
    "의견 수렴", "현황 알림",
)


# 정부 표창/포상 후보 모집 — '모집'이 붙어도 지원금(자금·바우처)이 아니므로 hard-제외
_AWARD_TITLE_KW = ("유공 포상", "유공자 포상", "포상 후보자", "포상 후보", "포상계획", "표창 후보", "표창계획")


def _is_non_support_title(title: str) -> bool:
    """지원사업이 아닌 행정/공지/명단 공고 판별. 단, 지원사업 신호가 있으면 차단 안 함(오탐 방지)."""
    t = title or ""
    # 표창/포상 후보 모집은 '모집' 신호보다 우선해 제외(지원사업 아님)
    if any(kw in t for kw in _AWARD_TITLE_KW):
        return True
    if any(s in t for s in ("모집", "지원사업", "지원금", "바우처", "공모", "지원 사업")):
        return False
    return any(kw in t for kw in _NON_SUPPORT_TITLE_KW)


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
    skip_consecutive_break: bool = False  # True: 비최신순 API — 연속 기존건 조기 종료 비활성화

    def fetch_items(self) -> List[Dict[str, Any]]:
        """공고 리스트 추출. 각 item dict는 다음 키를 포함:
          - title (str, 필수)
          - origin_url (str, 필수 — 상세 페이지)
          - deadline_date (str 'YYYY-MM-DD' or None)
          - deadline_raw (str or None: 마감 원문 — 있으면 저장 관문이 우선 파싱)
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
        items_expired = 0
        items_existing = 0
        items_rescued = 0  # 배치 안전망으로 마감미상 저장된 건수(관측성)
        status = "ok"
        error_message = None

        try:
            items = self.fetch_items() or []
            items_found = len(items)
            today = datetime.date.today()
            consecutive_existing = 0
            expired_items = []  # 즉시 드롭하지 않고 보류 — 배치 안전망 판정용

            for it in items:
                # 마감일 지난 것 — 즉시 드롭하지 않고 보류 (등록일→마감일 오인 방지)
                dl = it.get("deadline_date")
                if dl:
                    try:
                        if datetime.date.fromisoformat(str(dl)) < today:
                            expired_items.append(it)
                            continue
                    except Exception:
                        pass

                try:
                    saved = self._save_item(it, db_conn)
                    if saved:
                        items_saved += 1
                        consecutive_existing = 0
                    else:
                        items_existing += 1
                        consecutive_existing += 1
                        # 연속 5건 이미 DB에 있으면 나머지 스킵 (최신순 정렬 API 전용)
                        # skip_consecutive_break=True인 스크래퍼는 비활성화 (비최신순 API)
                        if not self.skip_consecutive_break and consecutive_existing >= 5:
                            break
                except Exception as e:
                    logger.warning(f"[{self.name}] save error on {it.get('title','')[:30]}: {e}")
                    try: db_conn.rollback()
                    except: pass

            # ── 배치 안전망 (근본개선) ──────────────────────────────
            # "found>0인데 저장 0 + 거의 전량 만료"는 등록일을 마감일로 오인한 신호다.
            # 스크래퍼가 추측한 마감일로 진행중 공고를 영구 드롭하는 것을 구조적으로 막는다.
            # 드롭 대신 마감미상(None)으로 저장 → deadline_enricher가 상세에서 실제 마감 보강.
            # 정상 소스(신선건 사이 만료 몇 건 드롭)는 saved>0이라 발동하지 않는다.
            if (items_found > 0 and items_saved == 0
                    and len(expired_items) >= max(3, items_found * 0.8)):
                for it in expired_items:
                    it2 = dict(it); it2["deadline_date"] = None
                    try:
                        if self._save_item(it2, db_conn):
                            items_saved += 1
                            items_rescued += 1
                    except Exception as e:
                        logger.warning(f"[{self.name}] rescue save error: {e}")
                        try: db_conn.rollback()
                        except: pass
                logger.warning(
                    f"[{self.name}] 전량 만료({len(expired_items)}) 오인 의심 → "
                    f"마감미상 저장 {items_saved}건 (등록일→마감일 오인 방지)")
            else:
                items_expired = len(expired_items)

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
                       items_saved = %s, items_expired = %s, items_rescued = %s,
                       error_message = %s, elapsed_sec = %s
                   WHERE id = %s""",
                (datetime.datetime.now(), status, items_found, items_saved,
                 items_expired, items_rescued, error_message, elapsed, run_id),
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
            "items_expired": items_expired,
            "items_existing": items_existing,
            "items_rescued": items_rescued,
            "elapsed_sec": elapsed,
            "error": error_message,
        }

    def _save_item(self, item: Dict[str, Any], db_conn) -> bool:
        """announcements 테이블에 저장 (origin_url 중복 시 UPDATE)."""
        title = (item.get("title") or "").strip()
        origin_url = (item.get("origin_url") or "").strip()
        if not title or not origin_url:
            return False
        if any(d in origin_url for d in BLOCKED_ORIGIN_DOMAINS):
            logger.info(f"[{self.name}] 블랙리스트 도메인 스킵: {origin_url[:60]}")
            return False
        if _is_non_support_title(title):
            logger.info(f"[{self.name}] 비-지원사업(행정/명단/공지) 스킵: {title[:40]}")
            return False

        # 정규화
        raw_region = item.get("region") or None
        raw_category = item.get("category") or None
        region = normalize_region_for_save(raw_region)
        # region이 전국/None이면 department→title 순으로 지역 추출 시도
        if not region or region == "전국":
            dept_text = item.get("department") or self.display_name or ""
            region = extract_region_from_text(dept_text) or extract_region_from_text(title) or region
        category = normalize_category(raw_category)
        # category가 NULL이면 제목 기반으로 추론 (스크래퍼가 분류 못한 경우)
        if not category:
            category = infer_category_from_title(title)
        target_type = item.get("target_type") or None

        # [P2-2] 마감 원문 → 중앙 파서(tier1도 저장 관문 일원화). deadline_raw 우선, 없으면 deadline_date.
        from app.services.deadline_enricher import parse_deadline
        _dl_date, _dl_type, _dl_raw = parse_deadline(item.get("deadline_raw") or item.get("deadline_date"))

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
                is_archived, analysis_status, deadline_type, deadline_raw_text,
                deadline_source, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       FALSE, 'pending', %s, %s, 'collect', CURRENT_TIMESTAMP)
               RETURNING announcement_id""",
            (
                title[:500],
                origin_url,
                (item.get("department") or self.display_name),
                region,
                category,
                target_type,  # NULL이면 AI 분류(ai_classify_pending)가 처리
                (item.get("support_amount") or None),
                _dl_date,
                (item.get("summary_text") or "")[:4000] or None,
                f"scraper:{self.name}",
                _dl_type,
                _dl_raw,
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
