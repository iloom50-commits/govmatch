"use client";

import { useState, useEffect } from "react";
import { useToast } from "@/components/ui/Toast";

const API = process.env.NEXT_PUBLIC_API_URL;

const BIZ_INTERESTS = ["창업지원", "기술개발", "수출마케팅", "고용지원", "시설개선", "정책자금", "디지털전환", "판로개척", "교육훈련", "에너지환경", "소상공인", "R&D"];
const IND_INTERESTS = ["취업", "주거", "교육", "청년", "출산", "육아", "다자녀", "장학금", "의료", "장애", "저소득", "노인", "문화"];
const CITIES = ["전국", "서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"];
const REVENUE = ["1억 미만", "1억~5억", "5억~10억", "10억~50억", "50억 이상"];
const EMPLOYEE = ["5인 미만", "5인~10인", "10인~30인", "30인~50인", "50인 이상"];

type UserType = "individual" | "business" | "both";

const TOTAL_STEPS = 5;

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

// ── 스텝 설정 ──
const STEP_TITLES = [
  "어떤 지원금을 찾고 계세요?",
  "지역을 선택해주세요",
  "관심분야를 선택해주세요",
  "구체적으로 찾는 지원금이 있나요?",
  "알림은 어떻게 받으실래요?",
];
const STEP_SUBTITLES = [
  "맞춤 공고를 찾아드릴게요",
  "여러 지역을 선택할 수 있어요",
  "관심있는 분야를 모두 골라주세요",
  "자유롭게 적어주시면 AI가 매칭해요",
  "평일 오전 9시에 맞춤 공고를 보내드려요",
];

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
  const [step, setStep] = useState(1);

  // 사용자 타입
  const [userType, setUserType] = useState<UserType>(profile?.user_type || "individual");

  // 프로필 정보 — 지역 복수 선택
  const [addressCities, setAddressCities] = useState<string[]>(
    profile?.address_city ? String(profile.address_city).split(",").filter(Boolean) : []
  );
  const [revenueBracket, setRevenueBracket] = useState(profile?.revenue_bracket || "");
  const [employeeBracket, setEmployeeBracket] = useState(profile?.employee_count_bracket || "");
  const [interests, setInterests] = useState<string[]>(
    profile?.interests ? String(profile.interests).split(",").filter(Boolean) : []
  );
  const [customNeeds, setCustomNeeds] = useState(profile?.custom_needs || "");

  // 알림 채널
  const [email, setEmail] = useState(profile?.email || "");
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushLoading, setPushLoading] = useState(false);
  const [kakaoEnabled, setKakaoEnabled] = useState(false);
  const [loading, setLoading] = useState(false);

  // 카카오 로그인 여부 판별
  const isKakaoUser = profile?.social_provider === "kakao";

  useEffect(() => {
    if (!isOpen || !businessNumber) return;
    setStep(1);
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
      setRevenueBracket(profile.revenue_bracket || "");
      setEmployeeBracket(profile.employee_count_bracket || "");
      setInterests(profile.interests ? String(profile.interests).split(",").filter(Boolean) : []);
      setCustomNeeds(profile.custom_needs || "");
      // 소셜 로그인 이메일 자동 채우기 (기존 설정이 없을 때)
      if (!email && profile.email && !profile.email.endsWith(".local")) {
        setEmail(profile.email);
      }
      // 카카오 사용자면 카카오 알림 기본 ON
      if (isKakaoUser) setKakaoEnabled(true);
    }
  }, [isOpen, businessNumber, profile]);

  const toggleCity = (city: string) => {
    if (city === "전국") {
      setAddressCities(prev => prev.includes("전국") ? [] : ["전국"]);
    } else {
      setAddressCities(prev => {
        const without전국 = prev.filter(c => c !== "전국");
        return without전국.includes(city) ? without전국.filter(c => c !== city) : [...without전국, city];
      });
    }
  };

  const toggleInterest = (item: string) => {
    setInterests(prev => prev.includes(item) ? prev.filter(i => i !== item) : [...prev, item]);
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

  const goNext = () => { if (step < TOTAL_STEPS) setStep(s => s + 1); };
  const goBack = () => { if (step > 1) setStep(s => s - 1); };

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
          revenue_bracket: userType !== "individual" ? revenueBracket : undefined,
          employee_count_bracket: userType !== "individual" ? employeeBracket : undefined,
          interests: interests.join(","),
          custom_needs: customNeeds,
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
      onSave({ userType, addressCities, interests, customNeeds });
      onClose();
    } catch {
      toast("저장 중 오류가 발생했습니다.", "error");
    } finally { setLoading(false); }
  };

  // 다음 버튼 활성화 조건
  const canNext = (): boolean => {
    switch (step) {
      case 1: return !!userType;
      case 2: return addressCities.length > 0;
      case 3: return interests.length > 0;
      case 4: return true;
      case 5: return true;
      default: return false;
    }
  };

  if (!isOpen) return null;

  const isInd = userType === "individual";
  const progressPct = (step / TOTAL_STEPS) * 100;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-3">
      <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300 max-h-[92vh] overflow-y-auto">
        {/* 진행률 바 */}
        <div className="h-1.5 bg-slate-100">
          <div
            className="h-full bg-indigo-600 transition-all duration-500 ease-out rounded-r-full"
            style={{ width: `${progressPct}%` }}
          />
        </div>

        <div className="p-5 sm:p-7">
          {/* 헤더 */}
          <div className="flex items-center justify-between mb-5 sm:mb-7">
            <div className="flex items-center gap-3">
              {step > 1 ? (
                <button onClick={goBack} className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400 transition-colors">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
                </button>
              ) : (
                <div className="w-10" />
              )}
              <div>
                <p className="text-xs font-bold text-indigo-500 tracking-wider">{step} / {TOTAL_STEPS}</p>
                <h2 className="text-xl sm:text-2xl font-black text-slate-900 leading-tight">{STEP_TITLES[step - 1]}</h2>
                <p className="text-xs sm:text-sm text-slate-400 mt-0.5">{STEP_SUBTITLES[step - 1]}</p>
              </div>
            </div>
            <button onClick={onClose} className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400 text-xl shrink-0">✕</button>
          </div>

          {/* 스텝 콘텐츠 */}
          <div className="min-h-[220px]">
            {/* Step 1: 사용자 타입 */}
            {step === 1 && (
              <div className="space-y-3 animate-in fade-in slide-in-from-right-4 duration-300">
                {([["individual", "개인 복지", "취업·주거·교육·출산 등 개인 지원금"], ["business", "기업 지원", "R&D·창업·수출·고용 등 기업 지원금"], ["both", "둘 다", "개인 복지 + 기업 지원 모두 받기"]] as [UserType, string, string][]).map(([val, label, desc]) => (
                  <button
                    key={val}
                    onClick={() => { setUserType(val); setInterests([]); }}
                    className={`w-full p-5 rounded-xl border-2 text-left transition-all active:scale-[0.98] ${
                      userType === val
                        ? "border-indigo-600 bg-indigo-50"
                        : "border-slate-200 bg-white hover:border-slate-300"
                    }`}
                  >
                    <p className={`text-base font-bold ${userType === val ? "text-indigo-700" : "text-slate-700"}`}>{label}</p>
                    <p className={`text-sm mt-1 ${userType === val ? "text-indigo-500" : "text-slate-400"}`}>{desc}</p>
                  </button>
                ))}
              </div>
            )}

            {/* Step 2: 지역 (복수 선택) + 사업자 정보 */}
            {step === 2 && (
              <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-bold text-slate-600">{isInd ? "거주 지역" : "사업장 소재지"} <span className="font-normal text-slate-400">(복수 선택)</span></p>
                    {addressCities.length > 0 && (
                      <p className="text-xs text-indigo-500 font-semibold">{addressCities.includes("전국") ? "전국" : `${addressCities.length}개 선택`}</p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {CITIES.map(city => (
                      <button
                        key={city}
                        onClick={() => toggleCity(city)}
                        className={`px-4 py-2 rounded-lg text-sm font-semibold border transition-all active:scale-95 ${
                          addressCities.includes(city)
                            ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                            : "bg-white text-slate-500 border-slate-200 hover:border-indigo-300"
                        }`}
                      >{city}</button>
                    ))}
                  </div>
                </div>

                {!isInd && (
                  <div className="grid grid-cols-2 gap-3 pt-2">
                    <div>
                      <p className="text-sm font-bold text-slate-600 mb-1.5">매출 규모</p>
                      <select value={revenueBracket} onChange={e => setRevenueBracket(e.target.value)}
                        className="w-full px-3 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-200">
                        <option value="">선택</option>
                        {REVENUE.map(r => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-600 mb-1.5">직원 수</p>
                      <select value={employeeBracket} onChange={e => setEmployeeBracket(e.target.value)}
                        className="w-full px-3 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-200">
                        <option value="">선택</option>
                        {EMPLOYEE.map(e => <option key={e} value={e}>{e}</option>)}
                      </select>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Step 3: 관심분야 */}
            {step === 3 && (
              <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
                {(userType === "both") ? (
                  <>
                    <div>
                      <p className="text-sm font-bold text-indigo-600 mb-2">개인 복지</p>
                      <div className="flex flex-wrap gap-2">
                        {IND_INTERESTS.map(item => (
                          <button key={item} onClick={() => toggleInterest(item)}
                            className={`px-4 py-2 rounded-full text-sm font-semibold border transition-all active:scale-95 ${
                              interests.includes(item) ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-slate-500 border-slate-200 hover:border-indigo-300"
                            }`}
                          >{item}</button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-sm font-bold text-violet-600 mb-2">기업 지원</p>
                      <div className="flex flex-wrap gap-2">
                        {BIZ_INTERESTS.map(item => (
                          <button key={item} onClick={() => toggleInterest(item)}
                            className={`px-4 py-2 rounded-full text-sm font-semibold border transition-all active:scale-95 ${
                              interests.includes(item) ? "bg-violet-600 text-white border-violet-600" : "bg-white text-slate-500 border-slate-200 hover:border-violet-300"
                            }`}
                          >{item}</button>
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {(isInd ? IND_INTERESTS : BIZ_INTERESTS).map(item => (
                      <button key={item} onClick={() => toggleInterest(item)}
                        className={`px-4 py-2 rounded-full text-sm font-semibold border transition-all active:scale-95 ${
                          interests.includes(item) ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-slate-500 border-slate-200 hover:border-indigo-300"
                        }`}
                      >{item}</button>
                    ))}
                  </div>
                )}
                {interests.length > 0 && (
                  <p className="text-xs text-indigo-500 font-semibold">{interests.length}개 선택됨</p>
                )}
              </div>
            )}

            {/* Step 4: 구체적 니즈 */}
            {step === 4 && (
              <div className="animate-in fade-in slide-in-from-right-4 duration-300">
                <textarea
                  value={customNeeds}
                  onChange={e => setCustomNeeds(e.target.value)}
                  placeholder={isInd
                    ? "예: 전세 자금 대출 지원, 청년 월세 지원, 취업 교육 프로그램"
                    : "예: 해외 수출 바우처, R&D 기술개발 자금, 고용 장려금"}
                  className="w-full px-4 py-4 bg-slate-50 border border-slate-200 rounded-xl text-base placeholder-slate-400 outline-none focus:ring-2 focus:ring-indigo-200 resize-none leading-relaxed"
                  rows={4}
                  autoFocus
                />
                <p className="text-xs text-slate-400 mt-2">건너뛰셔도 괜찮아요. 나중에 수정할 수 있습니다.</p>
              </div>
            )}

            {/* Step 5: 알림 채널 */}
            {step === 5 && (
              <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
                <div className="p-5 bg-slate-50 rounded-xl border border-slate-200">
                  <div className="flex items-center gap-2.5 mb-3">
                    <span className="text-lg">📧</span>
                    <p className="text-sm font-bold text-slate-700">이메일 알림</p>
                    {profile?.email && !profile.email.endsWith(".local") && email === profile.email && (
                      <span className="text-[10px] text-green-600 bg-green-50 px-2 py-0.5 rounded-full font-semibold">자동입력</span>
                    )}
                  </div>
                  <input
                    type="email" value={email} onChange={e => setEmail(e.target.value)}
                    placeholder="email@example.com"
                    className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-200"
                  />
                </div>

                <div className="p-5 bg-slate-50 rounded-xl border border-slate-200">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <span className="text-lg">🔔</span>
                      <div>
                        <p className="text-sm font-bold text-slate-700">브라우저 푸시 알림</p>
                        <p className="text-xs text-slate-400 mt-0.5">실시간으로 새 공고를 알려드려요</p>
                      </div>
                    </div>
                    <button
                      disabled={pushLoading}
                      onClick={() => handlePushToggle(!pushEnabled)}
                      className={`relative inline-flex h-8 w-14 items-center rounded-full transition-colors ${pushEnabled ? "bg-indigo-600" : "bg-slate-300"} ${pushLoading ? "opacity-50" : ""}`}
                    >
                      <span className={`inline-block h-6 w-6 transform rounded-full bg-white shadow transition-transform ${pushEnabled ? "translate-x-7" : "translate-x-1"}`} />
                    </button>
                  </div>
                </div>

                {/* 카카오톡 알림 (카카오 로그인 사용자만) */}
                {isKakaoUser && (
                  <div className="p-5 bg-yellow-50 rounded-xl border border-yellow-200">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <span className="text-lg">💬</span>
                        <div>
                          <p className="text-sm font-bold text-slate-700">카카오톡 알림</p>
                          <p className="text-xs text-slate-400 mt-0.5">카카오톡으로 맞춤 공고를 받아보세요</p>
                        </div>
                      </div>
                      <button
                        onClick={() => setKakaoEnabled(!kakaoEnabled)}
                        className={`relative inline-flex h-8 w-14 items-center rounded-full transition-colors ${kakaoEnabled ? "bg-yellow-500" : "bg-slate-300"}`}
                      >
                        <span className={`inline-block h-6 w-6 transform rounded-full bg-white shadow transition-transform ${kakaoEnabled ? "translate-x-7" : "translate-x-1"}`} />
                      </button>
                    </div>
                  </div>
                )}

                <div className="flex items-start gap-2.5 p-4 bg-indigo-50 rounded-xl">
                  <span className="text-sm mt-0.5">💡</span>
                  <p className="text-sm text-indigo-600 leading-relaxed">평일 오전 9시에 나에게 딱 맞는 공고를 보내드려요. 설정은 언제든 변경 가능해요.</p>
                </div>
              </div>
            )}
          </div>

          {/* 하단 버튼 */}
          <div className="mt-6">
            {step < TOTAL_STEPS ? (
              <button
                onClick={goNext}
                disabled={!canNext()}
                className="w-full py-4 bg-indigo-600 text-white rounded-xl font-bold text-base hover:bg-indigo-700 transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-indigo-200"
              >
                {step === 4 ? (customNeeds ? "다음" : "건너뛰기") : "다음"}
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
    </div>
  );
}
