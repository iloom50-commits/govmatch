"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "https://govmatch-production.up.railway.app";

/** 구독 관리(해지·환불) 공용 모달 — 마이페이지·PRO 계정칩에서 사용.
 *  해지: /api/plan/cancel (만료일까지 이용) · 환불: /api/plan/refund (공개 정책대로 실환불) */
export default function SubscriptionManageModal({ planStatus, onClose, onChanged }: {
  planStatus: any;
  onClose: () => void;
  onChanged?: () => void;   // 미지정 시 새로고침으로 플랜 상태 재로딩
}) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const label = planStatus?.label || (planStatus?.plan || "").toUpperCase() || "-";
  const daysLeft = planStatus?.days_left;

  const call = async (path: string, confirmText: string) => {
    if (typeof window !== "undefined" && !window.confirm(confirmText)) return;
    setBusy(true);
    setMsg("");
    try {
      const token = localStorage.getItem("auth_token") || "";
      const res = await fetch(`${API}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (res.ok) {
        setMsg(data.message || "처리되었습니다.");
        setTimeout(() => { if (onChanged) onChanged(); else window.location.reload(); }, 1800);
      } else {
        setMsg(data.detail || "처리에 실패했습니다.");
      }
    } catch {
      setMsg("서버 연결에 실패했습니다.");
    }
    setBusy(false);
  };

  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/50 px-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-sm p-6 space-y-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between">
          <h2 className="text-lg font-bold text-slate-900">구독 관리</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-2xl leading-none -mt-1">×</button>
        </div>

        <div className="rounded-xl bg-slate-50 border border-slate-100 px-4 py-3 text-sm text-slate-700">
          현재 플랜 <span className="font-bold text-violet-700">{label}</span>
          {typeof daysLeft === "number" && <> · 만료(다음 결제)까지 <b>D-{daysLeft}</b></>}
        </div>

        <div className="space-y-2">
          <button
            disabled={busy}
            onClick={() => call("/api/plan/cancel", "구독을 해지할까요?\n다음 결제일부터 결제되지 않으며, 만료일까지는 계속 이용할 수 있습니다.")}
            className="w-full py-2.5 rounded-lg border border-slate-200 text-sm font-bold text-slate-700 hover:bg-slate-50 transition-all disabled:opacity-50"
          >
            구독 해지 (만료일까지 이용)
          </button>
          <button
            disabled={busy}
            onClick={() => call("/api/plan/refund", "환불을 요청할까요?\n\n환불 정책: 결제 7일 이내·미사용 시 전액, 사용 시 이용일수 공제 후 일할 환불, 7일 경과 시 불가.\n환불 즉시 FREE 플랜으로 전환됩니다.")}
            className="w-full py-2.5 rounded-lg border border-rose-200 text-sm font-bold text-rose-600 hover:bg-rose-50 transition-all disabled:opacity-50"
          >
            환불 요청 (즉시 해지 + 환불)
          </button>
        </div>

        {busy && <p className="text-[12px] text-slate-400 text-center">처리 중...</p>}
        {msg && <p className="text-[12px] text-slate-700 text-center font-medium">{msg}</p>}

        <p className="text-[11px] text-slate-400 text-center">
          자세한 규정은 <a href="/refund" target="_blank" rel="noopener noreferrer" className="underline">환불 정책</a>을 확인하세요.
        </p>
      </div>
    </div>
  );
}
