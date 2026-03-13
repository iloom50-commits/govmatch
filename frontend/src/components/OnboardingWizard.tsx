"use client";

import { useState, useEffect } from "react";
import { useToast } from "@/components/ui/Toast";
import EmailInput from "@/components/ui/EmailInput";

interface OnboardingWizardProps {
  initialBusinessNumber?: string;
  onComplete: (data: any) => void;
  onLogout?: () => void;
}

export default function OnboardingWizard({ initialBusinessNumber = "", onComplete, onLogout }: OnboardingWizardProps) {
  const { toast } = useToast();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [industryQuery, setIndustryQuery] = useState("");
  const [industryCandidates, setIndustryCandidates] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [dateText, setDateText] = useState("");
  
  const [formData, setFormData] = useState({
    business_number: initialBusinessNumber,
    business_type: "" as "" | "individual" | "corporation",
    company_name: "",
    address_city: "전국",
    establishment_date: "",
    interests: "",
    industry_code: "",
    revenue_bracket: "",
    employee_count_bracket: "",
    notification_enabled: true,
    email: "",
    password: "",
    push_enabled: false,
  });

  const INTEREST_BY_INDUSTRY: Record<string, { id: string; label: string; tag: string; icon: string }[]> = {
    "56": [
      { id: "facility", label: "인테리어/시설 개선", tag: "시설개선", icon: "🏗️" },
      { id: "sales", label: "배달/온라인 판로", tag: "판로개척", icon: "📦" },
      { id: "hiring", label: "직원 채용/인건비", tag: "고용지원", icon: "👥" },
      { id: "hygiene", label: "위생/안전 설비", tag: "위생안전", icon: "🛡️" },
      { id: "fund", label: "소상공인 정책자금", tag: "정책자금", icon: "💰" },
    ],
    "47": [
      { id: "facility", label: "매장 개선/리모델링", tag: "시설개선", icon: "🏗️" },
      { id: "digital", label: "온라인 쇼핑몰/디지털 전환", tag: "디지털전환", icon: "💻" },
      { id: "hiring", label: "직원 채용/인건비", tag: "고용지원", icon: "👥" },
      { id: "marketing", label: "마케팅/홍보 지원", tag: "판로개척", icon: "📢" },
      { id: "fund", label: "소상공인 정책자금", tag: "정책자금", icon: "💰" },
    ],
    "96": [
      { id: "facility", label: "매장 리모델링", tag: "시설개선", icon: "🏗️" },
      { id: "hiring", label: "직원 채용/인건비", tag: "고용지원", icon: "👥" },
      { id: "marketing", label: "온라인 마케팅/홍보", tag: "판로개척", icon: "📢" },
      { id: "training", label: "기술 교육/자격증", tag: "직업훈련", icon: "🎓" },
      { id: "fund", label: "소상공인 정책자금", tag: "정책자금", icon: "💰" },
    ],
    "55": [
      { id: "facility", label: "시설 개선/리모델링", tag: "시설개선", icon: "🏗️" },
      { id: "marketing", label: "온라인 예약/홍보", tag: "판로개척", icon: "📢" },
      { id: "hiring", label: "직원 채용/인건비", tag: "고용지원", icon: "👥" },
      { id: "eco", label: "친환경/에너지 전환", tag: "에너지절감", icon: "🌿" },
      { id: "fund", label: "소상공인 정책자금", tag: "정책자금", icon: "💰" },
    ],
    "85": [
      { id: "facility", label: "교육 시설/장비 개선", tag: "시설개선", icon: "🏗️" },
      { id: "digital", label: "디지털 교육 전환", tag: "디지털전환", icon: "💻" },
      { id: "hiring", label: "강사 채용/인건비", tag: "고용지원", icon: "👥" },
      { id: "training", label: "직업훈련 프로그램", tag: "직업훈련", icon: "🎓" },
      { id: "fund", label: "소상공인 정책자금", tag: "정책자금", icon: "💰" },
    ],
    "62": [
      { id: "tech", label: "기술개발(R&D)", tag: "기술개발", icon: "🚀" },
      { id: "export", label: "해외 수출/글로벌", tag: "수출마케팅", icon: "🌐" },
      { id: "hiring", label: "인력 채용/교육", tag: "고용지원", icon: "👥" },
      { id: "ip", label: "특허/지식재산권", tag: "지식재산", icon: "📜" },
      { id: "infra", label: "클라우드/인프라", tag: "디지털전환", icon: "☁️" },
    ],
    "58": [
      { id: "tech", label: "기술개발(R&D)", tag: "기술개발", icon: "🚀" },
      { id: "export", label: "해외 수출/글로벌", tag: "수출마케팅", icon: "🌐" },
      { id: "hiring", label: "인력 채용/교육", tag: "고용지원", icon: "👥" },
      { id: "ip", label: "특허/지식재산권", tag: "지식재산", icon: "📜" },
      { id: "startup", label: "창업/사업화 지원", tag: "창업지원", icon: "🌱" },
    ],
    "63": [
      { id: "tech", label: "기술개발(R&D)", tag: "기술개발", icon: "🚀" },
      { id: "export", label: "해외 수출/글로벌", tag: "수출마케팅", icon: "🌐" },
      { id: "hiring", label: "인력 채용/교육", tag: "고용지원", icon: "👥" },
      { id: "data", label: "데이터/AI 인프라", tag: "디지털전환", icon: "🤖" },
      { id: "startup", label: "창업/사업화 지원", tag: "창업지원", icon: "🌱" },
    ],
    "10": [
      { id: "tech", label: "기술개발(R&D)", tag: "기술개발", icon: "🚀" },
      { id: "facility", label: "설비 투자/자동화", tag: "시설개선", icon: "🏭" },
      { id: "export", label: "수출/판로 개척", tag: "수출마케팅", icon: "🌐" },
      { id: "hiring", label: "인력 채용/교육", tag: "고용지원", icon: "👥" },
      { id: "eco", label: "친환경/탄소중립", tag: "에너지절감", icon: "🌿" },
    ],
    "45": [
      { id: "facility", label: "정비 시설/장비", tag: "시설개선", icon: "🔧" },
      { id: "hiring", label: "직원 채용/인건비", tag: "고용지원", icon: "👥" },
      { id: "digital", label: "디지털 전환/예약시스템", tag: "디지털전환", icon: "💻" },
      { id: "eco", label: "친환경 차량/설비", tag: "에너지절감", icon: "🌿" },
      { id: "fund", label: "소상공인 정책자금", tag: "정책자금", icon: "💰" },
    ],
    "68": [
      { id: "digital", label: "프롭테크/디지털 전환", tag: "디지털전환", icon: "💻" },
      { id: "hiring", label: "직원 채용/인건비", tag: "고용지원", icon: "👥" },
      { id: "marketing", label: "마케팅/홍보 지원", tag: "판로개척", icon: "📢" },
      { id: "fund", label: "정책자금/대출", tag: "정책자금", icon: "💰" },
      { id: "startup", label: "창업/사업화 지원", tag: "창업지원", icon: "🌱" },
    ],
    "46": [
      { id: "export", label: "수출/해외 판로", tag: "수출마케팅", icon: "🌐" },
      { id: "digital", label: "온라인 유통/디지털 전환", tag: "디지털전환", icon: "💻" },
      { id: "hiring", label: "직원 채용/인건비", tag: "고용지원", icon: "👥" },
      { id: "logistics", label: "물류/창고 개선", tag: "시설개선", icon: "📦" },
      { id: "fund", label: "정책자금/대출", tag: "정책자금", icon: "💰" },
    ],
    "49": [
      { id: "facility", label: "차량/장비 도입", tag: "시설개선", icon: "🚛" },
      { id: "digital", label: "배차/물류 시스템", tag: "디지털전환", icon: "💻" },
      { id: "hiring", label: "운전기사/직원 채용", tag: "고용지원", icon: "👥" },
      { id: "eco", label: "친환경 차량 전환", tag: "에너지절감", icon: "🌿" },
      { id: "fund", label: "정책자금/대출", tag: "정책자금", icon: "💰" },
    ],
    "52": [
      { id: "facility", label: "창고/물류센터 개선", tag: "시설개선", icon: "🏭" },
      { id: "digital", label: "재고관리/자동화 시스템", tag: "디지털전환", icon: "💻" },
      { id: "hiring", label: "직원 채용/인건비", tag: "고용지원", icon: "👥" },
      { id: "eco", label: "에너지 절감/친환경", tag: "에너지절감", icon: "🌿" },
      { id: "fund", label: "정책자금/대출", tag: "정책자금", icon: "💰" },
    ],
    "41": [
      { id: "tech", label: "스마트 건설/기술개발", tag: "기술개발", icon: "🚀" },
      { id: "facility", label: "장비/설비 투자", tag: "시설개선", icon: "🏗️" },
      { id: "hiring", label: "기능인력 채용/교육", tag: "고용지원", icon: "👥" },
      { id: "safety", label: "안전관리/인증", tag: "위생안전", icon: "🛡️" },
      { id: "fund", label: "정책자금/대출", tag: "정책자금", icon: "💰" },
    ],
    "42": [
      { id: "tech", label: "스마트 건설/기술개발", tag: "기술개발", icon: "🚀" },
      { id: "facility", label: "중장비/설비 투자", tag: "시설개선", icon: "🏗️" },
      { id: "hiring", label: "기능인력 채용/교육", tag: "고용지원", icon: "👥" },
      { id: "safety", label: "안전관리/인증", tag: "위생안전", icon: "🛡️" },
      { id: "fund", label: "정책자금/대출", tag: "정책자금", icon: "💰" },
    ],
    "75": [
      { id: "facility", label: "의료 장비/시설 개선", tag: "시설개선", icon: "🏥" },
      { id: "digital", label: "예약/관리 시스템", tag: "디지털전환", icon: "💻" },
      { id: "hiring", label: "수의사/직원 채용", tag: "고용지원", icon: "👥" },
      { id: "training", label: "전문 교육/자격", tag: "직업훈련", icon: "🎓" },
      { id: "fund", label: "소상공인 정책자금", tag: "정책자금", icon: "💰" },
    ],
    "86": [
      { id: "facility", label: "의료기기/시설 투자", tag: "시설개선", icon: "🏥" },
      { id: "digital", label: "전자차트/디지털 전환", tag: "디지털전환", icon: "💻" },
      { id: "hiring", label: "의료진/직원 채용", tag: "고용지원", icon: "👥" },
      { id: "tech", label: "의료 R&D/신기술", tag: "기술개발", icon: "🚀" },
      { id: "fund", label: "정책자금/대출", tag: "정책자금", icon: "💰" },
    ],
    "91": [
      { id: "facility", label: "체육시설/장비 개선", tag: "시설개선", icon: "🏟️" },
      { id: "hiring", label: "강사/직원 채용", tag: "고용지원", icon: "👥" },
      { id: "marketing", label: "온라인 마케팅/회원관리", tag: "판로개척", icon: "📢" },
      { id: "digital", label: "예약/결제 시스템", tag: "디지털전환", icon: "💻" },
      { id: "fund", label: "소상공인 정책자금", tag: "정책자금", icon: "💰" },
    ],
    "90": [
      { id: "facility", label: "공연장/작업공간 개선", tag: "시설개선", icon: "🎭" },
      { id: "hiring", label: "예술인/스태프 채용", tag: "고용지원", icon: "👥" },
      { id: "marketing", label: "홍보/관객 개발", tag: "판로개척", icon: "📢" },
      { id: "export", label: "해외 진출/교류", tag: "수출마케팅", icon: "🌐" },
      { id: "fund", label: "문화예술 지원금", tag: "정책자금", icon: "💰" },
    ],
    "81": [
      { id: "facility", label: "장비/차량 도입", tag: "시설개선", icon: "🧹" },
      { id: "hiring", label: "직원 채용/인건비", tag: "고용지원", icon: "👥" },
      { id: "safety", label: "안전/방역 인증", tag: "위생안전", icon: "🛡️" },
      { id: "digital", label: "관리 시스템/앱", tag: "디지털전환", icon: "💻" },
      { id: "fund", label: "소상공인 정책자금", tag: "정책자금", icon: "💰" },
    ],
    "95": [
      { id: "facility", label: "수리 장비/공구 투자", tag: "시설개선", icon: "🔧" },
      { id: "hiring", label: "기술자 채용/인건비", tag: "고용지원", icon: "👥" },
      { id: "training", label: "기술 교육/자격증", tag: "직업훈련", icon: "🎓" },
      { id: "digital", label: "예약/관리 시스템", tag: "디지털전환", icon: "💻" },
      { id: "fund", label: "소상공인 정책자금", tag: "정책자금", icon: "💰" },
    ],
  };

  const DEFAULT_INTERESTS = [
    { id: "tech", label: "기술개발(R&D)", tag: "기술개발", icon: "🚀" },
    { id: "export", label: "수출/마케팅", tag: "수출마케팅", icon: "🌐" },
    { id: "hiring", label: "신규 채용/인력", tag: "고용지원", icon: "👥" },
    { id: "startup", label: "창업/사업화", tag: "창업지원", icon: "🌱" },
    { id: "fund", label: "정책자금/대출", tag: "정책자금", icon: "💰" },
  ];

  const ksicPrefix = formData.industry_code?.substring(0, 2) || "";
  const interestOptions = INTEREST_BY_INDUSTRY[ksicPrefix] || DEFAULT_INTERESTS;

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
      if (!formData.business_type) {
        toast("개인사업자 또는 법인을 선택해 주세요.", "error");
        return;
      }
      if (!formData.establishment_date) {
        toast(formData.business_type === "individual" ? "사업자 등록일을 입력해 주세요." : "법인 설립일을 입력해 주세요.", "error");
        return;
      }
      if (!formData.address_city || formData.address_city === "전국") {
        toast("소재지를 선택해 주세요.", "error");
        return;
      }
      setStep(2);
    } else if (step === 2) {
      if (!formData.interests) {
        toast("관심 분야를 하나 이상 선택해주세요.", "error");
        return;
      }
      setStep(3);
    } else if (step === 3) {
      if (!formData.revenue_bracket || !formData.employee_count_bracket) {
        toast("매출 규모와 직원 수를 선택해주세요.", "error");
        return;
      }
      setStep(4);
    } else if (step === 4) {
      setStep(5);
    } else if (step === 5) {
      if (!formData.email || !formData.email.includes("@")) {
        toast("매칭 결과를 받을 이메일을 입력해 주세요.", "error");
        return;
      }
      if (!formData.password || formData.password.length < 6) {
        toast("비밀번호는 6자 이상 입력해 주세요.", "error");
        return;
      }
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

  const TOTAL_STEPS = 5;

  return (
    <div className="w-full max-w-xl bg-white/70 backdrop-blur-3xl rounded-[2rem] sm:rounded-[2.5rem] p-5 sm:p-8 md:p-12 shadow-2xl border border-white/60 animate-in zoom-in-95 duration-500 relative overflow-hidden">
      <div className="absolute -top-24 -right-24 w-48 h-48 bg-indigo-500/10 blur-[80px] rounded-full pointer-events-none" />
      
      <div className="relative z-10">
        <div className="flex justify-center gap-2 mb-5 sm:mb-8">
          {Array.from({ length: TOTAL_STEPS }, (_, i) => i + 1).map(s => (
            <div 
              key={s} 
              className={`h-1.5 rounded-full transition-all duration-500 ${s === step ? 'w-8 bg-indigo-600' : s < step ? 'w-4 bg-indigo-300' : 'w-2 bg-slate-200'}`} 
            />
          ))}
        </div>

        <div className="text-center mb-6 sm:mb-10">
          <h2 className="text-xl sm:text-2xl md:text-3xl font-black text-slate-900 tracking-tight mb-2">
            {step === 1 && "기업 기본정보를 알려주세요"}
            {step === 2 && "관심 분야를 알려주세요"}
            {step === 3 && "기업 규모를 알려주세요"}
            {step === 4 && "업종을 선택해 주세요"}
            {step === 5 && "맞춤 매칭 결과를 받아보세요"}
          </h2>
          <p className="text-slate-500 text-xs font-bold uppercase tracking-widest opacity-60">
            {step === 1 && "업력 기반 맞춤 매칭을 위한 핵심 정보입니다"}
            {step === 2 && (ksicPrefix ? "업종에 맞는 관심 분야를 선택하세요" : "가장 필요한 지원금을 골라주세요")}
            {step === 3 && "매출과 직원 수에 맞는 지원금을 찾습니다"}
            {step === 4 && "정확한 매칭을 위한 핵심 정보입니다"}
            {step === 5 && "새로운 맞춤 공고가 뜨면 바로 알려드립니다"}
          </p>
        </div>

        <div className="min-h-[220px]">
          {/* STEP 1: Business Type + Date + City */}
          {step === 1 && (
            <div className="space-y-5 animate-in slide-in-from-right-8 duration-500">
              {/* Business Type */}
              <div className="space-y-2">
                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">사업자 유형</label>
                <div className="grid grid-cols-2 gap-2.5">
                  {[
                    { value: "individual" as const, label: "개인사업자", icon: "👤" },
                    { value: "corporation" as const, label: "법인", icon: "🏢" },
                  ].map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => setFormData({ ...formData, business_type: opt.value })}
                      className={`p-4 rounded-2xl border-2 transition-all flex items-center justify-center gap-2 ${
                        formData.business_type === opt.value
                          ? "bg-indigo-600 border-indigo-600 text-white shadow-lg scale-[1.02]"
                          : "bg-white border-slate-100 text-slate-600 hover:border-indigo-200"
                      }`}
                    >
                      <span className="text-lg">{opt.icon}</span>
                      <span className="text-sm font-black">{opt.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Establishment Date */}
              {formData.business_type && (
                <div className="space-y-2 animate-in fade-in duration-300">
                  <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">
                    {formData.business_type === "individual" ? "사업자 등록일 (개업일)" : "법인 설립일"}
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="date"
                      max={new Date().toISOString().split("T")[0]}
                      className="flex-1 p-4 border border-white/80 rounded-2xl bg-white/50 focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-bold outline-none shadow-inner"
                      value={formData.establishment_date}
                      onChange={(e) => {
                        setFormData({ ...formData, establishment_date: e.target.value });
                        setDateText(e.target.value);
                      }}
                    />
                    <input
                      type="text"
                      placeholder="YYYY-MM-DD"
                      maxLength={10}
                      className="w-28 sm:w-36 p-3 sm:p-4 border border-white/80 rounded-2xl bg-white/50 focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-bold outline-none text-center tracking-wider shadow-inner"
                      value={dateText}
                      onChange={(e) => {
                        let v = e.target.value.replace(/[^0-9-]/g, "");
                        if (v.length === 4 && !v.includes("-")) v += "-";
                        if (v.length === 7 && v.split("-").length === 2) v += "-";
                        setDateText(v);
                        if (/^\d{4}-\d{2}-\d{2}$/.test(v)) {
                          setFormData({ ...formData, establishment_date: v });
                        }
                      }}
                    />
                  </div>
                </div>
              )}

              {/* City */}
              {formData.business_type && (
                <div className="space-y-2 animate-in fade-in duration-300">
                  <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">소재지</label>
                  <div className="flex flex-wrap gap-1.5">
                    {["서울","경기","인천","부산","대구","대전","광주","울산","세종","강원","충북","충남","전북","전남","경북","경남","제주"].map(city => (
                      <button
                        key={city}
                        onClick={() => setFormData({ ...formData, address_city: city })}
                        className={`px-3 py-1.5 rounded-xl text-xs font-black transition-all border ${
                          formData.address_city === city
                            ? "bg-indigo-600 border-indigo-600 text-white shadow-md"
                            : "bg-white border-slate-100 text-slate-500 hover:border-indigo-200"
                        }`}
                      >
                        {city}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP 2: Interests */}
          {step === 2 && (
            <div className="space-y-4 animate-in slide-in-from-right-8 duration-500">
              <div className="grid grid-cols-2 gap-2">
                {interestOptions.map(opt => (
                  <button
                    key={opt.id}
                    onClick={() => toggleInterest(opt.tag)}
                    className={`p-3 sm:p-4 rounded-2xl border-2 transition-all flex items-center gap-2 text-left group ${
                      formData.interests.includes(opt.tag)
                        ? "bg-indigo-600 border-indigo-600 text-white shadow-lg scale-[1.02]"
                        : "bg-white border-slate-100 text-slate-600 hover:border-indigo-200"
                    }`}
                  >
                    <span className="text-xl flex-shrink-0 group-hover:scale-110 transition-transform">{opt.icon}</span>
                    <span className="text-xs font-black leading-tight">{opt.label}</span>
                  </button>
                ))}
              </div>
              <div className="relative">
                <input
                  type="text"
                  placeholder="기타 관심 분야를 직접 입력하세요"
                  className="w-full p-4 border border-slate-200 rounded-2xl bg-white/50 focus:ring-4 focus:ring-indigo-100 focus:bg-white transition-all text-sm font-medium outline-none"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      const val = (e.target as HTMLInputElement).value.trim();
                      if (val) {
                        toggleInterest(val);
                        (e.target as HTMLInputElement).value = "";
                      }
                    }
                  }}
                />
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[10px] text-slate-400 font-bold">Enter로 추가</span>
              </div>
              {formData.interests && (
                <div className="flex flex-wrap gap-1.5 px-1">
                  {formData.interests.split(',').filter(i => i.trim()).map((tag, i) => (
                    <span key={i} className="px-2.5 py-1 bg-indigo-100 text-indigo-700 text-[10px] font-black rounded-full flex items-center gap-1">
                      {tag}
                      <button onClick={() => toggleInterest(tag)} className="hover:text-rose-500 transition-colors">×</button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* STEP 3: Company Size */}
          {step === 3 && (
            <div className="space-y-6 animate-in slide-in-from-right-8 duration-500">
              <div className="space-y-2">
                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">연간 매출 규모</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { value: "1억 미만", label: "1억 미만" },
                    { value: "1억~5억", label: "1억 ~ 5억" },
                    { value: "5억~10억", label: "5억 ~ 10억" },
                    { value: "10억~50억", label: "10억 ~ 50억" },
                    { value: "50억 이상", label: "50억 이상" },
                  ].map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => setFormData({ ...formData, revenue_bracket: opt.value })}
                      className={`p-3 sm:p-4 rounded-2xl border-2 text-sm font-black transition-all ${
                        formData.revenue_bracket === opt.value
                          ? "bg-indigo-600 border-indigo-600 text-white shadow-lg scale-[1.02]"
                          : "bg-white border-slate-100 text-slate-700 hover:border-indigo-200"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">직원 수</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { value: "5인 미만", label: "5인 미만" },
                    { value: "5인~10인", label: "5 ~ 10인" },
                    { value: "10인~30인", label: "10 ~ 30인" },
                    { value: "30인~50인", label: "30 ~ 50인" },
                    { value: "50인 이상", label: "50인 이상" },
                  ].map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => setFormData({ ...formData, employee_count_bracket: opt.value })}
                      className={`p-3 sm:p-4 rounded-2xl border-2 text-sm font-black transition-all ${
                        formData.employee_count_bracket === opt.value
                          ? "bg-indigo-600 border-indigo-600 text-white shadow-lg scale-[1.02]"
                          : "bg-white border-slate-100 text-slate-700 hover:border-indigo-200"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* STEP 4: Industry Selection */}
          {step === 4 && (
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

          {/* STEP 5: Email + Password + Notification */}
          {step === 5 && (
            <div className="space-y-5 animate-in slide-in-from-right-8 duration-500">
              <EmailInput
                value={formData.email}
                onChange={(email) => setFormData({ ...formData, email })}
              />
              <div className="space-y-1.5">
                <label className="text-[10px] font-black text-indigo-500 uppercase tracking-[0.2em] ml-2">
                  다음 접속 시 사용할 비밀번호
                </label>
                <input
                  type="password"
                  required
                  minLength={6}
                  placeholder="6자 이상"
                  className="w-full p-4 border border-white/80 rounded-2xl bg-white/50 focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-bold outline-none shadow-inner"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                />
              </div>
              <div className="bg-slate-50 border border-slate-100 p-4 rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-base">📧</span>
                    <span className="text-xs font-black text-slate-700">이메일 매칭 알림</span>
                  </div>
                  <input
                    type="checkbox"
                    className="w-4 h-4 accent-indigo-600"
                    checked={formData.notification_enabled}
                    onChange={(e) => setFormData({ ...formData, notification_enabled: e.target.checked })}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-base">🔔</span>
                    <span className="text-xs font-black text-slate-700">브라우저 실시간 알림</span>
                  </div>
                  <input
                    type="checkbox"
                    className="w-4 h-4 accent-indigo-600"
                    checked={formData.push_enabled}
                    onChange={(e) => setFormData({ ...formData, push_enabled: e.target.checked })}
                  />
                </div>
                <p className="text-[10px] text-slate-400 font-medium">
                  매일 오전 10시, AI가 분석한 맞춤 리포트를 보내드립니다
                </p>
              </div>
              <p className="text-[10px] text-slate-400 text-center font-medium leading-relaxed">
                30일 무료체험이 시작됩니다.
              </p>
            </div>
          )}
        </div>

        <div className="mt-6 sm:mt-10 space-y-4">
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
              {loading ? "분석 중..." : step === TOTAL_STEPS ? "30일 무료 매칭 시작하기" : "다음 단계로"}
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
