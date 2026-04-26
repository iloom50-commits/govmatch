"use client";

import { useState, useEffect } from "react";
import { useToast } from "@/components/ui/Toast";
import { useModalBack } from "@/hooks/useModalBack";
import IndustryPicker from "@/components/shared/IndustryPicker";

const API = process.env.NEXT_PUBLIC_API_URL;

// ── 선택지 상수 ──
const CITIES = ["서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"];
const REVENUE = ["1억 미만", "1억~5억", "5억~10억", "10억~50억", "50억 이상"];
const EMPLOYEE = ["5인 미만", "5인~10인", "10인~30인", "30인~50인", "50인 이상"];

const GENDERS = ["남성", "여성"];
const AGE_RANGES = ["20대", "30대", "40대", "50대", "60대 이상"];
// 화면 표시용 금액 범위 → DB 저장값 매핑
const INCOME_DISPLAY = [
  { label: "월 100만원 이하", value: "기초생활" },
  { label: "월 100~200만원", value: "차상위" },
  { label: "월 200~300만원", value: "중위50%이하" },
  { label: "월 300~400만원", value: "중위75%이하" },
  { label: "월 400~500만원", value: "중위100%이하" },
  { label: "월 500만원 이상", value: "해당없음" },
];
const FAMILY_TYPES = ["1인가구", "다자녀", "한부모", "신혼부부", "다문화", "일반"];
const EMPLOYMENT_STATUSES = ["재직자", "구직자", "자영업", "프리랜서", "학생", "해당없음"];

const CERTIFICATIONS = ["벤처기업", "이노비즈", "메인비즈", "여성기업", "장애인기업", "사회적기업", "없음"];

// 관심분야 자동완성용 카테고리
const BIZ_INTERESTS = ["창업지원", "기술개발", "수출마케팅", "고용지원", "시설개선", "정책자금", "디지털전환", "판로개척", "교육훈련", "에너지환경", "소상공인", "R&D"];
const IND_INTERESTS = ["취업", "주거", "교육", "청년", "출산", "육아", "다자녀", "장학금", "의료", "장애", "저소득", "노인", "문화"];

// 맞춤 키워드 추천 태그
const BIZ_KEYWORDS = ["전문가 모집", "주관기관 모집", "운영기관 모집", "컨설턴트 모집", "평가위원", "심사위원", "수행기관", "위탁운영", "사업설명회", "데모데이", "IR", "멘토링", "액셀러레이팅", "해외전시회", "바우처", "인증지원"];
const IND_KEYWORDS = ["전세자금", "월세지원", "청년수당", "취업성공패키지", "내일배움카드", "국민취업지원", "긴급복지", "기초연금", "장애수당", "보육료", "산후조리", "문화바우처", "체육바우처", "교육바우처", "의료비지원", "주거급여"];

type UserType = "individual" | "business" | "both";

// ── 푸시 구독 유틸 ──
// 최적화:
// 1. 권한 요청을 맨 먼저 → 사용자 클릭 즉시 브라우저 팝업이 뜸 (체감 속도 향상)
// 2. Service Worker 등록과 VAPID key fetch를 병렬 처리
// 3. 서버 저장(/api/push/subscribe)은 fire-and-forget — 구독 성공 후 UI 차단 없이 백그라운드 전송
async function subscribePush(bn: string): Promise<boolean> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return false;
  try {
    // 1) 권한 요청을 최우선 — 사용자 클릭 반응 즉시 나타남
    const perm = await Notification.requestPermission();
    if (perm !== "granted") return false;

    // 2) SW 등록 + VAPID 키 fetch를 병렬로 실행
    const [reg, vapidRes] = await Promise.all([
      navigator.serviceWorker.getRegistration("/sw.js").then(r => r || navigator.serviceWorker.register("/sw.js")),
      fetch(`${API}/api/push/vapid-key`).then(r => r.json()).catch(() => null),
    ]);
    if (!reg || !vapidRes?.publicKey) return false;

    // 3) 기존 구독 있으면 재사용
    const existing = await reg.pushManager.getSubscription();
    if (existing) {
      // 서버 저장은 백그라운드로 (UI 차단 X)
      const subJson = existing.toJSON();
      fetch(`${API}/api/push/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ business_number: bn, endpoint: subJson.endpoint, keys: subJson.keys }),
      }).catch(() => {});
      return true;
    }

    // 4) 새 구독 생성 (FCM 왕복 — 2~10초, 브라우저 제어)
    const publicKey = vapidRes.publicKey;
    const padding = "=".repeat((4 - (publicKey.length % 4)) % 4);
    const base64 = (publicKey + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(base64);
    const applicationServerKey = Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
    const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey });

    // 5) 서버 저장은 fire-and-forget (성공 즉시 UI 반환)
    const subJson = sub.toJSON();
    fetch(`${API}/api/push/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business_number: bn, endpoint: subJson.endpoint, keys: subJson.keys }),
    }).catch(() => {});

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

// ── 스텝 테마: 개인=emerald, 기업=blue, 공통=indigo ──
type StepTheme = "indigo" | "emerald" | "blue";
function getStepTheme(stepId: StepId): StepTheme {
  if (stepId?.startsWith("ind_")) return "emerald";
  if (stepId?.startsWith("biz_")) return "blue";
  return "indigo";
}
const THEME = {
  indigo: { bar: "bg-indigo-600", btn: "bg-indigo-600 hover:bg-indigo-700 shadow-indigo-200", num: "text-indigo-500", badge: null },
  emerald: { bar: "bg-emerald-500", btn: "bg-emerald-600 hover:bg-emerald-700 shadow-emerald-200", num: "text-emerald-600", badge: { text: "개인 정보", cls: "bg-emerald-100 text-emerald-700" } },
  blue:    { bar: "bg-blue-600",    btn: "bg-blue-600 hover:bg-blue-700 shadow-blue-200",       num: "text-blue-600",    badge: { text: "기업 정보", cls: "bg-blue-100 text-blue-700" } },
};

// ── 동적 스텝 계산 (페이지당 2~3항목, 스크롤 없음) ──
type StepId = "type" | "ind_location" | "ind_basic" | "ind_life" | "biz_location" | "biz_info1" | "biz_info2" | "interests" | "notify";
function getSteps(userType: UserType): { id: StepId; title: string; subtitle: string }[] {
  const steps: { id: StepId; title: string; subtitle: string }[] = [
    { id: "type", title: "어떤 지원금을 찾고 계세요?", subtitle: "맞춤 공고를 찾아드릴게요" },
  ];
  if (userType === "individual" || userType === "both") {
    steps.push({ id: "ind_location", title: "거주 지역을 알려주세요", subtitle: "공고 지역 필터링에 사용합니다" });
    steps.push({ id: "ind_basic", title: "기본 정보를 알려주세요", subtitle: "성별·연령·소득 조건 매칭에 사용합니다" });
    steps.push({ id: "ind_life", title: "생활 정보를 알려주세요", subtitle: "가구유형·취업상태 매칭에 사용합니다" });
  }
  if (userType === "business") {
    steps.push({ id: "biz_location", title: "사업장 소재지를 알려주세요", subtitle: "공고 지역 필터링에 사용합니다" });
  }
  if (userType === "business" || userType === "both") {
    steps.push({ id: "biz_info1", title: "기업 기본 정보", subtitle: "기업명·매출·직원수를 알려주세요" });
    steps.push({ id: "biz_info2", title: "기업 상세 정보", subtitle: "설립일·보유인증을 알려주세요" });
  }
  steps.push({ id: "interests", title: "관심분야를 선택해주세요", subtitle: "키워드를 골라주시면 AI가 매칭해요" });
  steps.push({ id: "notify", title: "알림 설정", subtitle: "맞춤 공고를 어떻게 받으실건가요?" });
  return steps;
}

// ── 관심분야 자동완성 + AI fallback ──

type TagSuggestion = { tag: string; category?: string; similarity: number };

function InterestAutocomplete({ options, selected, onSelect, onRemove, userType }: { options: string[]; selected: string[]; onSelect: (opt: string) => void; onRemove?: (opt: string) => void; userType?: string }) {
  const [input, setInput] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<TagSuggestion[]>([]);
  const [showPanel, setShowPanel] = useState(false);
  const localFiltered = input ? options.filter(opt => opt.toLowerCase().includes(input.toLowerCase()) && !selected.includes(opt)) : [];

  const fetchSuggestions = async () => {
    const q = input.trim();
    if (!q || aiLoading) return;
    setAiLoading(true);
    try {
      const res = await fetch(`${API}/api/ai/suggest-tags`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: q, user_type: userType || "business", limit: 10 }),
      });
      if (res.ok) {
        const data = await res.json();
        const sugg = (data.suggestions || []) as TagSuggestion[];
        const filtered = sugg.filter(s => !selected.includes(s.tag));
        setSuggestions(filtered);
        // 유사도 0.7 이상은 자동 선택 (부모 interests에 즉시 반영)
        filtered.forEach(s => { if (s.similarity >= 0.7 && !selected.includes(s.tag)) onSelect(s.tag); });
        setShowPanel(true);
      }
    } catch {
      // 실패 시 원문만 추가
      onSelect(q);
      setInput("");
    } finally {
      setAiLoading(false);
    }
  };

  // 체크 토글 시 즉시 부모 interests에 반영 → canNext()가 실시간으로 true가 됨
  const toggleCheck = (tag: string) => {
    if (selected.includes(tag)) {
      onRemove?.(tag);
    } else {
      onSelect(tag);
    }
  };

  const confirmSelection = () => {
    // 사용자 원문도 추가 (중복 제외)
    const raw = input.trim();
    if (raw && !selected.includes(raw)) {
      onSelect(raw);
    }
    setInput("");
    setSuggestions([]);
    setShowPanel(false);
  };

  const cancelPanel = () => {
    setSuggestions([]);
    setShowPanel(false);
  };

  return (
    <div className="relative">
      <input
        type="text" value={input}
        onChange={(e) => { setInput(e.target.value); if (showPanel) cancelPanel(); }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            if (localFiltered.length > 0) { onSelect(localFiltered[0]); setInput(""); }
            else if (input.trim()) fetchSuggestions();
          }
        }}
        placeholder="관심분야를 자유롭게 입력하세요 (예: 바이오 의료기기 인허가)"
        className="w-full px-3 py-2.5 bg-white border border-slate-200 rounded-xl text-sm text-slate-700 placeholder-slate-400 outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300 transition-all"
      />
      {/* 로컬 고정목록 자동완성 */}
      {input && !showPanel && localFiltered.length > 0 && (
        <div className="absolute z-20 w-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg max-h-48 overflow-y-auto">
          {localFiltered.slice(0, 8).map(opt => (
            <button key={opt} type="button" onClick={() => { onSelect(opt); setInput(""); }}
              className="w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 transition-all"
            >{opt}</button>
          ))}
          <button type="button" onClick={fetchSuggestions} disabled={aiLoading}
            className="w-full px-3 py-2 text-left text-sm text-indigo-600 font-semibold border-t border-slate-100 hover:bg-indigo-50 disabled:opacity-50"
          >
            {aiLoading ? "AI 검색 중..." : `"${input}"로 AI가 유사 태그 찾기 →`}
          </button>
        </div>
      )}
      {/* 로컬 매칭 없고 패널 닫힌 상태 → AI 검색 버튼 */}
      {input && input.length >= 2 && !showPanel && localFiltered.length === 0 && (
        <div className="absolute z-20 w-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg p-3">
          <button type="button" onClick={fetchSuggestions} disabled={aiLoading}
            className="w-full text-left text-sm text-indigo-600 font-semibold hover:text-indigo-800 transition-all disabled:opacity-50"
          >
            {aiLoading ? "AI가 유사 태그 찾는 중..." : `"${input}" → AI가 유사 태그 찾기 (Enter)`}
          </button>
        </div>
      )}
      {/* AI 제안 패널 — 모바일: fixed 하단 시트 / 데스크탑: absolute 드롭다운 */}
      {showPanel && (
        <>
          {/* 모바일 배경 딤 */}
          <div className="fixed inset-0 z-40 bg-black/20 sm:hidden" onClick={cancelPanel} />
          <div className="fixed left-0 right-0 bottom-0 z-50 rounded-t-2xl sm:absolute sm:bottom-auto sm:top-full sm:left-0 sm:right-0 sm:rounded-xl sm:z-30 bg-white border-t border-indigo-200 sm:border sm:border-indigo-300 shadow-2xl sm:shadow-xl p-4 sm:p-3 max-h-[60vh] sm:max-h-96 overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <p className="text-[13px] font-bold text-indigo-700">AI가 찾은 유사 태그 ({suggestions.length}개)</p>
              <button onClick={cancelPanel} className="text-slate-400 hover:text-slate-600 text-lg leading-none">✕</button>
            </div>
            {suggestions.length === 0 ? (
              <p className="text-sm text-slate-500 py-3 text-center">유사한 태그를 찾지 못했습니다.<br/>입력한 내용을 그대로 추가하려면 확인을 누르세요.</p>
            ) : (
              <div className="space-y-1">
                {suggestions.map(s => (
                  <label key={s.tag} className="flex items-center gap-3 px-2 py-2.5 rounded-lg hover:bg-indigo-50 active:bg-indigo-100 cursor-pointer">
                    <input type="checkbox" checked={selected.includes(s.tag)} onChange={() => toggleCheck(s.tag)}
                      className="w-5 h-5 accent-indigo-600 flex-shrink-0" />
                    <span className="text-sm text-slate-700 flex-1">{s.tag}</span>
                    {s.category && <span className="text-[11px] text-slate-400">{s.category}</span>}
                    <span className="text-[11px] text-indigo-400 font-mono w-8 text-right">{Math.round(s.similarity * 100)}%</span>
                  </label>
                ))}
              </div>
            )}
            <div className="flex gap-2 mt-4 pt-3 border-t border-slate-100">
              <button onClick={confirmSelection}
                className="flex-1 py-3 bg-indigo-600 text-white rounded-xl text-sm font-bold hover:bg-indigo-700 active:scale-95">
                확인
              </button>
              <button onClick={cancelPanel}
                className="px-5 py-3 bg-slate-100 text-slate-600 rounded-xl text-sm font-medium hover:bg-slate-200 active:scale-95">
                취소
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
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
  isOpen, onClose, businessNumber, onSave, profile, shortcutMode = false, contextMessage,
}: {
  isOpen: boolean;
  onClose: () => void;
  businessNumber: string;
  onSave: (data: any) => void;
  profile?: any;
  shortcutMode?: boolean;  // true면 프로필 스텝 스킵 — 알림 설정만 바로 보여줌
  contextMessage?: string; // AI 상담 게이트 등에서 열릴 때 상단에 표시할 안내 문구
}) {
  useModalBack(isOpen, onClose);
  const { toast } = useToast();
  const [step, setStep] = useState(0);

  // 사용자 타입
  const [userType, setUserType] = useState<UserType>(profile?.user_type || "individual");

  // 공통
  const [homeCity, setHomeCity] = useState("");  // 소재지 (1개)
  const [interestRegions, setInterestRegions] = useState<string[]>([]);  // 관심지역 (복수)
  // 하위 호환용 (기존 코드에서 addressCities 참조)
  const addressCities = homeCity ? ["전국", homeCity, ...interestRegions] : ["전국", ...interestRegions];
  const setAddressCities = (_: string[]) => {}; // deprecated

  // 개인 필드
  const [gender, setGender] = useState("");
  const [ageRange, setAgeRange] = useState("");
  const [incomeLevel, setIncomeLevel] = useState("");
  const [familyType, setFamilyType] = useState("");
  const [employmentStatus, setEmploymentStatus] = useState("");

  // 기업 필드
  const [companyName, setCompanyName] = useState("");
  const [industryCode, setIndustryCode] = useState("");
  const [industryName, setIndustryName] = useState("");
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
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || !businessNumber) return;
    setStep(shortcutMode ? steps.length - 1 : 0);

    // 알림 설정 로드 (인증 필요)
    const _tok = localStorage.getItem("auth_token");
    if (_tok) {
      fetch(`${API}/api/notification-settings/${businessNumber}`, {
        headers: { Authorization: `Bearer ${_tok}` },
      })
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (d?.status === "SUCCESS" && d.data) {
            if (d.data.email) setEmail(d.data.email);
            if (d.data.kakao_enabled) setKakaoEnabled(true);
          }
        })
        .catch(() => {});
    }
    isPushSubscribed().then(setPushEnabled);

    // 프로필을 항상 DB에서 직접 fetch — prop 타이밍 이슈 방지
    const token = localStorage.getItem("auth_token");
    if (token) {
      fetch(`${API}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          const p = data?.user || profile;
          if (!p) return;
          setUserType(p.user_type || "individual");
          const cities = p.address_city ? String(p.address_city).split(",").filter((c: string) => c && c !== "전국") : [];
          setHomeCity(cities[0] || "");
          setInterestRegions(p.interest_regions ? String(p.interest_regions).split(",").filter(Boolean) : []);
          setGender(p.gender || "");
          setAgeRange(p.age_range || "");
          setIncomeLevel(p.income_level || "");
          setFamilyType(p.family_type || "");
          setEmploymentStatus(p.employment_status || "");
          setCompanyName(p.company_name || "");
          setIndustryCode(p.industry_code || "");
          setIndustryName(p.industry_name || "");
          setRevenueBracket(p.revenue_bracket || "");
          setEmployeeBracket(p.employee_count_bracket || "");
          setFoundedDate(p.founded_date || "");
          setIsPreFounder(p.is_pre_founder || false);
          setCertifications(p.certifications ? String(p.certifications).split(",").filter(Boolean) : []);
          setInterests(p.interests ? String(p.interests).split(",").filter(Boolean) : []);
          setCustomKeywords(p.custom_keywords ? String(p.custom_keywords).split(",").filter(Boolean) : []);
          if (!email && p.email && !p.email.endsWith(".local")) setEmail(p.email);
          if (p.social_provider === "kakao") setKakaoEnabled(true);
        })
        .catch(() => {
          // fetch 실패 시 prop으로 폴백
          if (!profile) return;
          const p = profile;
          setUserType(p.user_type || "individual");
          const cities = p.address_city ? String(p.address_city).split(",").filter((c: string) => c && c !== "전국") : [];
          setHomeCity(cities[0] || "");
          setInterestRegions(p.interest_regions ? String(p.interest_regions).split(",").filter(Boolean) : []);
          setGender(p.gender || ""); setAgeRange(p.age_range || ""); setIncomeLevel(p.income_level || "");
          setFamilyType(p.family_type || ""); setEmploymentStatus(p.employment_status || "");
          setCompanyName(p.company_name || "");
          setIndustryCode(p.industry_code || "");
          setIndustryName(p.industry_name || "");
          setRevenueBracket(p.revenue_bracket || "");
          setEmployeeBracket(p.employee_count_bracket || ""); setFoundedDate(p.founded_date || "");
          setIsPreFounder(p.is_pre_founder || false);
          setCertifications(p.certifications ? String(p.certifications).split(",").filter(Boolean) : []);
          setInterests(p.interests ? String(p.interests).split(",").filter(Boolean) : []);
          setCustomKeywords(p.custom_keywords ? String(p.custom_keywords).split(",").filter(Boolean) : []);
        });
    } else if (profile) {
      // 비로그인 폴백 (실제로는 발생 안 함)
      const p = profile;
      setUserType(p.user_type || "individual");
    }
  }, [isOpen, businessNumber]);

  // ── 토글 헬퍼 (deprecated — UI에서 직접 setHomeCity/setInterestRegions 사용) ──
  const toggleCity = (_city: string) => {};
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
  const goBack = () => {
    if (shortcutMode) return;  // shortcut에선 뒤로 불가 (프로필 스텝 접근 차단)
    if (step > 0) setStep(s => s - 1);
  };

  // shortcutMode에서 userType이 프로필 로드 후 바뀌면 마지막 스텝으로 재정렬
  useEffect(() => {
    if (isOpen && shortcutMode) setStep(steps.length - 1);
  }, [isOpen, shortcutMode, userType]);  // eslint-disable-line

  // 유형 변경 시 스텝 리셋 + 자동 다음
  const handleTypeChange = (val: UserType) => {
    setUserType(val);
    setInterests([]);
    setCustomKeywords([]);
    // 선택 즉시 다음 스텝으로 이동 (짧은 딜레이로 애니메이션 느낌)
    setTimeout(() => setStep(s => s + 1), 150);
  };

  // ── 저장 ──
  const handleSave = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("auth_token") || "";
      const profileRes = await fetch(`${API}/api/profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          user_type: userType,
          address_city: homeCity ? `전국,${homeCity}` : "전국",
          interest_regions: interestRegions.join(","),
          // 개인
          gender: (userType !== "business") ? gender : undefined,
          age_range: (userType !== "business") ? ageRange : undefined,
          income_level: (userType !== "business") ? incomeLevel : undefined,
          family_type: (userType !== "business") ? familyType : undefined,
          employment_status: (userType !== "business") ? employmentStatus : undefined,
          // 기업
          company_name: (userType !== "individual" && companyName.trim()) ? companyName.trim() : undefined,
          industry_code: (userType !== "individual" && industryCode) ? industryCode : undefined,
          industry_name: (userType !== "individual" && industryName) ? industryName : undefined,
          revenue_bracket: (userType !== "individual") ? revenueBracket : undefined,
          employee_count_bracket: (userType !== "individual") ? employeeBracket : undefined,
          founded_date: (userType !== "individual" && !isPreFounder && foundedDate) ? foundedDate : undefined,
          is_pre_founder: (userType !== "individual") ? isPreFounder : undefined,
          certifications: (userType !== "individual") ? certifications.join(",") : undefined,
          // 관심
          interests: interests.join(","),
          custom_keywords: customKeywords.join(","),
        }),
      });
      if (!profileRes.ok) {
        const err = await profileRes.json().catch(() => ({}));
        toast(err.detail || `프로필 저장 실패 (${profileRes.status})`, "error");
        setLoading(false);
        return;
      }
      const notifyRes = await fetch(`${API}/api/notification-settings`, {
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
      if (!notifyRes.ok) {
        toast(`알림 설정 저장 실패 (${notifyRes.status})`, "error");
        setLoading(false);
        return;
      }
      toast("맞춤 알림이 설정되었습니다! 평일 오전 9시에 맞춤 공고를 알려드려요.", "success");
      onSave({ userType, addressCities, interests, customKeywords });
      onClose();
    } catch (e) {
      toast("저장 중 오류가 발생했습니다.", "error");
    } finally { setLoading(false); }
  };

  // ── canNext ──
  const canNext = (): boolean => {
    switch (currentStep.id) {
      case "type": return !!userType;
      case "ind_location": return true;
      case "ind_basic": return true;
      case "ind_life": return true;
      case "biz_location": return true;
      case "biz_info1": return true;
      case "biz_info2": return true;
      case "interests": return interests.length > 0;
      case "notify": return true;
      default: return true;
    }
  };

  if (!isOpen) return null;

  const isInd = userType === "individual";
  const isBoth = userType === "both";
  const progressPct = ((step + 1) / totalSteps) * 100;
  const isLastStep = step === totalSteps - 1;
  const theme = THEME[getStepTheme(currentStep.id)];

  return (
    <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center sm:p-3">
      <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full sm:max-w-lg bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl overflow-hidden animate-in slide-in-from-bottom sm:zoom-in-95 duration-300 h-[100dvh] sm:h-auto sm:max-h-[96vh] flex flex-col">
        {/* 진행률 바 — shortcut에선 숨김 */}
        {!shortcutMode && (
          <div className="h-1.5 bg-slate-100 shrink-0">
            <div className={`h-full ${theme.bar} transition-all duration-500 ease-out rounded-r-full`} style={{ width: `${progressPct}%` }} />
          </div>
        )}

        {/* 컨텍스트 배너 — AI 상담 게이트 등 진입 시 안내 */}
        {contextMessage && (
          <div className="flex items-center gap-2 px-4 py-2.5 bg-indigo-50 border-b border-indigo-100 shrink-0">
            <svg className="w-4 h-4 text-indigo-500 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span className="text-xs font-medium text-indigo-700">{contextMessage}</span>
          </div>
        )}

        <div className="relative flex-1 overflow-y-auto">
          <div className="p-4 sm:p-7">
          {/* 헤더 */}
          <div className="flex items-center justify-between mb-4 sm:mb-7">
            <div className="flex items-center gap-3">
              {step > 0 && !shortcutMode ? (
                <button onClick={goBack} className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400 transition-colors">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
                </button>
              ) : (
                <div className="w-10" />
              )}
              <div>
                {shortcutMode ? (
                  <>
                    <p className="text-xs font-bold text-indigo-500 tracking-wider">맞춤 알림</p>
                    <h2 className="text-xl sm:text-2xl font-black text-slate-900 leading-tight">알림 받기</h2>
                    <p className="text-xs sm:text-sm text-slate-400 mt-0.5">평일 오전 9시에 맞춤 공고를 보내드려요</p>
                  </>
                ) : (
                  <>
                    <div className="flex items-center gap-2 mb-0.5">
                      <p className={`text-xs font-bold tracking-wider ${theme.num}`}>{step + 1} / {totalSteps}</p>
                      {theme.badge && (
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${theme.badge.cls}`}>{theme.badge.text}</span>
                      )}
                    </div>
                    <h2 className="text-xl sm:text-2xl font-black text-slate-900 leading-tight">{currentStep.title}</h2>
                    <p className="text-xs sm:text-sm text-slate-400 mt-0.5">{currentStep.subtitle}</p>
                  </>
                )}
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

            {/* ===== Step: 개인 — 거주지역 + 관심지역 ===== */}
            {currentStep.id === "ind_location" && (
              <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-bold text-slate-600">거주 지역 <span className="font-normal text-slate-400">(1개 선택)</span></p>
                    {homeCity && <p className="text-xs text-indigo-500 font-semibold">{homeCity}</p>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {CITIES.map(city => <ChipRect key={city} label={city} selected={homeCity === city} onClick={() => setHomeCity(homeCity === city ? "" : city)} />)}
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-bold text-slate-600">관심 지역 <span className="font-normal text-slate-400">(복수, 선택사항)</span></p>
                    {interestRegions.length > 0 && <p className="text-xs text-violet-500 font-semibold">{interestRegions.join(", ")}</p>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {CITIES.filter(c => c !== homeCity).map(city => (
                      <ChipRect key={city} label={city} selected={interestRegions.includes(city)}
                        onClick={() => setInterestRegions(prev => prev.includes(city) ? prev.filter(c => c !== city) : [...prev, city])} />
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ===== Step: 개인 — 기본정보 (성별·연령대·소득수준) ===== */}
            {currentStep.id === "ind_basic" && (
              <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">성별</p>
                  <div className="flex gap-2">
                    {GENDERS.map(g => <ChipRect key={g} label={g} selected={gender === g} onClick={() => setGender(gender === g ? "" : g)} />)}
                  </div>
                </div>
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">연령대</p>
                  <div className="flex flex-wrap gap-2">
                    {AGE_RANGES.map(a => <ChipRect key={a} label={a} selected={ageRange === a} onClick={() => setAgeRange(ageRange === a ? "" : a)} />)}
                  </div>
                </div>
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">소득수준</p>
                  <div className="flex flex-wrap gap-2">
                    {INCOME_DISPLAY.map(({ label, value }) => <ChipRect key={value} label={label} selected={incomeLevel === value} onClick={() => setIncomeLevel(incomeLevel === value ? "" : value)} />)}
                  </div>
                </div>
                <p className="text-xs text-slate-400">선택하지 않은 항목은 전체 대상으로 매칭됩니다</p>
              </div>
            )}

            {/* ===== Step: 개인 — 생활정보 (가구유형·취업상태) ===== */}
            {currentStep.id === "ind_life" && (
              <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">가구유형</p>
                  <div className="flex flex-wrap gap-2">
                    {FAMILY_TYPES.map(f => <ChipRect key={f} label={f} selected={familyType === f} onClick={() => setFamilyType(familyType === f ? "" : f)} />)}
                  </div>
                </div>
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">취업상태</p>
                  <div className="flex flex-wrap gap-2">
                    {EMPLOYMENT_STATUSES.map(s => <ChipRect key={s} label={s} selected={employmentStatus === s} onClick={() => setEmploymentStatus(employmentStatus === s ? "" : s)} />)}
                  </div>
                </div>
                <p className="text-xs text-slate-400">선택하지 않은 항목은 전체 대상으로 매칭됩니다</p>
              </div>
            )}

            {/* ===== Step: 기업 — 사업장 소재지 + 관심지역 ===== */}
            {currentStep.id === "biz_location" && (
              <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-bold text-slate-600">사업장 소재지 <span className="font-normal text-slate-400">(1개 선택)</span></p>
                    {homeCity && <p className="text-xs text-indigo-500 font-semibold">{homeCity}</p>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {CITIES.map(city => <ChipRect key={city} label={city} selected={homeCity === city} onClick={() => setHomeCity(homeCity === city ? "" : city)} />)}
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-bold text-slate-600">관심 지역 <span className="font-normal text-slate-400">(복수, 선택사항)</span></p>
                    {interestRegions.length > 0 && <p className="text-xs text-violet-500 font-semibold">{interestRegions.join(", ")}</p>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {CITIES.filter(c => c !== homeCity).map(city => (
                      <ChipRect key={city} label={city} selected={interestRegions.includes(city)}
                        onClick={() => setInterestRegions(prev => prev.includes(city) ? prev.filter(c => c !== city) : [...prev, city])} />
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ===== Step: 기업 — 기본정보 (기업명·업종·매출·직원수) ===== */}
            {currentStep.id === "biz_info1" && (
              <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">기업명 (상호명) <span className="font-normal text-slate-400">(선택)</span></p>
                  <input
                    type="text" value={companyName} onChange={e => setCompanyName(e.target.value)}
                    placeholder="예: 지원금AI"
                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-[16px] outline-none focus:ring-2 focus:ring-blue-200"
                  />
                </div>
                <IndustryPicker
                  value={industryName}
                  selectedCode={industryCode}
                  onSelect={(code, name) => { setIndustryCode(code); setIndustryName(name); }}
                  label="업종"
                  sublabel="(AI가 유사 업종 추천)"
                  dark={false}
                />
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">매출 규모</p>
                  <div className="flex flex-wrap gap-2">
                    {REVENUE.map(r => <ChipRect key={r} label={r} selected={revenueBracket === r} onClick={() => setRevenueBracket(revenueBracket === r ? "" : r)} />)}
                  </div>
                </div>
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">직원 수</p>
                  <div className="flex flex-wrap gap-2">
                    {EMPLOYEE.map(e => <ChipRect key={e} label={e} selected={employeeBracket === e} onClick={() => setEmployeeBracket(employeeBracket === e ? "" : e)} />)}
                  </div>
                </div>
              </div>
            )}

            {/* ===== Step: 기업 — 상세정보 (설립일·보유인증) ===== */}
            {currentStep.id === "biz_info2" && (
              <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">설립일</p>
                  {!isPreFounder && (
                    <input
                      type="text" inputMode="numeric" maxLength={10} value={foundedDate}
                      onChange={e => {
                        const raw = e.target.value.replace(/[^0-9]/g, "").slice(0, 8);
                        let formatted = raw;
                        if (raw.length >= 5) formatted = raw.slice(0, 4) + "-" + raw.slice(4);
                        if (raw.length >= 7) formatted = raw.slice(0, 4) + "-" + raw.slice(4, 6) + "-" + raw.slice(6);
                        setFoundedDate(formatted);
                      }}
                      placeholder="예: 20230315"
                      className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-[16px] outline-none focus:ring-2 focus:ring-indigo-200"
                    />
                  )}
                  <label className="flex items-center gap-2 mt-2 cursor-pointer">
                    <input
                      type="checkbox" checked={isPreFounder}
                      onChange={e => { setIsPreFounder(e.target.checked); if (e.target.checked) setFoundedDate(""); }}
                      className="w-5 h-5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-200"
                    />
                    <span className="text-sm text-slate-600">아직 창업 전입니다 (예비창업자)</span>
                  </label>
                </div>
                <div>
                  <p className="text-sm font-bold text-slate-600 mb-2">보유 인증 <span className="font-normal text-slate-400">(복수 선택)</span></p>
                  <div className="flex flex-wrap gap-2">
                    {CERTIFICATIONS.map(c => <ChipRect key={c} label={c} selected={certifications.includes(c)} onClick={() => toggleCert(c)} />)}
                  </div>
                </div>
              </div>
            )}

            {/* ===== Step: 관심분야 ===== */}
            {currentStep.id === "interests" && (
              <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
                <p className="text-sm font-bold text-slate-700 mb-2">관심분야를 입력하세요</p>
                {interests.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {interests.map((tag) => (
                      <span key={tag} className="inline-flex items-center gap-1 px-2.5 py-1 bg-indigo-100 text-indigo-700 rounded-full text-[13px] font-semibold">
                        {tag}
                        <button type="button" onClick={() => setInterests(prev => prev.filter(t => t !== tag))} className="hover:text-indigo-900 text-indigo-400">×</button>
                      </span>
                    ))}
                  </div>
                )}
                <InterestAutocomplete
                  options={[
                    ...(isBoth ? [...IND_INTERESTS, ...BIZ_INTERESTS] : isInd ? IND_INTERESTS : BIZ_INTERESTS),
                    ...(isBoth ? [...IND_KEYWORDS, ...BIZ_KEYWORDS] : isInd ? IND_KEYWORDS : BIZ_KEYWORDS),
                  ]}
                  selected={interests}
                  onSelect={(opt) => setInterests(prev => [...prev, opt])}
                  onRemove={(opt) => setInterests(prev => prev.filter(t => t !== opt))}
                  userType={isInd ? "individual" : "business"}
                />
                <p className="text-[11px] text-slate-400 mt-1">키워드를 입력하면 추천 목록이 나타납니다</p>
              </div>
            )}

            {/* ===== Step: 알림 설정 ===== */}
            {currentStep.id === "notify" && (
              <div className="space-y-3 animate-in fade-in slide-in-from-right-4 duration-300">
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
                    <div className="flex flex-col">
                      <span className="text-sm font-semibold text-slate-700">브라우저 푸시</span>
                      {pushLoading && (
                        <span className="text-[10px] text-indigo-500 font-medium animate-pulse">설정 중... (최대 10초)</span>
                      )}
                    </div>
                  </div>
                  <button
                    disabled={pushLoading}
                    onClick={() => handlePushToggle(!pushEnabled)}
                    className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${pushEnabled ? "bg-indigo-600" : "bg-slate-300"} ${pushLoading ? "opacity-50 cursor-wait" : ""}`}
                  >
                    {pushLoading ? (
                      <svg className="animate-spin h-4 w-4 text-white mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.4 0 0 5.4 0 12h4z" />
                      </svg>
                    ) : (
                      <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${pushEnabled ? "translate-x-6" : "translate-x-1"}`} />
                    )}
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
            )}
          </div>
          </div>
        </div>

        {/* 하단 버튼 (고정) */}
        <div className="p-4 sm:p-7 pt-0 shrink-0">
          {!isLastStep ? (
            <button
              onClick={goNext}
              disabled={!canNext()}
              className={`w-full py-4 text-white rounded-xl font-bold text-base transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed shadow-lg ${theme.btn}`}
            >
              다음
            </button>
          ) : (
            <button
              onClick={handleSave}
              disabled={loading}
              className={`w-full py-4 text-white rounded-xl font-bold text-base transition-all active:scale-[0.98] disabled:opacity-50 shadow-lg ${theme.btn}`}
            >
              {loading ? "설정 중..." : "맞춤 알림 설정 완료"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
