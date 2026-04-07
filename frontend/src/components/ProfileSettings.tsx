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

  // 맞춤 설정 요약
  const profileSummary = {
    type: userTypeLabel[profile?.user_type] || "미설정",
    region: profile?.address_city || "미설정",
    industry: profile?.industry_name || (profile?.industry_code && profile.industry_code !== "00000" ? profile.industry_code : "미설정"),
    age: profile?.age_range || "미설정",
    interests: profile?.interests || "미설정",
  };
  const isIndividual = profile?.user_type === "individual";
  const hasProfile = isIndividual
    ? (profile?.age_range || profile?.address_city)
    : (profile?.industry_code && profile?.industry_code !== "00000");

  // 가입일 포맷
  const joinDate = profile?.created_at
    ? new Date(profile.created_at).toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" })
    : profile?.plan_started_at
      ? new Date(profile.plan_started_at).toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" })
      : null;

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
        <div className="p-6 space-y-4 overflow-y-auto flex-1 min-h-0">

          {/* ── 1. 가입 현황 ── */}
          <div className="space-y-2">
            <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest pl-1">가입 현황</p>
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-3">
              {/* 이메일 */}
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 bg-indigo-100 rounded-xl flex items-center justify-center flex-shrink-0">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-indigo-600"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-bold text-slate-900 truncate">{profile?.email || "이메일 미등록"}</p>
                  {joinDate && <p className="text-[11px] text-slate-400">{joinDate} 가입</p>}
                </div>
              </div>

              {/* 플랜 */}
              <div className="h-px bg-slate-200/60" />
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-black text-indigo-700">{label}</span>
                  {daysLeft !== undefined && daysLeft !== null && plan !== "free" && plan !== "expired" && (
                    <span className="px-1.5 py-0.5 bg-indigo-100 text-indigo-600 text-[10px] font-bold rounded-md">
                      {daysLeft > 0 ? `D-${daysLeft}` : "만료"}
                    </span>
                  )}
                </div>
                <span className="text-[11px] text-slate-400">{profileSummary.type}</span>
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
          </div>

          {/* ── 2. 맞춤 설정 현황 ── */}
          <div className="space-y-2">
            <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest pl-1">맞춤 설정</p>
            <div className="p-4 bg-white border border-slate-200 rounded-2xl">
              {hasProfile ? (
                <div className="space-y-2">
                  <div className="grid grid-cols-[60px_1fr] gap-y-2 text-[12px]">
                    <span className="text-slate-400">유형</span>
                    <span className="font-bold text-slate-700">{profileSummary.type}</span>
                    <span className="text-slate-400">지역</span>
                    <span className="font-bold text-slate-700">{profileSummary.region}</span>
                    {isIndividual ? (
                      <>
                        <span className="text-slate-400">연령대</span>
                        <span className="font-bold text-slate-700">{profileSummary.age}</span>
                        <span className="text-slate-400">관심분야</span>
                        <span className="font-bold text-slate-700 break-words">{profileSummary.interests}</span>
                      </>
                    ) : (
                      <>
                        <span className="text-slate-400">업종</span>
                        <span className="font-bold text-slate-700 break-words">{profileSummary.industry}</span>
                        {profile?.interests && (
                          <>
                            <span className="text-slate-400">관심분야</span>
                            <span className="font-bold text-slate-700 break-words">{profileSummary.interests}</span>
                          </>
                        )}
                      </>
                    )}
                  </div>
                  <button
                    onClick={() => { onClose(); onOpenNotify?.(); }}
                    className="w-full mt-2 py-2.5 bg-indigo-50 text-indigo-700 rounded-xl font-bold text-xs hover:bg-indigo-100 transition-all active:scale-[0.98] border border-indigo-100"
                  >
                    맞춤 설정 변경
                  </button>
                </div>
              ) : (
                <div className="text-center py-2">
                  <p className="text-[13px] text-slate-500 mb-3">아직 맞춤 설정이 없어요</p>
                  <button
                    onClick={() => { onClose(); onOpenNotify?.(); }}
                    className="w-full py-3 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all active:scale-[0.98]"
                  >
                    맞춤 설정하기
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* ── 3. 계정 관리 ── */}
          <div className="space-y-2">
            <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest pl-1">계정 관리</p>
            <div className="p-4 bg-white border border-slate-200 rounded-2xl space-y-3">
              {/* 비밀번호 변경 (이메일 가입자만) */}
              {!profile?.is_social && (
                <div className="space-y-2">
                  <label className="text-[12px] font-bold text-slate-600">비밀번호 변경</label>
                  <div className="flex gap-2">
                    <input
                      type="password"
                      placeholder="새 비밀번호 입력"
                      className={`flex-1 p-2.5 border rounded-xl bg-white text-xs font-medium outline-none focus:ring-2 focus:ring-indigo-100 ${passwordError ? 'border-red-400' : 'border-slate-200'}`}
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
                      className="px-4 py-2.5 bg-slate-900 text-white rounded-xl text-xs font-bold hover:bg-slate-700 transition-all active:scale-[0.98] whitespace-nowrap"
                    >
                      변경
                    </button>
                  </div>
                  {passwordError && <p className="text-[11px] font-bold text-red-500 pl-1">{passwordError}</p>}
                </div>
              )}

              {/* 소셜 로그인 표시 */}
              {profile?.is_social && (
                <div className="flex items-center gap-2 text-[12px] text-slate-500">
                  <span className="text-base">{profile.social_provider === "kakao" ? "💬" : profile.social_provider === "naver" ? "🟢" : "🔵"}</span>
                  <span>{profile.social_provider === "kakao" ? "카카오" : profile.social_provider === "naver" ? "네이버" : "Google"} 계정으로 로그인 중</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50/50 border-t border-slate-100 flex-shrink-0 safe-bottom">
          <div className="flex items-center justify-center gap-4">
            <a
              href="/support"
              className="text-slate-400 hover:text-indigo-600 text-[11px] font-bold transition-all"
            >
              고객문의
            </a>
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
