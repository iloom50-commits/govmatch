// 원본(외부) 링크 렌더 가드 — 유효한 http(s) URL만 통과(빈값이면 비링크).
// 깨진 값(#portalHome, manual:// 합성키, 공백, 스킴없음, 중복스킴)을 차단해
// 깨진 링크가 사용자에게 노출되지 않도록 한다. (상용 서비스 — 깨진 링크 노출 방지)
export function cleanExternalUrl(raw?: string | null): string {
  let u = (raw || "").trim();
  if (!u) return "";
  const m = [...u.matchAll(/https?:\/\//gi)];
  if (m.length >= 2) u = u.substring(m[m.length - 1].index || 0); // 중복 스킴 → 마지막 http부터
  if (!/^https?:\/\//i.test(u)) return "";        // http(s) 스킴 없음 (#portalHome 등)
  const rest = u.replace(/^https?:\/\//i, "");
  if (rest.includes("://")) return "";             // manual:// 등 가짜 스킴
  if (/\s/.test(u)) return "";                     // 공백 포함
  const host = rest.split(/[/?#]/)[0];
  if (!host.includes(".")) return "";              // 호스트에 점 없음(이상)
  return u;
}

// 여러 후보(final_url, origin_url 등) 중 첫 유효 URL 반환.
// 각 후보를 개별 검증하므로, final_url이 깨졌어도(#portalHome) 유효한 origin_url로 폴백한다.
export function bestExternalUrl(...candidates: (string | null | undefined)[]): string {
  for (const c of candidates) {
    const v = cleanExternalUrl(c);
    if (v) return v;
  }
  return "";
}
