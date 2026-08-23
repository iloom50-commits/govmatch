import { Metadata } from "next";
import TossWidget from "./TossWidget";

// PG 심사용 결제경로 확인 페이지 — 검색에 노출되면 안 된다.
export const metadata: Metadata = {
  title: "크레딧 충전",
  robots: { index: false, follow: false },
};

export default function TossPaymentPage() {
  return <TossWidget />;
}
