"use client";

import { useState, useEffect, useCallback } from "react";
import Dashboard from "@/components/Dashboard";
import OnboardingWizard from "@/components/OnboardingWizard";
import ProfileSettings from "@/components/ProfileSettings";
import SkeletonLoader from "@/components/ui/SkeletonLoader";

export default function Home() {
  const [step, setStep] = useState<"IDLE" | "LOADING" | "PROFILE" | "RESULTS" | "ONBOARDING">("IDLE");
  const [businessNumber, setBusinessNumber] = useState("");
  const [profileData, setProfileData] = useState<any>(null);
  const [matches, setMatches] = useState<any[]>([]);
  const [updateRequired, setUpdateRequired] = useState(false);

  // Helper for profile editing
  const handleEditProfile = () => setStep("PROFILE");

  const performMatching = useCallback(async (bn: string) => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/match`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ business_number: bn })
      });
      const result = await res.json();
      
      if (result.status === "SUCCESS") {
        setMatches(result.data);
        setStep("RESULTS");
      } else {
        throw new Error(result.detail || "매칭 실패");
      }
    } catch (err) {
      alert("매칭 수행 중 오류가 발생했습니다.");
      setStep("IDLE");
    }
  }, []);

  const handleOnboardingComplete = async (data: any) => {
    setStep("LOADING");
    setBusinessNumber(data.business_number);
    localStorage.setItem("saved_bn", data.business_number);
    
    try {
      // 1. Save Profile
      const profilePayload = {
        ...data,
        industry_code: data.industry_code || "00000",
        revenue_bracket: "UNDER_1B",
        employee_count_bracket: "UNDER_10"
      };
      
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/save-profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profilePayload)
      });

      // 2. Save Notification Settings
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/notification-settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_number: data.business_number,
          channel: "EMAIL",
          is_active: data.notification_enabled
        })
      });

      // 3. Perform Matching
      setProfileData(profilePayload);
      await performMatching(data.business_number);
      
    } catch (err) {
      alert("온보딩 처리 중 오류가 발생했습니다.");
      setStep("IDLE");
    }
  };

  const handleSearch = async (targetBN?: string) => {
    const bn = targetBN || businessNumber;
    if (bn.length !== 10) {
      setStep("ONBOARDING"); 
      return;
    }
    
    setStep("LOADING");
    localStorage.setItem("saved_bn", bn);
    
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/fetch-company`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ business_number: bn })
      });
      const result = await res.json();
      
      if (result.status === "SUCCESS") {
        setProfileData(result.data);
        if (result.type === "EXISTING") {
          if (result.requires_update) {
            setUpdateRequired(true);
          }
          await performMatching(bn);
        } else {
          // New User? Go to Onboarding Wizard
          setStep("ONBOARDING");
        }
      }
    } catch (err) {
      setStep("ONBOARDING");
    }
  };

  useEffect(() => {
    const saved = localStorage.getItem("saved_bn");
    if (saved && saved.length === 10) {
      setBusinessNumber(saved);
      handleSearch(saved);
    }
  }, []);

  const handleConfirm = async (finalData: any) => {
    setStep("LOADING");
    try {
      const payload = {
        ...finalData,
        revenue_bracket: finalData.revenue,
        employee_count_bracket: finalData.employees,
      };
      setProfileData(payload);
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/save-profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      const result = await res.json();
      if (result.status === "SUCCESS") {
        await performMatching(businessNumber);
      } else {
        alert("프로필 저장에 실패했습니다.");
        setStep("PROFILE");
      }
    } catch (err) {
      alert("매칭 수행 중 오류가 발생했습니다.");
      setStep("PROFILE");
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("saved_bn");
    setBusinessNumber("");
    setStep("IDLE");
    setMatches([]);
    setProfileData(null);
  };

  return (
    <main className={`min-h-screen flex flex-col ${step === "RESULTS" ? 'items-stretch pt-8 md:pt-14 px-4 md:px-12 lg:px-20 pb-12 md:pb-20' : 'items-center justify-center p-6'}`}>
      
      {updateRequired && step === "RESULTS" && (
        <div className="w-full max-w-[1600px] mx-auto mb-6 md:mb-8 p-4 md:p-6 bg-amber-50 border border-amber-200 rounded-3xl md:rounded-[2.5rem] flex flex-col md:flex-row items-center justify-between gap-4 md:gap-0 animate-in slide-in-from-top duration-500 shadow-sm">
          <div className="flex items-center gap-3 md:gap-4">
            <span className="text-2xl md:text-3xl">📅</span>
            <div>
              <p className="text-amber-900 font-black text-sm md:text-base">매출 정보 업데이트 필요</p>
              <p className="text-amber-700 text-xs md:text-sm font-medium">정기 신고 기간이 경과되었습니다. 정보를 갱신해 주세요.</p>
            </div>
          </div>
          <button onClick={() => setStep("PROFILE")} className="w-full md:w-auto px-6 py-3 bg-amber-500 text-white rounded-xl md:rounded-2xl font-black hover:bg-amber-600 transition-all shadow-lg text-sm">
            지금 업데이트
          </button>
        </div>
      )}

      {/* Hero Header (Hidden when results match) */}
      {(step === "IDLE" || step === "ONBOARDING") && (
        <div className="text-center mb-6 md:mb-8 animate-in fade-in duration-500">
           <h1 className="text-2xl md:text-3xl lg:text-4xl font-black text-slate-900 mb-2 tracking-tighter">AI 맞춤 <span className="text-indigo-600 italic">정부지원금 매칭</span></h1>
           <p className="text-slate-500 text-xs md:text-sm max-w-sm mx-auto font-medium leading-relaxed px-4 opacity-80">
             우리 기업에 딱 맞는 정부지원금을 <br className="md:hidden" /> AI가 자동으로 찾아드립니다
           </p>
        </div>
      )}

      {step === "IDLE" && (
        <OnboardingWizard onComplete={handleOnboardingComplete} />
      )}

      {step === "ONBOARDING" && (
        <OnboardingWizard initialBusinessNumber={businessNumber} onComplete={handleOnboardingComplete} onLogout={handleLogout} />
      )}

      {step === "LOADING" && <SkeletonLoader />}
      
      {step === "PROFILE" && (
        <ProfileSettings profile={profileData} onSave={handleConfirm} onClose={() => setStep("RESULTS")} />
      )}
      
      {step === "RESULTS" && (
        <div className="flex justify-center">
          <Dashboard matches={matches} profile={profileData} onEditProfile={handleEditProfile} onLogout={handleLogout} />
        </div>
      )}

      {step !== "RESULTS" && (
        <footer className="mt-8 md:mt-10 text-slate-400 text-[9px] font-black tracking-[0.2em] md:tracking-[0.2em] uppercase opacity-40">
          &copy; 2026 AI 맞춤 정부지원금 매칭
        </footer>
      )}
    </main>
  );
}
