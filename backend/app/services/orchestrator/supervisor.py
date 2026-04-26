"""오케스트레이터 AI 슈퍼바이저 — 메인 실행기.

매일 09:30 KST 자동 실행:
1. 에이전트별 지표 수집
2. 상담 품질 체크
3. 학�� 파이프라인 감시
4. 자동 개선 조치
5. 보고서 생성 + 전송
"""

import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)


def collect_metrics(db_conn) -> Dict[str, Any]:
    """DB 쿼리로 에이전트별 핵심 지표 수집."""
    cur = db_conn.cursor()
    metrics: Dict[str, Any] = {}

    # ── A. AI 에이전트 상담 지표 ──
    try:
        # 오늘 ���담 건수 (에이전트별)
        cur.execute("""
            SELECT
                COALESCE(mode, 'unknown') as agent,
                COUNT(*) as cnt,
                COUNT(*) FILTER (WHERE reply ILIKE '%%오류%%' OR reply ILIKE '%%실패%%') as error_cnt
            FROM ai_consult_logs
            WHERE created_at >= CURRENT_DATE
            GROUP BY mode
        """)
        agent_stats = {}
        for r in cur.fetchall():
            agent_stats[r["agent"]] = {"count": r["cnt"], "errors": r["error_cnt"]}
        metrics["agents"] = agent_stats

        # 전체 상담 건수
        cur.execute("SELECT COUNT(*) as cnt FROM ai_consult_logs WHERE created_at >= CURRENT_DATE")
        metrics["total_consults_today"] = cur.fetchone()["cnt"]

        # PRO 세션
        cur.execute("SELECT COUNT(*) as cnt FROM pro_consult_sessions WHERE created_at >= CURRENT_DATE")
        metrics["pro_sessions_today"] = cur.fetchone()["cnt"]
    except Exception as e:
        logger.warning(f"[Supervisor] agent metrics error: {e}")
        try: db_conn.rollback()
        except: pass
        metrics["agents"] = {}
        metrics["total_consults_today"] = 0

    # ── B. 지식 파이프라인 ──
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM knowledge_base")
        metrics["kb_total"] = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) as cnt FROM knowledge_base WHERE created_at >= CURRENT_DATE")
        metrics["kb_new_today"] = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) as cnt FROM knowledge_base WHERE use_count = 0")
        metrics["kb_unused"] = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) as cnt FROM knowledge_base WHERE embedding IS NULL")
        metrics["kb_no_embedding"] = cur.fetchone()["cnt"]
    except Exception as e:
        logger.warning(f"[Supervisor] kb metrics error: {e}")
        try: db_conn.rollback()
        except: pass

    # ── C. 공고 분석 ──
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM announcements")
        total_ann = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM announcement_analysis")
        analyzed = cur.fetchone()["cnt"]
        metrics["announcements_total"] = total_ann
        metrics["announcements_analyzed"] = analyzed
        metrics["analysis_rate"] = round(analyzed / total_ann * 100, 1) if total_ann > 0 else 0

        # 오늘 수집된 공고
        cur.execute("SELECT COUNT(*) as cnt FROM announcements WHERE created_at >= CURRENT_DATE")
        metrics["new_announcements_today"] = cur.fetchone()["cnt"]

        # 분석 큐 대기
        cur.execute("SELECT COUNT(*) as cnt FROM analysis_failures WHERE resolved_at IS NULL")
        metrics["analysis_queue"] = cur.fetchone()["cnt"]
    except Exception as e:
        logger.warning(f"[Supervisor] analysis metrics error: {e}")
        try: db_conn.rollback()
        except: pass

    # ── D. 비즈니스 지표 ──
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM users WHERE updated_at >= CURRENT_DATE")
        metrics["new_users_today"] = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT plan, COUNT(*) as cnt
            FROM users
            GROUP BY plan
        """)
        plan_dist = {}
        for r in cur.fetchall():
            plan_dist[r["plan"] or "free"] = r["cnt"]
        metrics["plan_distribution"] = plan_dist
    except Exception as e:
        logger.warning(f"[Supervisor] business metrics error: {e}")
        try: db_conn.rollback()
        except: pass

    # ── E. 만료 공고 비율 ──
    try:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE deadline_date < CURRENT_DATE) as expired,
                COUNT(*) as total
            FROM announcements
            WHERE deadline_date IS NOT NULL
        """)
        r = cur.fetchone()
        metrics["expired_ratio"] = round(r["expired"] / r["total"] * 100, 1) if r["total"] > 0 else 0
    except Exception as e:
        logger.warning(f"[Supervisor] expiry metrics error: {e}")
        try: db_conn.rollback()
        except: pass

    return metrics


def detect_anomalies(metrics: Dict[str, Any], url_health: Dict = None) -> list:
    """임계값 기반 이상 감지. 반환: [(severity, message), ...]"""
    alerts = []

    # 상담 0건
    if metrics.get("total_consults_today", 0) == 0:
        alerts.append(("info", "오늘 상담 0건 — 사용자 활동 없음"))

    # 에이전트별 오류율
    for agent, stats in metrics.get("agents", {}).items():
        if stats["count"] > 0:
            error_rate = stats["errors"] / stats["count"]
            if error_rate > 0.1:
                alerts.append(("warning", f"{agent} 오류율 {error_rate*100:.0f}% (임계: 10%)"))

    # 신규 공고 수집 0건
    if metrics.get("new_announcements_today", 0) == 0:
        alerts.append(("info", "오늘 신규 공고 수집 0건"))

    # 분석률
    if metrics.get("analysis_rate", 100) < 20:
        alerts.append(("warning", f"공고 분석률 {metrics.get('analysis_rate')}% — 20% 미만"))

    # 분석 큐 과다
    queue = metrics.get("analysis_queue", 0)
    if queue > 200:
        alerts.append(("warning", f"분석 큐 {queue}건 대기 중"))

    # 미활용 지식 비율
    kb_total = metrics.get("kb_total", 1)
    kb_unused = metrics.get("kb_unused", 0)
    if kb_total > 0 and kb_unused / kb_total > 0.8:
        alerts.append(("warning", f"knowledge_base 미활용 비율 {kb_unused/kb_total*100:.0f}%"))

    # 임베딩 누락
    if metrics.get("kb_no_embedding", 0) > 10:
        alerts.append(("info", f"knowledge_base 임베딩 누락 {metrics.get('kb_no_embedding')}건"))

    # 만료 공고
    if metrics.get("expired_ratio", 0) > 50:
        alerts.append(("warning", f"만료 공고 비율 {metrics.get('expired_ratio')}%"))

    # URL 오등록 의심 기관
    if url_health:
        suspect_count = url_health.get("suspect_count", 0)
        if suspect_count > 0:
            alerts.append(("warning", f"admin_urls 의심 기관 {suspect_count}개 — URL 점검 필요"))

    return alerts


def auto_improve(db_conn, metrics: Dict, quality: Dict, learning: Dict) -> list:
    """자동 개선 조치 실행. 반환: 수행한 조치 목록."""
    actions = []
    cur = db_conn.cursor()

    # 1. 임베딩 누락 지식 보강
    if metrics.get("kb_no_embedding", 0) > 0:
        try:
            from ..ai_consultant import _generate_knowledge_embedding
            import json as _json

            cur.execute("""
                SELECT id, category, content
                FROM knowledge_base
                WHERE embedding IS NULL
                LIMIT 20
            """)
            rows = cur.fetchall()
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
                actions.append(f"임베딩 누락 {fixed}건 보강")
        except Exception as e:
            logger.warning(f"[Supervisor] embed fix error: {e}")
            try:
                db_conn.rollback()
            except Exception:
                pass

    # 2. 품질 낮은 에이전트 → 관련 지식 부족 여부 확인
    for agent_name, scores in quality.get("agent_scores", {}).items():
        avg = scores.get("avg_score", 10)
        if avg < 6:
            actions.append(f"{agent_name} 평균 품질 {avg:.1f}/10 — 지식 보강 필요")

    # 3. 학습 중단 감지
    if learning.get("extraction_today", 0) == 0 and metrics.get("total_consults_today", 0) > 5:
        actions.append("상담 5건 이상인데 학습 추출 0건 — 학습 파이프라인 점검 필요")

    # 4. 30일+ 미활용 저신뢰 지식 자동 정리
    #    (daily_pipeline propagate_learning이 DELETE하지만, 여기서도 보조 실행 — 수동 트리거 대비)
    try:
        cur.execute("""
            DELETE FROM knowledge_base
            WHERE confidence < 0.3
              AND use_count = 0
              AND created_at < CURRENT_DATE - INTERVAL '30 days'
        """)
        removed = cur.rowcount or 0
        if removed > 0:
            db_conn.commit()
            actions.append(f"미활용 저품질 지식 {removed}건 정리")
    except Exception as e:
        logger.warning(f"[Supervisor] KB cleanup error: {e}")
        try: db_conn.rollback()
        except Exception: pass

    # 5. 최근 7일 저품질 상담 샘플 수 집계 → 재검토 요청
    try:
        cur.execute("""
            SELECT COUNT(*) as cnt FROM orchestrator_reviews
            WHERE needs_review = TRUE
              AND review_date >= CURRENT_DATE - INTERVAL '7 days'
        """)
        row = cur.fetchone()
        low_cnt = row["cnt"] if row else 0
        if low_cnt >= 5:
            actions.append(f"7일간 5점 미만 상담 {low_cnt}건 — orchestrator_reviews 재검토 필요")
    except Exception as e:
        logger.warning(f"[Supervisor] review count error: {e}")
        try: db_conn.rollback()
        except Exception: pass

    return actions


def run_daily_supervision(db_conn) -> Dict[str, Any]:
    """일일 슈퍼바이저 전체 실행. patrol 스케줄러에서 호출."""
    start = time.time()
    result = {"success": False}

    try:
        # 1. 지표 수집
        logger.info("[Supervisor] Collecting metrics...")
        metrics = collect_metrics(db_conn)

        # 2. URL 헬스체크 (admin_urls 오등록/장기 미수집 감지)
        logger.info("[Supervisor] Checking admin URL health...")
        url_health: Dict[str, Any] = {}
        try:
            from .scraper_monitor import check_admin_url_health
            url_health = check_admin_url_health(db_conn)
            logger.info(f"[Supervisor] URL health: {url_health.get('suspect_count', 0)} suspects / {url_health.get('total_active', 0)} active")
        except Exception as e:
            logger.warning(f"[Supervisor] URL health check error: {e}")

        # 3. 비지원사업 공고 일일 정제
        logger.info("[Supervisor] Cleaning non-support announcements...")
        cleanup_deleted = 0
        try:
            from app.main import _cleanup_non_support_announcements
            cleanup_deleted = _cleanup_non_support_announcements() or 0
            if cleanup_deleted:
                logger.info(f"[Supervisor] Cleanup: {cleanup_deleted} non-support announcements deleted")
        except Exception as e:
            logger.warning(f"[Supervisor] Cleanup error: {e}")

        # 4. 이상 감지
        alerts = detect_anomalies(metrics, url_health=url_health)

        # 5. 품질 체크
        logger.info("[Supervisor] Checking agent quality...")
        from .quality_checker import check_agent_quality
        quality = check_agent_quality(db_conn)

        # 6. 학습 감시
        logger.info("[Supervisor] Checking learning health...")
        from .learning_monitor import check_learning_health
        learning = check_learning_health(db_conn)

        # 7. 자동 개선
        logger.info("[Supervisor] Running auto-improvements...")
        actions = auto_improve(db_conn, metrics, quality, learning)
        if cleanup_deleted:
            actions.append(f"비지원사업 공고 {cleanup_deleted}건 정제 완료")

        # 8. 보고서 생성 + 전송
        logger.info("[Supervisor] Generating report...")
        from .reporter import generate_and_send_report
        report_sent = generate_and_send_report(
            db_conn=db_conn,
            metrics=metrics,
            alerts=alerts,
            quality=quality,
            learning=learning,
            actions=actions,
            url_health=url_health,
        )

        elapsed = round(time.time() - start, 1)
        result = {
            "success": True,
            "elapsed_seconds": elapsed,
            "metrics_summary": {
                "consults_today": metrics.get("total_consults_today", 0),
                "kb_total": metrics.get("kb_total", 0),
                "analysis_rate": metrics.get("analysis_rate", 0),
            },
            "alerts_count": len(alerts),
            "actions_count": len(actions),
            "report_sent": report_sent,
            "url_suspects": url_health.get("suspect_count", 0),
            "cleanup_deleted": cleanup_deleted,
        }
        logger.info(f"[Supervisor] Done in {elapsed}s — {len(alerts)} alerts, {len(actions)} actions, {url_health.get('suspect_count',0)} URL suspects")

    except Exception as e:
        logger.error(f"[Supervisor] Error: {e}")
        result["error"] = str(e)

    return result
