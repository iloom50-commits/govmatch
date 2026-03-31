"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, Suspense } from "react";

function SearchRedirect() {
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    const q = searchParams.get("q") || "";
    const id = searchParams.get("id") || "";
    const utm = searchParams.get("utm_source") || "";

    // GA4 UTM 추적
    if (utm === "blog" && typeof window !== "undefined" && (window as any).gtag) {
      (window as any).gtag("event", "blog_referral", {
        search_query: q,
        announcement_id: id,
      });
    }

    // 메인 페이지로 리다이렉트 (검색어 전달)
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (id) params.set("id", id);
    router.replace(`/?${params.toString()}`);
  }, [searchParams, router]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="flex items-center gap-3">
        <div className="w-5 h-5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-slate-500">검색 결과로 이동 중...</p>
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-slate-400">로딩 중...</div>}>
      <SearchRedirect />
    </Suspense>
  );
}
