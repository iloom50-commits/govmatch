// 중진공(중소벤처기업진흥공단) 정책자금 융자 공고 판별 — 'AI 신청서 작성' 버튼 게이팅.
// SmartDoc 신청서 자동작성이 중진공 융자신청서 전용이므로 이 집합에만 노출한다.
// 조건: (부서~중진공 OR 제목="중소기업 정책자금") AND (제목에 자금 OR 융자) AND NOT 소상공인
export function isKosmePolicyLoan(a: { title?: string | null; department?: string | null }): boolean {
  const title = a.title || "";
  const dept = a.department || "";
  if (title.includes("소상공인")) return false; // 소진공 정책자금은 별개(양식 다름)
  const isKosme =
    dept.includes("중소벤처기업진흥공단") ||
    dept.includes("중소기업진흥공단") ||
    title.includes("중소기업 정책자금");
  const isLoan = title.includes("자금") || title.includes("융자");
  return isKosme && isLoan;
}
