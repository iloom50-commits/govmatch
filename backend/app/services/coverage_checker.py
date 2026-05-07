"""커버리지 갭 체크 — 매일 오케스트레이터가 호출.

coverage_targets 테이블 기준으로 각 기관의 최근 수집 현황을 확인하고
RED/YELLOW/GREEN 상태를 업데이트한다.
"""
from __future__ import annotations
import datetime
from typing import List, Dict, Any


# ── 목표 기관 마스터 목록 ─────────────────────────────────────────
# (source_name, url, tier, scraper_name)
# tier 1 = 전용 스크래퍼, tier 2 = admin_urls 일반, tier 3 = API
COVERAGE_MASTER: List[Dict[str, Any]] = [
    # ── Tier 1: 전용 스크래퍼 ──
    {"source_name": "창조경제혁신센터(서울)",    "url": "https://ccei.creativekorea.or.kr/seoul/",    "tier": 1, "scraper_name": "ccei_seoul"},
    {"source_name": "창조경제혁신센터(부산)",    "url": "https://ccei.creativekorea.or.kr/busan/",    "tier": 1, "scraper_name": "ccei_busan"},
    {"source_name": "창조경제혁신센터(대구)",    "url": "https://ccei.creativekorea.or.kr/daegu/",    "tier": 1, "scraper_name": "ccei_daegu"},
    {"source_name": "창조경제혁신센터(인천)",    "url": "https://ccei.creativekorea.or.kr/incheon/",  "tier": 1, "scraper_name": "ccei_incheon"},
    {"source_name": "창조경제혁신센터(광주)",    "url": "https://ccei.creativekorea.or.kr/gwangju/",  "tier": 1, "scraper_name": "ccei_gwangju"},
    {"source_name": "창조경제혁신센터(대전)",    "url": "https://ccei.creativekorea.or.kr/daejeon/",  "tier": 1, "scraper_name": "ccei_daejeon"},
    {"source_name": "창조경제혁신센터(경기)",    "url": "https://ccei.creativekorea.or.kr/gyeonggi/", "tier": 1, "scraper_name": "ccei_gyeonggi"},
    {"source_name": "창조경제혁신센터(강원)",    "url": "https://ccei.creativekorea.or.kr/gangwon/",  "tier": 1, "scraper_name": "ccei_gangwon"},
    {"source_name": "창조경제혁신센터(충북)",    "url": "https://ccei.creativekorea.or.kr/chungbuk/", "tier": 1, "scraper_name": "ccei_chungbuk"},
    {"source_name": "창조경제혁신센터(충남)",    "url": "https://ccei.creativekorea.or.kr/chungnam/", "tier": 1, "scraper_name": "ccei_chungnam"},
    {"source_name": "창조경제혁신센터(전북)",    "url": "https://ccei.creativekorea.or.kr/jeonbuk/",  "tier": 1, "scraper_name": "ccei_jeonbuk"},
    {"source_name": "창조경제혁신센터(전남)",    "url": "https://ccei.creativekorea.or.kr/jeonnam/",  "tier": 1, "scraper_name": "ccei_jeonnam"},
    {"source_name": "창조경제혁신센터(경북)",    "url": "https://ccei.creativekorea.or.kr/gyeongbuk/","tier": 1, "scraper_name": "ccei_gyeongbuk"},
    {"source_name": "창조경제혁신센터(경남)",    "url": "https://ccei.creativekorea.or.kr/gyeongnam/","tier": 1, "scraper_name": "ccei_gyeongnam"},
    {"source_name": "창조경제혁신센터(제주)",    "url": "https://ccei.creativekorea.or.kr/jeju/",     "tier": 1, "scraper_name": "ccei_jeju"},
    {"source_name": "경남테크노파크",             "url": "https://www.gntp.or.kr/biz/apply",           "tier": 1, "scraper_name": "gntp"},

    # ── Tier 3: API 연동 ──
    {"source_name": "기업마당(bizinfo)",  "url": None, "tier": 3, "scraper_name": "bizinfo_api"},
    {"source_name": "소상공인진흥공단",   "url": None, "tier": 3, "scraper_name": "semas_api"},
    {"source_name": "중소기업24",         "url": None, "tier": 3, "scraper_name": "smes24_api"},

    # ── Tier 2: admin_urls ──
    {"source_name": "부산테크노파크",     "url": "https://www.btp.or.kr/kor/CMS/Board/Board.do?mCode=MN013", "tier": 2, "scraper_name": None},
    {"source_name": "인천테크노파크",     "url": "https://itp.or.kr/intro.asp?tmid=13",                      "tier": 2, "scraper_name": None},
    {"source_name": "충남테크노파크",     "url": "https://www.ctp.or.kr/business/data.do",                   "tier": 2, "scraper_name": None},
    {"source_name": "전남테크노파크",     "url": "https://data.jntp.or.kr/jntp/content/business/announcement/list.jsp", "tier": 2, "scraper_name": None},
    {"source_name": "제주테크노파크",     "url": "https://www.jejutp.or.kr/board/business",                  "tier": 2, "scraper_name": None},
    {"source_name": "서울테크노파크",     "url": "https://www.seoultp.or.kr/user/nd54882.do",                "tier": 2, "scraper_name": None},
    {"source_name": "경기테크노파크",     "url": "https://www.gtp.or.kr/user/nd91800.do",                    "tier": 2, "scraper_name": None},
    {"source_name": "강원테크노파크",     "url": "https://www.gwtp.or.kr/bbs/board.php?bo_table=biz_notice", "tier": 2, "scraper_name": None},
    {"source_name": "충북테크노파크",     "url": "https://www.cbtp.or.kr/sub06/06_01.php",                   "tier": 2, "scraper_name": None},
    {"source_name": "전북테크노파크",     "url": "https://www.jbtp.or.kr/board/list.jbtp?boardId=BBS_0000006","tier": 2, "scraper_name": None},
    {"source_name": "경북테크노파크",     "url": "https://www.gbtp.or.kr/board.es?mid=a10301000000&bid=0006", "tier": 2, "scraper_name": None},
    {"source_name": "광주테크노파크",     "url": "https://www.gjtp.or.kr/board/list.gjtp?boardId=BBS_0000002","tier": 2, "scraper_name": None},
    {"source_name": "대전테크노파크",     "url": "https://www.djtp.or.kr/sub05/05_01.php",                   "tier": 2, "scraper_name": None},
    {"source_name": "울산테크노파크",     "url": "https://www.utp.or.kr/default/mp/index.do?mg_id=2c928de97f1a9b87017f1b0fb2ce0004", "tier": 2, "scraper_name": None},
    {"source_name": "한국콘텐츠진흥원",   "url": "https://www.kocca.kr/kocca/pims/list.do?menuNo=204104",    "tier": 2, "scraper_name": None},
    {"source_name": "정보통신산업진흥원", "url": "https://www.nipa.kr/home/2-2",                              "tier": 2, "scraper_name": None},
    {"source_name": "창업진흥원",         "url": "https://www.kised.or.kr/menu.es?mid=a10302000000",          "tier": 2, "scraper_name": None},
    {"source_name": "KOTRA",              "url": "https://www.kotra.or.kr/subList/20000020753/subhome/bizAply/", "tier": 2, "scraper_name": None},
    {"source_name": "경기도경제과학진흥원","url": "https://pms.gbsa.or.kr/info/pblanc/pblancList.do",         "tier": 2, "scraper_name": None},
]

RED_DAYS = 7    # 7일 이상 수집 0건 → RED
YELLOW_DAYS = 3  # 3일 이상 수집 0건 → YELLOW


def seed_coverage_targets(conn) -> Dict[str, int]:
    """COVERAGE_MASTER를 coverage_targets 테이블에 upsert."""
    cur = conn.cursor()
    inserted, skipped = 0, 0
    for t in COVERAGE_MASTER:
        cur.execute("""
            INSERT INTO coverage_targets (source_name, url, tier, scraper_name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (source_name) DO NOTHING
        """, (t["source_name"], t.get("url"), t["tier"], t.get("scraper_name")))
        if cur.rowcount > 0:
            inserted += 1
        else:
            skipped += 1
    conn.commit()
    return {"inserted": inserted, "skipped": skipped}


def run_coverage_check(conn) -> Dict[str, Any]:
    """각 coverage_targets의 최근 수집 현황 업데이트 및 갭 리포트 반환."""
    cur = conn.cursor()
    now = datetime.datetime.now()

    cur.execute("SELECT id, source_name, url, tier, scraper_name FROM coverage_targets WHERE is_active = TRUE")
    targets = cur.fetchall()

    red, yellow, green, unknown = [], [], [], []

    for t in targets:
        name = t["source_name"]
        tier = t["tier"]
        scraper = t.get("scraper_name")

        # 수집 건수 조회: tier1/2는 origin_url 또는 department로, tier3는 source로
        count = 0
        last_dt = None

        if tier == 1 and scraper:
            # tier1: scraper_runs 테이블에서 마지막 실행 확인
            cur.execute("""
                SELECT MAX(started_at) as last_run, SUM(items_saved) as total
                FROM scraper_runs
                WHERE source = %s AND started_at > NOW() - INTERVAL '7 days'
            """, (scraper,))
            row = cur.fetchone()
            if row and row["total"]:
                count = int(row["total"])
                last_dt = row["last_run"]
        elif tier == 2 and t.get("url"):
            # tier2: announcements 테이블에서 origin_url prefix로 조회
            from urllib.parse import urlparse
            domain = urlparse(t["url"]).netloc
            cur.execute("""
                SELECT COUNT(*) as cnt, MAX(created_at) as last_dt
                FROM announcements
                WHERE origin_url LIKE %s AND created_at > NOW() - INTERVAL '7 days'
            """, (f"%{domain}%",))
            row = cur.fetchone()
            if row:
                count = int(row["cnt"] or 0)
                last_dt = row["last_dt"]
        elif tier == 3:
            # tier3: announcements의 department 또는 source로 조회
            cur.execute("""
                SELECT COUNT(*) as cnt, MAX(created_at) as last_dt
                FROM announcements
                WHERE (department LIKE %s OR source LIKE %s)
                  AND created_at > NOW() - INTERVAL '7 days'
            """, (f"%{name[:8]}%", f"%{name[:8]}%"))
            row = cur.fetchone()
            if row:
                count = int(row["cnt"] or 0)
                last_dt = row["last_dt"]

        # 상태 판정
        if last_dt is None or count == 0:
            days_since = (now - last_dt).days if last_dt else 999
            if days_since >= RED_DAYS:
                status = "red"
                red.append(name)
            else:
                status = "yellow"
                yellow.append(name)
        else:
            status = "green"
            green.append(name)

        cur.execute("""
            UPDATE coverage_targets
            SET last_collected_at = %s, last_count = %s, status = %s
            WHERE source_name = %s
        """, (last_dt, count, status, name))

    conn.commit()

    return {
        "green": len(green),
        "yellow": len(yellow),
        "red": len(red),
        "red_list": red,
        "yellow_list": yellow,
        "total": len(targets),
        "checked_at": now.isoformat(),
    }
