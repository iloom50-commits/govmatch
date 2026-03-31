"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import ResultCard from "@/components/ResultCard";
import { useToast } from "@/components/ui/Toast";

const API = process.env.NEXT_PUBLIC_API_URL;

interface Announcement {
  announcement_id: number;
  title: string;
  support_amount: string;
  match_score?: number;
  recommendation_reason: string;
  deadline_date?: string;
  summary_text?: string;
  region?: string;
  established_years_limit?: number;
  revenue_limit?: number;
  employee_limit?: number;
  origin_url?: string;
  url?: string;
  category?: string;
  department?: string;
  origin_source?: string;
  target_type?: string;
  eligibility_logic?: Record<string, unknown>;
}

function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { toast } = useToast();

  const q = searchParams.get("q") || "";
  const highlightId = searchParams.get("id") ? Number(searchParams.get("id")) : null;
  const utmSource = searchParams.get("utm_source") || "";

  const [query, setQuery] = useState(q);
  const [results, setResults] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [showLogin, setShowLogin] = useState(false);

  // UTM 추적
  useEffect(() => {
    if (utmSource === "blog" && typeof window !== "undefined" && (window as any).gtag) {
      (window as any).gtag("event", "blog_referral", {
        search_query: q,
        announcement_id: highlightId,
      });
    }
  }, [utmSource, q, highlightId]);

  // 검색 실행
  const doSearch = useCallback(async (keyword: string) => {
    if (!keyword.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/announcements/public?search=${encodeURIComponent(keyword)}&page=1&size=30`);
      const data = await res.json();
      const items: Announcement[] = data.data || data.items || [];
      setTotal(data.total || items.length);

      // id 파라미터가 있으면 해당 공고를 최상단으로
      if (highlightId) {
        const highlighted = items.find(a => a.announcement_id === highlightId);
        const rest = items.filter(a => a.announcement_id !== highlightId);
        if (highlighted) {
          setResults([highlighted, ...rest]);
        } else {
          // 검색 결과에 없으면 별도 조회
          try {
            const detailRes = await fetch(`${API}/api/announcements/${highlightId}/detail`);
            if (detailRes.ok) {
              const detail = await detailRes.json();
              const ann = detail.data || detail;
              setResults([ann, ...items]);
              setTotal((data.total || items.length) + 1);
            } else {
              setResults(items);
            }
          } catch {
            setResults(items);
          }
        }
      } else {
        setResults(items);
      }
    } catch {
      toast("검색 중 오류가 발생했습니다.", "error");
    }
    setLoading(false);
  }, [highlightId, toast]);

  // 초기 검색
  useEffect(() => {
    if (q) doSearch(q);
  }, [q, doSearch]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    router.push(`/search?q=${encodeURIComponent(query.trim())}`);
    doSearch(query.trim());
  };

  const handleLoginRequired = () => {
    setShowLogin(true);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* 헤더 */}
      <header className="sticky top-0 z-30 bg-white/90 backdrop-blur-md border-b border-slate-200/60 shadow-sm">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <a href="/" className="flex items-center gap-2 shrink-0">
            <span className="px-2 py-0.5 bg-indigo-600 text-white text-[11px] font-black rounded-md tracking-wider">지원금GO</span>
          </a>
          <form onSubmit={handleSearch} className="flex-1 flex items-center gap-2">
            <div className="flex-1 relative">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="지원금 검색 (예: 청년 주거, 출산 지원)"
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-700 placeholder-slate-400 outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300"
              />
            </div>
            <button type="submit" className="px-4 py-2.5 bg-indigo-600 text-white text-sm font-bold rounded-xl hover:bg-indigo-700 transition-all active:scale-95 shrink-0">
              검색
            </button>
          </form>
        </div>
      </header>

      {/* 검색 결과 */}
      <main className="max-w-4xl mx-auto px-4 py-6">
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="flex items-center gap-3">
              <div className="w-5 h-5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-slate-500 font-medium">검색 중...</p>
            </div>
          </div>
        ) : q && results.length > 0 ? (
          <>
            <p className="text-sm text-slate-500 mb-4">
              <span className="font-bold text-indigo-600">&quot;{q}&quot;</span> 검색 결과 <span className="font-bold text-indigo-600">{total}건</span>
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {results.map((res, idx) => (
                <div
                  key={res.announcement_id ?? idx}
                  className={highlightId && res.announcement_id === highlightId ? "ring-2 ring-indigo-500 ring-offset-2 rounded-xl" : ""}
                >
                  <ResultCard
                    res={res}
                    onLoginRequired={handleLoginRequired}
                  />
                </div>
              ))}
            </div>
          </>
        ) : q ? (
          <div className="text-center py-16">
            <p className="text-slate-400 text-sm mb-2">&quot;{q}&quot; 검색 결과가 없습니다</p>
            <p className="text-slate-300 text-xs">다른 키워드로 검색해보세요</p>
          </div>
        ) : (
          <div className="text-center py-16">
            <p className="text-slate-400 text-sm">검색어를 입력하세요</p>
          </div>
        )}

        {/* CTA: 앱 메인으로 유도 */}
        <div className="mt-8 p-5 bg-gradient-to-r from-indigo-50 to-violet-50 rounded-2xl border border-indigo-100 text-center">
          <p className="text-sm font-bold text-slate-800 mb-1">나에게 맞는 지원금, AI가 자동으로 찾아드립니다</p>
          <p className="text-xs text-slate-500 mb-3">회원가입하면 매일 맞춤 공고를 알려드려요</p>
          <a
            href="/"
            className="inline-block px-6 py-2.5 bg-indigo-600 text-white text-sm font-bold rounded-xl hover:bg-indigo-700 transition-all active:scale-95"
          >
            지원금GO 시작하기
          </a>
        </div>
      </main>

      {/* 로그인 모달 (간단 버전) */}
      {showLogin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowLogin(false)} />
          <div className="relative w-full max-w-sm bg-white rounded-2xl shadow-2xl p-6 text-center animate-in zoom-in-95 duration-300">
            <h3 className="text-lg font-bold text-slate-900 mb-2">로그인이 필요합니다</h3>
            <p className="text-sm text-slate-500 mb-4">공고 상세 정보를 확인하려면 로그인하세요</p>
            <a
              href="/"
              className="block w-full py-3 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all active:scale-[0.98] mb-2"
            >
              로그인 / 회원가입
            </a>
            <button onClick={() => setShowLogin(false)} className="w-full py-2 text-slate-400 text-xs font-medium hover:text-slate-600">
              닫기
            </button>
          </div>
        </div>
      )}

      {/* 푸터 */}
      <footer className="mt-12 border-t border-slate-200/60 bg-slate-50/80">
        <div className="max-w-4xl mx-auto px-4 py-6 text-center text-[11px] text-slate-400">
          <p>&copy; {new Date().getFullYear()} 밸류파인더. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-slate-400">로딩 중...</div>}>
      <SearchContent />
    </Suspense>
  );
}
