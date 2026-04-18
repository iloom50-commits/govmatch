"""중소벤처기업부(mss.go.kr) 사업공고 크롤러.

중진공 + 소진공 사업이 모두 이 사이트에 공고되므로,
원본 기관 사이트 대신 여기서 직접 수집하면 정확한 공고문 확보 가능.

cbIdx=310 : 사업공고 게시판
"""

import os
import re
import json
import logging
import requests
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.mss.go.kr"
LIST_URL = f"{BASE_URL}/site/smba/ex/bbs/List.do"
VIEW_URL = f"{BASE_URL}/site/smba/ex/bbs/View.do"
DOWNLOAD_URL = f"{BASE_URL}/common/board/Download.do"
CB_IDX = "310"  # 사업공고 게시판

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"{LIST_URL}?cbIdx={CB_IDX}",
}


def fetch_announcement_list(page: int = 1) -> List[Dict[str, Any]]:
    """사업공고 목록 페이지에서 공고 bcIdx + 첨부파일 URL 추출.

    Returns: [{"bcIdx": "1067445", "downloads": [{"url": "...", "ext": "pdf"}, ...]}]
    """
    try:
        resp = requests.get(
            LIST_URL,
            params={"cbIdx": CB_IDX, "pageIndex": page},
            headers=_HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning(f"[MSS] List page {page} failed: {resp.status_code}")
            return []
    except Exception as e:
        logger.warning(f"[MSS] List fetch error: {e}")
        return []

    # bcIdx 추출 (Download URL에 포함)
    bc_ids = sorted(set(re.findall(r"bcIdx=(\d+)", resp.text)), reverse=True)

    # 각 bcIdx에 대한 첨부파일 URL 수집
    items = []
    for bc_id in bc_ids:
        download_pattern = re.compile(
            rf'href=["\'](/common/board/Download\.do\?bcIdx={bc_id}&[^"\']+)["\']'
        )
        raw_urls = download_pattern.findall(resp.text)
        # &amp; → & 치환 + 중복 제거
        seen = set()
        downloads = []
        for u in raw_urls:
            clean = u.replace("&amp;", "&")
            # streFileNm 기준 중복 제거
            file_nm = re.search(r"streFileNm=([^&]+)", clean)
            if file_nm and file_nm.group(1) not in seen:
                seen.add(file_nm.group(1))
                ext = "unknown"
                if ".pdf" in clean:
                    ext = "pdf"
                elif ".hwpx" in clean:
                    ext = "hwpx"
                elif ".hwp" in clean:
                    ext = "hwp"
                elif ".docx" in clean:
                    ext = "docx"
                downloads.append({"url": f"{BASE_URL}{clean}", "ext": ext})

        items.append({"bcIdx": bc_id, "downloads": downloads})

    logger.info(f"[MSS] Page {page}: {len(items)} announcements found")
    return items


def fetch_announcement_detail(bc_idx: str) -> Dict[str, Any]:
    """공고 상세 페이지에서 메타데이터 + 본문 + 첨부파일 추출.

    Returns: {
        "bcIdx": str,
        "title": str,
        "announcement_number": str,
        "apply_period": str,
        "department": str,
        "reg_date": str,
        "body_text": str,
        "body_html": str,
        "downloads": [{"url", "ext", "filename"}],
        "origin_url": str,
    }
    """
    url = f"{VIEW_URL}?cbIdx={CB_IDX}&bcIdx={bc_idx}"
    result = {
        "bcIdx": bc_idx,
        "origin_url": url,
        "title": "",
        "announcement_number": "",
        "apply_period": "",
        "department": "",
        "reg_date": "",
        "body_text": "",
        "body_html": "",
        "downloads": [],
    }

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code != 200:
            return result
    except Exception as e:
        logger.warning(f"[MSS] Detail fetch error: {e}")
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── 메타데이터 (table) ──
    table = soup.find("table")
    if table:
        ths = [th.get_text(strip=True) for th in table.find_all("th")]
        tds = [td.get_text(strip=True) for td in table.find_all("td")]
        meta = dict(zip(ths, tds))
        result["announcement_number"] = meta.get("공고번호", "")
        result["apply_period"] = meta.get("신청기간", "")
        result["department"] = meta.get("담당부서", "")
        result["reg_date"] = meta.get("등록일", "")

    # ── 본문 (view_contents) ──
    view_con = soup.find(class_="view_contents")
    if view_con:
        result["body_html"] = str(view_con)
        # HTML 태그 제거
        text = re.sub(r"<br\s*/?>", "\n", str(view_con))
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&#\d+;", " ", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        result["body_text"] = text.strip()

    # ── 제목 (h4 태그) ──
    h4 = soup.find("h4")
    if h4:
        result["title"] = h4.get_text(strip=True)[:200]

    # 제목이 아직 없으면 본문에서 추출
    if not result["title"] and result["body_text"]:
        lines = [l.strip() for l in result["body_text"].split("\n") if l.strip()]
        for i, line in enumerate(lines):
            if "공고" in line and ("호]" in line or "호)" in line):
                # 공고번호 줄 다음이 제목
                if i + 1 < len(lines):
                    candidate = lines[i + 1].strip()
                    if len(candidate) > 5:
                        result["title"] = candidate[:100]
                        break
        if not result["title"]:
            for line in lines:
                if len(line) > 15 and not line.startswith("["):
                    result["title"] = line[:100]
                    break

    # ── 첨부파일 ──
    for a in soup.find_all("a", href=re.compile(r"Download\.do")):
        href = a["href"].replace("&amp;", "&")
        filename = a.get_text(strip=True) or "첨부파일"
        ext = "unknown"
        ext_match = re.search(r"streFileNm=.*?\.(pdf|hwpx?|docx?)", href)
        if ext_match:
            ext = ext_match.group(1)
        full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
        result["downloads"].append({"url": full_url, "ext": ext, "filename": filename})

    return result


def download_file(url: str) -> tuple:
    """첨부파일 다운로드. Returns: (bytes, detected_type)"""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=30, allow_redirects=True)
        if resp.status_code != 200:
            return b"", "unknown"
        content = resp.content
        if content[:4] == b"%PDF":
            return content, "pdf"
        elif content[:8] == bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1]):
            return content, "hwp"
        elif content[:4] == bytes([0x50, 0x4B, 0x03, 0x04]):
            return content, "hwpx"
        return content, "unknown"
    except Exception as e:
        logger.warning(f"[MSS] Download error: {e}")
        return b"", "unknown"


def crawl_and_store(db_conn, max_pages: int = 3, max_items: int = 30) -> Dict[str, Any]:
    """중기부 사업공고를 크롤링하여 DB에 저장 + 분석 큐 등록.

    Returns: {"crawled": int, "new": int, "queued": int}
    """
    from app.services.doc_analysis_service import extract_text_from_bytes, analyze_and_store

    cur = db_conn.cursor()
    stats = {"crawled": 0, "new": 0, "queued": 0, "analyzed": 0}

    for page in range(1, max_pages + 1):
        items = fetch_announcement_list(page)
        if not items:
            break

        for item in items:
            if stats["crawled"] >= max_items:
                break
            stats["crawled"] += 1

            bc_idx = item["bcIdx"]

            # 이미 DB에 있는지 확인 (origin_url 기준)
            origin_url = f"{VIEW_URL}?cbIdx={CB_IDX}&bcIdx={bc_idx}"
            cur.execute(
                "SELECT announcement_id FROM announcements WHERE origin_url = %s",
                (origin_url,),
            )
            if cur.fetchone():
                continue

            # 상세 페이지 파싱
            detail = fetch_announcement_detail(bc_idx)
            if not detail["title"] and not detail["body_text"]:
                continue

            stats["new"] += 1
            title = detail["title"] or f"중기부 사업공고 {detail['announcement_number']}"

            # ── 첨부파일 텍스트 추출 ──
            full_text = detail["body_text"]
            for dl in detail.get("downloads", []):
                if dl["ext"] in ("pdf", "hwp", "hwpx"):
                    content, ftype = download_file(dl["url"])
                    if content:
                        extracted = extract_text_from_bytes(content, ftype, max_chars=50000)
                        if extracted and len(extracted) > 100:
                            full_text += f"\n\n[첨부: {dl.get('filename', '파일')}]\n{extracted}"

            # ── DB 저장 ──
            try:
                cur.execute("""
                    INSERT INTO announcements
                        (title, origin_url, department, summary_text, origin_source, target_type, region)
                    VALUES (%s, %s, %s, %s, 'mss-direct', 'business', '전국')
                    RETURNING announcement_id
                """, (
                    title[:200],
                    origin_url,
                    detail.get("department", "중소벤처기업부")[:60],
                    full_text[:5000],
                ))
                new_id = cur.fetchone()["announcement_id"]
                db_conn.commit()

                # 분석 실행
                if len(full_text) > 200:
                    try:
                        result = analyze_and_store(
                            announcement_id=new_id,
                            origin_url=origin_url,
                            title=title,
                            db_conn=db_conn,
                            summary_text=full_text[:10000],
                        )
                        if result.get("success"):
                            stats["analyzed"] += 1
                    except Exception as ae:
                        logger.warning(f"[MSS] Analysis error for {bc_idx}: {ae}")
                        # 분석 큐에 등록
                        try:
                            cur.execute("""
                                INSERT INTO analysis_failures
                                    (announcement_id, error_type, error_message, retry_count, next_retry_at)
                                VALUES (%s, 'pending_first_analysis', 'MSS crawl - analysis deferred', 0, CURRENT_TIMESTAMP)
                                ON CONFLICT DO NOTHING
                            """, (new_id,))
                            db_conn.commit()
                            stats["queued"] += 1
                        except Exception:
                            db_conn.rollback()

            except Exception as e:
                logger.warning(f"[MSS] DB save error for {bc_idx}: {e}")
                try:
                    db_conn.rollback()
                except Exception:
                    pass

    logger.info(f"[MSS] Done: crawled={stats['crawled']}, new={stats['new']}, analyzed={stats['analyzed']}, queued={stats['queued']}")
    return stats
