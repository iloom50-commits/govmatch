"""커버리지 갭 체크 — 매일 오케스트레이터가 호출.

coverage_targets 테이블 기준으로 각 기관의 최근 수집 현황을 확인하고
RED/YELLOW/GREEN 상태를 업데이트한다.
"""
from __future__ import annotations
import datetime
import math
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
    {"source_name": "부산경제진흥원(BEPA)",       "url": "https://www.bepa.kr/kor/view.do?no=1502",    "tier": 1, "scraper_name": "busan_bepa"},

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
            # tier3: announcements의 department 또는 origin_source로 조회
            cur.execute("""
                SELECT COUNT(*) as cnt, MAX(created_at) as last_dt
                FROM announcements
                WHERE (department LIKE %s OR origin_source LIKE %s)
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


# ══════════════════════════════════════════════════════════════════
# 자동 회귀감지 (self-maintaining watchlist) — announcements.origin_source 기반
# 하드코딩 목록(COVERAGE_MASTER)의 사각지대를 제거. 오케스트레이터 일일 스텝에서 호출.
# ══════════════════════════════════════════════════════════════════

MIN_ACTIVE_WEEKS  = 4     # 정규성 게이트: 90일 중 활동주 4개(≈월1회+) 이상이어야 자기교정 판정
YELLOW_MULT       = 1.5   # 평시 주기의 1.5배 침묵 → 주의
RED_MULT          = 3.0   # 평시 주기의 3배 침묵 → 회귀
YELLOW_FLOOR_DAYS = 7     # 7일 미만 침묵은 절대 경보 안 함(조기경보 레인이 담당)
RED_FLOOR_DAYS    = 14
DORMANT_DAYS      = 60    # 불규칙 소스: 60일 이상 무소식이면 휴면 주의
DORMANT_MIN_ITEMS = 3     # 1~2건은 테스트·일회성 가능성 → 제외


def _tier_from_prefix(origin_source: str) -> int:
    """origin_source 접두로 수집 채널 tier 추정. scraper:→1, admin-manual:→2, *-api→3, 그 외→0."""
    s = origin_source or ""
    if s.startswith("scraper:"):
        return 1
    if s.startswith("admin-manual:"):
        return 2
    if s.endswith("-api"):
        return 3
    return 0


def classify_source_row(row: dict) -> dict:
    """순수함수. 소스별 수집 통계 → 상태 판정.

    row: {origin_source, last_seen, total_items, active_weeks_90d, days_quiet}
    반환: {status: green|yellow|red|na, expected_gap_days: int|None, reason: str}
    """
    aw = int(row.get("active_weeks_90d") or 0)
    dq = float(row.get("days_quiet") or 0)
    total = int(row.get("total_items") or 0)
    gap = math.ceil(90 / aw) if aw > 0 else None

    # ① 정규 소스: 소스별 평시 주기 자기교정
    if aw >= MIN_ACTIVE_WEEKS:
        red_t = max(RED_MULT * gap, RED_FLOOR_DAYS)
        yellow_t = max(YELLOW_MULT * gap, YELLOW_FLOOR_DAYS)
        if dq >= red_t:
            return {"status": "red", "expected_gap_days": gap,
                    "reason": f"평시 ~{gap}일 주기의 3배({red_t:.0f}일) 넘게 신규 없음"}
        if dq >= yellow_t:
            return {"status": "yellow", "expected_gap_days": gap,
                    "reason": f"평시 ~{gap}일 주기의 1.5배({yellow_t:.0f}일) 넘게 신규 없음"}
        return {"status": "green", "expected_gap_days": gap, "reason": ""}

    # ② 불규칙 소스: 휴면 감지만 (오탐 비용 최소화)
    if total >= DORMANT_MIN_ITEMS and dq >= DORMANT_DAYS:
        return {"status": "yellow", "expected_gap_days": gap,
                "reason": f"불규칙 소스 {dq:.0f}일째 휴면"}
    return {"status": "na", "expected_gap_days": gap, "reason": "판정보류(수집 이력 부족)"}


def _early_warnings_from_rows(rows_24h: list) -> List[Dict[str, Any]]:
    """scraper_runs 기반 조기경보 — 진짜 실패 신호만(순수함수).

    rows_24h: [{source, runs, ok, err, saved_24h, found_24h, expired_24h}]  (직전 24h 집계)
    반환: [{level, source, msg}]

    ※ status=error 급증(≥3회)만 경보한다. "items_saved=0 연속"은 신규 공고가
      없는 정상 상태(월간 게시판 등)이므로 경보하지 않는다 — 소스 침묵은
      announcements 기반 자기교정 회귀감지(classify_source_row)가 정확히 담당.

    ※ 단, "found>0인데 saved=0이고 expired가 found를 거의 다 차지"는 다르다.
      공고를 찾았는데 전부 '마감'으로 스킵됐다는 뜻 — 등록일을 마감일로 오인한
      날짜 파싱 버그(BEPA류)의 증상이므로 경보한다. 정상 '신규 없음'은 이미 DB에
      있어(items_existing) expired가 낮으므로 구분된다.
    """
    alerts: List[Dict[str, Any]] = []
    for r in rows_24h or []:
        if (r.get("err") or 0) >= 3:
            alerts.append({"level": "critical", "source": r["source"],
                           "msg": f"24h 내 에러 {r['err']}회 — 스크래퍼 점검 필요"})
            continue
        found = r.get("found_24h") or 0
        saved = r.get("saved_24h") or 0
        expired = r.get("expired_24h") or 0
        if found > 0 and saved == 0 and expired >= max(3, found * 0.8):
            alerts.append({"level": "warning", "source": r["source"],
                           "msg": (f"24h 내 {found}건 발견했으나 전부 마감 처리(저장 0) "
                                   f"— 등록일을 마감일로 오인했을 가능성. 날짜 파싱 점검 필요")})
    return alerts


def _assemble_coverage(classified: list, muted_set: set) -> Dict[str, Any]:
    """순수함수. 분류된 소스 목록 + 뮤트셋 → 집계/경보 목록."""
    muted_set = muted_set or set()
    green = yellow = red = na = muted = 0
    red_list: list = []
    yellow_list: list = []
    for c in classified:
        src = c.get("origin_source")
        if src in muted_set:
            muted += 1
            continue
        st = c.get("status")
        entry = {"source": src, "days_quiet": c.get("days_quiet"),
                 "expected_gap_days": c.get("expected_gap_days"),
                 "last_seen": c.get("last_seen"), "reason": c.get("reason")}
        if st == "green":
            green += 1
        elif st == "yellow":
            yellow += 1
            yellow_list.append(entry)
        elif st == "red":
            red += 1
            red_list.append(entry)
        else:
            na += 1
    red_list.sort(key=lambda x: x["days_quiet"] or 0, reverse=True)
    yellow_list.sort(key=lambda x: x["days_quiet"] or 0, reverse=True)
    return {"total_sources": len(classified), "green": green, "yellow": yellow,
            "red": red, "na": na, "muted": muted,
            "red_list": red_list, "yellow_list": yellow_list}


# ── DB SQL: 소스별 요약 + last_seen 기준 90일 활동주 ──
_COVERAGE_SQL = """
WITH src AS (
    SELECT origin_source,
           MAX(created_at) AS last_seen,
           COUNT(*)        AS total_items
    FROM announcements
    WHERE origin_source IS NOT NULL AND origin_source <> ''
    GROUP BY origin_source
)
SELECT s.origin_source,
       s.last_seen,
       s.total_items,
       (SELECT COUNT(DISTINCT DATE_TRUNC('week', a.created_at))
          FROM announcements a
         WHERE a.origin_source = s.origin_source
           AND a.created_at >  s.last_seen - INTERVAL '90 days'
           AND a.created_at <= s.last_seen)                AS active_weeks_90d,
       EXTRACT(EPOCH FROM (NOW() - s.last_seen)) / 86400.0 AS days_quiet
FROM src s
ORDER BY days_quiet DESC
"""

_EARLY_24H_SQL = """
    SELECT source,
           COUNT(*) AS runs,
           COUNT(CASE WHEN status='ok' THEN 1 END) AS ok,
           COUNT(CASE WHEN status='error' THEN 1 END) AS err,
           SUM(items_saved) AS saved_24h,
           SUM(items_found) AS found_24h,
           SUM(COALESCE(items_expired, 0)) AS expired_24h
    FROM scraper_runs
    WHERE started_at > NOW() - INTERVAL '24 hours'
    GROUP BY source
"""

def _collect_early_warnings(conn) -> List[Dict[str, Any]]:
    """scraper_runs에서 조기경보 입력을 조회해 _early_warnings_from_rows 적용."""
    try:
        cur = conn.cursor()
        cur.execute(_EARLY_24H_SQL)
        rows_24h = [dict(r) for r in cur.fetchall()]
        return _early_warnings_from_rows(rows_24h)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return []


def check_source_coverage(conn) -> Dict[str, Any]:
    """일일 진입점(오케스트레이터 Step). origin_source 회귀감지 + 조기경보.

    반환: {checked_at, total_sources, green, yellow, red, na, muted,
           red_list[], yellow_list[], scraper_alerts[]}
    """
    cur = conn.cursor()
    cur.execute(_COVERAGE_SQL)
    raw_rows = [dict(r) for r in cur.fetchall()]

    # 뮤트 셋 (auto 소스 중 is_active=FALSE) — 컬럼 없으면 빈 셋
    muted_set: set = set()
    try:
        cur.execute("SELECT source_name FROM coverage_targets "
                    "WHERE detection = 'auto' AND is_active = FALSE")
        muted_set = {r["source_name"] for r in cur.fetchall()}
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    classified = []
    for raw in raw_rows:
        c = dict(raw)
        c.update(classify_source_row(raw))
        classified.append(c)

    result = _assemble_coverage(classified, muted_set)

    # 스냅샷 upsert (best-effort — 컬럼 미비/권한 문제 시 결과에 영향 없이 스킵)
    try:
        for c in classified:
            src = c["origin_source"]
            cur.execute("""
                INSERT INTO coverage_targets
                    (source_name, origin_source, tier, detection, status,
                     last_collected_at, last_count, active_weeks_90d,
                     expected_gap_days, days_quiet)
                VALUES (%(src)s, %(src)s, %(tier)s, 'auto', %(status)s,
                        %(last_seen)s, %(total)s, %(aw)s, %(gap)s, %(dq)s)
                ON CONFLICT (source_name) DO UPDATE SET
                    status = EXCLUDED.status,
                    last_collected_at = EXCLUDED.last_collected_at,
                    last_count = EXCLUDED.last_count,
                    active_weeks_90d = EXCLUDED.active_weeks_90d,
                    expected_gap_days = EXCLUDED.expected_gap_days,
                    days_quiet = EXCLUDED.days_quiet
            """, {"src": src, "tier": _tier_from_prefix(src), "status": c["status"],
                  "last_seen": c.get("last_seen"), "total": c.get("total_items"),
                  "aw": c.get("active_weeks_90d"), "gap": c.get("expected_gap_days"),
                  "dq": round(float(c.get("days_quiet") or 0), 1)})
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        result["persist_error"] = str(e)[:200]

    result["scraper_alerts"] = _collect_early_warnings(conn)
    result["checked_at"] = datetime.datetime.now().isoformat()
    return result
