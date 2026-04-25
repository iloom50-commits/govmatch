"use client";

import { useState, useEffect, useCallback } from "react";
import LoginModal from "@/components/LoginModal";
import Dashboard from "@/components/Dashboard";
import OnboardingWizard from "@/components/OnboardingWizard";
import ProfileSettings from "@/components/ProfileSettings";
import SkeletonLoader from "@/components/ui/SkeletonLoader";
import PaymentModal from "@/components/PaymentModal";
import AiConsultModal from "@/components/AiConsultModal";
import AiChatBot from "@/components/AiChatBot";
import { useToast } from "@/components/ui/Toast";

const API = process.env.NEXT_PUBLIC_API_URL;

async function subscribePush(bn: string) {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
  try {
    const reg = await navigator.serviceWorker.register("/sw.js");
    const existing = await reg.pushManager.getSubscription();
    if (existing) return;

    const res = await fetch(`${API}/api/push/vapid-key`);
    const { publicKey } = await res.json();
    if (!publicKey) return;

    const perm = await Notification.requestPermission();
    if (perm !== "granted") return;

    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
    const subJson = sub.toJSON();
    await fetch(`${API}/api/push/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        business_number: bn,
        endpoint: subJson.endpoint,
        keys: subJson.keys,
      }),
    });
  } catch (e) {
    console.warn("Push subscription failed:", e);
  }
}

function urlBase64ToUint8Array(base64String: string) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

interface PlanStatus {
  plan: string;
  active: boolean;
  days_left: number | null;
  label: string;
  ai_used?: number;
  ai_limit?: number;
  consult_limit?: number;
}

// Steps:
// BROWSE   = 비로그인 공고 리스트 (첫 화면)
// LOGIN    = 기존 로그인 페이지 (풀스크린, 비밀번호 찾기 등)
// LOADING  = 로딩
// ONBOARDING = 온보딩 위자드
// PROFILE  = 프로필 설정
// RESULTS  = 매칭 결과 대시보드
type Step = "BROWSE" | "LOGIN" | "LOADING" | "ONBOARDING" | "PROFILE" | "RESULTS";

export default function Home() {
  const [step, setStep] = useState<Step>("LOADING");
  const [businessNumber, setBusinessNumber] = useState("");
  const [profileData, setProfileData] = useState<any>(null);
  const [matches, setMatches] = useState<any[]>([]);
  const [updateRequired, setUpdateRequired] = useState(false);
  const [planStatus, setPlanStatus] = useState<PlanStatus | null>(null);
  const [showPayment, setShowPayment] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [referralCode, setReferralCode] = useState<string | null>(null);
  const [consultantResult, setConsultantResult] = useState<{ matches: any[]; profile: any } | null>(null);
  const [publicMatches, setPublicMatches] = useState<any[]>([]);
  const [showProfileNudge, setShowProfileNudge] = useState(false);
  const [openNotifyOnReturn, setOpenNotifyOnReturn] = useState(false);
  const [currentMajorTab, setCurrentMajorTab] = useState<"business" | "individual">("business");
  const { toast } = useToast();

  // AI 플로팅 버튼에서 "무료 상담 시작하기(로그인)" 클릭 시 로그인 모달 열기
  useEffect(() => {
    const handler = () => setShowLoginModal(true);
    window.addEventListener("open-login-modal", handler);
    return () => window.removeEventListener("open-login-modal", handler);
  }, []);

  // 맞춤 설정 유도: NotificationModal이 실제 저장하는 필드 중 하나라도 있으면 설정 완료
  const isProfileIncomplete = profileData && !(() => {
    const city = profileData.address_city ? String(profileData.address_city).split(",").filter((c: string) => c && c !== "전국")[0] : "";
    return !!(
      city ||
      profileData.age_range ||
      profileData.gender ||
      profileData.income_level ||
      profileData.family_type ||
      profileData.employment_status ||
      profileData.revenue_bracket ||
      profileData.employee_count_bracket ||
      profileData.founded_date ||
      profileData.is_pre_founder ||
      (profileData.certifications && String(profileData.certifications).length > 0) ||
      (profileData.interests && String(profileData.interests).length > 0)
    );
  })();

  // AI 챗봇에서 "지금 채우기" 클릭 시 프로필 설정 열기
  useEffect(() => {
    const handler = () => { if (step === "RESULTS") setStep("PROFILE"); };
    window.addEventListener("open-profile-settings", handler);
    return () => window.removeEventListener("open-profile-settings", handler);
  }, [step]);

  // 맞춤 설정 모달: 최초 1회만
  useEffect(() => {
    if (!isProfileIncomplete || step !== "RESULTS") return;
    const alreadyShown = localStorage.getItem("profile_nudge_shown");
    if (alreadyShown) return;

    const timer = setTimeout(() => {
      setShowProfileNudge(true);
      localStorage.setItem("profile_nudge_shown", "1");
    }, 5000);

    return () => clearTimeout(timer);
  }, [isProfileIncomplete, step]);

  // 비로그인 공고 로드 (localStorage 캐시 → 즉시 표시 → 백그라운드 갱신)
  const [publicCategoryCountsBiz, setPublicCategoryCountsBiz] = useState<Record<string, number>>({});
  const [publicCategoryCountsInd, setPublicCategoryCountsInd] = useState<Record<string, number>>({});

  const handleCategoryCountsLoaded = useCallback((counts: Record<string, number>, tab: "business" | "individual") => {
    if (tab === "business") setPublicCategoryCountsBiz(counts);
    else setPublicCategoryCountsInd(counts);
  }, []);

  // URL ?ref= 파라미터 읽기 (추천 링크)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ref = params.get("ref");
    if (ref) {
      setReferralCode(ref);
      localStorage.setItem("referral_code", ref);
    } else {
      const stored = localStorage.getItem("referral_code");
      if (stored) setReferralCode(stored);
    }
  }, []);

  // 컨설턴트 매칭 결과 이벤트 수신
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.matches) {
        setConsultantResult({ matches: detail.matches, profile: detail.profile });
      }
    };
    window.addEventListener("consultant-match-result", handler);
    return () => window.removeEventListener("consultant-match-result", handler);
  }, []);

  const getToken = () => localStorage.getItem("auth_token");

  const authHeaders = useCallback(() => {
    const token = getToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return headers;
  }, []);

  const handleEditProfile = () => setStep("PROFILE");

  const performMatching = useCallback(async (bn: string, forceRefresh = false, targetType?: string) => {
    const tt = targetType || "business"; // 기본: 기업탭 우선
    const cacheKey = `match_cache_${tt}`;

    // 캐시 확인 (15분 이내면 재사용)
    if (!forceRefresh) {
      try {
        const cached = sessionStorage.getItem(cacheKey);
        if (cached) {
          const { data, bn: cachedBn, ts } = JSON.parse(cached);
          if (cachedBn === bn && Date.now() - ts < 15 * 60 * 1000) {
            setMatches(prev => {
              // 기존 다른 탭 결과와 병합
              const otherTab = prev.filter((m: any) => {
                const mtt = m.target_type || "business";
                return tt === "business" ? mtt !== "business" : mtt === "business";
              });
              return [...data, ...otherTab];
            });
            setStep("RESULTS");
            return;
          }
        }
      } catch {}
    }

    try {
      const res = await fetch(`${API}/api/match`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ business_number: bn, target_type: tt }),
      });
      const result = await res.json();

      if (result.status === "SUCCESS") {
        setMatches(prev => {
          const otherTab = prev.filter((m: any) => {
            const mtt = m.target_type || "business";
            return tt === "business" ? mtt !== "business" : mtt === "business";
          });
          return [...result.data, ...otherTab];
        });
        setStep("RESULTS");
        try {
          sessionStorage.setItem(cacheKey, JSON.stringify({ data: result.data, bn, ts: Date.now() }));
        } catch {}

        // 백그라운드: 다른 탭 매칭도 미리 요청 (캐시 워밍)
        const otherTt = tt === "business" ? "individual" : "business";
        const otherKey = `match_cache_${otherTt}`;
        try {
          const otherCached = sessionStorage.getItem(otherKey);
          if (otherCached) {
            const { bn: cBn, ts } = JSON.parse(otherCached);
            if (cBn === bn && Date.now() - ts < 15 * 60 * 1000) return; // 이미 캐시 있음
          }
        } catch {}
        // 백그라운드 fetch (결과만 캐시, UI 업데이트 안 함)
        fetch(`${API}/api/match`, {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify({ business_number: bn, target_type: otherTt }),
        }).then(r => r.json()).then(r2 => {
          if (r2.status === "SUCCESS") {
            try { sessionStorage.setItem(otherKey, JSON.stringify({ data: r2.data, bn, ts: Date.now() })); } catch {}
            // matches에도 병합
            setMatches(prev => [...prev.filter((m: any) => (m.target_type || "business") !== (otherTt === "individual" ? "individual" : "business")), ...r2.data]);
          }
        }).catch(() => {});
      } else {
        throw new Error(result.detail || "매칭 실패");
      }
    } catch {
      toast("매칭 수행 중 오류가 발생했습니다.", "error");
      setStep(getToken() ? "RESULTS" : "BROWSE");
    }
  }, [toast, authHeaders]);

  // On mount: check for existing JWT token
  const loadUserAndMatch = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setStep("BROWSE");
      return;
    }

    setStep("LOADING");
    try {
      // JWT에서 bn 추출 (auth/me 대기 없이 match 병렬 시작용)
      let jwtBn = "";
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        jwtBn = payload.bn || "";
      } catch {}

      // auth/me + match 병렬 호출
      const mePromise = fetch(`${API}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const matchPromise = jwtBn ? fetch(`${API}/api/match`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ business_number: jwtBn, target_type: "business" }),
      }) : null;

      const res = await mePromise;
      if (!res.ok) {
        localStorage.removeItem("auth_token");
        setStep("BROWSE");
        return;
      }

      const data = await res.json();
      const user = data.user;
      setPlanStatus(data.plan);
      setBusinessNumber(user.business_number);
      setProfileData(user);

      if (data.plan.plan === "expired") {
        setStep("RESULTS");
        setMatches([]);
        return;
      }

      // 프로필 매칭 가능 여부 — user_type별 기준 분리
      const utype = user.user_type || "both";
      const canMatch = (() => {
        if (utype === "individual") {
          const hasBasic = !!(user.age_range || user.address_city);
          const hasContext = !!(user.income_level || user.family_type || user.employment_status || user.interests);
          return hasBasic && hasContext;
        }
        if (utype === "business") {
          const hasIndustry = !!(user.industry_code && user.industry_code !== "00000");
          const hasRegionInterest = !!(user.address_city && user.interests);
          return hasIndustry || hasRegionInterest;
        }
        const bizOk = !!(user.industry_code && user.industry_code !== "00000");
        const indOk = !!(user.age_range || (user.address_city && user.interests));
        return bizOk || indOk;
      })();
      if (!canMatch) {
        setStep("RESULTS");
        setMatches([]);
        return;
      }

      // match 병렬 결과 수거 (이미 실행 중)
      const firstTab = (user.user_type === "individual") ? "individual" : "business";
      if (matchPromise && firstTab === "business") {
        // 이미 business로 요청했으므로 결과만 수거
        try {
          const matchRes = await matchPromise;
          const matchResult = await matchRes.json();
          if (matchResult.status === "SUCCESS") {
            setMatches(matchResult.data);
            setStep("RESULTS");
            try { sessionStorage.setItem("match_cache_business", JSON.stringify({ data: matchResult.data, bn: user.business_number, ts: Date.now() })); } catch {}
            // 백그라운드: individual 매칭
            fetch(`${API}/api/match`, { method: "POST", headers: authHeaders(), body: JSON.stringify({ business_number: user.business_number, target_type: "individual" }) })
              .then(r => r.json()).then(r2 => {
                if (r2.status === "SUCCESS") {
                  try { sessionStorage.setItem("match_cache_individual", JSON.stringify({ data: r2.data, bn: user.business_number, ts: Date.now() })); } catch {}
                  setMatches(prev => [...prev.filter((m: any) => (m.target_type || "business") !== "individual"), ...r2.data]);
                }
              }).catch(() => {});
            return;
          }
        } catch {}
      }
      // fallback: 순차 호출
      await performMatching(user.business_number, false, firstTab);
    } catch {
      localStorage.removeItem("auth_token");
      setStep("BROWSE");
    }
  }, [performMatching, authHeaders]);

  useEffect(() => {
    loadUserAndMatch();
  }, [loadUserAndMatch]);

  // Login success (from modal or full login page)
  const handleLoginSuccess = async (token: string, user: any, plan: any) => {
    localStorage.setItem("auth_token", token);
    if (user.email) localStorage.setItem("last_email", user.email);
    setPlanStatus(plan);
    setBusinessNumber(user.business_number);
    setShowLoginModal(false);

    setStep("LOADING");
    try {
      const meRes = await fetch(`${API}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const meData = await meRes.json();
      setProfileData(meData.user);

      // 프로필 매칭 가능 여부 — user_type별 기준 분리
      const u2 = meData.user;
      const utype2 = u2.user_type || "both";
      const canMatch2 = (() => {
        if (utype2 === "individual") {
          const hasBasic = !!(u2.age_range || u2.address_city);
          const hasContext = !!(u2.income_level || u2.family_type || u2.employment_status || u2.interests);
          return hasBasic && hasContext;
        }
        if (utype2 === "business") {
          const hasIndustry = !!(u2.industry_code && u2.industry_code !== "00000");
          const hasRegionInterest = !!(u2.address_city && u2.interests);
          return hasIndustry || hasRegionInterest;
        }
        const bizOk = !!(u2.industry_code && u2.industry_code !== "00000");
        const indOk = !!(u2.age_range || (u2.address_city && u2.interests));
        return bizOk || indOk;
      })();
      if (!canMatch2) {
        setStep("RESULTS");
        setMatches([]);
        setShowProfileNudge(true);
        return;
      }

      if (plan.plan === "expired") {
        setStep("RESULTS");
        setMatches([]);
        return;
      }

      const firstTab2 = (u2.user_type === "individual") ? "individual" : "business";
      await performMatching(user.business_number, false, firstTab2);
    } catch {
      toast("프로필 로딩 중 오류가 발생했습니다.", "error");
      setStep("BROWSE");
    }
  };

  // Onboarding complete → register (간소화: 이메일만으로 바로 가입) + match
  const handleOnboardingComplete = async (data: any) => {
    setStep("LOADING");

    const existingToken = getToken();
    const bn = data.business_number || businessNumber || `U${Date.now().toString().slice(-9)}`;
    setBusinessNumber(bn);

    try {
      let token = existingToken;

      // 소셜 로그인으로 이미 토큰이 있으면 등록 스킵, 없으면 신규 등록
      if (!token) {
        const regRes = await fetch(`${API}/api/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: data.email,
            password: data.password || `social_${Date.now()}`,
            business_number: bn,
            company_name: data.company_name || "",
            referred_by: referralCode || undefined,
          }),
        });
        const regData = await regRes.json();

        if (!regRes.ok) {
          toast(regData.detail || "계정 생성 중 오류가 발생했습니다.", "error");
          setStep("ONBOARDING");
          return;
        }

        token = regData.token;
        localStorage.setItem("auth_token", token!);
        if (data.email) localStorage.setItem("last_email", data.email);
        localStorage.removeItem("referral_code");
        setReferralCode(null);
        setPlanStatus(regData.plan);
      }

      // 프로필 데이터가 있으면 저장 (온보딩에서 입력한 경우)
      if (data.user_type || data.address_city || data.interests) {
        const profilePayload = {
          business_number: bn,
          company_name: data.company_name,
          establishment_date: data.establishment_date || (data.user_type === "individual" ? null : new Date().toISOString().split("T")[0]),
          address_city: data.address_city,
          industry_code: data.user_type === "individual" ? null : "00000",
          revenue_bracket: data.revenue_bracket || (data.user_type === "individual" ? null : "1억 미만"),
          employee_count_bracket: data.employee_count_bracket || (data.user_type === "individual" ? null : "5인 미만"),
          interests: data.interests,
          user_type: data.user_type || "business",
          age_range: data.age_range || null,
          income_level: data.income_level || null,
          family_type: data.family_type || null,
          employment_status: data.employment_status || null,
        };

        await fetch(`${API}/api/save-profile`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(profilePayload),
        });
      }

      const meRes = await fetch(`${API}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
      if (meRes.ok) setProfileData((await meRes.json()).user);

      toast("가입이 완료되었습니다!", "success");
      await performMatching(bn, true);
    } catch {
      toast("처리 중 오류가 발생했습니다.", "error");
      setStep("ONBOARDING");
    }
  };

  const handleConfirm = async (finalData: any) => {
    setStep("LOADING");
    try {
      const payload = {
        ...finalData,
        revenue_bracket: finalData.revenue,
        employee_count_bracket: finalData.employees,
      };
      const res = await fetch(`${API}/api/save-profile`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });

      const result = await res.json();
      if (res.status === 401) {
        toast(result.detail || "비밀번호가 올바르지 않습니다.", "error");
        setStep("PROFILE");
        return;
      }
      if (result.status === "SUCCESS") {
        const meRes = await fetch(`${API}/api/auth/me`, { headers: authHeaders() });
        if (meRes.ok) {
          const meData = await meRes.json();
          setProfileData(meData.user);
        }
        await performMatching(businessNumber, true);
        // 자금상담 "지금 채우기" 경유 시 채팅 자동 재시작
        if (localStorage.getItem("reopen_fund_chat_after_profile")) {
          localStorage.removeItem("reopen_fund_chat_after_profile");
          setTimeout(() => window.dispatchEvent(new CustomEvent("profile-saved-reopen-fund-chat")), 300);
        }
      } else {
        toast("프로필 저장에 실패했습니다.", "error");
        setStep("PROFILE");
      }
    } catch {
      toast("매칭 수행 중 오류가 발생했습니다.", "error");
      setStep("PROFILE");
    }
  };

  const refreshProfile = async () => {
    try {
      const token = localStorage.getItem("auth_token");
      if (!token) return;
      const res = await fetch(`${API}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const data = await res.json();
        setProfileData(data.user);
      }
    } catch {}
  };

  const handleLogout = () => {
    localStorage.removeItem("auth_token");
    setBusinessNumber("");
    setStep("BROWSE");
    setMatches([]);
    setProfileData(null);
    setPlanStatus(null);
  };

  return (
    <main
      className={`min-h-screen flex flex-col ${
        step === "RESULTS"
          ? "items-stretch pt-4 md:pt-6 px-4 md:px-12 lg:px-20 pb-12 md:pb-20"
          : step === "BROWSE"
          ? "items-stretch pt-4 md:pt-8 px-4 md:px-12 lg:px-20 pb-12"
          : "items-center justify-center p-6"
      }`}
    >
      {/* 비로그인: 기존 대시보드와 동일한 레이아웃 (사이드바 없음) */}
      {step === "BROWSE" && (
        <div className="flex justify-center">
          <Dashboard
            matches={publicMatches}
            profile={null}
            onEditProfile={() => setShowLoginModal(true)}
            onLogout={() => {}}
            isPublic={true}
            onLoginRequired={() => setShowLoginModal(true)}
            categoryCountsBiz={publicCategoryCountsBiz}
            categoryCountsInd={publicCategoryCountsInd}
            onCategoryCountsLoaded={handleCategoryCountsLoaded}
          />
        </div>
      )}

      {/* 로그인 모달 (공고 클릭 시 오버레이) */}
      {showLoginModal && (
        <LoginModal
          onLoginSuccess={handleLoginSuccess}
          onClose={() => setShowLoginModal(false)}
          onGoToRegister={() => {
            setShowLoginModal(false);
            setStep("ONBOARDING");
          }}
        />
      )}

      {updateRequired && step === "RESULTS" && (
        <div className="w-full max-w-[1600px] mx-auto mb-6 md:mb-8 p-4 md:p-6 bg-amber-50 border border-amber-200 rounded-3xl md:rounded-[2.5rem] flex flex-col md:flex-row items-center justify-between gap-4 md:gap-0 animate-in slide-in-from-top duration-500 shadow-sm">
          <div className="flex items-center gap-3 md:gap-4">
            <span className="text-2xl md:text-3xl">📅</span>
            <div>
              <p className="text-amber-900 font-black text-sm md:text-base">매출 정보 업데이트 필요</p>
              <p className="text-amber-700 text-xs md:text-sm font-medium">정기 신고 기간이 경과되었습니다. 정보를 갱신해 주세요.</p>
            </div>
          </div>
          <button
            onClick={() => setStep("PROFILE")}
            className="w-full md:w-auto px-6 py-3 bg-amber-500 text-white rounded-xl md:rounded-2xl font-black hover:bg-amber-600 transition-all shadow-lg text-sm"
          >
            지금 업데이트
          </button>
        </div>
      )}

      {planStatus?.plan === "expired" && step === "RESULTS" && (
        <div className="w-full max-w-[1600px] mx-auto mb-6 p-5 bg-rose-50 border border-rose-200 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4 animate-in slide-in-from-top duration-500 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🔒</span>
            <div>
              <p className="text-rose-900 font-bold text-sm">구독이 만료되었습니다</p>
              <p className="text-rose-700 text-xs font-medium">플랜을 선택하면 AI 기능을 계속 이용할 수 있습니다.</p>
            </div>
          </div>
          <button
            onClick={() => setShowPayment(true)}
            className="w-full md:w-auto px-6 py-2 bg-indigo-600 text-white rounded-lg font-bold hover:bg-indigo-700 transition-all shadow-lg text-sm"
          >
            플랜 선택하기
          </button>
        </div>
      )}

      {/* 프로필 미완성 유도 배너 */}
      {step === "RESULTS" && profileData && !profileData.user_type && (
        <div className="w-full max-w-[1600px] mx-auto mb-4 p-4 bg-gradient-to-r from-violet-50 to-indigo-50 border border-indigo-200 rounded-xl flex flex-col sm:flex-row items-center justify-between gap-3 animate-in slide-in-from-top duration-500 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🎯</span>
            <div>
              <p className="text-indigo-900 font-bold text-sm">내 조건에 맞는 공고만 보고 싶다면?</p>
              <p className="text-indigo-600 text-xs font-medium">간단한 프로필 설정으로 AI 맞춤 매칭을 받아보세요</p>
            </div>
          </div>
          <button
            onClick={() => setStep("ONBOARDING")}
            className="w-full sm:w-auto px-5 py-2.5 bg-indigo-600 text-white rounded-lg font-bold text-xs hover:bg-indigo-700 transition-all shadow-lg flex-shrink-0 active:scale-95"
          >
            맞춤 설정하기
          </button>
        </div>
      )}

      {/* FREE 배너 — 결제 시스템 준비 후 복원 */}

      {/* Hero Header for onboarding & full login */}
      {(step === "LOGIN" || step === "ONBOARDING") && (
        <div className="text-center mb-6 md:mb-8 animate-in fade-in duration-500">
          <h1 className="text-2xl md:text-3xl lg:text-4xl font-bold text-slate-900 mb-2 tracking-tighter">
            <span className="brand-badge brand-badge-lg brand-go-hover"><span className="brand-name">지원금</span><span className="brand-go">AI</span></span>
            <span className="sr-only">지원금AI - AI 정부 지원금 자동 매칭</span>
          </h1>
          <p className="text-slate-500 text-xs md:text-sm max-w-md mx-auto font-medium leading-relaxed px-4 opacity-80">
            AI가 매시간 5,000개 이상의 정부 공고를 분석하여
            <br className="md:hidden" /> 우리 기업에 딱 맞는 지원사업을 찾아드립니다
          </p>
        </div>
      )}

      {/* Onboarding (신규 가입) */}
      {step === "ONBOARDING" && (
        <>
          <OnboardingWizard
            initialBusinessNumber={businessNumber || undefined}
            initialEmail={profileData?.email || ""}
            onComplete={handleOnboardingComplete}
            onLogout={businessNumber ? handleLogout : undefined}
          />
          <div className="flex items-center justify-center gap-4 mt-4">
            <button
              onClick={() => setStep("BROWSE")}
              className="text-slate-400 hover:text-slate-600 text-xs font-bold transition-all"
            >
              ← 돌아가기
            </button>
            <button
              onClick={() => setStep("LOGIN")}
              className="text-slate-400 hover:text-indigo-600 text-xs font-black transition-all"
            >
              이미 계정이 있으신가요? 로그인
            </button>
          </div>
        </>
      )}

      {/* Full login page (비밀번호 찾기 등 풀 기능) */}
      {step === "LOGIN" && (
        <>
          {/* Import AuthPage inline to avoid circular deps */}
          <AuthPageWrapper
            onLoginSuccess={handleLoginSuccess}
            onGoToRegister={() => setStep("ONBOARDING")}
          />
        </>
      )}

      {step === "LOADING" && (
        <div className="flex-1 flex items-center justify-center">
          <SkeletonLoader />
        </div>
      )}

      {step === "PROFILE" && (
        <ProfileSettings profile={profileData} onSave={handleConfirm} onClose={() => setStep("RESULTS")} onLogout={handleLogout} planStatus={planStatus} onOpenNotify={() => { setOpenNotifyOnReturn(true); setStep("RESULTS"); }} />
      )}

      {step === "RESULTS" && (
        <div className="flex justify-center">
          <Dashboard
            matches={isProfileIncomplete ? [] : matches}
            profile={profileData}
            onEditProfile={handleEditProfile}
            onLogout={handleLogout}
            planStatus={planStatus}
            onUpgrade={() => setShowPayment(true)}
            consultantResult={consultantResult}
            onClearConsultant={() => setConsultantResult(null)}
            onRefresh={() => { setConsultantResult(null); performMatching(businessNumber, true); }}
            isPublic={isProfileIncomplete || false}
            onLoginRequired={isProfileIncomplete ? handleEditProfile : undefined}
            categoryCountsBiz={publicCategoryCountsBiz}
            categoryCountsInd={publicCategoryCountsInd}
            onCategoryCountsLoaded={handleCategoryCountsLoaded}
            defaultMajorTab={isProfileIncomplete ? "individual" : undefined}
            autoOpenNotify={openNotifyOnReturn}
            onNotifyOpened={() => setOpenNotifyOnReturn(false)}
            onPlanUpdate={(updated: any) => setPlanStatus((prev: any) => ({ ...prev, ...updated }))}
            onProfileRefresh={refreshProfile}
            onMajorTabChange={setCurrentMajorTab}
          />
        </div>
      )}

      {/* 맞춤 설정 유도 모달 */}
      {showProfileNudge && isProfileIncomplete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[2px]" onClick={() => setShowProfileNudge(false)} />
          <div className="relative w-full max-w-sm bg-white rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300">
            <div className="p-6 text-center">
              <div className="w-16 h-16 mx-auto mb-4 bg-indigo-100 rounded-full flex items-center justify-center">
                <span className="text-3xl">🎯</span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">
                맞춤 설정 한 번이면
              </h3>
              <p className="text-sm text-slate-600 mb-4 leading-relaxed">
                매일 내 조건에 맞는 새 지원금을<br />
                <strong className="text-indigo-600">AI가 자동으로 찾아서 알려드립니다</strong>
              </p>
              <div className="space-y-2 text-left mb-5 px-2">
                <div className="flex items-center gap-2 text-[13px] text-slate-700">
                  <span className="text-emerald-500 font-bold">✓</span>
                  검색 없이 자동 추천
                </div>
                <div className="flex items-center gap-2 text-[13px] text-slate-700">
                  <span className="text-emerald-500 font-bold">✓</span>
                  마감 임박 알림 자동 발송
                </div>
                <div className="flex items-center gap-2 text-[13px] text-slate-700">
                  <span className="text-emerald-500 font-bold">✓</span>
                  AI 상담 정확도 향상
                </div>
              </div>
              <button
                onClick={() => {
                  setShowProfileNudge(false);
                  setOpenNotifyOnReturn(true);
                }}
                className="w-full py-3 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all active:scale-[0.98]"
              >
                1분이면 끝! 맞춤 설정하기
              </button>
              <button
                onClick={() => setShowProfileNudge(false)}
                className="w-full py-2 mt-2 text-slate-400 text-xs font-medium hover:text-slate-600 transition-all"
              >
                나중에 할게요
              </button>
            </div>
          </div>
        </div>
      )}

      {showPayment && (
        <PaymentModal
          planStatus={planStatus}
          userType={profileData?.user_type}
          onSuccess={(newToken, newPlan) => {
            setPlanStatus(newPlan);
            setShowPayment(false);
            if (planStatus?.plan === "expired") {
              performMatching(businessNumber);
            }
          }}
          onClose={() => setShowPayment(false)}
        />
      )}

      <AiConsultModal planStatus={planStatus} onUpgrade={() => setShowPayment(true)} onPlanUpdate={(u: any) => setPlanStatus((prev: any) => prev ? { ...prev, ...u } : prev)} />
      <AiChatBot planStatus={planStatus} onUpgrade={() => setShowPayment(true)} userType={profileData?.user_type} currentTab={currentMajorTab} />

      {/* SEO 정적 콘텐츠 — 검색봇용 (사용자 화면에서 숨김) */}
      <section className="sr-only">
        <h2 className="text-lg font-bold text-slate-800 mb-4">지원금AI — AI 정부 지원금 자동 매칭 서비스</h2>
        <p className="mb-3">지원금AI는 17,000건 이상의 정부 지원금, 보조금, 정책자금 공고를 AI가 실시간 분석하여 내 조건에 딱 맞는 지원사업을 자동으로 매칭해주는 서비스입니다.</p>
        <h3 className="font-bold text-slate-700 mt-6 mb-2">중소기업·소상공인 지원</h3>
        <p className="mb-3">정책자금, 융자, 신용보증, 창업자금, R&D 지원, 수출 바우처, 고용장려금, 스마트공장 구축 등 기업 대상 정부 지원사업을 AI가 자격요건까지 대조하여 추천합니다.</p>
        <h3 className="font-bold text-slate-700 mt-6 mb-2">개인 복지·생활 지원</h3>
        <p className="mb-3">청년 전세자금, 주거 지원, 취업 훈련, 출산·육아 지원, 학자금, 긴급 생계 지원 등 개인 대상 복지사업도 AI가 맞춤 매칭합니다.</p>
        <h3 className="font-bold text-slate-700 mt-6 mb-2">AI 자금 상담</h3>
        <p>정책자금 금리, 신청 자격, 필요 서류, 신청 방법까지 AI 전문 상담사가 실시간으로 답변합니다. 정부 지원금, 보조금, 정책자금이 궁금하면 지원금AI에서 무료로 상담하세요.</p>
      </section>

    </main>
  );
}

// Wrapper to lazy-import AuthPage (avoid removing the component)
import AuthPage from "@/components/AuthPage";

function AuthPageWrapper({ onLoginSuccess, onGoToRegister }: {
  onLoginSuccess: (token: string, user: any, plan: any) => void;
  onGoToRegister: () => void;
}) {
  return (
    <AuthPage
      onLoginSuccess={onLoginSuccess}
      onGoToRegister={onGoToRegister}
      initialEmail={typeof window !== "undefined" ? localStorage.getItem("last_email") || "" : ""}
    />
  );
}
