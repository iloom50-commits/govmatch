"""일일 자동 파이프라인 — 매일 03:00 KST 순차 실행.

docs/daily-pipeline.md 참조.
9단계를 순서대로 실행하며, 각 단계는 독립적으로 에러 처리.
"""

import time
import json
import logging
import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


def run_daily_pipeline(db_conn) -> Dict[str, Any]:
    """전체 일일 파이프라인 순차 실행.

    Returns: 각 단계별 결과 + 전체 소요 시간
    """
    start = time.time()
    results: Dict[str, Any] = {
        "started_at": datetime.datetime.now().isoformat(),
        "steps": {},
        "errors": [],
    }

    # 시작 기록 — 트리거(cron/스케줄러) 무관하게 "파이프라인이 돌았다"는 유일한 증거.
    # (과거엔 완료 로그가 varchar 버그로 유실돼, 실행 여부조차 알 수 없었음 — A-1/A-3)
    try:
        _sc = db_conn.cursor()
        _sc.execute(
            "INSERT INTO system_logs (action, category, detail, result) "
            "VALUES ('pipeline_start', 'system', %s, 'started')",
            (results["started_at"],),
        )
        db_conn.commit()
    except Exception:
        try:
            db_conn.rollback()
        except Exception:
            pass

    # ── 스텝별 영구 로그 헬퍼 (C-2) — 성공/0건/실패 무조건 system_logs 1행 ──
    #   과거엔 실행 주체만 로그를 남겨, 스텝이 안 돌거나 0건·에러여도 흔적이 없었다.
    def _extract_count(result):
        if isinstance(result, dict):
            for k in ("saved", "count", "updated", "ok", "processed", "recovered",
                      "discovered", "queued_for_analysis", "sent", "attempted"):
                v = result.get(k)
                if isinstance(v, int):
                    return v
        return 0

    def _log_step(name, result_status, detail_obj, count=0):
        try:
            _lc = db_conn.cursor()
            _d = detail_obj if isinstance(detail_obj, str) else json.dumps(detail_obj, ensure_ascii=False, default=str)
            _lc.execute(
                "INSERT INTO system_logs (action, category, detail, result, count_affected) "
                "VALUES (%s, 'pipeline_step', %s, %s, %s)",
                (f"step:{name}"[:50], _d[:2000], str(result_status)[:20], int(count or 0)),
            )
            db_conn.commit()
        except Exception:
            try:
                db_conn.rollback()
            except Exception:
                pass

    def _run_step(name: str, func, **kwargs):
        """단계 실행 래퍼 — 에러 격리 + 시간 측정 + 스텝별 영구 로그(C-2)."""
        step_start = time.time()
        try:
            logger.info(f"[Pipeline] ▶ {name} 시작...")
            result = func(**kwargs)
            elapsed = round(time.time() - step_start, 1)
            results["steps"][name] = {"status": "ok", "elapsed": elapsed, "result": result}
            logger.info(f"[Pipeline] ✓ {name} 완료 ({elapsed}s)")
            _log_step(name, "ok", {"elapsed": elapsed, "result": result}, _extract_count(result))
        except Exception as e:
            elapsed = round(time.time() - step_start, 1)
            error_msg = f"{name} 실패: {type(e).__name__}: {str(e)[:200]}"
            results["steps"][name] = {"status": "error", "elapsed": elapsed, "error": error_msg}
            results["errors"].append(error_msg)
            logger.error(f"[Pipeline] ✗ {error_msg}")
            try:
                db_conn.rollback()
            except Exception:
                pass
            _log_step(name, "error", error_msg)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ① 공고 수집 (외부 API)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_1_collect():
        from app.services.sync_service import SyncService
        import asyncio
        sync = SyncService()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(sync.sync_all())
        finally:
            loop.close()

        # 상세 보강
        try:
            from app.services.public_api_service import gov_api_service
            loop2 = asyncio.new_event_loop()
            try:
                loop2.run_until_complete(gov_api_service.enrich_local_welfare_details(batch_size=100))
                loop2.run_until_complete(gov_api_service.enrich_gov24_individual_details(batch_size=100))
            finally:
                loop2.close()
        except Exception as e:
            logger.warning(f"[Pipeline] 상세 보강 부분 실패: {e}")

        return {"collected": True}

    _run_step("① 공고 수집", step_1_collect)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ② 원본 기관 직접 크롤링
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_2_crawl():
        result = {}
        try:
            from app.services.scrapers.mss_scraper import crawl_and_store as mss_crawl
            result["mss"] = mss_crawl(db_conn, max_pages=3, max_items=20)
        except Exception as e:
            result["mss_error"] = str(e)[:100]

        try:
            from app.services.scrapers.semas_scraper import sync_semas_knowledge
            result["semas"] = sync_semas_knowledge(db_conn, max_pages=2)
        except Exception as e:
            result["semas_error"] = str(e)[:100]

        # [Tier 1] TP·공공기관 개별 스크래퍼 실행 (scraper_runs 로그 자동 기록)
        try:
            from app.services.scrapers.tier1 import run_tier1_scrapers
            result["tier1"] = run_tier1_scrapers(db_conn)
        except Exception as e:
            result["tier1_error"] = str(e)[:200]

        return result

    _run_step("② 직접 크롤링", step_2_crawl)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ②-1 기관 수집 (admin_urls) — 지자체·TP·진흥원 (A-4 부활)
    #   별도 Railway cron 없이 파이프라인에 통합. Playwright로 last_scraped 오래된
    #   순 batch_size개씩만 순환 수집(≈167/40 ≈ 4~5일 전체 주기) → 파이프라인 시간 완화.
    #   MAX_ADMIN_BATCH 환경변수로 조정(기본 40). 크롬 미설치면 run_batch가 skip 반환.
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_2b_admin_scrape():
        import os
        import asyncio
        from app.services.admin_scraper import admin_scraper
        n = int(os.getenv("MAX_ADMIN_BATCH", "40"))
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(admin_scraper.run_batch(batch_size=n))
        finally:
            loop.close()

    _run_step("②-1 기관 수집(admin)", step_2b_admin_scrape)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ③ DB 정리
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_3_cleanup():
        from app.main import (
            _cleanup_non_support_announcements,
            _deduplicate_announcements,
        )
        from app.services.patrol.target_type_classifier import ai_classify_pending

        _cleanup_non_support_announcements()
        _deduplicate_announcements()

        # AI 기반 target_type 분류 (NULL 공고만 대상, 배치 100건)
        try:
            classify_result = ai_classify_pending(db_conn, batch_size=100)
        except Exception as e:
            classify_result = {"error": str(e)[:200]}

        return {"cleaned": True, "classify": classify_result}

    _run_step("③ DB 정리", step_3_cleanup)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ④ 공고 분석
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_4_analyze():
        from .analysis_recovery import discover_unanalyzed, recover_failed_analyses
        from .url_health import scan_and_fix_urls

        url_result = scan_and_fix_urls(db_conn)
        discover_result = discover_unanalyzed(db_conn, limit=300)
        recovery_result = recover_failed_analyses(db_conn, max_retries=500)

        return {
            "url_health": url_result,
            "discovered": discover_result.get("queued_for_analysis", 0),
            "recovered": recovery_result.get("recovered", 0),
            "attempted": recovery_result.get("attempted", 0),
        }

    _run_step("④ 공고 분석", step_4_analyze)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ④-0. matcher용 재분석 (eligibility_logic 백필)
    #   matcher.py가 제외 판정에 쓰는 eligibility_logic이 비어있는 미분석 공고를
    #   Gemini로 채우고 ai_analyzed_at 마킹. 기업·오래된 것 우선(starvation 방지).
    #   한도는 MATCHER_REANALYZE_LIMIT 환경변수로 조정(기본 400).
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_4a_matcher_reanalyze():
        import os
        from .matcher_reanalyze import reanalyze_empty_eligibility
        limit = int(os.getenv("MATCHER_REANALYZE_LIMIT", "400"))
        return reanalyze_empty_eligibility(db_conn, limit=limit)

    _run_step("④-0 매칭 재분석", step_4a_matcher_reanalyze)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ④-1. 원문 URL 추적 (경유지 → 원본)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_4b_resolve_urls():
        from app.services.scrapers.url_resolver import batch_resolve_final_urls
        return batch_resolve_final_urls(db_conn, limit=500)

    _run_step("④-1 원문 URL 추적", step_4b_resolve_urls)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ④-2. 마감일 보강 (full_text → 마감일/상시 분류)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_4c_deadlines():
        from app.services.deadline_enricher import enrich_pending_deadlines
        return enrich_pending_deadlines(db_conn, limit=1000)

    _run_step("④-2 마감일 보강", step_4c_deadlines)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ④-2. 외부 검색 학습 (Google Search → knowledge_base)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_4c_search_learn():
        from app.services.scrapers.url_resolver import search_and_learn
        return search_and_learn(db_conn, limit=100)

    _run_step("④-2 외부 검색 학습", step_4c_search_learn)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ④-3. 블로그용 AI 분석 (full_text → blog_analysis)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_4d_blog_analysis():
        from app.services.patrol.blog_analyzer import run_blog_analysis_batch
        return run_blog_analysis_batch(db_conn, batch_size=20)

    _run_step("④-3 블로그 AI 분석", step_4d_blog_analysis)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⑤ 학습 전파 정리
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_5_learning():
        return propagate_learning(db_conn)

    _run_step("⑤ 학습 전파", step_5_learning)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⑤-B. [Phase 4] 공고 데이터 품질 자동 정리
    #      - 마감 + 30일 경과 → is_archived=TRUE
    #      - deadline_type='expired' → is_archived=TRUE
    #      - analysis_status='failed' + 3개월 경과 → 아카이브
    #      - deadline NULL + 수집 후 6개월 경과 → expired 처리 + 아카이브
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_5b_data_cleanup():
        return archive_stale_announcements(db_conn)

    _run_step("⑤-B 공고 품질 정리", step_5b_data_cleanup)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⑥ 사전매칭 캐시 갱신
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_6_prematch():
        from app.main import _run_prematch_cache
        count = _run_prematch_cache()
        return {"cached_users": count}

    _run_step("⑥ 사전매칭 캐시", step_6_prematch)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⑥-1. AI 맞춤 매칭 (2단계 정밀 매칭)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_6b_smart_match():
        from app.services.smart_match import batch_smart_match_for_users
        return batch_smart_match_for_users(db_conn, limit=50)

    _run_step("⑥-1 AI 맞춤 매칭", step_6b_smart_match)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⑦ 오케스트레이터 (품질 체크 + 보고서)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_7_orchestrator():
        from app.services.orchestrator.supervisor import run_daily_supervision
        return run_daily_supervision(db_conn)

    _run_step("⑦ 오케스트레이터", step_7_orchestrator)

    # ⑧ 다이제스트 발송은 run_digest_cron.py (UTC 00:00 평일)가 단독 담당
    # — 이 파이프라인에서 호출하면 KST 03:00 + 09:00 이중 발송 발생하므로 제거

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⑨ 구독/결제 관리
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_9_billing():
        from app.main import _auto_renew_subscriptions
        _auto_renew_subscriptions()
        return {"renewed": True}

    _run_step("⑨ 구독 관리", step_9_billing)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 완료 — 결과 로그 저장
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    total_elapsed = round(time.time() - start, 1)
    results["total_elapsed"] = total_elapsed
    results["completed_at"] = datetime.datetime.now().isoformat()
    results["error_count"] = len(results["errors"])

    # system_logs에 결과 저장
    #   ⚠️ result 컬럼은 varchar(20) — 짧은 상태만. 상세 JSON은 text인 detail에 넣는다.
    #   (과거: 2000자 JSON을 result에 넣어 매번 길이초과 INSERT 실패 → 상세로그 전면 유실)
    try:
        cur = db_conn.cursor()
        err_n = len(results["errors"])
        step_status = {name: (s or {}).get("status") for name, s in results.get("steps", {}).items()}
        detail = json.dumps({
            "elapsed": total_elapsed,
            "error_count": err_n,
            "steps": step_status,        # 스텝별 ok/error 한눈에
            "errors": results["errors"],  # 실패 사유 전문
        }, ensure_ascii=False, default=str)
        result_status = "success" if err_n == 0 else "partial"
        cur.execute("""
            INSERT INTO system_logs (action, category, detail, result, count_affected)
            VALUES ('daily_pipeline', 'system', %s, %s, %s)
        """, (detail, result_status, err_n))
        db_conn.commit()
    except Exception as e:
        logger.warning(f"[Pipeline] 결과 로그 저장 실패: {e}")
        try:
            db_conn.rollback()
        except Exception:
            pass

    logger.info(f"[Pipeline] 전체 완료: {total_elapsed}s, 에러 {len(results['errors'])}건")
    return results


def propagate_learning(db_conn) -> Dict[str, Any]:
    """학습 전파 정리 — 새벽 배치 작업.

    1. source_agent 미태깅 지식 보정
    2. 임베딩 누락 보강
    3. 저품질 지식 정리
    4. 기업/개인 카테고리 정리
    """
    cur = db_conn.cursor()
    stats = {"tagged": 0, "embedded": 0, "cleaned": 0}

    # 1. source_agent 미태깅 보정
    try:
        cur.execute("""
            UPDATE knowledge_base SET source_agent = 'pro'
            WHERE source = 'pro_consult' AND source_agent IS NULL
        """)
        cur.execute("""
            UPDATE knowledge_base SET source_agent = 'lite'
            WHERE source LIKE 'lite_%%' AND source_agent IS NULL
        """)
        cur.execute("""
            UPDATE knowledge_base SET source_agent = 'crawler'
            WHERE source = 'crawler' AND source_agent IS NULL
        """)
        cur.execute("""
            UPDATE knowledge_base SET source_agent = 'consult'
            WHERE source LIKE 'consult_%%' AND source_agent IS NULL
        """)
        cur.execute("""
            UPDATE knowledge_base SET source_agent = 'seed'
            WHERE source IN ('seed', 'fund_seed') AND source_agent IS NULL
        """)
        db_conn.commit()
        # 태깅된 건수 확인
        cur.execute("SELECT COUNT(*) as cnt FROM knowledge_base WHERE source_agent IS NOT NULL")
        stats["tagged"] = cur.fetchone()["cnt"]
    except Exception as e:
        logger.warning(f"[Learning] Tagging error: {e}")
        try:
            db_conn.rollback()
        except Exception:
            pass

    # 2. 임베딩 누락 보강
    try:
        cur.execute("SELECT id, category, content FROM knowledge_base WHERE embedding IS NULL LIMIT 30")
        rows = cur.fetchall()
        if rows:
            from app.services.ai_consultant import _generate_knowledge_embedding
            import json as _json

            fixed = 0
            for r in rows:
                content = r["content"]
                if isinstance(content, str):
                    try:
                        content = _json.loads(content)
                    except Exception:
                        content = {"raw": content}
                vec = _generate_knowledge_embedding(content, r.get("category"))
                if vec:
                    vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
                    cur.execute("UPDATE knowledge_base SET embedding = %s::vector WHERE id = %s", (vec_str, r["id"]))
                    fixed += 1
            if fixed > 0:
                db_conn.commit()
            stats["embedded"] = fixed
    except Exception as e:
        logger.warning(f"[Learning] Embedding error: {e}")
        try:
            db_conn.rollback()
        except Exception:
            pass

    # 3. 저품질 지식 정리 (confidence < 0.3 AND 30일 경과)
    try:
        cur.execute("""
            DELETE FROM knowledge_base
            WHERE confidence < 0.3
              AND use_count = 0
              AND created_at < CURRENT_DATE - INTERVAL '30 days'
        """)
        stats["cleaned"] = cur.rowcount
        db_conn.commit()
    except Exception as e:
        logger.warning(f"[Learning] Cleanup error: {e}")
        try:
            db_conn.rollback()
        except Exception:
            pass

    logger.info(f"[Learning] Propagation: tagged={stats['tagged']}, embedded={stats['embedded']}, cleaned={stats['cleaned']}")
    return stats


def archive_stale_announcements(db_conn) -> Dict[str, Any]:
    """[Phase 4] 공고 데이터 품질 자동 정리 — 마감·기한초과·분석실패 공고 아카이브.

    규칙:
    1) deadline_type='fixed' + deadline_date < KST 오늘 → is_archived=TRUE + deadline_type='expired'
    2) deadline_type='expired' AND NOT is_archived → is_archived=TRUE
    3) analysis_status='failed' + created_at < (오늘 - 3개월) → is_archived=TRUE
    4) deadline_type='unknown' AND created_at < (오늘 - 6개월) AND analysis_status != 'ongoing'
       → deadline_type='expired' + is_archived=TRUE (보수적 정리)
    5) 제목에 과거 연도 명시 + deadline_type='unknown' → is_archived=TRUE

    Returns: 각 규칙별 처리 건수
    """
    cur = db_conn.cursor()
    stats = {"past_deadline": 0, "expired_type": 0, "failed_old": 0, "unknown_old": 0, "past_year_title": 0}

    # 1) 마감일 경과 (KST 자정 기준 — 당일 마감 공고는 당일까지 노출)
    try:
        cur.execute("""
            UPDATE announcements
            SET is_archived = TRUE,
                deadline_type = 'expired'
            WHERE is_archived = FALSE
              AND deadline_type = 'fixed'
              AND deadline_date IS NOT NULL
              AND deadline_date < (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')::DATE
        """)
        stats["past_deadline"] = cur.rowcount or 0
        db_conn.commit()
    except Exception as e:
        logger.warning(f"[Archive] past_deadline error: {e}")
        try: db_conn.rollback()
        except Exception: pass

    # 2) deadline_type='expired' 인데 아직 아카이브 안 된 것
    try:
        cur.execute("""
            UPDATE announcements
            SET is_archived = TRUE
            WHERE is_archived = FALSE
              AND deadline_type = 'expired'
        """)
        stats["expired_type"] = cur.rowcount or 0
        db_conn.commit()
    except Exception as e:
        logger.warning(f"[Archive] expired_type error: {e}")
        try: db_conn.rollback()
        except Exception: pass

    # 3) 분석 3회 이상 실패 + 3개월 경과
    try:
        cur.execute("""
            UPDATE announcements
            SET is_archived = TRUE
            WHERE is_archived = FALSE
              AND analysis_status = 'failed'
              AND created_at < CURRENT_DATE - INTERVAL '3 months'
        """)
        stats["failed_old"] = cur.rowcount or 0
        db_conn.commit()
    except Exception as e:
        logger.warning(f"[Archive] failed_old error: {e}")
        try: db_conn.rollback()
        except Exception: pass

    # 4) deadline 미확인 + 6개월 경과 (상시 제외)
    try:
        cur.execute("""
            UPDATE announcements
            SET is_archived = TRUE,
                deadline_type = 'expired'
            WHERE is_archived = FALSE
              AND deadline_type = 'unknown'
              AND created_at < CURRENT_DATE - INTERVAL '6 months'
        """)
        stats["unknown_old"] = cur.rowcount or 0
        db_conn.commit()
    except Exception as e:
        logger.warning(f"[Archive] unknown_old error: {e}")
        try: db_conn.rollback()
        except Exception: pass

    # 5) 제목에 과거 연도 명시 (예: "2024년 XXX 지원") + deadline 불명
    try:
        cur.execute(r"""
            UPDATE announcements
            SET is_archived = TRUE,
                deadline_type = 'expired'
            WHERE is_archived = FALSE
              AND deadline_type = 'unknown'
              AND title ~ '^\d{4}년'
              AND SUBSTRING(title FROM '^(\d{4})년')::int < EXTRACT(YEAR FROM CURRENT_DATE)::int
        """)
        stats["past_year_title"] = cur.rowcount or 0
        db_conn.commit()
    except Exception as e:
        logger.warning(f"[Archive] past_year_title error: {e}")
        try: db_conn.rollback()
        except Exception: pass

    total = sum(stats.values())
    logger.info(f"[Archive] Stale announcements cleaned: {total} total — {stats}")
    return {"total_archived": total, **stats}
