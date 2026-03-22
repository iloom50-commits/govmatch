"use client";

import ResultCard from "./ResultCard";
import { useState, useMemo, useCallback, useEffect } from "react";
import NotificationModal from "./NotificationModal";
import SmartDocModal from "./SmartDocModal";
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
    target_type?: string;
}

// 대분류
type MajorTab = "business" | "individual";

const BUSINESS_TABS: { label: string; key: string; categories: string[] }[] = [
  { label: "전체", key: "all", categories: [] },
  { label: "소상공인", key: "small_biz", categories: ["Small Business/Startup", "SME Support", "General Business Support", "General", "Food Industry", "소상공인", "내수"] },
  { label: "창업", key: "startup", categories: ["Entrepreneurship", "Small Business/Startup", "창업"] },
  { label: "R&D/기술", key: "rnd", categories: ["R&D", "R&D/Digital", "기술", "기술개발", "스마트공장", "정보"] },
  { label: "자금/융자", key: "loan", categories: ["Loan/Investment", "금융"] },
  { label: "경영/수출/인력", key: "biz", categories: ["Marketing", "General Business Support", "경영", "수출", "수출지원", "인력", "인력지원", "기타"] },
];

const INDIVIDUAL_TABS: { label: string; key: string; categories: string[] }[] = [
  { label: "전체", key: "all", categories: [] },
  { label: "복지", key: "welfare", categories: ["복지", "생활안정", "의료"] },
  { label: "교육", key: "education", categories: ["교육", "장학", "훈련"] },
  { label: "주거", key: "housing", categories: ["주거", "주택", "임대"] },
  { label: "고용", key: "employment", categories: ["고용", "취업", "일자리", "채용"] },
  { label: "출산/육아", key: "parenting", categories: ["출산", "육아", "보육", "양육"] },
  { label: "금융/세제", key: "finance", categories: ["금융", "세제", "감면", "대출"] },
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
  ai_used?: number;
  ai_limit?: number;
  consult_limit?: number;
  guide_price?: number | null;
}

export default function Dashboard({ matches, profile, onEditProfile, onLogout, planStatus, onUpgrade, consultantResult, onClearConsultant, isPublic, onLoginRequired }: { matches: MatchItem[], profile: any, onEditProfile: () => void, onLogout: () => void, planStatus?: PlanStatus | null, onUpgrade?: () => void, consultantResult?: { matches: any[]; profile: any } | null, onClearConsultant?: () => void, isPublic?: boolean, onLoginRequired?: () => void }) {
  const { toast } = useToast();
  // 사용자 유형에 따라 초기 대분류 탭 결정
  const userType = profile?.user_type || "business";
  const initialMajor: MajorTab = userType === "individual" ? "individual" : "business";
  const [majorTab, setMajorTab] = useState<MajorTab>(initialMajor);
  const [activeTab, setActiveTab] = useState("all");
  const currentTabs = majorTab === "business" ? BUSINESS_TABS : INDIVIDUAL_TABS;

  // 탭 노출 제어: 비로그인=둘다, individual=개인만, business=기업만, both=둘다
  const showBusinessTab = isPublic || userType === "business" || userType === "both";
  const showIndividualTab = isPublic || userType === "individual" || userType === "both";
  const [sortKey, setSortKey] = useState<SortKey>("latest");
  const [isNotifyOpen, setIsNotifyOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [savedItems, setSavedItems] = useState<SavedItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isPwaInstalled, setIsPwaInstalled] = useState(false);
  const [isIos, setIsIos] = useState(false);
  const [iosBannerDismissed, setIosBannerDismissed] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    // 이미 PWA로 실행 중이면 설치 버튼 숨김
    if (window.matchMedia("(display-mode: standalone)").matches || (window.navigator as any).standalone) {
      setIsPwaInstalled(true);
      return;
    }
    // iOS 감지 (Safari에서는 beforeinstallprompt 미지원)
    const ua = window.navigator.userAgent;
    const isiOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    if (isiOS) {
      setIsIos(true);
      const dismissed = sessionStorage.getItem("ios_pwa_dismissed");
      if (dismissed) setIosBannerDismissed(true);
    }
    // 글로벌로 캡처된 프롬프트 확인 (컴포넌트 마운트 전 이벤트 대비)
    if ((window as any).__pwaPrompt) {
      setDeferredPrompt((window as any).__pwaPrompt);
    }
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
      (window as any).__pwaPrompt = e;
    };
    window.addEventListener("beforeinstallprompt", handler);
    window.addEventListener("appinstalled", () => setIsPwaInstalled(true));
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const handlePwaInstall = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") {
      setIsPwaInstalled(true);
      toast("앱이 설치되었습니다!", "success");
    }
    setDeferredPrompt(null);
  };

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

  // 컨설턴트 결과가 있으면 해당 결과를 우선 표시
  const rawMatches = consultantResult?.matches ?? matches;

  // majorTab에 따라 target_type 필터링
  const displayMatches = useMemo(() => {
    return rawMatches.filter((m: any) => {
      const tt = m.target_type || "business";
      if (majorTab === "business") return tt === "business" || tt === "both";
      if (majorTab === "individual") return tt === "individual" || tt === "both";
      return true;
    });
  }, [rawMatches, majorTab]);

  const filteredMatches = useMemo(() => {
    let result = [...displayMatches];

    // 키워드 검색 필터
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      result = result.filter(m =>
        (m.title || "").toLowerCase().includes(q) ||
        (m.summary_text || "").toLowerCase().includes(q) ||
        (m.department || "").toLowerCase().includes(q)
      );
    }

    if (activeTab !== "all") {
      const group = currentTabs.find((t: { key: string }) => t.key === activeTab);
      if (group) {
        result = result.filter(m => {
          const cat = (m.category || "").trim();
          return group.categories.some((gc: string) =>
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
  }, [displayMatches, activeTab, sortKey, searchQuery]);

  const searchedMatches = useMemo(() => {
    if (!searchQuery.trim()) return displayMatches;
    const q = searchQuery.trim().toLowerCase();
    return displayMatches.filter(m =>
      (m.title || "").toLowerCase().includes(q) ||
      (m.summary_text || "").toLowerCase().includes(q) ||
      (m.department || "").toLowerCase().includes(q)
    );
  }, [displayMatches, searchQuery]);

  const tabCounts = useMemo(() => {
    const counts: Record<string, number> = { all: searchedMatches.length };
    currentTabs.forEach((g: { key: string; categories: string[] }) => {
      if (g.key === "all") return;
      counts[g.key] = searchedMatches.filter(m => {
        const cat = (m.category || "").trim();
        return g.categories.some((gc: string) => cat.toLowerCase().includes(gc.toLowerCase()));
      }).length;
    });
    return counts;
  }, [searchedMatches, currentTabs]);

  // 비로그인 사이드바 (프로그램 소개 + CTA)
  const PublicSidebarContent = () => (
    <div className="glass p-4 md:p-5 rounded-2xl space-y-4 shadow-xl border border-white/40 overflow-x-hidden w-full max-w-full box-border relative">
      <div className="absolute -top-16 -right-16 w-32 h-32 bg-indigo-500/10 blur-[50px] rounded-full pointer-events-none" />
      <div className="absolute -bottom-16 -left-16 w-32 h-32 bg-violet-500/10 blur-[50px] rounded-full pointer-events-none" />

      {/* 브랜드 */}
      <div className="relative z-10 text-center py-3">
        <h2 className="text-xl font-black text-slate-900 tracking-tight mb-1">
          <span className="text-indigo-600">지원금톡톡</span>
        </h2>
        <p className="text-[11px] text-slate-500 font-medium leading-relaxed">
          AI가 매시간 5,000개 이상의<br />정부 공고를 분석합니다
        </p>
      </div>

      {/* 핵심 기능 소개 */}
      <div className="relative z-10 space-y-2.5">
        {[
          { icon: "🎯", title: "AI 맞춤 매칭", desc: "기업 조건에 딱 맞는 공고만" },
          { icon: "💬", title: "지원대상 즉시 판별", desc: "공고별 자격요건 AI 정밀 분석" },
          { icon: "📝", title: "AI 신청서 자동작성", desc: "공고 양식 학습 후 자동 작성" },
          { icon: "🔔", title: "마감 D-day 알림", desc: "놓치지 않는 맞춤형 알림" },
        ].map((item) => (
          <div key={item.title} className="flex items-start gap-3 p-3 bg-white/60 rounded-xl border border-slate-100/80">
            <span className="text-lg flex-shrink-0 mt-0.5">{item.icon}</span>
            <div>
              <p className="text-[12px] font-bold text-slate-800">{item.title}</p>
              <p className="text-[11px] text-slate-500 font-medium">{item.desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* 통계 */}
      <div className="relative z-10 p-3 bg-indigo-50/80 rounded-xl border border-indigo-100/60 text-center">
        <p className="text-[11px] text-indigo-500 font-bold uppercase tracking-widest mb-1">실시간 분석 중</p>
        <p className="text-lg font-black text-indigo-700">{(matches.length || 0).toLocaleString()}건</p>
        <p className="text-[11px] text-slate-500 font-medium">의 공고를 확인할 수 있습니다</p>
      </div>

      {/* 구분선 */}
      <div className="relative z-10 flex items-center gap-3">
        <div className="flex-1 h-px bg-slate-200/60" />
        <span className="text-[11px] text-slate-400 font-bold">무료로 시작하기</span>
        <div className="flex-1 h-px bg-slate-200/60" />
      </div>

      {/* 소셜 로그인 */}
      <div className="relative z-10 space-y-2">
        <button
          onClick={() => window.location.href = `${API}/api/auth/social/kakao`}
          className="w-full py-2.5 bg-[#FEE500] text-[#191919] rounded-xl text-xs font-bold flex items-center justify-center gap-2 hover:brightness-95 transition-all active:scale-[0.98]"
        >
          <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
            <path d="M12 3C6.48 3 2 6.58 2 10.9c0 2.78 1.86 5.22 4.65 6.6l-.96 3.56c-.08.3.26.54.52.37l4.23-2.82c.51.05 1.03.09 1.56.09 5.52 0 10-3.58 10-7.9C22 6.58 17.52 3 12 3z" />
          </svg>
          카카오로 시작하기
        </button>
        <button
          onClick={() => window.location.href = `${API}/api/auth/social/naver`}
          className="w-full py-2.5 bg-[#03C75A] text-white rounded-xl text-xs font-bold flex items-center justify-center gap-2 hover:brightness-95 transition-all active:scale-[0.98]"
        >
          <span className="text-sm font-black">N</span>
          네이버로 시작하기
        </button>
        <button
          onClick={() => window.location.href = `${API}/api/auth/social/google`}
          className="w-full py-2.5 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold flex items-center justify-center gap-2 hover:bg-slate-50 transition-all active:scale-[0.98]"
        >
          <svg viewBox="0 0 24 24" className="w-4 h-4">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          Google로 시작하기
        </button>
      </div>

      {/* 이메일 가입 */}
      <div className="relative z-10 text-center">
        <button
          onClick={() => onLoginRequired?.()}
          className="text-[11px] text-slate-400 hover:text-indigo-600 font-bold transition-all"
        >
          이메일로 로그인/가입 →
        </button>
      </div>

      {/* PWA 앱 설치 유도 — Android/Chrome (비로그인) */}
      {!isPwaInstalled && deferredPrompt && (
        <div className="relative z-10 p-3 bg-gradient-to-r from-indigo-50 to-violet-50 rounded-lg border border-indigo-100/60">
          <div className="flex items-center gap-2.5 mb-2">
            <span className="text-lg">📲</span>
            <div>
              <p className="text-[11px] font-bold text-slate-800">앱으로 설치하기</p>
              <p className="text-[11px] text-slate-500">홈 화면에서 바로 실행할 수 있어요</p>
            </div>
          </div>
          <button
            onClick={handlePwaInstall}
            className="w-full py-2 bg-indigo-600 text-white rounded-lg font-bold text-[11px] hover:bg-indigo-700 transition-all active:scale-95 shadow-md flex items-center justify-center gap-1.5"
          >
            <span className="text-xs">⬇️</span>
            지원금톡톡 설치
          </button>
        </div>
      )}

      {/* PWA 설치 안내 — iOS Safari (비로그인) */}
      {!isPwaInstalled && isIos && !deferredPrompt && !iosBannerDismissed && (
        <div className="relative z-10 p-3 bg-gradient-to-r from-indigo-50 to-violet-50 rounded-lg border border-indigo-100/60">
          <button
            onClick={() => { setIosBannerDismissed(true); sessionStorage.setItem("ios_pwa_dismissed", "1"); }}
            className="absolute top-2 right-2 text-slate-400 hover:text-slate-600 text-sm leading-none"
            aria-label="닫기"
          >✕</button>
          <div className="flex items-center gap-2.5 mb-2">
            <span className="text-lg">📲</span>
            <div>
              <p className="text-[11px] font-bold text-slate-800">홈 화면에 추가하기</p>
              <p className="text-[11px] text-slate-500">앱처럼 바로 실행할 수 있어요</p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 bg-white/80 rounded-lg border border-slate-100">
            <div className="flex items-center justify-center w-7 h-7 bg-indigo-100 rounded-lg shrink-0">
              <span className="text-sm">□↑</span>
            </div>
            <p className="text-[11px] text-slate-600 font-medium leading-relaxed">
              Safari 하단 <span className="font-bold text-indigo-600">공유 버튼(□↑)</span>을 누른 뒤<br/>
              <span className="font-bold text-indigo-600">&quot;홈 화면에 추가&quot;</span>를 선택하세요
            </p>
          </div>
        </div>
      )}

      {/* 서비스 공유 */}
      <div className="relative z-10 pt-2">
        <div className="flex items-center gap-3 mb-2">
          <div className="flex-1 h-px bg-slate-200/60" />
          <span className="text-[11px] text-slate-400 font-bold">친구에게 알려주기</span>
          <div className="flex-1 h-px bg-slate-200/60" />
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          <button
            onClick={() => {
              const url = window.location.origin;
              const text = "AI가 나에게 맞는 정부지원금을 찾아줘요! 지원금톡톡에서 확인해보세요.";
              if (navigator.share) {
                navigator.share({ title: "지원금톡톡", text, url });
              } else {
                navigator.clipboard.writeText(`${text} ${url}`).then(() => toast("공유 텍스트가 복사되었습니다!", "success"));
              }
            }}
            className="flex items-center justify-center gap-1.5 py-2 bg-blue-50 rounded-lg hover:bg-blue-100 transition-all active:scale-95 border border-blue-200/60 text-xs font-bold text-blue-700"
          >
            <span>📤</span> 공유하기
          </button>
          <button
            onClick={() => {
              navigator.clipboard.writeText(window.location.origin).then(() => toast("링크가 복사되었습니다!", "success"));
            }}
            className="flex items-center justify-center gap-1.5 py-2 bg-violet-50 rounded-lg hover:bg-violet-100 transition-all active:scale-95 border border-violet-200/60 text-xs font-bold text-violet-700"
          >
            <span>🔗</span> 링크복사
          </button>
        </div>
      </div>
    </div>
  );

  // 사이드바 내용 (모바일 드로어 + 데스크탑 공용)
  const SidebarContent = () => (
    <div className="glass p-4 md:p-5 rounded-2xl space-y-3 shadow-xl border border-white/40 overflow-x-hidden w-full max-w-full box-border">
      <div className="absolute -top-16 -right-16 w-32 h-32 bg-indigo-500/10 blur-[50px] rounded-full pointer-events-none" />

      <div className="relative z-10 p-5 bg-white/60 rounded-xl border border-slate-100/80 shadow-sm">
        {/* 상호명 + 뱃지 */}
        <div className="flex items-center gap-2.5 mb-4">
          <div className="w-10 h-10 bg-slate-950 rounded-lg flex-shrink-0 flex items-center justify-center text-lg shadow">🏢</div>
          <div className="min-w-0 flex-1">
            <p className="text-[15px] font-bold text-slate-900 tracking-tight truncate">{profile?.company_name || "기업명 미등록"}</p>
            <span className="px-1.5 py-px bg-emerald-50 text-emerald-600 text-[11px] font-bold rounded flex items-center gap-1 border border-emerald-100/50 mt-0.5 w-fit">
              <span className="w-1 h-1 bg-emerald-500 rounded-full animate-pulse" />
              {(() => {
                const emp = profile?.employee_count_bracket || "";
                if (["UNDER_5", "5인 미만"].includes(emp)) return "소기업";
                if (["UNDER_10", "5_10", "10인 미만", "5~10인", "5인~10인"].includes(emp)) return "소기업";
                if (["10_50", "10~50인"].includes(emp)) return "중소기업";
                return "중소기업";
              })()}
            </span>
          </div>
        </div>
        {/* 기업 상세 정보 */}
        <div className="h-px bg-slate-100 mb-4" />
        <div className="grid grid-cols-[56px_1fr] gap-y-3.5 text-[13px]">
          <span className="text-slate-400">설립</span>
          <span className="font-semibold text-slate-800">{profile?.establishment_date ? String(profile.establishment_date).slice(0, 10) : "미등록"}</span>
          <span className="text-slate-400">소재지</span>
          <span className="font-semibold text-slate-800">{profile?.address_city || "전국"}</span>
          <span className="text-slate-400">업종</span>
          <span className="font-semibold text-slate-800 break-words">{industryDisplayName || profile?.industry_code || "미등록"}</span>
          <span className="text-slate-400">매출</span>
          <span className="font-semibold text-slate-800">{REVENUE_KR[profile?.revenue_bracket] || REVENUE_KR[profile?.revenue] || profile?.revenue_bracket || "1억 미만"}</span>
          <span className="text-slate-400">인원</span>
          <span className="font-semibold text-slate-800">{EMPLOYEE_KR[profile?.employee_count_bracket] || profile?.employee_count_bracket || "5인 미만"}</span>
        </div>
      </div>

      {planStatus && (
        <div className={`relative z-10 p-3 rounded-lg border ${
          planStatus.plan === "pro" || planStatus.plan === "biz"
            ? "bg-violet-50 border-violet-200"
            : planStatus.plan === "basic"
            ? "bg-indigo-50 border-indigo-200"
            : planStatus.plan === "expired"
            ? "bg-rose-50 border-rose-200"
            : "bg-slate-50 border-slate-200"
        }`}>
          <div className="flex items-center justify-between mb-1.5">
            <span className={`text-[11px] font-bold uppercase tracking-widest ${
              planStatus.plan === "pro" || planStatus.plan === "biz"
                ? "text-violet-600"
                : planStatus.plan === "basic"
                ? "text-indigo-600"
                : planStatus.plan === "expired"
                ? "text-rose-600"
                : "text-slate-500"
            }`}>
              {planStatus.label}
            </span>
            {planStatus.days_left != null && planStatus.days_left > 0 && (
              <span className="text-[11px] font-semibold text-slate-400">D-{planStatus.days_left}</span>
            )}
          </div>
          {/* AI 상담 사용량 */}
          {planStatus.ai_limit != null && planStatus.ai_limit < 999999 && (
            <div className="mb-2">
              <div className="flex items-center justify-between text-[11px] mb-1">
                <span className="text-slate-500 font-medium">AI 상담 (자유+컨설턴트)</span>
                <span className="font-bold text-slate-600">{planStatus.ai_used || 0}/{planStatus.ai_limit}회</span>
              </div>
              <div className="w-full h-1.5 bg-slate-200/60 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    ((planStatus.ai_used || 0) / planStatus.ai_limit) > 0.8
                      ? "bg-rose-500"
                      : planStatus.plan === "pro" || planStatus.plan === "biz" ? "bg-violet-500" : "bg-indigo-500"
                  }`}
                  style={{ width: `${Math.min(((planStatus.ai_used || 0) / planStatus.ai_limit) * 100, 100)}%` }}
                />
              </div>
            </div>
          )}
          {planStatus.ai_limit != null && planStatus.ai_limit >= 999999 && (
            <div className="mb-2">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500 font-medium">AI 상담</span>
                <span className="font-bold text-violet-600">무제한</span>
              </div>
            </div>
          )}
          {/* 공고별 상담 상태 */}
          <div className="mb-2">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-500 font-medium">공고별 지원대상 상담</span>
              <span className={`font-bold ${(planStatus.consult_limit || 0) > 0 ? "text-emerald-600" : "text-slate-400"}`}>
                {(planStatus.consult_limit || 0) >= 999999 ? "무제한" : (planStatus.consult_limit || 0) > 0 ? `${planStatus.consult_limit}회 무료` : "BASIC부터"}
              </span>
            </div>
          </div>
          {!["basic", "pro", "biz"].includes(planStatus.plan) && onUpgrade && (
            <button
              onClick={onUpgrade}
              className="w-full py-1.5 bg-amber-500 text-white rounded-lg text-[11px] font-bold hover:bg-amber-600 transition-all active:scale-95"
            >
              {planStatus.plan === "expired" ? "플랜 시작하기" : "업그레이드"}
            </button>
          )}
        </div>
      )}

      {profile?.referral_code && (
        <div className="relative z-10 space-y-2">
          <p className="text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em] px-1">친구에게 추천하기</p>
          <div className="grid grid-cols-3 gap-1.5">
            <button
              onClick={() => {
                const url = `${window.location.origin}?ref=${profile.referral_code}`;
                const text = `AI가 우리 기업에 맞는 정부지원금을 찾아줘요! 지원금톡톡에서 확인해보세요.`;
                if (typeof window !== "undefined" && (window as any).Kakao?.Share) {
                  (window as any).Kakao.Share.sendDefault({
                    objectType: "feed",
                    content: {
                      title: "지원금톡톡",
                      description: text,
                      imageUrl: `${window.location.origin}/icon-512.png`,
                      link: { mobileWebUrl: url, webUrl: url },
                    },
                    buttons: [{ title: "지원금 확인하기", link: { mobileWebUrl: url, webUrl: url } }],
                  });
                } else {
                  window.open(`https://story.kakao.com/share?url=${encodeURIComponent(url)}`, "_blank", "width=500,height=600");
                }
              }}
              className="flex flex-col items-center gap-1 py-2 bg-yellow-50 rounded-lg hover:bg-yellow-100 transition-all active:scale-95 border border-yellow-200/60"
            >
              <span className="text-base">💬</span>
              <span className="text-[11px] font-semibold text-yellow-800">카카오톡</span>
            </button>
            <button
              onClick={() => {
                const url = `${window.location.origin}?ref=${profile.referral_code}`;
                const text = `AI가 우리 기업에 맞는 정부지원금을 찾아줘요!`;
                if (navigator.share) {
                  navigator.share({ title: "지원금톡톡", text, url });
                } else {
                  navigator.clipboard.writeText(`${text} ${url}`).then(() => toast("공유 텍스트가 복사되었습니다!", "success"));
                }
              }}
              className="flex flex-col items-center gap-1 py-2 bg-blue-50 rounded-lg hover:bg-blue-100 transition-all active:scale-95 border border-blue-200/60"
            >
              <span className="text-base">📤</span>
              <span className="text-[11px] font-semibold text-blue-800">공유</span>
            </button>
            <button
              onClick={() => {
                const url = `${window.location.origin}?ref=${profile.referral_code}`;
                navigator.clipboard.writeText(url).then(() => toast("추천 링크가 복사되었습니다!", "success"));
              }}
              className="flex flex-col items-center gap-1 py-2 bg-violet-50 rounded-lg hover:bg-violet-100 transition-all active:scale-95 border border-violet-200/60"
            >
              <span className="text-base">🔗</span>
              <span className="text-[11px] font-semibold text-violet-800">링크복사</span>
            </button>
          </div>
          {(profile?.merit_months || 0) > 0 && (
            <p className="text-center text-[11px] text-violet-500 font-bold">
              추천 적립 {profile.merit_months}개월
            </p>
          )}
        </div>
      )}

      <div className="relative z-10">
        <button
          onClick={() => { setIsNotifyOpen(true); setSidebarOpen(false); }}
          className="w-full py-2 bg-indigo-50 text-indigo-700 rounded-lg font-bold flex items-center justify-center gap-2 hover:bg-indigo-100 transition-all border border-indigo-100 active:scale-95 text-xs"
        >
          <span className="text-sm">🔔</span>
          <span className="tracking-tight">맞춤형 알림 요청</span>
        </button>
      </div>

      {/* PWA 앱 설치 유도 — Android/Chrome */}
      {!isPwaInstalled && deferredPrompt && (
        <div className="relative z-10 p-3 bg-gradient-to-r from-indigo-50 to-violet-50 rounded-lg border border-indigo-100/60">
          <div className="flex items-center gap-2.5 mb-2">
            <span className="text-lg">📲</span>
            <div>
              <p className="text-[11px] font-bold text-slate-800">앱으로 설치하기</p>
              <p className="text-[11px] text-slate-500">홈 화면에서 바로 실행할 수 있어요</p>
            </div>
          </div>
          <button
            onClick={handlePwaInstall}
            className="w-full py-2 bg-indigo-600 text-white rounded-lg font-bold text-[11px] hover:bg-indigo-700 transition-all active:scale-95 shadow-md flex items-center justify-center gap-1.5"
          >
            <span className="text-xs">⬇️</span>
            지원금톡톡 설치
          </button>
        </div>
      )}

      {/* PWA 설치 안내 — iOS Safari */}
      {!isPwaInstalled && isIos && !deferredPrompt && !iosBannerDismissed && (
        <div className="relative z-10 p-3 bg-gradient-to-r from-indigo-50 to-violet-50 rounded-lg border border-indigo-100/60">
          <button
            onClick={() => { setIosBannerDismissed(true); sessionStorage.setItem("ios_pwa_dismissed", "1"); }}
            className="absolute top-2 right-2 text-slate-400 hover:text-slate-600 text-sm leading-none"
            aria-label="닫기"
          >✕</button>
          <div className="flex items-center gap-2.5 mb-2">
            <span className="text-lg">📲</span>
            <div>
              <p className="text-[11px] font-bold text-slate-800">홈 화면에 추가하기</p>
              <p className="text-[11px] text-slate-500">앱처럼 바로 실행할 수 있어요</p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 bg-white/80 rounded-lg border border-slate-100">
            <div className="flex items-center justify-center w-7 h-7 bg-indigo-100 rounded-lg shrink-0">
              <span className="text-sm">□↑</span>
            </div>
            <p className="text-[11px] text-slate-600 font-medium leading-relaxed">
              Safari 하단 <span className="font-bold text-indigo-600">공유 버튼(□↑)</span>을 누른 뒤<br/>
              <span className="font-bold text-indigo-600">&quot;홈 화면에 추가&quot;</span>를 선택하세요
            </p>
          </div>
        </div>
      )}

      {(upcomingSaved.length > 0 || savedItems.length > 0) && (
        <div className="space-y-3 relative z-10">
          <div className="h-px bg-slate-200/60" />
          <div className="flex items-center justify-between px-1 pt-1">
            <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em]">다가오는 일정</h4>
            <a href="/calendar" className="text-[11px] font-bold text-indigo-500 hover:text-indigo-700 transition-colors">
              전체 보기 →
            </a>
          </div>
          {upcomingSaved.length > 0 ? (
            <div className="space-y-2">
              {upcomingSaved.map(s => {
                const d = s.deadline_date ? new Date(s.deadline_date) : null;
                const diff = d ? Math.ceil((d.getTime() - Date.now()) / 86400000) : null;
                return (
                  <div key={s.id} className="flex items-center gap-2.5 p-3 bg-white/50 rounded-lg border border-white/60 text-[11px]">
                    <span className={`px-2 py-0.5 rounded-md font-bold flex-shrink-0 ${diff !== null && diff <= 3 ? "bg-rose-100 text-rose-700" : "bg-indigo-50 text-indigo-600"}`}>
                      {diff !== null ? `D-${diff}` : "상시"}
                    </span>
                    <span className="font-bold text-slate-700 truncate flex-1">{s.title}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-[11px] text-slate-400 px-1">저장된 일정이 없습니다.</p>
          )}
        </div>
      )}

      <div className="relative z-10 pt-1 space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => { onEditProfile(); setSidebarOpen(false); }}
            className="py-2 bg-slate-950 text-white rounded-lg font-bold flex items-center justify-center gap-1.5 hover:bg-indigo-600 transition-all shadow-lg active:scale-95 text-xs"
          >
            <span className="text-sm">⚙️</span>
            <span className="tracking-tight">정보 관리</span>
          </button>
          <a
            href="/calendar"
            className="py-2 bg-indigo-50 text-indigo-700 rounded-lg font-bold flex items-center justify-center gap-1.5 hover:bg-indigo-100 transition-all border border-indigo-100 active:scale-95 text-xs"
          >
            <span className="text-sm">📅</span>
            <span className="tracking-tight">일정 관리</span>
          </a>
        </div>
        {!isPublic && onLogout && (
          <button
            onClick={() => { onLogout(); setSidebarOpen(false); }}
            className="w-full py-2 text-slate-400 hover:text-rose-500 rounded-lg text-xs font-medium transition-all"
          >
            로그아웃
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="w-full max-w-[1280px] mx-auto animate-in fade-in slide-in-from-bottom-6 duration-700 px-1 sm:px-2 lg:px-0 overflow-x-clip">

      {/* 모바일 상단 바 (lg 미만에서만 표시) — 로그인 사용자만 */}
      {isPublic ? null : (
        <div className="lg:hidden flex items-center justify-between py-3 mb-4 border-b border-slate-200/60">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-base font-bold text-indigo-600 tracking-tight">지원금톡톡</span>
            <div className="min-w-0">
              {planStatus && (
                <p className={`text-[11px] font-bold uppercase tracking-widest ${
                  planStatus.plan === "pro" || planStatus.plan === "biz" ? "text-violet-600" :
                  planStatus.plan === "basic" ? "text-indigo-600" :
                  planStatus.plan === "expired" ? "text-rose-500" : "text-slate-400"
                }`}>{planStatus.label}</p>
              )}
            </div>
          </div>
          <button
            onClick={() => setSidebarOpen(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-100 rounded-lg text-xs font-bold text-slate-700 hover:bg-slate-200 transition-all active:scale-95 flex-shrink-0"
          >
            <span>☰</span> 메뉴
          </button>
        </div>
      )}

      {/* 모바일 드로어 오버레이 */}
      {!isPublic && sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 모바일 드로어 패널 */}
      {!isPublic && (
        <div className={`fixed top-0 right-0 h-full w-[85vw] max-w-sm z-50 bg-white/95 backdrop-blur-xl shadow-2xl overflow-y-auto transition-transform duration-300 lg:hidden ${sidebarOpen ? "translate-x-0" : "translate-x-full"}`}>
          <div className="p-4">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">메뉴</span>
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
      )}

      {/* 데스크탑 레이아웃 */}
      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6 items-start">
        {/* 데스크탑 사이드바 */}
        <aside className="hidden lg:block lg:sticky lg:top-6 lg:self-start">
          {isPublic ? <PublicSidebarContent /> : <SidebarContent />}
        </aside>

        <main className="space-y-4 lg:space-y-5 pb-16 lg:pb-16">
          {/* 모바일 비로그인 하단 플로팅 CTA (lg 미만) */}

          {/* 컨설턴트 매칭 결과 배너 */}
          {consultantResult && (
            <div className="p-4 bg-gradient-to-r from-violet-50 to-purple-50 border border-violet-200 rounded-xl animate-in slide-in-from-top duration-300 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 bg-violet-100 rounded-lg flex items-center justify-center flex-shrink-0">
                    <svg className="w-5 h-5 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9zm3.75 11.625a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-[13px] font-bold text-violet-800">
                      AI 컨설턴트 매칭 결과 — {consultantResult.profile?.company_name || "고객사"}
                    </p>
                    <p className="text-[11px] text-violet-600 font-medium">
                      {consultantResult.matches.length}건의 맞춤 지원사업 | 소재지: {consultantResult.profile?.address_city || "-"} | 매출: {consultantResult.profile?.revenue_bracket || "-"} | 인원: {consultantResult.profile?.employee_count_bracket || "-"}
                    </p>
                  </div>
                </div>
                <button
                  onClick={onClearConsultant}
                  className="px-3 py-1.5 bg-white border border-violet-200 text-violet-700 rounded-lg text-[11px] font-bold hover:bg-violet-50 transition-all active:scale-95 flex-shrink-0"
                >
                  내 매칭으로 돌아가기
                </button>
              </div>
            </div>
          )}

          <header className="space-y-3">
            <h2 className="text-xl sm:text-2xl md:text-3xl lg:text-4xl font-bold text-slate-950 tracking-tighter leading-tight flex flex-wrap items-baseline gap-1.5 sm:gap-3">
              <span className={consultantResult ? "text-violet-600" : "text-indigo-600"}>
                {consultantResult ? "컨설턴트 매칭" : "지원금톡톡"}
              </span>
              <span className="text-[11px] sm:text-xs md:text-sm font-medium text-slate-500 tracking-normal">
                {consultantResult ? `${consultantResult.profile?.company_name || "고객사"} 맞춤 결과` : "AI가 찾아주는 맞춤 정부보조금"}
              </span>
            </h2>

            {/* 대분류 탭 */}
            <div className="flex items-center gap-2 mb-2">
              {([
                { key: "business" as MajorTab, label: "기업지원 매칭", icon: "🏢", show: showBusinessTab },
                { key: "individual" as MajorTab, label: "개인지원 매칭", icon: "👤", show: showIndividualTab },
              ]).map((tab) => {
                if (!tab.show) return null;
                // 비활성 상태 (상대 탭이 미등록인 경우) — 현재는 show=false로 처리하므로 여기 도달하면 활성
                return (
                  <button
                    key={tab.key}
                    onClick={() => { setMajorTab(tab.key); setActiveTab("all"); }}
                    className={`flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-bold transition-all duration-300 ${
                      majorTab === tab.key
                        ? tab.key === "business"
                          ? "bg-indigo-600 text-white shadow-lg shadow-indigo-200"
                          : "bg-emerald-600 text-white shadow-lg shadow-emerald-200"
                        : "bg-white/80 text-slate-500 hover:bg-slate-50 border border-slate-200"
                    }`}
                  >
                    <span className="text-sm">{tab.icon}</span>
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* 키워드 검색 */}
            <div className="flex items-center gap-2 bg-white/70 backdrop-blur-md p-2 rounded-lg border border-slate-200/60 shadow-sm">
              <div className="flex items-center gap-1.5 px-2 text-slate-400 flex-shrink-0">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={majorTab === "business" ? "공고명, 키워드 검색 (예: 창업, R&D, 수출)" : "공고명, 키워드 검색 (예: 복지, 육아, 주거, 취업)"}
                className="flex-1 bg-transparent border-none px-1 py-1.5 text-xs text-slate-700 placeholder-slate-400 outline-none"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="p-1 text-slate-400 hover:text-slate-600 transition-colors flex-shrink-0"
                  aria-label="검색어 초기화"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>

            {/* 하위 카테고리 탭 + 정렬 */}
            <div className="flex items-center gap-1.5 bg-white/60 backdrop-blur-md p-1.5 rounded-lg border border-white/80 shadow-sm">
              {/* Mobile: 드롭다운 */}
              <div className="relative sm:hidden flex-1">
                <select
                  value={activeTab}
                  onChange={(e) => setActiveTab(e.target.value)}
                  className={`w-full appearance-none text-white px-3 py-2 pr-8 rounded-lg text-[11px] font-bold outline-none cursor-pointer ${
                    majorTab === "business" ? "bg-slate-950" : "bg-emerald-700"
                  }`}
                >
                  {currentTabs.map((tab) => {
                    const count = tabCounts[tab.key] || 0;
                    if (tab.key !== "all" && count === 0) return null;
                    return (
                      <option key={tab.key} value={tab.key}>
                        {tab.label} ({count})
                      </option>
                    );
                  })}
                </select>
                <svg className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-white/70 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </div>

              {/* Desktop: 하위 카테고리 탭 버튼 */}
              <div className="hidden sm:flex items-center gap-1">
                {currentTabs.map((tab) => {
                  const count = tabCounts[tab.key] || 0;
                  if (tab.key !== "all" && count === 0) return null;
                  return (
                    <button
                      key={tab.key}
                      onClick={() => setActiveTab(tab.key)}
                      className={`flex items-center gap-1 px-3 py-2 rounded-lg text-[11px] font-bold transition-all duration-300 whitespace-nowrap flex-shrink-0 ${
                        activeTab === tab.key
                          ? majorTab === "business"
                            ? "bg-slate-950 text-white shadow-md"
                            : "bg-emerald-700 text-white shadow-md"
                          : "text-slate-500 hover:bg-slate-50"
                      }`}
                    >
                      {tab.label}
                      <span className={`text-[11px] px-1.5 py-0.5 rounded-full font-bold ${
                        activeTab === tab.key
                          ? "bg-white/20 text-white/80"
                          : "bg-slate-100 text-slate-400"
                      }`}>
                        {count}
                      </span>
                    </button>
                  );
                })}
              </div>

              <div className="ml-auto flex-shrink-0 h-6 w-px bg-slate-200" />

              <div className="flex items-center gap-1 flex-shrink-0">
                {([
                  { key: "latest" as SortKey, label: "최신" },
                  { key: "deadline" as SortKey, label: "마감임박" },
                ]).map((s) => (
                  <button
                    key={s.key}
                    onClick={() => setSortKey(s.key)}
                    className={`px-2.5 py-1.5 rounded-lg text-[11px] font-bold transition-all duration-300 whitespace-nowrap ${
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
            <div className="flex flex-col items-center justify-center py-12 md:py-20 px-6 text-center bg-white/40 backdrop-blur-xl rounded-2xl border border-white/60 shadow-lg animate-in zoom-in duration-500 w-full">
              <div className="w-14 h-14 bg-slate-100 rounded-full flex items-center justify-center text-3xl mb-5 animate-pulse">🔍</div>
              <h2 className="text-lg md:text-2xl font-bold text-slate-900 mb-3">
                {searchQuery.trim()
                  ? `"${searchQuery.trim()}" 검색 결과가 없습니다`
                  : matches.length === 0 ? "맞춤형 공고가 아직 없습니다" : "조건에 맞는 공고가 없습니다"}
              </h2>
              <p className="text-xs md:text-base text-slate-500 max-w-lg mx-auto mb-6 font-medium leading-relaxed">
                {searchQuery.trim()
                  ? "다른 키워드로 검색하거나 검색어를 초기화해 보세요."
                  : matches.length === 0
                  ? "국가기관의 최신 공고 데이터를 실시간으로 분석하고 있습니다. 잠시 후 다시 시도하시거나 알림 설정을 켜주세요."
                  : "다른 카테고리 탭을 선택해 보세요."
                }
              </p>
              {searchQuery.trim() ? (
                <button
                  onClick={() => setSearchQuery("")}
                  className="px-6 py-3 bg-slate-950 text-white rounded-lg font-bold hover:bg-indigo-600 transition-all shadow-lg active:scale-95 text-sm"
                >
                  검색어 초기화
                </button>
              ) : matches.length === 0 ? (
                <button
                  onClick={() => setIsNotifyOpen(true)}
                  className="px-6 py-3 bg-slate-950 text-white rounded-lg font-bold hover:bg-indigo-600 transition-all shadow-lg active:scale-95 text-sm"
                >
                  알림 받기 설정
                </button>
              ) : (
                <button
                  onClick={() => setActiveTab("all")}
                  className="px-6 py-3 bg-slate-950 text-white rounded-lg font-bold hover:bg-indigo-600 transition-all shadow-lg active:scale-95 text-sm"
                >
                  전체 보기
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-6 pb-20">
              {filteredMatches.map((res, idx) => (
                <div
                  key={res.announcement_id ?? idx}
                  className="animate-in fade-in slide-in-from-bottom-6 duration-700"
                  style={{ animationDelay: `${idx * 80}ms` }}
                >
                  <ResultCard
                    res={res}
                    selected={isPublic ? false : selectedIds.has(res.announcement_id)}
                    onToggle={isPublic ? undefined : () => toggleSelect(res.announcement_id)}
                    planStatus={isPublic ? null : planStatus}
                    onUpgrade={isPublic ? undefined : onUpgrade}
                    onLoginRequired={isPublic ? onLoginRequired : undefined}
                  />
                </div>
              ))}
            </div>
          )}

          {selectedIds.size > 0 && (
            <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-slate-950 text-white px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3 animate-in slide-in-from-bottom-4 duration-300 w-[calc(100%-2rem)] max-w-sm sm:w-auto sm:max-w-none">
              <span className="text-sm font-bold whitespace-nowrap">☑ {selectedIds.size}건 선택</span>
              <button
                onClick={handleBulkSave}
                disabled={saving}
                className="flex-1 sm:flex-none px-4 py-2 bg-indigo-600 rounded-lg text-sm font-bold hover:bg-indigo-500 transition-all active:scale-95 disabled:opacity-50 whitespace-nowrap"
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

      {/* 하단 플로팅 로그인 바 (비로그인 모바일) */}
      {isPublic && (
        <div className="fixed bottom-0 left-0 right-0 z-50 lg:hidden animate-in slide-in-from-bottom duration-500">
          <div className="bg-white/95 backdrop-blur-xl border-t border-slate-200/80 shadow-[0_-4px_20px_rgba(0,0,0,0.08)] px-3 py-2.5 safe-bottom">
            <div className="flex items-center gap-2 max-w-lg mx-auto">
              <span className="text-[11px] font-bold text-slate-600 whitespace-nowrap flex-shrink-0">무료 시작</span>
              <button
                onClick={() => window.location.href = `${API}/api/auth/social/kakao`}
                className="flex-1 py-2 bg-[#FEE500] text-[#191919] rounded-lg text-[11px] font-bold flex items-center justify-center gap-1 hover:brightness-95 transition-all active:scale-[0.98]"
              >
                💬 카카오
              </button>
              <button
                onClick={() => window.location.href = `${API}/api/auth/social/naver`}
                className="flex-1 py-2 bg-[#03C75A] text-white rounded-lg text-[11px] font-bold flex items-center justify-center gap-1 hover:brightness-95 transition-all active:scale-[0.98]"
              >
                N 네이버
              </button>
              <button
                onClick={() => onLoginRequired?.()}
                className="py-2 px-3 bg-slate-900 text-white rounded-lg text-[11px] font-bold hover:bg-indigo-600 transition-all active:scale-[0.98] flex-shrink-0"
              >
                가입
              </button>
            </div>
          </div>
        </div>
      )}

      <NotificationModal
        isOpen={isNotifyOpen}
        onClose={() => setIsNotifyOpen(false)}
        businessNumber={profile?.business_number}
        onSave={() => {}}
      />
      <SmartDocModal />
    </div>
  );
}
