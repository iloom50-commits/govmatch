"""Phase 2: 누락 기관 식별 — 기준 리스트 vs DB 대조"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from app.main import get_db_connection

# 한국 주요 정부지원사업 발주 기관 기준 리스트
# 대한민국 정부·공공기관·지자체 중 실제 지원사업 발주처

TECHNOPARKS = [
    "서울테크노파크", "경기테크노파크", "경기대진테크노파크", "인천테크노파크",
    "강원테크노파크", "대전테크노파크", "충북테크노파크", "충남테크노파크",
    "세종테크노파크", "전북테크노파크", "광주테크노파크", "전남테크노파크",
    "대구테크노파크", "경북테크노파크", "포항테크노파크", "부산테크노파크",
    "울산테크노파크", "경남테크노파크", "제주테크노파크",
]

CREATIVE_CENTERS = [
    "서울창조경제혁신센터", "경기창조경제혁신센터", "인천창조경제혁신센터",
    "강원창조경제혁신센터", "대전창조경제혁신센터", "충북창조경제혁신센터",
    "충남창조경제혁신센터", "세종창조경제혁신센터", "전북창조경제혁신센터",
    "광주창조경제혁신센터", "전남창조경제혁신센터", "대구창조경제혁신센터",
    "경북창조경제혁신센터", "포항창조경제혁신센터", "부산창조경제혁신센터",
    "울산창조경제혁신센터", "경남창조경제혁신센터", "제주창조경제혁신센터",
]

METRO_GOVS = [
    "서울특별시", "부산광역시", "대구광역시", "인천광역시",
    "광주광역시", "대전광역시", "울산광역시", "세종특별자치시",
    "경기도", "강원특별자치도", "충청북도", "충청남도",
    "전북특별자치도", "전라남도", "경상북도", "경상남도", "제주특별자치도",
]

MAJOR_AGENCIES = [
    "중소벤처기업부", "산업통상자원부", "과학기술정보통신부", "농림축산식품부",
    "보건복지부", "고용노동부", "문화체육관광부", "교육부", "환경부",
    "해양수산부", "국토교통부", "여성가족부",
    "중소벤처기업진흥공단", "한국콘텐츠진흥원", "한국산업기술평가관리원",
    "한국산업기술진흥원", "한국에너지기술평가원", "한국보건산업진흥원",
    "한국농업기술진흥원", "해양수산과학기술진흥원", "KOTRA", "창업진흥원",
    "중소기업중앙회", "소상공인시장진흥공단", "기업은행", "신용보증기금",
    "기술보증기금", "한국관광공사", "한국전자기술연구원", "한국문화예술위원회",
    "한국디자인진흥원", "서울산업진흥원(SBA)", "경기도경제과학진흥원",
    "부산경제진흥원", "인천경제산업정보테크노파크", "대구디지털혁신진흥원",
]

SPECIALIZED = [
    "농업기술실용화재단", "농촌진흥청", "수산업협동조합중앙회",
    "한국에너지공단", "한국환경공단", "한국임업진흥원",
    "영상물등급위원회", "한국출판문화산업진흥원", "한국영상자료원",
    "한국저작권위원회", "한국발명진흥회", "특허청",
]

def check(cur, names, category):
    found = []
    missing = []
    for name in names:
        cur.execute(
            "SELECT COUNT(*) c FROM announcements WHERE department ILIKE %s OR title ILIKE %s",
            (f"%{name}%", f"%{name}%")
        )
        cnt = cur.fetchone()['c']
        if cnt == 0:
            missing.append(name)
        else:
            found.append((name, cnt))
    return found, missing

def main():
    conn = get_db_connection()
    cur = conn.cursor()

    print("="*60)
    print("Phase 2 — 누락 기관 전수 조사")
    print("="*60)

    for category, names in [
        ("테크노파크 (19개)", TECHNOPARKS),
        ("창조경제혁신센터 (18개)", CREATIVE_CENTERS),
        ("광역자치단체 (17개)", METRO_GOVS),
        ("중앙부처·공공기관", MAJOR_AGENCIES),
        ("특화기관", SPECIALIZED),
    ]:
        found, missing = check(cur, names, category)
        total = len(names)
        print(f"\n[{category}] 수집 {len(found)}/{total} | 누락 {len(missing)}")
        print("  ── 수집됨 (상위 10) ──")
        for n, c in sorted(found, key=lambda x: -x[1])[:10]:
            print(f"    {n:<30} {c:>5}건")
        if missing:
            print("  ── 누락 ──")
            for n in missing:
                print(f"    ❌ {n}")

    conn.close()

if __name__ == "__main__":
    main()
