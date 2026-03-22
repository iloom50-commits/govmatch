"use client";

import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import EmailInput from "@/components/ui/EmailInput";

interface OnboardingWizardProps {
  initialBusinessNumber?: string;
  initialEmail?: string;
  onComplete: (data: any) => void;
  onLogout?: () => void;
}

export default function OnboardingWizard({ initialBusinessNumber = "", initialEmail = "", onComplete, onLogout }: OnboardingWizardProps) {
  const { toast } = useToast();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  
  const [formData, setFormData] = useState({
    business_number: initialBusinessNumber,
    user_type: "" as "" | "individual" | "business" | "both",
    business_type: "" as "" | "individual" | "corporation",
    company_name: "",
    address_city: "",
    address_cities: ["전국"] as string[],
    establishment_date: "",
    interests: "",

    revenue_bracket: "",
    employee_count_bracket: "",
    notification_enabled: true,
    email: initialEmail,
    push_enabled: false,
    // 개인 프로필 필드
    age_range: "",
    income_level: "",
    family_type: "",
    employment_status: "",
  });

  const DEFAULT_INTERESTS = [
    { id: "tech", label: "기술개발(R&D)", tag: "기술개발", icon: "🚀" },
    { id: "export", label: "수출/마케팅", tag: "수출마케팅", icon: "🌐" },
    { id: "hiring", label: "신규 채용/인력", tag: "고용지원", icon: "👥" },
    { id: "startup", label: "창업/사업화", tag: "창업지원", icon: "🌱" },
    { id: "fund", label: "정책자금/대출", tag: "정책자금", icon: "💰" },
  ];

  const interestOptions = DEFAULT_INTERESTS;

  const handleNext = async () => {
    const st = stepType;

    if (st === "user_type") {
      if (!formData.user_type) {
        toast("지원금 유형을 선택해 주세요.", "error");
        return;
      }
      setStep(1);
    } else if (st === "personal_info_1") {
      if (!formData.age_range) {
        toast("나이대를 선택해 주세요.", "error");
        return;
      }
      setStep(step + 1);
    } else if (st === "personal_info_2") {
      setStep(step + 1);
    } else if (st === "business_info") {
      if (!formData.business_type) {
        toast("개인사업자 또는 법인을 선택해 주세요.", "error");
        return;
      }
      if (!formData.establishment_date) {
        toast(formData.business_type === "individual" ? "사업자 등록일을 입력해 주세요." : "법인 설립일을 입력해 주세요.", "error");
        return;
      }
      setStep(step + 1);
    } else if (st === "business_region") {
      if (!formData.address_cities || formData.address_cities.length === 0) {
        toast("관심지역을 선택해 주세요.", "error");
        return;
      }
      setStep(step + 1);
    } else if (st === "interests") {
      if (!formData.interests) {
        toast("관심 분야를 하나 이상 선택해주세요.", "error");
        return;
      }
      setStep(step + 1);
    } else if (st === "company_size") {
      if (!formData.revenue_bracket || !formData.employee_count_bracket) {
        toast("매출 규모와 직원 수를 선택해주세요.", "error");
        return;
      }
      setStep(step + 1);
    } else if (st === "account") {
      if (!formData.email || !formData.email.includes("@")) {
        toast("매칭 결과를 받을 이메일을 입력해 주세요.", "error");
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

  // 개인: step 0(유형) → 1(개인1) → 2(개인2) → 3(계정) = 4단계
  // 기업: step 0(유형) → 1(사업자) → 2(지역) → 3(관심) → 4(규모) → 5(계정) = 6단계
  // 둘다: step 0(유형) → 1(개인1) → 2(개인2) → 3(사업자) → 4(지역) → 5(관심) → 6(규모) → 7(계정) = 8단계
  const isIndividualOnly = formData.user_type === "individual";
  const isBoth = formData.user_type === "both";
  const TOTAL_STEPS = isIndividualOnly ? 4 : isBoth ? 8 : 6;

  // step 번호를 논리적 단계로 매핑
  const getStepType = (s: number): string => {
    if (s === 0) return "user_type";
    if (isIndividualOnly) {
      if (s === 1) return "personal_info_1";
      if (s === 2) return "personal_info_2";
      if (s === 3) return "account";
    } else if (isBoth) {
      if (s === 1) return "personal_info_1";
      if (s === 2) return "personal_info_2";
      if (s === 3) return "business_info";
      if (s === 4) return "business_region";
      if (s === 5) return "interests";
      if (s === 6) return "company_size";
      if (s === 7) return "account";
    } else {
      // business
      if (s === 1) return "business_info";
      if (s === 2) return "business_region";
      if (s === 3) return "interests";
      if (s === 4) return "company_size";
      if (s === 5) return "account";
    }
    return "unknown";
  };

  const stepType = getStepType(step);

  return (
    <div className="w-full max-w-xl bg-white/70 backdrop-blur-3xl rounded-[2rem] sm:rounded-[2.5rem] p-5 sm:p-8 md:p-12 shadow-2xl border border-white/60 animate-in zoom-in-95 duration-500 relative overflow-hidden">
      <div className="absolute -top-24 -right-24 w-48 h-48 bg-indigo-500/10 blur-[80px] rounded-full pointer-events-none" />
      
      <div className="relative z-10">
        {/* Progress bar */}
        <div className="mb-6 sm:mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-bold text-indigo-600 tracking-wide">
              {step + 1} / {TOTAL_STEPS} 단계
            </span>
            <span className="text-[11px] font-bold text-slate-400">
              {Math.round(((step + 1) / TOTAL_STEPS) * 100)}%
            </span>
          </div>
          <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 to-indigo-600 rounded-full transition-all duration-700 ease-out"
              style={{ width: `${((step + 1) / TOTAL_STEPS) * 100}%` }}
            />
          </div>
        </div>

        <div className="text-center mb-5 sm:mb-7">
          {stepType !== "personal_info_1" && stepType !== "personal_info_2" && stepType !== "business_region" && (
            <h2 className="text-xl sm:text-2xl md:text-3xl font-black text-slate-900 tracking-tight mb-2">
              {stepType === "user_type" && "어떤 지원금을 찾으세요?"}
              {stepType === "business_info" && "사업자 정보를 알려주세요"}
              {stepType === "interests" && "관심 분야를 알려주세요"}
              {stepType === "company_size" && "기업 규모를 알려주세요"}
              {stepType === "account" && "맞춤 매칭 결과를 받아보세요"}
            </h2>
          )}
          <p className={`text-slate-400 font-semibold tracking-wide ${
            stepType === "personal_info_1" || stepType === "personal_info_2" || stepType === "business_region"
              ? "text-sm sm:text-base text-slate-500" : "text-xs"
          }`}>
            {stepType === "user_type" && "개인·기업 유형에 따라 매칭 가능한 지원금이 달라요"}
            {stepType === "personal_info_1" && "나이·소득 조건에 맞는 지원금을 걸러드려요"}
            {stepType === "personal_info_2" && "가구·취업 상황별 맞춤 지원금을 찾아드려요"}
            {stepType === "business_info" && "업력에 따라 신청 가능 여부가 결정돼요"}
            {stepType === "business_region" && "지역별로 다른 지원금이 있어요"}
            {stepType === "interests" && "관심 분야를 선택하면 우선순위를 높여 매칭해요"}
            {stepType === "company_size" && "지원금마다 매출·인원 기준이 달라 정확한 필터링이 필요해요"}
            {stepType === "account" && "새 공고가 뜨면 이메일로 바로 알려드려요"}
          </p>
        </div>

        <div className="min-h-[220px]">
          {/* STEP 0: 개인 / 기업 / 둘 다 선택 */}
          {stepType === "user_type" && (
            <div className="space-y-5 animate-in slide-in-from-right-8 duration-500">
              <div className="grid grid-cols-1 gap-3">
                {[
                  { value: "individual" as const, label: "개인 지원금", desc: "복지, 교육, 주거, 고용 등 개인 보조금", icon: "👤", color: "emerald" },
                  { value: "business" as const, label: "기업 지원금", desc: "소상공인, 창업, R&D 등 사업자 지원금", icon: "🏢", color: "indigo" },
                  { value: "both" as const, label: "둘 다", desc: "개인 보조금 + 기업 지원금 모두 매칭", icon: "🔄", color: "violet" },
                ].map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => {
                      setFormData({ ...formData, user_type: opt.value });
                      setStep(1);
                    }}
                    className={`p-5 rounded-2xl border-2 transition-all flex items-center gap-4 text-left ${
                      formData.user_type === opt.value
                        ? opt.color === "emerald"
                          ? "bg-emerald-600 border-emerald-600 text-white shadow-lg"
                          : opt.color === "indigo"
                          ? "bg-indigo-600 border-indigo-600 text-white shadow-lg"
                          : "bg-violet-600 border-violet-600 text-white shadow-lg"
                        : "bg-white border-slate-100 text-slate-600 hover:border-slate-300 hover:shadow-md"
                    }`}
                  >
                    <span className="text-2xl">{opt.icon}</span>
                    <div>
                      <span className="text-sm font-black block">{opt.label}</span>
                      <span className={`text-xs font-medium ${formData.user_type === opt.value ? "text-white/80" : "text-slate-400"}`}>{opt.desc}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 개인 정보 1단계: 나이대 + 소득 수준 */}
          {stepType === "personal_info_1" && (
            <div className="space-y-4 animate-in slide-in-from-right-8 duration-500">
              {/* 나이대 — 필수 */}
              <div className="bg-slate-50/60 rounded-2xl p-4 border border-slate-100/80">
                <label className="text-[11px] font-black text-slate-500 uppercase tracking-widest ml-0.5 flex items-center gap-1 mb-2.5">
                  나이대 <span className="text-rose-400 text-[11px]">*</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {["20대", "30대", "40대", "50대", "60대 이상"].map(v => (
                    <button
                      key={v}
                      onClick={() => setFormData({ ...formData, age_range: v })}
                      className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${
                        formData.age_range === v
                          ? "bg-indigo-600 text-white shadow-md ring-2 ring-indigo-600/20"
                          : "bg-white border border-slate-200 text-slate-600 hover:border-indigo-300 hover:bg-indigo-50/30"
                      }`}
                    >
                      {v}
                    </button>
                  ))}
                </div>
              </div>

              {/* 소득 수준 — 선택 */}
              <div className="bg-slate-50/60 rounded-2xl p-4 border border-slate-100/80">
                <label className="text-[11px] font-black text-slate-500 uppercase tracking-widest ml-0.5 flex items-center gap-1 mb-2.5">
                  소득 수준 <span className="text-[11px] text-slate-300 font-semibold normal-case tracking-normal">(선택)</span>
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {[
                    { value: "기초생활", label: "기초생활수급" },
                    { value: "차상위", label: "차상위계층" },
                    { value: "중위50%이하", label: "중위 50% 이하" },
                    { value: "중위75%이하", label: "중위 75% 이하" },
                    { value: "중위100%이하", label: "중위 100% 이하" },
                    { value: "해당없음", label: "해당없음/모름" },
                  ].map(v => (
                    <button
                      key={v.value}
                      onClick={() => setFormData({ ...formData, income_level: v.value })}
                      className={`px-3 py-2.5 rounded-xl text-xs font-bold transition-all text-center ${
                        formData.income_level === v.value
                          ? "bg-indigo-600 text-white shadow-md ring-2 ring-indigo-600/20"
                          : "bg-white border border-slate-200 text-slate-600 hover:border-indigo-300 hover:bg-indigo-50/30"
                      }`}
                    >
                      {v.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* 개인 정보 2단계: 가구 형태 + 취업 상태 + 관심지역 */}
          {stepType === "personal_info_2" && (
            <div className="space-y-4 animate-in slide-in-from-right-8 duration-500">
              {/* 가구 형태 — 선택 */}
              <div className="bg-slate-50/60 rounded-2xl p-4 border border-slate-100/80">
                <label className="text-[11px] font-black text-slate-500 uppercase tracking-widest ml-0.5 flex items-center gap-1 mb-2.5">
                  가구 형태 <span className="text-[11px] text-slate-300 font-semibold normal-case tracking-normal">(선택)</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {[
                    { value: "1인가구", label: "1인 가구" },
                    { value: "다자녀", label: "다자녀" },
                    { value: "한부모", label: "한부모" },
                    { value: "신혼부부", label: "신혼부부" },
                    { value: "다문화", label: "다문화" },
                    { value: "일반", label: "일반" },
                  ].map(v => (
                    <button
                      key={v.value}
                      onClick={() => setFormData({ ...formData, family_type: v.value })}
                      className={`px-3 py-2.5 rounded-xl text-xs font-bold transition-all ${
                        formData.family_type === v.value
                          ? "bg-indigo-600 text-white shadow-md ring-2 ring-indigo-600/20"
                          : "bg-white border border-slate-200 text-slate-600 hover:border-indigo-300 hover:bg-indigo-50/30"
                      }`}
                    >
                      {v.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 취업 상태 — 선택 */}
              <div className="bg-slate-50/60 rounded-2xl p-4 border border-slate-100/80">
                <label className="text-[11px] font-black text-slate-500 uppercase tracking-widest ml-0.5 flex items-center gap-1 mb-2.5">
                  취업 상태 <span className="text-[11px] text-slate-300 font-semibold normal-case tracking-normal">(선택)</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {[
                    { value: "재직자", label: "재직자" },
                    { value: "구직자", label: "구직자" },
                    { value: "자영업", label: "자영업" },
                    { value: "프리랜서", label: "프리랜서" },
                    { value: "학생", label: "학생" },
                    { value: "해당없음", label: "해당없음" },
                  ].map(v => (
                    <button
                      key={v.value}
                      onClick={() => setFormData({ ...formData, employment_status: v.value })}
                      className={`px-3 py-2.5 rounded-xl text-xs font-bold transition-all ${
                        formData.employment_status === v.value
                          ? "bg-indigo-600 text-white shadow-md ring-2 ring-indigo-600/20"
                          : "bg-white border border-slate-200 text-slate-600 hover:border-indigo-300 hover:bg-indigo-50/30"
                      }`}
                    >
                      {v.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 관심지역 (개인전용) */}
              {isIndividualOnly && (
                <div className="bg-slate-50/60 rounded-2xl p-4 border border-slate-100/80">
                  <label className="text-[11px] font-black text-slate-500 uppercase tracking-widest ml-0.5 flex items-center gap-1 mb-2.5">
                    관심지역 <span className="text-[11px] text-slate-300 font-semibold normal-case tracking-normal">(복수 선택 가능)</span>
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {["전국","서울","경기","인천","부산","대구","대전","광주","울산","세종","강원","충북","충남","전북","전남","경북","경남","제주"].map(city => {
                      const isAll = city === "전국";
                      const selected = isAll
                        ? formData.address_cities.includes("전국")
                        : formData.address_cities.includes(city);
                      return (
                        <button
                          key={city}
                          onClick={() => {
                            if (isAll) {
                              setFormData({ ...formData, address_cities: ["전국"], address_city: "전국" });
                            } else {
                              const without = formData.address_cities.filter(c => c !== "전국" && c !== city);
                              const next = selected ? without : [...without, city];
                              const final = next.length ? next : ["전국"];
                              setFormData({ ...formData, address_cities: final, address_city: final.join(",") });
                            }
                          }}
                          className={`px-2.5 py-1.5 rounded-lg text-[11px] font-bold transition-all ${
                            selected
                              ? "bg-indigo-600 text-white shadow-sm ring-2 ring-indigo-600/20"
                              : "bg-white border border-slate-200 text-slate-500 hover:border-indigo-300 hover:bg-indigo-50/30"
                          }`}
                        >
                          {city}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP: 사업자 유형 + 등록일 */}
          {stepType === "business_info" && (
            <div className="space-y-4 animate-in slide-in-from-right-8 duration-500">
              <div className="bg-slate-50/60 rounded-2xl p-4 border border-slate-100/80">
                <label className="text-[11px] font-black text-slate-500 uppercase tracking-widest ml-0.5 flex items-center gap-1 mb-2.5">
                  사업자 유형 <span className="text-rose-400 text-[11px]">*</span>
                </label>
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

              {formData.business_type && (
                <div className="bg-slate-50/60 rounded-2xl p-4 border border-slate-100/80 animate-in fade-in duration-300">
                  <label className="text-[11px] font-black text-slate-500 uppercase tracking-widest ml-0.5 flex items-center gap-1 mb-2.5">
                    {formData.business_type === "individual" ? "사업자 등록일 (개업일)" : "법인 설립일"} <span className="text-rose-400 text-[11px]">*</span>
                  </label>
                  <input
                    type="date"
                    max={new Date().toISOString().split("T")[0]}
                    className="w-full p-4 border border-white/80 rounded-2xl bg-white/50 focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-bold outline-none shadow-inner"
                    value={formData.establishment_date}
                    onChange={(e) => setFormData({ ...formData, establishment_date: e.target.value })}
                  />
                </div>
              )}
            </div>
          )}

          {/* STEP: 관심지역 */}
          {stepType === "business_region" && (
            <div className="space-y-4 animate-in slide-in-from-right-8 duration-500">
              <div className="bg-slate-50/60 rounded-2xl p-4 border border-slate-100/80">
                <label className="text-[11px] font-black text-slate-500 uppercase tracking-widest ml-0.5 flex items-center gap-1 mb-2.5">
                  관심지역 <span className="text-[11px] text-slate-300 font-semibold normal-case tracking-normal">(복수 선택 가능)</span>
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {["전국","서울","경기","인천","부산","대구","대전","광주","울산","세종","강원","충북","충남","전북","전남","경북","경남","제주"].map(city => {
                    const isAll = city === "전국";
                    const selected = isAll
                      ? formData.address_cities.includes("전국")
                      : formData.address_cities.includes(city);
                    return (
                      <button
                        key={city}
                        onClick={() => {
                          if (isAll) {
                            setFormData({ ...formData, address_cities: ["전국"], address_city: "전국" });
                          } else {
                            const without = formData.address_cities.filter((c: string) => c !== "전국");
                            const next = selected ? without.filter((c: string) => c !== city) : [...without, city];
                            const final = next.length === 0 ? ["전국"] : next;
                            setFormData({ ...formData, address_cities: final, address_city: final.join(",") });
                          }
                        }}
                        className={`px-2.5 py-1.5 rounded-lg text-[11px] font-bold transition-all ${
                          selected
                            ? "bg-indigo-600 text-white shadow-sm ring-2 ring-indigo-600/20"
                            : "bg-white border border-slate-200 text-slate-500 hover:border-indigo-300 hover:bg-indigo-50/30"
                        }`}
                      >
                        {city}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* STEP: Interests */}
          {stepType === "interests" && (
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
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[11px] text-slate-400 font-bold">Enter로 추가</span>
              </div>
              {formData.interests && (
                <div className="flex flex-wrap gap-1.5 px-1">
                  {formData.interests.split(',').filter(i => i.trim()).map((tag, i) => (
                    <span key={i} className="px-2.5 py-1 bg-indigo-100 text-indigo-700 text-[11px] font-black rounded-full flex items-center gap-1">
                      {tag}
                      <button onClick={() => toggleInterest(tag)} className="hover:text-rose-500 transition-colors">×</button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* STEP: Company Size */}
          {stepType === "company_size" && (
            <div className="space-y-6 animate-in slide-in-from-right-8 duration-500">
              <div className="space-y-2">
                <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest ml-1">연간 매출 규모</label>
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
                <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest ml-1">직원 수</label>
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

          {/* STEP: Email + Notification */}
          {stepType === "account" && (
            <div className="space-y-5 animate-in slide-in-from-right-8 duration-500">
              {initialEmail ? (
                <div className="bg-slate-50/60 rounded-2xl p-4 border border-slate-100/80">
                  <label className="text-[11px] font-black text-slate-500 uppercase tracking-widest ml-0.5 mb-2.5 block">
                    로그인 계정
                  </label>
                  <div className="w-full p-4 rounded-2xl bg-white/50 border border-white/80 text-sm font-bold text-slate-700">
                    {initialEmail}
                  </div>
                </div>
              ) : (
                <EmailInput
                  value={formData.email}
                  onChange={(email) => setFormData({ ...formData, email })}
                />
              )}
              <div className="bg-slate-50/60 rounded-2xl p-4 border border-slate-100/80 space-y-3">
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
                <p className="text-[11px] text-slate-400 font-medium">
                  매일 오전 10시, AI가 분석한 맞춤 리포트를 보내드립니다
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="mt-6 sm:mt-10 space-y-4">
          <div className="flex gap-3">
            {step > 0 && stepType !== "user_type" && (
              <button
                onClick={() => setStep(step - 1)}
                className="flex-1 py-5 bg-slate-100 text-slate-500 rounded-2xl font-black text-sm hover:bg-slate-200 transition-all active:scale-95"
              >
                ← 이전
              </button>
            )}
            {stepType !== "user_type" && (
              <button
                onClick={handleNext}
                disabled={loading}
                className={`${step > 0 ? 'flex-[2]' : 'w-full'} py-5 bg-slate-900 text-white rounded-2xl font-black text-base shadow-xl shadow-indigo-100 hover:bg-indigo-600 transition-all active:scale-95 flex items-center justify-center group`}
              >
                {loading ? "분석 중..." : stepType === "account" ? "무료 매칭 시작하기" : "다음 단계로"}
                {!loading && <span className="ml-2 group-hover:translate-x-1 transition-transform">→</span>}
              </button>
            )}
          </div>
          
          {onLogout && (
            <button 
              onClick={onLogout}
              className="w-full py-2 text-slate-400 hover:text-rose-500 text-[11px] font-black uppercase tracking-widest transition-all opacity-60"
            >
              처음으로 돌아가기
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
