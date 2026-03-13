"use client";

import { useState, useEffect } from "react";

interface ProfileSettingsProps {
  profile: any;
  onSave: (data: any) => void;
  onClose: () => void;
}

export default function ProfileSettings({ profile, onSave, onClose }: ProfileSettingsProps) {
  const REVENUE_MIGRATE: Record<string, string> = {
    UNDER_1B: "1억 미만", "1B_5B": "1억~5억", "1B_TO_5B": "1억~5억",
    "5B_10B": "5억~10억", "5B_TO_10B": "5억~10억",
    "10B_50B": "10억~50억", OVER_10B: "10억~50억",
    "50B_PLUS": "50억 이상",
  };
  const EMP_MIGRATE: Record<string, string> = {
    UNDER_5: "5인 미만", UNDER_10: "5인 미만",
    "5_10": "5인~10인", "5_TO_10": "5인~10인",
    "10_50": "10인~30인", "10_TO_50": "10인~30인",
    "50_100": "50인 이상", OVER_50: "50인 이상",
  };

  const rawRev = profile.revenue_bracket || profile.revenue || "";
  const rawEmp = profile.employee_count_bracket || profile.employees || "";

  const [formData, setFormData] = useState({
    ...profile,
    revenue: REVENUE_MIGRATE[rawRev] || rawRev || "1억 미만",
    employees: EMP_MIGRATE[rawEmp] || rawEmp || "5인 미만",
    industry_code: profile.industry_code || "",
  });
  const [industryQuery, setIndustryQuery] = useState("");
  const [industryCandidates, setIndustryCandidates] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [industryName, setIndustryName] = useState("");

  useEffect(() => {
    if (formData.industry_code && formData.industry_code.length >= 2) {
      fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/industry-recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company_name: "", business_content: formData.industry_code })
      })
        .then(r => r.json())
        .then(result => {
          if (result.status === "SUCCESS" && result.data.candidates) {
            const match = result.data.candidates.find((c: any) => c.code === formData.industry_code);
            if (match) setIndustryName(match.name);
          }
        })
        .catch(() => {});
    }
  }, []);

  useEffect(() => {
    if (industryQuery.length < 2) return;
    const timer = setTimeout(() => searchIndustry(true), 600);
    return () => clearTimeout(timer);
  }, [industryQuery]);

  const searchIndustry = async (silent = false) => {
    if (!industryQuery) return;
    if (!silent) setIsSearching(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/industry-recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company_name: formData.company_name || "", business_content: industryQuery })
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

  const cities = ["서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"];
  const revenueOptions = [
    { label: "1억 미만", value: "1억 미만" },
    { label: "1억 ~ 5억", value: "1억~5억" },
    { label: "5억 ~ 10억", value: "5억~10억" },
    { label: "10억 ~ 50억", value: "10억~50억" },
    { label: "50억 이상", value: "50억 이상" },
  ];
  const employeeOptions = [
    { label: "5인 미만", value: "5인 미만" },
    { label: "5 ~ 10인", value: "5인~10인" },
    { label: "10 ~ 30인", value: "10인~30인" },
    { label: "30 ~ 50인", value: "30인~50인" },
    { label: "50인 이상", value: "50인 이상" },
  ];

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-md animate-in fade-in duration-300">
      <div className="bg-white w-full max-w-xl rounded-[2rem] sm:rounded-[2.5rem] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-500">
        {/* Header */}
        <div className="p-5 sm:p-8 border-b border-slate-100 flex justify-between items-center">
          <div>
            <h2 className="text-xl font-black text-slate-900 tracking-tight">기업 정보 수정</h2>
            <p className="text-xs text-slate-400 font-bold mt-1 uppercase tracking-widest">Quick Profile Update</p>
          </div>
          <button onClick={onClose} className="p-3 bg-slate-50 rounded-2xl hover:bg-slate-100 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="text-slate-400"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-5 sm:p-8 space-y-6 sm:space-y-8 max-h-[75vh] overflow-y-auto custom-scrollbar">
          
          {/* Location */}
          <div className="space-y-3">
            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest pl-1">소재지</label>
            <div className="flex flex-wrap gap-2">
              {cities.map(city => (
                <button
                  key={city}
                  onClick={() => setFormData({ ...formData, address_city: city })}
                  className={`px-4 py-2 rounded-xl text-xs font-black transition-all border-2 ${formData.address_city === city ? 'bg-indigo-600 border-indigo-600 text-white shadow-lg' : 'bg-slate-50 border-transparent text-slate-500 hover:bg-white hover:border-indigo-100'}`}
                >
                  {city}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Revenue */}
            <div className="space-y-3">
              <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest pl-1">매출액 (연)</label>
              <div className="space-y-2">
                {revenueOptions.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => setFormData({ ...formData, revenue: opt.value })}
                    className={`w-full p-4 rounded-2xl text-left text-xs font-black transition-all border-2 flex justify-between items-center ${formData.revenue === opt.value ? 'bg-indigo-50 border-indigo-600 text-indigo-900 shadow-sm' : 'bg-slate-50 border-transparent text-slate-500'}`}
                  >
                    {opt.label}
                    {formData.revenue === opt.value && <span className="w-2 h-2 bg-indigo-600 rounded-full animate-pulse" />}
                  </button>
                ))}
              </div>
            </div>

            {/* Employees */}
            <div className="space-y-3">
              <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest pl-1">직원 수</label>
              <div className="space-y-2">
                {employeeOptions.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => setFormData({ ...formData, employees: opt.value })}
                    className={`w-full p-4 rounded-2xl text-left text-xs font-black transition-all border-2 flex justify-between items-center ${formData.employees === opt.value ? 'bg-indigo-50 border-indigo-600 text-indigo-900 shadow-sm' : 'bg-slate-50 border-transparent text-slate-500'}`}
                  >
                    {opt.label}
                    {formData.employees === opt.value && <span className="w-2 h-2 bg-indigo-600 rounded-full animate-pulse" />}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Industry / KSIC */}
          <div className="space-y-3">
            <div className="flex justify-between items-end">
              <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest pl-1">업종 (KSIC)</label>
              {formData.industry_code && (
                <span className="text-[10px] font-black text-indigo-600 tracking-widest">
                  KSIC {formData.industry_code}{industryName ? ` · ${industryName}` : ""}
                </span>
              )}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="사업 내용을 입력하여 검색..."
                className="flex-1 p-3 border border-slate-200 rounded-xl bg-white text-xs font-medium outline-none focus:ring-2 focus:ring-indigo-100"
                value={industryQuery}
                onChange={(e) => setIndustryQuery(e.target.value)}
              />
              <input
                type="text"
                placeholder="코드"
                maxLength={5}
                className="w-16 sm:w-20 p-3 border border-slate-200 rounded-xl bg-white text-sm font-black outline-none text-center tracking-widest focus:ring-2 focus:ring-indigo-100"
                value={formData.industry_code}
                onChange={(e) => setFormData({ ...formData, industry_code: e.target.value.replace(/[^0-9]/g, "") })}
              />
            </div>
            {industryCandidates.length > 0 && (
              <div className="space-y-1.5 max-h-[120px] overflow-y-auto">
                {industryCandidates.map((cand, idx) => (
                  <button
                    key={idx}
                    onClick={() => { setFormData({ ...formData, industry_code: cand.code }); setIndustryName(cand.name); setIndustryCandidates([]); setIndustryQuery(""); }}
                    className={`w-full p-3 rounded-xl text-left text-xs font-black transition-all border ${
                      formData.industry_code === cand.code
                        ? "bg-indigo-600 border-indigo-600 text-white"
                        : "bg-white border-slate-100 text-slate-700 hover:border-indigo-200"
                    }`}
                  >
                    <span className={`text-[9px] ${formData.industry_code === cand.code ? 'text-indigo-200' : 'text-slate-400'}`}>KSIC {cand.code}</span>
                    <span className="ml-2">{cand.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

        </div>

        {/* Footer */}
        <div className="p-5 sm:p-8 bg-slate-50/50 border-t border-slate-100">
          <button 
            onClick={() => onSave(formData)}
            className="w-full py-5 bg-slate-950 text-white rounded-2xl font-black text-sm tracking-tight hover:bg-indigo-600 transition-all shadow-xl shadow-indigo-100 active:scale-[0.98]"
          >
            설정 저장하고 결과 업데이트 →
          </button>
        </div>
      </div>
    </div>
  );
}
