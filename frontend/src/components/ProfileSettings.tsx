"use client";

import { useState } from "react";

interface ProfileSettingsProps {
  profile: any;
  onSave: (data: any) => void;
  onClose: () => void;
  onLogout?: () => void;
  onOpenNotify?: () => void;
  planStatus?: any;
}

export default function ProfileSettings({ profile, onSave, onClose, onLogout, onOpenNotify, planStatus }: ProfileSettingsProps) {
  const [password, setPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");

  const plan = planStatus?.plan || "free";
  const label = planStatus?.label || "FREE";
  const daysLeft = planStatus?.days_left;

  const userTypeLabel: Record<string, string> = { individual: "개인", business: "사업자", both: "개인+사업자" };

  return (
    <div className="fixed inset-0 z-[100] bg-slate-900/40 backdrop-blur-md animate-in fade-in duration-300 md:flex md:items-center md:justify-center md:p-6">
      <div className="bg-white w-full h-full md:h-auto md:max-w-md md:max-h-[95vh] md:rounded-[2.5rem] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-500 flex flex-col">
        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-slate-100 flex justify-between items-center flex-shrink-0 safe-top">
          <h2 className="text-lg font-black text-slate-900 tracking-tight">마이페이지</h2>
          <button onClick={onClose} className="p-2 bg-slate-50 rounded-xl hover:bg-slate-100 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="text-slate-400"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5 overflow-y-auto flex-1 min-h-0">

          {/* 계정 이메일 */}
          <div className="flex items-center gap-3 p-4 bg-slate-50 border border-slate-200 rounded-2xl">
            <div className="w-10 h-10 bg-indigo-100 rounded-xl flex items-center justify-center flex-shrink-0">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-indigo-600"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-black text-slate-900 truncate">{profile?.email || "이메일 미등록"}</p>
              <p className="text-[11px] text-slate-400 font-medium">
                {userTypeLabel[profile?.user_type] || "미설정"} · {profile?.address_city || "지역 미설정"}
              </p>
            </div>
          </div>

          {/* 현재 플랜 */}
          <div className="p-4 bg-gradient-to-r from-indigo-50 to-violet-50 border border-indigo-100 rounded-2xl">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-black text-indigo-700">{label}</span>
              {daysLeft !== undefined && daysLeft !== null && (
                <span className="text-[11px] font-bold text-indigo-500">
                  {plan === "free" || plan === "expired" ? "" : daysLeft > 0 ? `D-${daysLeft}` : "만료"}
                </span>
              )}
            </div>
            <div className="text-[12px] text-slate-500 space-y-1">
              <div className="flex justify-between">
                <span>공고AI 상담</span>
                <span className="font-bold text-slate-700">
                  {planStatus?.consult_limit >= 999 ? "무제한" : `월 ${planStatus?.consult_limit || 0}회`}
                </span>
              </div>
              <div className="flex justify-between">
                <span>저장 · 알림</span>
                <span className="font-bold text-slate-700">
                  {plan === "free" ? "불가" : "사용 가능"}
                </span>
              </div>
            </div>
          </div>

          {/* 맞춤형 알림 설정 버튼 */}
          <button
            onClick={() => { onClose(); onOpenNotify?.(); }}
            className="w-full py-3.5 bg-indigo-600 text-white rounded-2xl font-black text-sm tracking-tight hover:bg-indigo-700 transition-all active:scale-[0.98] flex items-center justify-center gap-2"
          >
            <span className="text-base">🔔</span>
            맞춤형 알림 · 프로필 설정
          </button>

          {/* 비밀번호 변경 (이메일 가입자만) */}
          {!profile?.is_social && (
            <div className="space-y-2">
              <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest pl-1">비밀번호 변경</label>
              <div className="flex gap-2">
                <input
                  type="password"
                  placeholder="새 비밀번호 입력"
                  className={`flex-1 p-3 border rounded-xl bg-white text-xs font-medium outline-none focus:ring-2 focus:ring-indigo-100 ${passwordError ? 'border-red-400' : 'border-slate-200'}`}
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setPasswordError(""); }}
                />
                <button
                  onClick={() => {
                    if (!password || password.length < 6) {
                      setPasswordError("6자 이상 입력해주세요.");
                      return;
                    }
                    onSave({ ...profile, password, address_city: profile.address_city });
                  }}
                  className="px-4 py-3 bg-slate-900 text-white rounded-xl text-xs font-bold hover:bg-slate-700 transition-all active:scale-[0.98] whitespace-nowrap"
                >
                  변경
                </button>
              </div>
              {passwordError && <p className="text-[11px] font-bold text-red-500 pl-1">{passwordError}</p>}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50/50 border-t border-slate-100 flex-shrink-0 safe-bottom">
          <div className="flex items-center justify-center gap-4">
            <button
              onClick={async () => {
                if (!confirm("구독을 해지하시겠습니까?\n만료일까지는 계속 이용 가능하며, 이후 자동결제가 중지됩니다.")) return;
                try {
                  const token = localStorage.getItem("auth_token");
                  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/plan/cancel`, {
                    method: "POST",
                    headers: { Authorization: `Bearer ${token}` },
                  });
                  const data = await res.json();
                  alert(res.ok ? data.message : (data.detail || "해지 실패"));
                  if (res.ok) window.location.reload();
                } catch { alert("서버 오류"); }
              }}
              className="text-slate-400 hover:text-amber-600 text-[11px] font-bold transition-all"
            >
              구독 해지
            </button>
            <span className="text-slate-200">|</span>
            <button
              onClick={async () => {
                if (!confirm("환불을 요청하시겠습니까?\n무료체험 중이면 즉시 FREE로 전환되며, 유료 결제 건은 환불 처리됩니다.")) return;
                try {
                  const token = localStorage.getItem("auth_token");
                  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/plan/refund`, {
                    method: "POST",
                    headers: { Authorization: `Bearer ${token}` },
                  });
                  const data = await res.json();
                  alert(res.ok ? data.message : (data.detail || "환불 실패"));
                  if (res.ok) window.location.reload();
                } catch { alert("서버 오류"); }
              }}
              className="text-slate-400 hover:text-rose-500 text-[11px] font-bold transition-all"
            >
              환불 요청
            </button>
            {onLogout && (
              <>
                <span className="text-slate-200">|</span>
                <button
                  onClick={onLogout}
                  className="text-slate-400 hover:text-rose-500 text-[11px] font-bold transition-all"
                >
                  로그아웃
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
