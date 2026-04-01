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

  // 사용자 타입
  const [userType, setUserType] = useState<UserType>(profile?.user_type || "individual");

  // 프로필 정보
  const [addressCity, setAddressCity] = useState(profile?.address_city || "");
  const [revenueBracket, setRevenueBracket] = useState(profile?.revenue_bracket || "");
  const [employeeBracket, setEmployeeBracket] = useState(profile?.employee_count_bracket || "");
  const [interests, setInterests] = useState<string[]>(
    profile?.interests ? String(profile.interests).split(",").filter(Boolean) : []
  );
  const [customNeeds, setCustomNeeds] = useState(profile?.custom_needs || "");

  // 알림 채널
  const [email, setEmail] = useState("");
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushLoading, setPushLoading] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen || !businessNumber) return;
    // 기존 알림 설정 로드
    fetch(`${API}/api/notification-settings/${businessNumber}`)
      .then(r => r.json())
      .then(d => { if (d.status === "SUCCESS" && d.data) setEmail(d.data.email || ""); })
      .catch(() => {});
    isPushSubscribed().then(setPushEnabled);

    // 프로필에서 초기값
    if (profile) {
      setUserType(profile.user_type || "individual");
      setAddressCity(profile.address_city || "");
      setRevenueBracket(profile.revenue_bracket || "");
      setEmployeeBracket(profile.employee_count_bracket || "");
      setInterests(profile.interests ? String(profile.interests).split(",").filter(Boolean) : []);
      setCustomNeeds(profile.custom_needs || "");
    }
  }, [isOpen, businessNumber, profile]);

  const toggleInterest = (item: string) => {
    setInterests(prev => prev.includes(item) ? prev.filter(i => i !== item) : [...prev, item]);
  };

  const handlePushToggle = async (enabled: boolean) => {
    setPushLoading(true);
    try {
      if (enabled) {
        const ok = await subscribePush(businessNumber);
        setPushEnabled(ok);
        toast(ok ? "푸시 알림이 활성화되었습니다." : "푸시 권한이 거부되었습니다.", ok ? "success" : "error");
      } else {
        await unsubscribePush();
        setPushEnabled(false);
        toast("푸시 알림이 해제되었습니다.", "success");
      }
    } finally { setPushLoading(false); }
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("auth_token") || "";
      // 1. 프로필 업데이트 (관심분야, 니즈 포함)
      await fetch(`${API}/api/profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          user_type: userType,
          address_city: addressCity,
          revenue_bracket: userType !== "individual" ? revenueBracket : undefined,
          employee_count_bracket: userType !== "individual" ? employeeBracket : undefined,
          interests: interests.join(","),
          custom_needs: customNeeds,
        }),
      });
      // 2. 알림 설정 저장
      await fetch(`${API}/api/notification-settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_number: businessNumber,
          email,
          channel: "BOTH",
          is_active: 1,
        }),
      });
      toast("맞춤 알림이 설정되었습니다! 평일 오전 9시에 맞춤 공고를 알려드려요.", "success");
      onSave({ userType, addressCity, interests, customNeeds });
      onClose();
    } catch {
      toast("저장 중 오류가 발생했습니다.", "error");
    } finally { setLoading(false); }
  };

  if (!isOpen) return null;

  const isInd = userType === "individual";
  const isBiz = userType === "business";
  const interestOptions = isInd ? IND_INTERESTS : isBiz ? BIZ_INTERESTS : [...IND_INTERESTS, ...BIZ_INTERESTS];

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300 max-h-[90vh] overflow-y-auto">
        <div className="p-6 space-y-5">
          {/* 헤더 */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[11px] font-bold text-indigo-500 tracking-wider">맞춤 설정</p>
              <h2 className="text-xl font-black text-slate-900">맞춤 알림 설정</h2>
            </div>
            <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400">✕</button>
          </div>

          {/* Q1: 사용자 타입 */}
          <div>
            <p className="text-[12px] font-bold text-slate-700 mb-2">어떤 지원금을 찾고 계세요?</p>
            <div className="flex gap-2">
              {([["individual", "개인"], ["business", "사업자"], ["both", "둘 다"]] as [UserType, string][]).map(([val, label]) => (
                <button
                  key={val}
                  onClick={() => { setUserType(val); setInterests([]); }}
                  className={`flex-1 py-2.5 rounded-xl text-[12px] font-bold transition-all active:scale-95 ${
                    userType === val ? "bg-indigo-600 text-white shadow-sm" : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                  }`}
                >{label}</button>
              ))}
            </div>
          </div>

          {/* Q2: 기본 정보 */}
          <div>
            <p className="text-[12px] font-bold text-slate-700 mb-2">{isInd ? "거주지" : "소재지"}</p>
            <div className="flex flex-wrap gap-1.5">
              {CITIES.map(city => (
                <button
                  key={city}
                  onClick={() => setAddressCity(city)}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-all active:scale-95 ${
                    addressCity === city ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-slate-500 border-slate-200 hover:border-indigo-300"
                  }`}
                >{city}</button>
              ))}
            </div>
          </div>

          {/* 사업자 전용 필드 */}
          {!isInd && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="text-[11px] font-bold text-slate-600 mb-1">매출 규모</p>
                <select value={revenueBracket} onChange={e => setRevenueBracket(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-[12px] outline-none focus:ring-2 focus:ring-indigo-200">
                  <option value="">선택</option>
                  {REVENUE.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <p className="text-[11px] font-bold text-slate-600 mb-1">직원 수</p>
                <select value={employeeBracket} onChange={e => setEmployeeBracket(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-[12px] outline-none focus:ring-2 focus:ring-indigo-200">
                  <option value="">선택</option>
                  {EMPLOYEE.map(e => <option key={e} value={e}>{e}</option>)}
                </select>
              </div>
            </div>
          )}

          {/* Q3: 관심분야 */}
          <div>
            <p className="text-[12px] font-bold text-slate-700 mb-2">관심분야 <span className="font-normal text-slate-400">(복수 선택)</span></p>
            {userType === "both" ? (
              <div className="space-y-3">
                <div>
                  <p className="text-[11px] font-bold text-indigo-600 mb-1.5">개인 복지</p>
                  <div className="flex flex-wrap gap-1.5">
                    {IND_INTERESTS.map(item => (
                      <button key={item} onClick={() => toggleInterest(item)}
                        className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-all active:scale-95 ${
                          interests.includes(item) ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-slate-500 border-slate-200 hover:border-indigo-300"
                        }`}
                      >{item}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[11px] font-bold text-violet-600 mb-1.5">기업 지원</p>
                  <div className="flex flex-wrap gap-1.5">
                    {BIZ_INTERESTS.map(item => (
                      <button key={item} onClick={() => toggleInterest(item)}
                        className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-all active:scale-95 ${
                          interests.includes(item) ? "bg-violet-600 text-white border-violet-600" : "bg-white text-slate-500 border-slate-200 hover:border-violet-300"
                        }`}
                      >{item}</button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {(isInd ? IND_INTERESTS : BIZ_INTERESTS).map(item => (
                  <button key={item} onClick={() => toggleInterest(item)}
                    className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-all active:scale-95 ${
                      interests.includes(item) ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-slate-500 border-slate-200 hover:border-indigo-300"
                    }`}
                  >{item}</button>
                ))}
              </div>
            )}
          </div>

          {/* Q4: 구체적 니즈 */}
          <div>
            <p className="text-[12px] font-bold text-slate-700 mb-2">구체적으로 찾는 지원금 <span className="font-normal text-slate-400">(선택)</span></p>
            <textarea
              value={customNeeds}
              onChange={e => setCustomNeeds(e.target.value)}
              placeholder={isInd ? "예: 전세 자금 대출 지원, 청년 월세 지원" : "예: 해외 수출 바우처, R&D 기술개발 자금"}
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-[12px] placeholder-slate-400 outline-none focus:ring-2 focus:ring-indigo-200 resize-none"
              rows={2}
            />
          </div>

          {/* 구분선 */}
          <div className="border-t border-slate-100 pt-4">
            <p className="text-[12px] font-bold text-slate-700 mb-3">알림 받을 방법</p>

            {/* 이메일 */}
            <div className="space-y-2 mb-3">
              <p className="text-[11px] font-bold text-slate-500">이메일</p>
              <input
                type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="email@example.com"
                className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-[12px] outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </div>

            {/* 푸시 */}
            <div className="flex items-center justify-between mb-1">
              <p className="text-[11px] font-bold text-slate-500">브라우저 푸시</p>
              <button
                disabled={pushLoading}
                onClick={() => handlePushToggle(!pushEnabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${pushEnabled ? "bg-indigo-600" : "bg-slate-200"} ${pushLoading ? "opacity-50" : ""}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${pushEnabled ? "translate-x-6" : "translate-x-1"}`} />
              </button>
            </div>
            <p className="text-[10px] text-slate-400 mb-2">평일 오전 9시에 맞춤 공고를 알려드립니다</p>
          </div>

          {/* 저장 */}
          <button
            onClick={handleSave}
            disabled={loading}
            className="w-full py-3.5 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all active:scale-[0.98] disabled:opacity-50 shadow-lg shadow-indigo-200"
          >
            {loading ? "저장 중..." : "맞춤 알림 설정 완료"}
          </button>
        </div>
      </div>
    </div>
  );
}
