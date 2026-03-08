"use client";

interface Result {
  announcement_id: number;
  title: string;
  support_amount: string;
  match_score: number;
  recommendation_reason: string;
  deadline_date?: string;
  summary_text?: string;
  region?: string;
  established_years_limit?: number;
  revenue_limit?: number;
  employee_limit?: number;
  origin_url?: string;
  url?: string;
}

export default function ResultCard({ res, isCompact = false }: { res: Result, isCompact?: boolean }) {
  const getDDay = (dateStr?: string) => {
    if (!dateStr) return null;
    const target = new Date(dateStr);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const diffTime = target.getTime() - today.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return "D-Day";
    if (diffDays < 0) return "마감";
    return `D-${diffDays}`;
  };

  const dDay = getDDay(res.deadline_date);

  return (
    <div className={`group relative glass-card p-5 md:p-6 rounded-[1.5rem] transition-all duration-300 hover:shadow-[0_20px_40px_-10px_rgba(79,70,229,0.12)] flex flex-col h-full overflow-hidden ${isCompact ? "min-h-[300px]" : "min-h-[400px]"}`}>
      
      {/* Subtle Glow Effect */}
      <div className="absolute -top-16 -right-16 w-40 h-40 bg-indigo-500/5 blur-[60px] group-hover:bg-indigo-500/10 transition-all duration-1000 pointer-events-none" />
      
      <div className={`flex flex-col gap-5 h-full ${!isCompact ? "lg:flex-row lg:items-start" : ""}`}>
        
        {/* Left/Top: Score & Meta */}
        <div className={`flex flex-col items-center flex-shrink-0 ${!isCompact ? "lg:w-[160px]" : "w-full"} gap-4`}>
          <div className="relative flex items-center justify-center w-24 h-24 md:w-28 md:h-28">
            <svg className="w-full h-full transform -rotate-90">
              <circle cx="50%" cy="50%" r="42%" fill="none" stroke="#f1f5f9" strokeWidth="2.5" />
              <circle 
                cx="50%" cy="50%" r="42%" fill="none" stroke="#4f46e5" strokeWidth="5" 
                className="drop-shadow-[0_0_8px_rgba(79,70,229,0.25)] transition-all duration-1500 ease-out"
                strokeDasharray="264"
                strokeDashoffset={264 - (264 * res.match_score) / 100}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute flex flex-col items-center leading-none">
              <span className="text-2xl md:text-3xl font-black text-slate-900 tracking-tighter">{res.match_score}</span>
              <span className="text-[7px] font-black text-indigo-400 uppercase tracking-widest mt-0.5">적합도</span>
            </div>
          </div>

          <div className="w-full grid grid-cols-2 gap-2">
            {[
              { label: "지원규모", value: res.support_amount || "별도공고", icon: "💰" },
              { label: "추천등급", value: "프리미엄", icon: "💎" }
            ].map((meta, i) => (
              <div key={i} className="flex flex-col items-center gap-1 py-2 px-1 bg-slate-50/50 rounded-xl border border-slate-100 group-hover:bg-white transition-all">
                <span className="text-[7px] font-bold text-slate-400 uppercase tracking-wider">{meta.label}</span>
                <p className="text-slate-900 font-extrabold text-[9px] md:text-[10px] truncate max-w-full px-1">{meta.icon} {meta.value}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Right/Bottom: Main Content */}
        <div className="flex-1 flex flex-col gap-5">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 bg-slate-950 text-white text-[8px] font-black rounded-full uppercase tracking-widest">매칭완료</span>
              <span className={`px-2 py-0.5 text-[8px] font-black rounded-full uppercase tracking-widest border italic ${dDay ? "bg-rose-50 text-rose-600 border-rose-100" : "bg-emerald-50 text-emerald-600 border-emerald-100"}`}>
                {res.deadline_date ? `마감일: ${res.deadline_date} (${dDay})` : "마감일: 상시모집"}
              </span>
              <div className="h-px bg-slate-100 flex-1" />
            </div>
            <h3 className={`font-black text-slate-900 leading-tight tracking-tight group-hover:text-indigo-600 transition-colors ${!isCompact ? "text-xl md:text-2xl" : "text-lg md:text-xl"}`}>
              {res.title}
            </h3>
          </div>

          <div className="relative bg-slate-50/80 p-5 md:p-6 rounded-2xl flex-1 border border-slate-100/50 group-hover:bg-indigo-50/20 transition-all">
            <div className="flex items-center gap-2.5 mb-3">
              <div className="w-6 h-6 bg-white rounded-lg flex items-center justify-center text-xs shadow-sm border border-slate-100">✨</div>
              <span className="text-[8px] font-black text-indigo-600 uppercase tracking-widest">AI 매칭 분석</span>
            </div>
            <p className="text-slate-700 text-xs md:text-sm font-semibold leading-relaxed mb-4">
              {res.recommendation_reason.split('"').map((text, i) => i % 2 === 1 ? <strong key={i} className="text-indigo-950 font-black px-0.5">{text}</strong> : text)}
            </p>

            {/* Structured Eligibility Section */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-3 border-t border-slate-200/50">
              <div className="space-y-0.5">
                <span className="text-[8px] font-black text-slate-400 uppercase tracking-wider flex items-center gap-1">
                   <span className="w-1 h-1 bg-indigo-400 rounded-full" /> 지원 대상
                </span>
                <p className="text-slate-900 text-[10px] font-bold leading-tight">
                  {(res.region || "전국") + " 소재 "}
                  {res.established_years_limit ? `${res.established_years_limit}년 이내` : "업력 무관"}
                </p>
              </div>
              <div className="space-y-0.5">
                <span className="text-[8px] font-black text-slate-400 uppercase tracking-wider flex items-center gap-1">
                   <span className="w-1 h-1 bg-emerald-400 rounded-full" /> 요건
                </span>
                <p className="text-slate-900 text-[10px] font-bold leading-tight">
                  {res.revenue_limit ? `매출 ${Math.floor(res.revenue_limit / 100000000)}억↑` : "무관"}
                  {res.employee_limit ? ` & ${res.employee_limit}인↑` : ""}
                </p>
              </div>
            </div>
          </div>

          {res.origin_url || res.url ? (
            <a 
              href={res.origin_url || res.url}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full py-3 bg-slate-950 text-white rounded-xl font-black text-xs uppercase tracking-wider hover:bg-indigo-600 transition-all active:scale-[0.98] shadow-lg mt-auto text-center block"
            >
              상세 공고 확인 →
            </a>
          ) : (
            <button 
              onClick={() => alert('상세 페이지 링크가 없습니다.')}
              className="w-full py-3 bg-slate-300 text-slate-500 rounded-xl font-black text-xs uppercase tracking-wider cursor-not-allowed mt-auto"
            >
              링크 없음
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
