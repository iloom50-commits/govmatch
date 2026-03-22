"use client";

import { useState, useEffect, useRef } from "react";
import { useToast } from "@/components/ui/Toast";

interface ProfileCardProps {
  data: any;
  onConfirm: (data: any) => void;
  onLogout?: () => void;
  onClose?: () => void;
}

export default function ProfileCard({ data, onConfirm, onLogout, onClose }: ProfileCardProps) {
  const { toast } = useToast();
  const [step, setStep] = useState(1);
  const [isRecommending, setIsRecommending] = useState(false);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [businessContent, setBusinessContent] = useState("");
  
  // Separate reference images for Step 1 (Registration) and Step 4 (Financials)
  const [regImage, setRegImage] = useState<string | null>(null);
  const [finImage, setFinImage] = useState<string | null>(null);
  const [activeRef, setActiveRef] = useState<"REG" | "FIN" | null>(null);
  const datePickerRef = useRef<HTMLInputElement>(null);

  const [formData, setFormData] = useState({
    business_number: data?.business_number || "",
    company_name: data?.company_name || "",
    address_city: data?.address_city || "전국",
    establishment_date: data?.establishment_date || "",
    industry_code: data?.industry_code || "",
    revenue: "1억 미만",
    employees: "5인 미만",
  });

  // Instant DB Search as the user types (with debounce)
  useEffect(() => {
    if (businessContent.length < 2) {
      if (businessContent.length === 0) setCandidates([]);
      return;
    }

    const timer = setTimeout(() => {
      handleRecommendIndustry(true); // silent search
    }, 600);

    return () => clearTimeout(timer);
  }, [businessContent]);

  const revenueOptions = ["1억 미만", "1억~5억", "5억~10억", "10억~50억", "50억 이상"];
  const employeeOptions = ["5인 미만", "5인~10인", "10인~30인", "30인~50인", "50인 이상"];

  const handleRecommendIndustry = async (silent = false) => {
    if (!businessContent && !formData.company_name) return;
    
    if (!silent) setIsRecommending(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/industry-recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          company_name: formData.company_name,
          business_content: businessContent 
        })
      });
      const result = await res.json();
      if (result.status === "SUCCESS" && result.data.candidates) {
        setCandidates(result.data.candidates);
      }
    } catch (err) {
      console.error("Industry recommendation failed", err);
    } finally {
      if (!silent) setIsRecommending(false);
    }
  };

  const selectCandidate = (cand: any) => {
    setFormData({ ...formData, industry_code: cand.code });
  };

  const handleDateChange = (val: string) => {
    let clean = val.replace(/[^0-9]/g, "");
    if (clean.length > 8) clean = clean.slice(0, 8);
    
    let formatted = clean;
    if (clean.length >= 5) {
      formatted = `${clean.slice(0, 4)}-${clean.slice(4, 6)}`;
      if (clean.length >= 7) {
        formatted += `-${clean.slice(6, 8)}`;
      }
    }
    setFormData({ ...formData, establishment_date: formatted });
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>, type: "REG" | "FIN") => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        if (type === "REG") {
          setRegImage(reader.result as string);
          setActiveRef("REG");
        } else {
          setFinImage(reader.result as string);
          setActiveRef("FIN");
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const currentRefImage = activeRef === "REG" ? regImage : finImage;

  return (
    <div className={`bg-white/70 backdrop-blur-2xl border border-white/50 rounded-[3rem] shadow-[0_32px_64px_rgba(0,0,0,0.06)] animate-in zoom-in-95 duration-700 relative flex flex-col md:flex-row overflow-hidden ${currentRefImage ? 'max-w-6xl' : 'max-w-2xl'}`}>
      
      {/* Reference Image Sidebar */}
      {currentRefImage && (
        <div className="md:w-1/2 bg-slate-100/50 p-6 border-r border-slate-200 flex flex-col border-white/40">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-[11px] font-black text-slate-400 uppercase tracking-widest">
              {activeRef === "REG" ? "Business Registration Reference" : "Financial Statement Reference"}
            </h3>
            <div className="flex gap-2">
              {regImage && activeRef !== "REG" && (
                <button onClick={() => setActiveRef("REG")} className="text-[11px] font-bold text-indigo-600 hover:underline">등록증 보기</button>
              )}
              {finImage && activeRef !== "FIN" && (
                <button onClick={() => setActiveRef("FIN")} className="text-[11px] font-bold text-indigo-600 hover:underline">재무제표 보기</button>
              )}
              <button onClick={() => setActiveRef(null)} className="text-slate-400 hover:text-rose-500 transition-colors ml-2">
                <span className="text-xl">×</span>
              </button>
            </div>
          </div>
          <div className="flex-1 bg-white rounded-2xl overflow-hidden shadow-inner flex items-center justify-center p-4">
            <img src={currentRefImage} alt="Reference" className="max-w-full max-h-full object-contain" />
          </div>
          <p className="mt-4 text-[11px] text-slate-400 text-center font-medium leading-relaxed">
            이미지를 참고하여 정보를 입력해 주세요.<br/>입력하신 정보는 AI 추출 없이 그대로 활용됩니다.
          </p>
        </div>
      )}

      <div className="flex-1 p-10 flex flex-col">
        <div className="flex justify-between items-start mb-10">
          <div className="space-y-1">
            <h2 className="text-2xl font-black text-slate-900 tracking-tight">
              {step === 1 && "신원 확인 및 등록증"}
              {step === 2 && "기본 기업 정보"}
              {step === 3 && "업종 및 사업 분류"}
              {step === 4 && "재무 및 매출 규모"}
              {step === 5 && "인력 규모 및 저장"}
            </h2>
            <p className="text-slate-400 text-xs font-bold uppercase tracking-widest">Step {step} of 5</p>
          </div>
          
          <div className="flex items-center gap-6">
            <div className="flex gap-1.5">
              {[1, 2, 3, 4, 5].map((s) => (
                <div key={s} className={`h-1.5 w-6 rounded-full transition-all duration-500 ${s <= step ? 'bg-indigo-600 w-12' : 'bg-slate-100'}`} />
              ))}
            </div>

            {onClose && (
              <button 
                onClick={onClose}
                className="p-2 text-slate-400 hover:text-slate-950 transition-colors bg-slate-50 rounded-xl border border-slate-100"
                aria-label="창 닫기"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-x"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
              </button>
            )}
          </div>
        </div>

        <div className="flex-1 min-h-[350px]">
          {/* STEP 1: Identification & Registration Upload */}
          {step === 1 && (
            <div className="space-y-8 animate-in slide-in-from-right-8 duration-500">
              <div className="space-y-2">
                <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest pl-1">입력된 사업자 번호</label>
                <div className="bg-slate-50/50 p-8 rounded-3xl border border-slate-100 text-center">
                  <p className="text-3xl font-black text-indigo-900 tracking-tighter">{formData.business_number}</p>
                  <p className="text-[11px] text-slate-400 font-bold mt-2 font-mono">신규 기업 등록을 시작합니다</p>
                </div>
              </div>

              {!regImage ? (
                <div className="mt-8 p-10 bg-indigo-50/50 border-2 border-dashed border-indigo-200 rounded-[2.5rem] flex flex-col items-center justify-center text-center group hover:border-indigo-400 transition-all cursor-pointer relative">
                  <input 
                    type="file" 
                    className="absolute inset-0 opacity-0 cursor-pointer" 
                    onChange={(e) => handleFileUpload(e, "REG")}
                    accept="image/*,application/pdf"
                  />
                  <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center text-2xl shadow-sm mb-4 group-hover:scale-110 transition-transform">📄</div>
                  <p className="text-sm font-black text-indigo-600 mb-1">사업자등록증 업로드 (선택)</p>
                  <p className="text-[11px] text-slate-400 font-medium px-10">서류를 보며 정확한 기업 정보를 입력하고 싶으신 경우 업로드해 주세요.</p>
                </div>
              ) : (
                <div className="flex items-center gap-4 p-6 bg-emerald-50 border border-emerald-100 rounded-3xl">
                  <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center text-lg">✅</div>
                  <div className="flex-1">
                    <p className="text-xs font-black text-emerald-900">등록증 업로드 완료</p>
                    <p className="text-[11px] text-emerald-600">왼쪽 화면을 참고하여 정보를 입력할 수 있습니다.</p>
                  </div>
                  <button onClick={() => {setRegImage(null); if(activeRef==="REG") setActiveRef(null);}} className="text-rose-500 text-xs font-bold px-3 py-1 bg-white rounded-xl shadow-sm">교체</button>
                </div>
              )}
            </div>
          )}

          {/* STEP 2: Basic Company Info */}
          {step === 2 && (
            <div className="space-y-6 animate-in slide-in-from-right-8 duration-500">
                <div className="space-y-2">
                  <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest pl-1">상호명</p>
                  <input 
                    type="text" 
                    className="w-full p-5 border border-slate-200 rounded-2xl bg-slate-50/50 focus:ring-4 focus:ring-indigo-100 focus:bg-white transition-all text-lg font-black outline-none"
                    value={formData.company_name}
                    onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                    placeholder="상호명을 입력하세요"
                  />
                </div>

                <div className="space-y-2">
                  <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest pl-1">소재지 (매칭 필수 정보)</p>
                  <div className="grid grid-cols-4 gap-1.5 md:grid-cols-6 max-h-[140px] overflow-y-auto p-1 scrollbar-hide">
                    {["전국", "서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"].map((city) => (
                      <button
                        key={city}
                        onClick={() => setFormData({ ...formData, address_city: city })}
                        className={`py-2 rounded-lg text-[11px] font-black border-2 transition-all ${
                          formData.address_city === city 
                            ? "bg-indigo-600 border-indigo-600 text-white shadow-md"
                            : "bg-white border-slate-100 text-slate-500 hover:border-indigo-100"
                        }`}
                      >
                        {city}
                      </button>
                    ))}
                  </div>
                </div>
              
                <div className="space-y-2">
                  <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest pl-1">설립일 (숫자 8자리 혹은 달력 선택)</p>
                  <div className="relative group">
                    <input 
                      type="text"
                      placeholder="YYYY-MM-DD"
                      className="w-full p-5 border border-slate-200 rounded-2xl bg-white focus:ring-4 focus:ring-indigo-100 transition-all text-lg font-black outline-none placeholder:text-slate-200"
                      value={formData.establishment_date}
                      onChange={(e) => handleDateChange(e.target.value)}
                    />
                    <button 
                      type="button"
                      onClick={() => datePickerRef.current?.showPicker ? datePickerRef.current.showPicker() : datePickerRef.current?.click()}
                      className="absolute right-5 top-1/2 -translate-y-1/2 text-xl hover:scale-110 transition-transform cursor-pointer"
                    >
                      📅
                    </button>
                    <input 
                      type="date"
                      ref={datePickerRef}
                      className="absolute bottom-0 left-0 w-0 h-0 opacity-0 pointer-events-none"
                      onChange={(e) => handleDateChange(e.target.value)}
                    />
                  </div>
                </div>
            </div>
          )}

          {/* STEP 3: Industry Selection */}
          {step === 3 && (
            <div className="space-y-6 animate-in slide-in-from-right-8 duration-500">
              <div className="flex justify-between items-end px-1">
                <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest">사업내용 키워드 검색</label>
                <button 
                  onClick={() => handleRecommendIndustry(false)}
                  disabled={isRecommending}
                  className="text-indigo-600 text-xs font-black flex items-center gap-1 hover:text-indigo-800 transition-colors"
                >
                  {isRecommending ? '⏳ 분석 중...' : '✨ 상세 AI 업종 추천'}
                </button>
              </div>
              
              <div className="space-y-4">
                <textarea 
                  placeholder="예: 화장품 온라인 쇼핑몰 및 SNS 광고 대행"
                  className="w-full p-6 border border-slate-200 rounded-3xl bg-slate-50/50 focus:ring-4 focus:ring-indigo-100 focus:bg-white transition-all text-sm font-medium outline-none min-h-[100px]"
                  value={businessContent}
                  onChange={(e) => setBusinessContent(e.target.value)}
                />

                <input 
                  type="text"
                  placeholder="업종 코드 직접 입력 (5자리)"
                  maxLength={5}
                  className="w-full p-4 border border-slate-200 rounded-2xl bg-white focus:ring-4 focus:ring-indigo-100 transition-all text-xl font-black outline-none text-center tracking-widest"
                  value={formData.industry_code}
                  onChange={(e) => setFormData({ ...formData, industry_code: e.target.value.replace(/[^0-9]/g, "") })}
                />

                {candidates.length > 0 && (
                  <div className="space-y-3 mt-4 overflow-y-auto max-h-[180px] pr-2">
                    <span className="text-[11px] font-black text-indigo-600 uppercase tracking-widest px-1">DB 검색 결과 (하나를 선택하세요)</span>
                    {candidates.map((cand, idx) => (
                      <button
                        key={idx}
                        onClick={() => selectCandidate(cand)}
                        className={`w-full p-5 rounded-2xl text-left border-2 transition-all block mb-3 ${
                          formData.industry_code === cand.code
                            ? "bg-indigo-600 border-indigo-600 text-white shadow-lg scale-[1.02]"
                            : "bg-white border-slate-100 text-slate-900 hover:border-indigo-200"
                        }`}
                      >
                        <div className="flex justify-between items-center mb-1">
                          <span className={`text-[11px] font-black uppercase tracking-widest ${formData.industry_code === cand.code ? 'text-indigo-200' : 'text-slate-400'}`}>
                            KSIC {cand.code}
                          </span>
                        </div>
                        <p className="text-sm font-black mb-1">{cand.name}</p>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* STEP 4: Revenue & Financials */}
          {step === 4 && (
            <div className="space-y-8 animate-in slide-in-from-right-8 duration-500">
              <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest pl-1">최근 1년 매출 규모</label>
              
              <div className="grid gap-2">
                {revenueOptions.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => setFormData({ ...formData, revenue: opt })}
                    className={`p-5 rounded-[2rem] text-left border-2 transition-all duration-300 flex justify-between items-center ${formData.revenue === opt ? 'border-indigo-600 bg-indigo-50/50 scale-[1.02]' : 'border-slate-100 hover:border-indigo-200 bg-slate-50/30'}`}
                  >
                    <span className={`text-sm font-black ${formData.revenue === opt ? 'text-indigo-900' : 'text-slate-600'}`}>{opt}</span>
                    {formData.revenue === opt && <div className="w-4 h-4 bg-indigo-600 rounded-full flex items-center justify-center"><span className="text-white text-[11px]">✓</span></div>}
                  </button>
                ))}
              </div>

              {!finImage ? (
                <div className="p-6 bg-slate-50 border-2 border-dashed border-slate-200 rounded-3xl flex flex-col items-center justify-center text-center group hover:border-indigo-400 transition-all cursor-pointer relative">
                  <input 
                    type="file" 
                    className="absolute inset-0 opacity-0 cursor-pointer" 
                    onChange={(e) => handleFileUpload(e, "FIN")}
                    accept="image/*,application/pdf"
                  />
                  <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center text-lg shadow-sm mb-2">📊</div>
                  <p className="text-[11px] font-black text-indigo-600 mb-1">재무제표 또는 부가세증명 업로드 (선택)</p>
                  <p className="text-[11px] text-slate-400 font-medium">서류를 보며 매출액을 정확히 선택할 수 있습니다.</p>
                </div>
              ) : (
                <div className="flex items-center gap-4 p-4 bg-indigo-50 border border-indigo-100 rounded-3xl">
                  <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center text-md">📑</div>
                  <div className="flex-1">
                    <p className="text-[11px] font-black text-indigo-900">재무제표 참조 활성화</p>
                  </div>
                  <button onClick={() => {setFinImage(null); if(activeRef==="FIN") setActiveRef(null);}} className="text-rose-500 text-[11px] font-black px-3 py-1 bg-white rounded-xl shadow-sm">교체</button>
                </div>
              )}
            </div>
          )}

          {/* STEP 5: Workforce & Final Confirmation */}
          {step === 5 && (
            <div className="space-y-8 animate-in slide-in-from-right-8 duration-500">
              <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest pl-1">상시 근로자 수</label>
              <div className="grid gap-3">
                {employeeOptions.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => setFormData({ ...formData, employees: opt })}
                    className={`p-6 rounded-[2.5rem] text-left border-2 transition-all duration-300 flex justify-between items-center ${formData.employees === opt ? 'border-indigo-600 bg-indigo-50/50 scale-[1.02]' : 'border-slate-100 hover:border-indigo-200 bg-slate-50/30'}`}
                  >
                    <span className={`text-sm font-black ${formData.employees === opt ? 'text-indigo-900' : 'text-slate-600'}`}>{opt}</span>
                    {formData.employees === opt && <div className="w-5 h-5 bg-indigo-600 rounded-full flex items-center justify-center"><span className="text-white text-[11px]">✓</span></div>}
                  </button>
                ))}
              </div>
              <p className="text-center text-[11px] text-slate-400 font-medium leading-relaxed px-10">
                마지막 단계입니다. 정보를 저장하면<br/>귀사에게 꼭 맞는 지원사업을 실시간 매칭합니다.
              </p>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-4 mt-12">
          <div className="flex gap-4">
            {step > 1 && (
              <button 
                onClick={() => {
                   const prevStep = step - 1;
                   setStep(prevStep);
                   // Show relevant doc if available
                   if (prevStep === 1 && regImage) setActiveRef("REG");
                   if (prevStep === 4 && finImage) setActiveRef("FIN");
                }}
                className="flex-1 py-6 bg-slate-100 text-slate-500 rounded-[2rem] font-black text-sm hover:bg-slate-200 transition-all"
              >
                이전으로
              </button>
            )}
            <button 
              onClick={() => {
                if (step === 2 && (!formData.company_name || !formData.establishment_date)) {
                  toast("상호명과 설립일을 모두 입력해 주세요.", "error");
                  return;
                }
                if (step === 3 && !formData.industry_code) {
                  toast("정확한 매칭을 위해 업종 코드를 입력해 주세요.", "error");
                  return;
                }
                if (step < 5) {
                   const nextStep = step + 1;
                   setStep(nextStep);
                   // Auto-switch reference if doc exists for that step
                   if (nextStep === 4 && finImage) setActiveRef("FIN");
                } else {
                  onConfirm(formData);
                }
              }}
              className="flex-[2] py-6 bg-slate-900 text-white rounded-[2rem] font-black text-sm hover:bg-indigo-600 shadow-xl shadow-slate-200 transition-all active:scale-95"
            >
              {step === 5 ? '정보 저장 및 결과 확인' : '다음 단계로'}
            </button>
          </div>
          
          {onLogout && step === 1 && (
            <button 
              onClick={onLogout}
              className="w-full py-4 text-slate-400 hover:text-rose-500 text-[11px] font-black uppercase tracking-widest transition-all mt-2"
            >
              계정 로그아웃
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
