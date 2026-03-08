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
  category?: string;
  department?: string;
  origin_source?: string;
}

const CATEGORY_KR: Record<string, string> = {
  "Entrepreneurship": "창업지원",
  "Small Business/Startup": "중소·창업",
  "R&D": "R&D",
  "R&D/Digital": "R&D·디지털",
  "Loan/Investment": "자금·융자",
  "Marketing": "판로·마케팅",
  "General Business Support": "경영지원",
  "SME Support": "중소기업",
  "Food Industry": "식품산업",
  "General": "일반",
};

const SOURCE_KR: Record<string, string> = {
  "kised-api": "K-Startup",
  "mss-api": "중기부",
  "bizinfo-portal-api": "기업마당",
  "bizinfo-api": "기업마당",
  "msit-rnd-api": "과기부 R&D",
  "msit-api": "과기부",
  "smes24-api": "중소벤처24",
  "foodpolis-api": "식품클러스터",
};

function getGrade(score: number): { label: string; color: string; icon: string } {
  if (score >= 90) return { label: "최우선", color: "bg-indigo-600 text-white", icon: "👑" };
  if (score >= 75) return { label: "우수", color: "bg-indigo-100 text-indigo-700", icon: "💎" };
  if (score >= 60) return { label: "적합", color: "bg-emerald-100 text-emerald-700", icon: "✅" };
  return { label: "관심", color: "bg-slate-100 text-slate-600", icon: "📌" };
}

function getDDayInfo(dateStr?: string): { text: string; days: number | null; urgency: "expired" | "critical" | "warning" | "normal" | "open" } {
  if (!dateStr) return { text: "상시모집", days: null, urgency: "open" };
  const target = new Date(dateStr);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diffDays = Math.ceil((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return { text: "마감", days: diffDays, urgency: "expired" };
  if (diffDays === 0) return { text: "D-Day", days: 0, urgency: "critical" };
  if (diffDays <= 3) return { text: `D-${diffDays}`, days: diffDays, urgency: "critical" };
  if (diffDays <= 7) return { text: `D-${diffDays}`, days: diffDays, urgency: "warning" };
  return { text: `D-${diffDays}`, days: diffDays, urgency: "normal" };
}

const URGENCY_STYLES: Record<string, string> = {
  expired: "bg-slate-200 text-slate-500 border-slate-300",
  critical: "bg-rose-100 text-rose-700 border-rose-200 animate-pulse",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  normal: "bg-emerald-50 text-emerald-600 border-emerald-100",
  open: "bg-sky-50 text-sky-600 border-sky-100",
};

export default function ResultCard({ res, isCompact = false }: { res: Result, isCompact?: boolean }) {
  const dDay = getDDayInfo(res.deadline_date);
  const grade = getGrade(res.match_score);
  const categoryKr = CATEGORY_KR[(res.category || "").trim()] || res.category || "";
  const sourceKr = SOURCE_KR[(res.origin_source || "").trim()] || res.origin_source || "";

  return (
    <div className={`group relative glass-card p-5 md:p-6 rounded-[1.5rem] transition-all duration-300 hover:shadow-[0_20px_40px_-10px_rgba(79,70,229,0.12)] flex flex-col h-full overflow-hidden ${isCompact ? "min-h-[300px]" : "min-h-[400px]"}`}>
      
      <div className="absolute -top-16 -right-16 w-40 h-40 bg-indigo-500/5 blur-[60px] group-hover:bg-indigo-500/10 transition-all duration-1000 pointer-events-none" />

      {/* Urgent ribbon */}
      {dDay.urgency === "critical" && (
        <div className="absolute top-4 right-4 z-10 px-3 py-1 bg-rose-600 text-white text-[9px] font-black rounded-full shadow-lg animate-bounce">
          {dDay.text}
        </div>
      )}
      
      <div className={`flex flex-col gap-5 h-full ${!isCompact ? "lg:flex-row lg:items-start" : ""}`}>
        
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
            <div className="flex flex-col items-center gap-1 py-2 px-1 bg-slate-50/50 rounded-xl border border-slate-100 group-hover:bg-white transition-all">
              <span className="text-[7px] font-bold text-slate-400 uppercase tracking-wider">지원규모</span>
              <p className="text-slate-900 font-extrabold text-[9px] md:text-[10px] truncate max-w-full px-1">💰 {res.support_amount || "별도공고"}</p>
            </div>
            <div className={`flex flex-col items-center gap-1 py-2 px-1 rounded-xl border transition-all ${grade.color}`}>
              <span className="text-[7px] font-bold uppercase tracking-wider opacity-70">추천등급</span>
              <p className="font-extrabold text-[9px] md:text-[10px]">{grade.icon} {grade.label}</p>
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col gap-5">
          <div className="space-y-2.5">
            {/* Tags row */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="px-2 py-0.5 bg-slate-950 text-white text-[8px] font-black rounded-full uppercase tracking-widest">매칭완료</span>
              <span className={`px-2 py-0.5 text-[8px] font-black rounded-full border ${URGENCY_STYLES[dDay.urgency]}`}>
                {res.deadline_date ? `${res.deadline_date} (${dDay.text})` : "상시모집"}
              </span>
              {res.department && (
                <span className="px-2 py-0.5 bg-blue-50 text-blue-600 text-[8px] font-bold rounded-full border border-blue-100">
                  {res.department}
                </span>
              )}
              {categoryKr && (
                <span className="px-2 py-0.5 bg-violet-50 text-violet-600 text-[8px] font-bold rounded-full border border-violet-100">
                  {categoryKr}
                </span>
              )}
              {sourceKr && (
                <span className="px-2 py-0.5 bg-slate-50 text-slate-500 text-[8px] font-bold rounded-full border border-slate-200">
                  {sourceKr}
                </span>
              )}
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
