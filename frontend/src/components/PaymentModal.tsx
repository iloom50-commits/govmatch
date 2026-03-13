"use client";

import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { loadTossPayments, ANONYMOUS } from "@tosspayments/tosspayments-sdk";

const API = process.env.NEXT_PUBLIC_API_URL;
const TOSS_CLIENT_KEY = process.env.NEXT_PUBLIC_TOSS_CLIENT_KEY || "test_ck_D5GePWvyJnrK0W0k6q8gLzN97Emo";

interface PaymentModalProps {
  planStatus: { plan: string; days_left: number | null; label: string } | null;
  onSuccess: (token: string, plan: any) => void;
  onClose: () => void;
}

export default function PaymentModal({ planStatus, onSuccess, onClose }: PaymentModalProps) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [agreed, setAgreed] = useState(false);

  const handleUpgrade = async () => {
    if (!agreed) {
      toast("이용약관에 동의해 주세요.", "error");
      return;
    }

    setLoading(true);
    const token = localStorage.getItem("auth_token");
    const orderId = `ORDER_${Date.now()}_${Math.random().toString(36).slice(2, 8).toUpperCase()}`;

    try {
      const tossPayments = await loadTossPayments(TOSS_CLIENT_KEY);
      const payment = tossPayments.payment({ customerKey: ANONYMOUS });

      await payment.requestPayment({
        method: "CARD",
        amount: { currency: "KRW", value: 4900 },
        orderId,
        orderName: "AI 정부지원금 매칭 베이직 플랜",
        successUrl: `${window.location.origin}/payment/success?token=${encodeURIComponent(token || "")}`,
        failUrl: `${window.location.origin}/payment/fail`,
      });
      // requestPayment는 성공 시 successUrl로 리다이렉트되므로 아래는 실행 안 됨
    } catch (err: any) {
      if (err?.code === "PAY_PROCESS_CANCELED") {
        toast("결제가 취소되었습니다.", "error");
      } else {
        toast(err?.message || "결제 중 오류가 발생했습니다.", "error");
      }
      setLoading(false);
    }
  };

  const isExpired = planStatus?.plan === "expired";
  const isTrial = planStatus?.plan === "trial";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-md bg-white rounded-[2rem] shadow-2xl border border-white/60 overflow-hidden animate-in zoom-in-95 duration-300">
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-indigo-500/10 blur-[60px] rounded-full pointer-events-none" />
        <div className="absolute -bottom-20 -left-20 w-40 h-40 bg-violet-500/10 blur-[60px] rounded-full pointer-events-none" />

        <div className="relative z-10 p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-indigo-100 text-indigo-700 rounded-full text-[10px] font-black uppercase tracking-widest mb-4">
              {isExpired ? "체험 기간 만료" : "업그레이드"}
            </div>
            <h2 className="text-2xl font-black text-slate-900 tracking-tight mb-1">
              베이직 플랜
            </h2>
            <p className="text-slate-500 text-xs font-medium">
              {isExpired
                ? "체험 기간이 종료되었습니다. 베이직 플랜으로 계속 이용하세요."
                : "지금 업그레이드하면 중단 없이 이용할 수 있습니다."}
            </p>
          </div>

          {/* Price */}
          <div className="bg-gradient-to-br from-indigo-50 to-violet-50 rounded-2xl p-6 mb-6 border border-indigo-100">
            <div className="flex items-end justify-center gap-1 mb-4">
              <span className="text-4xl font-black text-slate-900">4,900</span>
              <span className="text-sm font-black text-slate-500 pb-1">원/월</span>
            </div>
            <div className="space-y-2.5">
              {[
                "AI 맞춤 정부지원금 매칭 (무제한)",
                "매일 오전 10시 맞춤 리포트 발송",
                "실시간 신규 공고 알림",
                "마감일 일정 관리",
                "브라우저 푸시 알림",
              ].map((feature, i) => (
                <div key={i} className="flex items-center gap-2.5">
                  <div className="w-5 h-5 bg-indigo-600 rounded-full flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <span className="text-xs font-bold text-slate-700">{feature}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Current Status */}
          {isTrial && planStatus?.days_left !== null && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 mb-5 text-center">
              <span className="text-xs font-black text-amber-800">
                무료체험 {planStatus.days_left}일 남음
              </span>
            </div>
          )}

          {/* Agreement */}
          <label className="flex items-start gap-2.5 mb-5 cursor-pointer group">
            <input
              type="checkbox"
              className="w-4 h-4 accent-indigo-600 mt-0.5 flex-shrink-0"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
            />
            <span className="text-[11px] text-slate-500 font-medium leading-relaxed group-hover:text-slate-700 transition-colors">
              월 4,900원 정기결제에 동의합니다. 언제든 해지할 수 있으며, 해지 시 남은 기간까지 이용 가능합니다.
            </span>
          </label>

          {/* Actions */}
          <button
            onClick={handleUpgrade}
            disabled={loading || !agreed}
            className={`w-full py-4 rounded-2xl font-black text-base shadow-xl transition-all active:scale-95 flex items-center justify-center group ${
              agreed
                ? "bg-indigo-600 text-white hover:bg-indigo-700 shadow-indigo-200"
                : "bg-slate-200 text-slate-400 cursor-not-allowed shadow-none"
            }`}
          >
            {loading ? (
              <span className="animate-pulse">결제 처리 중...</span>
            ) : (
              <>
                월 4,900원으로 시작하기
                <span className="ml-2 group-hover:translate-x-1 transition-transform">→</span>
              </>
            )}
          </button>

          <button
            onClick={onClose}
            className="w-full mt-3 py-2 text-slate-400 hover:text-slate-600 text-xs font-black transition-all text-center"
          >
            {isExpired ? "나중에 결제하기" : "취소"}
          </button>

          <p className="text-[9px] text-slate-400 text-center mt-4 font-medium leading-relaxed">
            결제는 토스페이먼츠를 통해 안전하게 처리됩니다.
            <br />
            VAT 포함 가격이며, 매월 자동 결제됩니다.
          </p>
        </div>
      </div>
    </div>
  );
}
