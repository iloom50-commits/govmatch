"""
기존 공고의 support_amount가 비어 있는 경우 summary_text/title에서 정규식으로 추출해 채운다.

Usage (Railway shell 또는 로컬에서 DATABASE_URL 환경변수 설정 후):
    python -m scripts.backfill_support_amount             # dry-run
    python -m scripts.backfill_support_amount --commit    # 실제 UPDATE

안전:
- support_amount가 이미 있으면 건드리지 않음
- 정규식으로 추출 못 하면 그대로 둠
- --commit 없으면 SELECT만 하고 샘플 출력
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import DATABASE_URL
from app.services.public_api_service import GovernmentAPIService
import psycopg2
import psycopg2.extras


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true", help="실제 UPDATE 수행")
    parser.add_argument("--limit", type=int, default=0, help="처리 행 수 제한 (0=무제한)")
    args = parser.parse_args()

    extract = GovernmentAPIService._extract_amount_from_text

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    sql = """
        SELECT announcement_id, title, summary_text
        FROM announcements
        WHERE (support_amount IS NULL OR support_amount = '')
        ORDER BY announcement_id DESC
    """
    if args.limit > 0:
        sql += f" LIMIT {int(args.limit)}"
    cur.execute(sql)
    rows = cur.fetchall()
    print(f"[Backfill] 대상: {len(rows)}건 (support_amount 비어있음)")

    updated = 0
    samples = []
    for row in rows:
        text = (row["summary_text"] or "") + " " + (row["title"] or "")
        amount = extract(text)
        if not amount:
            continue
        if args.commit:
            cur.execute(
                "UPDATE announcements SET support_amount = %s WHERE announcement_id = %s",
                (amount, row["announcement_id"]),
            )
        updated += 1
        if len(samples) < 10:
            samples.append((row["announcement_id"], row["title"][:40], amount))

    if args.commit:
        conn.commit()
        print(f"[Backfill] COMMIT 완료: {updated}건 업데이트")
    else:
        print(f"[Backfill] DRY-RUN: {updated}건 추출 가능 (실제 반영 X)")

    print("\n샘플:")
    for s in samples:
        print(f"  #{s[0]}  [{s[2]}]  {s[1]}")

    conn.close()


if __name__ == "__main__":
    main()
