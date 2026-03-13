"""
기존 공고 AI 재분석 스크립트
- eligibility_logic이 없는 공고를 DB에서 꺼내 AI 분석 후 저장
- 사용법: python reanalyze_announcements.py [--limit N] [--batch N]
"""

import asyncio
import sqlite3
import json
import re
import sys
import argparse
from datetime import datetime
from app.config import DB_PATH
from app.services.ai_service import ai_service


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_unanalyzed(limit: int) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT announcement_id, rowid, title, summary_text, origin_url, department, category
        FROM announcements
        WHERE eligibility_logic IS NULL
           OR eligibility_logic = ''
           OR eligibility_logic = '{}'
        ORDER BY announcement_id
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def save_analysis(ann_id: int, rowid: int, details: dict, conn: sqlite3.Connection):
    cursor = conn.cursor()

    elig = details.get("eligibility_logic", {})
    if not isinstance(elig, dict):
        elig = {}

    # business_type, target_keywords → eligibility_logic 안에 통합
    if details.get("business_type"):
        elig["business_type"] = details["business_type"]
    if details.get("target_keywords"):
        elig["target_keywords"] = details["target_keywords"]

    eligibility_json = json.dumps(elig, ensure_ascii=False)
    ai_summary = details.get("summary_text") or details.get("description", "")

    pk = ann_id or rowid
    cursor.execute("""
        UPDATE announcements SET
            eligibility_logic = ?,
            summary_text = CASE WHEN ? != '' THEN ? ELSE summary_text END,
            department = CASE WHEN department IS NULL OR department = '' THEN ? ELSE department END,
            category = CASE WHEN category IS NULL OR category = '' THEN ? ELSE category END,
            deadline_date = CASE WHEN deadline_date IS NULL AND ? IS NOT NULL THEN ? ELSE deadline_date END
        WHERE announcement_id = ? OR (announcement_id IS NULL AND rowid = ?)
    """, (
        eligibility_json,
        ai_summary, ai_summary,
        details.get("department", ""),
        details.get("category", ""),
        details.get("deadline_date"), details.get("deadline_date"),
        pk, rowid,
    ))
    conn.commit()


async def analyze_one(row: dict) -> dict | None:
    title = row.get("title", "")
    raw_summary = row.get("summary_text", "")
    clean_summary = strip_html(raw_summary)

    # AI에 넘길 텍스트 구성
    input_text = f"제목: {title}\n\n내용: {clean_summary[:8000]}"

    if len(clean_summary.strip()) < 20 and len(title.strip()) < 10:
        return None  # 데이터 너무 부족

    try:
        details = await ai_service.extract_program_details(input_text)
        return details
    except Exception as e:
        print(f"    ⚠️ AI 오류: {e}")
        return None


async def run(limit: int, batch_size: int, delay: float):
    rows = get_unanalyzed(limit)
    total = len(rows)
    print(f"📊 분석 대상: {total}건 (limit={limit})")

    if total == 0:
        print("✅ 분석할 공고가 없습니다.")
        return

    conn = sqlite3.connect(DB_PATH, timeout=30)
    success = 0
    skipped = 0
    failed = 0
    start = datetime.now()

    for i, row in enumerate(rows, 1):
        ann_id = row.get("announcement_id")
        rowid = row.get("rowid")
        title = row.get("title", "")[:50]

        print(f"  [{i}/{total}] {title}...", end=" ", flush=True)

        details = await analyze_one(row)

        if not details:
            print("SKIP (데이터 부족)")
            skipped += 1
        else:
            try:
                save_analysis(ann_id, rowid, details, conn)
                print(f"OK  ({details.get('category','?')} / {', '.join(details.get('business_type') or [])})")
                success += 1
            except Exception as e:
                print(f"DB 오류: {e}")
                failed += 1

        # 진행률 출력 (배치마다)
        if i % batch_size == 0:
            elapsed = (datetime.now() - start).total_seconds()
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            print(f"\n  ─── {i}/{total}건 처리 | 성공:{success} 스킵:{skipped} 실패:{failed} "
                  f"| 속도:{rate:.1f}건/s | 예상남은시간:{eta/60:.1f}분 ───\n")

        await asyncio.sleep(delay)

    conn.close()

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n{'='*60}")
    print(f"✅ 완료: 성공={success}, 스킵={skipped}, 실패={failed}")
    print(f"   소요시간: {elapsed/60:.1f}분 ({elapsed:.0f}초)")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="기존 공고 AI 재분석")
    parser.add_argument("--limit", type=int, default=100, help="처리할 최대 공고 수 (기본: 100)")
    parser.add_argument("--batch", type=int, default=20, help="진행률 출력 단위 (기본: 20)")
    parser.add_argument("--delay", type=float, default=0.5, help="요청 간격(초) (기본: 0.5)")
    args = parser.parse_args()

    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print(f"[START] AI reanalysis | limit={args.limit} delay={args.delay}s")
    asyncio.run(run(args.limit, args.batch, args.delay))
