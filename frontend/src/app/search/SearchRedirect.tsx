"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, Suspense } from "react";

function RedirectInner() {
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    const q = searchParams.get("q") || "";
    const id = searchParams.get("id") || "";
    const utm = searchParams.get("utm_source") || "";

    if (!q && !id) return;

    if (utm === "blog" && typeof window !== "undefined" && (window as any).gtag) {
      (window as any).gtag("event", "blog_referral", {
        search_query: q,
        announcement_id: id,
      });
    }

    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (id) params.set("id", id);
    router.replace(`/?${params.toString()}`);
  }, [searchParams, router]);

  const q = searchParams.get("q") || "";
  const id = searchParams.get("id") || "";
  if (!q && !id) return null;

  return (
    <div className="flex items-center gap-3 py-8">
      <div className="w-5 h-5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
      <p className="text-sm text-slate-500">검색 결과로 이동 중...</p>
    </div>
  );
}

export default function SearchRedirect() {
  return (
    <Suspense fallback={<div className="py-8 text-center text-slate-400 text-sm">로딩 중...</div>}>
      <RedirectInner />
    </Suspense>
  );
}
