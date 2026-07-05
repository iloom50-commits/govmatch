// 배포 버전 식별 엔드포인트 — stale 클라이언트 감지용.
// layout.tsx의 인라인 스크립트가 이 값을 주기적으로 폴링해, 자신이 로드된
// 빌드(VERCEL_GIT_COMMIT_SHA)와 다르면 "새 배포됨"으로 판단한다.
// 반드시 동적·무캐시로 응답해 현재 배포본의 SHA를 실시간 반환한다.
export const dynamic = "force-dynamic";

export function GET() {
  const version = process.env.VERCEL_GIT_COMMIT_SHA || "";
  return new Response(version, {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store, no-cache, must-revalidate",
    },
  });
}
