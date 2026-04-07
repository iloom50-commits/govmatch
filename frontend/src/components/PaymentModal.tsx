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
  const isBusiness = userType === "business" || userType === "both";
  const litePrice = isBusiness ? "4,900" : "2,900";
  const litePriceLabel = isBusiness ? "사업자" : "개인";

  const currentPlan = planStatus?.plan || "free";
  const isLite = ["lite", "lite_trial", "basic"].includes(currentPlan);
  const isPro = ["pro", "biz"].includes(currentPlan);

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

  // 체크/엑스 아이콘
  const Check = () => <span className="text-emerald-500 text-[11px] font-bold">&#10003;</span>;
  const Cross = () => <span className="text-slate-300 text-[11px]">—</span>;
  const Current = () => <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-700 text-[9px] font-bold rounded">현재</span>;

  // 비교표 행
  const Row = ({ label, free, lite, pro, bold }: { label: string; free: React.ReactNode; lite: React.ReactNode; pro: React.ReactNode; bold?: boolean }) => (
    <div className={`grid grid-cols-[1fr_64px_64px_64px] items-center py-2 border-b border-slate-50 ${bold ? "font-bold" : ""}`}>
      <span className="text-[11px] text-slate-600 pr-1">{label}</span>
      <span className="text-[11px] text-center text-slate-500">{free}</span>
      <span className="text-[11px] text-center text-indigo-700">{lite}</span>
      <span className="text-[11px] text-center text-violet-700">{pro}</span>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-white/60 overflow-hidden animate-in zoom-in-95 duration-300 max-h-[92vh] overflow-y-auto">
        <div className="relative z-10 p-5 sm:p-6">
          {/* 닫기 */}
          <button onClick={onClose} className="absolute top-3 right-3 w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400 text-lg z-20">✕</button>

          {/* Header */}
          <div className="text-center mb-4">
            <h2 className="text-[17px] font-bold text-slate-900 tracking-tight">플랜 선택</h2>
            <p className="text-slate-400 text-[11px] mt-1">내게 맞는 플랜을 선택하세요</p>
          </div>

          {/* ── 비교표 ── */}
          <div className="rounded-xl border border-slate-200 overflow-hidden mb-4">
            {/* 헤더 행 */}
            <div className="grid grid-cols-[1fr_64px_64px_64px] items-end bg-slate-50 px-4 py-3 border-b border-slate-200">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">기능</span>
              <div className="text-center">
                <p className="text-[12px] font-bold text-slate-500">FREE</p>
                <p className="text-[10px] text-slate-400">무료</p>
                {currentPlan === "free" && <Current />}
              </div>
              <div className="text-center">
                <p className="text-[12px] font-bold text-indigo-700">LITE</p>
                <p className="text-[10px] text-indigo-500">{litePrice}원</p>
                {isLite && <Current />}
              </div>
              <div className="text-center">
                <p className="text-[12px] font-bold text-violet-700">PRO</p>
                <p className="text-[10px] text-violet-500">49,000원</p>
                {isPro && <Current />}
              </div>
            </div>

            {/* 기능 행들 */}
            <div className="px-4">
              <Row label="공고 열람" free={<Check />} lite={<Check />} pro={<Check />} />
              <Row label="공고AI 상담" free="1회" lite={<strong>20회</strong>} pro={<strong>무제한</strong>} bold />
              <Row label="맞춤 공고 알림" free={<Cross />} lite={<Check />} pro={<Check />} />
              <Row label="마감 알림 (카톡/이메일)" free={<Cross />} lite={<Check />} pro={<Check />} />
              <Row label="공고 저장 · 일정관리" free={<Cross />} lite={<Check />} pro={<Check />} />
              <Row label="자유AI 상담" free={<Cross />} lite={<Cross />} pro={<strong>무제한</strong>} />
              <Row label="전문가 상담 에이전트" free={<Cross />} lite={<Cross />} pro={<Check />} />
            </div>

            {/* 결제 버튼 행 */}
            <div className="grid grid-cols-[1fr_64px_64px_64px] items-center px-4 py-3 bg-slate-50 border-t border-slate-200">
              <span />
              <span className="text-center">
                {currentPlan === "free" && <span className="text-[10px] text-slate-400 font-bold">이용 중</span>}
              </span>
              <span className="text-center">
                {!isLite && !isPro ? (
                  <button
                    onClick={() => handleSubscribe("lite")}
                    disabled={loading}
                    className="px-2 py-1.5 bg-indigo-600 text-white rounded-lg text-[10px] font-bold hover:bg-indigo-700 transition-all active:scale-95 disabled:opacity-50 w-full"
                  >
                    {loading ? "..." : "시작"}
                  </button>
                ) : isLite ? (
                  <span className="text-[10px] text-indigo-600 font-bold">이용 중</span>
                ) : null}
              </span>
              <span className="text-center">
                {!isPro ? (
                  <button
                    onClick={() => handleSubscribe("pro")}
                    disabled={loading}
                    className="px-2 py-1.5 bg-violet-600 text-white rounded-lg text-[10px] font-bold hover:bg-violet-700 transition-all active:scale-95 disabled:opacity-50 w-full"
                  >
                    {loading ? "..." : "시작"}
                  </button>
                ) : (
                  <span className="text-[10px] text-violet-600 font-bold">이용 중</span>
                )}
              </span>
            </div>
          </div>

          {/* 무료체험 안내 */}
          <p className="text-[10px] text-slate-400 text-center mb-4">
            {isLite ? "체험 종료 후에도 계속 이용하려면 유료 결제하기" :
             isPro ? "" :
             "LITE 7일 무료체험 · PRO 7일 무료체험 후 자동결제"}
          </p>

          {/* ── 친구 추천 ── */}
          <div className="rounded-xl border border-amber-200 overflow-hidden mb-4">
            <div className="px-4 py-3 bg-amber-50 flex items-center justify-between">
              <div>
                <p className="text-[12px] font-bold text-amber-800">친구 추천 시 LITE 1개월 무료</p>
                <p className="text-[10px] text-amber-600 mt-0.5">최대 5명까지 · 양쪽 모두 혜택</p>
              </div>
              <button
                onClick={async () => {
                  const url = "https://govmatch.kr";
                  const text = "정부지원금, 아직도 직접 찾고 계세요?\nAI가 내 조건에 맞는 지원금을 자동으로 찾아줍니다.";
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
          </div>

          {/* 닫기 */}
          <button onClick={onClose} className="w-full py-2.5 text-slate-400 text-[12px] font-medium hover:text-slate-600 transition-all">
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
