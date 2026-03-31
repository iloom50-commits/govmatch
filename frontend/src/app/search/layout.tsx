import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "지원금 검색 — 지원금GO",
  description: "정부 지원금, 보조금, 복지 혜택을 검색하세요. AI가 내 조건에 맞는 지원금을 자동으로 찾아드립니다.",
  openGraph: {
    title: "지원금 검색 — 지원금GO",
    description: "정부 지원금, 보조금, 복지 혜택을 검색하세요.",
  },
};

export default function SearchLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
