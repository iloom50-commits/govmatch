"""
기존 공고 AI 재분석 스크립트 (PostgreSQL)
- eligibility_logic이 비어있는 공고를 AI 분석 후 업데이트
- 사용법: python reanalyze_pg.py [--limit N] [--batch N] [--delay N]
"""

import asyncio
import psycopg2
import psycopg2.extras
import json
import re
import sys
import io
import argparse
from datetime import datetime
from app.config import DATABASE_URL
from app.services.ai_service import ai_service

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;|&amp;|&lt;|&gt;|&#\d+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_db():
    db_url = DATABASE_URL.replace(":6543/", ":5432/")
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    return conn


def get_unanalyzed(limit: int) -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT announcement_id, title, summary_text, origin_url, department, category
        FROM announcements
        WHERE eligibility_logic IS NULL
           OR eligibility_logic = ''
           OR eligibility_logic = '{}'
        ORDER BY announcement_id
        LIMIT %s
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def save_analysis(ann_id: int, details: dict, conn):
    cur = conn.cursor()

    elig = details.get("eligibility_logic", {})
    if not isinstance(elig, dict):
        elig = {}

    if details.get("business_type"):
        elig["business_type"] = details["business_type"]
    if details.get("target_keywords"):
        elig["target_keywords"] = details["target_keywords"]
    if details.get("target_industries"):
        elig["target_industries"] = details["target_industries"]

    eligibility_json = json.dumps(elig, ensure_ascii=False)
    ai_summary = details.get("summary_text") or details.get("description", "")

    cur.execute("""
        UPDATE announcements SET
            eligibility_logic = %s,
            summary_text = CASE WHEN %s != '' THEN %s ELSE summary_text END,
            department = CASE WHEN department IS NULL OR department = '' THEN %s ELSE department END,
            category = CASE WHEN category IS NULL OR category = '' THEN %s ELSE category END,
            deadline_date = CASE WHEN deadline_date IS NULL AND %s IS NOT NULL THEN %s::date ELSE deadline_date END
        WHERE announcement_id = %s
    """, (
        eligibility_json,
        ai_summary, ai_summary,
        details.get("department", ""),
        details.get("category", ""),
        details.get("deadline_date"), details.get("deadline_date"),
        ann_id,
    ))


async def analyze_one(row: dict) -> dict | None:
    title = row.get("title", "")
    raw_summary = row.get("summary_text", "")
    clean_summary = strip_html(raw_summary)

    input_text = f"제목: {title}\n\n내용: {clean_summary[:8000]}"

    if len(clean_summary.strip()) < 20 and len(title.strip()) < 10:
        return None

    try:
        details = await ai_service.extract_program_details(input_text)
        return details
    except Exception as e:
        print(f"    [WARN] AI error: {e}")
        return None


async def run(limit: int, batch_size: int, delay: float):
    rows = get_unanalyzed(limit)
    total = len(rows)
    print(f"Analysis target: {total} items (limit={limit})")

    if total == 0:
        print("[OK] No announcements to analyze.")
        return

    conn = get_db()
    success = 0
    skipped = 0
    failed = 0
    start = datetime.now()

    for i, row in enumerate(rows, 1):
        ann_id = row.get("announcement_id")
        title = row.get("title", "")[:50]

        print(f"  [{i}/{total}] {title}...", end=" ", flush=True)

        details = await analyze_one(row)

        if not details:
            print("SKIP")
            skipped += 1
        else:
            try:
                save_analysis(ann_id, details, conn)
                btype = ", ".join(details.get("business_type") or [])
                cat = details.get("category", "?")
                print(f"OK ({cat} / {btype})")
                success += 1
            except Exception as e:
                print(f"DB error: {e}")
                failed += 1

        if i % batch_size == 0:
            elapsed = (datetime.now() - start).total_seconds()
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            print(f"\n  --- {i}/{total} done | ok:{success} skip:{skipped} fail:{failed} "
                  f"| {rate:.1f}/s | ETA:{eta/60:.1f}min ---\n")

        await asyncio.sleep(delay)

    conn.close()

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n{'='*60}")
    print(f"[DONE] success={success}, skipped={skipped}, failed={failed}")
    print(f"   Time: {elapsed/60:.1f}min ({elapsed:.0f}s)")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI reanalysis (PostgreSQL)")
    parser.add_argument("--limit", type=int, default=100, help="Max items (default: 100)")
    parser.add_argument("--batch", type=int, default=20, help="Progress interval (default: 20)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests (default: 0.5s)")
    args = parser.parse_args()

    print(f"[START] AI reanalysis | limit={args.limit} delay={args.delay}s")
    asyncio.run(run(args.limit, args.batch, args.delay))
