"use client";

import { useState, useEffect, useCallback } from "react";
import Dashboard from "@/components/Dashboard";
import OnboardingWizard from "@/components/OnboardingWizard";
import ProfileSettings from "@/components/ProfileSettings";
import SkeletonLoader from "@/components/ui/SkeletonLoader";
import AuthPage from "@/components/AuthPage";
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
}

export default function Home() {
  // IDLE = first visit (onboarding), LOGIN = returning user login screen
  const [step, setStep] = useState<"IDLE" | "LOGIN" | "LOADING" | "PROFILE" | "RESULTS" | "ONBOARDING">("LOADING");
  const [businessNumber, setBusinessNumber] = useState("");
  const [profileData, setProfileData] = useState<any>(null);
  const [matches, setMatches] = useState<any[]>([]);
  const [updateRequired, setUpdateRequired] = useState(false);
  const [planStatus, setPlanStatus] = useState<PlanStatus | null>(null);
  const [showPayment, setShowPayment] = useState(false);
  const [referralCode, setReferralCode] = useState<string | null>(null);
  const [consultantResult, setConsultantResult] = useState<{ matches: any[]; profile: any } | null>(null);
  const { toast } = useToast();

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

  const performMatching = useCallback(async (bn: string) => {
    try {
      const res = await fetch(`${API}/api/match`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ business_number: bn }),
      });
      const result = await res.json();

      if (result.status === "SUCCESS") {
        setMatches(result.data);
        setStep("RESULTS");
      } else {
        throw new Error(result.detail || "매칭 실패");
      }
    } catch {
      toast("매칭 수행 중 오류가 발생했습니다.", "error");
      setStep("IDLE");
    }
  }, [toast, authHeaders]);

  // On mount: check for existing JWT token
  const loadUserAndMatch = useCallback(async () => {
    const token = getToken();
    if (!token) {
      // No token → show login (user can navigate to register from there)
      setStep("LOGIN");
      return;
    }

    setStep("LOADING");
    try {
      const res = await fetch(`${API}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        localStorage.removeItem("auth_token");
        // Token invalid → show login (returning user with expired token)
        setStep("LOGIN");
        return;
      }

      const data = await res.json();
      const user = data.user;
      setPlanStatus(data.plan);
      setBusinessNumber(user.business_number);
      setProfileData(user);

      if (!user.interests && !user.industry_code) {
        setStep("ONBOARDING");
        return;
      }

      if (data.plan.plan === "expired") {
        setStep("RESULTS");
        setMatches([]);
        return;
      }

      await performMatching(user.business_number);
    } catch {
      localStorage.removeItem("auth_token");
      setStep("LOGIN");
    }
  }, [performMatching]);

  useEffect(() => {
    loadUserAndMatch();
  }, [loadUserAndMatch]);

  // Login success (returning user)
  const handleLoginSuccess = async (token: string, user: any, plan: any) => {
    localStorage.setItem("auth_token", token);
    if (user.email) localStorage.setItem("last_email", user.email);
    setPlanStatus(plan);
    setBusinessNumber(user.business_number);

    setStep("LOADING");
    try {
      const meRes = await fetch(`${API}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const meData = await meRes.json();
      setProfileData(meData.user);

      if (plan.plan === "expired") {
        setStep("RESULTS");
        setMatches([]);
        return;
      }

      await performMatching(user.business_number);
    } catch {
      toast("프로필 로딩 중 오류가 발생했습니다.", "error");
      setStep("LOGIN");
    }
  };

  // Onboarding complete → register + save profile + match
  const handleOnboardingComplete = async (data: any) => {
    setStep("LOADING");

    const bn = data.business_number || `U${Date.now().toString().slice(-9)}`;
    setBusinessNumber(bn);

    try {
      // 1. Register account (email + password from Step 5)
      const regRes = await fetch(`${API}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: data.email,
          password: data.password,
          business_number: bn,
          company_name: data.company_name,
          referred_by: referralCode || undefined,
        }),
      });
      const regData = await regRes.json();

      if (!regRes.ok) {
        if (regRes.status === 409) {
          // Already registered → try login automatically
          const loginRes = await fetch(`${API}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: data.email, password: data.password }),
          });
          const loginData = await loginRes.json();

          if (loginRes.ok) {
            toast("기존 계정으로 로그인되었습니다.", "success");
            localStorage.setItem("auth_token", loginData.token);
            if (data.email) localStorage.setItem("last_email", data.email);
            setPlanStatus(loginData.plan);
            setBusinessNumber(loginData.user.business_number);
            // 온보딩 재시도 시 프로파일 업데이트
            await fetch(`${API}/api/save-profile`, {
              method: "POST",
              headers: { "Content-Type": "application/json", Authorization: `Bearer ${loginData.token}` },
              body: JSON.stringify({
                business_number: bn,
                company_name: data.company_name,
                establishment_date: data.establishment_date || new Date().toISOString().split("T")[0],
                address_city: data.address_city,
                industry_code: data.industry_code || "00000",
                revenue_bracket: data.revenue_bracket || "1억 미만",
                employee_count_bracket: data.employee_count_bracket || "5인 미만",
                interests: data.interests,
              }),
            });
            const meRes = await fetch(`${API}/api/auth/me`, { headers: { Authorization: `Bearer ${loginData.token}` } });
            if (meRes.ok) setProfileData((await meRes.json()).user);
            await performMatching(bn);
            return;
          }
          toast("이미 가입된 이메일입니다. 비밀번호를 확인해 주세요.", "error");
          setStep("LOGIN");
          return;
        }
        toast(regData.detail || "계정 생성 중 오류가 발생했습니다.", "error");
        setStep("ONBOARDING");
        return;
      }

      localStorage.setItem("auth_token", regData.token);
      if (data.email) localStorage.setItem("last_email", data.email);
      localStorage.removeItem("referral_code");
      setReferralCode(null);
      setPlanStatus(regData.plan);

      // 2. Save full profile
      const profilePayload = {
        business_number: bn,
        company_name: data.company_name,
        establishment_date: data.establishment_date || new Date().toISOString().split("T")[0],
        address_city: data.address_city,
        industry_code: data.industry_code || "00000",
        revenue_bracket: data.revenue_bracket || "1억 미만",
        employee_count_bracket: data.employee_count_bracket || "5인 미만",
        interests: data.interests,
      };

      await fetch(`${API}/api/save-profile`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${regData.token}`,
        },
        body: JSON.stringify(profilePayload),
      });

      // 3. Save notification settings
      await fetch(`${API}/api/notification-settings`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${regData.token}`,
        },
        body: JSON.stringify({
          business_number: bn,
          email: data.email,
          channel: "EMAIL",
          is_active: data.notification_enabled,
        }),
      });

      // 4. Subscribe to push if enabled
      if (data.push_enabled) {
        subscribePush(bn);
      }

      // 5. Run matching
      setProfileData(profilePayload);
      toast("30일 무료체험이 시작되었습니다!", "success");
      await performMatching(bn);
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
        // Reload profile from server to get industry_name and latest data
        const meRes = await fetch(`${API}/api/auth/me`, { headers: authHeaders() });
        if (meRes.ok) {
          const meData = await meRes.json();
          setProfileData(meData.user);
        }
        await performMatching(businessNumber);
      } else {
        toast("프로필 저장에 실패했습니다.", "error");
        setStep("PROFILE");
      }
    } catch {
      toast("매칭 수행 중 오류가 발생했습니다.", "error");
      setStep("PROFILE");
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("auth_token");
    setBusinessNumber("");
    setStep("LOGIN");
    setMatches([]);
    setProfileData(null);
    setPlanStatus(null);
  };

  return (
    <main
      className={`min-h-screen flex flex-col ${
        step === "RESULTS"
          ? "items-stretch pt-4 md:pt-6 px-4 md:px-12 lg:px-20 pb-12 md:pb-20"
          : "items-center justify-center p-6"
      }`}
    >
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

      {planStatus?.plan === "free" && step === "RESULTS" && (
        <div className="w-full max-w-[1600px] mx-auto mb-4 p-4 bg-indigo-50 border border-indigo-200 rounded-xl flex items-center justify-between animate-in slide-in-from-top duration-500">
          <p className="text-indigo-800 text-xs font-bold">
            FREE 플랜 사용 중 — 더 많은 AI 기능을 원하시면 업그레이드하세요 (첫 달 무료)
          </p>
          <button
            onClick={() => setShowPayment(true)}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg font-bold text-xs hover:bg-indigo-700 transition-all flex-shrink-0"
          >
            업그레이드
          </button>
        </div>
      )}

      {/* Hero Header for onboarding & login */}
      {(step === "IDLE" || step === "ONBOARDING" || step === "LOGIN") && (
        <div className="text-center mb-6 md:mb-8 animate-in fade-in duration-500">
          <h1 className="text-2xl md:text-3xl lg:text-4xl font-bold text-slate-900 mb-2 tracking-tighter">
            <span className="text-indigo-600">지원금톡톡</span>
          </h1>
          <p className="text-slate-500 text-xs md:text-sm max-w-md mx-auto font-medium leading-relaxed px-4 opacity-80">
            AI가 매시간 5,000개 이상의 정부 공고를 분석하여
            <br className="md:hidden" /> 우리 기업에 딱 맞는 지원사업을 찾아드립니다
          </p>
        </div>
      )}

      {/* First visit: straight to onboarding */}
      {step === "IDLE" && (
        <>
          <OnboardingWizard onComplete={handleOnboardingComplete} />
          <button
            onClick={() => setStep("LOGIN")}
            className="mt-4 text-slate-400 hover:text-indigo-600 text-xs font-black transition-all"
          >
            이미 계정이 있으신가요? 로그인
          </button>
        </>
      )}

      {/* Continuing onboarding (e.g. after login found incomplete profile) */}
      {step === "ONBOARDING" && (
        <OnboardingWizard
          initialBusinessNumber={businessNumber}
          onComplete={handleOnboardingComplete}
          onLogout={handleLogout}
        />
      )}

      {/* Returning user login */}
      {step === "LOGIN" && (
        <AuthPage onLoginSuccess={handleLoginSuccess} onGoToRegister={() => setStep("IDLE")} initialEmail={typeof window !== "undefined" ? localStorage.getItem("last_email") || "" : ""} />
      )}

      {step === "LOADING" && <SkeletonLoader />}

      {step === "PROFILE" && (
        <ProfileSettings profile={profileData} onSave={handleConfirm} onClose={() => setStep("RESULTS")} onLogout={handleLogout} />
      )}

      {step === "RESULTS" && (
        <div className="flex justify-center">
          <Dashboard
            matches={matches}
            profile={profileData}
            onEditProfile={handleEditProfile}
            onLogout={handleLogout}
            planStatus={planStatus}
            onUpgrade={() => setShowPayment(true)}
            consultantResult={consultantResult}
            onClearConsultant={() => setConsultantResult(null)}
          />
        </div>
      )}

      {showPayment && (
        <PaymentModal
          planStatus={planStatus}
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

      <AiConsultModal />
      <AiChatBot />

      {step !== "RESULTS" && (
        <footer className="mt-8 md:mt-10 text-slate-400 text-[9px] font-black tracking-[0.2em] md:tracking-[0.2em] uppercase opacity-40">
          &copy; 2026 지원금톡톡
        </footer>
      )}
    </main>
  );
}
