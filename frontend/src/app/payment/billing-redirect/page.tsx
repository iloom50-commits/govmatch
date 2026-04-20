"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL;

type Status = "processing" | "success" | "error";

function BillingRedirectContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<Status>("processing");
  const [message, setMessage] = useState("결제 정보를 확인하고 있어요...");

  useEffect(() => {
    // PortOne v2 리다이렉트 쿼리 파라미터
    // - 성공: ?billingKey=...&txId=...&transactionType=ISSUE_BILLING_KEY
    // - 실패/취소: ?code=USER_CANCEL&message=...
    const code = searchParams.get("code");
    const errMsg = searchParams.get("message");
    const billingKey = searchParams.get("billingKey");

    // sessionStorage 컨텍스트 복원
    let ctx: { targetPlan?: "lite" | "pro"; token?: string; savedAt?: number } = {};
    try {
      const raw = sessionStorage.getItem("portone_billing_context");
      if (raw) ctx = JSON.parse(raw);
      sessionStorage.removeItem("portone_billing_context");
    } catch {
      /* ignore */
    }

    // 실패/취소 처리
    if (code && code !== "SUCCESS") {
      const decoded = errMsg ? decodeURIComponent(errMsg) : "결제가 취소되었습니다.";
      router.replace(`/payment/fail?message=${encodeURIComponent(decoded)}`);
      return;
    }

    if (!billingKey) {
      router.replace(`/payment/fail?message=${encodeURIComponent("빌링키 발급 정보가 누락되었습니다.")}`);
      return;
    }

    const token = ctx.token || localStorage.getItem("auth_token") || "";
    const targetPlan = (ctx.targetPlan as "lite" | "pro") || "lite";

    if (!token) {
      router.replace(`/payment/fail?message=${encodeURIComponent("로그인 정보가 만료되었습니다. 다시 로그인해 주세요.")}`);
      return;
    }

    // /api/plan/subscribe 호출
    (async () => {
      try {
        const res = await fetch(`${API}/api/plan/subscribe`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ billing_key: billingKey, target_plan: targetPlan }),
        });
        const data = await res.json();
        if (!res.ok) {
          setStatus("error");
          setMessage(data.detail || "구독 시작에 실패했습니다.");
          setTimeout(() => {
            router.replace(`/payment/fail?message=${encodeURIComponent(data.detail || "구독 시작 실패")}`);
          }, 2000);
          return;
        }

        // 새 토큰 저장
        if (data.token) {
          localStorage.setItem("auth_token", data.token);
        }

        setStatus("success");
        setMessage(data.message || "구독이 시작되었습니다!");

        // 메인으로 복귀 (full reload — Dashboard 프로필 재조회)
        setTimeout(() => {
          window.location.href = "/?upgraded=" + targetPlan;
        }, 2000);
      } catch {
        setStatus("error");
        setMessage("결제 처리 중 통신 오류가 발생했습니다.");
        setTimeout(() => {
          router.replace(`/payment/fail?message=${encodeURIComponent("결제 처리 통신 오류")}`);
        }, 2000);
      }
    })();
  }, [searchParams, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 to-violet-50 px-4">
      <div className="bg-white rounded-3xl p-10 shadow-2xl text-center max-w-sm w-full">
        {status === "processing" && (
          <>
            <div className="w-14 h-14 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-5" />
            <h2 className="text-lg font-black text-slate-900 mb-1">결제 확인 중</h2>
            <p className="text-slate-500 text-[13px]">{message}</p>
          </>
        )}
        {status === "success" && (
          <>
            <div className="w-14 h-14 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-5">
              <svg className="w-7 h-7 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-lg font-black text-slate-900 mb-1">결제 완료!</h2>
            <p className="text-slate-500 text-[13px]">{message}</p>
            <p className="text-slate-400 text-[11px] mt-3">메인 화면으로 이동합니다...</p>
          </>
        )}
        {status === "error" && (
          <>
            <div className="w-14 h-14 bg-rose-100 rounded-full flex items-center justify-center mx-auto mb-5">
              <svg className="w-7 h-7 text-rose-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h2 className="text-lg font-black text-slate-900 mb-1">오류 발생</h2>
            <p className="text-slate-500 text-[13px]">{message}</p>
            <p className="text-slate-400 text-[11px] mt-3">잠시 후 안내 페이지로 이동합니다...</p>
          </>
        )}
      </div>
    </div>
  );
}

export default function BillingRedirectPage() {
  return (
    <Suspense>
      <BillingRedirectContent />
    </Suspense>
  );
}
