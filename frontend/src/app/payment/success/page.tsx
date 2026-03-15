"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";

const API = process.env.NEXT_PUBLIC_API_URL;

function PaymentSuccessContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<"processing" | "success" | "error">("processing");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const paymentKey = searchParams.get("paymentKey");
    const orderId = searchParams.get("orderId");
    const amount = searchParams.get("amount");
    const targetPlan = searchParams.get("plan") || "basic";
    const token = searchParams.get("token") || localStorage.getItem("auth_token");

    if (!paymentKey || !orderId || !amount) {
      setStatus("error");
      setMessage("결제 정보가 올바르지 않습니다.");
      return;
    }

    fetch(`${API}/api/plan/upgrade`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        payment_key: paymentKey,
        order_id: orderId,
        amount: Number(amount),
        target_plan: targetPlan,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.token) {
          localStorage.setItem("auth_token", data.token);
        }
        setStatus("success");
        const label = targetPlan === "pro" ? "PRO" : "BASIC";
        setMessage(`${label} 플랜으로 업그레이드되었습니다!`);
        setTimeout(() => router.push("/"), 2500);
      })
      .catch(() => {
        setStatus("error");
        setMessage("결제 확인 중 오류가 발생했습니다.");
      });
  }, [searchParams, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 to-violet-50">
      <div className="bg-white rounded-3xl p-12 shadow-2xl text-center max-w-sm w-full mx-4">
        {status === "processing" && (
          <>
            <div className="w-16 h-16 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-6" />
            <h2 className="text-xl font-black text-slate-900">결제 확인 중...</h2>
          </>
        )}
        {status === "success" && (
          <>
            <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-8 h-8 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-xl font-black text-slate-900 mb-2">결제 완료!</h2>
            <p className="text-slate-500 text-sm">{message}</p>
            <p className="text-slate-400 text-xs mt-3">잠시 후 메인 화면으로 이동합니다...</p>
          </>
        )}
        {status === "error" && (
          <>
            <div className="w-16 h-16 bg-rose-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-8 h-8 text-rose-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h2 className="text-xl font-black text-slate-900 mb-2">오류 발생</h2>
            <p className="text-slate-500 text-sm mb-6">{message}</p>
            <button
              onClick={() => router.push("/")}
              className="px-6 py-3 bg-indigo-600 text-white rounded-xl font-black text-sm hover:bg-indigo-700 transition-all"
            >
              메인으로 돌아가기
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default function PaymentSuccessPage() {
  return (
    <Suspense>
      <PaymentSuccessContent />
    </Suspense>
  );
}
