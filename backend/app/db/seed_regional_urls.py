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
    ("부산테크노파크", "https://www.btp.or.kr/kor/CMS/Board/Board.do?mCode=MN013"),
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

    # ── 누락 테크노파크 (9개 추가) ──
    ("서울테크노파크(STP)", "https://www.seoultp.or.kr/user/nd54882.do"),
    ("경기테크노파크", "https://www.gtp.or.kr/user/nd91800.do"),
    ("강원테크노파크", "https://www.gwtp.or.kr/bbs/board.php?bo_table=biz_notice"),
    ("충북테크노파크", "https://www.cbtp.or.kr/sub06/06_01.php"),
    ("전북테크노파크", "https://www.jbtp.or.kr/board/list.jbtp?boardId=BBS_0000006"),
    ("경북테크노파크", "https://www.gbtp.or.kr/board.es?mid=a10301000000&bid=0006"),
    ("광주테크노파크", "https://www.gjtp.or.kr/board/list.gjtp?boardId=BBS_0000002"),
    ("대전테크노파크", "https://www.djtp.or.kr/sub05/05_01.php"),
    ("울산테크노파크", "https://www.utp.or.kr/default/mp/index.do?mg_id=2c928de97f1a9b87017f1b0fb2ce0004"),

    # ── 누락 경제/산업진흥원 ──
    ("인천경제산업진흥원", "https://www.ifez.go.kr/"),
    ("울산경제진흥원", "https://www.ulsanbe.or.kr/"),
    ("세종창조경제혁신센터", "https://ccei.creativekorea.or.kr/sejong/"),
    ("충북경제진흥원", "https://www.cbepa.or.kr/"),
    ("강원경제진흥원", "https://www.gwepa.or.kr/"),
    ("전북경제통상진흥원", "https://www.jbba.kr/"),
    ("전남경제통상진흥원", "https://www.jnbe.or.kr/"),
    ("경북경제진흥원", "https://www.gbepa.or.kr/"),
    ("경남경제진흥원", "https://www.gnepa.or.kr/"),
    ("제주경제통상진흥원", "https://www.jejueco.or.kr/"),

    # ── 주요 시/군/구 (기초지자체) 지원사업 페이지 ──
    # 경기도
    ("수원시 기업지원", "https://www.suwon.go.kr/web/board/BD_board.list.do?bbsCd=1043"),
    ("성남시 기업지원", "https://www.seongnam.go.kr/city/1000052/30005/bbsList.do"),
    ("고양시 기업지원", "https://www.goyang.go.kr/www/www09/www0904/www090402.jsp"),
    ("용인시 기업지원", "https://www.yongin.go.kr/home/www/www09/www0904/www090402.jsp"),
    ("화성시 기업지원", "https://www.hscity.go.kr/www/selectBbsNttList.do?bbsNo=125"),
    ("안양시 기업지원", "https://www.anyang.go.kr/main/selectBbsNttList.do?bbsNo=612"),
    ("부천시 기업지원", "https://www.bucheon.go.kr/site/main/index006"),
    ("안산시 기업지원", "https://www.ansan.go.kr/www/selectBbsNttList.do?bbsNo=888"),
    ("평택시 기업지원", "https://www.pyeongtaek.go.kr/pyeongtaek/selectBbsNttList.do?bbsNo=91"),
    ("시흥시 기업지원", "https://www.siheung.go.kr/main/selectBbsNttList.do?bbsNo=223"),
    ("김포시 기업지원", "https://www.gimpo.go.kr/portal/selectBbsNttList.do?bbsNo=540"),
    ("파주시 기업지원", "https://www.paju.go.kr/user/board/BD_board.list.do?bbsCd=1061"),
    # 서울 주요구
    ("강남구 기업지원", "https://www.gangnam.go.kr/notice/list.do?mid=ID01_040102"),
    ("서초구 기업지원", "https://www.seocho.go.kr/site/seocho/ex/bbs/List.do?cbIdx=232"),
    ("마포구 기업지원", "https://www.mapo.go.kr/site/main/board/bidding/list"),
    ("영등포구 기업지원", "https://www.ydp.go.kr/www/selectBbsNttList.do?bbsNo=199"),
    ("성동구 기업지원", "https://www.sd.go.kr/main/selectBbsNttList.do?bbsNo=1195"),
    ("금천구 기업지원", "https://www.geumcheon.go.kr/portal/selectBbsNttList.do?bbsNo=1009"),
    # 부산 주요구
    ("해운대구 기업지원", "https://www.haeundae.go.kr/index.do"),
    ("사상구 기업지원", "https://www.sasang.go.kr/index.do"),
    # 대구
    ("달서구 기업지원", "https://www.dalseo.daegu.kr/"),
    ("북구(대구) 기업지원", "https://www.buk.daegu.kr/"),
    # 인천
    ("남동구 기업지원", "https://www.namdong.go.kr/main/selectBbsNttList.do?bbsNo=218"),
    ("연수구 기업지원", "https://www.yeonsu.go.kr/main/selectBbsNttList.do?bbsNo=299"),
    # 충남/충북
    ("천안시 기업지원", "https://www.cheonan.go.kr/prog/selectBbsNttList.do?bbsNo=125"),
    ("청주시 기업지원", "https://www.cheongju.go.kr/www/selectBbsNttList.do?bbsNo=335"),
    # 전북/전남
    ("전주시 기업지원", "https://www.jeonju.go.kr/index.9is?contentUid=9be517a74f8deed7014f90e21fc52aa1"),
    ("순천시 기업지원", "https://www.suncheon.go.kr/kr/selectBbsNttList.do?bbsNo=248"),
    # 경북/경남
    ("포항시 기업지원", "https://www.pohang.go.kr/pohang/selectBbsNttList.do?bbsNo=182"),
    ("창원시 기업지원", "https://www.changwon.go.kr/portal/selectBbsNttList.do?bbsNo=5"),
    ("김해시 기업지원", "https://www.gimhae.go.kr/main/selectBbsNttList.do?bbsNo=205"),

    # ── 전국 단위 추가 기관 ──
    ("한국산업단지공단(KICOX)", "https://www.kicox.or.kr/user/bbs/BD_selectBbsList.do?q_bbsCode=1034"),
    ("중소기업기술정보진흥원(TIPA)", "https://www.tipa.or.kr/biz/bizAnnounce.do"),
    ("한국무역보험공사(K-SURE)", "https://www.ksure.or.kr/"),
    ("한국벤처투자(KVIC)", "https://www.k-vic.co.kr/fund/fundAnc.do"),
    ("여성기업종합지원센터", "https://www.wbiz.or.kr/"),
    ("장애인기업종합지원센터", "https://www.debc.or.kr/"),
    ("사회적기업진흥원", "https://www.socialenterprise.or.kr/"),
    ("한국환경산업기술원(KEITI)", "https://www.keiti.re.kr/site/keiti/main.do"),
    ("에너지기술평가원(KETEP)", "https://www.ketep.re.kr/"),
    ("문화체육관광부 사업공고", "https://www.mcst.go.kr/kor/s_notice/press/pressView.jsp"),

    # ── 중앙부처 사업공고 ──
    ("환경부(기후에너지환경부)", "https://www.me.go.kr/home/web/board/list.do?boardMasterId=1&menuId=286"),
    ("농림축산식품부", "https://www.mafra.go.kr/home/5108/subview.do"),

    # ── 전국 단위 추가 기관 (2026-03-26 추가) ──
    ("한국연구재단(NRF)", "https://www.nrf.re.kr/biz/info/notice/list"),
    ("한국무역협회(KITA)", "https://www.kita.net/cmmrcInfo/cmmrcNews/busiNotice/busiNoticeList.do"),
    ("한국보건산업진흥원(KHIDI)", "https://www.khidi.or.kr/board?menuId=MENU01108"),
    ("한국발명진흥회(KIPA)", "https://www.kipa.org/kipa/ip003/kw_culture_0202.jsp"),
    ("KOTRA(대한무역투자진흥공사)", "https://www.kotra.or.kr/subList/20000020753/subhome/bizAply/"),
    ("한국농수산식품유통공사(aT)", "https://www.at.or.kr/"),
    ("한국표준협회(KSA)", "https://www.ksa.or.kr/ksa_kr/828/subview.do"),
    ("한국경영혁신중소기업협회(메인비즈)", "https://www.mainbiz.or.kr/usr/board/BBSMSTR_000000000053/list.do"),
    ("이노비즈협회", "https://www.innobiz.net/common/boardList.do?boardId=notice"),
    ("농업기술실용화재단", "https://www.fact.or.kr/bbs/board.php?bo_table=notice"),

    # ── 경제자유구역청 ──
    ("인천경제자유구역청(IFEZ)", "https://www.ifez.go.kr/ivt/main/contents.do?menuNo=500067"),
    ("부산진해경제자유구역청(BJFEZ)", "https://www.bjfez.go.kr/portal/bbs/B0000003/list.do"),
    ("광양만권경제자유구역청(GFEZ)", "https://www.gfez.go.kr/bbs/content/list.do?bCd=notice"),
    ("대구경북경제자유구역청(DGFEZ)", "https://www.dgfez.go.kr/bbs/boardList.do?menuCd=DOM_000000302001000000"),

    # ── 빠진 기초지자체 (인구 30만+) ──
    ("경기 남양주시 기업지원", "https://www.nyj.go.kr/main/1847/subview.do"),
    ("경기 광주시 기업지원", "https://www.gjcity.go.kr/portal/bbs/list.do?ptIdx=71"),
    ("경기 하남시 기업지원", "https://www.hanam.go.kr/www/selectBbsNttList.do?bbsNo=95"),
    ("서울 송파구 기업지원", "https://www.songpa.go.kr/www/contents/economy.do"),
    ("서울 노원구 기업지원", "https://www.nowon.kr/dong/bbs/BD_selectBbsList.do?q_bbsCode=1014"),
    ("서울 강서구 기업지원", "https://www.gangseo.seoul.kr/reserve/re010101"),
    ("서울 성북구 기업지원", "https://www.sb.go.kr/main/cop/bbs/selectBoardList.do?bbsId=B0000049"),
    ("인천 부평구 기업지원", "https://www.icbp.go.kr/open_content/ko/board/list.do?boardCd=BBS_0000003"),
    ("광주 북구 기업지원", "https://www.bukgu.gwangju.kr/board/list.do?boardId=BBS_0000025"),
    ("대전 유성구 기업지원", "https://www.yuseong.go.kr/kor/sub04_01_01.do"),
    ("제주시 기업지원", "https://www.jejusi.go.kr/news/notice.do"),

    # ── 대학 창업지원/산학협력 ──
    # 통합 포털
    ("BI-Net 창업보육센터네트워크", "https://www.smes.go.kr/binet/board/list.do"),
    ("LINC3.0 통합포털", "https://lincthree.nrf.re.kr/"),

    # 창업중심대학 11개교
    ("한양대 창업지원단", "https://startup.hanyang.ac.kr/"),
    ("성균관대 창업지원단", "https://skkustartup.kr/"),
    ("강원대 창업지원단", "https://ksef.kangwon.ac.kr/"),
    ("한남대 LINC3.0", "https://linc.hannam.ac.kr/"),
    ("호서대 LINC3.0", "https://linc.hoseo.ac.kr/"),
    ("충북대 창업지원단", "https://startup.chungbuk.ac.kr/"),
    ("대구대 창업지원단", "https://startup.daegu.ac.kr/"),
    ("경상국립대 창업지원단", "https://startup.gnu.ac.kr/"),
    ("부산대 창업지원단", "https://startup.pusan.ac.kr/"),
    ("전북대 창업지원단", "https://startup.jbnu.ac.kr/"),
    ("전남대 LINC3.0", "https://linc.jnu.ac.kr/"),

    # 주요 대학 창업지원센터
    ("서울대 창업지원센터", "https://startup.snu.ac.kr/"),
    ("KAIST 창업원", "https://tbic.kaist.ac.kr/"),
    ("연세대 창업지원센터", "https://venture.yonsei.ac.kr/"),
    ("고려대 창업지원센터", "https://kustartup.korea.ac.kr/"),
    ("POSTECH 창업지원센터", "https://startup.postech.ac.kr/"),
    ("서울과기대 창업지원센터", "https://sssf.seoultech.ac.kr/"),
    ("이화여대 창업지원센터", "https://startup.ewha.ac.kr/"),
    ("중앙대 창업지원센터", "http://changup1.cau.ac.kr/"),

    # ── SPA 사이트 (Playwright 필요) ──
    ("신용보증기금(KODIT)", "https://www.kodit.co.kr"),
    ("기술보증기금(KIBO)", "https://www.kibo.or.kr"),
    ("고용24(고용노동부)", "https://www.work24.go.kr"),
    ("HRD-Net(직업훈련)", "https://www.hrd.go.kr"),
    ("농촌진흥청", "https://www.rda.go.kr"),
    ("고용노동부 정책", "https://www.moel.go.kr"),
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
