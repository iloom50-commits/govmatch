import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "지원금 공고 검색 — 지원금AI",
  description: "정부 지원금·보조금·정책자금 공고 17,000건 이상을 검색하세요. 소상공인 정책자금, 창업지원금, 청년지원금, R&D 과제, 복지바우처 등 AI가 내 조건에 맞는 지원사업을 찾아드립니다.",
  keywords: ["지원금검색", "정부지원금검색", "보조금검색", "소상공인지원금", "창업지원금", "청년지원금", "정책자금", "R&D지원사업", "복지바우처검색"],
  alternates: { canonical: "https://www.govmatch.kr/search" },
  openGraph: {
    title: "지원금 공고 검색 — 지원금AI",
    description: "정부 지원금·보조금·정책자금 공고 17,000건 이상 검색. 소상공인 정책자금, 창업지원금, 청년지원금 등 AI 자동 매칭.",
    url: "https://www.govmatch.kr/search",
  },
};

export default function SearchLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
