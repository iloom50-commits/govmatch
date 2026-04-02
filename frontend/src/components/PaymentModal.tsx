"use client";

import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import * as PortOne from "@portone/browser-sdk/v2";

const API = process.env.NEXT_PUBLIC_API_URL;
const STORE_ID = process.env.NEXT_PUBLIC_PORTONE_STORE_ID || "";
const CHANNEL_KEY = process.env.NEXT_PUBLIC_PORTONE_CHANNEL_KEY || "";

interface PaymentModalProps {
  planStatus: { plan: string; days_left: number | null; label: string } | null;
  userType?: string | null;
  onSuccess: (token: string, plan: any) => void;
  onClose: () => void;
}

export default function PaymentModal({ planStatus, userType, onSuccess, onClose }: PaymentModalProps) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const isBusiness = userType === "business" || userType === "both";
  const isIndividual = userType === "individual";

  const getToken = () => typeof window !== "undefined" ? localStorage.getItem("auth_token") || "" : "";

  // PortOne iframe 잔여물 정리
  const cleanupPortone = () => {
    document.getElementById("imp-iframe-wrapper")?.remove();
    document.querySelectorAll("iframe[src*='portone'], iframe[src*='iamport']").forEach(el => {
      (el as HTMLElement).closest("div[style*='z-index']")?.remove();
    });
  };

  const handleSubscribe = async (targetPlan: "lite" | "pro") => {
    setLoading(true);
    try {
      const token = getToken();

      console.log("[Payment] requestIssueBillingKey 호출...", { storeId: STORE_ID, channelKey: CHANNEL_KEY });
      const billingKeyResponse = await PortOne.requestIssueBillingKey({
        storeId: STORE_ID,
        channelKey: CHANNEL_KEY,
        billingKeyMethod: "CARD",
      });
      console.log("[Payment] billingKeyResponse:", JSON.stringify(billingKeyResponse));

      const billingKey = (billingKeyResponse as any)?.billingKey;
      console.log("[Payment] billingKey:", billingKey, "code:", billingKeyResponse?.code);

      // 사용자 취소
      if (billingKeyResponse?.code === "USER_CANCEL") {
        cleanupPortone();
        setLoading(false);
        return;
      }

      // 빌링키가 없으면 에러
      if (!billingKey) {
        cleanupPortone();
        console.log("[Payment] 빌링키 없음, 에러:", billingKeyResponse?.code, billingKeyResponse?.message);
        toast(billingKeyResponse?.message || "카드 등록에 실패했습니다. 다시 시도해주세요.", "error");
        setLoading(false);
        return;
      }

      // 빌링키가 발급됐으면 PG 에러가 있어도 진행 (테스트 환경 호환)
      if (billingKeyResponse?.code) {
        console.log("[Payment] PG 경고 (빌링키 발급됨):", billingKeyResponse.code, billingKeyResponse.message);
      }

      // 백엔드로 빌링키 전달 → 무료 체험 시작
      console.log("[Payment] 백엔드 subscribe 호출...");
      const res = await fetch(`${API}/api/plan/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ billing_key: billingKey, target_plan: targetPlan }),
      });
      const data = await res.json();
      console.log("[Payment] subscribe 응답:", res.status, JSON.stringify(data));
      if (!res.ok) { toast(data.detail || "구독 시작 실패", "error"); setLoading(false); return; }
      toast(data.message || "구독이 시작되었습니다!", "success");
      onSuccess(data.token, data.plan);
    } catch (err: unknown) {
      cleanupPortone();
      console.error("[Payment] 에러:", err);
      const msg = err instanceof Error ? err.message : "결제 중 오류가 발생했습니다.";
      toast(msg, "error");
    } finally {
      cleanupPortone();
      setLoading(false);
    }
  };

  const handleShare = async () => {
    const url = "https://govmatch.kr";
    const text = "정부지원금, 아직도 직접 찾고 계세요?\nAI가 내 조건에 맞는 지원금을 자동으로 찾아줍니다.\n친구 추천 시 양쪽 모두 상담 혜택!";
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-white/60 overflow-hidden animate-in zoom-in-95 duration-300 max-h-[90vh] overflow-y-auto">
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-indigo-500/10 blur-[60px] rounded-full pointer-events-none" />

        <div className="relative z-10 p-5 sm:p-7">
          {/* 닫기 버튼 (우상단) */}
          <button onClick={onClose} className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400 text-lg z-20">✕</button>

          {/* Header */}
          <div className="text-center mb-5">
            <h2 className="text-lg font-bold text-slate-900 tracking-tight mb-1">
              {planStatus?.plan === "free" ? "현재 무료 이용 중" : `${planStatus?.label || ""} 플랜`}
            </h2>
            <p className="text-slate-500 text-xs font-medium">
              더 많은 AI 상담이 필요하시면 업그레이드하세요
            </p>
          </div>

          {/* ── 현재 무료 기능 ── */}
          <div className="mb-4 rounded-xl border border-emerald-200 overflow-hidden">
            <div className="bg-emerald-50 px-4 py-2 border-b border-emerald-200">
              <p className="text-[11px] font-bold text-emerald-700">현재 이용 가능</p>
            </div>
            <div className="px-4 py-3 space-y-1.5">
              <div className="flex items-center gap-2 text-[12px]">
                <span className="text-emerald-500">&#10003;</span>
                <span className="text-slate-700 font-medium">맞춤 공고 알림 — 무제한</span>
              </div>
              <div className="flex items-center gap-2 text-[12px]">
                <span className="text-emerald-500">&#10003;</span>
                <span className="text-slate-700 font-medium">공고AI 상담 — 월 3회</span>
              </div>
            </div>
          </div>

          {/* ── 유료 플랜 ── */}
          <div className="mb-4 space-y-3">
            {/* 개인 LITE or 사업자 LITE — 이미 LITE/PRO면 숨김 */}
            {!["lite", "lite_trial", "pro", "biz"].includes(planStatus?.plan || "") && (
            <div className="rounded-xl border-2 border-indigo-200 overflow-hidden hover:border-indigo-400 transition-all">
              <div className="bg-indigo-50 px-4 py-2.5 border-b border-indigo-200 flex items-center justify-between">
                <div>
                  <span className="text-[13px] font-bold text-indigo-700">LITE</span>
                  <span className="text-[11px] text-indigo-500 ml-1.5">
                    {isIndividual ? "개인" : "사업자"}
                  </span>
                </div>
                <span className="text-[14px] font-black text-indigo-700">
                  {isIndividual ? "2,900" : "4,900"}
                  <span className="text-[10px] font-medium text-indigo-400">원/월</span>
                </span>
              </div>
              <div className="px-4 py-3 space-y-1.5">
                <div className="flex items-center gap-2 text-[12px]">
                  <span className="text-indigo-500">&#10003;</span>
                  <span className="text-slate-700 font-medium">공고AI 상담 — <strong>월 10회</strong></span>
                </div>
                <div className="flex items-center gap-2 text-[12px]">
                  <span className="text-indigo-500">&#10003;</span>
                  <span className="text-slate-700 font-medium">맞춤 공고 알림 — 무제한</span>
                </div>
              </div>
              <div className="px-4 pb-3">
                <button
                  disabled={loading}
                  onClick={() => handleSubscribe("lite")}
                  className="w-full py-2.5 bg-indigo-600 text-white rounded-lg text-[12px] font-bold hover:bg-indigo-700 transition-all active:scale-[0.98] disabled:opacity-50"
                >
                  {loading ? "처리 중..." : "1개월 무료 체험 시작"}
                </button>
                <p className="text-[9px] text-slate-400 text-center mt-1.5">카드 등록 후 1개월 무료, 이후 월 {isIndividual ? "2,900" : "4,900"}원 자동결제</p>
              </div>
            </div>
            )}

            {/* 사업자 PRO — 사업자/both만 표시, LITE 사용자도 PRO 업그레이드 가능 */}
            {isBusiness && (
              <div className="rounded-xl border-2 border-violet-200 overflow-hidden hover:border-violet-400 transition-all relative">
                <div className="absolute -top-0.5 right-3 px-2 py-0.5 bg-violet-600 text-white text-[9px] font-bold rounded-b-md">
                  전문가용
                </div>
                <div className="bg-violet-50 px-4 py-2.5 border-b border-violet-200 flex items-center justify-between">
                  <div>
                    <span className="text-[13px] font-bold text-violet-700">PRO</span>
                    <span className="text-[11px] text-violet-500 ml-1.5">상담사·컨설턴트</span>
                  </div>
                  <span className="text-[14px] font-black text-violet-700">
                    49,000<span className="text-[10px] font-medium text-violet-400">원/월</span>
                  </span>
                </div>
                <div className="px-4 py-3 space-y-1.5">
                  <div className="flex items-center gap-2 text-[12px]">
                    <span className="text-violet-500">&#10003;</span>
                    <span className="text-slate-700 font-medium">공고AI 상담 — <strong>무제한</strong></span>
                  </div>
                  <div className="flex items-center gap-2 text-[12px]">
                    <span className="text-violet-500">&#10003;</span>
                    <span className="text-slate-700 font-medium">자유AI 상담 — <strong>무제한</strong></span>
                  </div>
                  <div className="flex items-center gap-2 text-[12px]">
                    <span className="text-violet-500">&#10003;</span>
                    <span className="text-slate-700 font-medium">고객 매칭 · 리포트</span>
                  </div>
                </div>
                <div className="px-4 pb-3">
                  <button
                    disabled={loading}
                    onClick={() => handleSubscribe("pro")}
                    className="w-full py-2.5 bg-violet-600 text-white rounded-lg text-[12px] font-bold hover:bg-violet-700 transition-all active:scale-[0.98] disabled:opacity-50"
                  >
                    {loading ? "처리 중..." : "1주일 무료 체험 시작"}
                  </button>
                  <p className="text-[9px] text-slate-400 text-center mt-1.5">카드 등록 후 1주일 무료, 이후 월 49,000원 자동결제</p>
                </div>
              </div>
            )}

            {/* both 표시 */}
            {isBusiness && (
              <p className="text-[10px] text-slate-400 text-center">
                * 사업자 유료 플랜에는 개인 지원금 기능이 포함됩니다
              </p>
            )}
          </div>

          {/* ── 친구 추천 ── */}
          <div className="mb-4 rounded-xl border border-amber-200 overflow-hidden">
            <div className="bg-amber-50 px-4 py-2 border-b border-amber-200">
              <p className="text-[11px] font-bold text-amber-700">친구에게 알려주면?</p>
            </div>
            <div className="px-4 py-3 space-y-1.5">
              <div className="flex items-center gap-2 text-[12px]">
                <span className="text-amber-500">&#9733;</span>
                <span className="text-slate-700 font-medium">
                  {isIndividual
                    ? "친구 추천 시 1개월간 상담 10회로 확장"
                    : "친구 추천 시 양쪽 LITE 1개월 무료"}
                </span>
              </div>
              <div className="flex items-center gap-2 text-[12px]">
                <span className="text-amber-500">&#9733;</span>
                <span className="text-slate-700 font-medium">최대 5명까지 적용 가능</span>
              </div>
            </div>
          </div>

          {/* 공유 버튼 */}
          <button
            onClick={handleShare}
            className="w-full py-3 rounded-xl font-bold text-sm shadow-lg transition-all active:scale-[0.98] mb-3 bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:from-indigo-700 hover:to-violet-700 shadow-indigo-200 flex items-center justify-center gap-2"
          >
            친구에게 공유하기
          </button>

          {/* 개인 사용자에게 사업자 플랜 안내 */}
          {isIndividual && (
            <p className="text-[10px] text-slate-400 text-center mb-2">
              사업자이신가요? 프로필 설정에서 사업자 등록하면 사업자 플랜을 이용할 수 있습니다
            </p>
          )}

          <button
            onClick={onClose}
            className="w-full py-2 text-slate-400 hover:text-slate-600 text-xs font-semibold transition-all text-center"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
