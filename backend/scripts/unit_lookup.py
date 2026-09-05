# -*- coding: utf-8 -*-
"""중층 매물 → 호수 후보 좁히기 (1단계: 건축물대장 전유부).

무엇을 하나
  매물에 「○○동 · 중층 · 전용 84.9㎡」 까지만 적혀 있을 때, 건축물대장 전유부에서
  그 동의 호별 층·전용면적을 받아 (1) 중층 범위 (2) 면적 일치 로 후보 호수를 남긴다.
  호수를 하나로 확정하는 도구가 아니다 — 후보를 몇 개로 줄이는 도구다.

쓰는 법 (backend 에서, PUBLIC_DATA_PORTAL_KEY 필요)
  # 단지에 어떤 동이 있고 각 동이 몇 층·몇 라인·어떤 면적인지 본다
  python scripts/unit_lookup.py --sigungu 26350 --bjdong 10400 --bun 1200 --ji 0 --list

  # 특정 동 · 중층 · 면적으로 후보를 뽑는다
  python scripts/unit_lookup.py --sigungu 26350 --bjdong 10400 --bun 1200 --ji 0 \\
      --dong 101 --band 중층 --area 84.9

  # 한 번 받은 원본을 파일로 남겨 두면 다음부터 API 없이 돈다
  ... --cache centumpark.json          (있으면 읽고, 없으면 받아서 저장)

코드 찾는 법
  시군구코드(5자리)+법정동코드(5자리) = 법정동코드 10자리.
  도로명주소 사이트(dorojuso.kr) 주소 페이지 URL 앞 10자리가 그 값이다.
  예) 부산 해운대구 재송동 = 26350 + 10400

중층 기준
  네이버 부동산 관행: 총 층수를 삼등분해 아래 1/3 저층, 가운데 중층, 위 1/3 고층.
  올리는 중개사마다 경계가 다르므로 --slack 1 로 경계를 한 층씩 넓힐 수 있다.

주의
  · 이 스크립트는 「후보 목록」까지다. 확정은 교차 매물·전월세 실거래·등기부로 한다.
  · API 는 공공데이터포털 「건축HUB 건축물대장정보 서비스」 활용신청 후 쓸 수 있다.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

API = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrExposPubuseAreaInfo"
PAGE = 500
BANDS = ("저층", "중층", "고층")


# ─────────────────────────── 1. 받기 ───────────────────────────


def fetch_all(key: str, sigungu: str, bjdong: str, bun: str, ji: str) -> list[dict]:
    """전유공용면적 레코드를 페이지 끝까지 받는다. 호 하나에 전유·공용 행이 여러 개다."""
    items: list[dict] = []
    page = 1
    total = None
    while True:
        params = {
            "serviceKey": key,
            "sigunguCd": sigungu,
            "bjdongCd": bjdong,
            "bun": bun.zfill(4),
            "ji": ji.zfill(4),
            "numOfRows": PAGE,
            "pageNo": page,
            "_type": "json",
        }
        url = API + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = resp.read().decode("utf-8", "replace")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # 키 오류·활용신청 누락이면 JSON 이 아니라 XML 오류문이 온다
            sys.exit(f"[오류] JSON 이 아닌 응답 (키·활용신청 확인):\n{raw[:600]}")
        header = (data.get("response") or {}).get("header") or {}
        if str(header.get("resultCode")) not in ("00", "0"):
            sys.exit(f"[오류] API resultCode={header.get('resultCode')} {header.get('resultMsg')}")
        body = (data.get("response") or {}).get("body") or {}
        if total is None:
            total = int(body.get("totalCount") or 0)
        chunk = (body.get("items") or {}).get("item") or []
        if isinstance(chunk, dict):
            chunk = [chunk]
        items.extend(chunk)
        print(f"  page {page}: {len(chunk)}건 (누적 {len(items)}/{total})", file=sys.stderr)
        if not chunk or len(items) >= total:
            break
        page += 1
    return items


# ─────────────────────────── 2. 정리 ───────────────────────────


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ho_number(ho: str) -> int | None:
    """'1203호' → 1203. 숫자가 아니면 None."""
    digits = "".join(ch for ch in str(ho or "") if ch.isdigit())
    return int(digits) if digits else None


def build_units(items: list[dict]) -> dict[str, dict[str, dict]]:
    """{동명: {호명: {"floor": int, "area": float}}}. 전유·지상·주거 행만 합산한다."""
    units: dict[str, dict[str, dict]] = defaultdict(dict)
    for it in items:
        if "전유" not in str(it.get("exposPubuseGbCdNm") or ""):
            continue
        if "지하" in str(it.get("flrGbCdNm") or ""):
            continue
        ho = str(it.get("hoNm") or "").strip()
        if _ho_number(ho) is None:
            continue
        dong = str(it.get("dongNm") or "").strip() or "(동명 없음)"
        floor = int(_num(it.get("flrNo")) or 0)
        area = _num(it.get("area")) or 0.0
        u = units[dong].setdefault(ho, {"floor": floor, "area": 0.0})
        u["area"] = round(u["area"] + area, 2)
        u["floor"] = max(u["floor"], floor)
    return units


def band_range(top: int, band: str, slack: int = 0) -> tuple[int, int]:
    """삼등분. 15층이면 저층 1-5 · 중층 6-10 · 고층 11-15. slack 으로 경계를 넓힌다."""
    lo_cut = math.floor(top / 3)          # 저층 상한
    hi_cut = math.floor(top * 2 / 3)      # 중층 상한
    if band == "저층":
        lo, hi = 1, lo_cut
    elif band == "중층":
        lo, hi = lo_cut + 1, hi_cut
    else:
        lo, hi = hi_cut + 1, top
    return max(1, lo - slack), min(top, hi + slack)


def pick_dong(units: dict, wanted: str) -> str | None:
    """'101' 이 '101동' 에도 맞도록 숫자만 비교한다."""
    w = "".join(ch for ch in wanted if ch.isdigit()) or wanted
    for name in units:
        n = "".join(ch for ch in name if ch.isdigit()) or name
        if n == w:
            return name
    return None


def candidates(units: dict, dong: str, band: str, area: float | None,
               tol: float, slack: int) -> tuple[list[dict], dict]:
    """(후보 목록, 단계별 건수). 후보는 층 → 호 순으로 정렬한다."""
    hos = units[dong]
    top = max(u["floor"] for u in hos.values())
    lo, hi = band_range(top, band, slack)
    stage = {"동 전체": len(hos), "top": top, "range": (lo, hi)}
    in_band = {h: u for h, u in hos.items() if lo <= u["floor"] <= hi}
    stage[band] = len(in_band)
    if area is not None:
        matched = {h: u for h, u in in_band.items() if abs(u["area"] - area) <= tol}
        stage["면적 일치"] = len(matched)
    else:
        matched = in_band
    rows = [{"ho": h, "floor": u["floor"], "area": u["area"],
             "line": (_ho_number(h) or 0) % 100} for h, u in matched.items()]
    rows.sort(key=lambda r: (r["floor"], _ho_number(r["ho"]) or 0))
    return rows, stage


# ─────────────────────────── 3. 출력 ───────────────────────────


def print_list(units: dict) -> None:
    print(f"{'동':<10}{'호수':>6}{'층수':>6}{'라인':>6}  전용면적 종류(㎡)")
    for dong in sorted(units, key=lambda d: (_ho_number(d) or 0, d)):
        hos = units[dong]
        top = max(u["floor"] for u in hos.values())
        lines = {(_ho_number(h) or 0) % 100 for h in hos}
        areas = sorted({u["area"] for u in hos.values()})
        print(f"{dong:<10}{len(hos):>6}{top:>6}{len(lines):>6}  {', '.join(f'{a:g}' for a in areas)}")


def print_candidates(dong: str, rows: list[dict], stage: dict, band: str, area) -> None:
    lo, hi = stage["range"]
    print(f"\n{dong}  총 {stage['top']}층 → {band} = {lo}~{hi}층")
    print(f"  동 전체 {stage['동 전체']}호 → {band} {stage[band]}호", end="")
    if area is not None:
        print(f" → 전용 {area:g}㎡ 일치 {stage['면적 일치']}호", end="")
    print()
    if not rows:
        print("  후보 0건. --tol 을 키우거나 --slack 1 로 다시 시도.")
        return
    print(f"\n  {'호':<8}{'층':>4}{'라인':>5}{'전용㎡':>9}")
    for r in rows:
        print(f"  {r['ho']:<8}{r['floor']:>4}{r['line']:>5}{r['area']:>9.2f}")
    by_line = defaultdict(int)
    for r in rows:
        by_line[r["line"]] += 1
    print("\n  라인별: " + ", ".join(f"{ln:02d}라인 {n}호" for ln, n in sorted(by_line.items())))
    print(f"  후보 {len(rows)}건. 다음 단계: 교차 매물(층) · 전월세 실거래(층) · 향(라인) 으로 좁힌다.")


# ─────────────────────────── main ───────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sigungu", required=True, help="시군구코드 5자리 (예: 26350)")
    ap.add_argument("--bjdong", required=True, help="법정동코드 뒤 5자리 (예: 10400)")
    ap.add_argument("--bun", required=True, help="번지 본번 (예: 1200)")
    ap.add_argument("--ji", default="0", help="번지 부번 (기본 0)")
    ap.add_argument("--cache", help="원본 JSON 경로. 있으면 읽고 없으면 받아서 저장")
    ap.add_argument("--list", action="store_true", help="동별 층수·라인·면적 종류만 보고 끝낸다")
    ap.add_argument("--dong", help="동 (예: 101 또는 101동)")
    ap.add_argument("--band", default="중층", choices=BANDS)
    ap.add_argument("--area", type=float, help="매물 전용면적 ㎡ (예: 84.9)")
    ap.add_argument("--tol", type=float, default=0.5, help="면적 허용 오차 ㎡ (기본 0.5)")
    ap.add_argument("--slack", type=int, default=0, help="층 경계를 위아래로 넓힐 층 수 (기본 0)")
    a = ap.parse_args()

    items: list[dict] | None = None
    cache = Path(a.cache) if a.cache else None
    if cache and cache.exists():
        items = json.loads(cache.read_text(encoding="utf-8"))
        print(f"[캐시] {cache} {len(items)}건", file=sys.stderr)
    else:
        key = os.getenv("PUBLIC_DATA_PORTAL_KEY", "")
        if not key:
            sys.exit("[오류] PUBLIC_DATA_PORTAL_KEY 가 없다. .env 또는 환경변수로 넣는다.")
        print(f"[API] 전유공용면적 {a.sigungu}-{a.bjdong} {a.bun}-{a.ji}", file=sys.stderr)
        items = fetch_all(key, a.sigungu, a.bjdong, a.bun, a.ji)
        if cache:
            cache.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            print(f"[저장] {cache}", file=sys.stderr)

    units = build_units(items)
    if not units:
        sys.exit("[결과] 전유(주거) 레코드 0건. 지번·코드가 맞는지 확인한다.")

    if a.list or not a.dong:
        print_list(units)
        if not a.dong:
            print("\n--dong 과 --area 를 주면 후보를 뽑는다.")
        return

    dong = pick_dong(units, a.dong)
    if dong is None:
        sys.exit(f"[오류] '{a.dong}' 동이 없다. 있는 동: {', '.join(sorted(units))}")
    rows, stage = candidates(units, dong, a.band, a.area, a.tol, a.slack)
    print_candidates(dong, rows, stage, a.band, a.area)


if __name__ == "__main__":
    main()
