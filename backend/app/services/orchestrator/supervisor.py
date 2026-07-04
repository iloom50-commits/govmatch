"""
supervisor.py — 오케스트레이터 AI COO 메인 실행기
매일 09:30 KST (UTC 00:30) 자동 실행

실행 흐름:
  1. 비즈니스 지표 수집 (회원/상담/DAU/매칭)
  2. 학습 현황 감시 (knowledge_base)
  3. 보고서 생성 + 이메일/카카오 발송
"""
import os
import time
import traceback
from datetime import datetime


def run_daily_supervision(db_conn=None) -> dict:
    """
    오케스트레이터 메인 — 매일 09:30 KST 실행.
    db_conn: 외부에서 주입 가능. None이면 내부 생성.
    """
    start = time.time()
    print(f"[AI COO] 일일 보고 시작 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

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
        # ── 1. 비즈니스 지표 수집 ──
        print("[AI COO] Step 1/4: 비즈니스 지표 수집 중...")
        try:
            from .metrics_collector import collect_business_metrics
            metrics = collect_business_metrics(db_conn)
            results["metrics"] = metrics
            print(
                f"  → 총 회원 {metrics.get('users_total')}명 "
                f"| 어제 신규 {metrics.get('new_users_yesterday')}명 "
                f"| DAU {metrics.get('dau_yesterday')}명"
            )
        except Exception as e:
            results["metrics"] = {"error": str(e)}
            metrics = {}
            print(f"  → 지표 수집 오류: {e}")
            traceback.print_exc()

        # ── 2. 에이전트 품질 감시 ──
        print("[AI COO] Step 2/4: 에이전트 역할 적합성 평가 중...")
        try:
            from .quality_checker import check_quality
            quality = check_quality(db_conn)
            results["quality"] = quality
            agents = quality.get("agents", {})
            for key, info in agents.items():
                score = info.get("avg_score")
                status = info.get("status", "no_data")
                flag = "⚠️" if status == "warning" else ("✅" if score is not None else "–")
                print(f"  → {flag} {info['label']}: {score if score is not None else 'N/A'}점")
            if quality.get("total_low_quality", 0) > 0:
                print(f"  → ⚠️ 저품질 {quality['total_low_quality']}건 발견")
        except Exception as e:
            results["quality"] = {"error": str(e)}
            quality = {}
            print(f"  → 품질 평가 오류: {e}")
            traceback.print_exc()

        # ── 3. 학습 현황 감시 ──
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

        # ── 4. SEO 현황 감시 ──
        print("[AI COO] Step 4/5: SEO 현황 수집 + AI 분석 중...")
        try:
            from .seo_monitor import check_seo
            seo = check_seo()
            results["seo"] = seo
            if seo.get("skipped"):
                print(f"  → SEO 스킵: {seo.get('reason')}")
            elif seo.get("error"):
                print(f"  → SEO 오류: {seo['error']}")
            else:
                t = seo.get("total", {})
                print(f"  → 클릭 {t.get('clicks')}회, 노출 {t.get('impressions')}회, CTR {t.get('ctr')}%, 순위 {t.get('position')}위")
        except Exception as e:
            results["seo"] = {"error": str(e)}
            seo = {}
            print(f"  → SEO 감시 오류: {e}")
            traceback.print_exc()

        # ── 5. 시스템 건강/경보 수집 (조용한 고장 감지) ──
        print("[AI COO] Step 5/6: 시스템 건강/경보 수집 중...")
        try:
            from .health_collector import collect_health
            health = collect_health(db_conn)
            results["health"] = health
            if health.get("alerts"):
                print(f"  → 🚨 경보 {len(health['alerts'])}건: {health['alerts']}")
            else:
                print("  → ✅ 시스템 이상 없음")
        except Exception as e:
            results["health"] = {"error": str(e)}
            print(f"  → 건강/경보 수집 오류: {e}")
            traceback.print_exc()

        # ── 6. 보고서 발송 ──
        print("[AI COO] Step 6/6: 보고서 생성 + 발송 중...")
        try:
            from .reporter import send_report
            report_result = send_report(
                metrics=results.get("metrics", {}),
                learning=results.get("learning", {}),
                quality=results.get("quality", {}),
                seo=results.get("seo", {}),
                health=results.get("health", {}),
            )
            results["report"] = report_result
            print(f"  → 이메일={report_result.get('email_sent')}, 카카오={report_result.get('kakao_sent')}")
            # dead-man's switch용 heartbeat — 경보 채널(운영현황 메일)이 살아있다는 증거.
            # 다이제스트 잡이 이 로그의 부재를 감지해 오너에게 교차 경보한다(C-4).
            if report_result.get("email_sent") or report_result.get("kakao_sent"):
                try:
                    _hc = db_conn.cursor()
                    _hc.execute(
                        "INSERT INTO system_logs (action, category, detail, result) "
                        "VALUES ('coo_report_sent', 'system', %s, 'success')",
                        (f"email={report_result.get('email_sent')} kakao={report_result.get('kakao_sent')}",),
                    )
                    db_conn.commit()
                except Exception:
                    try:
                        db_conn.rollback()
                    except Exception:
                        pass
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
    print(f"[AI COO] 일일 보고 완료 — {elapsed}초 소요")
    return results
