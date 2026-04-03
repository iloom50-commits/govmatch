"use client";

import { useState, useEffect } from "react";
import { useToast } from "@/components/ui/Toast";

const API = process.env.NEXT_PUBLIC_API_URL;

// ── 선택지 상수 ──
const CITIES = ["전국", "서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"];
const REVENUE = ["1억 미만", "1억~5억", "5억~10억", "10억~50억", "50억 이상"];
const EMPLOYEE = ["5인 미만", "5인~10인", "10인~30인", "30인~50인", "50인 이상"];

const GENDERS = ["남성", "여성"];
const AGE_RANGES = ["20대", "30대", "40대", "50대", "60대 이상"];
const INCOME_LEVELS = ["기초생활", "차상위", "중위50%이하", "중위75%이하", "중위100%이하", "해당없음"];
const FAMILY_TYPES = ["1인가구", "다자녀", "한부모", "신혼부부", "다문화", "일반"];
const EMPLOYMENT_STATUSES = ["재직자", "구직자", "자영업", "프리랜서", "학생", "해당없음"];

const CERTIFICATIONS = ["벤처기업", "이노비즈", "메인비즈", "여성기업", "장애인기업", "사회적기업", "없음"];

// 관심분야는 사용자 텍스트 입력 → 백엔드 AI 매핑으로 대체

// 맞춤 키워드 추천 태그
const BIZ_KEYWORDS = ["전문가 모집", "주관기관 모집", "운영기관 모집", "컨설턴트 모집", "평가위원", "심사위원", "수행기관", "위탁운영", "사업설명회", "데모데이", "IR", "멘토링", "액셀러레이팅", "해외전시회", "바우처", "인증지원"];
const IND_KEYWORDS = ["전세자금", "월세지원", "청년수당", "취업성공패키지", "내일배움카드", "국민취업지원", "긴급복지", "기초연금", "장애수당", "보육료", "산후조리", "문화바우처", "체육바우처", "교육바우처", "의료비지원", "주거급여"];

type UserType = "individual" | "business" | "both";

// ── 푸시 구독 유틸 ──
async function subscribePush(bn: string): Promise<boolean> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return false;
  try {
    const reg = await navigator.serviceWorker.register("/sw.js");
    const existing = await reg.pushManager.getSubscription();
    if (existing) return true;
    const res = await fetch(`${API}/api/push/vapid-key`);
    const { publicKey } = await res.json();
    if (!publicKey) return false;
    const perm = await Notification.requestPermission();
    if (perm !== "granted") return false;
    const padding = "=".repeat((4 - (publicKey.length % 4)) % 4);
    const base64 = (publicKey + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(base64);
    const applicationServerKey = Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
    const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey });
    const subJson = sub.toJSON();
    await fetch(`${API}/api/push/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business_number: bn, endpoint: subJson.endpoint, keys: subJson.keys }),
    });
    return true;
  } catch { return false; }
}
async function unsubscribePush(): Promise<boolean> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return false;
  try {
    const reg = await navigator.serviceWorker.getRegistration("/sw.js");
    if (!reg) return true;
    const existing = await reg.pushManager.getSubscription();
    if (!existing) return true;
    const endpoint = existing.endpoint;
    await existing.unsubscribe();
    await fetch(`${API}/api/push/unsubscribe`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ endpoint }) });
    return true;
  } catch { return false; }
}
async function isPushSubscribed(): Promise<boolean> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return false;
  try {
    const reg = await navigator.serviceWorker.getRegistration("/sw.js");
    return !!(reg && await reg.pushManager.getSubscription());
  } catch { return false; }
}

// ── 동적 스텝 계산 ──
function getSteps(userType: UserType) {
  // 공통: 유형 → 지역 → ... → 관심분야+키워드+알림
  const steps: { id: string; title: string; subtitle: string }[] = [
    { id: "type", title: "어떤 지원금을 찾고 계세요?", subtitle: "맞춤 공고를 찾아드릴게요" },
    { id: "region", title: "지역을 선택해주세요", subtitle: "여러 지역을 선택할 수 있어요" },
  ];
  if (userType === "individual" || userType === "both") {
    steps.push({ id: "individual", title: "개인 정보를 알려주세요", subtitle: "맞춤 복지 매칭에 활용돼요" });
  }
  if (userType === "business" || userType === "both") {
    steps.push({ id: "business", title: "기업 정보를 알려주세요", subtitle: "정확한 지원금 매칭에 활용돼요" });
  }
  steps.push({ id: "interests", title: "관심분야를 선택해주세요", subtitle: "키워드를 골라주시면 AI가 매칭해요" });
  return steps;
}

// ── 사각 칩 (지역/매출/직원 등) ──
function ChipRect({ label, selected, onClick }: { label: string; selected: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={`px-4 py-2 rounded-lg text-sm font-semibold border transition-all active:scale-95 ${
      selected ? "bg-indigo-600 text-white border-indigo-600 shadow-sm" : "bg-white text-slate-500 border-slate-200 hover:border-indigo-300"
    }`}>
      {label}
    </button>
  );
}

export default function NotificationModal({
  isOpen, onClose, businessNumber, onSave, profile
}: {
  isOpen: boolean;
  onClose: () => void;
  businessNumber: string;
  onSave: (data: any) => void;
  profile?: any;
}) {
  const { toast } = useToast();
  const [step, setStep] = useState(0);

  // 사용자 타입
  const [userType, setUserType] = useState<UserType>(profile?.user_type || "individual");

  // 공통
  const [addressCities, setAddressCities] = useState<string[]>([]);

  // 개인 필드
  const [gender, setGender] = useState("");
  const [ageRange, setAgeRange] = useState("");
  const [incomeLevel, setIncomeLevel] = useState("");
  const [familyType, setFamilyType] = useState("");
  const [employmentStatus, setEmploymentStatus] = useState("");

  // 기업 필드
  const [revenueBracket, setRevenueBracket] = useState("");
  const [employeeBracket, setEmployeeBracket] = useState("");
  const [foundedDate, setFoundedDate] = useState("");
  const [isPreFounder, setIsPreFounder] = useState(false);
  const [certifications, setCertifications] = useState<string[]>([]);

  // 관심분야 + 맞춤 키워드
  const [interests, setInterests] = useState<string[]>([]);
  const [customKeywords, setCustomKeywords] = useState<string[]>([]);

  // 알림 채널
  const [email, setEmail] = useState("");
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushLoading, setPushLoading] = useState(false);
  const [kakaoEnabled, setKakaoEnabled] = useState(false);
  const [loading, setLoading] = useState(false);

  const isKakaoUser = profile?.social_provider === "kakao";
  const steps = getSteps(userType);
  const totalSteps = steps.length;
  const currentStep = steps[step] || steps[0];

  useEffect(() => {
    if (!isOpen || !businessNumber) return;
    setStep(0);
    fetch(`${API}/api/notification-settings/${businessNumber}`)
      .then(r => r.json())
      .then(d => {
        if (d.status === "SUCCESS" && d.data) {
          if (d.data.email) setEmail(d.data.email);
          if (d.data.kakao_enabled) setKakaoEnabled(true);
        }
      })
      .catch(() => {});
    isPushSubscribed().then(setPushEnabled);

    if (profile) {
      setUserType(profile.user_type || "individual");
      setAddressCities(profile.address_city ? String(profile.address_city).split(",").filter(Boolean) : []);
      setGender(profile.gender || "");
      setAgeRange(profile.age_range || "");
      setIncomeLevel(profile.income_level || "");
      setFamilyType(profile.family_type || "");
      setEmploymentStatus(profile.employment_status || "");
      setRevenueBracket(profile.revenue_bracket || "");
      setEmployeeBracket(profile.employee_count_bracket || "");
      setFoundedDate(profile.founded_date || "");
      setIsPreFounder(profile.is_pre_founder || false);
      setCertifications(profile.certifications ? String(profile.certifications).split(",").filter(Boolean) : []);
      setInterests(profile.interests ? String(profile.interests).split(",").filter(Boolean) : []);
      setCustomKeywords(profile.custom_keywords ? String(profile.custom_keywords).split(",").filter(Boolean) : []);
      if (!email && profile.email && !profile.email.endsWith(".local")) {
        setEmail(profile.email);
      }
      if (isKakaoUser) setKakaoEnabled(true);
    }
  }, [isOpen, businessNumber, profile]);

  // ── 토글 헬퍼 ──
  const toggleCity = (city: string) => {
    if (city === "전국") {
      setAddressCities(prev => prev.includes("전국") ? [] : ["전국"]);
    } else {
      setAddressCities(prev => {
        const w = prev.filter(c => c !== "전국");
        return w.includes(city) ? w.filter(c => c !== city) : [...w, city];
      });
    }
  };
  // toggleInterest 제거 — 자유 텍스트 입력으로 대체
  const toggleKeyword = (kw: string) => setCustomKeywords(prev => prev.includes(kw) ? prev.filter(k => k !== kw) : [...prev, kw]);
  const toggleCert = (c: string) => {
    if (c === "없음") { setCertifications(["없음"]); return; }
    setCertifications(prev => {
      const w = prev.filter(x => x !== "없음");
      return w.includes(c) ? w.filter(x => x !== c) : [...w, c];
    });
  };

  const handlePushToggle = async (enabled: boolean) => {
    setPushLoading(true);
    try {
      if (enabled) {
        const ok = await subscribePush(businessNumber);
        setPushEnabled(ok);
        if (!ok) toast("푸시 권한이 거부되었습니다.", "error");
      } else {
        await unsubscribePush();
        setPushEnabled(false);
      }
    } finally { setPushLoading(false); }
  };

  // ── 네비게이션 ──
  const goNext = () => { if (step < totalSteps - 1) setStep(s => s + 1); };
  const goBack = () => { if (step > 0) setStep(s => s - 1); };

  // 유형 변경 시 스텝 리셋
  const handleTypeChange = (val: UserType) => {
    setUserType(val);
    setInterests([]);
    setCustomKeywords([]);
  };

  // ── 저장 ──
  const handleSave = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("auth_token") || "";
      await fetch(`${API}/api/profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          user_type: userType,
          address_city: addressCities.join(","),
          // 개인
          gender: (userType !== "business") ? gender : undefined,
          age_range: (userType !== "business") ? ageRange : undefined,
          income_level: (userType !== "business") ? incomeLevel : undefined,
          family_type: (userType !== "business") ? familyType : undefined,
          employment_status: (userType !== "business") ? employmentStatus : undefined,
          // 기업
          revenue_bracket: (userType !== "individual") ? revenueBracket : undefined,
          employee_count_bracket: (userType !== "individual") ? employeeBracket : undefined,
          founded_date: (userType !== "individual" && !isPreFounder) ? foundedDate : undefined,
          is_pre_founder: (userType !== "individual") ? isPreFounder : undefined,
          certifications: (userType !== "individual") ? certifications.join(",") : undefined,
          // 관심
          interests: interests.join(","),
          custom_keywords: customKeywords.join(","),
        }),
      });
      await fetch(`${API}/api/notification-settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_number: businessNumber,
          email,
          channel: "BOTH",
          is_active: 1,
          kakao_enabled: isKakaoUser && kakaoEnabled ? 1 : 0,
        }),
      });
      toast("맞춤 알림이 설정되었습니다! 평일 오전 9시에 맞춤 공고를 알려드려요.", "success");
      onSave({ userType, addressCities, interests, customKeywords });
      onClose();
    } catch {
      toast("저장 중 오류가 발생했습니다.", "error");
    } finally { setLoading(false); }
  };

  // ── canNext ──
  const canNext = (): boolean => {
    switch (currentStep.id) {
      case "type": return !!userType;
      case "region": return addressCities.length > 0;
      case "individual": return true; // 선택사항
      case "business": return true;
      case "interests": return interests.length > 0;
      default: return false;
    }
  };

  if (!isOpen) return null;

  const isInd = userType === "individual";
  const isBoth = userType === "both";
  const progressPct = ((step + 1) / totalSteps) * 100;
  const isLastStep = step === totalSteps - 1;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-3">
      <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300 max-h-[92vh] flex flex-col">
        {/* 진행률 바 */}
        <div className="h-1.5 bg-slate-100 shrink-0">
          <div className="h-full bg-indigo-600 transition-all duration-500 ease-out rounded-r-full" style={{ width: `${progressPct}%` }} />
        </div>

        <div className="p-5 sm:p-7 overflow-y-auto flex-1">
          {/* 헤더 */}
          <div className="flex items-center justify-between mb-5 sm:mb-7">
            <div className="flex items-center gap-3">
              {step > 0 ? (
                <button onClick={goBack} className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400 transition-colors">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
                </button>
              ) : (
                <div className="w-10" />
              )}
              <div>
                <p className="text-xs font-bold text-indigo-500 tracking-wider">{step + 1} / {totalSteps}</p>
                <h2 className="text-xl sm:text-2xl font-black text-slate-900 leading-tight">{currentStep.title}</h2>
                <p className="text-xs sm:text-sm text-slate-400 mt-0.5">{currentStep.subtitle}</p>
              </div>
            </div>
            <button onClick={onClose} className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400 text-xl shrink-0">✕</button>
          </div>

          {/* ── 스텝 콘텐츠 ── */}
          <div className="min-h-[220px]">

            {/* ===== Step: 사용자 유형 ===== */}
            {currentStep.id === "type" && (
              <div className="space-y-3 animate-in fade-in slide-in-from-right-4 duration-300">
                {([["individual", "개인 복지", "취업·주거·교육·출산 등 개인 지원금"], ["business", "기업 지원", "R&D·창업·수출·고용 등 기업 지원금"], ["both", "둘 다", "개인 복지 + 기업 지원 모두 받기"]] as [UserType, string, string][]).map(([val, label, desc]) => (
                  <button
                    key={val}
                    onClick={() => handleTypeChange(val)}
                    className={`w-full p-5 rounded-xl border-2 text-left transition-all active:scale-[0.98] ${
                      userType === val ? "border-indigo-600 bg-indigo-50" : "border-slate-200 bg-white hover:border-slate-300"
                    }`}
                  >
                    <p className={`text-base font-bold ${userType === val ? "text-indigo-700" : "text-slate-700"}`}>{label}</p>
                    <p className={`text-sm mt-1 ${userType === val ? "text-indigo-500" : "text-slate-400"}`}>{desc}</p>
                  </button>
                ))}
              </div>
            )}

            {/* ===== Step: 지역 ===== */}
            {currentStep.id === "region" && (
              <div className="animate-in fade-in slide-in-from-right-4 duration-300">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm font-bold text-slate-600">{isInd ? "거주 지역" : "소재지"} <span className="font-normal text-slate-400">(복수 선택)</span></p>
                  {addressCities.length > 0 && (
                    <p className="text-xs text-indigo-500 font-semibold">{addressCities.includes("전국") ? "전국" : `${addressCities.length}개 선택`}</p>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {CITIES.map(city => <ChipRect key={city} label={city} selected={addressCities.includes(city)} onClick={() => toggleCity(city)} />)}
                </div>
              </div>
            )}

            {/* ===== Step: 개인 정보 ===== */}
            {currentStep.id === "individual" && (
              <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                {/* 성별 */}
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">성별</p>
                  <div className="flex gap-2">
                    {GENDERS.map(g => <ChipRect key={g} label={g} selected={gender === g} onClick={() => setGender(gender === g ? "" : g)} />)}
                  </div>
                </div>
                {/* 연령대 */}
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">연령대</p>
                  <div className="flex flex-wrap gap-2">
                    {AGE_RANGES.map(a => <ChipRect key={a} label={a} selected={ageRange === a} onClick={() => setAgeRange(ageRange === a ? "" : a)} />)}
                  </div>
                </div>
                {/* 소득수준 */}
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">소득수준</p>
                  <div className="flex flex-wrap gap-2">
                    {INCOME_LEVELS.map(l => <ChipRect key={l} label={l} selected={incomeLevel === l} onClick={() => setIncomeLevel(incomeLevel === l ? "" : l)} />)}
                  </div>
                </div>
                {/* 가구유형 */}
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">가구유형</p>
                  <div className="flex flex-wrap gap-2">
                    {FAMILY_TYPES.map(f => <ChipRect key={f} label={f} selected={familyType === f} onClick={() => setFamilyType(familyType === f ? "" : f)} />)}
                  </div>
                </div>
                {/* 취업상태 */}
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">취업상태</p>
                  <div className="flex flex-wrap gap-2">
                    {EMPLOYMENT_STATUSES.map(s => <ChipRect key={s} label={s} selected={employmentStatus === s} onClick={() => setEmploymentStatus(employmentStatus === s ? "" : s)} />)}
                  </div>
                </div>
                <p className="text-xs text-slate-400">선택하지 않은 항목은 전체 대상으로 매칭됩니다</p>
              </div>
            )}

            {/* ===== Step: 기업 정보 ===== */}
            {currentStep.id === "business" && (
              <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                {/* 매출 */}
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">매출 규모</p>
                  <div className="flex flex-wrap gap-2">
                    {REVENUE.map(r => <ChipRect key={r} label={r} selected={revenueBracket === r} onClick={() => setRevenueBracket(revenueBracket === r ? "" : r)} />)}
                  </div>
                </div>
                {/* 직원수 */}
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">직원 수</p>
                  <div className="flex flex-wrap gap-2">
                    {EMPLOYEE.map(e => <ChipRect key={e} label={e} selected={employeeBracket === e} onClick={() => setEmployeeBracket(employeeBracket === e ? "" : e)} />)}
                  </div>
                </div>
                {/* 설립일 */}
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">설립일</p>
                  {!isPreFounder && (
                    <input
                      type="date"
                      value={foundedDate}
                      onChange={e => setFoundedDate(e.target.value)}
                      className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-200"
                    />
                  )}
                  <label className="flex items-center gap-2 mt-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isPreFounder}
                      onChange={e => { setIsPreFounder(e.target.checked); if (e.target.checked) setFoundedDate(""); }}
                      className="w-5 h-5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-200"
                    />
                    <span className="text-sm text-slate-600">아직 창업 전입니다 (예비창업자)</span>
                  </label>
                </div>
                {/* 보유인증 */}
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">보유 인증 <span className="font-normal text-slate-400">(복수 선택)</span></p>
                  <div className="flex flex-wrap gap-2">
                    {CERTIFICATIONS.map(c => <ChipRect key={c} label={c} selected={certifications.includes(c)} onClick={() => toggleCert(c)} />)}
                  </div>
                </div>
              </div>
            )}

            {/* ===== Step: 관심분야 + 맞춤키워드 + 알림 ===== */}
            {currentStep.id === "interests" && (
              <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                {/* 관심분야 — 자유 텍스트 입력 */}
                <div>
                  <p className="text-sm font-bold text-slate-700 mb-2">관심분야를 입력하세요</p>
                  <input
                    type="text"
                    value={interests.join(", ")}
                    onChange={(e) => {
                      const parsed = e.target.value.split(",").map(s => s.trim()).filter(Boolean);
                      // interests state 직접 업데이트
                      setInterests(parsed);
                    }}
                    placeholder={isBoth ? "예: AI 기술개발, 청년 취업, 수출" : isInd ? "예: 취업, 주거, 청년 지원" : "예: AI 기술개발, 해외진출, 보조금"}
                    className="w-full px-3 py-2.5 bg-white border border-slate-200 rounded-xl text-sm text-slate-700 placeholder-slate-400 outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300 transition-all"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">쉼표로 구분하여 자유롭게 입력하세요</p>
                </div>

                {/* 맞춤 키워드 */}
                <div className="border-t border-slate-100 pt-4">
                  <p className="text-sm font-bold text-slate-600 mb-2">맞춤 키워드 <span className="font-normal text-slate-400">(선택)</span></p>
                  <div className="flex flex-wrap gap-2">
                    {(isBoth ? [...IND_KEYWORDS, ...BIZ_KEYWORDS] : isInd ? IND_KEYWORDS : BIZ_KEYWORDS).map(kw => (
                      <button
                        key={kw}
                        onClick={() => toggleKeyword(kw)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all active:scale-95 ${
                          customKeywords.includes(kw) ? "bg-emerald-600 text-white border-emerald-600" : "bg-white text-slate-400 border-slate-200 hover:border-emerald-300"
                        }`}
                      >{kw}</button>
                    ))}
                  </div>
                  {customKeywords.length > 0 && <p className="text-xs text-emerald-500 font-semibold mt-1">{customKeywords.length}개 선택됨</p>}
                </div>

                {/* 알림 on/off */}
                <div className="border-t border-slate-100 pt-4 space-y-3">
                  <p className="text-sm font-bold text-slate-600">알림 받기</p>

                  {/* 이메일 */}
                  <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                    <div className="flex items-center gap-2">
                      <span className="text-base">📧</span>
                      <span className="text-sm font-semibold text-slate-700">이메일</span>
                      {profile?.email && !profile.email.endsWith(".local") && email === profile.email && (
                        <span className="text-[10px] text-green-600 bg-green-50 px-1.5 py-0.5 rounded-full font-semibold">자동</span>
                      )}
                    </div>
                    <input
                      type="email" value={email} onChange={e => setEmail(e.target.value)}
                      placeholder="email@example.com"
                      className="w-48 px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-200 text-right"
                    />
                  </div>

                  {/* 푸시 */}
                  <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                    <div className="flex items-center gap-2">
                      <span className="text-base">🔔</span>
                      <span className="text-sm font-semibold text-slate-700">브라우저 푸시</span>
                    </div>
                    <button
                      disabled={pushLoading}
                      onClick={() => handlePushToggle(!pushEnabled)}
                      className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${pushEnabled ? "bg-indigo-600" : "bg-slate-300"} ${pushLoading ? "opacity-50" : ""}`}
                    >
                      <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${pushEnabled ? "translate-x-6" : "translate-x-1"}`} />
                    </button>
                  </div>

                  {/* 카카오톡 */}
                  {isKakaoUser && (
                    <div className="flex items-center justify-between p-3 bg-yellow-50 rounded-xl">
                      <div className="flex items-center gap-2">
                        <span className="text-base">💬</span>
                        <span className="text-sm font-semibold text-slate-700">카카오톡</span>
                      </div>
                      <button
                        onClick={() => setKakaoEnabled(!kakaoEnabled)}
                        className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${kakaoEnabled ? "bg-yellow-500" : "bg-slate-300"}`}
                      >
                        <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${kakaoEnabled ? "translate-x-6" : "translate-x-1"}`} />
                      </button>
                    </div>
                  )}

                  <p className="text-xs text-slate-400">평일 오전 9시에 맞춤 공고를 보내드려요</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 하단 버튼 (고정) */}
        <div className="p-5 sm:p-7 pt-0 shrink-0">
          {!isLastStep ? (
            <button
              onClick={goNext}
              disabled={!canNext()}
              className="w-full py-4 bg-indigo-600 text-white rounded-xl font-bold text-base hover:bg-indigo-700 transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-indigo-200"
            >
              다음
            </button>
          ) : (
            <button
              onClick={handleSave}
              disabled={loading}
              className="w-full py-4 bg-indigo-600 text-white rounded-xl font-bold text-base hover:bg-indigo-700 transition-all active:scale-[0.98] disabled:opacity-50 shadow-lg shadow-indigo-200"
            >
              {loading ? "설정 중..." : "맞춤 알림 설정 완료"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
