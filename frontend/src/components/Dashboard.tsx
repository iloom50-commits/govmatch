"use client";

import ResultCard from "./ResultCard";
import { useState, useMemo, useCallback, useEffect } from "react";
import NotificationModal from "./NotificationModal";
import { useToast } from "@/components/ui/Toast";

const REVENUE_KR: Record<string, string> = {
  UNDER_1B: "1억 미만",
  "1B_5B": "1억~5억",
  "5B_10B": "5억~10억",
  "10B_50B": "10억~50억",
  "50B_PLUS": "50억 이상",
  "1억 미만": "1억 미만",
  "1억~5억": "1억~5억",
  "1ìµ~5ìµ": "1억~5억",
  "5억~10억": "5억~10억",
};

const EMPLOYEE_KR: Record<string, string> = {
  UNDER_5: "5인 미만",
  UNDER_10: "10인 미만",
  "5_10": "5~10인",
  "10_50": "10~50인",
  "50_100": "50~100인",
  "100_PLUS": "100인 이상",
  "5인 미만": "5인 미만",
  "5인~10인": "5~10인",
  "5ì¸~10ì¸": "5~10인",
};

interface MatchItem {
    announcement_id: number;
    title: string;
    support_amount: string;
    deadline_date: string;
    match_score?: number;
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
  { label: "소상공인", key: "small_biz", categories: ["Small Business/Startup", "SME Support", "General Business Support", "General", "Food Industry"] },
  { label: "창업지원", key: "startup", categories: ["Entrepreneurship", "Small Business/Startup"] },
  { label: "R&D/기술", key: "rnd", categories: ["R&D", "R&D/Digital"] },
  { label: "자금/융자", key: "loan", categories: ["Loan/Investment"] },
  { label: "경영/판로", key: "biz", categories: ["Marketing", "General Business Support"] },
];

type SortKey = "latest" | "deadline";

const API = process.env.NEXT_PUBLIC_API_URL;

interface SavedItem {
  id: number;
  announcement_id: number;
  title: string;
  deadline_date: string | null;
  origin_url: string | null;
}

interface PlanStatus {
  plan: string;
  active: boolean;
  days_left: number | null;
  label: string;
}

export default function Dashboard({ matches, profile, onEditProfile, onLogout, planStatus, onUpgrade }: { matches: MatchItem[], profile: any, onEditProfile: () => void, onLogout: () => void, planStatus?: PlanStatus | null, onUpgrade?: () => void }) {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("latest");
  const [isNotifyOpen, setIsNotifyOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [savedItems, setSavedItems] = useState<SavedItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const bn = profile?.business_number || "";
  const [industryDisplayName, setIndustryDisplayName] = useState<string>("");

  useEffect(() => {
    const code = profile?.industry_code;
    const name = profile?.industry_name;
    if (name) { setIndustryDisplayName(name); return; }
    if (!code || code === "00000") return;
    fetch(`${API}/api/industry-recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company_name: "", business_content: code }),
    })
      .then(r => r.json())
      .then(result => {
        if (result.status === "SUCCESS" && result.data.candidates) {
          const match = result.data.candidates.find((c: any) => c.code === code);
          if (match) setIndustryDisplayName(match.name);
          else if (result.data.candidates.length > 0) setIndustryDisplayName(result.data.candidates[0].name);
        }
      })
      .catch(() => {});
  }, [profile?.industry_code, profile?.industry_name]);

  const fetchSaved = useCallback(async () => {
    if (!bn) return;
    try {
      const res = await fetch(`${API}/api/saved/${bn}`);
      const data = await res.json();
      if (data.status === "SUCCESS") setSavedItems(data.data);
    } catch { /* silent */ }
  }, [bn]);

  useEffect(() => { fetchSaved(); }, [fetchSaved]);

  // 사이드바 열릴 때 body 스크롤 잠금
  useEffect(() => {
    if (sidebarOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [sidebarOpen]);

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleBulkSave = async () => {
    if (!bn || selectedIds.size === 0) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/saved/bulk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ business_number: bn, announcement_ids: Array.from(selectedIds) }),
      });
      const data = await res.json();
      if (data.status === "SUCCESS") {
        toast(`${data.inserted}건이 일정에 저장되었습니다.`, "success");
        setSelectedIds(new Set());
        fetchSaved();
      }
    } catch {
      toast("저장 중 오류가 발생했습니다.", "error");
    } finally {
      setSaving(false);
    }
  };

  const upcomingSaved = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return savedItems
      .filter(s => s.deadline_date && new Date(s.deadline_date) >= today)
      .slice(0, 3);
  }, [savedItems]);

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

    if (sortKey === "latest") {
      result.sort((a, b) => b.announcement_id - a.announcement_id);
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

  // 사이드바 내용 (모바일 드로어 + 데스크탑 공용)
  const SidebarContent = () => (
    <div className="glass p-5 md:p-8 rounded-[2rem] space-y-6 shadow-xl lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:overflow-y-auto border border-white/40 scrollbar-thin">
      <div className="absolute -top-16 -right-16 w-32 h-32 bg-indigo-500/10 blur-[50px] rounded-full pointer-events-none" />

      <div className="flex items-center gap-3 relative z-10">
        <div className="w-10 h-10 bg-slate-950 rounded-xl flex-shrink-0 flex items-center justify-center text-xl shadow-lg">🏢</div>
        <div className="min-w-0">
          <h1 className="text-lg md:text-2xl font-black text-slate-950 tracking-tight leading-tight mb-1">
            기업 <span className="text-indigo-600">분석</span>
          </h1>
          <div className="flex flex-wrap gap-1.5">
            <span className="px-2 py-0.5 bg-emerald-50 text-emerald-600 text-[9px] font-black rounded-full uppercase tracking-widest flex items-center gap-1 border border-emerald-100/50">
              <span className="w-1 h-1 bg-emerald-500 rounded-full animate-pulse" />
              {(() => {
                const emp = profile?.employee_count_bracket || "";
                if (["UNDER_5", "5인 미만"].includes(emp)) return "소기업";
                if (["UNDER_10", "5_10", "10인 미만", "5~10인", "5인~10인"].includes(emp)) return "소기업";
                if (["10_50", "10~50인"].includes(emp)) return "중소기업";
                return "중소기업";
              })()}
            </span>
            <span className="px-2 py-0.5 bg-slate-100/50 text-slate-600 text-[9px] font-black rounded-full uppercase tracking-widest border border-slate-200/50 truncate max-w-[120px]">
              {profile?.company_name || "기업명 미등록"}
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
            { label: "업종", value: industryDisplayName || profile?.industry_code || "미등록", icon: "🏭" },
            { label: "기업구조", value: EMPLOYEE_KR[profile?.employee_count_bracket] || profile?.employee_count_bracket || "5인 미만", icon: "👥" },
            { label: "매출규모", value: REVENUE_KR[profile?.revenue_bracket] || REVENUE_KR[profile?.revenue] || profile?.revenue_bracket || "1억 미만", icon: "📈" }
          ].map((item, i) => (
            <div key={i} className="flex items-center justify-between p-3 bg-white/40 hover:bg-white rounded-xl border border-white/50 shadow-sm transition-all duration-300">
              <div className="flex items-center gap-2">
                <span className="text-sm">{item.icon}</span>
                <span className="text-xs font-bold text-slate-400 tracking-wide">{item.label}</span>
              </div>
              <span className="text-xs font-black text-slate-900 truncate max-w-[120px]">{item.value}</span>
            </div>
          ))}
        </div>
      </div>

      {planStatus && (
        <div className={`relative z-10 p-3 rounded-xl border text-center ${
          planStatus.plan === "basic"
            ? "bg-indigo-50 border-indigo-200"
            : planStatus.plan === "expired"
            ? "bg-rose-50 border-rose-200"
            : "bg-emerald-50 border-emerald-200"
        }`}>
          <span className={`text-[10px] font-black uppercase tracking-widest ${
            planStatus.plan === "basic"
              ? "text-indigo-600"
              : planStatus.plan === "expired"
              ? "text-rose-600"
              : "text-emerald-600"
          }`}>
            {planStatus.label}
          </span>
          {planStatus.plan !== "basic" && onUpgrade && (
            <button
              onClick={onUpgrade}
              className="mt-2 w-full py-1.5 bg-indigo-600 text-white rounded-lg text-[10px] font-black hover:bg-indigo-700 transition-all active:scale-95"
            >
              {planStatus.plan === "expired" ? "베이직 플랜 시작" : "업그레이드"}
            </button>
          )}
        </div>
      )}

      {profile?.referral_code && (
        <div className="relative z-10">
          <button
            onClick={() => {
              const url = `${window.location.origin}?ref=${profile.referral_code}`;
              navigator.clipboard.writeText(url).then(() => toast("추천 링크가 복사되었습니다!", "success"));
            }}
            className="w-full py-3 bg-violet-50 text-violet-700 rounded-xl font-black flex items-center justify-center gap-2 hover:bg-violet-100 transition-all border border-violet-100 active:scale-95 text-xs"
          >
            <span className="text-base">🔗</span>
            <span className="tracking-tight">내 추천 링크 복사</span>
          </button>
          {(profile?.merit_months || 0) > 0 && (
            <p className="text-center text-[10px] text-violet-500 font-bold mt-1">
              추천 적립 {profile.merit_months}개월
            </p>
          )}
        </div>
      )}

      <div className="relative z-10">
        <button
          onClick={() => { setIsNotifyOpen(true); setSidebarOpen(false); }}
          className="w-full py-3 bg-indigo-50 text-indigo-700 rounded-xl font-black flex items-center justify-center gap-2 hover:bg-indigo-100 transition-all border border-indigo-100 active:scale-95 text-xs"
        >
          <span className="text-base">🔔</span>
          <span className="tracking-tight">맞춤형 알림 요청</span>
        </button>
      </div>

      {(upcomingSaved.length > 0 || savedItems.length > 0) && (
        <div className="space-y-3 relative z-10">
          <div className="h-px bg-slate-200/60" />
          <div className="flex items-center justify-between px-1 pt-1">
            <h4 className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em]">다가오는 일정</h4>
            <a href="/calendar" className="text-[9px] font-bold text-indigo-500 hover:text-indigo-700 transition-colors">
              전체 보기 →
            </a>
          </div>
          {upcomingSaved.length > 0 ? (
            <div className="space-y-2">
              {upcomingSaved.map(s => {
                const d = s.deadline_date ? new Date(s.deadline_date) : null;
                const diff = d ? Math.ceil((d.getTime() - Date.now()) / 86400000) : null;
                return (
                  <div key={s.id} className="flex items-center gap-2.5 p-3 bg-white/50 rounded-xl border border-white/60 text-[11px]">
                    <span className={`px-2 py-0.5 rounded-md font-black flex-shrink-0 ${diff !== null && diff <= 3 ? "bg-rose-100 text-rose-700" : "bg-indigo-50 text-indigo-600"}`}>
                      {diff !== null ? `D-${diff}` : "상시"}
                    </span>
                    <span className="font-bold text-slate-700 truncate flex-1">{s.title}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-[10px] text-slate-400 px-1">저장된 일정이 없습니다.</p>
          )}
        </div>
      )}

      <div className="relative z-10 pt-1 space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => { onEditProfile(); setSidebarOpen(false); }}
            className="py-3 bg-slate-950 text-white rounded-xl font-black flex items-center justify-center gap-1.5 hover:bg-indigo-600 transition-all shadow-lg active:scale-95 text-xs"
          >
            <span className="text-sm">⚙️</span>
            <span className="tracking-tight">정보 관리</span>
          </button>
          <a
            href="/calendar"
            className="py-3 bg-indigo-50 text-indigo-700 rounded-xl font-black flex items-center justify-center gap-1.5 hover:bg-indigo-100 transition-all border border-indigo-100 active:scale-95 text-xs"
          >
            <span className="text-sm">📅</span>
            <span className="tracking-tight">일정 관리</span>
          </a>
        </div>
        <button
          onClick={onLogout}
          className="w-full py-2 text-slate-400 hover:text-rose-500 text-[10px] font-black uppercase tracking-widest transition-all"
        >
          로그아웃
        </button>
      </div>
    </div>
  );

  return (
    <div className="w-full max-w-[1280px] mx-auto animate-in fade-in slide-in-from-bottom-6 duration-700 px-4 lg:px-0">

      {/* 모바일 상단 바 (lg 미만에서만 표시) */}
      <div className="lg:hidden flex items-center justify-between py-3 mb-4 border-b border-slate-200/60">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xl">🏢</span>
          <div className="min-w-0">
            <p className="text-sm font-black text-slate-900 truncate max-w-[180px]">
              {profile?.company_name || "기업명 미등록"}
            </p>
            {planStatus && (
              <p className={`text-[9px] font-black uppercase tracking-widest ${
                planStatus.plan === "basic" ? "text-indigo-600" :
                planStatus.plan === "expired" ? "text-rose-500" : "text-emerald-600"
              }`}>{planStatus.label}</p>
            )}
          </div>
        </div>
        <button
          onClick={() => setSidebarOpen(true)}
          className="flex items-center gap-1.5 px-3 py-2 bg-slate-100 rounded-xl text-xs font-black text-slate-700 hover:bg-slate-200 transition-all active:scale-95 flex-shrink-0"
        >
          <span>☰</span> 메뉴
        </button>
      </div>

      {/* 모바일 드로어 오버레이 */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 모바일 드로어 패널 */}
      <div className={`fixed top-0 right-0 h-full w-[85vw] max-w-sm z-50 bg-white/95 backdrop-blur-xl shadow-2xl overflow-y-auto transition-transform duration-300 lg:hidden ${sidebarOpen ? "translate-x-0" : "translate-x-full"}`}>
        <div className="p-4">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-black text-slate-400 uppercase tracking-widest">메뉴</span>
            <button
              onClick={() => setSidebarOpen(false)}
              className="w-8 h-8 flex items-center justify-center rounded-full bg-slate-100 text-slate-500 hover:bg-slate-200 transition-all"
            >
              ✕
            </button>
          </div>
          <SidebarContent />
        </div>
      </div>

      {/* 데스크탑 레이아웃 */}
      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6">
        {/* 데스크탑 사이드바 (lg 이상에서만 표시) */}
        <aside className="hidden lg:block">
          <SidebarContent />
        </aside>

        <main className="space-y-4 lg:space-y-5 pb-16 lg:pb-16">
          <header className="space-y-3">
            <h2 className="text-xl sm:text-2xl md:text-3xl lg:text-4xl font-black text-slate-950 tracking-tighter leading-tight">
              AI 맞춤 <span className="text-indigo-600 italic">정부지원금 매칭</span>
            </h2>

            {/* 탭 + 정렬 */}
            <div className="flex items-center gap-1.5 bg-white/60 backdrop-blur-md p-1.5 rounded-xl border border-white/80 shadow-sm overflow-x-auto scrollbar-none">
              {TAB_GROUPS.map((tab) => {
                const count = tabCounts[tab.key] || 0;
                if (tab.key !== "all" && count === 0) return null;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`flex items-center gap-1 px-3 py-2 rounded-lg text-[10px] font-black transition-all duration-300 whitespace-nowrap flex-shrink-0 ${
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
                  { key: "latest" as SortKey, label: "최신" },
                  { key: "deadline" as SortKey, label: "마감임박" },
                ]).map((s) => (
                  <button
                    key={s.key}
                    onClick={() => setSortKey(s.key)}
                    className={`px-2.5 py-1.5 rounded-lg text-[10px] font-black transition-all duration-300 whitespace-nowrap ${
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
          </header>

          {filteredMatches.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 md:py-20 px-6 text-center bg-white/40 backdrop-blur-xl rounded-[2rem] border border-white/60 shadow-lg animate-in zoom-in duration-500 w-full">
              <div className="w-14 h-14 bg-slate-100 rounded-full flex items-center justify-center text-3xl mb-5 animate-pulse">🔍</div>
              <h2 className="text-lg md:text-2xl font-black text-slate-900 mb-3">
                {matches.length === 0 ? "맞춤형 공고가 아직 없습니다" : "조건에 맞는 공고가 없습니다"}
              </h2>
              <p className="text-xs md:text-base text-slate-500 max-w-lg mx-auto mb-6 font-medium leading-relaxed">
                {matches.length === 0
                  ? "국가기관의 최신 공고 데이터를 실시간으로 분석하고 있습니다. 잠시 후 다시 시도하시거나 알림 설정을 켜주세요."
                  : "다른 카테고리 탭을 선택해 보세요."
                }
              </p>
              {matches.length === 0 ? (
                <button
                  onClick={() => setIsNotifyOpen(true)}
                  className="px-6 py-3 bg-slate-950 text-white rounded-xl font-black hover:bg-indigo-600 transition-all shadow-lg active:scale-95 text-sm"
                >
                  알림 받기 설정
                </button>
              ) : (
                <button
                  onClick={() => setActiveTab("all")}
                  className="px-6 py-3 bg-slate-950 text-white rounded-xl font-black hover:bg-indigo-600 transition-all shadow-lg active:scale-95 text-sm"
                >
                  전체 보기
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-6 pb-20">
              {filteredMatches.map((res, idx) => (
                <div
                  key={res.announcement_id ?? idx}
                  className="animate-in fade-in slide-in-from-bottom-6 duration-700"
                  style={{ animationDelay: `${idx * 80}ms` }}
                >
                  <ResultCard
                    res={res}
                    selected={selectedIds.has(res.announcement_id)}
                    onToggle={() => toggleSelect(res.announcement_id)}
                  />
                </div>
              ))}
            </div>
          )}

          {selectedIds.size > 0 && (
            <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-slate-950 text-white px-4 py-3 rounded-2xl shadow-2xl flex items-center gap-3 animate-in slide-in-from-bottom-4 duration-300 w-[calc(100%-2rem)] max-w-sm sm:w-auto sm:max-w-none">
              <span className="text-sm font-bold whitespace-nowrap">☑ {selectedIds.size}건 선택</span>
              <button
                onClick={handleBulkSave}
                disabled={saving}
                className="flex-1 sm:flex-none px-4 py-2 bg-indigo-600 rounded-xl text-sm font-black hover:bg-indigo-500 transition-all active:scale-95 disabled:opacity-50 whitespace-nowrap"
              >
                {saving ? "저장 중..." : "📅 일정 저장"}
              </button>
              <button
                onClick={() => setSelectedIds(new Set())}
                className="p-2 text-slate-400 hover:text-white transition-colors"
                aria-label="선택 취소"
              >
                ✕
              </button>
            </div>
          )}
        </main>
      </div>

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
