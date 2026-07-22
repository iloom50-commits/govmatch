"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL;

type Status = "processing" | "success" | "error";

function ChargeCallbackContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<Status>("processing");
  const [message, setMessage] = useState("결제 정보를 확인하고 있어요...");
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return; // StrictMode 중복 실행 방지
    ranRef.current = true;

    // PortOne v2 리다이렉트 쿼리 — 실패/취소: code+message / 성공: paymentId
    const code = searchParams.get("code");
    const errMsg = searchParams.get("message");
    const paymentId = searchParams.get("paymentId");

    if (code && code !== "SUCCESS") {
      const decoded = errMsg ? decodeURIComponent(errMsg) : "결제가 취소되었습니다.";
      router.replace(`/payment/fail?message=${encodeURIComponent(decoded)}`);
      return;
    }

    if (!paymentId) {
      router.replace(`/payment/fail?message=${encodeURIComponent("결제 정보가 누락되었습니다.")}`);
      return;
    }

    const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") || "" : "";
    if (!token) {
      router.replace(`/payment/fail?message=${encodeURIComponent("로그인 정보가 만료되었습니다. 다시 로그인해 주세요.")}`);
      return;
    }

    // 서버 검증(멱등) — 프론트 결과는 신뢰하지 않는다.
    (async () => {
      try {
        const res = await fetch(`${API}/api/wallet/charge/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ payment_id: paymentId }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          setStatus("error");
          const m = typeof data.detail === "string" ? data.detail : "충전 검증에 실패했습니다.";
          setMessage(m);
          setTimeout(() => router.replace(`/payment/fail?message=${encodeURIComponent(m)}`), 2000);
          return;
        }
        setStatus("success");
        setMessage(
          data.duplicate
            ? "이미 처리된 결제예요."
            : `충전 완료! 현재 ${(data.credits ?? 0).toLocaleString()} 크레딧`
        );
        // 홈으로 복귀 — 홈에서 잔액을 다시 조회한다.
        setTimeout(() => router.replace("/?charged=1"), 1800);
      } catch {
        setStatus("error");
        setMessage("결제 확인 중 오류가 발생했어요. 잠시 후 다시 시도해 주세요.");
        setTimeout(() => router.replace("/"), 2200);
      }
    })();
  }, [searchParams, router]);

  const icon = status === "success" ? "✅" : status === "error" ? "⚠️" : "⏳";

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-xs bg-white rounded-2xl shadow-sm border border-slate-100 p-8 text-center">
        <div className="text-4xl mb-4">{icon}</div>
        <p className="text-[14px] font-semibold text-slate-800 leading-relaxed">{message}</p>
        {status === "processing" && (
          <div className="mt-5 mx-auto w-6 h-6 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        )}
      </div>
    </div>
  );
}

export default function ChargeCallbackPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-slate-50" />}>
      <ChargeCallbackContent />
    </Suspense>
  );
}
