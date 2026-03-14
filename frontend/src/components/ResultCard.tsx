"use client";

import { useToast } from "@/components/ui/Toast";

interface Result {
  announcement_id: number;
  title: string;
  support_amount: string;
  match_score?: number;
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
  "innobiz-api": "이노비즈",
  "venture-api": "벤처확인",
  "mainbiz-api": "메인비즈",
  "admin-manual": "수동등록",
  "sbc": "중진공",
  "sbc-scraper": "중진공",
};

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

interface CardProps {
  res: Result;
  selected?: boolean;
  onToggle?: () => void;
}

export default function ResultCard({ res, selected, onToggle }: CardProps) {
  const { toast } = useToast();
  const dDay = getDDayInfo(res.deadline_date);
  const categoryKr = CATEGORY_KR[(res.category || "").trim()] || res.category || "";
  const sourceKr = SOURCE_KR[(res.origin_source || "").trim()] || res.origin_source || "";

  return (
    <div className={`group relative glass-card p-5 md:p-6 rounded-2xl transition-all duration-300 hover:shadow-[0_16px_32px_-8px_rgba(79,70,229,0.12)] flex flex-col h-full overflow-hidden ${selected ? "ring-2 ring-indigo-500 ring-offset-2" : ""}`}>
      <div className="absolute -top-16 -right-16 w-40 h-40 bg-indigo-500/5 blur-[60px] group-hover:bg-indigo-500/10 transition-all duration-1000 pointer-events-none" />

      {onToggle && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onToggle(); }}
          className={`absolute top-3 left-3 z-20 w-5 h-5 rounded-md border-[1.5px] flex items-center justify-center transition-all ${
            selected
              ? "bg-indigo-600 border-indigo-600 text-white shadow-sm"
              : "bg-white/80 border-slate-300 text-transparent hover:border-indigo-400"
          }`}
          aria-label={selected ? "선택 해제" : "선택"}
        >
          <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </button>
      )}

      {dDay.urgency === "critical" && (
        <div className="absolute top-4 right-4 z-10 px-3 py-1 bg-rose-600 text-white text-[9px] font-black rounded-full shadow-lg animate-bounce">
          {dDay.text}
        </div>
      )}

      <div className="flex flex-col gap-3 h-full relative z-[1]">

        {/* Tags */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className={`px-2 py-0.5 text-[8px] font-black rounded-full border ${URGENCY_STYLES[dDay.urgency]}`}>
            {res.deadline_date ? `${res.deadline_date} (${dDay.text})` : "상시모집"}
          </span>
          {res.support_amount && (
            <span className="px-2 py-0.5 bg-indigo-50 text-indigo-700 text-[8px] font-black rounded-full border border-indigo-100">
              {res.support_amount}
            </span>
          )}
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

        {/* Title */}
        <h3 className="font-black text-slate-900 text-base md:text-lg leading-snug tracking-tight group-hover:text-indigo-600 transition-colors">
          {res.title}
        </h3>

        {/* Recommendation & Info */}
        <div className="relative bg-slate-50/80 p-4 rounded-xl flex-1 border border-slate-100/50 group-hover:bg-indigo-50/20 transition-all">
          <p className="text-slate-700 text-xs font-semibold leading-relaxed mb-3">
            {res.recommendation_reason.split('"').map((text, i) => i % 2 === 1 ? <strong key={i} className="text-indigo-950 font-black px-0.5">{text}</strong> : text)}
          </p>
          <div className="flex flex-wrap items-center gap-3 pt-2.5 border-t border-slate-200/50">
            <div className="space-y-0.5 min-w-0">
              <span className="text-[7px] font-black text-slate-400 uppercase tracking-wider flex items-center gap-1">
                <span className="w-1 h-1 bg-indigo-400 rounded-full" /> 지원 대상
              </span>
              <p className="text-slate-900 text-[10px] font-bold leading-tight">
                {(res.region || "전국") + " · "}
                {res.established_years_limit ? `${res.established_years_limit}년 이내` : "업력 무관"}
              </p>
            </div>
            <div className="space-y-0.5 min-w-0">
              <span className="text-[7px] font-black text-slate-400 uppercase tracking-wider flex items-center gap-1">
                <span className="w-1 h-1 bg-emerald-400 rounded-full" /> 요건
              </span>
              <p className="text-slate-900 text-[10px] font-bold leading-tight">
                {res.revenue_limit ? `매출 ${Math.floor(res.revenue_limit / 100000000)}억↑` : "무관"}
                {res.employee_limit ? ` · ${res.employee_limit}인↑` : ""}
              </p>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (typeof window !== "undefined") {
                  window.dispatchEvent(new CustomEvent("open-smartdoc-modal", { detail: { announcement: res } }));
                }
              }}
              className="ml-auto px-3 py-1.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-[9px] font-black rounded-full shadow-md hover:shadow-lg hover:scale-105 transition-all active:scale-95 flex items-center gap-1.5 whitespace-nowrap"
            >
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6.23.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0 1 12 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
              </svg>
              AI 신청서 작성
            </button>
          </div>
        </div>

        {/* CTA */}
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
            onClick={() => toast('상세 페이지 링크가 없습니다.', 'info')}
            className="w-full py-3 bg-slate-300 text-slate-500 rounded-xl font-black text-xs uppercase tracking-wider cursor-not-allowed mt-auto"
          >
            링크 없음
          </button>
        )}
      </div>
    </div>
  );
}
