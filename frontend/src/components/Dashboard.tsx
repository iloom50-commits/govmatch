"use client";

import ResultCard from "./ResultCard";
import { useState, useMemo } from "react";
import NotificationModal from "./NotificationModal";

interface MatchItem {
    announcement_id: number;
    title: string;
    support_amount: string;
    deadline_date: string;
    match_score: number;
    recommendation_reason: string;
    summary_text: string;
    origin_url?: string;
    url?: string;
    category?: string;
    department?: string;
    origin_source?: string;
}

const TAB_GROUPS: { label: string; key: string; categories: string[] }[] = [
  { label: "전체", key: "all", categories: [] },
  { label: "창업지원", key: "startup", categories: ["Entrepreneurship", "Small Business/Startup"] },
  { label: "R&D/기술", key: "rnd", categories: ["R&D", "R&D/Digital"] },
  { label: "자금/융자", key: "loan", categories: ["Loan/Investment"] },
  { label: "경영/판로", key: "biz", categories: ["Marketing", "General Business Support", "SME Support", "General"] },
  { label: "특화산업", key: "special", categories: ["Food Industry"] },
];

type SortKey = "score" | "deadline";

export default function Dashboard({ matches, profile, onEditProfile, onLogout }: { matches: MatchItem[], profile: any, onEditProfile: () => void, onLogout: () => void }) {
  const [activeTab, setActiveTab] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [isNotifyOpen, setIsNotifyOpen] = useState(false);

  const filteredMatches = useMemo(() => {
    let result = [...matches];

    if (activeTab !== "all") {
      const group = TAB_GROUPS.find(t => t.key === activeTab);
      if (group) {
        result = result.filter(m => {
          const cat = (m.category || "").trim();
          return group.categories.some(gc =>
            cat.toLowerCase().includes(gc.toLowerCase())
          );
        });
      }
    }

    if (sortKey === "score") {
      result.sort((a, b) => b.match_score - a.match_score);
    } else if (sortKey === "deadline") {
      result.sort((a, b) => {
        if (!a.deadline_date) return 1;
        if (!b.deadline_date) return -1;
        return new Date(a.deadline_date).getTime() - new Date(b.deadline_date).getTime();
      });
    }

    return result;
  }, [matches, activeTab, sortKey]);

  const tabCounts = useMemo(() => {
    const counts: Record<string, number> = { all: matches.length };
    TAB_GROUPS.forEach(g => {
      if (g.key === "all") return;
      counts[g.key] = matches.filter(m => {
        const cat = (m.category || "").trim();
        return g.categories.some(gc => cat.toLowerCase().includes(gc.toLowerCase()));
      }).length;
    });
    return counts;
  }, [matches]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6 w-full max-w-[1280px] mx-auto animate-in fade-in slide-in-from-bottom-6 duration-700 px-4 md:px-0">
      
      <aside className="space-y-6">
        <div className="glass p-6 md:p-7 rounded-[2rem] space-y-8 shadow-xl lg:sticky lg:top-8 overflow-hidden group/sidebar border border-white/40">
          <div className="absolute -top-16 -right-16 w-32 h-32 bg-indigo-500/10 blur-[50px] rounded-full group-hover/sidebar:bg-indigo-500/15 transition-all duration-1000 pointer-events-none" />
          
          <div className="flex items-center gap-4 relative z-10">
            <div className="w-12 h-12 md:w-14 md:h-14 bg-slate-950 rounded-2xl flex-shrink-0 flex items-center justify-center text-2xl shadow-lg">🏢</div>
            <div className="min-w-0">
              <h1 className="text-xl md:text-2xl font-black text-slate-950 tracking-tight leading-tight mb-1">
                기업 <span className="text-indigo-600">분석</span>
              </h1>
              <div className="flex flex-wrap gap-1.5">
                <span className="px-2 py-0.5 bg-emerald-50 text-emerald-600 text-[9px] font-black rounded-full uppercase tracking-widest flex items-center gap-1 border border-emerald-100/50">
                  <span className="w-1 h-1 bg-emerald-500 rounded-full animate-pulse" /> 우수 중소기업
                </span>
                <span className="px-2 py-0.5 bg-slate-100/50 text-slate-600 text-[9px] font-black rounded-full uppercase tracking-widest border border-slate-200/50 truncate max-w-[120px]">
                  {profile?.company_name || "Company Name"}
                </span>
              </div>
            </div>
          </div>

          <div className="space-y-3 relative z-10">
            <div className="flex items-center justify-between px-1">
              <h4 className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em]">기업 프로필 데이터</h4>
              <div className="h-px bg-slate-100 flex-1 ml-3" />
            </div>
            <div className="grid grid-cols-1 gap-2">
              {[
                { label: "소재지", value: profile?.address_city || "전국", icon: "📍" },
                { label: "기업구조", value: profile?.employee_count_bracket || "5인 미만", icon: "👥" },
                { label: "매출규모", value: profile?.revenue_bracket || profile?.revenue || "1억 미만", icon: "📈" }
              ].map((item, i) => (
                <div key={i} className="flex items-center justify-between p-4 bg-white/40 hover:bg-white rounded-xl border border-white/50 shadow-sm transition-all duration-300 group/item">
                  <div className="flex items-center gap-3">
                    <span className="text-lg group-hover/item:scale-110 transition-transform">{item.icon}</span>
                    <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">{item.label}</span>
                  </div>
                  <span className="text-xs md:text-sm font-black text-slate-900">{item.value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-2 space-y-3 relative z-10">
            <button 
              onClick={onEditProfile}
              className="w-full py-4 bg-slate-950 text-white rounded-xl font-black flex items-center justify-center gap-2.5 hover:bg-indigo-600 transition-all shadow-lg active:scale-95 group relative overflow-hidden text-xs"
            >
              <span className="text-base group-hover:rotate-12 transition-transform">⚙️</span> 
              <span className="tracking-tight uppercase font-black">기업 정보 관리</span>
            </button>
          </div>
        </div>
      </aside>

      <main className="space-y-10 lg:pb-16">
        <header className="space-y-5">
          <div className="flex flex-col xl:flex-row xl:items-end justify-between gap-6 md:gap-7">
            <h2 className="text-2xl md:text-3xl lg:text-4xl font-black text-slate-950 tracking-tighter leading-tight whitespace-nowrap">
              AI 맞춤 <span className="text-indigo-600 italic">정부지원금 매칭</span>
            </h2>
          </div>

          {/* Tabs + Sort toggle */}
          <div className="flex items-center gap-2 bg-white/60 backdrop-blur-md p-1.5 rounded-xl border border-white/80 shadow-sm overflow-x-auto">
            {TAB_GROUPS.map((tab) => {
              const count = tabCounts[tab.key] || 0;
              if (tab.key !== "all" && count === 0) return null;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-[10px] font-black transition-all duration-300 whitespace-nowrap flex-shrink-0 ${
                    activeTab === tab.key
                      ? "bg-slate-950 text-white shadow-md"
                      : "text-slate-500 hover:bg-slate-50"
                  }`}
                >
                  {tab.label}
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-black ${
                    activeTab === tab.key
                      ? "bg-white/20 text-white/80"
                      : "bg-slate-100 text-slate-400"
                  }`}>
                    {count}
                  </span>
                </button>
              );
            })}

            <div className="ml-auto flex-shrink-0 h-6 w-px bg-slate-200" />

            <div className="flex items-center gap-1 flex-shrink-0">
              {([
                { key: "score" as SortKey, label: "적합도" },
                { key: "deadline" as SortKey, label: "마감임박" },
              ]).map((s) => (
                <button
                  key={s.key}
                  onClick={() => setSortKey(s.key)}
                  className={`px-3 py-1.5 rounded-lg text-[10px] font-black transition-all duration-300 whitespace-nowrap ${
                    sortKey === s.key
                      ? "bg-indigo-600 text-white shadow-sm"
                      : "text-slate-400 hover:bg-slate-50"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Result count */}
          <div className="flex items-center gap-2 px-1">
            <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full" />
            <span className="text-[10px] font-bold text-slate-500">
              총 <span className="text-indigo-600 font-black">{filteredMatches.length}</span>건 매칭
            </span>
          </div>
        </header>

        {filteredMatches.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 md:py-20 px-8 text-center bg-white/40 backdrop-blur-xl rounded-[2.5rem] border border-white/60 shadow-lg animate-in zoom-in duration-500 w-full">
            <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center text-3xl mb-6 animate-pulse">🔍</div>
            <h2 className="text-xl md:text-2xl font-black text-slate-900 mb-4">
              {matches.length === 0 ? "맞춤형 공고가 아직 없습니다" : "조건에 맞는 공고가 없습니다"}
            </h2>
            <p className="text-xs md:text-base text-slate-500 max-w-lg mx-auto mb-8 font-medium leading-relaxed">
              {matches.length === 0
                ? <>국가기관의 최신 공고 데이터를 실시간으로 분석하고 있습니다.<br className="hidden md:block" />잠시 후 다시 시도하시거나 알림 설정을 켜주세요.</>
                : "다른 카테고리 탭을 선택해 보세요."
              }
            </p>
            {matches.length === 0 ? (
              <button 
                onClick={() => setIsNotifyOpen(true)}
                className="px-8 py-3.5 bg-slate-950 text-white rounded-xl font-black hover:bg-indigo-600 transition-all shadow-lg active:scale-95 text-sm"
              >
                알림 받기 설정
              </button>
            ) : (
              <button 
                onClick={() => setActiveTab("all")}
                className="px-8 py-3.5 bg-slate-950 text-white rounded-xl font-black hover:bg-indigo-600 transition-all shadow-lg active:scale-95 text-sm"
              >
                전체 보기
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 md:gap-7">
            {filteredMatches.map((res, idx) => (
              <div 
                key={res.announcement_id ?? idx} 
                className={`${idx === 0 ? "sm:col-span-2" : ""} animate-in fade-in slide-in-from-bottom-6 duration-700`}
                style={{ animationDelay: `${idx * 80}ms` }}
              >
                <ResultCard res={res} isCompact={idx !== 0} />
              </div>
            ))}
          </div>
        )}

        {/* Global Action Section */}
        <section className="relative pt-6">
          <div className="glass-dark p-10 md:p-14 rounded-[3rem] text-center shadow-2xl relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-full h-full bg-[radial-gradient(circle_at_100%_0%,rgba(79,70,229,0.15),transparent)] opacity-60 pointer-events-none" />
            
            <div className="relative z-10 space-y-10">
              <div className="inline-flex items-center gap-2.5 px-4 py-1.5 bg-white/5 rounded-full border border-white/10">
                <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-ping" />
                <span className="text-[9px] font-black text-indigo-300 uppercase tracking-[0.2em]">정부지원 통합 검색 시스템</span>
              </div>
              
              <div className="space-y-4">
                <h3 className="text-2xl md:text-4xl font-black text-white tracking-tighter leading-tight">
                  더 많은 <span className="text-indigo-400">성장 기회</span>를 <br /> 실시간으로 확인하세요
                </h3>
                <p className="text-slate-400 text-xs md:text-base max-w-2xl mx-auto font-medium leading-relaxed">
                  본 서비스의 AI는 매시간 5,000개 이상의 정부 공고를 스캔하여 <br className="hidden md:block" /> 귀사가 놓치고 있는 최적의 사업을 찾아냅니다.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-3.5 pt-4">
                <button 
                  onClick={() => setIsNotifyOpen(true)}
                  className="w-full sm:w-auto px-8 py-4 bg-white text-slate-950 rounded-xl font-black shadow-lg hover:scale-105 transition-all text-xs md:text-sm"
                >
                  🔔 알림 설정
                </button>
                <button 
                  onClick={onEditProfile}
                  className="w-full sm:w-auto px-8 py-4 bg-white/5 text-white rounded-xl font-black border border-white/10 hover:bg-white/10 transition-all text-xs md:text-sm"
                >
                  기업 정보 수정
                </button>
              </div>
            </div>
          </div>
        </section>
      </main>

      <NotificationModal 
        isOpen={isNotifyOpen} 
        onClose={() => setIsNotifyOpen(false)}
        businessNumber={profile?.business_number}
        onSave={(newSettings) => {
          console.log("알림 설정 저장됨:", newSettings);
        }}
      />
    </div>
  );
}
