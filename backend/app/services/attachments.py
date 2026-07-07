"""공고 첨부(양식) 메타 수집 + 분류 — SmartDoc 연동용.

- discover_attachments(원본 페이지)로 첨부 URL 발견
- 각 첨부를 가볍게 probe(헤더 + 매직바이트)해 실제 파일명·mime·ext 확정
- kind 분류(신청서양식/사업계획서양식/공고문/붙임서식/기타)
- 결과 메타를 announcements.attachments(JSONB)에 캐시
실제 파일은 저장하지 않음 — url은 프록시 엔드포인트가 origin에서 통과 스트림.
"""
import json
import re
from urllib.parse import unquote

import requests

from app.services.doc_analysis_service import discover_attachments

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 매직바이트 → ext
_MAGIC = [
    (b"%PDF", "pdf"),
    (b"\xd0\xcf\x11\xe0", "hwp"),   # 구 한글(OLE) — .hwp / .doc / .xls 공통, 파일명으로 보정
    (b"PK\x03\x04", "zip"),         # hwpx/docx/xlsx/zip(OOXML) — 파일명으로 보정
]
_EXT_MIME = {
    "hwp": "application/x-hwp",
    "hwpx": "application/x-hwpx",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "zip": "application/zip",
    "": "application/octet-stream",
}


def _decode_filename(content_disposition: str) -> str:
    """Content-Disposition에서 파일명 추출 — RFC5987(filename*) 우선, 한글 인코딩(EUC-KR/UTF-8) 보정."""
    if not content_disposition:
        return ""
    # RFC5987: filename*=UTF-8''%EC%...
    m = re.search(r"filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)", content_disposition)
    if m:
        try:
            return unquote(m.group(1)).strip()
        except Exception:
            pass
    # filename="..."
    m = re.search(r'filename\s*=\s*"?([^";]+)"?', content_disposition)
    if not m:
        return ""
    raw = m.group(1).strip()
    # requests는 헤더를 latin-1로 디코드 → 원래 EUC-KR/UTF-8 바이트 복원 시도
    for enc in ("euc-kr", "utf-8"):
        try:
            fixed = raw.encode("latin-1").decode(enc)
            if not re.search(r"[�]", fixed):
                return fixed.strip()
        except Exception:
            continue
    return raw


def _ext_from(filename: str, magic_ext: str) -> str:
    """파일명 확장자 우선, 없으면 매직 기반. zip/ole는 파일명으로 hwpx/docx/xlsx 보정."""
    fn = (filename or "").lower()
    for e in ("hwpx", "hwp", "pdf", "docx", "xlsx", "zip"):
        if fn.endswith("." + e):
            return e
    if magic_ext == "zip":
        return "hwpx" if "hwpx" in fn else ("docx" if "docx" in fn else ("xlsx" if "xlsx" in fn else "zip"))
    if magic_ext == "hwp":
        return "hwp"
    return magic_ext or ""


_EDITABLE = ("hwp", "hwpx", "docx", "xlsx")


def _classify_kind(filename: str, ext: str = "") -> str:
    fn = filename or ""
    # 1) 파일명 키워드 우선
    if re.search(r"신청\s*서|신청\s*양식|지원\s*서|참가\s*신청", fn):
        return "신청서양식"
    if re.search(r"사업\s*계획", fn):
        return "사업계획서양식"
    if re.search(r"붙임|별지|서식", fn):
        return "붙임서식"
    if re.search(r"공고|공고문|안내", fn):
        return "공고문"
    # 2) 키워드 없으면 포맷 기반 — 편집문서·PDF 모두 작성 대상 양식으로 간주
    #    (SmartDoc이 PDF 신청서도 자동작성 → 키워드 없는 PDF도 신청서양식 후보. 2026-07-07 스펙)
    if ext in _EDITABLE or ext == "pdf":
        return "신청서양식"
    return "기타"


def _is_broken_filename(fn: str) -> bool:
    """원본 서버가 한글을 '?'/치환문자로 깨서 보낸 경우 감지."""
    if not fn or fn == "첨부파일":
        return True
    return ("?" in fn) or ("�" in fn)


def _probe(url: str, referer: str = "", title: str = "") -> dict | None:
    """첨부 1건 가볍게 probe — 헤더(파일명) + 매직바이트(ext). 실패 시 None.
    원본이 파일명을 깨서 보내면(title 기반 폴백) 깔끔한 이름 생성."""
    h = dict(_HEADERS)
    if referer:
        h["Referer"] = referer
    try:
        r = requests.get(url, headers=h, timeout=20, stream=True, allow_redirects=True)
        if r.status_code != 200:
            r.close()
            return None
        head = next(r.iter_content(8), b"")
        cd = r.headers.get("Content-Disposition", "")
        r.close()
    except Exception:
        return None
    magic_ext = next((e for sig, e in _MAGIC if head.startswith(sig)), "")
    if not magic_ext:
        return None  # 파일이 아님(HTML/차단 등)
    raw_fn = _decode_filename(cd)
    ext = _ext_from(raw_fn, magic_ext)
    if _is_broken_filename(raw_fn):
        base = re.sub(r'[\\/:*?"<>|]+', " ", (title or "첨부파일")).strip()[:60] or "첨부파일"
        filename = f"{base}.{ext}" if ext else base
    else:
        filename = raw_fn
        if "." not in filename and ext:
            filename = f"{filename}.{ext}"
    return {
        "kind": _classify_kind(filename, ext),
        "filename": filename,
        "mime_type": _EXT_MIME.get(ext, "application/octet-stream"),
        "origin_url": url,
    }


def build_attachments_meta(origin_url: str, title: str = "") -> list:
    """원본 페이지에서 첨부 메타 목록 생성 (파일은 저장 안 함)."""
    if not origin_url:
        return []
    metas = []
    for a in discover_attachments(origin_url):
        m = _probe(a.get("url", ""), referer=origin_url, title=title)
        if m:
            metas.append(m)
    return metas


def get_or_build(announcement_id: int, conn) -> list:
    """캐시된 attachments 반환, 없으면 origin에서 수집 후 캐시."""
    cur = conn.cursor()
    cur.execute("SELECT attachments, origin_url, title FROM announcements WHERE announcement_id=%s", (announcement_id,))
    row = cur.fetchone()
    if not row:
        return []
    cached = row["attachments"] if isinstance(row, dict) else row[0]
    if cached is not None:
        return cached if isinstance(cached, list) else json.loads(cached)
    origin = row["origin_url"] if isinstance(row, dict) else row[1]
    title = row["title"] if isinstance(row, dict) else row[2]
    metas = build_attachments_meta(origin or "", title or "")
    has_form = any(a.get("kind") == "신청서양식" for a in metas)
    cur.execute(
        "UPDATE announcements SET attachments=%s, has_application_form=%s WHERE announcement_id=%s",
        (json.dumps(metas, ensure_ascii=False), has_form, announcement_id),
    )
    conn.commit()
    return metas


def enrich_attachments(db_conn, limit: int = 150) -> dict:
    """미수집 기업공고의 첨부 메타 수집·분류 + 신청서양식 유무 기록 (일일 파이프라인 배치).

    - 대상: 유효 기업공고(business/both) + origin_url 있음 + attachments 미수집(NULL)
    - 각 공고: build_attachments_meta로 첨부 분류 → attachments + has_application_form 동시 기록
    - attachments IS NULL 조건이 재처리 방지(skip-done). 경량 크롤이라 limit 작게.
    Returns: {"scanned","with_form"}
    """
    cur = db_conn.cursor()
    cur.execute(
        """SELECT announcement_id AS id, origin_url, title
           FROM announcements
           WHERE is_archived = FALSE
             AND COALESCE(target_type, 'business') IN ('business', 'both')
             AND origin_url IS NOT NULL AND origin_url <> ''
             AND attachments IS NULL
           ORDER BY created_at DESC
           LIMIT %s""",
        (limit,),
    )
    rows = cur.fetchall()
    scanned = with_form = 0
    for r in rows:
        aid = r["id"] if isinstance(r, dict) else r[0]
        origin = (r["origin_url"] if isinstance(r, dict) else r[1]) or ""
        title = (r["title"] if isinstance(r, dict) else r[2]) or ""
        try:
            metas = build_attachments_meta(origin, title)
        except Exception:
            metas = []
        has_form = any(a.get("kind") == "신청서양식" for a in metas)
        cur.execute(
            "UPDATE announcements SET attachments=%s, has_application_form=%s WHERE announcement_id=%s",
            (json.dumps(metas, ensure_ascii=False), has_form, aid),
        )
        scanned += 1
        if has_form:
            with_form += 1
    db_conn.commit()
    return {"scanned": scanned, "with_form": with_form}
