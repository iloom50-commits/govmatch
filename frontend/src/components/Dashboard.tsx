"use client";

import ResultCard from "./ResultCard";
import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import NotificationModal from "./NotificationModal";
import SmartDocModal from "./SmartDocModal";
import ProDashboard from "./ProDashboard";
import { useToast } from "@/components/ui/Toast";

// 맞춤형 알림 버튼 + 말풍선 안내
function NudgeBubbleButton({ profile, onClick }: { profile: any; onClick: () => void }) {
  const [showBubble, setShowBubble] = useState(false);
  const isIndividual = profile?.user_type === "individual";
  const isIncomplete = !isIndividual && (
    !profile?.industry_code || profile?.industry_code === "00000" ||
    !profile?.address_city || profile?.address_city === "전국"
  );

  useEffect(() => {
    if (!isIncomplete) return;
    const shown = localStorage.getItem("profile_nudge_shown");
    if (!shown) return; // 모달이 아직 안 뜬 상태면 말풍선 불필요

    // 30초 후 말풍선 표시, 10초 유지 → 5분마다 반복 (최대 3회)
    let count = 0;
    const show = () => {
      if (count >= 3) return;
      setShowBubble(true);
      count++;
      setTimeout(() => setShowBubble(false), 10000);
    };
    const timer1 = setTimeout(show, 30000);
    const timer2 = setInterval(show, 300000);
    return () => { clearTimeout(timer1); clearInterval(timer2); };
  }, [isIncomplete]);

  return (
    <div className="relative z-10">
      {showBubble && (
        <div className="absolute -top-12 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-indigo-700 text-white text-[11px] font-bold rounded-full whitespace-nowrap shadow-lg animate-bounce z-20">
          맞춤 설정하면 AI가 자동 추천!
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-indigo-700 rotate-45" />
        </div>
      )}
      <button
        onClick={onClick}
        className="w-full py-2 bg-indigo-50 text-indigo-700 rounded-lg font-bold flex items-center justify-center gap-2 hover:bg-indigo-100 transition-all border border-indigo-100 active:scale-95 text-xs"
      >
        <span className="text-sm">🔔</span>
        <span className="tracking-tight">맞춤형 알림 요청</span>
      </button>
    </div>
  );
}

// 비로그인 CTA 버튼 + 말풍선
function PublicNudgeButton({ onClick }: { onClick: () => void }) {
  const [showBubble, setShowBubble] = useState(false);

  useEffect(() => {
    let count = 0;
    const show = () => {
      if (count >= 3) return;
      setShowBubble(true);
      count++;
      setTimeout(() => setShowBubble(false), 8000);
    };
    const timer1 = setTimeout(show, 15000);
    const timer2 = setInterval(show, 120000);
    return () => { clearTimeout(timer1); clearInterval(timer2); };
  }, []);

  return (
    <div className="relative z-10">
      {showBubble && (
        <div className="absolute -top-10 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-indigo-700 text-white text-[11px] font-bold rounded-full whitespace-nowrap shadow-lg animate-bounce z-20">
          가입 즉시 7일 무료체험!
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-indigo-700 rotate-45" />
        </div>
      )}
      <button
        onClick={onClick}
        className="w-full py-2 bg-indigo-600 text-white rounded-lg font-bold flex items-center justify-center gap-1.5 hover:bg-indigo-700 transition-all active:scale-95 text-xs shadow-md"
      >
        <span className="text-sm">🔔</span>
        <span className="tracking-tight">(무료가입) AI맞춤 알림</span>
      </button>
    </div>
  );
}

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

/** 토글형 공유 버튼 — 클릭 시 옵션이 펼쳐지는 아코디언 */
function ShareToggle({ label, getUrl, shareText, toast }: { label: string; getUrl: () => string; shareText: string; toast: (msg: string, type?: "success" | "error" | "info") => void }) {
  const [open, setOpen] = useState(false);
  const url = typeof window !== "undefined" ? getUrl() : "";
  return (
    <div className="relative z-10 space-y-1.5">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full py-2 bg-gradient-to-r from-indigo-50 to-violet-50 text-slate-700 rounded-lg font-bold flex items-center justify-center gap-2 hover:from-indigo-100 hover:to-violet-100 transition-all border border-indigo-100/60 active:scale-95 text-xs"
      >
        <span className="text-sm">📢</span>
        <span className="tracking-tight">{label}</span>
        <span className={`text-[10px] transition-transform ${open ? "rotate-180" : ""}`}>▼</span>
      </button>
      {open && (
        <div className="grid grid-cols-4 gap-1.5 animate-in slide-in-from-top-2 duration-200">
          <button
            onClick={() => {
              if (typeof window !== "undefined" && (window as any).Kakao?.Share) {
                (window as any).Kakao.Share.sendDefault({
                  objectType: "feed",
                  content: {
                    title: "지원금AI — 지원금 찾지 마세요. AI가 구석구석 찾아드림",
                    description: shareText,
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
            <span className="text-[10px] font-semibold text-yellow-800">카카오톡</span>
          </button>
          <button
            onClick={() => {
              const smsBody = encodeURIComponent(`${shareText} ${url}`);
              window.location.href = `sms:?&body=${smsBody}`;
            }}
            className="flex flex-col items-center gap-1 py-2 bg-green-50 rounded-lg hover:bg-green-100 transition-all active:scale-95 border border-green-200/60"
          >
            <span className="text-base">📱</span>
            <span className="text-[10px] font-semibold text-green-800">문자</span>
          </button>
          <button
            onClick={() => {
              if (navigator.share) {
                navigator.share({ title: "지원금AI — 지원금 찾지 마세요. AI가 구석구석 찾아드림", text: shareText, url });
              } else {
                navigator.clipboard.writeText(`${shareText} ${url}`).then(() => toast("공유 텍스트가 복사되었습니다!", "success"));
              }
            }}
            className="flex flex-col items-center gap-1 py-2 bg-blue-50 rounded-lg hover:bg-blue-100 transition-all active:scale-95 border border-blue-200/60"
          >
            <span className="text-base">📤</span>
            <span className="text-[10px] font-semibold text-blue-800">더보기</span>
          </button>
          <button
            onClick={() => {
              navigator.clipboard.writeText(url).then(() => toast("링크가 복사되었습니다!", "success"));
            }}
            className="flex flex-col items-center gap-1 py-2 bg-violet-50 rounded-lg hover:bg-violet-100 transition-all active:scale-95 border border-violet-200/60"
          >
            <span className="text-base">🔗</span>
            <span className="text-[10px] font-semibold text-violet-800">링크복사</span>
          </button>
        </div>
      )}
    </div>
  );
}

export default function Dashboard({ matches, profile, onEditProfile, onLogout, planStatus, onUpgrade, consultantResult, onClearConsultant, isPublic, onLoginRequired, onRefresh, categoryCountsBiz, categoryCountsInd }: { matches: MatchItem[], profile: any, onEditProfile: () => void, onLogout: () => void, planStatus?: PlanStatus | null, onUpgrade?: () => void, consultantResult?: { matches: any[]; profile: any } | null, onClearConsultant?: () => void, isPublic?: boolean, onLoginRequired?: () => void, onRefresh?: () => void, categoryCountsBiz?: Record<string, number>, categoryCountsInd?: Record<string, number> }) {
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
  const [currentPage, setCurrentPage] = useState(1);
  const ITEMS_PER_PAGE = 20;
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isPwaInstalled, setIsPwaInstalled] = useState(false);
  const [isIos, setIsIos] = useState(false);
  const [isAndroid, setIsAndroid] = useState(false);
  const [iosBannerDismissed, setIosBannerDismissed] = useState(false);
  const [androidBannerDismissed, setAndroidBannerDismissed] = useState(false);
  const [showInstallGuide, setShowInstallGuide] = useState(false);
  // URL 파라미터에서 검색어 읽기 (블로그 연동)
  const urlQ = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("q") || "" : "";
  const [searchQuery, setSearchQuery] = useState(urlQ);
  const [searchResults, setSearchResults] = useState<MatchItem[] | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showProDashboard, setShowProDashboard] = useState(false);
  const [showMyMenu, setShowMyMenu] = useState(false);
  const [totalAnnouncementCount, setTotalAnnouncementCount] = useState(0);

  // DB 전체 공고 수 조회
  useEffect(() => {
    (async () => {
      try {
        const [r1, r2] = await Promise.all([
          fetch(`${API}/api/announcements/public?page=1&size=1&target_type=business`),
          fetch(`${API}/api/announcements/public?page=1&size=1&target_type=individual`),
        ]);
        const d1 = await r1.json();
        const d2 = await r2.json();
        setTotalAnnouncementCount((d1.total || 0) + (d2.total || 0));
      } catch {}
    })();
  }, []);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    } else if (/Android/i.test(ua)) {
      setIsAndroid(true);
      const dismissed = sessionStorage.getItem("android_pwa_dismissed");
      if (dismissed) setAndroidBannerDismissed(true);
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

  // 백엔드 검색 API 호출 (debounce 500ms)
  const doSearch = useCallback((q: string, tab: MajorTab) => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (!q.trim()) { setSearchResults(null); setSearchLoading(false); return; }
    setSearchLoading(true);
    searchTimer.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `${API}/api/announcements/public?page=1&size=100&search=${encodeURIComponent(q.trim())}&target_type=${tab}`
        );
        const data = await res.json();
        if (data.status === "SUCCESS" && data.data?.length > 0) {
          setSearchResults(data.data);
        } else {
          setSearchResults(null); // fallback to local filter
        }
      } catch {
        setSearchResults(null); // fallback to local filter
      }
      setSearchLoading(false);
    }, 500);
  }, []);

  // searchQuery 또는 majorTab 변경 시 검색 실행
  useEffect(() => {
    doSearch(searchQuery, majorTab);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [searchQuery, majorTab, doSearch]);

  // FAB에서 "고객 관리" 클릭 시 ProDashboard 열기
  useEffect(() => {
    const handler = () => setShowProDashboard(true);
    window.addEventListener("open-pro-dashboard", handler);
    return () => window.removeEventListener("open-pro-dashboard", handler);
  }, []);

  // 자유AI 채팅에서 공고 링크 클릭 시 → 검색으로 해당 공고 표시
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.title) {
        // 공고 제목의 핵심 키워드로 검색 (너무 긴 제목은 앞 20자만)
        const keyword = detail.title.replace(/\[.*?\]/g, "").trim().slice(0, 20);
        setSearchQuery(keyword);
        // 상단으로 스크롤
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    };
    window.addEventListener("highlight-announcement", handler);
    return () => window.removeEventListener("highlight-announcement", handler);
  }, []);

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

  // 탭/검색 변경 시 페이지 리셋
  useEffect(() => { setCurrentPage(1); }, [majorTab, activeTab, searchQuery]);

  // 사이드바 열릴 때 body 스크롤 잠금
  useEffect(() => {
    if (sidebarOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [sidebarOpen]);

  const isFree = !planStatus || planStatus.plan === "free" || planStatus.plan === "expired";

  const toggleSelect = (id: number) => {
    if (isFree) {
      toast("공고 저장은 LITE 플랜부터 이용 가능합니다.", "info");
      onUpgrade?.();
      return;
    }
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleBulkSave = async () => {
    if (!bn || selectedIds.size === 0) return;
    if (isFree) {
      toast("공고 저장은 LITE 플랜부터 이용 가능합니다.", "info");
      onUpgrade?.();
      return;
    }
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

  // 검색어가 있으면 백엔드 결과 사용, 없으면 로컬 필터링 fallback
  const baseMatches = useMemo(() => {
    if (!searchQuery.trim()) return displayMatches;
    if (searchResults) return searchResults;
    // fallback: 백엔드 결과 없으면 로컬 필터링
    const q = searchQuery.trim().toLowerCase();
    return displayMatches.filter(m =>
      (m.title || "").toLowerCase().includes(q) ||
      (m.summary_text || "").toLowerCase().includes(q) ||
      (m.department || "").toLowerCase().includes(q) ||
      (m.category || "").toLowerCase().includes(q)
    );
  }, [searchQuery, searchResults, displayMatches]);

  const filteredMatches = useMemo(() => {
    let result = [...baseMatches];

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

    // 검색 중이면 백엔드 관련성 정렬 유지
    // 비로그인(isPublic)이고 "최신"이면 API 정렬(지원금 우선) 유지
    if (!searchQuery.trim()) {
      if (sortKey === "latest" && !isPublic) {
        result.sort((a, b) => b.announcement_id - a.announcement_id);
      } else if (sortKey === "deadline") {
        result.sort((a, b) => {
          if (!a.deadline_date) return 1;
          if (!b.deadline_date) return -1;
          return new Date(a.deadline_date).getTime() - new Date(b.deadline_date).getTime();
        });
      }
    }

    return result;
  }, [baseMatches, activeTab, sortKey, currentTabs, searchQuery]);

  const searchedMatches = baseMatches;

  const tabCounts = useMemo(() => {
    // majorTab에 따라 해당 target_type의 카테고리 건수 사용
    const activeCounts = majorTab === "business" ? categoryCountsBiz : categoryCountsInd;
    if (activeCounts && Object.keys(activeCounts).length > 0) {
      const counts: Record<string, number> = { all: Object.values(activeCounts).reduce((a, b) => a + b, 0) };
      currentTabs.forEach((g: { key: string; categories: string[] }) => {
        if (g.key === "all") return;
        counts[g.key] = g.categories.reduce((sum, gc) => {
          const gcLower = gc.toLowerCase();
          for (const [cat, cnt] of Object.entries(activeCounts)) {
            if (cat.toLowerCase().includes(gcLower) || gcLower.includes(cat.toLowerCase())) {
              sum += cnt;
            }
          }
          return sum;
        }, 0);
      });
      return counts;
    }
    const counts: Record<string, number> = { all: searchedMatches.length };
    currentTabs.forEach((g: { key: string; categories: string[] }) => {
      if (g.key === "all") return;
      counts[g.key] = searchedMatches.filter(m => {
        const cat = (m.category || "").trim();
        return g.categories.some((gc: string) => cat.toLowerCase().includes(gc.toLowerCase()));
      }).length;
    });
    return counts;
  }, [searchedMatches, currentTabs, majorTab, categoryCountsBiz, categoryCountsInd]);

  // 비로그인 사이드바 (프로그램 소개 + CTA)
  const PublicSidebarContent = () => (
    <div className="glass p-5 rounded-2xl space-y-4 shadow-xl border border-white/40 overflow-hidden w-full max-w-full box-border relative">
      <div className="absolute -top-16 -right-16 w-32 h-32 bg-indigo-500/10 blur-[50px] rounded-full pointer-events-none" />
      <div className="absolute -bottom-16 -left-16 w-32 h-32 bg-violet-500/10 blur-[50px] rounded-full pointer-events-none" />

      {/* 핵심 기능 소개 */}
      <div className="relative z-10 space-y-2 pt-1">
        {[
          { icon: "🎯", title: "AI 맞춤 매칭", desc: "내 조건에 딱 맞는 공고만" },
          { icon: "💬", title: "지원대상 즉시 판별", desc: "공고별 자격요건 AI 정밀 분석" },
          { icon: "📝", title: "AI 신청서 자동작성", desc: "공고 양식 학습 후 자동 작성" },
          { icon: "🔔", title: "마감 D-day 알림", desc: "놓치지 않는 맞춤형 알림" },
        ].map((item) => (
          <div key={item.title} className="flex items-center gap-3 px-3 py-2.5 bg-white/60 rounded-xl border border-slate-100/80">
            <span className="text-lg flex-shrink-0">{item.icon}</span>
            <div>
              <p className="text-[12px] font-bold text-slate-800">{item.title}</p>
              <p className="text-[11px] text-slate-500 font-medium">{item.desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* 통계 */}
      <div className="relative z-10 px-4 py-3 bg-indigo-50/80 rounded-xl border border-indigo-100/60 text-center">
        <p className="text-[11px] text-indigo-500 font-bold uppercase tracking-widest mb-1">AI가 분석한 지원사업</p>
        <p className="text-xl font-black text-indigo-700">{(totalAnnouncementCount > 0 ? totalAnnouncementCount : 14000).toLocaleString()}건+</p>
      </div>

      {/* CTA 버튼 */}
      <PublicNudgeButton onClick={() => onLoginRequired?.()} />

      {/* 서비스 공유 */}
      <ShareToggle
        label="친구에게 알려주기"
        getUrl={() => window.location.origin}
        shareText="지원금 찾지 마세요. AI가 구석구석 찾아드림 — 지원금AI에서 확인해보세요!"
        toast={toast}
      />

      <a
        href="/api-partnership"
        className="relative z-10 w-full py-2 bg-slate-50 text-slate-500 rounded-lg font-bold flex items-center justify-center gap-1.5 hover:bg-indigo-50 hover:text-indigo-600 transition-all border border-slate-100 active:scale-95 text-xs"
      >
        <span className="text-sm">🤝</span>
        <span className="tracking-tight">API 제공 · 협업 제안 하기</span>
      </a>
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
            : planStatus.plan === "lite" || planStatus.plan === "lite_trial" || planStatus.plan === "basic"
            ? "bg-indigo-50 border-indigo-200"
            : planStatus.plan === "expired"
            ? "bg-rose-50 border-rose-200"
            : "bg-slate-50 border-slate-200"
        }`}>
          <div className="flex items-center justify-between mb-1.5">
            <span className={`text-[11px] font-bold uppercase tracking-widest ${
              planStatus.plan === "pro" || planStatus.plan === "biz"
                ? "text-violet-600"
                : planStatus.plan === "lite" || planStatus.plan === "lite_trial" || planStatus.plan === "basic"
                ? "text-indigo-600"
                : planStatus.plan === "expired"
                ? "text-rose-600"
                : "text-slate-500"
            }`}>
              {planStatus.label}
            </span>
            {planStatus.days_left != null && planStatus.days_left > 0 && (
              <span className="text-[11px] font-semibold text-slate-400">
                {((planStatus.plan === "pro" && planStatus.days_left <= 7) || (planStatus.plan === "lite" && planStatus.days_left <= 30)) ? "무료체험 " : ""}D-{planStatus.days_left}
              </span>
            )}
          </div>
          {/* 기능별 상태 요약 */}
          <div className="space-y-1.5 mb-2">
            {/* 공고AI 상담 */}
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-500 font-medium">공고AI 상담</span>
              <span className={`font-bold ${
                (planStatus.consult_limit || 0) >= 999999 ? "text-emerald-600" :
                (planStatus.consult_limit || 0) > 0 ? "text-amber-600" : "text-slate-400"
              }`}>
                {(planStatus.consult_limit || 0) >= 999999 ? "무제한" : (planStatus.consult_limit || 0) > 0 ? `월 ${planStatus.consult_limit}회` : "LITE부터"}
              </span>
            </div>
            {/* 저장/알림 */}
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-500 font-medium">저장 · 알림</span>
              <span className={`font-bold ${isFree ? "text-slate-400" : "text-emerald-600"}`}>
                {isFree ? "LITE부터" : "사용 가능"}
              </span>
            </div>
            {/* 자유AI + 컨설턴트 */}
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-500 font-medium">자유AI · 컨설턴트</span>
              <span className={`font-bold ${
                (planStatus.ai_limit || 0) >= 999999 ? "text-violet-600" : "text-slate-400"
              }`}>
                {(planStatus.ai_limit || 0) >= 999999 ? "무제한" : "PRO 전용"}
              </span>
            </div>
            {/* 전문가 에이전트 */}
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-500 font-medium">전문가 에이전트</span>
              <span className={`font-bold ${
                ["pro", "biz"].includes(planStatus.plan) ? "text-violet-600" : "text-slate-400"
              }`}>
                {["pro", "biz"].includes(planStatus.plan) ? "사용 가능" : "PRO 전용"}
              </span>
            </div>
          </div>
          {!["pro", "biz"].includes(planStatus.plan) && onUpgrade && (
            <button
              onClick={onUpgrade}
              className="w-full py-1.5 bg-amber-500 text-white rounded-lg text-[11px] font-bold hover:bg-amber-600 transition-all active:scale-95"
            >
              {planStatus.plan === "expired" ? "플랜 시작하기" : ["lite", "basic"].includes(planStatus.plan) ? "PRO 업그레이드" : "업그레이드"}
            </button>
          )}
          {/* PRO 전문가 에이전트 → FAB의 "전문가 상담 에이전트"로 통합 */}
          {/* 구독 해지 → 마이페이지로 이동 */}
        </div>
      )}

      {profile?.referral_code && (
        <div className="relative z-10 space-y-1.5">
          <ShareToggle
            label="친구에게 추천하기"
            getUrl={() => `${window.location.origin}?ref=${profile.referral_code}`}
            shareText="지원금 찾지 마세요. AI가 구석구석 찾아드림 — 지원금AI에서 확인해보세요!"
            toast={toast}
          />
          {(profile?.merit_months || 0) > 0 && (
            <p className="text-center text-[11px] text-violet-500 font-bold">
              추천 적립 {profile.merit_months}개월
            </p>
          )}
        </div>
      )}

      <NudgeBubbleButton
        profile={profile}
        onClick={() => { setIsNotifyOpen(true); setSidebarOpen(false); }}
      />

      {/* PWA 설치는 우측 상단 버튼으로 통합 — 로그인 후 사이드바에서도 제거 */}

      {/* PWA 설치 안내 — 우측 상단 버튼으로 통합, 사이드바 제거 */}

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
            <span className="tracking-tight">마이페이지</span>
          </button>
          <a
            href="/calendar"
            className="py-2 bg-indigo-50 text-indigo-700 rounded-lg font-bold flex items-center justify-center gap-1.5 hover:bg-indigo-100 transition-all border border-indigo-100 active:scale-95 text-xs"
          >
            <span className="text-sm">📅</span>
            <span className="tracking-tight">일정 관리</span>
          </a>
        </div>
        {/* 드롭다운 제거 — 마이페이지 클릭 시 바로 ProfileSettings 모달 열림 */}
        <a
          href="/api-partnership"
          onClick={() => setSidebarOpen(false)}
          className="w-full py-2 bg-slate-50 text-slate-500 rounded-lg font-bold flex items-center justify-center gap-1.5 hover:bg-indigo-50 hover:text-indigo-600 transition-all border border-slate-100 active:scale-95 text-xs"
        >
          <span className="text-sm">🤝</span>
          <span className="tracking-tight">API 제공 · 협업 제안 하기</span>
        </a>
      </div>
    </div>
  );

  return (
    <div className="w-full max-w-[1280px] mx-auto animate-in fade-in slide-in-from-bottom-6 duration-700 px-1 sm:px-2 lg:px-0 overflow-x-clip">

      {/* 모바일 상단 지원금AI 로고 제거 — 검색창 위 로고와 중복 */}

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
        <aside className="hidden lg:block lg:sticky lg:top-6 lg:self-start lg:max-h-[calc(100vh-3rem)] lg:overflow-hidden">
          {isPublic ? <PublicSidebarContent /> : <SidebarContent />}
        </aside>

        <main className="space-y-4 lg:space-y-5 pb-16 lg:pb-16 min-w-0">
          {/* 모바일 비로그인 하단 플로팅 CTA (lg 미만) */}

          {/* 컨설턴트 매칭 → 내 매칭 복원 버튼 */}
          {consultantResult && (
            <div className="flex justify-end">
              <button
                onClick={onClearConsultant}
                className="px-3 py-1.5 bg-white border border-violet-200 text-violet-700 rounded-lg text-[11px] font-bold hover:bg-violet-50 transition-all active:scale-95"
              >
                내 매칭으로 돌아가기
              </button>
            </div>
          )}

          {/* 대분류 탭 — 밑줄(underline) 스타일 */}
          <div className="-mx-3 md:-mx-6 px-3 md:px-6 mb-5 border-b border-slate-200">
            <div className="flex items-center gap-6">
              {([
                { key: "business" as MajorTab, label: "기업 지원금", icon: "🏢", show: showBusinessTab, color: "indigo" },
                { key: "individual" as MajorTab, label: "개인 지원금", icon: "👤", show: showIndividualTab, color: "emerald" },
              ]).map((tab) => {
                if (!tab.show) return null;
                const isActive = majorTab === tab.key;
                return (
                  <button
                    key={tab.key}
                    onClick={() => { setMajorTab(tab.key); setActiveTab("all"); }}
                    className={`relative flex items-center gap-1.5 pb-3 pt-1 text-sm font-bold transition-all duration-200 ${
                      isActive
                        ? "text-slate-900"
                        : "text-slate-400 hover:text-slate-600"
                    }`}
                  >
                    <span>{tab.icon}</span>
                    {tab.label}
                    {/* 활성 밑줄 */}
                    {isActive && (
                      <span className={`absolute bottom-0 left-0 right-0 h-[3px] rounded-t-full ${
                        tab.color === "indigo" ? "bg-indigo-600" : "bg-emerald-600"
                      }`} />
                    )}
                  </button>
                );
              })}
              {/* 지원금AI 설치 */}
              {!isPwaInstalled && (
                <button
                  onClick={() => {
                    if (deferredPrompt) handlePwaInstall();
                    else setShowInstallGuide(true);
                  }}
                  className="ml-auto flex items-center justify-center gap-1.5 py-2 px-4 text-[13px] font-black text-indigo-600 hover:text-white hover:bg-indigo-600 bg-indigo-50 border border-indigo-200 rounded-full transition-all whitespace-nowrap active:scale-95 leading-none"
                >
                  <span className="text-[13px]">⬇️</span><span>지원금AI 설치</span>
                </button>
              )}
            </div>
          </div>

          <header className="space-y-3">
            <h2 className="text-base sm:text-lg md:text-xl lg:text-2xl font-bold text-slate-950 tracking-tighter leading-tight flex flex-wrap items-baseline gap-1.5 sm:gap-3">
              <span className="brand-badge brand-go-hover"><span className="brand-name">지원금</span><span className="brand-go">AI</span></span>
              <span className="text-[11px] sm:text-xs md:text-sm font-medium text-slate-500 tracking-normal">
                AI가 구석구석 모든 지원금을 찾아서 알려 드립니다
              </span>
            </h2>

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
              {searchLoading && (
                <div className="w-3.5 h-3.5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
              )}
              {searchQuery && !searchLoading && (
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
              <div className="relative sm:hidden flex-shrink-0">
                <select
                  value={activeTab}
                  onChange={(e) => setActiveTab(e.target.value)}
                  className={`w-full appearance-none px-3 py-2 pr-8 rounded-lg text-[11px] font-bold outline-none cursor-pointer border-2 ${
                    majorTab === "business"
                      ? "bg-white text-slate-800 border-slate-300"
                      : "bg-white text-emerald-800 border-emerald-300"
                  }`}
                >
                  {currentTabs.map((tab) => {
                    const count = tabCounts[tab.key] || 0;
                    if (tab.key !== "all" && count === 0) return null;
                    return (
                      <option key={tab.key} value={tab.key}>
                        {tab.label} ({count.toLocaleString()})
                      </option>
                    );
                  })}
                </select>
                <svg className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-400 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </div>

              {/* Desktop: 하위 카테고리 탭 — 가로 스크롤 */}
              <div className="hidden sm:flex items-center gap-1 overflow-x-auto scrollbar-hide min-w-0 flex-1">
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
                        {count.toLocaleString()}
                      </span>
                    </button>
                  );
                })}
              </div>

              <div className="flex-shrink-0 h-6 w-px bg-slate-200" />

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
                {onRefresh && (
                  <button
                    onClick={onRefresh}
                    className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all active:scale-95"
                    title="공고 새로고침"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
                    </svg>
                  </button>
                )}
              </div>
            </div>

          </header>

          {searchQuery.trim() && !searchLoading && searchResults && (
            <p className="text-xs text-slate-500 font-medium mb-2 px-1">
              &quot;{searchQuery.trim()}&quot; 검색 결과 <span className="font-bold text-indigo-600">{filteredMatches.length}건</span>
            </p>
          )}

          {filteredMatches.length === 0 && !searchLoading ? (
            <div className="flex flex-col items-center justify-center py-12 md:py-20 px-6 text-center bg-white/40 backdrop-blur-xl rounded-2xl border border-white/60 shadow-lg animate-in zoom-in duration-500 w-full">
              {/* 봇 캐릭터 — 컴퓨터 치는 장면 */}
              {!searchQuery.trim() && matches.length === 0 ? (
                <div className="mb-5">
                  <svg width="120" height="100" viewBox="0 0 70 60" fill="none" style={{ overflow: "visible", filter: "drop-shadow(0 4px 8px rgba(0,0,0,0.15))" }}>
                    <path d="M 5 50 L 65 50" stroke="#06B6D4" strokeWidth="2" opacity="0.6" style={{ filter: "drop-shadow(0 0 4px #22D3EE)" }} />
                    <path d="M 10 54 L 60 54" stroke="#06B6D4" strokeWidth="1" opacity="0.3" />
                    <ellipse cx="20" cy="46" rx="10" ry="2" fill="#22D3EE" opacity="0.1" style={{ filter: "blur(2px)" }} />
                    <path d="M 40 48 L 46 22 L 66 22 L 60 48 Z" fill="#0EA5E9" opacity="0.1" />
                    <path d="M 40 48 L 46 22 L 66 22 L 60 48 Z" stroke="#22D3EE" strokeWidth="1" opacity="0.8" style={{ filter: "drop-shadow(0 0 2px #22D3EE)" }} />
                    <g style={{ transform: "skewX(-13deg)" }}>
                      <rect x="52" y="26" width="10" height="2" rx="1" fill="#22D3EE" opacity="0.9" style={{ animation: "codeLine 1.5s ease-in-out infinite" }} />
                      <rect x="52" y="30" width="14" height="2" rx="1" fill="#67E8F9" opacity="0.7" style={{ animation: "codeLine 1.5s 0.3s ease-in-out infinite" }} />
                      <rect x="52" y="34" width="8" height="2" rx="1" fill="#22D3EE" opacity="0.8" style={{ animation: "codeLine 1.5s 0.6s ease-in-out infinite" }} />
                      <rect x="52" y="38" width="12" height="2" rx="1" fill="#BAE6FD" opacity="0.6" style={{ animation: "codeLine 1.5s 0.9s ease-in-out infinite" }} />
                    </g>
                    <line x1="22" y1="6" x2="22" y2="12" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" />
                    <circle cx="22" cy="6" r="3" fill="#22D3EE" style={{ filter: "drop-shadow(0 0 4px #22D3EE)" }} className="animate-pulse" />
                    <g style={{ transformOrigin: "22px 24px", animation: "headBob 2s ease-in-out infinite" }}>
                      <path d="M12 20 C 12 14, 32 14, 32 20 L 34 28 C 34 32, 30 34, 22 34 C 14 34, 10 32, 10 28 Z" fill="#1E293B" stroke="#334155" strokeWidth="1" />
                      <path d="M14 22 C 14 20, 30 20, 30 22 L 30 26 C 30 28, 14 28, 14 26 Z" fill="#0F172A" />
                      <path d="M16 23 C 16 22, 28 22, 28 23 L 28 25 C 28 26, 16 26, 16 25 Z" fill="#22D3EE" opacity="0.8" style={{ filter: "drop-shadow(0 0 6px #06B6D4)" }} />
                      <line x1="18" y1="24" x2="26" y2="24" stroke="white" strokeWidth="2" strokeDasharray="3 2" strokeLinecap="round" opacity="0.9" style={{ animation: "particleFade 1s infinite alternate" }} />
                    </g>
                    <path d="M16 38 L 28 38 L 30 46 C 30 48, 26 50, 22 50 C 18 50, 14 48, 14 46 Z" fill="#334155" stroke="#475569" strokeWidth="1" />
                    <circle cx="22" cy="46" r="2" fill="#22D3EE" style={{ filter: "drop-shadow(0 0 2px #22D3EE)" }} />
                    <path d="M 28 48 Q 36 46 44 48" stroke="#06B6D4" strokeWidth="2" fill="none" opacity="0.6" style={{ filter: "drop-shadow(0 0 3px #06B6D4)" }} />
                    <g style={{ transformOrigin: "16px 40px", animation: "typingLeft 0.3s ease-in-out infinite alternate" }}>
                      <path d="M16 40 C 12 40, 14 46, 28 47" stroke="#64748B" strokeWidth="3" fill="none" strokeLinecap="round" />
                    </g>
                    <g style={{ transformOrigin: "28px 40px", animation: "typingRight 0.3s 0.15s ease-in-out infinite alternate" }}>
                      <path d="M28 40 C 32 40, 38 44, 38 47" stroke="#64748B" strokeWidth="3" fill="none" strokeLinecap="round" />
                    </g>
                  </svg>
                </div>
              ) : (
                <div className="w-14 h-14 bg-slate-100 rounded-full flex items-center justify-center text-3xl mb-5 animate-pulse">🔍</div>
              )}
              <h2 className="text-lg md:text-2xl font-bold text-slate-900 mb-3">
                {searchQuery.trim()
                  ? `"${searchQuery.trim()}" 검색 결과가 없습니다`
                  : matches.length === 0
                    ? "AI가 공고를 찾고 있습니다..."
                    : "조건에 맞는 공고가 없습니다"}
              </h2>
              <p className="text-xs md:text-base text-slate-500 max-w-lg mx-auto mb-6 font-medium leading-relaxed">
                {searchQuery.trim()
                  ? "다른 키워드로 검색하거나 검색어를 초기화해 보세요."
                  : matches.length === 0
                  ? "잠시만 기다려주세요. 맞춤 공고를 분석하고 있습니다."
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
            <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-6 pb-6 overflow-hidden">
              {filteredMatches.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE).map((res, idx) => (
                <div
                  key={`${res.announcement_id}-${idx}`}
                  className="animate-in fade-in slide-in-from-bottom-6 duration-700"
                  style={{ animationDelay: `${Math.min(idx, 10) * 80}ms` }}
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
            {(() => {
              const totalPages = Math.ceil(filteredMatches.length / ITEMS_PER_PAGE);
              if (totalPages <= 1) return <div className="pb-20" />;
              const maxVisible = 7;
              let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
              let endPage = startPage + maxVisible - 1;
              if (endPage > totalPages) { endPage = totalPages; startPage = Math.max(1, endPage - maxVisible + 1); }
              const pages = Array.from({ length: endPage - startPage + 1 }, (_, i) => startPage + i);
              const goTo = (p: number) => { setCurrentPage(p); window.scrollTo({ top: 0, behavior: "smooth" }); };
              return (
                <div className="flex items-center justify-center gap-1.5 py-6 pb-20">
                  <button
                    onClick={() => goTo(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="px-3 py-2 text-sm font-bold rounded-lg border border-slate-200 bg-white text-slate-500 hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                  >
                    이전
                  </button>
                  {pages.map(p => (
                    <button
                      key={p}
                      onClick={() => goTo(p)}
                      className={`w-9 h-9 text-sm font-bold rounded-lg transition-all ${
                        p === currentPage
                          ? "bg-indigo-600 text-white shadow-md"
                          : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
                      }`}
                    >
                      {p}
                    </button>
                  ))}
                  <button
                    onClick={() => goTo(currentPage + 1)}
                    disabled={currentPage === totalPages}
                    className="px-3 py-2 text-sm font-bold rounded-lg border border-slate-200 bg-white text-slate-500 hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                  >
                    다음
                  </button>
                </div>
              );
            })()}
            </>
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

      {/* 플로팅 버튼 (모바일) — 좌측 하단 */}
      {isPublic ? (
        <button
          onClick={() => onLoginRequired?.()}
          className="fixed bottom-6 left-4 z-50 lg:hidden bg-indigo-600 text-white px-4 py-3 rounded-full shadow-[0_4px_20px_rgba(79,70,229,0.4)] hover:bg-indigo-700 active:scale-95 transition-all animate-in slide-in-from-bottom duration-500 flex items-center gap-2"
        >
          <span className="text-base">🚀</span>
          <span className="text-xs font-bold">무료 가입</span>
        </button>
      ) : (
        <button
          onClick={() => setSidebarOpen(true)}
          className="fixed bottom-6 left-4 z-50 lg:hidden bg-slate-800 text-white px-4 py-3 rounded-full shadow-[0_4px_20px_rgba(30,41,59,0.4)] hover:bg-slate-900 active:scale-95 transition-all animate-in slide-in-from-bottom duration-500 flex items-center gap-2"
        >
          <span className="text-base">👤</span>
          <span className="text-xs font-bold">내 정보</span>
        </button>
      )}

      <NotificationModal
        isOpen={isNotifyOpen}
        onClose={() => setIsNotifyOpen(false)}
        businessNumber={profile?.business_number}
        onSave={() => {}}
        profile={profile}
      />
      <SmartDocModal />

      {/* PRO 전문가 에이전트 */}
      {showProDashboard && (
        <ProDashboard onClose={() => setShowProDashboard(false)} />
      )}

      {/* 앱 설치 안내 모달 */}
      {showInstallGuide && (
        <div className="fixed inset-0 z-[9999] flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={() => setShowInstallGuide(false)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div
            className="relative bg-white w-full sm:max-w-sm rounded-t-2xl sm:rounded-2xl p-5 pb-8 sm:pb-5 shadow-2xl animate-[slideUp_0.3s_ease-out]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 핸들바 (모바일) */}
            <div className="sm:hidden w-10 h-1 bg-slate-300 rounded-full mx-auto mb-4" />
            <button
              onClick={() => setShowInstallGuide(false)}
              className="absolute top-3 right-3 w-7 h-7 flex items-center justify-center rounded-full bg-slate-100 text-slate-400 hover:text-slate-600 text-sm"
            >✕</button>

            <div className="text-center mb-4">
              <span className="text-3xl">📲</span>
              <h3 className="text-base font-black text-slate-900 mt-2">앱으로 설치하면 더 편해요</h3>
            </div>

            <div className="space-y-2.5 mb-5">
              <div className="flex items-start gap-2.5 p-2.5 bg-indigo-50 rounded-lg">
                <span className="text-lg mt-0.5">🔔</span>
                <div>
                  <p className="text-[12px] font-bold text-slate-800">맞춤 알림 수신</p>
                  <p className="text-[11px] text-slate-500">새 지원금 공고가 등록되면 즉시 알려드려요</p>
                </div>
              </div>
              <div className="flex items-start gap-2.5 p-2.5 bg-emerald-50 rounded-lg">
                <span className="text-lg mt-0.5">⚡</span>
                <div>
                  <p className="text-[12px] font-bold text-slate-800">빠른 실행</p>
                  <p className="text-[11px] text-slate-500">홈 화면에서 한 번 터치로 바로 접속</p>
                </div>
              </div>
              <div className="flex items-start gap-2.5 p-2.5 bg-amber-50 rounded-lg">
                <span className="text-lg mt-0.5">📱</span>
                <div>
                  <p className="text-[12px] font-bold text-slate-800">앱처럼 사용</p>
                  <p className="text-[11px] text-slate-500">주소창 없이 전체 화면으로 깔끔하게</p>
                </div>
              </div>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <p className="text-[11px] font-bold text-slate-700 mb-2">설치 방법</p>
              {isIos ? (
                <div className="flex items-center gap-2.5">
                  <div className="flex items-center justify-center w-8 h-8 bg-indigo-100 rounded-lg shrink-0">
                    <span className="text-base">□↑</span>
                  </div>
                  <p className="text-[11px] text-slate-600 leading-relaxed">
                    Safari 하단 <span className="font-bold text-indigo-600">공유 버튼(□↑)</span>을 누른 뒤<br/>
                    <span className="font-bold text-indigo-600">&quot;홈 화면에 추가&quot;</span>를 선택하세요
                  </p>
                </div>
              ) : (
                <div className="flex items-center gap-2.5">
                  <div className="flex items-center justify-center w-8 h-8 bg-indigo-100 rounded-lg shrink-0">
                    <span className="text-base font-bold">⋮</span>
                  </div>
                  <p className="text-[11px] text-slate-600 leading-relaxed">
                    Chrome 우측 상단 <span className="font-bold text-indigo-600">메뉴(⋮)</span>를 누른 뒤<br/>
                    <span className="font-bold text-indigo-600">&quot;홈 화면에 추가&quot;</span> 또는 <span className="font-bold text-indigo-600">&quot;앱 설치&quot;</span>를 선택하세요
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
