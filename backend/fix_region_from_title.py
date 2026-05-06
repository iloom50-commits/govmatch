"""공고 제목의 [지역] 태그로 잘못된 region 필드 보정.

실행: python fix_region_from_title.py
"""
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.main import get_db_connection

# 시·군·구 → 시도 매핑 (제목에 브래킷 태그 없을 때 보조 사용)
SIGUNGU_TO_SIDO = {
    # 경남
    "양산": "경남", "창원": "경남", "김해": "경남", "진주": "경남",
    "거제": "경남", "통영": "경남", "사천": "경남", "밀양": "경남",
    "함안": "경남", "고성": "경남", "남해": "경남", "하동": "경남",
    "산청": "경남", "함양": "경남", "거창": "경남", "합천": "경남",
    "의령": "경남",
    # 경북
    "포항": "경북", "경주": "경북", "구미": "경북", "안동": "경북",
    "영주": "경북", "영천": "경북", "상주": "경북", "문경": "경북",
    "경산": "경북", "군위": "경북", "의성": "경북", "청송": "경북",
    "영양": "경북", "영덕": "경북", "청도": "경북", "고령": "경북",
    "성주": "경북", "칠곡": "경북", "예천": "경북", "봉화": "경북",
    "울진": "경북", "울릉": "경북",
    # 전남
    "목포": "전남", "여수": "전남", "순천": "전남", "나주": "전남",
    "광양": "전남", "담양": "전남", "곡성": "전남", "구례": "전남",
    "고흥": "전남", "보성": "전남", "화순": "전남", "장흥": "전남",
    "강진": "전남", "해남": "전남", "영암": "전남", "무안": "전남",
    "함평": "전남", "영광": "전남", "장성": "전남", "완도": "전남",
    "진도": "전남", "신안": "전남",
    # 전북
    "전주": "전북", "군산": "전북", "익산": "전북", "정읍": "전북",
    "남원": "전북", "김제": "전북", "완주": "전북", "진안": "전북",
    "무주": "전북", "장수": "전북", "임실": "전북", "순창": "전북",
    "고창": "전북", "부안": "전북",
    # 충남
    "천안": "충남", "공주": "충남", "보령": "충남", "아산": "충남",
    "서산": "충남", "논산": "충남", "계룡": "충남", "당진": "충남",
    "금산": "충남", "부여": "충남", "서천": "충남", "청양": "충남",
    "홍성": "충남", "예산": "충남", "태안": "충남",
    # 충북
    "청주": "충북", "충주": "충북", "제천": "충북", "보은": "충북",
    "옥천": "충북", "영동": "충북", "증평": "충북", "진천": "충북",
    "괴산": "충북", "음성": "충북", "단양": "충북",
    # 강원
    "춘천": "강원", "원주": "강원", "강릉": "강원", "동해": "강원",
    "태백": "강원", "속초": "강원", "삼척": "강원", "홍천": "강원",
    "횡성": "강원", "영월": "강원", "평창": "강원", "정선": "강원",
    "철원": "강원", "화천": "강원", "양구": "강원", "인제": "강원",
    "고성": "강원", "양양": "강원",
    # 경기
    "수원": "경기", "성남": "경기", "고양": "경기", "용인": "경기",
    "부천": "경기", "안산": "경기", "안양": "경기", "남양주": "경기",
    "화성": "경기", "평택": "경기", "의정부": "경기", "시흥": "경기",
    "파주": "경기", "김포": "경기", "광명": "경기", "광주": "경기",
    "군포": "경기", "하남": "경기", "오산": "경기", "이천": "경기",
    "안성": "경기", "의왕": "경기", "양평": "경기", "여주": "경기",
    "동두천": "경기", "과천": "경기", "구리": "경기", "포천": "경기",
    "양주": "경기", "연천": "경기", "가평": "경기",
}

BRACKET_REGION_MAP = {
    "서울": "서울", "부산": "부산", "대구": "대구", "인천": "인천",
    "광주": "광주", "대전": "대전", "울산": "울산", "세종": "세종",
    "경기": "경기", "강원": "강원", "충북": "충북", "충남": "충남",
    "전북": "전북", "전남": "전남", "경북": "경북", "경남": "경남",
    "제주": "제주",
}

BRACKET_RE = re.compile(r'\[([가-힣]{2,4})\]')


def extract_region_from_title(title: str):
    """제목에서 지역 추출. 브래킷 태그 우선, 없으면 시·군·구 이름으로 보조."""
    m = BRACKET_RE.search(title)
    if m:
        tag = m.group(1)
        if tag in BRACKET_REGION_MAP:
            return BRACKET_REGION_MAP[tag]

    # 브래킷 없으면 시·군·구 이름으로 추론 (제목 앞 40자)
    head = title[:40]
    for sigungu, sido in SIGUNGU_TO_SIDO.items():
        if sigungu in head:
            return sido

    return None


def run():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT announcement_id, title, region
        FROM announcements
        WHERE region IS NOT NULL AND region NOT IN ('전국', '', 'All', '전국 및 각 지역')
        ORDER BY announcement_id
    """)
    rows = cur.fetchall()

    updated = 0
    skipped = 0
    errors = []

    for row in rows:
        aid = row["announcement_id"]
        title = row["title"] or ""
        stored_region = row["region"] or ""

        inferred = extract_region_from_title(title)
        if not inferred:
            skipped += 1
            continue

        if inferred == stored_region:
            skipped += 1
            continue

        print(f"[UPDATE] id={aid} | '{stored_region}' → '{inferred}' | {title[:60]}")
        try:
            cur.execute(
                "UPDATE announcements SET region = %s WHERE announcement_id = %s",
                (inferred, aid)
            )
            updated += 1
        except Exception as e:
            errors.append(f"id={aid}: {e}")

    conn.commit()
    conn.close()

    print(f"\n완료: updated={updated}, skipped={skipped}, errors={len(errors)}")
    for e in errors:
        print(f"  ERROR: {e}")


if __name__ == "__main__":
    run()
