import type { Metadata } from "next";
import ProPageClient from "./ProPageClient";

export const metadata: Metadata = {
  title: "GovMatch 전문상담툴",
  description: "전문가를 위한 정부지원사업 AI 상담 도구",
  robots: "noindex",
};

export default function ProPage() {
  return <ProPageClient />;
}
