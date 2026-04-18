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

    def _run_step(name: str, func, **kwargs):
        """단계 실행 래퍼 — 에러 격리 + 시간 측정"""
        step_start = time.time()
        try:
            logger.info(f"[Pipeline] ▶ {name} 시작...")
            result = func(**kwargs)
            elapsed = round(time.time() - step_start, 1)
            results["steps"][name] = {"status": "ok", "elapsed": elapsed, "result": result}
            logger.info(f"[Pipeline] ✓ {name} 완료 ({elapsed}s)")
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

        return result

    _run_step("② 직접 크롤링", step_2_crawl)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ③ DB 정리
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_3_cleanup():
        from app.main import (
            _cleanup_non_support_announcements,
            _deduplicate_announcements,
            _auto_classify_target_type,
        )
        _cleanup_non_support_announcements()
        _deduplicate_announcements()
        _auto_classify_target_type()
        return {"cleaned": True}

    _run_step("③ DB 정리", step_3_cleanup)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ④ 공고 분석
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_4_analyze():
        from .analysis_recovery import discover_unanalyzed, recover_failed_analyses
        from .url_health import scan_and_fix_urls

        url_result = scan_and_fix_urls(db_conn)
        discover_result = discover_unanalyzed(db_conn, limit=100)
        recovery_result = recover_failed_analyses(db_conn, max_retries=100)

        return {
            "url_health": url_result,
            "discovered": discover_result.get("queued_for_analysis", 0),
            "recovered": recovery_result.get("recovered", 0),
            "attempted": recovery_result.get("attempted", 0),
        }

    _run_step("④ 공고 분석", step_4_analyze)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ④-1. 원문 URL 추적 (경유지 → 원본)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_4b_resolve_urls():
        from app.services.scrapers.url_resolver import batch_resolve_final_urls
        return batch_resolve_final_urls(db_conn, limit=50)

    _run_step("④-1 원문 URL 추적", step_4b_resolve_urls)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ④-2. 외부 검색 학습 (Google Search → knowledge_base)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_4c_search_learn():
        from app.services.scrapers.url_resolver import search_and_learn
        return search_and_learn(db_conn, limit=10)

    _run_step("④-2 외부 검색 학습", step_4c_search_learn)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⑤ 학습 전파 정리
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_5_learning():
        return propagate_learning(db_conn)

    _run_step("⑤ 학습 전파", step_5_learning)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⑥ 사전매칭 캐시 갱신
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_6_prematch():
        from app.main import _run_prematch_cache
        count = _run_prematch_cache()
        return {"cached_users": count}

    _run_step("⑥ 사전매칭 캐시", step_6_prematch)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⑦ 오케스트레이터 (품질 체크 + 보고서)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_7_orchestrator():
        from app.services.orchestrator.supervisor import run_daily_supervision
        return run_daily_supervision(db_conn)

    _run_step("⑦ 오케스트레이터", step_7_orchestrator)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⑧ 일일 다이제스트 발송
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def step_8_digest():
        # 평일만 발송
        now = datetime.datetime.now()
        if now.weekday() >= 5:  # 토,일
            return {"skipped": "weekend"}
        from app.services.notification_service import notification_service
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            digest_results = loop.run_until_complete(notification_service.generate_daily_digest())
        finally:
            loop.close()
        sent = sum(1 for r in digest_results if r.get("email_sent"))
        return {"users": len(digest_results), "emails_sent": sent}

    _run_step("⑧ 다이제스트 발송", step_8_digest)

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
    try:
        cur = db_conn.cursor()
        summary = f"파이프라인 완료 ({total_elapsed}s, 에러 {len(results['errors'])}건)"
        cur.execute("""
            INSERT INTO system_logs (action, category, detail, result)
            VALUES ('daily_pipeline', 'system', %s, %s)
        """, (summary, json.dumps(results, ensure_ascii=False, default=str)[:2000]))
        db_conn.commit()
    except Exception:
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
