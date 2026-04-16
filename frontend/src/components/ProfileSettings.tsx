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
  const userType = profile?.user_type || "business";
  const showIndividual = userType === "individual" || userType === "both";
  const showBusiness = userType === "business" || userType === "both";

  // address_city는 "전국,부산" 형태. 첫 번째 "전국"을 제외한 나머지가 실제 선택 지역.
  const parseHomeCity = (raw: any): string => {
    if (!raw) return "";
    const parts = String(raw).split(",").map(s => s.trim()).filter(Boolean);
    return parts.filter(p => p !== "전국")[0] || "";
  };
  const homeCity = parseHomeCity(profile?.address_city);
  const interestRegions = profile?.interest_regions
    ? String(profile.interest_regions).split(",").map((s: string) => s.trim()).filter(Boolean)
    : [];

  const formatList = (raw: any, limit = 3): string => {
    if (!raw) return "미설정";
    const arr = String(raw).split(",").map(s => s.trim()).filter(Boolean);
    if (arr.length === 0) return "미설정";
    return arr.slice(0, limit).join(", ") + (arr.length > limit ? ` 외 ${arr.length - limit}` : "");
  };

  // 소득 화면표시용 역매핑
  const INCOME_LABEL: Record<string, string> = {
    "기초생활": "월 100만원 이하",
    "차상위": "월 100~200만원",
    "중위50%이하": "월 200~300만원",
    "중위75%이하": "월 300~400만원",
    "중위100%이하": "월 400~500만원",
    "해당없음": "월 500만원 이상",
  };

  const profileSummary = {
    type: userTypeLabel[userType] || "미설정",
    homeCity: homeCity || "미설정",
    interestRegions: interestRegions.length > 0 ? interestRegions.join(", ") : "미설정",
    gender: profile?.gender || "미설정",
    age: profile?.age_range || "미설정",
    income: profile?.income_level ? (INCOME_LABEL[profile.income_level] || profile.income_level) : "미설정",
    family: profile?.family_type || "미설정",
    employment: profile?.employment_status || "미설정",
    revenue: profile?.revenue_bracket || "미설정",
    employees: profile?.employee_count_bracket || "미설정",
    foundedDate: profile?.is_pre_founder ? "예비창업자" : (profile?.founded_date || "미설정"),
    certifications: formatList(profile?.certifications),
    interests: formatList(profile?.interests),
  };

  // 저장된 프로필 필드가 하나라도 있으면 true
  const hasProfile = !!(
    homeCity ||
    profile?.age_range ||
    profile?.gender ||
    profile?.income_level ||
    profile?.family_type ||
    profile?.employment_status ||
    profile?.revenue_bracket ||
    profile?.employee_count_bracket ||
    profile?.founded_date ||
    profile?.is_pre_founder ||
    (profile?.certifications && String(profile.certifications).length > 0) ||
    (profile?.interests && String(profile.interests).length > 0)
  );

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
                {showIndividual && (
                  <div className={showBusiness ? "pb-2" : ""}>
                    {showBusiness && (
                      <p className="text-[11px] font-bold text-indigo-500 mt-1 mb-0.5">개인</p>
                    )}
                    <Row label="거주 지역" value={profileSummary.homeCity} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    <Divider />
                    <Row label="관심 지역" value={profileSummary.interestRegions} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    <Divider />
                    <Row label="성별" value={profileSummary.gender} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    <Divider />
                    <Row label="연령대" value={profileSummary.age} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    <Divider />
                    <Row label="소득수준" value={profileSummary.income} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    <Divider />
                    <Row label="가구유형" value={profileSummary.family} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    <Divider />
                    <Row label="취업상태" value={profileSummary.employment} onClick={() => { onClose(); onOpenNotify?.(); }} />
                  </div>
                )}
                {showIndividual && showBusiness && (
                  <div className="h-2 bg-slate-50 -mx-5 my-2" />
                )}
                {showBusiness && (
                  <div className={showIndividual ? "pt-1" : ""}>
                    {showIndividual && (
                      <p className="text-[11px] font-bold text-indigo-500 mt-1 mb-0.5">기업</p>
                    )}
                    <Row label="사업장 소재지" value={profileSummary.homeCity} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    <Divider />
                    <Row label="관심 지역" value={profileSummary.interestRegions} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    <Divider />
                    <Row label="매출 규모" value={profileSummary.revenue} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    <Divider />
                    <Row label="직원 수" value={profileSummary.employees} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    <Divider />
                    <Row label="설립일" value={profileSummary.foundedDate} onClick={() => { onClose(); onOpenNotify?.(); }} />
                    <Divider />
                    <Row label="보유 인증" value={profileSummary.certifications} onClick={() => { onClose(); onOpenNotify?.(); }} />
                  </div>
                )}
                <Divider />
                <Row label="관심분야" value={profileSummary.interests} onClick={() => { onClose(); onOpenNotify?.(); }} />
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
