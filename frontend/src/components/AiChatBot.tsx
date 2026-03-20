"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useToast } from "@/components/ui/Toast";

const API = process.env.NEXT_PUBLIC_API_URL;

interface RelatedAnnouncement {
  announcement_id: number;
  title: string;
  support_amount?: string;
  deadline_date?: string;
  department?: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  choices?: string[];
  announcements?: RelatedAnnouncement[];
  done?: boolean;
}

type ChatMode = "select" | "free" | "consultant";
type ConsultantTab = "chat" | "form";

// 업종 옵션
const INDUSTRY_OPTIONS = [
  { code: "62010", label: "IT/소프트웨어" },
  { code: "56111", label: "음식점/외식업" },
  { code: "47190", label: "소매/유통" },
  { code: "10000", label: "제조업(식품)" },
  { code: "26000", label: "제조업(전자)" },
  { code: "20000", label: "제조업(화학/화장품)" },
  { code: "25000", label: "제조업(금속/가공)" },
  { code: "29000", label: "제조업(자동차)" },
  { code: "41000", label: "건설업" },
  { code: "55000", label: "숙박/관광" },
  { code: "85000", label: "교육서비스" },
  { code: "70000", label: "전문서비스/컨설팅" },
  { code: "74000", label: "디자인" },
  { code: "71000", label: "광고/마케팅" },
  { code: "86000", label: "의료/헬스케어" },
  { code: "46000", label: "도매/무역" },
  { code: "49000", label: "물류/운송" },
  { code: "96000", label: "미용/뷰티/생활서비스" },
  { code: "90000", label: "공연/문화/예술" },
];

const REVENUE_OPTIONS = ["1억 미만", "1억~5억", "5억~10억", "10억~50억", "50억 이상"];
const EMPLOYEE_OPTIONS = ["5인 미만", "5인~10인", "10인~30인", "30인~50인", "50인 이상"];
const CITY_OPTIONS = ["전국", "서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"];
const INTEREST_OPTIONS = ["창업지원", "기술개발", "수출마케팅", "고용지원", "시설개선", "정책자금", "디지털전환", "판로개척", "교육훈련", "에너지환경", "소상공인", "R&D"];

interface FormProfile {
  company_name: string;
  establishment_date: string;
  industry_code: string;
  revenue_bracket: string;
  employee_count_bracket: string;
  address_city: string;
  interests: string[];
}

const EMPTY_FORM: FormProfile = {
  company_name: "",
  establishment_date: "",
  industry_code: "",
  revenue_bracket: "",
  employee_count_bracket: "",
  address_city: "",
  interests: [],
};

export default function AiChatBot() {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<ChatMode>("select");
  const [consultantTab, setConsultantTab] = useState<ConsultantTab>("form");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [consultantProfile, setConsultantProfile] = useState<Record<string, any> | null>(null);
  const [matchingInProgress, setMatchingInProgress] = useState(false);
  const [formProfile, setFormProfile] = useState<FormProfile>({ ...EMPTY_FORM });
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  // 이벤트 리스너: 메인 화면에서 챗봇 열기
  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener("open-ai-chatbot", handler);
    return () => window.removeEventListener("open-ai-chatbot", handler);
  }, []);

  // 모달 열리면 모드 선택 화면
  useEffect(() => {
    if (open && mode === "select" && messages.length === 0) {
      // 모드 선택 화면은 messages를 비운 채로 유지
    }
  }, [open, mode, messages.length]);

  // 스크롤 하단 유지
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  // 로그인된 사용자 프로필 가져오기
  const fetchUserProfile = async (): Promise<Record<string, any> | null> => {
    const token = localStorage.getItem("auth_token");
    if (!token) return null;
    try {
      const res = await fetch(`${API}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        return data.user || null;
      }
    } catch {}
    return null;
  };

  // 프로필 요약 텍스트 생성
  const buildProfileSummary = (user: Record<string, any>) => {
    const parts: string[] = [];
    if (user.company_name) parts.push(`기업명: ${user.company_name}`);
    if (user.industry_name || user.industry_code) parts.push(`업종: ${user.industry_name || `KSIC ${user.industry_code}`}`);
    if (user.address_city) parts.push(`관심지역: ${user.address_city}`);
    if (user.revenue_bracket) parts.push(`매출: ${user.revenue_bracket}`);
    if (user.employee_count_bracket) parts.push(`직원수: ${user.employee_count_bracket}`);
    if (user.establishment_date) {
      const years = Math.floor((Date.now() - new Date(user.establishment_date).getTime()) / (365.25 * 24 * 60 * 60 * 1000));
      parts.push(`설립: ${user.establishment_date} (${years}년차)`);
    }
    return parts.join(" | ");
  };

  // 모드 시작
  const startMode = async (selectedMode: "free" | "consultant") => {
    setMode(selectedMode);
    setMessages([]);
    setConsultantProfile(null);
    setFormProfile({ ...EMPTY_FORM });

    if (selectedMode === "free") {
      // 자유 상담: 중소기업 지원사업 전반에 대한 자유 질의응답
      setMessages([{
        role: "assistant",
        text: "안녕하세요! 중소기업 지원사업 전문 AI 상담사입니다.\n\n지원사업 종류, 신청 자격, 절차, 지원 규모 등 궁금한 점을 자유롭게 질문해 주세요.",
        choices: ["R&D 지원사업 종류 알려줘", "소상공인 지원사업 뭐가 있어?", "창업 지원금 신청 방법은?", "정책자금 대출 조건이 궁금해"],
      }]);
    } else {
      // consultant: 로그인 프로필로 폼 사전 채움
      const user = await fetchUserProfile();
      if (user) {
        setFormProfile({
          company_name: user.company_name || "",
          establishment_date: user.establishment_date ? String(user.establishment_date).substring(0, 10) : "",
          industry_code: user.industry_code || "",
          revenue_bracket: user.revenue_bracket || "",
          employee_count_bracket: user.employee_count_bracket || "",
          address_city: user.address_city || "",
          interests: user.interests ? String(user.interests).split(",").filter(Boolean) : [],
        });
      }
      setConsultantTab("form");
    }
  };

  // 컨설턴트 대화 탭 전환 시 — 등록 프로필 요약 포함
  const switchToConsultantChat = async () => {
    setConsultantTab("chat");
    if (messages.length === 0) {
      const user = await fetchUserProfile();
      if (user && user.company_name) {
        const summary = buildProfileSummary(user);
        setMessages([{
          role: "assistant",
          text: `AI 컨설턴트 모드입니다.\n\n**현재 등록된 기업 정보:**\n${summary}\n\n이 정보를 기반으로 매칭할까요? 아니면 다른 고객사 정보를 입력하시겠습니까?`,
          choices: ["이 정보로 매칭해줘", "다른 고객사 정보를 입력할게요", "추가 정보를 더 알려줄게"],
        }]);
      } else {
        setMessages([{
          role: "assistant",
          text: "AI 컨설턴트 모드입니다.\n\n고객사의 기업 조건을 대화로 알려주시면, 맞춤 지원사업을 매칭해 드립니다.\n\n시작하시겠습니까?",
          choices: ["네, 시작할게요", "어떤 정보가 필요한가요?"],
        }]);
      }
    }
  };

  // 자유 상담 API 호출
  const sendToFreeChat = useCallback(async (chatHistory: ChatMessage[]) => {
    setLoading(true);
    const token = localStorage.getItem("auth_token");

    try {
      const res = await fetch(`${API}/api/ai/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          messages: chatHistory.map((m) => ({ role: m.role, text: m.text })),
        }),
      });

      if (res.status === 429) {
        toast("이번 달 AI 사용 한도를 모두 사용했습니다.", "error");
        setLoading(false);
        return;
      }
      if (res.status === 403) {
        toast("플랜이 만료되었습니다. 업그레이드 후 이용해 주세요.", "error");
        setOpen(false);
        setLoading(false);
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast(err.detail || "AI 응답 오류가 발생했습니다.", "error");
        setLoading(false);
        return;
      }

      const data = await res.json();
      const aiMsg: ChatMessage = {
        role: "assistant",
        text: data.reply || "응답을 처리할 수 없습니다.",
        choices: data.choices || [],
        announcements: data.announcements || [],
        done: data.done || false,
      };

      setMessages([...chatHistory, aiMsg]);
    } catch {
      toast("서버 연결에 실패했습니다.", "error");
    }
    setLoading(false);
  }, [toast]);

  // 컨설턴트 모드 API 호출
  const sendToConsultantChat = useCallback(async (chatHistory: ChatMessage[]) => {
    setLoading(true);
    const token = localStorage.getItem("auth_token");

    try {
      const res = await fetch(`${API}/api/ai/consultant/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          messages: chatHistory.map((m) => ({ role: m.role, text: m.text })),
        }),
      });

      if (res.status === 429) {
        toast("이번 달 AI 사용 한도를 모두 사용했습니다.", "error");
        setLoading(false);
        return;
      }
      if (res.status === 403) {
        toast("플랜이 만료되었습니다.", "error");
        setLoading(false);
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast(err.detail || "AI 응답 오류가 발생했습니다.", "error");
        setLoading(false);
        return;
      }

      const data = await res.json();

      // 조건 수집 완료 → 프로필 저장
      if (data.done && data.profile) {
        setConsultantProfile(data.profile);
      }

      const aiMsg: ChatMessage = {
        role: "assistant",
        text: data.reply || "응답을 처리할 수 없습니다.",
        choices: data.done && data.profile ? [] : (data.choices || []),
        done: data.done || false,
      };

      setMessages([...chatHistory, aiMsg]);

      // 프로필 수집 완료 → 자동으로 매칭 실행
      if (data.done && data.profile) {
        executeMatching(data.profile, [...chatHistory, aiMsg]);
      }
    } catch {
      toast("서버 연결에 실패했습니다.", "error");
    }
    setLoading(false);
  }, [toast]);

  // 매칭 실행
  const executeMatching = async (profile: Record<string, any>, currentMessages: ChatMessage[]) => {
    setMatchingInProgress(true);
    const token = localStorage.getItem("auth_token");

    // 매칭 중 안내 메시지
    setMessages([...currentMessages, {
      role: "assistant",
      text: "조건 수집이 완료되었습니다! 맞춤 지원사업을 매칭 중입니다...",
    }]);

    try {
      const res = await fetch(`${API}/api/ai/consultant/match`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ profile }),
      });

      if (res.status === 429) {
        toast("이번 달 AI 사용 한도를 모두 사용했습니다.", "error");
        setMatchingInProgress(false);
        return;
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast(err.detail || "매칭 실행 중 오류가 발생했습니다.", "error");
        setMatchingInProgress(false);
        return;
      }

      const data = await res.json();
      const matchCount = data.matches?.length || 0;

      // 대시보드로 결과 전송
      window.dispatchEvent(new CustomEvent("consultant-match-result", {
        detail: {
          matches: data.matches || [],
          profile: profile,
        }
      }));

      // 완료 메시지
      setMessages([...currentMessages, {
        role: "assistant",
        text: `매칭이 완료되었습니다!\n\n**${profile.company_name || "고객사"}** 조건으로 **${matchCount}건**의 맞춤 지원사업을 찾았습니다.\n\n대시보드에서 매칭 결과를 확인해 주세요.${matchCount > 0 ? "\n각 공고를 클릭하면 상세 자격요건 상담도 받으실 수 있습니다." : ""}`,
        choices: matchCount > 0 ? ["대시보드에서 결과 확인", "다른 조건으로 다시 매칭"] : ["다른 조건으로 다시 매칭"],
      }]);

      toast(`${matchCount}건의 맞춤 지원사업을 찾았습니다!`, "success");
    } catch {
      toast("매칭 실행 중 오류가 발생했습니다.", "error");
    }
    setMatchingInProgress(false);
  };

  const handleSend = (text: string) => {
    if (!text.trim() || loading || matchingInProgress) return;

    // 특수 선택지 처리
    if (mode === "consultant" && text === "대시보드에서 결과 확인") {
      setOpen(false);
      return;
    }
    if (mode === "consultant" && text === "다른 조건으로 다시 매칭") {
      startMode("consultant");
      return;
    }

    const userMsg: ChatMessage = { role: "user", text: text.trim() };
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInput("");

    if (mode === "free") {
      sendToFreeChat(newHistory);
    } else if (mode === "consultant") {
      sendToConsultantChat(newHistory);
    }
  };

  const handleClose = () => {
    setOpen(false);
    setMode("select");
    setMessages([]);
    setConsultantProfile(null);
    setFormProfile({ ...EMPTY_FORM });
    setConsultantTab("form");
  };

  const handleReset = () => {
    setMode("select");
    setMessages([]);
    setConsultantProfile(null);
    setFormProfile({ ...EMPTY_FORM });
    setConsultantTab("form");
  };

  // 폼 필드 업데이트
  const updateForm = (field: keyof FormProfile, value: string | string[]) => {
    setFormProfile((prev) => ({ ...prev, [field]: value }));
  };

  // 관심분야 토글
  const toggleInterest = (interest: string) => {
    setFormProfile((prev) => {
      const interests = prev.interests.includes(interest)
        ? prev.interests.filter((i) => i !== interest)
        : [...prev.interests, interest];
      return { ...prev, interests };
    });
  };

  // 폼 유효성 검사
  const isFormValid = () => {
    return (
      formProfile.company_name.trim() &&
      formProfile.establishment_date &&
      formProfile.industry_code &&
      formProfile.revenue_bracket &&
      formProfile.employee_count_bracket &&
      formProfile.address_city &&
      formProfile.interests.length > 0
    );
  };

  // 폼에서 직접 매칭 실행
  const handleFormSubmit = () => {
    if (!isFormValid()) {
      toast("모든 항목을 입력해 주세요.", "error");
      return;
    }
    const profile = {
      ...formProfile,
      interests: formProfile.interests.join(","),
    };
    executeMatching(profile, [{
      role: "assistant" as const,
      text: `**${profile.company_name}** 기업 정보로 매칭을 시작합니다.`,
    }]);
  };

  // 공고 상세 상담으로 이동
  const openConsult = (ann: RelatedAnnouncement) => {
    window.dispatchEvent(new CustomEvent("open-ai-consult", {
      detail: { announcement: ann }
    }));
  };

  if (!open) {
    // 플로팅 버튼
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 w-14 h-14 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full shadow-lg hover:shadow-xl transition-all active:scale-95 flex items-center justify-center group"
        title="AI 상담"
      >
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
        <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-400 rounded-full animate-pulse" />
      </button>
    );
  }

  // 모드 선택 헤더 색상
  const headerGradient = mode === "consultant"
    ? "from-violet-600 to-purple-600"
    : "from-indigo-600 to-violet-600";

  const headerTitle = mode === "consultant" ? "AI 컨설턴트" : mode === "free" ? "자유 상담" : "AI 서비스";
  const headerSub = mode === "consultant" ? "고객사 맞춤 매칭" : mode === "free" ? "지원사업 Q&A" : "모드를 선택하세요";

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-2">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={handleClose} />

      <div className="relative w-full sm:max-w-2xl h-full sm:h-[96vh] bg-white sm:rounded-2xl shadow-2xl border border-white/60 overflow-hidden flex flex-col animate-in slide-in-from-bottom sm:zoom-in-95 duration-300">

        {/* Header */}
        <div className={`relative z-10 px-4 py-3 border-b border-slate-100 bg-gradient-to-r ${headerGradient} flex-shrink-0`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center flex-shrink-0">
                {mode === "consultant" ? (
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9zm3.75 11.625a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                  </svg>
                )}
              </div>
              <div className="min-w-0">
                <p className="text-[13px] font-bold text-white">{headerTitle}</p>
                <p className="text-[10px] text-white/70 font-medium">{headerSub}</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={handleReset} className="p-1.5 hover:bg-white/20 rounded-lg transition-all" title="처음으로">
                <svg className="w-4 h-4 text-white/80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
                </svg>
              </button>
              <button onClick={handleClose} className="p-1.5 hover:bg-white/20 rounded-lg transition-all">
                <svg className="w-4 h-4 text-white/80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Mode Selection Screen */}
        {mode === "select" ? (
          <div className="flex-1 flex flex-col items-center justify-center px-6 gap-4 overflow-y-auto py-6">
            <div className="text-center mb-1">
              <p className="text-lg font-bold text-slate-800 mb-1">AI 서비스를 선택하세요</p>
              <p className="text-[12px] text-slate-500">원하시는 서비스를 선택해 주세요</p>
            </div>

            <button
              onClick={() => startMode("free")}
              className="w-full max-w-xs p-4 bg-gradient-to-br from-indigo-50 to-blue-50 border-2 border-indigo-200 rounded-2xl hover:border-indigo-400 hover:shadow-lg transition-all active:scale-[0.98] group text-left"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 bg-indigo-100 rounded-xl flex items-center justify-center group-hover:bg-indigo-200 transition-colors">
                  <svg className="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                </div>
                <div>
                  <p className="text-[14px] font-bold text-indigo-800">자유 상담</p>
                  <p className="text-[11px] text-indigo-600 font-medium">지원사업 Q&A</p>
                </div>
              </div>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                지원사업 종류, 신청 자격, 절차, 지원 규모 등<br />궁금한 점을 자유롭게 질문하세요.
              </p>
            </button>

            <button
              onClick={() => startMode("consultant")}
              className="w-full max-w-xs p-4 bg-gradient-to-br from-violet-50 to-purple-50 border-2 border-violet-200 rounded-2xl hover:border-violet-400 hover:shadow-lg transition-all active:scale-[0.98] group text-left"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 bg-violet-100 rounded-xl flex items-center justify-center group-hover:bg-violet-200 transition-colors">
                  <svg className="w-5 h-5 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9zm3.75 11.625a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
                  </svg>
                </div>
                <div>
                  <p className="text-[14px] font-bold text-violet-800">AI 컨설턴트</p>
                  <p className="text-[11px] text-violet-600 font-medium">고객사 맞춤 매칭</p>
                </div>
              </div>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                고객사의 기업 조건을 입력하면<br />맞춤 지원사업을 매칭해 드립니다.
              </p>
              <div className="mt-2 px-2 py-1 bg-violet-100 rounded-lg inline-block">
                <span className="text-[9px] font-bold text-violet-700">매칭 실행 시 AI 1건 차감</span>
              </div>
            </button>
          </div>
        ) : mode === "consultant" && consultantTab === "form" && !matchingInProgress && messages.length <= 1 ? (
          <>
            {/* Consultant Tab Toggle */}
            <div className="flex-shrink-0 px-4 pt-3 pb-1 border-b border-slate-100 bg-slate-50/80">
              <div className="flex gap-1 p-0.5 bg-slate-200/80 rounded-xl">
                <button
                  onClick={() => setConsultantTab("form")}
                  className="flex-1 py-1.5 text-[11px] font-bold rounded-lg transition-all bg-white text-violet-700 shadow-sm"
                >
                  직접 입력
                </button>
                <button
                  onClick={() => switchToConsultantChat()}
                  className="flex-1 py-1.5 text-[11px] font-bold rounded-lg transition-all text-slate-500 hover:text-slate-700"
                >
                  대화로 입력
                </button>
              </div>
            </div>

            {/* Direct Input Form */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
              {/* 기업명 */}
              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">기업명 <span className="text-red-400">*</span></label>
                <input
                  type="text"
                  value={formProfile.company_name}
                  onChange={(e) => updateForm("company_name", e.target.value)}
                  placeholder="예: (주)테스트기업"
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-[13px] text-slate-700 placeholder-slate-400 outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-300 transition-all"
                />
              </div>

              {/* 설립일 */}
              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">설립일 <span className="text-red-400">*</span></label>
                <input
                  type="date"
                  value={formProfile.establishment_date}
                  onChange={(e) => updateForm("establishment_date", e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-[13px] text-slate-700 outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-300 transition-all"
                />
              </div>

              {/* 업종 */}
              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">업종 <span className="text-red-400">*</span></label>
                <select
                  value={formProfile.industry_code}
                  onChange={(e) => updateForm("industry_code", e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-[13px] text-slate-700 outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-300 transition-all appearance-none"
                >
                  <option value="">업종을 선택하세요</option>
                  {INDUSTRY_OPTIONS.map((opt) => (
                    <option key={opt.code} value={opt.code}>{opt.label}</option>
                  ))}
                </select>
              </div>

              {/* 매출규모 & 직원수 (2열) */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">매출규모 <span className="text-red-400">*</span></label>
                  <select
                    value={formProfile.revenue_bracket}
                    onChange={(e) => updateForm("revenue_bracket", e.target.value)}
                    className="w-full px-2.5 py-2 bg-white border border-slate-200 rounded-xl text-[12px] text-slate-700 outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-300 transition-all appearance-none"
                  >
                    <option value="">선택</option>
                    {REVENUE_OPTIONS.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">직원수 <span className="text-red-400">*</span></label>
                  <select
                    value={formProfile.employee_count_bracket}
                    onChange={(e) => updateForm("employee_count_bracket", e.target.value)}
                    className="w-full px-2.5 py-2 bg-white border border-slate-200 rounded-xl text-[12px] text-slate-700 outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-300 transition-all appearance-none"
                  >
                    <option value="">선택</option>
                    {EMPLOYEE_OPTIONS.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* 관심지역 — 복수선택 */}
              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">
                  관심지역 <span className="text-red-400">*</span>
                  <span className="font-normal text-slate-400 ml-1">(복수 선택 가능)</span>
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {CITY_OPTIONS.map((city) => {
                    const isAll = city === "전국";
                    const cities = formProfile.address_city ? formProfile.address_city.split(",").filter(Boolean) : [];
                    const selected = isAll ? cities.includes("전국") : cities.includes(city);
                    return (
                      <button
                        key={city}
                        type="button"
                        onClick={() => {
                          if (isAll) {
                            updateForm("address_city", "전국");
                          } else {
                            const without = cities.filter(c => c !== "전국");
                            const next = selected ? without.filter(c => c !== city) : [...without, city];
                            updateForm("address_city", next.length === 0 ? "전국" : next.join(","));
                          }
                        }}
                        className={`px-2 py-1 rounded-lg text-[11px] font-semibold border transition-all active:scale-95 ${
                          selected
                            ? "bg-violet-600 text-white border-violet-600"
                            : "bg-white text-slate-600 border-slate-200 hover:border-violet-300"
                        }`}
                      >
                        {city}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 관심분야 (멀티셀렉트 칩) */}
              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1.5">
                  관심분야 <span className="text-red-400">*</span>
                  <span className="font-normal text-slate-400 ml-1">(복수 선택 가능)</span>
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {INTEREST_OPTIONS.map((interest) => (
                    <button
                      key={interest}
                      type="button"
                      onClick={() => toggleInterest(interest)}
                      className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-all active:scale-95 ${
                        formProfile.interests.includes(interest)
                          ? "bg-violet-600 text-white border-violet-600"
                          : "bg-white text-slate-600 border-slate-200 hover:border-violet-300 hover:text-violet-600"
                      }`}
                    >
                      {interest}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* 폼 제출 버튼 */}
            <div className="flex-shrink-0 border-t border-slate-100 bg-white px-4 py-3">
              <button
                onClick={handleFormSubmit}
                disabled={!isFormValid() || matchingInProgress}
                className="w-full py-2.5 bg-gradient-to-r from-violet-600 to-purple-600 text-white text-[13px] font-bold rounded-xl hover:from-violet-700 hover:to-purple-700 transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                </svg>
                맞춤 지원사업 매칭 실행
              </button>
              <p className="text-center text-[9px] text-slate-400 mt-1.5">매칭 실행 시 AI 1건이 차감됩니다</p>
            </div>
          </>
        ) : (
          <>
            {/* Consultant Tab Toggle (chat mode) */}
            {mode === "consultant" && !matchingInProgress && messages.length <= 1 && (
              <div className="flex-shrink-0 px-4 pt-3 pb-1 border-b border-slate-100 bg-slate-50/80">
                <div className="flex gap-1 p-0.5 bg-slate-200/80 rounded-xl">
                  <button
                    onClick={() => setConsultantTab("form")}
                    className={`flex-1 py-1.5 text-[11px] font-bold rounded-lg transition-all ${
                      consultantTab === "form"
                        ? "bg-white text-violet-700 shadow-sm"
                        : "text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    직접 입력
                  </button>
                  <button
                    onClick={() => setConsultantTab("chat")}
                    className={`flex-1 py-1.5 text-[11px] font-bold rounded-lg transition-all ${
                      consultantTab === "chat"
                        ? "bg-white text-violet-700 shadow-sm"
                        : "text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    대화로 입력
                  </button>
                </div>
              </div>
            )}

            {/* Chat area */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[88%] ${msg.role === "user" ? "order-1" : ""}`}>
                    {/* Message bubble */}
                    <div className={`px-3.5 py-2.5 rounded-2xl text-[13px] leading-relaxed whitespace-pre-wrap ${
                      msg.role === "user"
                        ? mode === "consultant" ? "bg-violet-600 text-white rounded-br-md" : "bg-indigo-600 text-white rounded-br-md"
                        : "bg-slate-100 text-slate-800 rounded-bl-md"
                    }`}>
                      {msg.text}
                    </div>

                    {/* Related announcements (free mode only) */}
                    {msg.role === "assistant" && msg.announcements && msg.announcements.length > 0 && (
                      <div className="mt-2 space-y-1.5">
                        <p className="text-[10px] font-semibold text-indigo-600 px-1">관련 공고</p>
                        {msg.announcements.map((ann) => (
                          <button
                            key={ann.announcement_id}
                            onClick={() => openConsult(ann)}
                            className="w-full text-left px-3 py-2 bg-indigo-50 border border-indigo-100 rounded-xl hover:bg-indigo-100 transition-all group"
                          >
                            <p className="text-[11px] font-semibold text-indigo-800 truncate group-hover:text-indigo-900">
                              {ann.title}
                            </p>
                            <div className="flex items-center gap-2 mt-0.5">
                              {ann.support_amount && (
                                <span className="text-[9px] text-indigo-600 font-medium">{ann.support_amount}</span>
                              )}
                              {ann.deadline_date && (
                                <span className="text-[9px] text-slate-500">마감: {ann.deadline_date}</span>
                              )}
                            </div>
                            <p className="text-[9px] text-indigo-500 mt-0.5">상세 상담 &rarr;</p>
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Choice buttons */}
                    {msg.role === "assistant" && msg.choices && msg.choices.length > 0 && i === messages.length - 1 && !loading && !matchingInProgress && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {msg.choices.map((choice, ci) => (
                          <button
                            key={ci}
                            onClick={() => handleSend(choice)}
                            disabled={loading || matchingInProgress}
                            className={`px-3 py-1.5 bg-white border rounded-full text-[11px] font-semibold transition-all active:scale-95 disabled:opacity-50 ${
                              mode === "consultant"
                                ? "border-violet-200 text-violet-700 hover:bg-violet-50 hover:border-violet-300"
                                : "border-indigo-200 text-indigo-700 hover:bg-indigo-50 hover:border-indigo-300"
                            }`}
                          >
                            {choice}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* Loading indicator */}
              {(loading || matchingInProgress) && (
                <div className="flex justify-start">
                  <div className="px-4 py-3 bg-slate-100 rounded-2xl rounded-bl-md">
                    <div className="flex items-center gap-2">
                      <div className={`w-4 h-4 border-2 border-t-transparent rounded-full animate-spin ${
                        mode === "consultant" ? "border-violet-400" : "border-indigo-400"
                      }`} />
                      <p className={`text-[12px] font-semibold ${mode === "consultant" ? "text-violet-600" : "text-indigo-600"}`}>
                        {matchingInProgress ? "맞춤 지원사업 매칭 중..." : mode === "consultant" ? "조건을 분석하고 있습니다..." : "지원사업 검색 중..."}
                      </p>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-1">
                      {matchingInProgress ? "수집한 조건으로 매칭 엔진을 실행하고 있습니다" : "AI가 응답을 생성하고 있습니다"}
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Input area */}
            <div className="flex-shrink-0 border-t border-slate-100 bg-white px-3 py-3">
              <div className="flex items-center gap-2">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                      e.preventDefault();
                      handleSend(input);
                    }
                  }}
                  placeholder={mode === "consultant" ? "고객사 정보를 입력하세요..." : "지원사업에 대해 자유롭게 질문하세요..."}
                  disabled={loading || matchingInProgress}
                  className={`flex-1 px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-[13px] text-slate-700 placeholder-slate-400 outline-none focus:ring-2 transition-all disabled:opacity-50 ${
                    mode === "consultant" ? "focus:ring-violet-200 focus:border-violet-300" : "focus:ring-indigo-200 focus:border-indigo-300"
                  }`}
                />
                <button
                  onClick={() => handleSend(input)}
                  disabled={loading || matchingInProgress || !input.trim()}
                  className={`p-2.5 text-white rounded-xl transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0 ${
                    mode === "consultant" ? "bg-violet-600 hover:bg-violet-700" : "bg-indigo-600 hover:bg-indigo-700"
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                  </svg>
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
