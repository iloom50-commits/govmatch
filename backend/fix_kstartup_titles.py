"""K-Startup 공고 제목 오염 데이터 정리

문제: <a> 태그 전체 텍스트를 제목으로 저장하여
      "카테고리 D-N 마감일자 YYYY-MM-DD 실제제목" 형태로 오염됨
      &amp; 같은 HTML 엔티티도 미디코딩 상태로 저장됨

수정:
  1. "~마감일자 YYYY-MM-DD " 앞 부분 제거 → 실제 제목만 남김
  2. &amp; → & 등 HTML 엔티티 디코딩
"""
import html as html_lib
import re
import os
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

_PREFIX_RE = re.compile(r"^.+?마감일자\s+\d{4}-\d{2}-\d{2}\s+")


def clean_title(title: str) -> str:
    cleaned = _PREFIX_RE.sub("", title).strip()
    # 정규식 미매칭 시 원본 유지
    result = cleaned if cleaned else title
    # HTML 엔티티 디코딩
    return html_lib.unescape(result)


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # K-Startup 공고 중 오염된 것 조회
    cur.execute("""
        SELECT announcement_id, title
        FROM announcements
        WHERE origin_url LIKE '%%k-startup.go.kr%%'
          AND (
            title ~ '마감일자\\s+\\d{4}-\\d{2}-\\d{2}'
            OR title LIKE '%%&amp;%%'
          )
        ORDER BY announcement_id
    """)
    rows = cur.fetchall()
    print(f"정리 대상: {len(rows)}건")

    updated = 0
    for ann_id, title in rows:
        new_title = clean_title(title)
        if new_title != title:
            cur.execute(
                "UPDATE announcements SET title = %s WHERE announcement_id = %s",
                (new_title[:400], ann_id)
            )
            print(f"  [{ann_id}] {title[:60]!r}")
            print(f"       → {new_title[:60]!r}")
            updated += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"\n완료: {updated}건 업데이트")


if __name__ == "__main__":
    main()
