"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { useToast } from "@/components/ui/Toast";
import { bestExternalUrl } from "@/lib/url";
import { isKosmePolicyLoan } from "@/lib/smartdocGating";

function ShareMenu({ toast, announcementId, announcementTitle }: { toast: (msg: string, type?: "success" | "error" | "info") => void; announcementId?: number; announcementTitle?: string }) {
  const [open, setOpen] = useState(false);
  const [referralCode, setReferralCode] = useState<string | null>(null);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  useEffect(() => {
    const fetchReferralCode = async () => {
      try {
        const token = localStorage.getItem("auth_token");
        if (!token) return;
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setReferralCode(data.user?.referral_code || null);
        }
      } catch (e) {
        console.error("Failed to fetch referral code:", e);
      }
    };
    fetchReferralCode();
  }, []);

  const baseUrl = announcementId ? `https://www.govmatch.kr?aid=${announcementId}` : "https://www.govmatch.kr";
  const url = referralCode ? `${baseUrl}${announcementId ? "&" : "?"}ref=${referralCode}` : baseUrl;

  const shareText = announcementTitle
    ? `이 지원사업 한번 확인해보세요!\n"${announcementTitle.slice(0, 40)}"\nAI가 자격 여부까지 분석해줍니다.`
    : "정부지원금, 아직도 직접 찾고 계세요?\nAI가 내 조건에 맞는 지원금을 자동으로 찾아줍니다.\n친구 추천 시 양쪽 모두 LITE 1개월 무료!";

  // OS 네이티브 공유 시트 → 카카오톡/메시지/메일 등 사용자가 직접 선택
  // Kakao SDK는 도메인 검증 이슈로 카톡 로그인 화면이 뜨는 문제가 있어 사용 안 함.
  const shareKakao = () => {
    if (typeof window === "undefined") return;
    if (navigator.share) {
      navigator.share({ text: shareText, url }).catch(() => {});
    } else {
      navigator.clipboard.writeText(`${shareText} ${url}`).then(
        () => toast("링크가 복사되었습니다!", "success"),
        () => toast("복사에 실패했습니다.", "error")
      );
    }
    setOpen(false);
  };

  const shareSMS = () => {
    window.location.href = `sms:?&body=${encodeURIComponent(shareText + " " + url)}`;
    setOpen(false);
  };

  const shareMore = () => {
    if (navigator.share) {
      navigator.share({ text: shareText, url });
    } else {
      navigator.clipboard.writeText(`${shareText} ${url}`).then(() => toast("복사되었습니다!", "success"));
    }
    setOpen(false);
  };

  const copyLink = () => {
    navigator.clipboard.writeText(url).then(() => toast("링크가 복사되었습니다!", "success"));
    setOpen(false);
  };

  return (
    <>
      <button
        onClick={(e) => {
          e.stopPropagation();
          // 모바일·태블릿: OS 네이티브 공유 시트 즉시 호출
          if (typeof navigator !== "undefined" && (navigator as any).share) {
            (navigator as any).share({ text: shareText, url }).catch(() => {});
          } else {
            setOpen(true);
          }
        }}
        className="w-full h-full py-2 bg-blue-50 text-slate-700 rounded-lg font-bold flex items-center justify-center gap-1.5 hover:bg-blue-100 transition-all border border-blue-100/60 active:scale-95 text-xs"
      >
        <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" /></svg> 친구에게 추천하기
      </button>

      {/* 공유 모달 — Portal로 body에 렌더링 (카드 hover 충돌 방지) */}
      {open && typeof document !== "undefined" && createPortal(
        <div className="fixed inset-0 z-[70] flex items-end sm:items-center justify-center" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[2px]" />
          <div
            className="relative w-full max-w-sm mx-auto bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl overflow-hidden animate-in slide-in-from-bottom sm:zoom-in-95 duration-300"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-5">
              <div className="text-center mb-5">
                <h3 className="text-[15px] font-bold text-slate-900">친구에게 추천하기</h3>
                <p className="text-[11px] text-slate-400 mt-1">추천 시 양쪽 모두 LITE 1개월 무료!</p>
              </div>

              <div className="grid grid-cols-4 gap-3">
                <button onClick={shareKakao} className="flex flex-col items-center gap-2 py-3 rounded-xl hover:bg-yellow-50 transition-all active:scale-95">
                  <div className="w-14 h-14 bg-[#FEE500] rounded-2xl flex items-center justify-center shadow-sm">
                    <span className="text-2xl">💬</span>
                  </div>
                  <span className="text-[11px] font-bold text-slate-700">카카오톡</span>
                </button>

                <button onClick={shareSMS} className="flex flex-col items-center gap-2 py-3 rounded-xl hover:bg-green-50 transition-all active:scale-95">
                  <div className="w-14 h-14 bg-emerald-500 rounded-2xl flex items-center justify-center shadow-sm">
                    <span className="text-2xl">💌</span>
                  </div>
                  <span className="text-[11px] font-bold text-slate-700">문자</span>
                </button>

                <button onClick={shareMore} className="flex flex-col items-center gap-2 py-3 rounded-xl hover:bg-blue-50 transition-all active:scale-95">
                  <div className="w-14 h-14 bg-blue-500 rounded-2xl flex items-center justify-center shadow-sm">
                    <span className="text-2xl">📤</span>
                  </div>
                  <span className="text-[11px] font-bold text-slate-700">더보기</span>
                </button>

                <button onClick={copyLink} className="flex flex-col items-center gap-2 py-3 rounded-xl hover:bg-blue-50 transition-all active:scale-95">
                  <div className="w-14 h-14 bg-blue-500 rounded-2xl flex items-center justify-center shadow-sm">
                    <span className="text-2xl">🔗</span>
                  </div>
                  <span className="text-[11px] font-bold text-slate-700">링크복사</span>
                </button>
              </div>
            </div>

            <button
              onClick={(e) => { e.stopPropagation(); setOpen(false); }}
              className="w-full py-3.5 border-t border-slate-100 text-slate-400 text-[13px] font-medium hover:text-slate-600 hover:bg-slate-50 transition-all"
            >
              닫기
            </button>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

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
  bucket?: string;
  bucket_label?: string;
  reasons?: { icon: string; label: string }[];
  deadline_date?: string;
  deadline_type?: string;
  summary_text?: string;
  region?: string;
  established_years_limit?: number;
  revenue_limit?: number;
  employee_limit?: number;
  origin_url?: string;
  final_url?: string;
  url?: string;
  category?: string;
  department?: string;
  origin_source?: string;
  target_type?: string;
  has_application_form?: boolean;   // 신청서양식 첨부 존재 → 'AI 신청서 작성' 버튼 노출 조건
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
  "Human Resources": "인력",
  "Employment": "인력·고용",
  "Design": "디자인",
  "Tech, R&D, Global": "기술·R&D",
  "Global": "수출·글로벌",
  "Export": "수출·판로",
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
  // "admin-manual"(수동등록)은 내부 관리 메타 — 사용자에게 무의미하고 "나머지는 미검수?" 역추론 유발하므로 배지 숨김
  "sbc": "중진공",
  "sbc-scraper": "중진공",
  "gov24-individual-api": "정부24",
  "gov24-api": "정부24",
};

function getDDayInfo(dateStr?: string, deadlineType?: string): { text: string; days: number | null; urgency: "expired" | "critical" | "warning" | "normal" | "open" | "unknown" } {
  // 날짜가 없으면: 진짜 상시(ongoing)만 "상시모집", 그 외(unknown·미상)는 "마감 확인 필요"로 정직 표기.
  // (마감일 파싱 실패분을 "상시모집"으로 오표기하던 것 차단 — 문제2 정직표시)
  if (!dateStr || isNaN(new Date(dateStr).getTime())) {
    return deadlineType === "ongoing"
      ? { text: "상시모집", days: null, urgency: "open" }
      : { text: "마감 확인 필요", days: null, urgency: "unknown" };
  }
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
  normal: "bg-slate-100 text-slate-600 border-slate-200",
  open: "bg-slate-100 text-slate-600 border-slate-200",
  unknown: "bg-slate-100 text-slate-500 border-slate-200",
};

const URGENCY_BAR: Record<string, string> = {
  expired: "bg-slate-300",
  critical: "bg-rose-500",
  warning: "bg-amber-400",
  normal: "bg-emerald-400",
  open: "bg-sky-400",
  unknown: "bg-slate-300",
};


interface CardProps {
  res: Result;
  selected?: boolean;
  onToggle?: () => void;
  saved?: boolean;
  saving?: boolean;
  onSave?: () => void;
  planStatus?: { plan: string; ai_used?: number; ai_limit?: number; consult_limit?: number } | null;
  onUpgrade?: () => void;
  onLoginRequired?: () => void;
}

export default function ResultCard({ res, selected, onToggle, saved, saving, onSave, planStatus, onUpgrade, onLoginRequired, highlight }: CardProps & { highlight?: boolean }) {
  const isPublic = !!onLoginRequired;
  const isExpired = !isPublic && planStatus?.plan === "expired";
  const isConsultBlocked = !isPublic && planStatus?.consult_limit === 0;  // FREE 플랜: 공고별 상담/신청서 차단
  const { toast } = useToast();
  const dDay = getDDayInfo(res.deadline_date, res.deadline_type);
  // 매핑에 있으면 국문, 없고 영문이면 숨김(한/영 혼용 방지), 없고 국문이면 원본 유지
  const _catRaw = (res.category || "").trim();
  const categoryKr = CATEGORY_KR[_catRaw] || (/[A-Za-z]/.test(_catRaw) ? "" : _catRaw);
  const rawSource = (res.origin_source || "").trim();
  const sourceKey = rawSource.includes(":") ? rawSource.split(":")[0] : rawSource;
  const sourceKr = SOURCE_KR[sourceKey] || SOURCE_KR[rawSource] || "";
  const elig = res.eligibility_logic || {};
  const bizTypes = (elig.business_type || []).slice(0, 3);
  const targetText = bizTypes.length > 0
    ? bizTypes.join(" · ")
    : (res.region && res.region !== "All" && res.region !== "전국" ? res.region : "전국");
  // 제목에 [지역] 태그가 없고 region이 특정 지역이면 앞에 표시
  const regionTag = (res.region && res.region !== "All" && res.region !== "전국" && !/^\[/.test(res.title || ""))
    ? `[${res.region}] `
    : "";

  // 금액 뱃지: support_amount_max(숫자) 우선 사용, 없으면 텍스트 파싱 (엄격)
  // 이전 버그: "P1/P2 과정..." → "1원", "~25개 조직..." → "25원" 오노출
  const _rawAmount = res.support_amount || "";
  const _rawMax = (res as any).support_amount_max;
  const _rawMin = (res as any).support_amount_min;
  const _formatKRW = (n: number, prefix = ""): string => {
    if (!n || n < 10000) return "";  // 1만원 미만은 넌센스로 간주
    if (n >= 100000000) {
      const eok = n / 100000000;
      return `${prefix}${eok % 1 === 0 ? eok : eok.toFixed(1)}억원`;
    }
    // 1천만~1억은 "N,NNN만원" 형식으로 정확히 표기 (반올림 과장 방지)
    const man = Math.round(n / 10000);
    return `${prefix}${man.toLocaleString()}만원`;
  };
  const _formatKoreanAmount = (raw: string, maxVal?: number, minVal?: number): string => {
    // 1) 숫자 컬럼 최우선 (DB에서 정규화된 값)
    if (typeof maxVal === "number" && maxVal >= 10000) {
      const label = _formatKRW(maxVal, "최대 ");
      if (label) return label;
    }
    if (typeof minVal === "number" && minVal >= 10000) {
      const label = _formatKRW(minVal);
      if (label) return label;
    }
    if (!raw) return "";
    // 2) 텍스트에 "억/천만/백만/만" qualifier + "원" 함께 있는 경우만 신뢰
    const m = raw.match(/(최대\s*)?[\d,]+(?:\.\d+)?\s*(?:억|천만|백만|만)\s*원/);
    if (m) {
      // 숫자 부분만 추출해서 0이면 무시 (원문 플레이스홀더 "00,000백만원" 방어)
      const numPart = m[0].match(/[\d,]+/);
      if (numPart && parseInt(numPart[0].replace(/,/g, ""), 10) === 0) return "";
      return m[0].replace(/\s+/g, "");
    }
    // 3) "N원" 명시 패턴 (숫자 + 원 직결, 최소 10,000원 이상)
    const m2 = raw.match(/(최대\s*)?([\d,]{5,})\s*원/);
    if (m2) {
      const n = parseInt(m2[2].replace(/,/g, ""), 10);
      if (!isNaN(n) && n >= 10000) {
        const prefix = m2[1] ? "최대 " : "";
        return _formatKRW(n, prefix) || `${prefix}${n.toLocaleString()}원`;
      }
    }
    // 4) 신뢰할 수 없으면 빈 문자열 → 호출부에서 뱃지 숨김
    return "";
  };
  const amountLabel = _formatKoreanAmount(_rawAmount, _rawMax, _rawMin);
  const amountIsAmount = !!amountLabel && /[0-9]/.test(amountLabel) && /(원|억|만)/.test(amountLabel);

  return (
    <div data-urgency={dDay.urgency} data-aid={res.announcement_id} className={`group relative glass-card pt-3.5 pb-3.5 px-4 md:pt-4 md:pb-4 md:px-5 rounded-xl transition-all duration-300 flex flex-col h-full overflow-hidden pl-4 ${saved ? "ring-2 ring-blue-400 ring-offset-1" : ""} ${selected ? "ring-2 ring-blue-500 ring-offset-2" : ""} ${highlight ? "ring-2 ring-blue-500 ring-offset-2 animate-glow-pulse" : ""}`}>
      {/* 좌측 긴급도 바 — 임박(D-7 이하)에만 표시(전 카드 공통이면 신호가 죽음) */}
      {(dDay.urgency === "critical" || dDay.urgency === "warning") && (
        <div className={`absolute left-0 top-3 bottom-3 w-1 rounded-r-full ${URGENCY_BAR[dDay.urgency]}`} />
      )}
      <div className="absolute -top-16 -right-16 w-40 h-40 bg-blue-500/5 blur-[60px] group-hover:bg-blue-500/10 transition-all duration-1000 pointer-events-none" />

      <div className="flex flex-col gap-3 h-full relative z-[1]">

        {/* Tags + Deadline inline */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {/* 저장 체크박스 — 태그 행 맨 앞 */}
          {onSave && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); if (!saving) onSave(); }}
              disabled={saving}
              className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all shrink-0 ${
                saved
                  ? "bg-blue-600 border-blue-600 text-white shadow-sm"
                  : saving
                  ? "bg-slate-100 border-slate-200 text-transparent cursor-wait"
                  : "bg-blue-50/50 border-blue-300 text-transparent hover:border-blue-500 hover:bg-blue-100"
              }`}
              aria-label={saved ? "저장 취소" : "일정 저장"}
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </button>
          )}
          {onToggle && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onToggle(); }}
              className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all shrink-0 ${
                selected
                  ? "bg-blue-600 border-blue-600 text-white shadow-sm"
                  : "bg-blue-50/50 border-blue-300 text-transparent hover:border-blue-500 hover:bg-blue-100"
              }`}
              aria-label={selected ? "선택 해제" : "선택"}
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </button>
          )}
          {/* 이유 뱃지 (백엔드에서 reasons 제공 시) */}
          {res.reasons && res.reasons.length > 0 && res.reasons.slice(0, 3).map((r, i) => (
            <span key={i} className="px-2 py-0.5 bg-amber-50 text-amber-700 text-[12px] font-bold rounded-full border border-amber-100">
              {r.icon} {r.label}
            </span>
          ))}
          {res.department && (
            <span className="px-2 py-0.5 bg-slate-100 text-slate-600 text-[12px] font-bold rounded-full border border-slate-200">
              {res.department}
            </span>
          )}
          {categoryKr && (
            <span className="px-2 py-0.5 bg-blue-50 text-blue-600 text-[12px] font-bold rounded-full border border-blue-100">
              {categoryKr}
            </span>
          )}
          {sourceKr && (
            <span className="px-2 py-0.5 bg-slate-50 text-slate-500 text-[12px] font-bold rounded-full border border-slate-200">
              {sourceKr}
            </span>
          )}
          {/* D-day 뱃지 — 인라인 */}
          <span className={`ml-auto px-2 py-0.5 rounded-full border text-[12px] font-bold whitespace-nowrap ${URGENCY_STYLES[dDay.urgency]}`}>
            {res.deadline_date ? (() => {
              if (dDay.urgency === "expired") return "마감";
              const d = new Date(res.deadline_date);
              if (isNaN(d.getTime())) return dDay.text;
              const days = ["일","월","화","수","목","금","토"];
              const yearPrefix = d.getFullYear() !== new Date().getFullYear() ? `'${String(d.getFullYear()).slice(2)} ` : "";
              return `${dDay.text} · ${yearPrefix}${d.getMonth()+1}/${d.getDate()}(${days[d.getDay()]})`;
            })() : dDay.text}
          </span>
        </div>

        {/* Title + Amount — 클릭 시 최종 원본 페이지로 이동 (유효 URL만 링크, 필드별 검증) */}
        {bestExternalUrl(res.final_url, res.origin_url, res.url) ? (
          <a
            href={bestExternalUrl(res.final_url, res.origin_url, res.url)}
            target="_blank"
            rel="noopener noreferrer"
            className="font-bold text-slate-900 text-base md:text-lg leading-snug tracking-tight hover:text-blue-600 hover:underline underline-offset-2 transition-colors line-clamp-2 min-h-[2lh] cursor-pointer"
            title={res.title}
            onClick={(e) => e.stopPropagation()}
          >
            {amountIsAmount && (
              <span className="inline-block mr-1.5 px-1.5 py-0.5 text-white text-[11px] font-black rounded align-middle leading-none whitespace-nowrap bg-rose-500">
                {amountLabel}
              </span>
            )}
            {regionTag && <span className="text-blue-500 font-black">{regionTag}</span>}{res.title}
          </a>
        ) : (
          <h3
            className="font-bold text-slate-900 text-base md:text-lg leading-snug tracking-tight transition-colors line-clamp-2 min-h-[2lh]"
            title={res.title}
          >
            {amountIsAmount && (
              <span className="inline-block mr-1.5 px-1.5 py-0.5 text-white text-[11px] font-black rounded align-middle leading-none whitespace-nowrap bg-rose-500">
                {amountLabel}
              </span>
            )}
            {regionTag && <span className="text-blue-500 font-black">{regionTag}</span>}{res.title}
          </h3>
        )}

        {/* Info & Buttons — 중첩 박스 제거(플랫), 여백으로 구분 */}
        <div className="relative flex-1 pt-1 overflow-hidden">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mb-4">
            <p className="text-[12px] font-bold flex items-center gap-1 whitespace-nowrap">
              <span className="w-1 h-1 bg-blue-400 rounded-full shrink-0" />
              <span className="text-slate-400">대상 :</span>
              <span className="text-slate-900">{targetText}{res.established_years_limit ? ` · ${res.established_years_limit}년 이내` : ""}</span>
            </p>
            {(res.revenue_limit || res.employee_limit) && (
              <p className="text-[12px] font-bold flex items-center gap-1 whitespace-nowrap">
                <span className="w-1 h-1 bg-emerald-400 rounded-full shrink-0" />
                <span className="text-slate-400">요건 :</span>
                <span className="text-slate-900">{res.revenue_limit ? `매출 ${Math.floor(res.revenue_limit / 100000000)}억↑` : ""}{res.employee_limit ? `${res.revenue_limit ? " · " : ""}${res.employee_limit}인↑` : ""}</span>
              </p>
            )}
          </div>
          {/* CTA — 일반: [나도 받을 수 있나?(넓게)][친구추천], 신청서: [나도][신청서]한줄+[친구추천] */}
          {(() => {
            const hasForm = res.target_type !== "individual"
              && (res.has_application_form || isKosmePolicyLoan(res));
            const primary = (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (isPublic) { onLoginRequired?.(); return; }
                  if (isExpired) { onUpgrade?.(); return; }
                  if (isConsultBlocked) { toast("AI 상담은 곧 유료 서비스로 제공될 예정입니다. 조금만 기다려 주세요!", "info"); onUpgrade?.(); return; }
                  if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("request-ai-consult", { detail: { announcement: res } }));
                  }
                }}
                className="w-full py-2 rounded-lg text-[13px] font-bold transition-all flex items-center justify-center gap-1 bg-blue-600 text-white hover:bg-blue-700 shadow-sm hover:shadow-md active:scale-[0.98]"
              >
                <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg> 나도 받을 수 있나?
              </button>
            );
            const formBtn = hasForm ? (
              <button
                onClick={async (e) => {
                  e.stopPropagation();
                  if (isPublic) { onLoginRequired?.(); return; }
                  // AI 신청서 작성 = 순수 건별(구독 게이트 없음): 로그인 사용자면 누구나(무료·만료 무관).
                  // 문서 과금은 SmartDoc이 건별(9,900원)로 담당. 구독 유도 안 함.
                  if (process.env.NEXT_PUBLIC_SMARTDOC_READY !== "true") {
                    toast("AI 신청서 작성은 곧 시작됩니다. 조금만 기다려 주세요!", "info");
                    return;
                  }
                  try {
                    const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
                    const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/smartdoc/handoff`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                      body: JSON.stringify({
                        announcement_id: res.announcement_id,
                        // 중진공 정책자금 융자 → 표준 융자신청서 경로(fund-start). 그 외는 공고 양식 경로.
                        ...(isKosmePolicyLoan(res) ? { product: "jungjingong" } : {}),
                      }),
                    });
                    const data = await r.json();
                    if (data?.url) window.location.href = data.url;
                    else toast("SmartDoc 연결에 실패했습니다.", "error");
                  } catch { toast("SmartDoc 연결에 실패했습니다.", "error"); }
                }}
                className="w-full py-2 rounded-lg text-[13px] font-bold transition-all flex items-center justify-center gap-1 bg-amber-500 text-white hover:bg-amber-600 shadow-sm hover:shadow-md active:scale-[0.98]"
              >
                <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 4H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V18a2 2 0 01-2 2z" /></svg> AI 신청서 작성
              </button>
            ) : null;
            const share = <ShareMenu toast={toast} announcementId={res.announcement_id} announcementTitle={res.title} />;
            return (
              <div className="flex flex-col gap-1.5 mt-1 min-w-0">
                {/* 1행 — 모든 카드 동일: 나도 받을 수 있나?(넓게) + 친구추천(좁게) */}
                <div className="flex items-stretch gap-1.5 min-w-0">
                  <div className="flex-[1.7] min-w-0">{primary}</div>
                  <div className="flex-1 min-w-0">{share}</div>
                </div>
                {/* 신청서 있는 카드만 2행에 전체폭으로 */}
                {hasForm && formBtn}
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
}
