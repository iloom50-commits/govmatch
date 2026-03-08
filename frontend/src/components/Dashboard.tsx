"use client";

import ResultCard from "./ResultCard";
import { useState } from "react";
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
}

export default function Dashboard({ matches, profile, onEditProfile, onLogout }: { matches: MatchItem[], profile: any, onEditProfile: () => void, onLogout: () => void }) {
  const [activeTab, setActiveTab] = useState("all");
  const [isNotifyOpen, setIsNotifyOpen] = useState(false);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6 w-full max-w-[1280px] mx-auto animate-in fade-in slide-in-from-bottom-6 duration-700 px-4 md:px-0">
      
      {/* Refined Sidebar: Expert Density */}
      <aside className="space-y-6">
        <div className="glass p-6 md:p-7 rounded-[2rem] space-y-8 shadow-xl lg:sticky lg:top-8 overflow-hidden group/sidebar border border-white/40">
          {/* Subtle Glow */}
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

      {/* Results Content Area */}
      <main className="space-y-10 lg:pb-16">
        <header className="flex flex-col xl:flex-row xl:items-end justify-between gap-6 md:gap-7">
          <div className="space-y-2">
            <div className="flex items-center gap-2.5">
              <div className="h-px bg-indigo-200 w-8" />
              <p className="text-[9px] font-black text-indigo-600 uppercase tracking-[0.3em]">AI 지원금 추천 엔진</p>
            </div>
            <h2 className="text-2xl md:text-3xl lg:text-4xl font-black text-slate-950 tracking-tighter leading-tight whitespace-nowrap">
              맞춤형 <span className="text-indigo-600 italic">지원사업 매칭</span>
            </h2>
          </div>
          
          <div className="flex items-center gap-1.5 bg-white/60 backdrop-blur-md p-1 rounded-xl border border-white/80 shadow-sm self-start xl:self-auto">
            {["전체", "금융지원", "인력지원"].map((tab, idx) => (
              <button 
                key={idx}
                onClick={() => setActiveTab(tab === "전체" ? "all" : tab)}
                className={`px-4 py-1.5 rounded-lg text-[9px] font-black transition-all duration-500 ${activeTab === (tab === "전체" ? "all" : tab) ? "bg-slate-950 text-white shadow-md scale-105" : "text-slate-500 hover:bg-slate-50"}`}
              >
                {tab}
              </button>
            ))}
          </div>
        </header>

        {matches.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 md:py-20 px-8 text-center bg-white/40 backdrop-blur-xl rounded-[2.5rem] border border-white/60 shadow-lg animate-in zoom-in duration-500 w-full">
            <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center text-3xl mb-6 animate-pulse">🔍</div>
            <h2 className="text-xl md:text-2xl font-black text-slate-900 mb-4">맞춤형 공고가 아직 없습니다</h2>
            <p className="text-xs md:text-base text-slate-500 max-w-lg mx-auto mb-8 font-medium leading-relaxed">
              국가기관의 최신 공고 데이터를 실시간으로 분석하고 있습니다.<br className="hidden md:block" />잠시 후 다시 시도하시거나 알림 설정을 켜주세요.
            </p>
            <button 
              onClick={() => setIsNotifyOpen(true)}
              className="px-8 py-3.5 bg-slate-950 text-white rounded-xl font-black hover:bg-indigo-600 transition-all shadow-lg active:scale-95 text-sm"
            >
              알림 받기 설정
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 md:gap-7">
            {matches.map((res, idx) => (
              <div 
                key={idx} 
                className={`${idx === 0 ? "sm:col-span-2" : ""} animate-in fade-in slide-in-from-bottom-6 duration-700`}
                style={{ animationDelay: `${idx * 100}ms` }}
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
                  onClick={() => alert('내 기업에 꼭 필요한 사업이 있나요? 제안 주시면 빠르게 검토하겠습니다! 💡')}
                  className="w-full sm:w-auto px-8 py-4 bg-white text-slate-950 rounded-xl font-black shadow-lg hover:scale-105 transition-all text-xs md:text-sm"
                >
                  📍 지원사업 제안하기
                </button>
                <button 
                  onClick={() => alert('전문가 맞춤 컨설팅 서비스가 준비 중입니다. 🎯')}
                  className="w-full sm:w-auto px-8 py-4 bg-white/5 text-white rounded-xl font-black border border-white/10 hover:bg-white/10 transition-all text-xs md:text-sm"
                >
                  맞춤형 컨설팅 허브
                </button>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Notification Settings Modal */}
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
