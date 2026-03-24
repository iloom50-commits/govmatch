"use client";

import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { loadTossPayments, ANONYMOUS } from "@tosspayments/tosspayments-sdk";

const API = process.env.NEXT_PUBLIC_API_URL;
const TOSS_CLIENT_KEY = process.env.NEXT_PUBLIC_TOSS_CLIENT_KEY || "test_ck_jExPeJWYVQ1RJDzyR6GxV49R5gvN";

const PLANS = [
  {
    id: "basic",
    name: "BASIC",
    price: 4900,
    priceLabel: "4,900",
    color: "indigo",
    features: [
      { text: "AI 맞춤 매칭", desc: "무제한", highlight: false },
      { text: "맞춤 매칭 알림", desc: "무제한", highlight: false },
      { text: "AI 지원대상 판별", desc: "무제한", highlight: true },
      { text: "AI 신청서 작성", desc: "자동 ₩4,900 / 전문가 ₩14,900", highlight: false },
    ],
  },
  {
    id: "pro",
    name: "PRO",
    price: 19000,
    priceLabel: "19,000",
    popular: true,
    color: "violet",
    features: [
      { text: "BASIC 기능 전부 포함", desc: "", highlight: false },
      { text: "자유 상담 (지원사업 Q&A)", desc: "무제한", highlight: true },
      { text: "AI 컨설턴트 (맞춤 매칭)", desc: "무제한", highlight: true },
      { text: "AI 신청서 작성", desc: "자동 ₩4,900 / 전문가 ₩14,900", highlight: false },
    ],
  },
];

interface PaymentModalProps {
  planStatus: { plan: string; days_left: number | null; label: string } | null;
  onSuccess: (token: string, plan: any) => void;
  onClose: () => void;
}

export default function PaymentModal({ planStatus, onSuccess, onClose }: PaymentModalProps) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState("pro");

  const plan = PLANS.find((p) => p.id === selectedPlan)!;

  const handleFreeTrial = async () => {
    setLoading(true);
    const token = localStorage.getItem("auth_token");
    try {
      const res = await fetch(`${API}/api/plan/upgrade`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          target_plan: selectedPlan,
          free_trial: true,
          amount: 0,
        }),
      });
      const data = await res.json();
      if (data.status === "SUCCESS") {
        localStorage.setItem("auth_token", data.token);
        toast(`${plan.name} 플랜 1개월 무료 체험이 시작되었습니다!`, "success");
        onSuccess(data.token, data.plan);
      } else {
        toast(data.detail || "오류가 발생했습니다.", "error");
      }
    } catch {
      toast("서버 오류가 발생했습니다.", "error");
    }
    setLoading(false);
  };

  const handlePayment = async () => {
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
        amount: { currency: "KRW", value: plan.price },
        orderId,
        orderName: `지원금GO ${plan.name} 플랜`,
        successUrl: `${window.location.origin}/payment/success?token=${encodeURIComponent(token || "")}&plan=${selectedPlan}`,
        failUrl: `${window.location.origin}/payment/fail`,
      });
    } catch (err: any) {
      if (err?.code === "PAY_PROCESS_CANCELED") {
        toast("결제가 취소되었습니다.", "error");
      } else {
        toast(err?.message || "결제 중 오류가 발생했습니다.", "error");
      }
      setLoading(false);
    }
  };

  const isFreePlan = !planStatus || planStatus.plan === "free" || planStatus.plan === "expired";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-white/60 overflow-hidden animate-in zoom-in-95 duration-300">
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-indigo-500/10 blur-[60px] rounded-full pointer-events-none" />
        <div className="absolute -bottom-20 -left-20 w-40 h-40 bg-violet-500/10 blur-[60px] rounded-full pointer-events-none" />

        <div className="relative z-10 p-6 sm:p-8">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-indigo-100 text-indigo-700 rounded-full text-[11px] font-bold uppercase tracking-widest mb-3">
              플랜 선택
            </div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">
              더 많은 AI 기능을 이용하세요
            </h2>
            <p className="text-slate-500 text-xs font-medium">
              공고별 상담, AI 상담 무제한, 신청서 작성까지
            </p>
          </div>

          {/* Plan Cards */}
          <div className="grid grid-cols-2 gap-3 mb-5">
            {PLANS.map((p) => (
              <button
                key={p.id}
                onClick={() => setSelectedPlan(p.id)}
                className={`relative text-left p-4 rounded-xl border-2 transition-all ${
                  selectedPlan === p.id
                    ? p.id === "pro"
                      ? "border-violet-500 bg-violet-50/50 shadow-md"
                      : "border-indigo-500 bg-indigo-50/50 shadow-md"
                    : "border-slate-200 bg-white hover:border-slate-300"
                }`}
              >
                {p.popular && (
                  <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 px-2.5 py-0.5 bg-violet-600 text-white text-[11px] font-bold rounded-full">
                    추천
                  </span>
                )}
                <div className={`text-xs font-bold mb-1 ${p.id === "pro" ? "text-violet-600" : "text-indigo-600"}`}>{p.name}</div>
                <div className="flex items-end gap-0.5 mb-3">
                  <span className="text-2xl font-bold text-slate-900">{p.priceLabel}</span>
                  <span className="text-[11px] font-semibold text-slate-500 pb-0.5">원/월</span>
                </div>
                <div className="space-y-1.5">
                  {p.features.map((f, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <svg className={`w-3.5 h-3.5 flex-shrink-0 ${f.highlight ? "text-violet-500" : "text-indigo-500"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                      <span className={`text-[11px] font-medium ${f.highlight ? "text-violet-700 font-bold" : "text-slate-600"}`}>
                        {f.text} <span className="text-slate-400">{f.desc}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </button>
            ))}
          </div>

          {/* Free vs Paid comparison hint */}
          <div className="text-center mb-4 px-3 py-2 bg-slate-50 rounded-lg border border-slate-100">
            <p className="text-[11px] text-slate-500 font-medium">
              FREE 플랜 (영구 무료): AI 매칭 + 지원대상 판별 1회 무료 | 추천 보상: BASIC 1개월 무료
            </p>
          </div>

          {/* Free Trial Button (첫 이용자만) */}
          {isFreePlan && (
            <button
              onClick={handleFreeTrial}
              disabled={loading}
              className={`w-full py-3 rounded-lg font-bold text-sm shadow-lg transition-all active:scale-[0.98] mb-3 ${
                selectedPlan === "pro"
                  ? "bg-violet-600 text-white hover:bg-violet-700 shadow-violet-200"
                  : "bg-indigo-600 text-white hover:bg-indigo-700 shadow-indigo-200"
              }`}
            >
              {loading ? (
                <span className="animate-pulse">처리 중...</span>
              ) : (
                <>첫 달 무료로 {plan.name} 시작하기</>
              )}
            </button>
          )}

          {/* Paid Upgrade (이미 유료 경험 있는 사용자) */}
          {!isFreePlan && (
            <>
              <label className="flex items-start gap-2.5 mb-4 cursor-pointer group">
                <input
                  type="checkbox"
                  className="w-4 h-4 accent-indigo-600 mt-0.5 flex-shrink-0"
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                />
                <span className="text-[11px] text-slate-500 font-medium leading-relaxed group-hover:text-slate-700 transition-colors">
                  월 {plan.priceLabel}원 정기결제에 동의합니다. 언제든 해지할 수 있으며, 해지 시 남은 기간까지 이용 가능합니다.
                </span>
              </label>

              <button
                onClick={handlePayment}
                disabled={loading || !agreed}
                className={`w-full py-3 rounded-lg font-bold text-sm shadow-lg transition-all active:scale-[0.98] ${
                  agreed
                    ? selectedPlan === "pro"
                      ? "bg-violet-600 text-white hover:bg-violet-700 shadow-violet-200"
                      : "bg-indigo-600 text-white hover:bg-indigo-700 shadow-indigo-200"
                    : "bg-slate-200 text-slate-400 cursor-not-allowed shadow-none"
                }`}
              >
                {loading ? (
                  <span className="animate-pulse">결제 처리 중...</span>
                ) : (
                  <>월 {plan.priceLabel}원으로 {plan.name} 시작하기</>
                )}
              </button>
            </>
          )}

          <button
            onClick={onClose}
            className="w-full mt-3 py-2 text-slate-400 hover:text-slate-600 text-xs font-semibold transition-all text-center"
          >
            나중에 하기
          </button>

          <p className="text-[11px] text-slate-400 text-center mt-3 font-medium leading-relaxed">
            결제는 토스페이먼츠를 통해 안전하게 처리됩니다. VAT 포함 가격입니다.
          </p>
        </div>
      </div>
    </div>
  );
}
