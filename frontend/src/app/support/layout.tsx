import { Metadata } from "next";

export const metadata: Metadata = {
  title: "고객 상담 — 지원금AI",
  description: "지원금AI 고객 상담 센터. AI 챗봇으로 즉시 답변받거나 문의 폼을 통해 담당자에게 연락하세요.",
  alternates: { canonical: "https://govmatch.kr/support" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
