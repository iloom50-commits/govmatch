"use client";

import ResultCard from "./ResultCard";
import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { createPortal, flushSync } from "react-dom";
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

// 마이페이지 버튼 + 프로필 미완성 말풍선
function ProfileNudgeButton({ profile, onClick }: { profile: any; onClick: () => void }) {
  const [showBubble, setShowBubble] = useState(false);
  const isIncomplete = !profile?.user_type || (
    profile?.user_type !== "individual" && (
      !profile?.industry_code || profile?.industry_code === "00000"
    )
  );

  useEffect(() => {
    if (!isIncomplete) return;
    let count = 0;
    const show = () => {
      if (count >= 3) return;
      setShowBubble(true);
      count++;
      setTimeout(() => setShowBubble(false), 8000);
    };
    const timer1 = setTimeout(show, 20000);
    const timer2 = setInterval(show, 180000);
    return () => { clearTimeout(timer1); clearInterval(timer2); };
  }, [isIncomplete]);

  return (
    <div className="relative">
      {showBubble && (
        <div className="absolute -top-10 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-indigo-700 text-white text-[11px] font-bold rounded-full whitespace-nowrap shadow-lg animate-bounce z-20">
          프로필 설정하면 맞춤 추천!
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-indigo-700 rotate-45" />
        </div>
      )}
      <button
        onClick={onClick}
        className="w-full py-2 bg-slate-950 text-white rounded-lg font-bold flex items-center justify-center gap-1.5 hover:bg-indigo-600 transition-all shadow-lg active:scale-95 text-xs"
      >
        <span className="text-sm">⚙️</span>
        <span className="tracking-tight">마이페이지</span>
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
    bucket?: string;
    bucket_label?: string;
    reasons?: { icon: string; label: string }[];
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

type SortKey = "recommend" | "amount" | "deadline";

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

  // OS 네이티브 공유 시트 (안드로이드/iOS) → 사용자가 카카오톡 등을 직접 선택
  // Kakao SDK는 도메인 mismatch 시 카톡 로그인 화면으로 빠지는 문제가 있어 사용 안 함.
  const shareKakao = () => {
    if (typeof window === "undefined") return;
    if (navigator.share) {
      navigator.share({ title: "지원금AI", text: shareText, url }).catch(() => {});
    } else {
      navigator.clipboard.writeText(`${shareText} ${url}`).then(
        () => toast("링크가 복사되었습니다!", "success"),
        () => toast("복사에 실패했습니다.", "error")
      );
    }
    setOpen(false);
  };

  return (
    <>
      <button
        onClick={() => {
          // 모바일·태블릿: OS 네이티브 공유 시트 즉시 호출 (인기공고 추천하기와 동일 UX)
          if (typeof navigator !== "undefined" && (navigator as any).share) {
            (navigator as any).share({ title: "지원금AI", text: shareText, url }).catch(() => {});
          } else {
            // 데스크톱 PC 등 미지원 환경: 커스텀 모달 표시
            setOpen(true);
          }
        }}
        className="relative z-10 w-full py-2 bg-gradient-to-r from-indigo-50 to-violet-50 text-slate-700 rounded-lg font-bold flex items-center justify-center gap-2 hover:from-indigo-100 hover:to-violet-100 transition-all border border-indigo-100/60 active:scale-95 text-xs"
      >
        <span className="text-sm">📢</span>
        <span className="tracking-tight">{label}</span>
      </button>

      {open && typeof document !== "undefined" && createPortal(
        <div className="fixed inset-0 z-[70] flex items-end sm:items-center justify-center" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[2px]" />
          <div
            className="relative w-full max-w-sm mx-auto bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl overflow-hidden animate-in slide-in-from-bottom sm:zoom-in-95 duration-300"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-5">
              <div className="text-center mb-5">
                <h3 className="text-[15px] font-bold text-slate-900">친구에게 추천하기</h3>
                <p className="text-[11px] text-slate-400 mt-1">추천 시 양쪽 모두 LITE 1개월 무료!</p>
              </div>
              <div className="grid grid-cols-4 gap-3">
                <button onClick={shareKakao} className="flex flex-col items-center gap-2 py-3 rounded-xl hover:bg-yellow-50 transition-all active:scale-95">
                  <div className="w-14 h-14 bg-[#FEE500] rounded-2xl flex items-center justify-center shadow-sm">
                    <span className="text-2xl">💬</span>
                  </div>
                  <span className="text-[11px] font-bold text-slate-700">카카오톡</span>
                </button>
                <button onClick={() => { window.location.href = `sms:?&body=${encodeURIComponent(shareText + " " + url)}`; setOpen(false); }} className="flex flex-col items-center gap-2 py-3 rounded-xl hover:bg-green-50 transition-all active:scale-95">
                  <div className="w-14 h-14 bg-emerald-500 rounded-2xl flex items-center justify-center shadow-sm">
                    <span className="text-2xl">💌</span>
                  </div>
                  <span className="text-[11px] font-bold text-slate-700">문자</span>
                </button>
                <button onClick={() => { if (navigator.share) navigator.share({ title: "지원금AI", text: shareText, url }); else navigator.clipboard.writeText(`${shareText} ${url}`).then(() => toast("복사됨!", "success")); setOpen(false); }} className="flex flex-col items-center gap-2 py-3 rounded-xl hover:bg-blue-50 transition-all active:scale-95">
                  <div className="w-14 h-14 bg-blue-500 rounded-2xl flex items-center justify-center shadow-sm">
                    <span className="text-2xl">📤</span>
                  </div>
                  <span className="text-[11px] font-bold text-slate-700">더보기</span>
                </button>
                <button onClick={() => { navigator.clipboard.writeText(url).then(() => toast("링크 복사됨!", "success")); setOpen(false); }} className="flex flex-col items-center gap-2 py-3 rounded-xl hover:bg-violet-50 transition-all active:scale-95">
                  <div className="w-14 h-14 bg-violet-500 rounded-2xl flex items-center justify-center shadow-sm">
                    <span className="text-2xl">🔗</span>
                  </div>
                  <span className="text-[11px] font-bold text-slate-700">링크복사</span>
                </button>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="w-full py-3.5 border-t border-slate-100 text-slate-400 text-[13px] font-medium hover:text-slate-600 hover:bg-slate-50 transition-all">
              닫기
            </button>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

export default function Dashboard({ matches, profile, onEditProfile, onLogout, planStatus, onUpgrade, consultantResult, onClearConsultant, isPublic, onLoginRequired, onRefresh, categoryCountsBiz, categoryCountsInd, defaultMajorTab, autoOpenNotify, onNotifyOpened, onPlanUpdate, onProfileRefresh }: { matches: MatchItem[], profile: any, onEditProfile: () => void, onLogout: () => void, planStatus?: PlanStatus | null, onUpgrade?: () => void, consultantResult?: { matches: any[]; profile: any } | null, onClearConsultant?: () => void, isPublic?: boolean, onLoginRequired?: () => void, onRefresh?: () => void, categoryCountsBiz?: Record<string, number>, categoryCountsInd?: Record<string, number>, defaultMajorTab?: MajorTab, autoOpenNotify?: boolean, onNotifyOpened?: () => void, onPlanUpdate?: (updated: any) => void, onProfileRefresh?: () => void }) {
  const { toast } = useToast();
  // 사용자 유형에 따라 초기 대분류 탭 결정
  const userType = profile?.user_type || "both";
  const initialMajor: MajorTab = defaultMajorTab || (userType === "individual" ? "individual" : "business");
  const [majorTab, setMajorTab] = useState<MajorTab>(initialMajor);
  const [activeTab, setActiveTab] = useState("all");
  // 탭 전환 — View Transitions API (미지원 브라우저는 즉시 전환)
  const switchMajorTab = (next: MajorTab) => {
    if (next === majorTab) return;
    const apply = () => { setMajorTab(next); setActiveTab("all"); };
    // PC(마우스 호버 가능 + 정밀 포인터)에서는 View Transitions API 잔상 이슈로 즉시 전환
    // 모바일(터치)에서만 슬라이드 애니메이션 사용
    const isDesktop = typeof window !== "undefined"
      && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    if (isDesktop) {
      apply();
      return;
    }
    try {
      const doc = document as any;
      if (typeof doc.startViewTransition === "function") {
        doc.documentElement.setAttribute("data-vt-dir", next === "business" ? "right" : "left");
        doc.startViewTransition(() => {
          flushSync(apply);
        });
      } else {
        apply();
      }
    } catch {
      apply();
    }
  };
  // 모바일 좌우 스와이프로 기업/개인 탭 전환 — 손 떼는 순간 판정 (View Transitions API 사용)
  const swipeStartX = useRef<number | null>(null);
  const swipeStartY = useRef<number | null>(null);
  const handleTabSwipeStart = (e: React.TouchEvent) => {
    swipeStartX.current = e.touches[0].clientX;
    swipeStartY.current = e.touches[0].clientY;
  };
  const handleTabSwipeEnd = (e: React.TouchEvent) => {
    if (swipeStartX.current == null || swipeStartY.current == null) return;
    const dx = e.changedTouches[0].clientX - swipeStartX.current;
    const dy = e.changedTouches[0].clientY - swipeStartY.current;
    swipeStartX.current = null;
    swipeStartY.current = null;
    if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
    if (dx < 0 && majorTab === "business") switchMajorTab("individual");
    else if (dx > 0 && majorTab === "individual") switchMajorTab("business");
  };
  const currentTabs = majorTab === "business" ? BUSINESS_TABS : INDIVIDUAL_TABS;

  // 탭 노출: 모든 사용자에게 전체 탭 표시 (열람은 자유, AI매칭/알림만 user_type 기반)
  const showBusinessTab = true;
  const showIndividualTab = true;
  const [sortKey, setSortKey] = useState<SortKey>("recommend");
  const [isNotifyOpen, setIsNotifyOpen] = useState(false);
  // 프로필 미완성(로그인O) → NotificationModal, 비로그인 → onLoginRequired
  const handleLoginRequired = () => {
    if (profile) { setIsNotifyOpen(true); } else { onLoginRequired?.(); }
  };
  // 외부에서 NotificationModal 열기 요청
  useEffect(() => {
    if (autoOpenNotify) { setIsNotifyOpen(true); onNotifyOpened?.(); }
  }, [autoOpenNotify]);
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
  const [isInAppBrowser, setIsInAppBrowser] = useState(false); // 카톡/네이버/라인 등 인앱 브라우저
  const [iosBannerDismissed, setIosBannerDismissed] = useState(false);
  const [androidBannerDismissed, setAndroidBannerDismissed] = useState(false);
  const [showInstallGuide, setShowInstallGuide] = useState(false);
  // URL 파라미터에서 검색어 읽기 (블로그 연동)
  const urlQ = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("q") || "" : "";
  const urlAid = typeof window !== "undefined" ? Number(new URLSearchParams(window.location.search).get("aid")) || 0 : 0;
  const [highlightAid, setHighlightAid] = useState(urlAid);
  const [searchQuery, setSearchQuery] = useState(urlQ);
  const [searchResults, setSearchResults] = useState<MatchItem[] | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showProDashboard, setShowProDashboard] = useState(false);
  const [showMyMenu, setShowMyMenu] = useState(false);
  const [totalAnnouncementCount, setTotalAnnouncementCount] = useState(0);

  // 공유 링크로 접속 시 해당 카드로 스크롤 + 하이라이트
  useEffect(() => {
    if (!highlightAid) return;
    // 여러 번 시도 (데이터 로드 타이밍에 따라)
    const tryScroll = (delay: number) => setTimeout(() => {
      const el = document.querySelector(`[data-aid="${highlightAid}"]`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    }, delay);
    const t1 = tryScroll(1500);
    const t2 = tryScroll(3000);
    const t3 = tryScroll(5000);
    const fadeTimer = setTimeout(() => setHighlightAid(0), 8000);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(fadeTimer); };
  }, [highlightAid]);

  // 오늘의 인기 공고 — majorTab(기업/개인) 따라 분기
  const [trendingItems, setTrendingItems] = useState<any[]>([]);
  useEffect(() => {
    const _token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : "";
    fetch(`${API}/api/trending?target_type=${majorTab}`, {
      headers: _token ? { Authorization: `Bearer ${_token}` } : {},
    }).then(r => r.json()).then(d => {
      if (d.data) setTrendingItems(d.data);
    }).catch(() => {});
  }, [majorTab]);

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
    // 인앱 브라우저 감지 (카카오톡/네이버/라인/페북/인스타 등 — PWA 설치 미지원)
    const inApp = /KAKAOTALK|NAVER|Line|FBAN|FBAV|Instagram|; wv\)|EveryTalk/i.test(ua);
    setIsInAppBrowser(inApp);
    // iOS 카톡 인앱 진입 시 자동으로 설치 안내 모달 오픈 (Android는 layout.tsx 인라인 스크립트가 자동 전환)
    if (inApp && isiOS) {
      const shown = sessionStorage.getItem("ios_inapp_guide_shown");
      if (!shown) {
        setShowInstallGuide(true);
        sessionStorage.setItem("ios_inapp_guide_shown", "1");
      }
    }
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
    if (!bn || !profile) return;
    const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
    if (!token) return;
    try {
      const res = await fetch(`${API}/api/saved/${bn}`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      if (data.status === "SUCCESS") setSavedItems(data.data);
    } catch { /* silent */ }
  }, [bn, profile]);

  useEffect(() => { fetchSaved(); }, [fetchSaved]);

  // 탭/검색 변경 시 페이지 리셋
  useEffect(() => { if (!isPublic) setCurrentPage(1); }, [majorTab, activeTab, searchQuery]);

  // 비로그인: Dashboard에서 직접 API 호출
  const [publicData, setPublicData] = useState<any[]>([]);
  const [publicServerTotal, setPublicServerTotal] = useState(0);
  const publicCache = useRef<Record<string, { data: any[]; total: number }>>({});

  const usePublicData = isPublic || (!isPublic && matches.length === 0);

  useEffect(() => {
    if (!usePublicData) return;
    const targetType = majorTab === "business" ? "business" : "individual";
    const group = currentTabs.find((t: { key: string }) => t.key === activeTab);
    const catKeyword = activeTab === "all" ? "" : (group?.categories?.find((c: string) => /[가-힣]/.test(c)) || group?.categories?.[0] || "");
    const search = searchQuery.trim();
    const page = currentPage;

    const cacheKey = `${targetType}:${catKeyword}:${page}:${search}`;
    if (publicCache.current[cacheKey]) {
      setPublicData(publicCache.current[cacheKey].data);
      setPublicServerTotal(publicCache.current[cacheKey].total);
      return;
    }

    let url = `${API}/api/announcements/public?page=${page}&size=${ITEMS_PER_PAGE}&target_type=${targetType}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    else if (catKeyword) url += `&category=${encodeURIComponent(catKeyword)}`;

    fetch(url)
      .then(r => r.json())
      .then(d => {
        if (d.status === "SUCCESS") {
          setPublicData(d.data || []);
          setPublicServerTotal(d.total || 0);
          publicCache.current[cacheKey] = { data: d.data || [], total: d.total || 0 };
        }
      })
      .catch(() => {});
  }, [isPublic, majorTab, activeTab, currentPage, searchQuery]);

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
      const token = localStorage.getItem("auth_token") || "";
      const res = await fetch(`${API}/api/saved/bulk`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
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
    // 비로그인 또는 프로필 미완성: 서버에서 이미 필터링/정렬된 데이터 사용
    const _parseAmount = (s: string) => {
      if (!s) return 0;
      let n = 0;
      const m1 = s.match(/(\d[\d,.]*)\s*억/);
      if (m1) n += parseFloat(m1[1].replace(/,/g, "")) * 100000000;
      const m2 = s.match(/(\d[\d,.]*)\s*만/);
      if (m2) n += parseFloat(m2[1].replace(/,/g, "")) * 10000;
      if (n === 0) {
        const m3 = s.match(/(\d[\d,.]+)/);
        if (m3) n = parseFloat(m3[1].replace(/,/g, ""));
      }
      return n;
    };

    if (usePublicData && publicData.length > 0) {
      let result = [...publicData];
      if (sortKey === "amount") {
        result.sort((a, b) => _parseAmount(b.support_amount || "") - _parseAmount(a.support_amount || ""));
      } else if (sortKey === "deadline") {
        result.sort((a, b) => {
          if (!a.deadline_date) return 1;
          if (!b.deadline_date) return -1;
          return new Date(a.deadline_date).getTime() - new Date(b.deadline_date).getTime();
        });
      }
      return result;
    }

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

    if (!searchQuery.trim()) {
      if (sortKey === "recommend") {
        // 맞춤추천: 서버에서 버킷 순서대로 정렬됨 — match_score는 순서 보존용
        result.sort((a, b) => (b.match_score || 0) - (a.match_score || 0));
      } else if (sortKey === "amount") {
        result.sort((a, b) => _parseAmount(b.support_amount || "") - _parseAmount(a.support_amount || ""));
      } else if (sortKey === "deadline") {
        result.sort((a, b) => {
          if (!a.deadline_date) return 1;
          if (!b.deadline_date) return -1;
          return new Date(a.deadline_date).getTime() - new Date(b.deadline_date).getTime();
        });
      }
    }

    return result;
  }, [baseMatches, activeTab, sortKey, currentTabs, searchQuery, isPublic, publicData]);

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
      <PublicNudgeButton onClick={handleLoginRequired} />

      {/* 서비스 공유 */}
      <ShareToggle
        label="친구에게 알려주기"
        getUrl={() => window.location.origin}
        shareText="17,000+ 정부 지원금 공고를 AI가 실시간 분석·자동 매칭해줘요. 기업·개인 모두 무료!"
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

      {/* 프로필 미완성: 설정 유도 카드 / 완성: 기업 정보 카드 */}
      {(() => {
        const ut = profile?.user_type || "both";
        const _city = profile?.address_city ? String(profile.address_city).split(",").filter((c: string) => c && c !== "전국")[0] : "";
        const hasProfile = !!(
          _city || profile?.age_range || profile?.gender || profile?.income_level ||
          profile?.family_type || profile?.employment_status || profile?.revenue_bracket ||
          profile?.employee_count_bracket || profile?.founded_date || profile?.is_pre_founder ||
          (profile?.certifications && String(profile.certifications).length > 0) ||
          (profile?.interests && String(profile.interests).length > 0)
        );
        if (!hasProfile) return (
          <div className="relative z-10 p-5 bg-gradient-to-br from-indigo-50 to-violet-50 rounded-xl border border-indigo-100/80 shadow-sm">
            <div className="text-center space-y-3">
              <div className="w-12 h-12 mx-auto bg-indigo-100 rounded-xl flex items-center justify-center text-2xl">
                {ut === "individual" ? "👤" : "🏢"}
              </div>
              <div>
                <p className="text-[15px] font-bold text-slate-900">프로필을 설정해보세요</p>
                <p className="text-[12px] text-slate-500 mt-1">내 조건을 입력하면 AI가 딱 맞는 지원금을 찾아드려요</p>
              </div>
              <button
                onClick={() => { setIsNotifyOpen(true); setSidebarOpen(false); }}
                className="w-full py-2.5 bg-indigo-600 text-white rounded-lg font-bold text-xs hover:bg-indigo-700 transition-all active:scale-95 shadow-sm"
              >
                프로필 설정하기
              </button>
            </div>
          </div>
        );
        // 개인 사용자: 개인 정보 카드
        if (ut === "individual") return (
          <div className="relative z-10 p-5 bg-white/60 rounded-xl border border-slate-100/80 shadow-sm">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-10 h-10 bg-indigo-100 rounded-lg flex-shrink-0 flex items-center justify-center text-lg shadow">👤</div>
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-bold text-slate-900 tracking-tight truncate">{profile?.company_name || profile?.email?.split("@")[0] || "회원"}</p>
                <span className="px-1.5 py-px bg-blue-50 text-blue-600 text-[11px] font-bold rounded border border-blue-100/50 mt-0.5 w-fit">개인</span>
              </div>
            </div>
            <div className="h-px bg-slate-100 mb-4" />
            <div className="grid grid-cols-[56px_1fr] gap-y-3.5 text-[13px]">
              <span className="text-slate-400">연령대</span>
              <span className="font-semibold text-slate-800">{profile?.age_range || "미설정"}</span>
              <span className="text-slate-400">지역</span>
              <span className="font-semibold text-slate-800">{profile?.address_city || "미설정"}</span>
              <span className="text-slate-400">관심분야</span>
              <span className="font-semibold text-slate-800">{profile?.interests || "미설정"}</span>
            </div>
          </div>
        );
        // 기업/both 사용자: 기업 정보 카드
        return (
          <div className="relative z-10 p-5 bg-white/60 rounded-xl border border-slate-100/80 shadow-sm">
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
            <div className="h-px bg-slate-100 mb-4" />
            <div className="grid grid-cols-[56px_1fr] gap-y-3.5 text-[13px]">
              <span className="text-slate-400">설립</span>
              <span className="font-semibold text-slate-800">{profile?.establishment_date ? String(profile.establishment_date).slice(0, 10) : "미설정"}</span>
              <span className="text-slate-400">소재지</span>
              <span className="font-semibold text-slate-800">{profile?.address_city || "미설정"}</span>
              <span className="text-slate-400">업종</span>
              <span className="font-semibold text-slate-800 break-words">{industryDisplayName || (profile?.industry_code && profile.industry_code !== "00000" ? profile.industry_code : "미설정")}</span>
              <span className="text-slate-400">매출</span>
              <span className="font-semibold text-slate-800">{REVENUE_KR[profile?.revenue_bracket] || REVENUE_KR[profile?.revenue] || profile?.revenue_bracket || "미설정"}</span>
              <span className="text-slate-400">인원</span>
              <span className="font-semibold text-slate-800">{EMPLOYEE_KR[profile?.employee_count_bracket] || profile?.employee_count_bracket || "미설정"}</span>
            </div>
          </div>
        );
      })()}

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
                {(planStatus.consult_limit || 0) >= 999999 ? "무제한" : (planStatus.consult_limit || 0) > 0 ? `${planStatus.ai_used || 0}/${planStatus.consult_limit}회` : "LITE부터"}
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
              <span className="text-slate-500 font-medium">지원사업 상담 AI</span>
              <span className={`font-bold ${
                (planStatus.ai_limit || 0) >= 999999 ? "text-violet-600" : "text-slate-400"
              }`}>
                {(planStatus.ai_limit || 0) >= 999999 ? "무제한" : "PRO 전용"}
              </span>
            </div>
            {/* 고객사 관리 AI */}
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-500 font-medium">고객사 관리 AI</span>
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
          {/* PRO 고객사 관리 AI → FAB의 "전문가 상담 에이전트"로 통합 */}
          {/* 구독 해지 → 마이페이지로 이동 */}
        </div>
      )}

      {profile?.referral_code && (
        <div className="relative z-10 space-y-1.5">
          <ShareToggle
            label="친구에게 추천하기"
            getUrl={() => `${window.location.origin}?ref=${profile.referral_code}`}
            shareText="17,000+ 정부 지원금 공고를 AI가 실시간 분석·자동 매칭해줘요. 기업·개인 모두 무료!"
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
          <ProfileNudgeButton
            profile={profile}
            onClick={() => { onEditProfile(); setSidebarOpen(false); }}
          />
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
      {(profile || !isPublic) && sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 모바일 드로어 패널 */}
      {(profile || !isPublic) && (
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
        <aside className="hidden lg:block lg:sticky lg:top-6 lg:self-start lg:max-h-[calc(100vh-3rem)] lg:overflow-y-auto scrollbar-hide">
          {isPublic && !profile ? <PublicSidebarContent /> : <SidebarContent />}
        </aside>

        <main
          className="space-y-4 lg:space-y-5 pb-16 lg:pb-16 min-w-0"
          onTouchStart={handleTabSwipeStart}
          onTouchEnd={handleTabSwipeEnd}
        >
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

          {/* 대분류 탭 — 밑줄(underline) 스타일, 스크롤 시 상단 고정 */}
          <div className="sticky top-0 z-30 -mx-3 md:-mx-6 px-3 md:px-6 mb-5 border-b border-slate-200 bg-slate-50/95 backdrop-blur-md">
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
                    onClick={() => switchMajorTab(tab.key)}
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

          <div style={{ viewTransitionName: "major-tab" } as React.CSSProperties}>
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
                  { key: "recommend" as SortKey, label: "맞춤추천" },
                  { key: "amount" as SortKey, label: "금액순" },
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

          {filteredMatches.length === 0 && !searchLoading && !(usePublicData && publicData.length === 0 && !searchQuery.trim()) ? (
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
            {/* 오늘의 인기 공고 — 일반 카드와 동일 형태 + 오렌지 테두리 + 2건 */}
            {trendingItems.length > 0 && (
              <div className="mb-6">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-lg">🔥</span>
                  <h3 className="text-[15px] font-bold text-slate-800">오늘의 인기 공고</h3>
                  <span className="text-[11px] text-slate-400">네이버 검색 트렌드 기반 선정</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-6">
                  {trendingItems.slice(0, 2).map((t) => (
                    <div
                      key={t.announcement_id}
                      className="rounded-xl ring-2 ring-orange-400/70 ring-offset-1"
                    >
                      <ResultCard
                        res={t}
                        planStatus={isPublic && !profile ? null : planStatus}
                        onUpgrade={isPublic && !profile ? undefined : onUpgrade}
                        onLoginRequired={isPublic && !profile ? handleLoginRequired : undefined}
                        highlight={highlightAid === t.announcement_id}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-6 pb-6 overflow-hidden">
              {(usePublicData && publicData.length > 0 ? filteredMatches : filteredMatches.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE)).map((res, idx) => (
                <div
                  key={`${res.announcement_id}-${idx}`}
                  className="animate-in fade-in slide-in-from-bottom-6 duration-700"
                  style={{ animationDelay: `${Math.min(idx, 10) * 80}ms` }}
                >
                  <ResultCard
                    res={res}
                    selected={isPublic ? false : selectedIds.has(res.announcement_id)}
                    onToggle={isPublic ? undefined : () => toggleSelect(res.announcement_id)}
                    planStatus={isPublic && !profile ? null : planStatus}
                    onUpgrade={isPublic && !profile ? undefined : onUpgrade}
                    onLoginRequired={isPublic && !profile ? handleLoginRequired : undefined}
                    highlight={highlightAid === res.announcement_id}
                  />
                </div>
              ))}
            </div>
            {(() => {
              const totalItems = (usePublicData && publicServerTotal > 0) ? publicServerTotal : filteredMatches.length;
              const totalPages = Math.ceil(totalItems / ITEMS_PER_PAGE);
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
          </div>
        </main>
      </div>

      {/* 플로팅 버튼 (모바일) — 좌측 하단 */}
      {isPublic && !profile ? (
        <button
          onClick={handleLoginRequired}
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
        onSave={() => { onProfileRefresh?.(); onRefresh?.(); }}
        profile={profile}
      />
      <SmartDocModal />

      {/* PRO 고객사 관리 AI */}
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

            {isInAppBrowser ? (
              /* 카톡/네이버/라인 등 인앱 브라우저 — PWA 설치 불가, 외부 브라우저로 유도 */
              <>
                <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 mb-3">
                  <p className="text-[12px] font-bold text-amber-700 mb-1">⚠ 카카오톡 브라우저에서는 설치할 수 없어요</p>
                  <p className="text-[11px] text-amber-600 leading-relaxed">
                    Chrome(안드로이드) 또는 Safari(아이폰)에서 열어야 설치 가능합니다.
                  </p>
                </div>
                <button
                  onClick={() => {
                    // 안드로이드: intent URL로 Chrome 강제 실행
                    if (/Android/i.test(navigator.userAgent)) {
                      window.location.href = "intent://govmatch.kr#Intent;scheme=https;package=com.android.chrome;end";
                    } else {
                      // iOS: 카톡 인앱 브라우저는 Safari로 자동 전환 불가
                      // 사용자에게 우측 상단 메뉴에서 "다른 브라우저로 열기" 선택 안내
                      alert("화면 우측 상단 ⋮(또는 ⋯) 메뉴를 누르고\n'다른 브라우저로 열기' 또는 'Safari로 열기'를 선택해주세요.");
                    }
                  }}
                  className="w-full py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white text-[13px] font-bold rounded-xl hover:opacity-90 transition-all active:scale-[0.98] flex items-center justify-center gap-2"
                >
                  🌐 외부 브라우저에서 열기
                </button>
                <div className="mt-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <p className="text-[11px] font-bold text-slate-700 mb-2">또는 수동으로:</p>
                  <p className="text-[11px] text-slate-600 leading-relaxed">
                    화면 우측 상단 <span className="font-bold text-indigo-600">⋮ 메뉴</span> →<br/>
                    <span className="font-bold text-indigo-600">&quot;다른 브라우저로 열기&quot;</span> 선택<br/>
                    → Chrome/Safari에서 설치하기
                  </p>
                </div>
              </>
            ) : (
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
            )}
          </div>
        </div>
      )}
    </div>
  );
}
