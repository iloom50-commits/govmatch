import { Metadata } from "next";
import { Suspense } from "react";
import TossWidget from "./TossWidget";

// PG 심사용 결제경로 확인 페이지 — 검색에 노출되면 안 된다.
export const metadata: Metadata = {
  title: "크레딧 충전",
  robots: { index: false, follow: false },
};

export default function TossPaymentPage() {
  // TossWidget 이 useSearchParams 로 결제 결과(paymentKey·orderId·amount)를 받는다.
  // App Router 는 Suspense 로 감싸지 않으면 빌드에서 프리렌더 오류를 낸다.
  return (
    <Suspense fallback={<main className="max-w-2xl mx-auto px-4 py-20 text-center text-sm text-slate-500">불러오는 중…</main>}>
      <TossWidget />
    </Suspense>
  );
}
