"use client";

import { useState, useEffect } from "react";
import { useToast } from "@/components/ui/Toast";
import { useModalBack } from "@/hooks/useModalBack";
import * as PortOne from "@portone/browser-sdk/v2";

const API = process.env.NEXT_PUBLIC_API_URL;
const STORE_ID = process.env.NEXT_PUBLIC_PORTONE_STORE_ID || "";
// 충전(카드 단건결제) 전용 채널키 — SmartDoc에서 카드 단건결제가 검증된 채널(동일 PortOne 스토어).
// 기존 NEXT_PUBLIC_PORTONE_CHANNEL_KEY(빌링 등 다른 용도일 수 있음)와 분리해, 검증된 단건결제 채널을 명시적으로 쓴다.
const CHARGE_CHANNEL_KEY = process.env.NEXT_PUBLIC_PORTONE_CHARGE_CHANNEL_KEY || "channel-key-c71e2358-2832-4bb8-a66e-f688c807e87c";
// 결제 승인(KCP 실채널) 연동 완료 전까지는 실제 결제창을 열지 않고 "준비 중" 안내만 띄운다.
// 연동 완료 시 Vercel 환경변수 NEXT_PUBLIC_CHARGE_READY=true 만 설정하면 코드 수정 없이 실결제가 열린다.
const CHARGE_READY = process.env.NEXT_PUBLIC_CHARGE_READY === "true";

interface Pack {
  krw: number;
  credits: number;
}

interface PaymentModalProps {
  /** /api/auth/me 의 plan_status (credits 포함). 현재 잔액 표시용. */
  planStatus?: { plan?: string; credits?: number } | null;
  userType?: string | null;
  /** 충전 성공 시 갱신된 잔액(credits)을 전달. 토큰 재발급은 없음. */
  onSuccess?: (credits: number) => void;
  onClose: () => void;
  /** 이전 구독 모달과의 호환용(현재는 미사용). */
  mode?: "lite" | "pro";
}

export default function PaymentModal({ planStatus, onSuccess, onClose }: PaymentModalProps) {
  const { toast } = useToast();
  useModalBack(true, onClose);
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  const [packs, setPacks] = useState<Pack[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [showComingSoon, setShowComingSoon] = useState(false);

  const currentCredits = typeof planStatus?.credits === "number" ? planStatus.credits : null;

  const getToken = () => typeof window !== "undefined" ? localStorage.getItem("auth_token") || "" : "";

  // JWT 페이로드에서 user_id(정수) 추출 — 백엔드 verify 가 payment.user_id 와 대조.
  const decodeJwt = (tok: string): { bn?: string; email?: string; user_id?: string | number } => {
    try {
      const part = tok.split(".")[1];
      if (!part) return {};
      const base = part.replace(/-/g, "+").replace(/_/g, "/").padEnd(part.length + ((4 - (part.length % 4)) % 4), "=");
      return JSON.parse(atob(base));
    } catch { return {}; }
  };

  // 충전팩 로드 (무인증)
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetch(`${API}/api/wallet/packs`);
        const data = await res.json();
        if (alive && Array.isArray(data.packs)) {
          setPacks(data.packs);
          setSelected(data.packs.length > 1 ? 1 : 0); // 기본: 두번째 팩(있으면)
        }
      } catch { /* 팩 로드 실패 시 빈 상태 */ }
    })();
    return () => { alive = false; };
  }, []);

  const handleCharge = async () => {
    if (selected === null || !packs[selected]) return;
    // 결제 승인 연동 완료 전 — 실제 결제창 대신 "준비 중" 안내를 띄운다.
    if (!CHARGE_READY) { setShowComingSoon(true); return; }
    const pack = packs[selected];
    const token = getToken();
    if (!token) { toast("로그인 후 이용해 주세요.", "info"); return; }
    const userId = decodeJwt(token).user_id;

    setLoading(true);
    try {
      // 모바일은 전체화면 리다이렉트, PC는 iframe. 모바일 리다이렉트 복귀는 /payment/charge-callback 에서 검증.
      const redirectUrl = typeof window !== "undefined"
        ? `${window.location.origin}/payment/charge-callback`
        : undefined;
      // SmartDoc 검증된 단건결제 이식 (@portone/browser-sdk/v2)
      const response = await PortOne.requestPayment({
        storeId: STORE_ID,
        channelKey: CHARGE_CHANNEL_KEY,
        // KCP V2 주문번호는 최대 40자. "gm-"(3) + uuid 32자 = 35자로 제한 내 유지.
        paymentId: "gm-" + crypto.randomUUID().replace(/-/g, ""),
        orderName: "지원금AI 크레딧 " + pack.credits.toLocaleString(),
        totalAmount: pack.krw,
        currency: "KRW",
        payMethod: "CARD",
        customData: JSON.stringify({ userId }),
        redirectUrl,
        windowType: { pc: "IFRAME", mobile: "REDIRECTION" },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      } as any);

      // 모바일 REDIRECTION은 여기서 반환되지 않고 페이지가 이동한다(콜백에서 처리).
      // 아래는 PC(IFRAME)에서 Promise로 결과를 받는 경로.
      if (response?.code) {
        toast(response.message || "결제가 취소되었습니다.", "info");
        setLoading(false);
        return;
      }

      const verifyRes = await fetch(`${API}/api/wallet/charge/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ payment_id: response?.paymentId }),
      });
      const data = await verifyRes.json();
      if (!verifyRes.ok || !data.ok) {
        toast(data.detail || "충전 검증에 실패했습니다. 잠시 후 다시 시도해 주세요.", "error");
        setLoading(false);
        return;
      }

      toast(data.duplicate ? "이미 처리된 결제입니다." : "충전 완료!", "success");
      onSuccess?.(typeof data.credits === "number" ? data.credits : 0);
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "결제 중 오류가 발생했습니다.", "error");
      setLoading(false);
    }
  };

  const selectedPack = selected !== null ? packs[selected] : null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-2 sm:p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* 결제 준비 중 안내 — KCP 실결제 연동 완료 전까지 표시 */}
      {showComingSoon && (
        <div className="absolute inset-0 z-[80] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/50" onClick={() => setShowComingSoon(false)} />
          <div className="relative w-full max-w-xs bg-white rounded-2xl shadow-2xl p-6 text-center animate-in zoom-in-95 duration-200">
            <div className="mx-auto mb-3 w-12 h-12 rounded-full bg-indigo-50 flex items-center justify-center text-2xl">🚧</div>
            <h3 className="text-[16px] font-bold text-slate-900 mb-1.5">결제 기능 준비 중이에요</h3>
            <p className="text-[12.5px] text-slate-500 leading-relaxed mb-5">
              카드 결제 연동을 마무리하고 있어요.<br />
              오픈되면 가입하신 연락처로 가장 먼저 알려드릴게요.<br />
              지금은 <strong className="text-indigo-600">가입 크레딧으로 상담·분석</strong>을 이용해 보세요!
            </p>
            <button
              onClick={() => setShowComingSoon(false)}
              className="w-full py-3 bg-indigo-600 text-white rounded-xl text-[13px] font-bold hover:bg-indigo-700 transition-all active:scale-[0.98]"
            >
              확인
            </button>
          </div>
        </div>
      )}

      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl border border-white/60 overflow-hidden animate-in zoom-in-95 duration-300 max-h-[95vh] overflow-y-auto">
        <div className="relative z-10 p-5 sm:p-6">
          {/* 닫기 */}
          <button onClick={onClose} className="absolute top-3 right-3 w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400 text-lg z-20">&#10005;</button>

          {/* Header */}
          <div className="text-center mb-5">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">크레딧 충전</h2>
            <p className="text-slate-400 text-[12px] mt-1">필요한 만큼 충전하고 사용한 만큼 차감돼요</p>
            {currentCredits !== null && (
              <div className="inline-flex items-center gap-1.5 mt-3 px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-100">
                <span className="text-[11px] text-slate-500">현재 잔액</span>
                <span className="text-[13px] font-bold text-indigo-700">{currentCredits.toLocaleString()} 크레딧</span>
              </div>
            )}
          </div>

          {/* 충전팩 카드 */}
          <div className="grid grid-cols-1 gap-2.5 mb-5">
            {packs.length === 0 ? (
              <div className="py-8 text-center text-[13px] text-slate-400">충전 상품을 불러오는 중...</div>
            ) : (
              packs.map((pack, i) => {
                const active = selected === i;
                return (
                  <button
                    key={pack.krw}
                    onClick={() => setSelected(i)}
                    className={`flex items-center justify-between w-full px-4 py-3.5 rounded-xl border-2 transition-all text-left ${
                      active
                        ? "border-indigo-500 bg-indigo-50/50"
                        : "border-slate-200 bg-white hover:border-slate-300"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className={`w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center ${active ? "border-indigo-500" : "border-slate-300"}`}>
                        {active && <span className="w-2 h-2 rounded-full bg-indigo-500" />}
                      </span>
                      <div>
                        <div className="text-[14px] font-bold text-slate-900">{pack.credits.toLocaleString()} 크레딧</div>
                      </div>
                    </div>
                    <div className="text-[15px] font-black text-slate-900">₩{pack.krw.toLocaleString()}</div>
                  </button>
                );
              })
            )}
          </div>

          {/* 충전 버튼 */}
          <button
            onClick={handleCharge}
            disabled={loading || selectedPack === null}
            className="w-full py-3 bg-indigo-600 text-white rounded-xl text-[14px] font-bold hover:bg-indigo-700 transition-all active:scale-[0.98] disabled:opacity-50"
          >
            {loading
              ? "결제창을 여는 중..."
              : selectedPack
                ? `₩${selectedPack.krw.toLocaleString()} 결제하기`
                : "충전할 상품을 선택하세요"}
          </button>

          <button onClick={onClose} className="w-full py-2 mt-2 text-slate-400 text-[12px] font-medium hover:text-slate-600 transition-all">
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
