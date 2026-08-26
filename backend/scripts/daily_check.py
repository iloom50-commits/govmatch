# -*- coding: utf-8 -*-
"""일일 파이프라인 결과 점검 — 아침에 한 번 돌려 어젯밤 실행이 정상이었는지 본다.

왜 필요한가 (2026-08-26)
  step:④ 공고 분석 이 이틀간(08-25·26) [error] 였는데 아무도 몰랐다.
  일일 메일에는 「시스템 정상」이라고 떴다 — 단계 실패가 메일에 반영되지 않는다.
  대표가 다른 일로 물어보지 않았다면 계속 죽어 있었을 것이다.

  눈으로 로그를 훑는 대신 **판정을 내려 보여준다**. 각 항목에 ✓ / ★ 를 붙인다.

실행:  cd backend && python scripts/daily_check.py
종료코드 1 = 확인이 필요한 항목이 있음
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    import psycopg2
    import psycopg2.extras
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=str(ROOT / ".env"))
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL 미설정 — 확인 불가")
        return 2

    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    problems = []

    cur.execute("SELECT NOW() AT TIME ZONE 'Asia/Seoul' AS kst")
    print(f"■ 점검 시각 {cur.fetchone()['kst']:%Y-%m-%d %H:%M} KST\n")

    # ── 1. 어젯밤 파이프라인이 돌았고, 실패한 단계가 없는가
    cur.execute("""
        SELECT (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul') AS kst,
               action, result, count_affected, LEFT(COALESCE(detail,''),90) AS d
        FROM system_logs
        WHERE category = 'pipeline_step' AND created_at > NOW() - INTERVAL '14 hours'
        ORDER BY created_at
    """)
    steps = cur.fetchall()
    if not steps:
        problems.append("파이프라인이 최근 14시간 안에 돌지 않았다")
        print("★ 파이프라인 기록 없음")
    else:
        bad = [s for s in steps if s["result"] not in ("ok", "warn")]
        print(f"{'★' if bad else '✓'} 파이프라인 {len(steps)}단계 · 실패 {len(bad)}건 "
              f"({steps[0]['kst']:%m-%d %H:%M} ~ {steps[-1]['kst']:%H:%M})")
        for s in bad:
            problems.append(f"{s['action']} 실패")
            print(f"    ★ {s['kst']:%H:%M} {s['action']} [{s['result']}]")
            print(f"       {s['d']}")

    # ── 2. 죽은 링크 검사가 돌았는가 (돌면 결과, 안 돌면 그것도 신호)
    cur.execute("""SELECT (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul') AS kst, detail
                   FROM system_logs WHERE action LIKE 'step:④-L%%'
                   ORDER BY created_at DESC LIMIT 1""")
    r = cur.fetchone()
    ran_link = any("④" in s["action"] and s["result"] == "ok" for s in steps)
    if r:
        d = json.loads(r["detail"]) if isinstance(r["detail"], str) else (r["detail"] or {})
        hosts = d.get("hosts") or []
        fresh = "오늘" if steps and r["kst"].date() >= steps[-1]["kst"].date() else "예전"
        mark = "★" if hosts and fresh == "오늘" else " "
        print(f"{mark} 죽은 링크 — {fresh} 기록 {r['kst']:%m-%d %H:%M} · {d.get('announcements', 0)}건")
        for h in hosts[:6]:
            print(f"      · {h.get('host')} — {h.get('total')}건")
        if hosts and fresh == "오늘":
            problems.append(f"죽은 링크 {len(hosts)}개 수집처")
    else:
        print("✓ 죽은 링크 — 기록 없음(죽은 것이 없으면 남기지 않는다)")

    # ── 3. 마감 지난 공고를 분석하고 있지 않은가
    cur.execute("""SELECT COUNT(*) AS total,
                          COUNT(*) FILTER (WHERE a.deadline_date < CURRENT_DATE) AS expired
                   FROM announcement_analysis aa JOIN announcements a USING (announcement_id)
                   WHERE aa.created_at > NOW() - INTERVAL '14 hours'""")
    x = cur.fetchone()
    if x["total"]:
        pct = x["expired"] / x["total"] * 100
        mark = "★" if pct > 5 else "✓"
        print(f"{mark} 최근 분석 {x['total']}건 중 마감 지난 것 {x['expired']}건 ({pct:.0f}퍼센트)")
        if pct > 5:
            problems.append(f"마감 지난 공고 분석 {pct:.0f}퍼센트")
    else:
        print("★ 최근 14시간 분석 0건")
        problems.append("분석이 한 건도 되지 않았다")

    # ── 4. 메일에 뜨는 숫자
    cur.execute("""SELECT COUNT(*) FILTER (WHERE error_type='pending_first_analysis') AS pend,
                          COUNT(*) FILTER (WHERE error_type<>'pending_first_analysis') AS fail
                   FROM analysis_failures WHERE resolved_at IS NULL""")
    x = cur.fetchone()
    print(f"  분석대기 {x['pend']}건 · 분석실패 {x['fail']}건")

    # ── 5. 서비스가 살아 있는가
    cur.execute("""SELECT COUNT(*) AS n FROM announcements
                   WHERE created_at > NOW() - INTERVAL '2 days'""")
    n = cur.fetchone()["n"]
    print(f"{'✓' if n else '★'} 최근 2일 신규 공고 {n}건")
    if not n:
        problems.append("이틀간 신규 공고 0건")

    conn.close()
    print()
    if problems:
        print(f"★ 확인이 필요한 것 {len(problems)}건")
        for p in problems:
            print(f"   · {p}")
        return 1
    print("✓ 모두 정상")
    return 0


if __name__ == "__main__":
    sys.exit(main())
