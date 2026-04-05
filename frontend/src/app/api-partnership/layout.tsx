import { Metadata } from "next";

export const metadata: Metadata = {
  title: "API 제휴 — 지원금AI 데이터를 귀사 서비스에 연동하세요",
  description: "17,000+ 정부 지원금 공고 데이터 + AI 매칭 엔진을 RESTful API로 제공합니다. 핀테크, HR, ERP, 회계 등 다양한 서비스에 연동 가능.",
  alternates: { canonical: "https://govmatch.kr/api-partnership" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
