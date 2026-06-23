"use client";
import { usePathname } from "next/navigation";

/**
 * /pro(전문가 페이지)에서는 소비자용 마케팅 랜딩을 숨긴다.
 * 그 외 경로에서는 children을 그대로 렌더(홈 SEO 콘텐츠 유지).
 */
export default function HideOnPro({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname && pathname.startsWith("/pro")) return null;
  return <>{children}</>;
}
