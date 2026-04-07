"use client";

import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import * as PortOne from "@portone/browser-sdk/v2";

const API = process.env.NEXT_PUBLIC_API_URL;
const STORE_ID = process.env.NEXT_PUBLIC_PORTONE_STORE_ID || "";
const CHANNEL_KEY = process.env.NEXT_PUBLIC_PORTONE_CHANNEL_KEY || "";

interface PaymentModalProps {
  planStatus: { plan: string; days_left: number | null; label: string; consult_limit?: number; ai_used?: number } | null;
  userType?: string | null;
  onSuccess: (token: string, plan: any) => void;
  onClose: () => void;
}

export default function PaymentModal({ planStatus, userType, onSuccess, onClose }: PaymentModalProps) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"individual" | "business">(
    userType === "individual" ? "individual" : "business"
  );

  const currentPlan = planStatus?.plan || "free";
  const isLite = ["lite", "lite_trial", "basic"].includes(currentPlan);
  const isPro = ["pro", "biz"].includes(currentPlan);

  const litePrice = tab === "individual" ? "2,900" : "4,900";

  const getToken = () => typeof window !== "undefined" ? localStorage.getItem("auth_token") || "" : "";

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
      const billingKeyResponse = await PortOne.requestIssueBillingKey({
        storeId: STORE_ID,
        channelKey: CHANNEL_KEY,
        billingKeyMethod: "CARD",
      });
      const billingKey = (billingKeyResponse as any)?.billingKey;
      if (billingKeyResponse?.code === "USER_CANCEL") { toast("결제가 취소되었습니다.", "info"); setLoading(false); return; }
      if (!billingKey) { toast("카드 등록에 실패했습니다.", "error"); setLoading(false); return; }

      const res = await fetch(`${API}/api/plan/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ billing_key: billingKey, target_plan: targetPlan }),
      });
      const data = await res.json();
      if (!res.ok) { toast(data.detail || "구독 시작 실패", "error"); setLoading(false); return; }
      toast(data.message || "구독이 시작되었습니다!", "success");
      onSuccess(data.token, data.plan);
    } catch (err: unknown) {
      cleanupPortone();
      const msg = err instanceof Error ? err.message : "결제 중 오류가 발생했습니다.";
      toast(msg, "error");
    } finally {
      cleanupPortone();
      setLoading(false);
    }
  };

  const Check = () => <span className="text-emerald-500">&#10003;</span>;
  const Dash = () => <span className="text-slate-300">—</span>;

  const Feature = ({ children, available }: { children: React.ReactNode; available: boolean }) => (
    <li className={`flex items-start gap-2 text-[12px] leading-relaxed ${available ? "text-slate-700" : "text-slate-400"}`}>
      <span className="mt-0.5 flex-shrink-0">{available ? <Check /> : <Dash />}</span>
      <span>{children}</span>
    </li>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-3xl bg-white rounded-2xl shadow-2xl border border-white/60 overflow-hidden animate-in zoom-in-95 duration-300 max-h-[95vh] overflow-y-auto">
        <div className="relative z-10 p-4 sm:p-6">
          {/* 닫기 */}
          <button onClick={onClose} className="absolute top-3 right-3 w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400 text-lg z-20">&#10005;</button>

          {/* Header */}
          <div className="text-center mb-5">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">플랜 선택</h2>
            <p className="text-slate-400 text-[12px] mt-1">내게 맞는 플랜을 선택하세요</p>
          </div>

          {/* 개인/사업자 탭 */}
          <div className="flex justify-center gap-1 mb-5">
            <button
              onClick={() => setTab("individual")}
              className={`px-5 py-2 rounded-full text-[12px] font-bold transition-all border ${
                tab === "individual"
                  ? "bg-slate-900 text-white border-slate-900"
                  : "bg-white text-slate-500 border-slate-200 hover:border-slate-300"
              }`}
            >
              개인
            </button>
            <button
              onClick={() => setTab("business")}
              className={`px-5 py-2 rounded-full text-[12px] font-bold transition-all border ${
                tab === "business"
                  ? "bg-slate-900 text-white border-slate-900"
                  : "bg-white text-slate-500 border-slate-200 hover:border-slate-300"
              }`}
            >
              사업자
            </button>
          </div>

          {/* 3열 카드 */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">

            {/* FREE */}
            <div className={`rounded-xl border-2 p-4 flex flex-col ${currentPlan === "free" ? "border-slate-300 bg-slate-50" : "border-slate-200"}`}>
              <div className="mb-4">
                <h3 className="text-[15px] font-bold text-slate-700">Free</h3>
                <div className="mt-2">
                  <span className="text-2xl font-black text-slate-900">₩0</span>
                  <span className="text-[11px] text-slate-400 ml-1">/ 월</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">기본 공고 열람</p>
              </div>

              {currentPlan === "free" ? (
                <div className="py-2.5 bg-slate-200 text-slate-500 rounded-lg text-[12px] font-bold text-center mb-4">
                  현재 플랜
                </div>
              ) : (
                <div className="py-2.5 mb-4" />
              )}

              <ul className="space-y-2 flex-1">
                <Feature available>공고 열람</Feature>
                <Feature available>공고AI 상담 — <strong>1회</strong>/월</Feature>
                <Feature available={false}>맞춤 공고 알림</Feature>
                <Feature available={false}>마감 알림 (카톡/이메일)</Feature>
                <Feature available={false}>공고 저장 · 일정관리</Feature>
                <Feature available={false}>자유AI 상담</Feature>
                <Feature available={false}>전문가 상담 에이전트</Feature>
              </ul>
            </div>

            {/* LITE */}
            <div className={`rounded-xl border-2 p-4 flex flex-col relative ${isLite ? "border-indigo-400 bg-indigo-50/30" : "border-indigo-300 bg-white"}`}>
              {/* 추천 배지 */}
              {!isPro && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-indigo-600 text-white text-[10px] font-bold rounded-full">
                  추천
                </div>
              )}

              <div className="mb-4">
                <h3 className="text-[15px] font-bold text-indigo-700">Lite</h3>
                <div className="mt-2">
                  <span className="text-2xl font-black text-slate-900">₩{litePrice}</span>
                  <span className="text-[11px] text-slate-400 ml-1">/ 월</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">
                  {tab === "individual" ? "개인 맞춤 지원금" : "기업 맞춤 지원금"}
                </p>
              </div>

              {isLite ? (
                <div className="py-2.5 bg-indigo-100 text-indigo-700 rounded-lg text-[12px] font-bold text-center mb-4">
                  현재 플랜 {planStatus?.days_left != null && planStatus.days_left > 0 ? `(D-${planStatus.days_left})` : ""}
                </div>
              ) : isPro ? (
                <div className="py-2.5 mb-4" />
              ) : (
                <button
                  onClick={() => handleSubscribe("lite")}
                  disabled={loading}
                  className="w-full py-2.5 bg-indigo-600 text-white rounded-lg text-[12px] font-bold hover:bg-indigo-700 transition-all active:scale-[0.98] disabled:opacity-50 mb-4"
                >
                  {loading ? "처리 중..." : "Lite 시작하기"}
                </button>
              )}

              <ul className="space-y-2 flex-1">
                <Feature available>공고 열람</Feature>
                <Feature available>공고AI 상담 — <strong>20회</strong>/월</Feature>
                <Feature available>맞춤 공고 알림</Feature>
                <Feature available>마감 알림 (카톡/이메일)</Feature>
                <Feature available>공고 저장 · 일정관리</Feature>
                <Feature available={false}>자유AI 상담</Feature>
                <Feature available={false}>전문가 상담 에이전트</Feature>
              </ul>

              {!isLite && !isPro && (
                <p className="text-[10px] text-indigo-500 text-center mt-3 font-medium">7일 무료체험 후 자동결제</p>
              )}
            </div>

            {/* PRO */}
            <div className={`rounded-xl border-2 p-4 flex flex-col ${isPro ? "border-violet-400 bg-violet-50/30" : "border-slate-200"}`}>
              <div className="mb-4">
                <h3 className="text-[15px] font-bold text-violet-700">Pro</h3>
                <div className="mt-2">
                  <span className="text-2xl font-black text-slate-900">₩49,000</span>
                  <span className="text-[11px] text-slate-400 ml-1">/ 월</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">전문가 · 컨설턴트</p>
              </div>

              {isPro ? (
                <div className="py-2.5 bg-violet-100 text-violet-700 rounded-lg text-[12px] font-bold text-center mb-4">
                  현재 플랜
                </div>
              ) : (
                <button
                  onClick={() => handleSubscribe("pro")}
                  disabled={loading}
                  className="w-full py-2.5 bg-violet-600 text-white rounded-lg text-[12px] font-bold hover:bg-violet-700 transition-all active:scale-[0.98] disabled:opacity-50 mb-4"
                >
                  {loading ? "처리 중..." : "Pro 시작하기"}
                </button>
              )}

              <ul className="space-y-2 flex-1">
                <Feature available>공고 열람</Feature>
                <Feature available>공고AI 상담 — <strong>무제한</strong></Feature>
                <Feature available>맞춤 공고 알림</Feature>
                <Feature available>마감 알림 (카톡/이메일)</Feature>
                <Feature available>공고 저장 · 일정관리</Feature>
                <Feature available>자유AI 상담 — <strong>무제한</strong></Feature>
                <Feature available>전문가 상담 에이전트</Feature>
              </ul>

              {!isPro && (
                <p className="text-[10px] text-violet-500 text-center mt-3 font-medium">7일 무료체험 후 자동결제</p>
              )}
            </div>
          </div>

          {/* 친구 추천 */}
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 flex items-center justify-between mb-3">
            <div>
              <p className="text-[12px] font-bold text-amber-800">친구 추천 시 LITE 1개월 무료</p>
              <p className="text-[10px] text-amber-600 mt-0.5">최대 5명까지 · 양쪽 모두 혜택</p>
            </div>
            <button
              onClick={async () => {
                const url = "https://govmatch.kr";
                const text = "정부지원금, AI가 자동으로 찾아줍니다.";
                try {
                  if (navigator.share) await navigator.share({ title: "지원금AI", text, url });
                  else { await navigator.clipboard.writeText(`${text}\n${url}`); toast("링크 복사됨!", "success"); }
                } catch {
                  try { await navigator.clipboard.writeText(`${text}\n${url}`); toast("링크 복사됨!", "success"); } catch {}
                }
              }}
              className="px-3 py-1.5 bg-amber-600 text-white rounded-lg text-[11px] font-bold hover:bg-amber-700 transition-all active:scale-95 whitespace-nowrap"
            >
              공유하기
            </button>
          </div>

          {/* 닫기 */}
          <button onClick={onClose} className="w-full py-2 text-slate-400 text-[12px] font-medium hover:text-slate-600 transition-all">
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
