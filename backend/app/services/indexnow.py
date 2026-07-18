# -*- coding: utf-8 -*-
"""IndexNow 자동 색인 요청.

새 공고 URL을 네이버·빙 등 IndexNow 참여 검색엔진에 즉시 통지한다. 수동 수집요청
(하루 ~50개 제한) 부담을 없애고 색인을 수 분~수 시간으로 앞당긴다.
네이버 엔드포인트: https://searchadvisor.naver.com/indexnow (POST urlList 지원, 타 엔진과 공유)
"""
import json as _json
import logging
import urllib.request

logger = logging.getLogger(__name__)

# IndexNow 키 (8~128자, 영숫자·대시). 프론트 public/{KEY}.txt 파일과 반드시 동일.
INDEXNOW_KEY = "a7f3c9e2b8d14650a9e7c3f18b2d6e04"
HOST = "www.govmatch.kr"
KEY_LOCATION = f"https://{HOST}/{INDEXNOW_KEY}.txt"

# 네이버 + 중립 엔드포인트(참여 엔진 전체로 전파). 개별 실패는 격리.
ENDPOINTS = [
    "https://searchadvisor.naver.com/indexnow",
    "https://api.indexnow.org/indexnow",
]

_MAX_URLS = 10000  # IndexNow 1회 상한


def prepare_urls(urls):
    """공백/None 제거 + 순서 보존 중복 제거 + 상한 적용."""
    seen = set()
    out = []
    for u in urls or []:
        if not u or not str(u).strip():
            continue
        u = str(u).strip()
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= _MAX_URLS:
            break
    return out


def build_payload(urls):
    """IndexNow POST 본문(dict) 생성."""
    return {
        "host": HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls,
    }


def submit_urls(urls):
    """URL 목록을 IndexNow 엔드포인트들에 POST. 반환: 제출 건수 + 엔드포인트별 상태."""
    prepared = prepare_urls(urls)
    if not prepared:
        return {"submitted": 0, "endpoints": {}}
    body = _json.dumps(build_payload(prepared)).encode("utf-8")
    results = {}
    for ep in ENDPOINTS:
        try:
            req = urllib.request.Request(
                ep, data=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                results[ep] = r.status
        except Exception as e:  # 색인 통지 실패가 파이프라인을 막지 않도록 격리
            results[ep] = f"error: {str(e)[:120]}"
            logger.warning(f"[IndexNow] {ep} 실패: {e}")
    logger.info(f"[IndexNow] {len(prepared)}건 제출: {results}")
    return {"submitted": len(prepared), "endpoints": results}
