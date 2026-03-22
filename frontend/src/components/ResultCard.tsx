"use client";

import { useToast } from "@/components/ui/Toast";

interface EligibilityLogic {
  business_type?: string[];
  target_keywords?: string[];
  max_founding_years?: number;
  max_revenue?: number;
  max_employee_count?: number;
  region_restriction?: string;
  target_industries?: string[];
  [key: string]: unknown;
}

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
  eligibility_logic?: EligibilityLogic;
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
  planStatus?: { plan: string; ai_used?: number; ai_limit?: number; consult_limit?: number } | null;
  onUpgrade?: () => void;
  onLoginRequired?: () => void;
}

export default function ResultCard({ res, selected, onToggle, planStatus, onUpgrade, onLoginRequired }: CardProps) {
  const isPublic = !!onLoginRequired;
  const isExpired = !isPublic && planStatus?.plan === "expired";
  const isConsultBlocked = !isPublic && planStatus?.consult_limit === 0;  // FREE 플랜: 공고별 상담/신청서 차단
  const { toast } = useToast();
  const dDay = getDDayInfo(res.deadline_date);
  const categoryKr = CATEGORY_KR[(res.category || "").trim()] || res.category || "";
  const sourceKr = SOURCE_KR[(res.origin_source || "").trim()] || res.origin_source || "";
  const elig = res.eligibility_logic || {};
  const bizTypes = (elig.business_type || []).slice(0, 3);
  const targetText = bizTypes.length > 0
    ? bizTypes.join(" · ")
    : (res.region && res.region !== "All" && res.region !== "전국" ? res.region : "전국");

  return (
    <div className={`group relative glass-card p-4 md:p-5 rounded-xl transition-all duration-300 hover:shadow-[0_16px_32px_-8px_rgba(79,70,229,0.12)] flex flex-col h-full overflow-hidden ${selected ? "ring-2 ring-indigo-500 ring-offset-2" : ""}`}>
      <div className="absolute -top-16 -right-16 w-40 h-40 bg-indigo-500/5 blur-[60px] group-hover:bg-indigo-500/10 transition-all duration-1000 pointer-events-none" />

      {/* Deadline badge — top-right */}
      <div className={`absolute top-3 right-3 z-10 px-2.5 py-1.5 rounded-lg border text-center ${URGENCY_STYLES[dDay.urgency]} ${dDay.urgency === "critical" ? "animate-pulse shadow-lg" : "shadow-sm"}`}>
        <span className="block text-[11px] font-bold leading-tight">
          {dDay.text}
        </span>
        {res.deadline_date && (
          <span className="block text-[11px] font-medium leading-tight mt-0.5 opacity-70">
            ~{res.deadline_date.slice(5)}
          </span>
        )}
      </div>

      <div className="flex flex-col gap-4 h-full relative z-[1]">

        {/* Tags */}
        <div className="flex items-center gap-1.5 flex-wrap pr-[72px]">
          {onToggle && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onToggle(); }}
              className={`w-4 h-4 rounded border-[1.5px] flex items-center justify-center transition-all shrink-0 ${
                selected
                  ? "bg-indigo-600 border-indigo-600 text-white shadow-sm"
                  : "bg-white/80 border-slate-300 text-transparent hover:border-indigo-400"
              }`}
              aria-label={selected ? "선택 해제" : "선택"}
            >
              <svg className="w-2 h-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={4}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </button>
          )}
          {res.support_amount && (
            <span className="px-2 py-0.5 bg-indigo-50 text-indigo-700 text-[11px] font-semibold rounded-full border border-indigo-100">
              {res.support_amount}
            </span>
          )}
          {res.department && (
            <span className="px-2 py-0.5 bg-blue-50 text-blue-600 text-[11px] font-bold rounded-full border border-blue-100">
              {res.department}
            </span>
          )}
          {categoryKr && (
            <span className="px-2 py-0.5 bg-violet-50 text-violet-600 text-[11px] font-bold rounded-full border border-violet-100">
              {categoryKr}
            </span>
          )}
          {sourceKr && (
            <span className="px-2 py-0.5 bg-slate-50 text-slate-500 text-[11px] font-bold rounded-full border border-slate-200">
              {sourceKr}
            </span>
          )}
        </div>

        {/* Title */}
        <h3 className="font-bold text-slate-900 text-sm md:text-base leading-snug tracking-tight group-hover:text-indigo-600 transition-colors line-clamp-2 min-h-[2lh]" title={res.title}>
          {res.title}
        </h3>

        {/* Info & Buttons */}
        <div className="relative bg-slate-50/80 p-4 rounded-lg flex-1 border border-slate-100/50 group-hover:bg-indigo-50/20 transition-all">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mb-5">
            <p className="text-[11px] font-bold flex items-center gap-1 whitespace-nowrap">
              <span className="w-1 h-1 bg-indigo-400 rounded-full shrink-0" />
              <span className="text-slate-400">대상 :</span>
              <span className="text-slate-900">{targetText}{res.established_years_limit ? ` · ${res.established_years_limit}년 이내` : ""}</span>
            </p>
            {(res.revenue_limit || res.employee_limit) && (
              <p className="text-[11px] font-bold flex items-center gap-1 whitespace-nowrap">
                <span className="w-1 h-1 bg-emerald-400 rounded-full shrink-0" />
                <span className="text-slate-400">요건 :</span>
                <span className="text-slate-900">{res.revenue_limit ? `매출 ${Math.floor(res.revenue_limit / 100000000)}억↑` : ""}{res.employee_limit ? `${res.revenue_limit ? " · " : ""}${res.employee_limit}인↑` : ""}</span>
              </p>
            )}
          </div>
          {/* CTA buttons */}
          <div className="flex flex-col gap-2 mt-2">
            {/* 상세 공고 이동 */}
            {isPublic ? (
              <button
                onClick={() => onLoginRequired?.()}
                className="w-full py-2 bg-slate-950 text-white rounded-lg font-bold text-[11px] uppercase tracking-wider hover:bg-indigo-600 transition-all active:scale-[0.98] shadow-md text-center"
              >
                상세 공고 이동 →
              </button>
            ) : isExpired ? (
              <button
                onClick={() => onUpgrade?.()}
                className="w-full py-2 bg-slate-300 text-slate-500 rounded-lg font-bold text-[11px] uppercase tracking-wider flex items-center justify-center gap-1 hover:bg-slate-400 hover:text-white transition-all"
              >
                🔒 플랜 만료 — 업그레이드 후 이용
              </button>
            ) : res.origin_url || res.url ? (
              <a
                href={res.origin_url || res.url}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full py-2 bg-slate-950 text-white rounded-lg font-bold text-[11px] uppercase tracking-wider hover:bg-indigo-600 transition-all active:scale-[0.98] shadow-md text-center block"
              >
                상세 공고 이동 →
              </a>
            ) : (
              <button
                onClick={() => toast('상세 페이지 링크가 없습니다.', 'info')}
                className="w-full py-2 bg-slate-300 text-slate-500 rounded-lg font-bold text-[11px] uppercase tracking-wider cursor-not-allowed"
              >
                링크 없음
              </button>
            )}
            {/* AI 버튼 2개 */}
            <div className="flex items-center gap-2">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (isPublic) { onLoginRequired?.(); return; }
                  if (isExpired) { onUpgrade?.(); return; }
                  if (isConsultBlocked) { toast("공고별 지원대상 상담은 BASIC 플랜부터 이용할 수 있습니다.", "error"); onUpgrade?.(); return; }
                  if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("open-ai-consult", { detail: { announcement: res } }));
                  }
                }}
                className={`flex-1 py-1.5 rounded-lg text-[11px] font-bold transition-all flex items-center justify-center gap-1 border
                  bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100 hover:shadow-md active:scale-[0.98]`}
              >
                <span className="animate-sparkle">{isPublic ? "🔒" : isExpired ? "🔒" : isConsultBlocked ? "🔒" : "💬"}</span> 지원대상 여부 상담
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (isPublic) { onLoginRequired?.(); return; }
                  if (isExpired) { onUpgrade?.(); return; }
                  if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("open-smartdoc-modal", { detail: { announcement: res } }));
                  }
                }}
                className={`flex-1 py-1.5 rounded-lg text-[11px] font-bold transition-all flex items-center justify-center gap-1 border
                  bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100 hover:shadow-md active:scale-[0.98]`}
              >
                <span className="animate-sparkle">{isPublic ? "🔒" : isExpired ? "🔒" : "✨"}</span> AI 신청서 작성
              </button>
            </div>
            {/* 공유 버튼 */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                const url = res.origin_url || res.url || window.location.origin;
                const text = `[지원금톡톡] ${res.title}`;
                if (navigator.share) {
                  navigator.share({ title: res.title, text, url });
                } else {
                  navigator.clipboard.writeText(`${text}\n${url}`).then(() => toast("공고 링크가 복사되었습니다!", "success"));
                }
              }}
              className="w-full py-1.5 rounded-lg text-[11px] font-bold transition-all flex items-center justify-center gap-1 border bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100 active:scale-[0.98]"
            >
              <span>📤</span> 이 공고 공유하기
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
