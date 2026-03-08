"use client";

import { useState, useEffect } from "react";

interface OnboardingWizardProps {
  initialBusinessNumber?: string;
  onComplete: (data: any) => void;
  onLogout?: () => void;
}

export default function OnboardingWizard({ initialBusinessNumber = "", onComplete, onLogout }: OnboardingWizardProps) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [industryQuery, setIndustryQuery] = useState("");
  const [industryCandidates, setIndustryCandidates] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  
  const [formData, setFormData] = useState({
    business_number: initialBusinessNumber,
    company_name: "",
    address_city: "전국",
    establishment_date: new Date().toISOString().split('T')[0],
    interests: "",
    industry_code: "",
    notification_enabled: true
  });

  const interestOptions = [
    { id: "tech", label: "기술개발(R&D)", tag: "기술개발", icon: "🚀" },
    { id: "export", label: "수출/마케팅", tag: "수출/마케팅", icon: "🌐" },
    { id: "hiring", label: "신규 채용/인력", tag: "고용지원", icon: "👥" },
    { id: "startup", label: "창업/사업화", tag: "창업지원", icon: "🌱" }
  ];

  useEffect(() => {
    if (industryQuery.length < 2) {
      if (industryQuery.length === 0) setIndustryCandidates([]);
      return;
    }
    const timer = setTimeout(() => searchIndustry(true), 600);
    return () => clearTimeout(timer);
  }, [industryQuery]);

  const searchIndustry = async (silent = false) => {
    if (!industryQuery && !formData.company_name) return;
    if (!silent) setIsSearching(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/industry-recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company_name: formData.company_name,
          business_content: industryQuery
        })
      });
      const result = await res.json();
      if (result.status === "SUCCESS" && result.data.candidates) {
        setIndustryCandidates(result.data.candidates);
      }
    } catch (err) {
      console.error("Industry search failed", err);
    } finally {
      if (!silent) setIsSearching(false);
    }
  };

  const handleNext = async () => {
    if (step === 1) {
      if (formData.business_number.length !== 10) {
        alert("사업자 번호 10자리를 입력해주세요.");
        return;
      }
      setLoading(true);
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/fetch-company`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ business_number: formData.business_number })
        });
        const result = await res.json();
        if (result.status === "SUCCESS") {
          setFormData(prev => ({
            ...prev,
            company_name: result.data.company_name || prev.company_name,
            address_city: result.data.address_city || prev.address_city,
            establishment_date: result.data.establishment_date || prev.establishment_date,
            industry_code: result.data.industry_code || prev.industry_code
          }));
          setStep(2);
        }
      } catch (err) {
        alert("정보를 가져오는 중 오류가 발생했습니다.");
      } finally {
        setLoading(false);
      }
    } else if (step === 2) {
      if (!formData.interests) {
        alert("관심 분야를 하나 이상 선택해주세요.");
        return;
      }
      setStep(3);
    } else if (step === 3) {
      setStep(4);
    } else if (step === 4) {
      onComplete(formData);
    }
  };

  const toggleInterest = (tag: string) => {
    const current = formData.interests.split(',').filter(i => i.trim());
    if (current.includes(tag)) {
      setFormData({ ...formData, interests: current.filter(i => i !== tag).join(',') });
    } else {
      setFormData({ ...formData, interests: [...current, tag].join(',') });
    }
  };

  const TOTAL_STEPS = 4;

  return (
    <div className="w-full max-w-xl bg-white/70 backdrop-blur-3xl rounded-[2.5rem] p-8 md:p-12 shadow-2xl border border-white/60 animate-in zoom-in-95 duration-500 relative overflow-hidden">
      <div className="absolute -top-24 -right-24 w-48 h-48 bg-indigo-500/10 blur-[80px] rounded-full pointer-events-none" />
      
      <div className="relative z-10">
        <div className="flex justify-center gap-2 mb-8">
          {Array.from({ length: TOTAL_STEPS }, (_, i) => i + 1).map(s => (
            <div 
              key={s} 
              className={`h-1.5 rounded-full transition-all duration-500 ${s === step ? 'w-8 bg-indigo-600' : s < step ? 'w-4 bg-indigo-300' : 'w-2 bg-slate-200'}`} 
            />
          ))}
        </div>

        <div className="text-center mb-10">
          <h2 className="text-2xl md:text-3xl font-black text-slate-900 tracking-tight mb-2">
            {step === 1 && "기업 정보를 확인합니다"}
            {step === 2 && "관심 분야를 알려주세요"}
            {step === 3 && "업종을 선택해 주세요"}
            {step === 4 && "알림을 설정할까요?"}
          </h2>
          <p className="text-slate-500 text-xs font-bold uppercase tracking-widest opacity-60">
            {step === 1 && "사업자번호로 즉시 시작하세요"}
            {step === 2 && "가장 필요한 지원금을 골라주세요"}
            {step === 3 && "정확한 매칭을 위한 핵심 정보입니다"}
            {step === 4 && "매일 오전 10시, 맞춤 소식을 드립니다"}
          </p>
        </div>

        <div className="min-h-[220px]">
          {/* STEP 1: Business Number */}
          {step === 1 && (
            <div className="space-y-6 animate-in slide-in-from-right-8 duration-500">
              <div className="space-y-2">
                <label className="text-[10px] font-black text-indigo-500 uppercase tracking-[0.2em] ml-2">Business Number</label>
                <input 
                  type="text" 
                  maxLength={10}
                  placeholder="0000000000"
                  className="w-full p-5 border border-white/80 rounded-2xl bg-white/50 focus:ring-4 focus:ring-indigo-500/5 focus:border-indigo-500 transition-all text-2xl font-black tracking-tighter outline-none text-center shadow-inner"
                  value={formData.business_number}
                  onChange={(e) => setFormData({ ...formData, business_number: e.target.value.replace(/[^0-9]/g, "") })}
                  onKeyDown={(e) => e.key === "Enter" && handleNext()}
                />
              </div>
              <p className="text-[10px] text-slate-400 text-center font-medium leading-relaxed">
                사업자번호를 입력하면 지역과 업력이 자동으로 설정됩니다.
              </p>
            </div>
          )}

          {/* STEP 2: Interests */}
          {step === 2 && (
            <div className="grid grid-cols-2 gap-3 animate-in slide-in-from-right-8 duration-500">
              {interestOptions.map(opt => (
                <button
                  key={opt.id}
                  onClick={() => toggleInterest(opt.tag)}
                  className={`p-5 rounded-3xl border-2 transition-all flex flex-col items-center justify-center text-center gap-2 group ${
                    formData.interests.includes(opt.tag)
                      ? "bg-indigo-600 border-indigo-600 text-white shadow-lg scale-105"
                      : "bg-white border-slate-100 text-slate-600 hover:border-indigo-100"
                  }`}
                >
                  <span className="text-2xl group-hover:scale-110 transition-transform">{opt.icon}</span>
                  <span className="text-xs font-black">{opt.label}</span>
                </button>
              ))}
            </div>
          )}

          {/* STEP 3: Industry Selection */}
          {step === 3 && (
            <div className="space-y-4 animate-in slide-in-from-right-8 duration-500">
              <div className="flex justify-between items-end px-1">
                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">사업 내용으로 검색</label>
                <button 
                  onClick={() => searchIndustry(false)}
                  disabled={isSearching}
                  className="text-indigo-600 text-[10px] font-black flex items-center gap-1 hover:text-indigo-800 transition-colors"
                >
                  {isSearching ? '분석 중...' : '✨ AI 추천'}
                </button>
              </div>

              <textarea 
                placeholder="예: 화장품 온라인 쇼핑몰 및 SNS 광고 대행"
                className="w-full p-4 border border-slate-200 rounded-2xl bg-white/50 focus:ring-4 focus:ring-indigo-100 focus:bg-white transition-all text-sm font-medium outline-none min-h-[80px]"
                value={industryQuery}
                onChange={(e) => setIndustryQuery(e.target.value)}
              />

              <input 
                type="text"
                placeholder="업종 코드 직접 입력 (5자리)"
                maxLength={5}
                className="w-full p-4 border border-slate-200 rounded-2xl bg-white focus:ring-4 focus:ring-indigo-100 transition-all text-lg font-black outline-none text-center tracking-widest"
                value={formData.industry_code}
                onChange={(e) => setFormData({ ...formData, industry_code: e.target.value.replace(/[^0-9]/g, "") })}
              />

              {industryCandidates.length > 0 && (
                <div className="space-y-2 max-h-[160px] overflow-y-auto pr-1">
                  <span className="text-[9px] font-black text-indigo-600 uppercase tracking-widest px-1">검색 결과 (하나를 선택하세요)</span>
                  {industryCandidates.map((cand, idx) => (
                    <button
                      key={idx}
                      onClick={() => setFormData({ ...formData, industry_code: cand.code })}
                      className={`w-full p-4 rounded-2xl text-left border-2 transition-all block ${
                        formData.industry_code === cand.code
                          ? "bg-indigo-600 border-indigo-600 text-white shadow-lg scale-[1.02]"
                          : "bg-white border-slate-100 text-slate-900 hover:border-indigo-200"
                      }`}
                    >
                      <span className={`text-[9px] font-black uppercase tracking-widest ${formData.industry_code === cand.code ? 'text-indigo-200' : 'text-slate-400'}`}>
                        KSIC {cand.code}
                      </span>
                      <p className="text-sm font-black mt-0.5">{cand.name}</p>
                    </button>
                  ))}
                </div>
              )}

              {!formData.industry_code && industryCandidates.length === 0 && (
                <p className="text-[10px] text-slate-400 text-center font-medium leading-relaxed">
                  사업 내용을 입력하면 AI가 업종을 추천합니다.<br/>건너뛰기도 가능합니다.
                </p>
              )}
            </div>
          )}

          {/* STEP 4: Notification Consent */}
          {step === 4 && (
            <div className="space-y-6 animate-in slide-in-from-right-8 duration-500 flex flex-col items-center">
              <div className="w-20 h-20 bg-amber-50 rounded-full flex items-center justify-center text-3xl shadow-inner mb-2 animate-bounce">🔔</div>
              <div className="bg-slate-50 border border-slate-100 p-6 rounded-3xl text-center w-full">
                <p className="text-sm font-black text-slate-800 mb-1">데일리 맞춤 브리핑</p>
                <p className="text-[11px] text-slate-500 font-medium">새로운 지원사업이 뜨면 AI가 분석하여<br/>오전 10시에 요약 리포트를 보내드립니다.</p>
              </div>
              <div className="flex items-center gap-3">
                 <input 
                   type="checkbox" 
                   id="notify" 
                   className="w-5 h-5 accent-indigo-600"
                   checked={formData.notification_enabled}
                   onChange={(e) => setFormData({ ...formData, notification_enabled: e.target.checked })}
                 />
                 <label htmlFor="notify" className="text-sm font-black text-slate-700 cursor-pointer">네, 매칭 알림을 받겠습니다 (추천)</label>
              </div>
            </div>
          )}
        </div>

        <div className="mt-10 space-y-4">
          <div className="flex gap-3">
            {step > 1 && (
              <button
                onClick={() => setStep(step - 1)}
                className="flex-1 py-5 bg-slate-100 text-slate-500 rounded-2xl font-black text-sm hover:bg-slate-200 transition-all active:scale-95"
              >
                ← 이전
              </button>
            )}
            <button 
              onClick={handleNext}
              disabled={loading}
              className={`${step > 1 ? 'flex-[2]' : 'w-full'} py-5 bg-slate-900 text-white rounded-2xl font-black text-base shadow-xl shadow-indigo-100 hover:bg-indigo-600 transition-all active:scale-95 flex items-center justify-center group`}
            >
              {loading ? "분석 중..." : step === TOTAL_STEPS ? "매칭 시작하기" : "다음 단계로"}
              {!loading && <span className="ml-2 group-hover:translate-x-1 transition-transform">→</span>}
            </button>
          </div>
          
          {onLogout && (
            <button 
              onClick={onLogout}
              className="w-full py-2 text-slate-400 hover:text-rose-500 text-[10px] font-black uppercase tracking-widest transition-all opacity-60"
            >
              처음으로 돌아가기
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
