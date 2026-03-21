"""
지자체·공공기관 사업공고 URL 일괄 등록 스크립트
admin_urls 테이블에 주요 기관의 사업공고 목록 페이지를 등록합니다.

실행: python -m app.db.seed_regional_urls
"""
import psycopg2
import psycopg2.extras
from app.config import DATABASE_URL

# ─── 등록할 기관 목록 (source_name, url) ───

REGIONAL_URLS = [
    # ── 테크노파크 (17개 시도) ──
    ("부산테크노파크", "https://www.btp.or.kr/index.php?action=BD0000M&pagecode=P000000296&language=KR"),
    ("대구디지털혁신진흥원(대구TP)", "https://daon.distep.re.kr/alert/announce"),
    ("인천테크노파크", "https://itp.or.kr/intro.asp?tmid=13"),
    ("세종테크노파크", "https://sjtp.or.kr/bbs/board.php?bo_table=business01"),
    ("충남테크노파크", "https://www.ctp.or.kr/business/data.do"),
    ("전남테크노파크", "https://data.jntp.or.kr/jntp/content/business/announcement/list.jsp"),
    ("경남테크노파크", "https://www.gntp.or.kr/biz/apply"),
    ("제주테크노파크", "https://www.jejutp.or.kr/board/business"),

    # ── 창조경제혁신센터 (통합 포털 + 주요 지역) ──
    ("창조경제혁신센터(통합)", "https://ccei.creativekorea.or.kr/"),
    ("서울창조경제혁신센터", "https://ccei.creativekorea.or.kr/seoul/"),
    ("부산창조경제혁신센터", "https://ccei.creativekorea.or.kr/busan/"),
    ("대구창조경제혁신센터", "https://ccei.creativekorea.or.kr/daegu/"),
    ("인천창조경제혁신센터", "https://ccei.creativekorea.or.kr/incheon/"),
    ("광주창조경제혁신센터", "https://ccei.creativekorea.or.kr/gwangju/"),
    ("대전창조경제혁신센터", "https://ccei.creativekorea.or.kr/daejeon/"),
    ("경기창조경제혁신센터", "https://ccei.creativekorea.or.kr/gyeonggi/"),
    ("강원창조경제혁신센터", "https://ccei.creativekorea.or.kr/gangwon/"),
    ("충북창조경제혁신센터", "https://ccei.creativekorea.or.kr/chungbuk/"),
    ("충남창조경제혁신센터", "https://ccei.creativekorea.or.kr/chungnam/"),
    ("전북창조경제혁신센터", "https://ccei.creativekorea.or.kr/jeonbuk/"),
    ("전남창조경제혁신센터", "https://ccei.creativekorea.or.kr/jeonnam/"),
    ("경북창조경제혁신센터", "https://ccei.creativekorea.or.kr/gyeongbuk/"),
    ("경남창조경제혁신센터", "https://ccei.creativekorea.or.kr/gyeongnam/"),
    ("제주창조경제혁신센터", "https://ccei.creativekorea.or.kr/jeju/"),

    # ── 경제진흥원 / 산업진흥원 ──
    ("서울경제진흥원(SBA) R&D공고", "https://seoul.rnbd.kr/client/c030100/c030100_00.jsp"),
    ("부산경제진흥원(BEPA)", "https://www.bepa.kr/kor/view.do?no=1508"),
    ("대전일자리경제진흥원", "https://www.djbea.or.kr/pms/an/an_0101/list"),
    ("경기도경제과학진흥원(GBSA)", "https://pms.gbsa.or.kr/info/pblanc/pblancList.do"),
    ("광주정보문화산업진흥원", "https://www.gicon.or.kr/board.es?mid=a10204000000&bid=0003"),

    # ── 전국 단위 진흥원/재단 ──
    ("한국콘텐츠진흥원(KOCCA)", "https://www.kocca.kr/kocca/pims/list.do?menuNo=204104"),
    ("정보통신산업진흥원(NIPA)", "https://www.nipa.kr/home/2-2"),
    ("한국디자인진흥원(KIDP)", "https://www.kidp.or.kr/?menuno=865"),
    ("한국산업기술진흥원(KIAT)", "https://kiat.or.kr/front/board/boardContentsListPage.do?board_id=90"),
    ("창업진흥원(KISED)", "https://www.kised.or.kr/menu.es?mid=a10302000000"),
    ("소상공인시장진흥공단(SEMAS)", "https://www.semas.or.kr/web/board/webBoardList.kmdc?bCd=10"),
    ("경기콘텐츠진흥원", "https://www.gcon.or.kr/gcon/business/gconNotice/list.do?menuNo=200061"),
    ("연구개발특구진흥재단", "https://www.innopolis.or.kr/board/view?menuId=MENU00319"),
    ("부산디자인진흥원", "https://dcb.or.kr/01_news/?mcode=0401010000&mode=1&hd=%EA%B3%B5%EA%B3%A0"),

    # ── 지역 창업/기업 지원센터 ──
    ("인천콘텐츠기업지원센터", "https://www.incc.or.kr/user/business/list.php"),
]


def seed():
    db_url = DATABASE_URL.replace(":6543/", ":5432/")
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    cursor = conn.cursor()

    inserted, skipped = 0, 0
    for source_name, url in REGIONAL_URLS:
        try:
            cursor.execute(
                """INSERT INTO admin_urls (url, source_name, is_active)
                   VALUES (%s, %s, 1)
                   ON CONFLICT (url) DO NOTHING""",
                (url, source_name),
            )
            if cursor.rowcount > 0:
                inserted += 1
                print(f"  [+] {source_name}")
            else:
                skipped += 1
                print(f"  [=] {source_name} (이미 등록됨)")
        except Exception as e:
            print(f"  [!] {source_name}: {e}")

    conn.close()
    print(f"\n완료: {inserted}건 신규 등록, {skipped}건 중복 스킵")


if __name__ == "__main__":
    seed()
