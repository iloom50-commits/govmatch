"use client";

import { useState } from "react";
import { useModalBack } from "@/hooks/useModalBack";

interface ProfileSettingsProps {
  profile: any;
  onSave: (data: any) => void;
  onClose: () => void;
  onLogout?: () => void;
  onOpenNotify?: () => void;
  planStatus?: any;
}

export default function ProfileSettings({ profile, onSave, onClose, onLogout, onOpenNotify, planStatus }: ProfileSettingsProps) {
  useModalBack(true, onClose);
  const [showPwChange, setShowPwChange] = useState(false);
  const [password, setPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");

  const plan = planStatus?.plan || "free";
  const label = planStatus?.label || "FREE";
  const daysLeft = planStatus?.days_left;

  const userTypeLabel: Record<string, string> = { individual: "개인", business: "사업자", both: "개인+사업자" };
  const isIndividual = profile?.user_type === "individual";

  const profileSummary = {
    type: userTypeLabel[profile?.user_type] || "미설정",
    region: profile?.address_city || "미설정",
    industry: profile?.industry_name || (profile?.industry_code && profile.industry_code !== "00000" ? profile.industry_code : "미설정"),
    age: profile?.age_range || "미설정",
    interests: profile?.interests || "미설정",
  };

  const hasProfile = isIndividual
    ? (profile?.age_range || profile?.address_city)
    : (profile?.industry_code && profile?.industry_code !== "00000");

  const joinDate = profile?.created_at
    ? new Date(profile.created_at).toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" })
    : profile?.plan_started_at
      ? new Date(profile.plan_started_at).toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" })
      : null;

  // 리스트 아이템 컴포넌트
  const Row = ({ label, value, accent, onClick }: { label: string; value: string; accent?: boolean; onClick?: () => void }) => (
    <button
      onClick={onClick}
      disabled={!onClick}
      className={`w-full flex items-center justify-between py-3.5 ${onClick ? "cursor-pointer active:bg-slate-50" : "cursor-default"} transition-colors`}
    >
      <span className="text-[13px] text-slate-500">{label}</span>
      <span className={`text-[13px] font-semibold ${accent ? "text-indigo-600" : "text-slate-900"} flex items-center gap-1`}>
        {value}
        {onClick && <span className="text-slate-300 text-[11px] ml-0.5">{">"}</span>}
      </span>
    </button>
  );

  const Divider = () => <div className="h-px bg-slate-100" />;

  return (
    <div className="fixed inset-0 z-[100] bg-slate-900/40 backdrop-blur-md animate-in fade-in duration-300 md:flex md:items-center md:justify-center md:p-6">
      <div className="bg-white w-full h-full md:h-auto md:max-w-md md:max-h-[95vh] md:rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-500 flex flex-col">
        {/* Header */}
        <div className="px-5 pt-4 pb-3 border-b border-slate-100 flex justify-between items-center flex-shrink-0 safe-top">
          <h2 className="text-[17px] font-bold text-slate-900">마이페이지</h2>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-slate-100 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-slate-400"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto min-h-0">

          {/* ── 내 정보 ── */}
          <div className="px-5 pt-5 pb-1">
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-1">내 정보</p>
          </div>
          <div className="px-5">
            <Row label="이메일" value={profile?.email || "미등록"} />
            <Divider />
            {joinDate && <><Row label="가입일" value={joinDate} /><Divider /></>}
            <Row label="사용자 유형" value={profileSummary.type} />
          </div>

          {/* 구분 */}
          <div className="h-2 bg-slate-50 mt-2" />

          {/* ── 구독 정보 ── */}
          <div className="px-5 pt-4 pb-1">
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-1">구독 정보</p>
          </div>
          <div className="px-5">
            <Row
              label="플랜"
              value={`${label}${daysLeft !== undefined && daysLeft !== null && plan !== "free" && plan !== "expired" ? ` (D-${daysLeft})` : ""}`}
              accent
            />
            <Divider />
            <Row
              label="공고AI 상담"
              value={(planStatus?.consult_limit || 0) >= 999 ? "무제한" : `${planStatus?.ai_used || 0} / ${planStatus?.consult_limit || 0}회`}
            />
            <Divider />
            <Row label="저장 · 알림" value={plan === "free" ? "불가" : "사용 가능"} />
          </div>

          {/* 구분 */}
          <div className="h-2 bg-slate-50 mt-2" />

          {/* ── 맞춤 설정 ── */}
          <div className="px-5 pt-4 pb-1">
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-1">맞춤 설정</p>
          </div>
          <div className="px-5">
            {hasProfile ? (
              <>
                <Row label="지역" value={profileSummary.region} onClick={() => { onClose(); onOpenNotify?.(); }} />
                <Divider />
                {isIndividual ? (
                  <>
                    <Row label="연령대" value={profileSummary.age} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    <Divider />
                    <Row label="관심분야" value={profileSummary.interests === "미설정" ? "미설정" : profileSummary.interests.split(",").slice(0, 3).join(", ")} onClick={() => { onClose(); onOpenNotify?.(); }} />
                  </>
                ) : (
                  <>
                    <Row label="업종" value={profileSummary.industry} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    <Divider />
                    {profile?.interests && (
                      <Row label="관심분야" value={profileSummary.interests.split(",").slice(0, 3).join(", ")} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    )}
                  </>
                )}
              </>
            ) : (
              <div className="py-4">
                <p className="text-[13px] text-slate-400 text-center mb-3">아직 맞춤 설정이 없어요</p>
                <button
                  onClick={() => { onClose(); onOpenNotify?.(); }}
                  className="w-full py-3 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all active:scale-[0.98]"
                >
                  맞춤 설정하기
                </button>
              </div>
            )}
          </div>

          {/* 구분 */}
          <div className="h-2 bg-slate-50 mt-2" />

          {/* ── 계정 관리 ── */}
          <div className="px-5 pt-4 pb-1">
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-1">계정 관리</p>
          </div>
          <div className="px-5 pb-4">
            {/* 비밀번호 변경 */}
            {!profile?.is_social && (
              <>
                {!showPwChange ? (
                  <Row label="비밀번호 변경" value="" onClick={() => setShowPwChange(true)} />
                ) : (
                  <div className="py-3">
                    <div className="flex gap-2">
                      <input
                        type="password"
                        placeholder="새 비밀번호 (6자 이상)"
                        className={`flex-1 px-3 py-2.5 border rounded-lg bg-white text-xs outline-none focus:ring-2 focus:ring-indigo-100 ${passwordError ? 'border-red-400' : 'border-slate-200'}`}
                        value={password}
                        onChange={(e) => { setPassword(e.target.value); setPasswordError(""); }}
                        autoFocus
                      />
                      <button
                        onClick={() => {
                          if (!password || password.length < 6) {
                            setPasswordError("6자 이상 입력해주세요.");
                            return;
                          }
                          onSave({ ...profile, password, address_city: profile.address_city });
                          setShowPwChange(false);
                          setPassword("");
                        }}
                        className="px-3 py-2.5 bg-slate-900 text-white rounded-lg text-xs font-bold hover:bg-slate-700 transition-all whitespace-nowrap"
                      >
                        변경
                      </button>
                      <button
                        onClick={() => { setShowPwChange(false); setPassword(""); setPasswordError(""); }}
                        className="px-2 py-2.5 text-slate-400 text-xs font-bold hover:text-slate-600 transition-all"
                      >
                        취소
                      </button>
                    </div>
                    {passwordError && <p className="text-[11px] text-red-500 mt-1">{passwordError}</p>}
                  </div>
                )}
                <Divider />
              </>
            )}

            {/* 소셜 로그인 */}
            {profile?.is_social && (
              <>
                <Row
                  label="로그인 방식"
                  value={profile.social_provider === "kakao" ? "카카오" : profile.social_provider === "naver" ? "네이버" : "Google"}
                />
                <Divider />
              </>
            )}

            <Row
              label="📋 내 상담 이력"
              value=""
              onClick={() => { onClose(); window.location.href = "/my/consults"; }}
            />
            <Divider />
            <Row label="고객문의" value="" onClick={() => { onClose(); window.location.href = "/support"; }} />
            <Divider />
            {onLogout && (
              <Row label="로그아웃" value="" onClick={onLogout} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
