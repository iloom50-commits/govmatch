"""
supervisor.py — 오케스트레이터 AI COO 메인 실행기
매일 09:30 KST (UTC 00:30) 자동 실행

실행 흐름:
  1. 상담 지표 수집
  2. 품질 체크 (Gemini 채점)
  3. 학습 감시 (knowledge_base 현황)
  4. 보고서 생성 + 이메일/카카오 발송
"""
import os
import time
import traceback
from datetime import datetime


def collect_metrics(db_conn) -> dict:
    """에이전트별 상담 건수, 오늘 활동량 등 기본 지표 수집"""
    metrics = {}
    cur = db_conn.cursor()

    try:
        cur.execute("SELECT COUNT(*) AS cnt FROM ai_consult_logs")
        row = cur.fetchone()
        metrics["total_consults"] = row["cnt"] if row else 0
    except Exception:
        metrics["total_consults"] = "N/A"

    try:
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM ai_consult_logs
            WHERE updated_at >= CURRENT_DATE
        """)
        row = cur.fetchone()
        metrics["today_consults"] = row["cnt"] if row else 0
    except Exception:
        metrics["today_consults"] = "N/A"

    try:
        cur.execute("SELECT COUNT(*) AS cnt FROM pro_consult_sessions")
        row = cur.fetchone()
        metrics["pro_sessions"] = row["cnt"] if row else 0
    except Exception:
        metrics["pro_sessions"] = "N/A"

    try:
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM pro_consult_sessions
            WHERE updated_at >= CURRENT_DATE
        """)
        row = cur.fetchone()
        metrics["pro_sessions_today"] = row["cnt"] if row else 0
    except Exception:
        metrics["pro_sessions_today"] = "N/A"

    try:
        cur.execute("""
            SELECT COUNT(DISTINCT business_number) AS cnt
            FROM ai_consult_logs
            WHERE updated_at >= CURRENT_DATE - INTERVAL '7 days'
        """)
        row = cur.fetchone()
        metrics["active_users_7d"] = row["cnt"] if row else 0
    except Exception:
        metrics["active_users_7d"] = "N/A"

    return metrics


def run_daily_supervision(db_conn=None) -> dict:
    """
    오케스트레이터 메인 — 매일 09:30 KST 실행.
    db_conn: 외부에서 주입 가능. None이면 내부 생성.
    """
    start = time.time()
    print(f"[AI COO] 일일 감시 시작 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    _own_conn = False
    if db_conn is None:
        try:
            import psycopg2
            import psycopg2.extras
            DATABASE_URL = os.environ.get("DATABASE_URL", "")
            db_conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
            _own_conn = True
        except Exception as e:
            print(f"[AI COO] DB 연결 실패: {e}")
            return {"error": str(e)}

    results = {}

    try:
        # ── 1. 지표 수집 ──
        print("[AI COO] Step 1/4: 상담 지표 수집 중...")
        try:
            metrics = collect_metrics(db_conn)
            results["metrics"] = metrics
            print(f"  → 총 상담 {metrics.get('total_consults')}건, 오늘 {metrics.get('today_consults')}건")
        except Exception as e:
            results["metrics"] = {"error": str(e)}
            print(f"  → 지표 수집 오류: {e}")

        # ── 2. 품질 체크 ──
        print("[AI COO] Step 2/4: 상담 품질 체크 중...")
        try:
            from .quality_checker import check_quality
            quality = check_quality(db_conn)
            results["quality"] = quality
            print(f"  → 평균 품질 {quality.get('avg_total', 0)}/50점, 저품질 {quality.get('low_quality_count', 0)}건")
        except Exception as e:
            results["quality"] = {"error": str(e)}
            quality = {}
            print(f"  → 품질 체크 오류: {e}")
            traceback.print_exc()

        # ── 3. 학습 감시 ──
        print("[AI COO] Step 3/4: 학습 현황 감시 중...")
        try:
            from .learning_monitor import check_learning
            learning = check_learning(db_conn)
            results["learning"] = learning
            print(f"  → 지식베이스 {learning.get('total', 0)}건, 오늘 추가 {learning.get('today_added', 0)}건")
        except Exception as e:
            results["learning"] = {"error": str(e)}
            learning = {}
            print(f"  → 학습 감시 오류: {e}")
            traceback.print_exc()

        # ── 4. 보고서 발송 ──
        print("[AI COO] Step 4/4: 보고서 생성 + 발송 중...")
        try:
            from .reporter import send_report
            report_result = send_report(
                metrics=results.get("metrics", {}),
                quality=results.get("quality", {}),
                learning=results.get("learning", {}),
            )
            results["report"] = report_result
            print(f"  → 이메일={report_result.get('email_sent')}, 카카오={report_result.get('kakao_sent')}")
        except Exception as e:
            results["report"] = {"error": str(e)}
            print(f"  → 보고서 발송 오류: {e}")
            traceback.print_exc()

    finally:
        if _own_conn:
            try:
                db_conn.close()
            except Exception:
                pass

    elapsed = round(time.time() - start, 1)
    results["elapsed"] = elapsed
    print(f"[AI COO] 일일 감시 완료 — {elapsed}초 소요")
    return results
