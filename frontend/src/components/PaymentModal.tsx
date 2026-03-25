"use client";

import { useToast } from "@/components/ui/Toast";

// ── 무료 체험 기능 안내 ──
const FREE_FEATURES = [
  { label: "AI가 나에게 맞는 지원금을 찾아줍니다", desc: "업종·지역·규모 등 내 조건을 입력하면, 받을 수 있는 정부지원금 목록을 자동으로 보여드려요" },
  { label: "\"이거 나도 받을 수 있어?\" AI에게 물어보세요", desc: "관심 있는 공고를 클릭하면, 지원 자격과 준비서류를 AI가 쉽게 설명해 드려요 (3회)" },
];

// ── 친구 추천 시 추가 혜택 ──
const REFERRAL_BENEFITS = [
  { label: "친구와 함께 쓰면 AI 상담 무제한!", desc: "친구에게 공유하면, 나도 친구도 1개월간 AI 상담 횟수 제한이 풀려요" },
  { label: "최대 5번까지 가능", desc: "친구 5명에게 공유하면 최대 5개월간 무제한 혜택!" },
];


interface PaymentModalProps {
  planStatus: { plan: string; days_left: number | null; label: string } | null;
  onSuccess: (token: string, plan: any) => void;
  onClose: () => void;
}

export default function PaymentModal({ planStatus, onClose }: PaymentModalProps) {
  const { toast } = useToast();

  const handleShare = async () => {
    const url = "https://govmatch.kr";
    const text = "정부지원금, 아직도 직접 찾고 계세요?\nAI가 내 조건에 맞는 지원금을 자동으로 찾아줍니다.\n친구 추천 시 양쪽 모두 상담 무제한 혜택!";
    try {
      if (typeof navigator !== "undefined" && navigator.share) {
        await navigator.share({ title: "지원금GO — AI 맞춤 지원금 매칭", text, url });
      } else {
        await navigator.clipboard.writeText(`${text}\n${url}`);
        toast("공유 링크가 복사되었습니다!", "success");
      }
    } catch {
      try {
        await navigator.clipboard.writeText(`${text}\n${url}`);
        toast("공유 링크가 복사되었습니다!", "success");
      } catch {
        toast("공유에 실패했습니다.", "error");
      }
    }
  };

  const daysLeft = planStatus?.days_left;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-white/60 overflow-hidden animate-in zoom-in-95 duration-300 max-h-[90vh] overflow-y-auto">
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-emerald-500/10 blur-[60px] rounded-full pointer-events-none" />
        <div className="absolute -bottom-20 -left-20 w-40 h-40 bg-indigo-500/10 blur-[60px] rounded-full pointer-events-none" />

        <div className="relative z-10 p-5 sm:p-7">
          {/* Header */}
          <div className="text-center mb-5">
            <h2 className="text-lg font-bold text-slate-900 tracking-tight mb-1">
              지금은 무료로 이용하실 수 있습니다!
            </h2>
            <p className="text-slate-500 text-xs font-medium">
              모든 기능을 먼저 체험해 보세요
            </p>
          </div>

          {/* ── 현재 이용 가능한 기능 ── */}
          <div className="mb-5 rounded-xl border border-emerald-200 overflow-hidden">
            <div className="bg-emerald-50 px-4 py-2.5 border-b border-emerald-200">
              <p className="text-[12px] font-bold text-emerald-700">지금 바로 할 수 있어요</p>
            </div>
            <div className="divide-y divide-emerald-100">
              {FREE_FEATURES.map((f, i) => (
                <div key={i} className="flex items-start gap-3 px-4 py-3">
                  <span className="text-emerald-500 text-sm mt-0.5">&#10003;</span>
                  <div>
                    <div className="text-[12px] font-bold text-slate-800">{f.label}</div>
                    <div className="text-[10px] text-slate-400 mt-0.5 leading-tight">{f.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ── 친구 추천 혜택 ── */}
          <div className="mb-5 rounded-xl border border-amber-200 overflow-hidden">
            <div className="bg-amber-50 px-4 py-2.5 border-b border-amber-200">
              <p className="text-[12px] font-bold text-amber-700">친구에게 알려주면?</p>
            </div>
            <div className="divide-y divide-amber-100">
              {REFERRAL_BENEFITS.map((b, i) => (
                <div key={i} className="flex items-start gap-3 px-4 py-3">
                  <span className="text-amber-500 text-sm mt-0.5">&#9733;</span>
                  <div>
                    <div className="text-[12px] font-bold text-slate-800">{b.label}</div>
                    <div className="text-[10px] text-slate-400 mt-0.5 leading-tight">{b.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 공유 버튼 */}
          <button
            onClick={handleShare}
            className="w-full py-3.5 rounded-xl font-bold text-sm shadow-lg transition-all active:scale-[0.98] mb-3 bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:from-indigo-700 hover:to-violet-700 shadow-indigo-200 flex items-center justify-center gap-2"
          >
            <span className="text-base">&#128228;</span>
            친구에게 공유하고 무제한 혜택 받기
          </button>

          <button
            onClick={onClose}
            className="w-full py-2.5 text-slate-400 hover:text-slate-600 text-xs font-semibold transition-all text-center"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
