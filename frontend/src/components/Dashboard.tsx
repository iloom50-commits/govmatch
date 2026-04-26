"use client";

import ResultCard from "./ResultCard";
import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { createPortal, flushSync } from "react-dom";
import NotificationModal from "./NotificationModal";
import SmartDocModal from "./SmartDocModal";
import ProDashboard from "./ProDashboard";
import { useToast } from "@/components/ui/Toast";
import { useModalBack } from "@/hooks/useModalBack";

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

// 뉴스 티커 — 공고 리스트 최상단 가로 스크롤


// 마이페이지 버튼 + 스마트 말풍선 (D-3 업그레이드 / 새 맞춤 공고 / 프로필 미완성)
function ProfileNudgeButton({ profile, planStatus, newMatchCount, onClick }: { profile: any; planStatus?: any; newMatchCount?: number; onClick: () => void }) {
  const [showBubble, setShowBubble] = useState(false);
  const [bubbleMsg, setBubbleMsg] = useState("");

  const isIncomplete = !profile?.user_type || (
    profile?.user_type !== "individual" && (
      !profile?.industry_code || profile?.industry_code === "00000"
    )
  );

  // 우선순위: D-3 > 새 공고 N건 > 프로필 미완성
  const getMsg = (): string | null => {
    const plan = planStatus?.plan;
    const daysLeft = planStatus?.days_left;
    if ((plan === "lite" || plan === "lite_trial") && typeof daysLeft === "number" && daysLeft <= 3) {
      return `LITE D-${daysLeft}! 지금 업그레이드하세요`;
    }
    if (newMatchCount && newMatchCount > 0) {
      return `새 맞춤 공고 ${newMatchCount}건 업데이트됐어요`;
    }
    if (isIncomplete) {
      return "프로필 설정하면 맞춤 추천!";
    }
    return null;
  };

  useEffect(() => {
    const msg = getMsg();
    if (!msg) return;
    setBubbleMsg(msg);
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
  }, [isIncomplete, planStatus?.days_left, newMatchCount]);

  return (
    <div className="relative">
      {showBubble && bubbleMsg && (
        <div className="absolute -top-10 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-indigo-700 text-white text-[11px] font-bold rounded-full whitespace-nowrap shadow-lg animate-bounce z-20">
          {bubbleMsg}
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
    match_score?: number;  // 구버전 호환 (deprecated) — rank 사용
    rank?: number;
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

export default function Dashboard({ matches, profile, onEditProfile, onLogout, planStatus, onUpgrade, consultantResult, onClearConsultant, isPublic, onLoginRequired, onRefresh, categoryCountsBiz, categoryCountsInd, defaultMajorTab, autoOpenNotify, onNotifyOpened, onPlanUpdate, onProfileRefresh, onMajorTabChange, onCategoryCountsLoaded }: { matches: MatchItem[], profile: any, onEditProfile: () => void, onLogout: () => void, planStatus?: PlanStatus | null, onUpgrade?: () => void, consultantResult?: { matches: any[]; profile: any } | null, onClearConsultant?: () => void, isPublic?: boolean, onLoginRequired?: () => void, onRefresh?: () => void, categoryCountsBiz?: Record<string, number>, categoryCountsInd?: Record<string, number>, defaultMajorTab?: MajorTab, autoOpenNotify?: boolean, onNotifyOpened?: () => void, onPlanUpdate?: (updated: any) => void, onProfileRefresh?: () => void, onMajorTabChange?: (tab: MajorTab) => void, onCategoryCountsLoaded?: (counts: Record<string, number>, tab: "business" | "individual") => void }) {
  const { toast } = useToast();
  // 사용자 유형에 따라 초기 대분류 탭 결정
  const userType = profile?.user_type || "both";
  const initialMajor: MajorTab = defaultMajorTab || (userType === "individual" ? "individual" : "business");
  const [majorTab, setMajorTab] = useState<MajorTab>(initialMajor);
  const [activeTab, setActiveTab] = useState("all");
  // 탭 전환 — View Transitions API (미지원 브라우저는 즉시 전환)
  const switchMajorTab = (next: MajorTab) => {
    if (next === majorTab) return;
    const apply = () => { setMajorTab(next); setActiveTab("all"); onMajorTabChange?.(next); };
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
  const baseTabs = majorTab === "business" ? BUSINESS_TABS : INDIVIDUAL_TABS;
  // "맞춤 추천" 탭 — 항상 표시
  const currentTabs = [...baseTabs];

  // 탭 노출: 모든 사용자에게 전체 탭 표시 (열람은 자유, AI매칭/알림만 user_type 기반)
  const showBusinessTab = true;
  const showIndividualTab = true;
  const [sortKey, setSortKey] = useState<SortKey>("recommend");
  const [isNotifyOpen, setIsNotifyOpen] = useState(false);
  const [notifyShortcut, setNotifyShortcut] = useState(false);  // true면 모달이 알림 설정만 바로 표시 (프로필 스텝 스킵)
  const [hasNotificationSet, setHasNotificationSet] = useState<boolean>(true);  // 기본 true (깜빡임 방지) — 실제 상태는 API로 확인
  const [showPromoModal, setShowPromoModal] = useState(false);

  // 프로필 완성도 체크 — user_type별로 분리
  const profileCity = profile?.address_city ? String(profile.address_city).split(",").filter((c: string) => c && c !== "전국")[0] : "";
  const profileUserType = profile?.user_type || "individual";
  const hasProfile = (() => {
    if (!profile) return false;
    if (profileUserType === "business") {
      // 기업: 소재지·매출·직원수·업종 중 하나라도 있어야 완성
      return !!(profileCity || profile.revenue_bracket || profile.employee_count_bracket || profile.industry_code);
    }
    if (profileUserType === "individual") {
      return !!(profile.age_range || profile.income_level || profile.family_type || profile.employment_status || profile.gender);
    }
    // both
    const bizOk = !!(profileCity || profile.revenue_bracket || profile.employee_count_bracket || profile.industry_code);
    const indOk = !!(profile.age_range || profile.income_level || profile.family_type || profile.employment_status || profile.gender);
    return bizOk || indOk;
  })();

  // 프로필 미완성(로그인O) → NotificationModal, 비로그인 → onLoginRequired
  const handleLoginRequired = () => {
    if (profile) { setIsNotifyOpen(true); setNotifyShortcut(false); } else { onLoginRequired?.(); }
  };
  // 외부에서 NotificationModal 열기 요청 (props)
  useEffect(() => {
    if (autoOpenNotify) { setIsNotifyOpen(true); setNotifyShortcut(false); onNotifyOpened?.(); }
  }, [autoOpenNotify]);

  // AI챗봇 "지금 채우기" 버튼 → NotificationModal 열기 (레거시 호환)
  useEffect(() => {
    const handler = () => { setIsNotifyOpen(true); setNotifyShortcut(false); };
    window.addEventListener("open-notification-modal", handler);
    return () => window.removeEventListener("open-notification-modal", handler);
  }, []);

  // 프로필 게이트: 프로필 미완성 또는 기업 업종 미설정 시 폼 먼저 → 저장 후 원래 액션 자동 실행
  const pendingActionRef = useRef<(() => void) | null>(null);
  // 기업/both 사용자가 업종 미설정인 경우 ('00000'도 미설정으로 처리)
  const industryNotSet = !profile?.industry_code || profile?.industry_code === "00000";
  const bizNeedsIndustry = (profileUserType === "business" || profileUserType === "both") && industryNotSet;
  const [notifyFromGate, setNotifyFromGate] = useState(false);
  const checkProfileThenRun = useCallback((action: () => void) => {
    if (hasProfile && !bizNeedsIndustry) {
      action();
    } else {
      pendingActionRef.current = action;
      setIsNotifyOpen(true);
      setNotifyShortcut(false);
      setNotifyFromGate(true);
      setSidebarOpen(false);
    }
  }, [hasProfile, bizNeedsIndustry]);

  // request-ai-consult → 프로필 게이트 → open-ai-consult
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      checkProfileThenRun(() => {
        window.dispatchEvent(new CustomEvent("close-fund-chat")); // AiChatBot 닫기
        window.dispatchEvent(new CustomEvent("open-ai-consult", { detail }));
      });
    };
    window.addEventListener("request-ai-consult", handler);
    return () => window.removeEventListener("request-ai-consult", handler);
  }, [checkProfileThenRun]);

  // request-fund-chat → 프로필 게이트 → open-fund-chat
  useEffect(() => {
    const handler = () => {
      checkProfileThenRun(() => {
        window.dispatchEvent(new CustomEvent("open-fund-chat"));
      });
    };
    window.addEventListener("request-fund-chat", handler);
    return () => window.removeEventListener("request-fund-chat", handler);
  }, [checkProfileThenRun]);

  // 맞춤알림 설정 여부 체크 — 미설정 시 빨간 점/배지 노출
  useEffect(() => {
    const bn = profile?.business_number;
    if (!bn) return;
    const _tok = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
    fetch(`${API}/api/notification-settings/${bn}`, {
      headers: _tok ? { Authorization: `Bearer ${_tok}` } : {},
    })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        const active = d?.data?.is_active;
        const hasEmail = !!(d?.data?.email);
        setHasNotificationSet(Boolean(active && hasEmail));
      })
      .catch(() => setHasNotificationSet(true));  // 실패 시 조용히 (배지 안 띄움)
  }, [profile?.business_number, isNotifyOpen]);  // 모달 닫힌 후 재조회
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [savedItems, setSavedItems] = useState<SavedItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const ITEMS_PER_PAGE = 20;
  const [smartMatches, setSmartMatches] = useState<any[]>([]);
  const [smartLoading, setSmartLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isPwaInstalled, setIsPwaInstalled] = useState(false);
  const [isIos, setIsIos] = useState(false);
  const [isAndroid, setIsAndroid] = useState(false);
  // 브라우저 타입 — 설치 가이드 맞춤 안내용 (Samsung/Firefox/Edge/Chrome/Safari 구분)
  type BrowserType = "samsung" | "firefox_android" | "edge_android" | "chrome_android" | "safari_ios" | "chrome_ios" | "chrome_desktop" | "edge_desktop" | "safari_desktop" | "firefox_desktop" | "other";
  const [browserType, setBrowserType] = useState<BrowserType>("other");
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

  // 이메일 ?aid= 링크 접속 시 해당 공고 fetch → 목록 최상단 고정 + 스크롤
  const [pinnedAnnouncement, setPinnedAnnouncement] = useState<MatchItem | null>(null);
  useEffect(() => {
    if (!highlightAid) return;
    // 1) 해당 공고 단건 fetch (목록에 없을 수 있으므로)
    fetch(`${API}/api/announcements/${highlightAid}`)
      .then(r => r.ok ? r.json() : null)
      .then(json => {
        if (json?.data) setPinnedAnnouncement(json.data as MatchItem);
      })
      .catch(() => {});
    // 2) 스크롤 — 여러 번 시도 (데이터 로드 타이밍)
    const tryScroll = (delay: number) => setTimeout(() => {
      const el = document.querySelector(`[data-aid="${highlightAid}"]`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    }, delay);
    const t1 = tryScroll(300);
    const t2 = tryScroll(1500);
    const t3 = tryScroll(3000);
    const fadeTimer = setTimeout(() => { setHighlightAid(0); setPinnedAnnouncement(null); }, 12000);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(fadeTimer); };
  }, [highlightAid]);

  // 오늘의 인기 공고 state/fetch 제거 (사장님 요청)

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

    // 브라우저 타입 판별 (설치 가이드 맞춤 안내용)
    // 체크 순서 중요: SamsungBrowser/Edg/Firefox/OPR 먼저, Chrome은 마지막
    const isAndroidUA = /Android/i.test(ua);
    if (/SamsungBrowser/i.test(ua)) {
      setBrowserType("samsung");
    } else if (/EdgA/i.test(ua)) {
      setBrowserType("edge_android");
    } else if (/EdgiOS/i.test(ua)) {
      setBrowserType("chrome_ios"); // iOS Edge는 Safari WebView 기반 — iOS 공유 버튼으로 안내
    } else if (/FxiOS/i.test(ua)) {
      setBrowserType("chrome_ios"); // iOS Firefox도 Safari WebView — iOS 공유 버튼으로 안내
    } else if (/CriOS/i.test(ua)) {
      setBrowserType("chrome_ios"); // iOS Chrome — Safari WebView 기반
    } else if (isiOS) {
      setBrowserType("safari_ios");
    } else if (isAndroidUA && /Firefox/i.test(ua)) {
      setBrowserType("firefox_android");
    } else if (isAndroidUA && /Chrome/i.test(ua)) {
      setBrowserType("chrome_android");
    } else if (/Edg\//i.test(ua)) {
      setBrowserType("edge_desktop");
    } else if (/Firefox/i.test(ua)) {
      setBrowserType("firefox_desktop");
    } else if (/Safari/i.test(ua) && !/Chrome/i.test(ua)) {
      setBrowserType("safari_desktop");
    } else if (/Chrome/i.test(ua)) {
      setBrowserType("chrome_desktop");
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

  const newMatchCount = 0;

  // 비로그인: Dashboard에서 직접 API 호출
  const [publicData, setPublicData] = useState<any[]>([]);
  const [publicServerTotal, setPublicServerTotal] = useState(0);
  const publicCache = useRef<Record<string, { data: any[]; total: number }>>({});

  const usePublicData = true;  // 전체 공고 항상 API 데이터 사용 (일별 로테이션 맞춤 정렬)

  // 서버 데이터 로드
  useEffect(() => {
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

    const _tok = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
    fetch(url, {
      headers: _tok ? { Authorization: `Bearer ${_tok}` } : {},
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === "SUCCESS") {
          setPublicData(d.data || []);
          setPublicServerTotal(d.total || 0);
          publicCache.current[cacheKey] = { data: d.data || [], total: d.total || 0 };
          if (d.total) setTotalAnnouncementCount(prev => prev || d.total);
          if (d.category_counts && onCategoryCountsLoaded) {
            onCategoryCountsLoaded(d.category_counts, targetType as "business" | "individual");
          }
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

  // 모바일 뒤로가기로 사이드바 닫기
  useModalBack(sidebarOpen, () => setSidebarOpen(false));

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
    const thirtyDaysLater = new Date(today);
    thirtyDaysLater.setDate(thirtyDaysLater.getDate() + 30);
    return savedItems
      .filter(s => s.deadline_date && new Date(s.deadline_date) >= today && new Date(s.deadline_date) <= thirtyDaysLater)
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

    // 카테고리 탭이 "전체"가 아닌 경우 → 서버 공고 데이터 사용 (카테고리 필터링은 서버에서)
    if (activeTab !== "all" && publicData.length > 0) {
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

    if (!searchQuery.trim()) {
      if (sortKey === "recommend") {
        // 맞춤추천: 서버에서 버킷 순서대로 정렬됨
        // rank 오름차순 (1등이 앞) — match_score는 deprecated지만 구버전 호환 유지
        result.sort((a, b) => {
          const ra = a.rank ?? (1000 - (a.match_score || 0));
          const rb = b.rank ?? (1000 - (b.match_score || 0));
          return ra - rb;
        });
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

      {/* 🔔 맞춤 알림 카드 — 프로필+알림 둘 다 완료 시 녹색, 하나라도 미완성 시 핑크 CTA */}
      {(() => {
        const _city = profile?.address_city ? String(profile.address_city).split(",").filter((c: string) => c && c !== "전국")[0] : "";
        const _ut = profile?.user_type || "individual";
        const hasProfile = (() => {
          if (!profile) return false;
          if (_ut === "business") return !!(_city || profile.revenue_bracket || profile.employee_count_bracket || profile.industry_code);
          if (_ut === "individual") return !!(profile.age_range || profile.income_level || profile.family_type || profile.employment_status || profile.gender);
          return !!(_city || profile.revenue_bracket || profile.industry_code || profile.age_range || profile.income_level);
        })();
        const allDone = hasProfile && hasNotificationSet;

        if (!profile) return null;

        if (allDone) return (
          <div className="relative z-10 p-4 bg-gradient-to-br from-emerald-50 to-teal-50 rounded-xl border border-emerald-200/80 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 flex-shrink-0 bg-white rounded-xl flex items-center justify-center text-xl shadow-sm">✅</div>
              <div className="flex-1 min-w-0">
                <p className="text-[14px] font-bold text-emerald-800">맞춤 알림 설정 완료</p>
                <p className="text-[11px] text-slate-500 mt-0.5">평일 오전 9시에 맞춤 공고를 받아보고 있어요</p>
              </div>
              <button
                onClick={() => { setNotifyShortcut(false); setIsNotifyOpen(true); setSidebarOpen(false); }}
                className="flex-shrink-0 px-3 py-1.5 text-sm font-bold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-colors"
              >
                수정
              </button>
            </div>
          </div>
        );

        // 프로필 미완성 → 프로필 폼부터 / 프로필 완성+알림 미설정 → 알림 설정만
        const handleCardClick = () => {
          setNotifyShortcut(false);  // 항상 step 0부터 — 핑크 카드는 프로필 미완성 상태
          setIsNotifyOpen(true);
          setSidebarOpen(false);
        };
        const ctaLabel = !hasProfile ? "1분만에 설정하기" : "알림만 켜면 완성!";
        const ctaDesc = !hasProfile
          ? "평일 오전 9시에 내 조건에 맞는 공고를 이메일·푸시로 받아보세요"
          : "프로필은 완성됐어요. 알림만 켜면 맞춤 공고를 받을 수 있어요";

        return (
          <div className="relative z-10 p-4 bg-gradient-to-br from-rose-50 to-amber-50 rounded-xl border border-rose-100/80 shadow-sm">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 flex-shrink-0 bg-white rounded-xl flex items-center justify-center text-xl shadow-sm">🔔</div>
              <div className="flex-1 min-w-0">
                <p className="text-[14px] font-bold text-slate-900">맞춤 알림 켜기</p>
                <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">{ctaDesc}</p>
                <button
                  onClick={handleCardClick}
                  className="mt-2.5 w-full py-2 bg-rose-500 text-white rounded-lg font-bold text-[12px] hover:bg-rose-600 transition-all active:scale-95 shadow-sm"
                >
                  {ctaLabel}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* 프로필 미완성: 설정 유도 카드 / 완성: 기업 정보 카드 */}
      {(() => {
        const ut = profile?.user_type || "both";
        const _city = profile?.address_city ? String(profile.address_city).split(",").filter((c: string) => c && c !== "전국")[0] : "";
        const hasProfile = (() => {
          if (!profile) return false;
          if (ut === "business") return !!(_city || profile.revenue_bracket || profile.employee_count_bracket || profile.industry_code);
          if (ut === "individual") return !!(profile.age_range || profile.income_level || profile.family_type || profile.employment_status || profile.gender);
          return !!(_city || profile.revenue_bracket || profile.industry_code || profile.age_range || profile.income_level);
        })();
        if (!hasProfile) return null;
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
              <span className="font-semibold text-slate-800">{profile?.founded_date || profile?.establishment_date ? String(profile.founded_date || profile.establishment_date).slice(0, 10) : (profile?.is_pre_founder ? "예비창업자" : "미설정")}</span>
              <span className="text-slate-400">소재지</span>
              <span className="font-semibold text-slate-800">{(() => { const c = profile?.address_city; if (!c) return "미설정"; const parts = String(c).split(",").filter((s: string) => s.trim() && s.trim() !== "전국"); return parts[0] || "전국"; })()}</span>
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
            planStatus={planStatus}
            newMatchCount={newMatchCount}
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
        <a
          href="/my/consults"
          onClick={() => setSidebarOpen(false)}
          className="w-full py-2 bg-violet-50 text-violet-700 rounded-lg font-bold flex items-center justify-center gap-1.5 hover:bg-violet-100 transition-all border border-violet-100 active:scale-95 text-xs"
        >
          <span className="text-sm">💬</span>
          <span className="tracking-tight">상담 이력</span>
        </a>
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
    <div className="w-full max-w-[1280px] mx-auto animate-in fade-in duration-700 px-1 sm:px-2 lg:px-0 overflow-x-clip">

      {/* [프로모션 2026-04-22 ~ 2026-05-23] LITE 1개월 무료 배너 */}
      {planStatus && (planStatus.plan === "lite" || planStatus.plan === "lite_trial") && (() => {
        // 2026-05-23까지 남은 일수 계산
        const now = new Date();
        const promoEnd = new Date("2026-05-23T23:59:59");
        const daysLeft = Math.max(0, Math.ceil((promoEnd.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)));
        // 프로모션 기간 종료 시 자동 숨김
        if (daysLeft === 0 || now > promoEnd) return null;
        return (
          <button
            onClick={() => setShowPromoModal(true)}
            className="w-full mb-3 rounded-xl bg-gradient-to-r from-violet-600 via-indigo-600 to-purple-600 text-white px-4 py-3 shadow-md text-left active:scale-[0.99] transition-transform"
          >
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <span className="text-lg">🎁</span>
                <div className="min-w-0">
                  <div className="text-[13px] font-bold truncate">
                    LITE 1개월 무료 체험 중 · D-{daysLeft}
                  </div>
                  <div className="text-[11px] opacity-90 truncate">
                    2026-05-23까지 모든 기능 무료 · 공고AI 상담 · 맞춤 공고 알림
                  </div>
                </div>
              </div>
              <span className="text-[11px] opacity-70 flex-shrink-0">자세히 ›</span>
            </div>
          </button>
        );
      })()}

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
            </div>
          </div>

          <div style={{ viewTransitionName: "major-tab" } as React.CSSProperties}>
          <header className="space-y-3">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <h2 className="text-base sm:text-lg md:text-xl lg:text-2xl font-bold text-slate-950 tracking-tighter leading-tight flex items-baseline gap-1.5 sm:gap-3 flex-wrap">
                <span className="brand-badge brand-go-hover"><span className="brand-name">지원금</span><span className="brand-go">AI</span></span>
                <span className="text-[11px] sm:text-xs md:text-sm font-medium text-slate-500 tracking-normal">
                  전국 모든 지원금
                </span>
              </h2>
              <div className="flex items-center gap-2 flex-shrink-0">
                {/* 🔔 맞춤 알림 켜기 — 데스크탑 전용 compact (미설정 시만, 모바일은 빨간 점 뱃지로 대체) */}
                {profile && !hasNotificationSet && (
                  <button
                    onClick={() => { setNotifyShortcut(hasProfile); setIsNotifyOpen(true); }}
                    className="hidden sm:flex items-center justify-center gap-1.5 py-1.5 px-3 text-[12px] font-black text-rose-600 hover:text-white hover:bg-rose-500 bg-rose-50 border border-rose-200 rounded-full transition-all whitespace-nowrap active:scale-95 leading-none relative"
                    title="맞춤 알림 켜기"
                  >
                    <span className="text-[12px]">🔔</span><span>알림 켜기</span>
                    <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-rose-500 rounded-full ring-2 ring-white animate-pulse" />
                  </button>
                )}
                {/* 지원금AI 설치 */}
                {!isPwaInstalled && (
                  <button
                    onClick={() => {
                      if (deferredPrompt) handlePwaInstall();
                      else setShowInstallGuide(true);
                    }}
                    className="flex items-center justify-center gap-1.5 py-1.5 px-3 text-[12px] font-black text-indigo-600 hover:text-white hover:bg-indigo-600 bg-indigo-50 border border-indigo-200 rounded-full transition-all whitespace-nowrap active:scale-95 leading-none"
                  >
                    <span className="text-[12px]">⬇️</span><span>지원금AI 설치</span>
                  </button>
                )}
              </div>
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

              <div className="flex items-center gap-1 flex-shrink-0">
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
            {/* 오늘의 인기 공고 섹션 제거 (사장님 요청) */}

            {/* 이메일 ?aid= 접속 시 해당 공고 최상단 고정 */}
            {pinnedAnnouncement && highlightAid && (
              <div className="mb-3 animate-in fade-in slide-in-from-top-4 duration-500">
                <p className="text-[11px] text-indigo-500 font-bold mb-2 flex items-center gap-1">
                  <span>📌</span> 이메일에서 선택한 공고
                </p>
                <ResultCard
                  res={pinnedAnnouncement}
                  selected={false}
                  planStatus={isPublic && !profile ? null : planStatus}
                  onUpgrade={isPublic && !profile ? undefined : onUpgrade}
                  onLoginRequired={isPublic && !profile ? handleLoginRequired : undefined}
                  highlight={true}
                />
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pb-6 overflow-hidden">
              {(() => {
                // 항상 서버 공고 표시 (맞춤 결과는 ⭐맞춤 탭에서만)
                if (publicData.length > 0) {
                  return publicData;
                }
                return filteredMatches.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE);
              })().map((res, idx) => (
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
              const totalItems = publicServerTotal > 0 ? publicServerTotal : filteredMatches.length;
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
          {/* 맞춤알림 미설정 시 빨간 점 — 사이드바 열면 최상단 카드로 안내 */}
          {profile && !hasNotificationSet && (
            <span className="absolute -top-1 -right-1 w-3 h-3 bg-rose-500 rounded-full ring-2 ring-white animate-pulse" aria-label="알림 미설정" />
          )}
        </button>
      )}

      <NotificationModal
        isOpen={isNotifyOpen}
        onClose={() => { setIsNotifyOpen(false); setNotifyShortcut(false); setNotifyFromGate(false); }}
        contextMessage={notifyFromGate ? "정확한 매칭을 위해 정보가 필요해요" : undefined}
        businessNumber={profile?.business_number}
        onSave={() => {
          setNotifyFromGate(false);
          onRefresh?.();
          (async () => {
            await onProfileRefresh?.();
            if (pendingActionRef.current) {
              pendingActionRef.current();
              pendingActionRef.current = null;
            }
          })();
        }}
        profile={profile}
        shortcutMode={notifyShortcut}
      />
      <SmartDocModal />

      {/* LITE 프로모션 공지 모달 */}
      {showPromoModal && (
        <div className="fixed inset-0 z-[9999] flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={() => setShowPromoModal(false)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div className="relative bg-white w-full sm:max-w-sm rounded-t-2xl sm:rounded-2xl p-6 pb-8 sm:pb-6 shadow-2xl animate-in slide-in-from-bottom sm:zoom-in-95 duration-300" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-2xl">🎁</span>
                <h3 className="text-[16px] font-black text-slate-900">LITE 1개월 무료 체험</h3>
              </div>
              <button onClick={() => setShowPromoModal(false)} className="w-8 h-8 flex items-center justify-center rounded-full bg-slate-100 text-slate-500 hover:bg-slate-200 transition-all text-sm">✕</button>
            </div>
            <div className="space-y-3 mb-5">
              <div className="bg-violet-50 rounded-xl p-4 border border-violet-100">
                <p className="text-[13px] font-bold text-violet-700 mb-1">🗓 체험 기간</p>
                <p className="text-[13px] text-slate-700">2026년 4월 22일 ~ <strong>5월 23일</strong>까지</p>
              </div>
              <div className="space-y-2">
                <p className="text-[12px] font-bold text-slate-500 uppercase tracking-wide">무료 제공 기능</p>
                {[
                  ["✅", "공고AI 상담 월 50회"],
                  ["✅", "맞춤 공고 알림 (이메일·푸시)"],
                  ["✅", "관심 공고 저장 · 일정 관리"],
                  ["✅", "AI 스마트 매칭 (전체 공고)"],
                ].map(([icon, text]) => (
                  <div key={text} className="flex items-center gap-2 text-[13px] text-slate-700">
                    <span>{icon}</span><span>{text}</span>
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">체험 기간 종료 후 자동으로 무료 플랜(공고AI 상담 월 3회)으로 전환됩니다. 별도 해지 불필요.</p>
            </div>
            <button onClick={() => setShowPromoModal(false)} className="w-full py-3 bg-indigo-600 text-white rounded-xl font-bold text-[14px] hover:bg-indigo-700 transition-all active:scale-[0.98]">
              확인
            </button>
          </div>
        </div>
      )}

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
                <p className="text-[11px] font-bold text-slate-700 mb-2">
                  {browserType === "samsung" && "🔸 삼성 인터넷 설치 방법"}
                  {browserType === "chrome_android" && "🔸 Chrome 설치 방법"}
                  {browserType === "firefox_android" && "🔸 Firefox 설치 방법"}
                  {browserType === "edge_android" && "🔸 Edge 설치 방법"}
                  {browserType === "safari_ios" && "🔸 Safari 설치 방법"}
                  {browserType === "chrome_ios" && "🔸 iPhone 설치 방법"}
                  {browserType === "chrome_desktop" && "🔸 Chrome 설치 방법"}
                  {browserType === "edge_desktop" && "🔸 Edge 설치 방법"}
                  {(browserType === "firefox_desktop" || browserType === "safari_desktop" || browserType === "other") && "🔸 설치 방법"}
                </p>

                {/* Samsung Internet — 하단 중앙 탭바에 ≡ 아이콘 */}
                {browserType === "samsung" && (
                  <>
                    <div className="flex items-start gap-2.5 mb-2">
                      <div className="flex items-center justify-center w-10 h-10 bg-blue-50 border border-blue-200 rounded-lg shrink-0 text-lg">≡</div>
                      <p className="text-[11px] text-slate-700 leading-relaxed pt-1">
                        <span className="font-black">1단계:</span> 화면 <span className="font-bold text-blue-700">하단 중앙 ≡ 메뉴</span> 탭
                      </p>
                    </div>
                    <div className="flex items-start gap-2.5">
                      <div className="flex items-center justify-center w-10 h-10 bg-emerald-50 border border-emerald-200 rounded-lg shrink-0 text-base">➕</div>
                      <p className="text-[11px] text-slate-700 leading-relaxed pt-1">
                        <span className="font-black">2단계:</span> <span className="font-bold text-emerald-700">&quot;현재 페이지 추가&quot;</span> → <span className="font-bold text-emerald-700">&quot;홈 화면&quot;</span> 선택
                      </p>
                    </div>
                  </>
                )}

                {/* Chrome Android */}
                {browserType === "chrome_android" && (
                  <>
                    <div className="flex items-start gap-2.5 mb-2">
                      <div className="flex items-center justify-center w-10 h-10 bg-indigo-50 border border-indigo-200 rounded-lg shrink-0 text-lg font-black">⋮</div>
                      <p className="text-[11px] text-slate-700 leading-relaxed pt-1">
                        <span className="font-black">1단계:</span> <span className="font-bold text-indigo-700">우측 상단 ⋮ 메뉴</span> 탭
                      </p>
                    </div>
                    <div className="flex items-start gap-2.5">
                      <div className="flex items-center justify-center w-10 h-10 bg-emerald-50 border border-emerald-200 rounded-lg shrink-0 text-base">📱</div>
                      <p className="text-[11px] text-slate-700 leading-relaxed pt-1">
                        <span className="font-black">2단계:</span> <span className="font-bold text-emerald-700">&quot;앱 설치&quot;</span> 또는 <span className="font-bold text-emerald-700">&quot;홈 화면에 추가&quot;</span> 선택
                      </p>
                    </div>
                  </>
                )}

                {/* Firefox Android */}
                {browserType === "firefox_android" && (
                  <>
                    <div className="flex items-start gap-2.5 mb-2">
                      <div className="flex items-center justify-center w-10 h-10 bg-orange-50 border border-orange-200 rounded-lg shrink-0 text-lg font-black">⋮</div>
                      <p className="text-[11px] text-slate-700 leading-relaxed pt-1">
                        <span className="font-black">1단계:</span> <span className="font-bold text-orange-700">우측 하단 ⋮ 메뉴</span> 탭
                      </p>
                    </div>
                    <div className="flex items-start gap-2.5">
                      <div className="flex items-center justify-center w-10 h-10 bg-emerald-50 border border-emerald-200 rounded-lg shrink-0 text-base">➕</div>
                      <p className="text-[11px] text-slate-700 leading-relaxed pt-1">
                        <span className="font-black">2단계:</span> <span className="font-bold text-emerald-700">&quot;설치&quot;</span> 또는 <span className="font-bold text-emerald-700">&quot;홈 화면에 추가&quot;</span> 선택
                      </p>
                    </div>
                  </>
                )}

                {/* Edge Android */}
                {browserType === "edge_android" && (
                  <>
                    <div className="flex items-start gap-2.5 mb-2">
                      <div className="flex items-center justify-center w-10 h-10 bg-sky-50 border border-sky-200 rounded-lg shrink-0 text-lg font-black">⋯</div>
                      <p className="text-[11px] text-slate-700 leading-relaxed pt-1">
                        <span className="font-black">1단계:</span> <span className="font-bold text-sky-700">하단 중앙 ⋯ 메뉴</span> 탭
                      </p>
                    </div>
                    <div className="flex items-start gap-2.5">
                      <div className="flex items-center justify-center w-10 h-10 bg-emerald-50 border border-emerald-200 rounded-lg shrink-0 text-base">📱</div>
                      <p className="text-[11px] text-slate-700 leading-relaxed pt-1">
                        <span className="font-black">2단계:</span> <span className="font-bold text-emerald-700">&quot;앱&quot;</span> → <span className="font-bold text-emerald-700">&quot;이 사이트를 앱으로 설치&quot;</span>
                      </p>
                    </div>
                  </>
                )}

                {/* Safari iOS / Chrome·Firefox·Edge iOS (모두 Safari WebView) */}
                {(browserType === "safari_ios" || browserType === "chrome_ios") && (
                  <>
                    <div className="flex items-start gap-2.5 mb-2">
                      <div className="flex items-center justify-center w-10 h-10 bg-indigo-50 border border-indigo-200 rounded-lg shrink-0 text-base">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-indigo-600"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg>
                      </div>
                      <p className="text-[11px] text-slate-700 leading-relaxed pt-1">
                        <span className="font-black">1단계:</span> <span className="font-bold text-indigo-700">하단 공유 버튼</span> (□↑) 탭
                        {browserType === "chrome_ios" && (
                          <span className="block text-[10px] text-amber-700 mt-1">
                            ⚠ iPhone은 Safari로 열어야 설치 가능합니다.
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="flex items-start gap-2.5">
                      <div className="flex items-center justify-center w-10 h-10 bg-emerald-50 border border-emerald-200 rounded-lg shrink-0 text-base">🏠</div>
                      <p className="text-[11px] text-slate-700 leading-relaxed pt-1">
                        <span className="font-black">2단계:</span> <span className="font-bold text-emerald-700">&quot;홈 화면에 추가&quot;</span> 선택
                      </p>
                    </div>
                  </>
                )}

                {/* Desktop Chrome / Edge */}
                {(browserType === "chrome_desktop" || browserType === "edge_desktop") && (
                  <>
                    <div className="flex items-start gap-2.5 mb-2">
                      <div className="flex items-center justify-center w-10 h-10 bg-indigo-50 border border-indigo-200 rounded-lg shrink-0 text-base">🔗</div>
                      <p className="text-[11px] text-slate-700 leading-relaxed pt-1">
                        <span className="font-black">1단계:</span> <span className="font-bold text-indigo-700">주소창 오른쪽</span>의 설치 아이콘 클릭
                      </p>
                    </div>
                    <div className="flex items-start gap-2.5">
                      <div className="flex items-center justify-center w-10 h-10 bg-emerald-50 border border-emerald-200 rounded-lg shrink-0 text-base">📲</div>
                      <p className="text-[11px] text-slate-700 leading-relaxed pt-1">
                        <span className="font-black">대안:</span> <span className="font-bold text-emerald-700">⋮ 메뉴 → &quot;지원금AI 앱 설치&quot;</span>
                      </p>
                    </div>
                  </>
                )}

                {/* Desktop Safari / Firefox / 기타 — PWA 설치 제한적 */}
                {(browserType === "firefox_desktop" || browserType === "safari_desktop" || browserType === "other") && (
                  <div className="flex items-start gap-2.5">
                    <div className="flex items-center justify-center w-10 h-10 bg-amber-50 border border-amber-200 rounded-lg shrink-0 text-base">💡</div>
                    <p className="text-[11px] text-slate-700 leading-relaxed pt-1">
                      이 브라우저는 PWA 설치 지원이 제한적입니다.<br/>
                      <span className="font-bold text-indigo-700">Chrome, Edge</span> 또는 <span className="font-bold text-indigo-700">Safari(iOS)</span>에서 열면 설치 가능합니다.
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
