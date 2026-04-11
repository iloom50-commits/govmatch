"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useModalBack } from "@/hooks/useModalBack";
import { useToast } from "@/components/ui/Toast";
import DOMPurify from "dompurify";

const API = process.env.NEXT_PUBLIC_API_URL;

// FAB 버튼 + 라벨 (PRO 도구 항상 명시)
function FabWithBubble({ label, onClick, botPhase }: { label: string; onClick: () => void; botPhase: string }) {
  return (
    <div className="fixed bottom-24 right-6 z-40 flex items-center gap-2">
      {/* 항상 노출되는 라벨 — "전문가용 지원사업 상담 도구" */}
      <div className="hidden sm:flex items-center gap-1.5 px-3 py-2 bg-white border border-violet-200 rounded-full shadow-lg">
        <span className="text-[11px] font-bold text-violet-700">전문가용 지원사업 상담 도구</span>
        <span className="px-1.5 py-0.5 bg-gradient-to-r from-violet-600 to-purple-600 text-white text-[9px] font-black rounded-full">PRO</span>
      </div>
      <button
        onClick={onClick}
        className="relative w-14 h-14 bg-gradient-to-br from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white rounded-full shadow-xl hover:shadow-2xl transition-all active:scale-95 flex items-center justify-center"
        style={botPhase === "return" ? { animation: "btnAbsorb 1.5s 1.5s ease-out forwards" } : undefined}
        title={label}
        aria-label="전문가용 지원사업 상담 도구 (PRO)"
      >
        <span className="text-2xl animate-ai-pulse">✨</span>
        {/* 모바일용 - 작은 PRO 뱃지 */}
        <span className="sm:hidden absolute -top-1 -right-1 px-1 py-0.5 bg-white text-violet-700 text-[8px] font-black rounded-full border border-violet-200 shadow">PRO</span>
      </button>
    </div>
  );
}

/** 마크다운 → 보고서 스타일 HTML 변환 */
function renderMarkdown(text: string): string {
  // 0) (None) 링크 패턴 제거
  text = text.replace(/\(\[.*?\]\(None\)\)/g, "").replace(/\[.*?\]\(None\)/g, "");

  // 1) 이스케이프
  let html = text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // 2) 인라인: bold, 이모지 보존
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="text-slate-900 font-semibold">$1</strong>');

  const lines = html.split("\n");
  const result: string[] = [];
  let listType: "ul" | "ol" | null = null;

  const closeList = () => {
    if (listType) { result.push(listType === "ol" ? "</ol>" : "</ul>"); listType = null; }
  };

  for (const line of lines) {
    const trimmed = line.trim();

    // 번호 리스트: 1. or 1) — 공고 항목 등
    const olMatch = trimmed.match(/^(\d+)[.\)]\s+(.*)/);
    // 불릿 리스트: * or - (앞에 공백 허용)
    const ulMatch = !olMatch && trimmed.match(/^[*\-•]\s+(.*)/);

    if (olMatch) {
      if (listType !== "ol") { closeList(); result.push('<ol class="ml-4 mt-2 mb-2 space-y-1.5 list-decimal list-outside">'); listType = "ol"; }
      result.push(`<li class="text-slate-700 leading-relaxed">${olMatch[2]}</li>`);
    } else if (ulMatch) {
      if (listType !== "ul") { closeList(); result.push('<ul class="ml-4 mt-1 mb-1 space-y-1 list-disc list-outside">'); listType = "ul"; }
      result.push(`<li class="text-slate-700 leading-relaxed">${ulMatch[1]}</li>`);
    } else {
      closeList();
      // 섹션 제목: bold만으로 구성된 줄
      if (/^<strong.*<\/strong>[:\s]*$/.test(trimmed) || /^#{1,3}\s/.test(trimmed)) {
        const title = trimmed.replace(/^#{1,3}\s/, "");
        result.push(`<div class="mt-4 mb-1.5 pb-1 border-b border-indigo-100 text-[13px] font-bold text-indigo-700">${title}</div>`);
      } else if (trimmed === "") {
        result.push('<div class="h-1.5"></div>');
      } else {
        result.push(`<p class="text-slate-700 leading-relaxed mb-1">${trimmed}</p>`);
      }
    }
  }
  closeList();
  return result.join("");
}

interface RelatedAnnouncement {
  announcement_id: number;
  title: string;
  support_amount?: string;
  deadline_date?: string;
  department?: string;
  category?: string;
  summary_text?: string;
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
const INDIVIDUAL_INTEREST_OPTIONS = ["취업", "주거", "교육", "청년", "출산", "육아", "다자녀", "장학금", "의료", "장애", "저소득", "노인", "문화"];

interface FormProfile {
  company_name: string;
  establishment_date: string;
  industry_code: string;
  revenue_bracket: string;
  employee_count_bracket: string;
  address_city: string;
  interests: string[];
  _interestInput?: string;
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

interface AiChatBotProps {
  planStatus?: { plan: string; ai_limit?: number; consult_limit?: number } | null;
  onUpgrade?: () => void;
  userType?: string | null;
}

export default function AiChatBot({ planStatus, onUpgrade, userType }: AiChatBotProps) {
  const isIndividual = userType === "individual";
  const isPro = planStatus && ["pro", "biz"].includes(planStatus.plan);
  const [open, setOpen] = useState(false);
  useModalBack(open, () => setOpen(false));
  const [mode, setMode] = useState<ChatMode>("select");
  const [consultantTab, setConsultantTab] = useState<ConsultantTab>("form");
  const [clientCategory, setClientCategory] = useState<"" | "individual_biz" | "corporate" | "individual" | "unknown">("");
  const [selectedExistingClient, setSelectedExistingClient] = useState<number | null>(null);
  const [existingClients, setExistingClients] = useState<any[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [consultantProfile, setConsultantProfile] = useState<Record<string, any> | null>(null);
  const [matchingInProgress, setMatchingInProgress] = useState(false);
  const [formProfile, setFormProfile] = useState<FormProfile>({ ...EMPTY_FORM });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 드래그 이동
  const [dragPos, setDragPos] = useState<{ x: number; y: number } | null>(null);
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    const panel = e.currentTarget.closest("[data-chat-panel]") as HTMLElement;
    if (!panel) return;
    const rect = panel.getBoundingClientRect();
    dragRef.current = { startX: e.clientX, startY: e.clientY, origX: rect.left, origY: rect.top };
    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      const dx = ev.clientX - dragRef.current.startX;
      const dy = ev.clientY - dragRef.current.startY;
      setDragPos({ x: dragRef.current.origX + dx, y: dragRef.current.origY + dy });
    };
    const onUp = () => {
      dragRef.current = null;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, []);
  const inputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  // 이벤트 리스너: 메인 화면에서 챗봇 열기
  useEffect(() => {
    const handler = () => { setOpen(true); setDragPos(null); };
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

  // 공고 AI 상담 결과 수신 → 고객사 상담 컨텍스트에 추가
  useEffect(() => {
    const handler = (e: Event) => {
      if (mode !== "consultant" || !open) return;
      const detail = (e as CustomEvent).detail;
      if (detail?.title && detail?.summary) {
        setMessages(prev => [...prev, {
          role: "assistant",
          text: `📋 **공고 상담 결과가 반영되었습니다.**\n\n**${detail.title}**\n${detail.summary.substring(0, 300)}...\n\n이 결과를 바탕으로 추가 상담을 진행할까요?`,
          choices: ["다른 공고도 상담해줘", "이 고객 보고서 작성해줘", "직접 질문할게요"],
        }]);
        // 컨텍스트에 추가
        setFormProfile(prev => ({
          ...prev,
          _systemContext: `${(prev as any)?._systemContext || ""}\n\n[공고 상담 결과: ${detail.title}]\n${detail.summary.substring(0, 1000)}`,
        } as any));
      }
    };
    window.addEventListener("consult-result", handler);
    return () => window.removeEventListener("consult-result", handler);
  }, [mode, open]);

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
      setMessages([{
        role: "assistant",
        text: isIndividual
          ? "안녕하세요! 정부 지원사업 AI 상담사입니다.\n\n개인 복지·지원금, 청년 정책, 주거·취업 지원 등 궁금한 점을 자유롭게 질문해 주세요."
          : "안녕하세요! 중소기업 지원사업 전문 AI 상담사입니다.\n\n지원사업 종류, 신청 자격, 절차, 지원 규모 등 궁금한 점을 자유롭게 질문해 주세요.",
        choices: isIndividual
          ? ["청년 지원금 종류 알려줘", "주거 지원 뭐가 있어?", "취업 지원 프로그램 추천해줘", "출산·육아 혜택 알려줘"]
          : ["R&D 지원사업 종류 알려줘", "소상공인 지원사업 뭐가 있어?", "창업 지원금 신청 방법은?", "정책자금 대출 조건이 궁금해"],
      }]);
    } else {
      // consultant: 고객 유형 선택 화면 먼저 표시
      setClientCategory("");
      setSelectedExistingClient(null);
      setConsultantTab("form");
      // 기존 고객 목록 로드
      try {
        const token = localStorage.getItem("auth_token") || "";
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/pro/clients`, {
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        });
        if (res.ok) {
          const data = await res.json();
          setExistingClients(data.clients || []);
        }
      } catch { /* */ }
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
          text: isIndividual
            ? `개인 상담 에이전트 모드입니다.\n\n**현재 등록된 정보:**\n${summary}\n\n이 정보를 기반으로 매칭할까요? 아니면 다른 고객 정보를 입력하시겠습니까?`
            : `고객사별 상담/관리 AI에이전트 모드입니다.\n\n**현재 등록된 기업 정보:**\n${summary}\n\n이 정보를 기반으로 매칭할까요? 아니면 다른 고객사 정보를 입력하시겠습니까?`,
          choices: isIndividual
            ? ["이 정보로 매칭해줘", "다른 고객 정보를 입력할게요", "추가 정보를 더 알려줄게"]
            : ["이 정보로 매칭해줘", "다른 고객사 정보를 입력할게요", "추가 정보를 더 알려줄게"],
        }]);
      } else {
        setMessages([{
          role: "assistant",
          text: isIndividual
            ? "개인 상담 에이전트 모드입니다.\n\n고객의 조건(이름, 나이, 거주지, 관심분야)을 대화로 알려주시면, 맞춤 복지·지원사업을 매칭해 드립니다.\n\n시작하시겠습니까?"
            : "고객사별 상담/관리 AI에이전트 모드입니다.\n\n고객사의 기업 조건을 대화로 알려주시면, 맞춤 지원사업을 매칭해 드립니다.\n\n시작하시겠습니까?",
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
        toast("이번 달 무료 상담 횟수를 모두 사용했어요. 업그레이드하면 더 많이 이용할 수 있습니다!", "info");
        setLoading(false);
        return;
      }
      if (res.status === 403) {
        toast("결제 서비스가 곧 시작됩니다. 조금만 기다려 주세요!", "info");
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
      const announcements = data.announcements || [];
      const aiMsg: ChatMessage = {
        role: "assistant",
        text: data.reply || "응답을 처리할 수 없습니다.",
        choices: data.choices || [],
        announcements,
        done: data.done || false,
      };

      setMessages([...chatHistory, aiMsg]);

      // 관련 공고가 있으면 메인 대시보드에도 표시
      if (announcements.length > 0) {
        window.dispatchEvent(new CustomEvent("consultant-match-result", {
          detail: { matches: announcements, profile: null }
        }));
      }
    } catch {
      toast("서버 연결에 실패했습니다.", "error");
    }
    setLoading(false);
  }, [toast]);

  // 컨설턴트 모드 API 호출
  const sendToConsultantChat = useCallback(async (chatHistory: ChatMessage[]) => {
    setLoading(true);
    const token = localStorage.getItem("auth_token");
    const sysCtx = (formProfile as any)?._systemContext || "";

    try {
      const res = await fetch(`${API}/api/ai/consultant/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          messages: chatHistory.map((m, i) => ({
            role: m.role,
            text: (i === 0 && m.role === "user" && sysCtx) ? `${sysCtx}\n\n${m.text}` : m.text,
          })),
        }),
      });

      if (res.status === 429) {
        toast("이번 달 무료 상담 횟수를 모두 사용했어요. 업그레이드하면 더 많이 이용할 수 있습니다!", "info");
        setLoading(false);
        return;
      }
      if (res.status === 403) {
        toast("결제 서비스가 곧 시작됩니다. 조금만 기다려 주세요!", "info");
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
        toast("이번 달 무료 상담 횟수를 모두 사용했어요. 업그레이드하면 더 많이 이용할 수 있습니다!", "info");
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
        text: `매칭이 완료되었습니다!\n\n**${profile.company_name || (isIndividual ? "고객" : "고객사")}** 조건으로 **${matchCount}건**의 맞춤 ${isIndividual ? "복지·지원사업" : "지원사업"}을 찾았습니다.\n\n대시보드에서 매칭 결과를 확인해 주세요.${matchCount > 0 ? "\n각 공고를 클릭하면 상세 자격요건 상담도 받으실 수 있습니다." : ""}`,
        choices: matchCount > 0 ? ["대시보드에서 결과 확인", "다른 조건으로 다시 매칭"] : ["다른 조건으로 다시 매칭"],
      }]);

      toast(`${matchCount}건의 맞춤 지원사업을 찾았습니다!`, "success");
    } catch {
      toast("매칭 실행 중 오류가 발생했습니다.", "error");
    }
    setMatchingInProgress(false);
  };

  const CONSULT_MSG_LIMIT = 50;
  const userMsgCount = messages.filter((m) => m.role === "user").length;
  const isAtMsgLimit = userMsgCount >= CONSULT_MSG_LIMIT;

  // 파일 첨부 처리 (클릭 + 드래그&드롭 공용)
  const handleFileAttach = async (file: File) => {
    if (file.size > 10 * 1024 * 1024) { toast("10MB 이하만 가능", "error"); return; }
    const token = localStorage.getItem("auth_token") || "";

    setMessages(prev => [...prev, { role: "user", text: `📎 ${file.name} 첨부` }]);
    setLoading(true);

    try {
      const text = await new Promise<string>((resolve) => {
        const reader = new FileReader();
        reader.onload = () => resolve((reader.result as string || "").substring(0, 8000));
        reader.onerror = () => resolve("");
        reader.readAsText(file);
      });

      const analyzeRes = await fetch(`${API}/api/pro/files/analyze`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.substring(0, 8000), file_name: file.name, file_type: "other" }),
      });
      const analyzeData = analyzeRes.ok ? await analyzeRes.json() : { summary: "분석 실패" };

      setMessages(prev => [...prev, {
        role: "assistant",
        text: `📊 **${file.name}** 분석 결과:\n\n${analyzeData.summary}\n\n이 정보를 바탕으로 어떤 상담을 원하시나요?`,
        choices: ["이 고객에 맞는 지원사업 찾아줘", "자격요건 판단해줘", "추가 자료를 올릴게요", "직접 질문할게요"],
      }]);

      setFormProfile(prev => ({
        ...prev,
        _systemContext: `${(prev as any)?._systemContext || ""}\n\n[첨부: ${file.name}]\n${text.substring(0, 5000)}`,
        _attachedText: text.substring(0, 5000),
      } as any));
    } catch {
      setMessages(prev => [...prev, { role: "assistant", text: "파일 분석에 실패했습니다. 다시 시도해 주세요." }]);
    }
    setLoading(false);
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

    // 메시지 한도 체크 (공고AI 상담 모드)
    if (mode !== "free" && userMsgCount >= CONSULT_MSG_LIMIT) {
      toast(`상담 메시지 한도(${CONSULT_MSG_LIMIT}회)를 초과했습니다.`, "error");
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
    setIsFullscreen(false);
    setIsDone(false);
    setShowReport(false);
  };

  const handleReset = () => {
    setMode("select");
    setMessages([]);
    setConsultantProfile(null);
    setFormProfile({ ...EMPTY_FORM });
    setConsultantTab("form");
    setIsFullscreen(false);
    setIsDone(false);
    setShowReport(false);
  };

  // 상담 종료 → 보고서 생성
  const handleEndConsultation = () => {
    setIsDone(true);
    const endMsg: ChatMessage = {
      role: "assistant",
      text: "상담이 종료되었습니다. 상담 보고서를 확인하시려면 아래 버튼을 눌러주세요.",
      choices: [],
      done: true,
    };
    setMessages((prev) => [...prev, endMsg]);
  };

  // 보고서 HTML 생성
  const generateReportHtml = () => {
    const now = new Date().toLocaleString("ko-KR");
    const modeLabel = mode === "consultant" ? "고객사 매칭 상담" : "지원사업 상담";
    const convHtml = messages
      .filter((m) => !m.done && m.text)
      .map((m) => {
        if (m.role === "user") {
          return `<div style="margin:12px 0;padding:10px 14px;background:#f0f4ff;border-radius:10px;border-left:3px solid #6366f1"><strong style="color:#4f46e5">Q.</strong> ${m.text.replace(/</g, "&lt;")}</div>`;
        }
        const html = renderMarkdown(m.text);
        return `<div style="margin:12px 0;padding:10px 14px;background:#fafafa;border-radius:10px;border-left:3px solid #10b981"><strong style="color:#059669">A.</strong> <div style="margin-top:6px">${html}</div></div>`;
      })
      .join("");

    return `<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>상담 보고서</title>
<style>body{font-family:-apple-system,sans-serif;max-width:800px;margin:0 auto;padding:20px;color:#1e293b}
h1{font-size:20px;border-bottom:2px solid #6366f1;padding-bottom:8px}
.meta{color:#64748b;font-size:13px;margin-bottom:20px}
@media print{body{padding:10px}}</style></head><body>
<h1>${modeLabel} 보고서</h1>
<div class="meta">${now}</div>
${convHtml}
<div style="margin-top:30px;padding-top:15px;border-top:1px solid #e2e8f0;color:#94a3b8;font-size:11px;text-align:center">지원금AI AI 상담 보고서 · govmatch.kr</div>
</body></html>`;
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
    if (isIndividual) {
      return (
        formProfile.company_name.trim() &&
        formProfile.establishment_date &&
        formProfile.address_city &&
        formProfile.interests.length > 0
      );
    }
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
      industry_code: isIndividual ? "" : formProfile.industry_code,
      revenue_bracket: isIndividual ? "1억 미만" : formProfile.revenue_bracket,
      employee_count_bracket: isIndividual ? "5인 미만" : formProfile.employee_count_bracket,
      interests: formProfile.interests.join(","),
    };
    executeMatching(profile, [{
      role: "assistant" as const,
      text: isIndividual
        ? `**${profile.company_name}**님 조건으로 맞춤 지원사업 매칭을 시작합니다.`
        : `**${profile.company_name}** 기업 정보로 매칭을 시작합니다.`,
    }]);
  };

  // 공고로 이동 — 채팅 닫고 메인 화면에서 해당 공고 하이라이트
  const goToAnnouncement = (ann: RelatedAnnouncement) => {
    setOpen(false);
    // 메인 화면에 공고 하이라이트 이벤트 전달
    window.dispatchEvent(new CustomEvent("highlight-announcement", {
      detail: { announcement_id: ann.announcement_id, title: ann.title }
    }));
  };

  // AI봇: 브랜드 알에서 깨고 등장 → 오른쪽으로 걸어감 → 책상 작업 → 왼쪽 복귀
  const [botPhase, setBotPhase] = useState<"idle" | "crack" | "emerge" | "walk" | "work" | "return" | "done">("idle");
  useEffect(() => {
    if (open) { setBotPhase("idle"); return; }
    const timers: ReturnType<typeof setTimeout>[] = [];
    const startBot = () => {
      // 1. 브랜드 알이 흔들리며 금이 감 (0~1.5s)
      setBotPhase("crack");
      // 2. 봇 알에서 등장 (1.5~2.5s)
      timers.push(setTimeout(() => setBotPhase("emerge"), 1500));
      // 3. 오른쪽으로 천천히 걸어감 (2.5~8s)
      timers.push(setTimeout(() => setBotPhase("walk"), 2500));
      // 4. 책상에 앉아서 오래 작업 (8~28s)
      timers.push(setTimeout(() => setBotPhase("work"), 8000));
      // 5. 플로팅 버튼으로 걸어가서 흡수 (28~31s)
      timers.push(setTimeout(() => setBotPhase("return"), 28000));
      // 6. 완료 — 달걀 숨김 유지
      timers.push(setTimeout(() => setBotPhase("done"), 31500));
    };
    timers.push(setTimeout(startBot, 4000));
    return () => { timers.forEach(clearTimeout); };
  }, [open]);

  /* 하이테크 미래형 SVG 미니 AI봇 — 정면 서 있는 상태 */
  const MiniBot = ({ waving = false }: { waving?: boolean }) => (
    <svg width="40" height="62" viewBox="0 0 40 62" fill="none" style={{ overflow: "visible", filter: "drop-shadow(0 4px 6px rgba(0,0,0,0.25))" }}>
      {/* 안테나 */}
      <line x1="20" y1="2" x2="20" y2="8" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" />
      <circle cx="20" cy="2" r="3" fill="#22D3EE" style={{ filter: "drop-shadow(0 0 4px #22D3EE)" }} className="animate-pulse" />

      {/* 머리 */}
      <path d="M10 16 C 10 10, 30 10, 30 16 L 32 24 C 32 28, 28 30, 20 30 C 12 30, 8 28, 8 24 Z" fill="#1E293B" stroke="#334155" strokeWidth="1" />
      <rect x="6" y="16" width="3" height="8" rx="1.5" fill="#38BDF8" />
      <rect x="31" y="16" width="3" height="8" rx="1.5" fill="#38BDF8" />

      {/* Visor */}
      <path d="M12 18 C 12 16, 28 16, 28 18 L 28 22 C 28 24, 12 24, 12 22 Z" fill="#0F172A" />
      <path d="M14 19 C 14 18, 26 18, 26 19 L 26 21 C 26 22, 14 22, 14 21 Z" fill="#22D3EE" opacity="0.8" style={{ filter: "drop-shadow(0 0 6px #06B6D4)" }} />
      <line x1="16" y1="20" x2="24" y2="20" stroke="white" strokeWidth="2" strokeDasharray="2 2" strokeLinecap="round" opacity="0.9" style={{ animation: "particleFade 1.5s infinite alternate" }} />

      {/* 목 */}
      <rect x="18" y="30" width="4" height="4" fill="#334155" />

      {/* 몸통 */}
      <path d="M14 34 L 26 34 L 28 42 C 28 44, 24 46, 20 46 C 16 46, 12 44, 12 42 Z" fill="#334155" stroke="#475569" strokeWidth="1" />
      <path d="M16 34 L 24 34 L 25 38 L 15 38 Z" fill="#1E293B" />
      <circle cx="20" cy="42" r="2" fill="#22D3EE" style={{ filter: "drop-shadow(0 0 2px #22D3EE)" }} />

      {/* 왼팔 */}
      <g style={{ transformOrigin: "14px 36px", animation: waving ? "armSwing 0.6s ease-in-out infinite alternate" : undefined }}>
        <path d="M14 36 C 8 36, 6 40, 6 44" stroke="#64748B" strokeWidth="3" strokeLinecap="round" fill="none" />
        <circle cx="6" cy="44" r="2" fill="#22D3EE" />
      </g>
      {/* 오른팔 */}
      <g style={{ transformOrigin: "26px 36px" }}>
        <path d="M26 36 C 32 36, 34 40, 34 44" stroke="#64748B" strokeWidth="3" strokeLinecap="round" fill="none" />
        <circle cx="34" cy="44" r="2" fill="#22D3EE" />
      </g>

      {/* 왼다리 */}
      <g>
        <path d="M16 46 L 14 54" stroke="#64748B" strokeWidth="3" strokeLinecap="round" />
        <ellipse cx="13" cy="56" rx="4" ry="2" fill="#334155" stroke="#475569" strokeWidth="0.5" />
      </g>
      {/* 오른다리 */}
      <g>
        <path d="M24 46 L 26 54" stroke="#64748B" strokeWidth="3" strokeLinecap="round" />
        <ellipse cx="27" cy="56" rx="4" ry="2" fill="#334155" stroke="#475569" strokeWidth="0.5" />
      </g>

      {/* 바닥 떠있는 효과 */}
      <circle cx="20" cy="58" r="10" fill="#22D3EE" opacity="0.15" className="animate-pulse" style={{ filter: "blur(4px)" }} />
    </svg>
  );

  /* 하이테크 미래형 SVG 미니 AI봇 — 옆모습 걷기 */
  const MiniBotWalking = () => (
    <svg width="36" height="62" viewBox="0 0 36 62" fill="none" style={{ overflow: "visible", filter: "drop-shadow(0 4px 6px rgba(0,0,0,0.25))" }}>
      {/* 안테나 */}
      <line x1="20" y1="2" x2="20" y2="7" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" />
      <circle cx="20" cy="2" r="2.5" fill="#22D3EE" style={{ filter: "drop-shadow(0 0 4px #22D3EE)" }} className="animate-pulse" />

      {/* 머리 — 옆모습 (오른쪽 향함) */}
      <path d="M10 12 C 10 7, 28 7, 28 12 L 30 20 C 30 24, 26 26, 18 26 C 12 26, 8 24, 8 20 Z" fill="#1E293B" stroke="#334155" strokeWidth="1" />
      {/* 센서/귀 (뒷쪽) */}
      <rect x="7" y="14" width="2.5" height="6" rx="1.2" fill="#38BDF8" />
      {/* 바이저 — 오른쪽으로 약간 돌출 */}
      <path d="M14 15 C 14 13, 30 13, 30 15 L 30 19 C 30 21, 14 21, 14 19 Z" fill="#0F172A" />
      <path d="M16 16 C 16 15, 28 15, 28 16 L 28 18 C 28 19, 16 19, 16 18 Z" fill="#22D3EE" opacity="0.8" style={{ filter: "drop-shadow(0 0 6px #06B6D4)" }} />
      <line x1="18" y1="17" x2="26" y2="17" stroke="white" strokeWidth="1.5" strokeDasharray="2 2" strokeLinecap="round" opacity="0.9" style={{ animation: "particleFade 1.5s infinite alternate" }} />

      {/* 목 */}
      <rect x="16" y="26" width="5" height="3" rx="1" fill="#334155" />

      {/* 몸통 — 옆모습 (좁음) */}
      <path d="M12 29 L 25 29 L 27 40 C 27 42, 23 43, 18 43 C 13 43, 10 42, 10 40 Z" fill="#334155" stroke="#475569" strokeWidth="1" />
      <path d="M14 29 L 23 29 L 24 33 L 13 33 Z" fill="#1E293B" />
      <circle cx="18" cy="38" r="1.5" fill="#22D3EE" style={{ filter: "drop-shadow(0 0 2px #22D3EE)" }} />

      {/* 뒷팔 (왼팔, 뒤쪽 — 약간 어둡게) */}
      <g style={{ transformOrigin: "18px 30px", animation: "sideArmBack 1.2s ease-in-out infinite alternate" }}>
        <path d="M18 30 L 18 40" stroke="#475569" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx="18" cy="40" r="1.5" fill="#0891B2" />
      </g>

      {/* 뒷다리 (왼다리, 뒤쪽) — 허벅지 + 종아리 */}
      <g style={{ transformOrigin: "18px 42px", animation: "sideLegBack 1.2s ease-in-out infinite alternate" }}>
        <path d="M18 42 L 18 50" stroke="#475569" strokeWidth="3" strokeLinecap="round" />
        <g style={{ transformOrigin: "18px 50px", animation: "sideKneeBack 1.2s ease-in-out infinite alternate" }}>
          <path d="M18 50 L 18 56" stroke="#475569" strokeWidth="2.5" strokeLinecap="round" />
          <ellipse cx="18" cy="57" rx="3" ry="1.5" fill="#2D3748" />
        </g>
      </g>

      {/* 앞다리 (오른다리) — 허벅지 + 종아리 */}
      <g style={{ transformOrigin: "18px 42px", animation: "sideLegFront 1.2s ease-in-out infinite alternate" }}>
        <path d="M18 42 L 18 50" stroke="#64748B" strokeWidth="3" strokeLinecap="round" />
        <g style={{ transformOrigin: "18px 50px", animation: "sideKneeFront 1.2s ease-in-out infinite alternate" }}>
          <path d="M18 50 L 18 56" stroke="#64748B" strokeWidth="2.5" strokeLinecap="round" />
          <ellipse cx="18" cy="57" rx="3" ry="1.5" fill="#334155" stroke="#475569" strokeWidth="0.5" />
          <ellipse cx="18" cy="57" rx="1.8" ry="0.8" fill="#22D3EE" opacity="0.3" />
        </g>
      </g>

      {/* 앞팔 (오른팔, 앞쪽) */}
      <g style={{ transformOrigin: "18px 30px", animation: "sideArmFront 1.2s ease-in-out infinite alternate" }}>
        <path d="M18 30 L 18 40" stroke="#64748B" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx="18" cy="40" r="1.5" fill="#22D3EE" />
      </g>
    </svg>
  );

  /* 하이테크 미래형 터미널에서 작업하는 봇 */
  const MiniBotWorking = () => (
    <svg width="70" height="60" viewBox="0 0 70 60" fill="none" style={{ overflow: "visible", filter: "drop-shadow(0 4px 8px rgba(0,0,0,0.3))" }}>
      {/* Holographic Desk */}
      <path d="M 5 50 L 65 50" stroke="#06B6D4" strokeWidth="2" opacity="0.6" style={{ filter: "drop-shadow(0 0 4px #22D3EE)" }} />
      <path d="M 10 54 L 60 54" stroke="#06B6D4" strokeWidth="1" opacity="0.3" />
      <path d="M 15 50 L 5 60 M 55 50 L 65 60" stroke="#06B6D4" strokeWidth="1" opacity="0.3" />

      {/* Hover chair base */}
      <ellipse cx="20" cy="46" rx="10" ry="2" fill="#22D3EE" opacity="0.1" style={{ filter: "blur(2px)" }} />

      {/* 미래형 디스플레이 (Hologram Screen) */}
      <path d="M 40 48 L 46 22 L 66 22 L 60 48 Z" fill="#0EA5E9" opacity="0.1" />
      <path d="M 40 48 L 46 22 L 66 22 L 60 48 Z" stroke="#22D3EE" strokeWidth="1" opacity="0.8" style={{ filter: "drop-shadow(0 0 2px #22D3EE)" }} />
      
      {/* 데이터 코드 라인들 */}
      <g style={{ transform: "skewX(-13deg)" }}>
        <rect x="52" y="26" width="10" height="2" rx="1" fill="#22D3EE" opacity="0.9" style={{ animation: "codeLine 1.5s ease-in-out infinite" }} />
        <rect x="52" y="30" width="14" height="2" rx="1" fill="#67E8F9" opacity="0.7" style={{ animation: "codeLine 1.5s 0.3s ease-in-out infinite" }} />
        <rect x="52" y="34" width="8" height="2" rx="1" fill="#22D3EE" opacity="0.8" style={{ animation: "codeLine 1.5s 0.6s ease-in-out infinite" }} />
        <rect x="52" y="38" width="12" height="2" rx="1" fill="#BAE6FD" opacity="0.6" style={{ animation: "codeLine 1.5s 0.9s ease-in-out infinite" }} />
      </g>

      {/* 안테나 */}
      <line x1="22" y1="6" x2="22" y2="12" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" />
      <circle cx="22" cy="6" r="3" fill="#22D3EE" style={{ filter: "drop-shadow(0 0 4px #22D3EE)" }} className="animate-pulse" />

      {/* 머리 — 약간 기울임 */}
      <g style={{ transformOrigin: "22px 24px", animation: "headBob 2s ease-in-out infinite" }}>
        <path d="M12 20 C 12 14, 32 14, 32 20 L 34 28 C 34 32, 30 34, 22 34 C 14 34, 10 32, 10 28 Z" fill="#1E293B" stroke="#334155" strokeWidth="1" />
        
        {/* 센서 디테일 */}
        <rect x="8" y="20" width="3" height="8" rx="1.5" fill="#38BDF8" transform="rotate(-15 8 20)" />

        {/* Visor */}
        <path d="M14 22 C 14 20, 30 20, 30 22 L 30 26 C 30 28, 14 28, 14 26 Z" fill="#0F172A" />
        <path d="M16 23 C 16 22, 28 22, 28 23 L 28 25 C 28 26, 16 26, 16 25 Z" fill="#22D3EE" opacity="0.8" style={{ filter: "drop-shadow(0 0 6px #06B6D4)" }} />
        <line x1="18" y1="24" x2="26" y2="24" stroke="white" strokeWidth="2" strokeDasharray="3 2" strokeLinecap="round" opacity="0.9" style={{ animation: "particleFade 1s infinite alternate" }} />
      </g>

      {/* 몸통 */}
      <path d="M16 38 L 28 38 L 30 46 C 30 48, 26 50, 22 50 C 18 50, 14 48, 14 46 Z" fill="#334155" stroke="#475569" strokeWidth="1" />
      <path d="M18 38 L 26 38 L 27 42 L 17 42 Z" fill="#1E293B" />
      <circle cx="22" cy="46" r="2" fill="#22D3EE" style={{ filter: "drop-shadow(0 0 2px #22D3EE)" }} />

      {/* Holographic Keyboard Arc */}
      <path d="M 28 48 Q 36 46 44 48" stroke="#06B6D4" strokeWidth="2" fill="none" opacity="0.6" style={{ filter: "drop-shadow(0 0 3px #06B6D4)" }} />

      {/* 왼팔 */}
      <g style={{ transformOrigin: "16px 40px", animation: "typingLeft 0.3s ease-in-out infinite alternate" }}>
        <path d="M16 40 C 12 40, 14 46, 28 47" stroke="#64748B" strokeWidth="3" fill="none" strokeLinecap="round" />
        <circle cx="28" cy="47" r="2" fill="#22D3EE" style={{ filter: "drop-shadow(0 0 2px #22D3EE)" }} />
      </g>
      {/* 오른팔 */}
      <g style={{ transformOrigin: "28px 40px", animation: "typingRight 0.3s ease-in-out infinite alternate-reverse" }}>
        <path d="M28 40 C 32 40, 34 46, 40 47" stroke="#64748B" strokeWidth="3" fill="none" strokeLinecap="round" />
        <circle cx="40" cy="47" r="2" fill="#22D3EE" style={{ filter: "drop-shadow(0 0 2px #22D3EE)" }} />
      </g>
    </svg>
  );

  /* 미니 브랜드 알 (좌하단) — 봇이 여기서 깨고 나옴 */
  const BrandEgg = ({ shaking, cracking }: { shaking?: boolean; cracking?: boolean }) => (
    <div className="relative" style={shaking ? { animation: "brandEggShake 1.2s ease-in-out forwards" } : undefined}>
      {/* 알 본체: 네이비 배지 + 금빛 GO — 달걀 모양 */}
      <div
        className="flex items-center justify-center"
        style={{
          width: 40,
          height: 50,
          borderRadius: "50% 50% 50% 50% / 60% 60% 40% 40%",
          background: "linear-gradient(160deg, #FDF5E6 0%, #F5E6C8 25%, #E8D5A3 50%, #D4B896 75%, #C4A882 100%)",
          boxShadow: "0 2px 8px rgba(180, 150, 100, 0.4), inset 0 2px 4px rgba(255,255,255,0.6), inset 0 -2px 4px rgba(160,120,60,0.15)",
          border: "1px solid rgba(200, 175, 130, 0.3)",
        }}
      >
        <span
          style={{
            fontSize: 11,
            fontWeight: 900,
            color: "#8B6914",
            textShadow: "0 1px 1px rgba(255,255,255,0.5)",
          }}
        >
          GO
        </span>
      </div>

      {/* 금이 가는 SVG */}
      {cracking && (
        <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 40 50" style={{ zIndex: 10 }}>
          <path d="M20 3 L18 14 L22 20 L18 30 L21 40 L20 47" stroke="rgba(120,80,30,0.7)" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeDasharray="35" style={{ animation: "brandCrackLine 1s ease-out forwards" }} />
          <path d="M18 14 L12 18" stroke="rgba(120,80,30,0.5)" strokeWidth="1" fill="none" strokeLinecap="round" strokeDasharray="8" style={{ animation: "brandCrackLine 0.6s 0.3s ease-out forwards", strokeDashoffset: 8 }} />
        </svg>
      )}
    </div>
  );

  if (!open) {
    return (
      <>
        {/* 봇 애니메이션 영역 — 화면 하단 전체 */}
        {botPhase !== "idle" && (
          <div className="fixed bottom-0 left-0 right-0 z-30 pointer-events-none overflow-hidden h-20">
            {/* Phase: emerge — 하단 중앙에서 봇 등장 */}
            {botPhase === "emerge" && (
              <div
                className="absolute"
                style={{
                  left: "50%",
                  marginLeft: -20,
                  bottom: 0,
                  animation: "botEmergeFromBrand 1s cubic-bezier(0.34, 1.56, 0.64, 1) forwards",
                }}
              >
                <MiniBot waving />
                <div style={{ position: "absolute", top: -8, right: -12, animation: "particleFade 0.4s ease-in-out infinite alternate" }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="#FDE047"><path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" /></svg>
                </div>
              </div>
            )}

            {/* Phase: walk — 중앙에서 오른쪽으로 천천히 걸어감 (옆모습) */}
            {botPhase === "walk" && (
              <div
                className="absolute"
                style={{
                  bottom: 0,
                  animation: "botWalkCenterToRight 5.5s ease-in-out forwards",
                }}
              >
                <div style={{ animation: "botWalkBob 0.7s ease-in-out infinite" }}>
                  <MiniBotWalking />
                </div>
              </div>
            )}

            {/* Phase: work — 우측에서 책상 작업 */}
            {botPhase === "work" && (
              <div
                className="absolute"
                style={{
                  bottom: 0,
                  animation: "botSettleToWork 0.5s ease-out forwards",
                }}
              >
                <MiniBotWorking />
                <div style={{ position: "absolute", top: -14, left: 18, animation: "ideaPop 4s ease-in-out infinite" }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="#FBBF24"><path d="M9 21H15V22H9V21ZM12 2C8.13 2 5 5.13 5 9C5 11.38 6.19 13.47 8 14.74V17C8 17.55 8.45 18 9 18H15C15.55 18 16 17.55 16 17V14.74C17.81 13.47 19 11.38 19 9C19 5.13 15.87 2 12 2Z" /><circle cx="12" cy="10" r="4" fill="#FEF08A" /></svg>
                </div>
                <div style={{ position: "absolute", top: -4, left: 44, animation: "particleFade 3s ease-in-out infinite alternate" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="#FDE047"><path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" /></svg>
                </div>
              </div>
            )}

            {/* Phase: return — 플로팅 버튼 쪽으로 걸어가서 흡수됨 (옆모습) */}
            {botPhase === "return" && (
              <div
                className="absolute"
                style={{
                  bottom: 0,
                  animation: "botWalkToBtn 3s ease-in-out forwards",
                }}
              >
                <div style={{ animation: "botWalkBob 0.7s ease-in-out infinite" }}>
                  <MiniBotWalking />
                </div>
              </div>
            )}
          </div>
        )}

        {/* 하단 중앙 브랜드 알 — 봇이 여기서 깨고 나옴 */}
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-30">
          {/* 깨진 껍데기 — 벌어진 후 2~3초 유지하다 페이드아웃 */}
          {botPhase === "emerge" && (
            <>
              <div
                className="absolute overflow-hidden pointer-events-none"
                style={{
                  width: 24, height: 30,
                  top: 2, left: 0,
                  borderRadius: "50% 50% 50% 50% / 60% 60% 40% 40%",
                  background: "linear-gradient(160deg, #FDF5E6 0%, #E8D5A3 50%, #C4A882 100%)",
                  clipPath: "polygon(0 0, 55% 0, 40% 50%, 10% 100%, 0 100%)",
                  animation: "brandEggCrackLeft 3s ease-out forwards",
                  zIndex: 50,
                }}
              />
              <div
                className="absolute overflow-hidden pointer-events-none"
                style={{
                  width: 24, height: 30,
                  top: 2, right: 0,
                  borderRadius: "50% 50% 50% 50% / 60% 60% 40% 40%",
                  background: "linear-gradient(160deg, #FDF5E6 0%, #E8D5A3 50%, #C4A882 100%)",
                  clipPath: "polygon(45% 0, 100% 0, 100% 100%, 60% 100%, 40% 50%)",
                  animation: "brandEggCrackRight 3s ease-out forwards",
                  zIndex: 50,
                }}
              />
            </>
          )}

          {/* 브랜드 알 — crack 단계에서 흔들림, emerge 이후 안 보임 */}
          <div style={
            botPhase === "crack"
              ? undefined
              : botPhase !== "idle"
                ? { opacity: 0, pointerEvents: "none" as const }
                : undefined
          }>
            <BrandEgg
              shaking={botPhase === "crack"}
              cracking={botPhase === "crack"}
            />
          </div>
        </div>

        {/* 플로팅 AI 상담 버튼 */}
        <FabWithBubble
          label={isIndividual ? "전문가용 개인 상담 에이전트" : "전문가용 기업 상담 에이전트"}
          onClick={() => { setOpen(true); setDragPos(null); }}
          botPhase={botPhase}
        />
      </>
    );
  }

  // 모드 선택 헤더 색상
  const headerGradient = mode === "consultant"
    ? "from-violet-600 to-purple-600"
    : "from-indigo-600 to-violet-600";

  const headerTitle = mode === "consultant" ? "고객사별 상담/관리 AI에이전트" : mode === "free" ? "지원사업 상담 AI에이전트" : "AI 서비스";
  const headerSub = mode === "consultant" ? "고객사 조건 입력 → 맞춤 매칭" : mode === "free" ? "지원사업 종류·자격·절차 상담" : "모드를 선택하세요";

  // PRO 사용자는 전문가 대시보드로 전환
  if (open && isPro) {
    const ProSecretary = require("@/components/pro/ProSecretary").default;
    return <ProSecretary onClose={handleClose} planStatus={planStatus} onUpgrade={onUpgrade} userType={userType} />;
  }

  // 비PRO 사용자는 PRO 소개/가입 유도 화면
  if (open && !isPro) {
    const ProUpsellScreen = require("@/components/pro/ProUpsellScreen").default;
    return <ProUpsellScreen onClose={handleClose} onUpgrade={onUpgrade} />;
  }

  return (
    <div className="fixed inset-0 z-50 flex lg:pointer-events-none">
      <div className="absolute inset-0 bg-black/20 backdrop-blur-[2px] lg:hidden" onClick={handleClose} />

      <div
        data-chat-panel
        className={`bg-white shadow-2xl border border-slate-200 overflow-hidden flex flex-col pointer-events-auto ${
          (isFullscreen || mode === "consultant" || mode === "select")
            ? "fixed inset-0 w-full h-full rounded-none z-[60]"
            : dragPos
              ? "fixed rounded-2xl"
              : "relative w-full sm:w-[420px] lg:w-[380px] h-full animate-in slide-in-from-left duration-300"
        }`}
        style={!isFullscreen && mode === "free" && dragPos ? { left: dragPos.x, top: dragPos.y, width: 400, height: "80vh", zIndex: 60, borderRadius: 16 } : undefined}
      >

        {/* Header — 드래그 핸들 */}
        <div
          className={`relative z-10 px-4 py-3 border-b border-slate-100 bg-gradient-to-r ${headerGradient} flex-shrink-0 cursor-grab active:cursor-grabbing select-none`}
          onMouseDown={handleDragStart}
        >
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
                <p className="text-[11px] text-white/70 font-medium">{headerSub}</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={handleReset} className="p-1.5 hover:bg-white/20 rounded-lg transition-all" title="처음으로">
                <svg className="w-4 h-4 text-white/80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
                </svg>
              </button>
              <button onClick={() => { setIsFullscreen(!isFullscreen); setDragPos(null); }} className="p-1.5 hover:bg-white/20 rounded-lg transition-all hidden lg:block" title={isFullscreen ? "축소" : "전체화면"}>
                {isFullscreen ? (
                  <svg className="w-4 h-4 text-white/80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4 text-white/80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
                  </svg>
                )}
              </button>
              <button onClick={handleClose} className="p-1.5 hover:bg-white/20 rounded-lg transition-all">
                <svg className="w-4 h-4 text-white/80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* PRO 전문가 대시보드 */}
        {mode === "select" ? (
          <div className="flex-1 flex overflow-hidden">
            {/* 좌측 네비게이션 */}
            <nav className="w-[200px] lg:w-[220px] border-r border-slate-100 bg-gradient-to-b from-slate-50 to-white flex flex-col flex-shrink-0 overflow-y-auto">
              <div className="p-4 pb-2">
                <p className="text-[10px] font-bold text-violet-500 uppercase tracking-widest">전문가 도구</p>
              </div>
              {[
                { id: "free", icon: "💬", label: "지원사업 상담", desc: "정책·자격·절차 Q&A", needsPro: true },
                { id: "consultant", icon: "📋", label: "고객사 상담", desc: "맞춤 상담·분석", needsPro: true },
                { id: "search", icon: "🔍", label: "공고 매칭/검색", desc: "조건별 공고 검색", needsPro: false },
                { id: "analysis", icon: "📄", label: "공고 상세 분석", desc: "원문 AI 정밀 분석", needsPro: true },
                { id: "crm", icon: "👥", label: "고객 관리", desc: "CRM·자료·이력", needsPro: true },
                { id: "reports", icon: "📊", label: "보고서", desc: "컨설팅 보고서·PDF", needsPro: true },
                { id: "email", icon: "📧", label: "이메일 발송", desc: "고객 일괄 발송", needsPro: true },
              ].map(item => (
                <button
                  key={item.id}
                  onClick={() => {
                    if (item.needsPro && !isPro) { toast("PRO 플랜에서 이용 가능합니다.", "info"); onUpgrade?.(); return; }
                    if (item.id === "free") startMode("free");
                    else if (item.id === "consultant") startMode("consultant");
                    else if (item.id === "crm") {
                      setOpen(false);
                      window.dispatchEvent(new CustomEvent("open-pro-dashboard"));
                    }
                    else toast(`${item.label} — 준비 중입니다.`, "info");
                  }}
                  className="w-full px-4 py-3 flex items-start gap-3 hover:bg-violet-50 transition-all text-left group"
                >
                  <span className="text-lg mt-0.5">{item.icon}</span>
                  <div className="min-w-0">
                    <p className="text-[13px] font-bold text-slate-700 group-hover:text-violet-700 transition-colors">{item.label}</p>
                    <p className="text-[10px] text-slate-400">{item.desc}</p>
                  </div>
                  {item.needsPro && !isPro && (
                    <span className="ml-auto px-1.5 py-0.5 bg-violet-100 text-violet-600 text-[8px] font-bold rounded flex-shrink-0 mt-1">PRO</span>
                  )}
                </button>
              ))}
            </nav>

            {/* 중앙 메인 영역 — 환영 화면 */}
            <div className="flex-1 flex flex-col items-center justify-center px-8 overflow-y-auto">
              <div className="max-w-md text-center">
                <div className="w-16 h-16 mx-auto mb-4 bg-violet-100 rounded-2xl flex items-center justify-center">
                  <span className="text-3xl">✨</span>
                </div>
                <h2 className="text-xl font-bold text-slate-800 mb-2">전문가 대시보드</h2>
                <p className="text-[13px] text-slate-500 leading-relaxed mb-6">
                  좌측 메뉴에서 원하시는 서비스를 선택하세요.<br/>
                  AI가 지원사업 상담, 고객 관리, 공고 분석을 도와드립니다.
                </p>
                <div className="grid grid-cols-2 gap-3 text-left">
                  <button onClick={() => { if (!isPro) { toast("PRO 플랜에서 이용 가능합니다.", "info"); onUpgrade?.(); return; } startMode("consultant"); }}
                    className="p-3 bg-violet-50 border border-violet-200 rounded-xl hover:bg-violet-100 transition-all">
                    <p className="text-[12px] font-bold text-violet-700">📋 고객사 상담 시작</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">고객 유형 선택 → AI 대화</p>
                  </button>
                  <button onClick={() => { if (!isPro) { toast("PRO 플랜에서 이용 가능합니다.", "info"); onUpgrade?.(); return; } startMode("free"); }}
                    className="p-3 bg-indigo-50 border border-indigo-200 rounded-xl hover:bg-indigo-100 transition-all">
                    <p className="text-[12px] font-bold text-indigo-700">💬 지원사업 상담</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">정책·자격·절차 질문</p>
                  </button>
                </div>

                {!isPro && (
                  <div className="mt-6 p-3 bg-slate-50 border border-slate-200 rounded-xl">
                    <p className="text-[11px] text-slate-500">
                      전문가 도구는 <span className="font-bold text-violet-600">PRO</span> 플랜에서 이용 가능합니다.
                    </p>
                    <button onClick={() => { setOpen(false); onUpgrade?.(); }}
                      className="mt-2 px-4 py-1.5 bg-violet-600 text-white rounded-lg text-[11px] font-bold hover:bg-violet-700 transition-all">
                      PRO 플랜 알아보기
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

        ) : mode === "consultant" && !clientCategory && !matchingInProgress ? (
          /* ── 고객 유형 선택 화면 ── */
          <div className="flex-1 flex flex-col px-5 py-6 overflow-y-auto">
            <div className="text-center mb-5">
              <p className="text-[16px] font-bold text-slate-800">고객 유형을 선택하세요</p>
              <p className="text-[12px] text-slate-400 mt-1">유형에 맞는 입력 폼이 자동으로 구성됩니다</p>
            </div>

            {/* 기존 고객 불러오기 */}
            {existingClients.length > 0 && (
              <div className="mb-4">
                <label className="block text-[11px] font-bold text-slate-500 mb-1.5">기존 고객 불러오기</label>
                <select
                  value={selectedExistingClient || ""}
                  onChange={(e) => {
                    const cid = Number(e.target.value);
                    if (!cid) return;
                    const client = existingClients.find((c: any) => c.id === cid);
                    if (client) {
                      setSelectedExistingClient(cid);
                      const ct = client.client_type === "individual" ? "individual" as const : "corporate" as const;
                      setClientCategory(ct);
                      setFormProfile({
                        company_name: client.client_name || "",
                        establishment_date: client.establishment_date ? String(client.establishment_date).substring(0, 10) : "",
                        industry_code: client.industry_code || "",
                        revenue_bracket: client.revenue_bracket || "",
                        employee_count_bracket: client.employee_count_bracket || "",
                        address_city: client.address_city || "",
                        interests: client.interests ? String(client.interests).split(",").filter(Boolean) : [],
                      });
                    }
                  }}
                  className="w-full px-3 py-2.5 border border-violet-200 rounded-xl text-sm bg-white focus:ring-2 focus:ring-violet-300 outline-none"
                >
                  <option value="">고객 선택...</option>
                  {existingClients.map((c: any) => (
                    <option key={c.id} value={c.id}>{c.client_name} ({c.address_city || "지역미등록"})</option>
                  ))}
                </select>
              </div>
            )}

            <p className="text-[11px] text-slate-400 text-center mb-3">{existingClients.length > 0 ? "또는 새 고객:" : ""}</p>

            {/* 유형 선택 버튼 */}
            <div className="grid grid-cols-2 gap-3">
              {([
                { key: "individual_biz" as const, label: "개인사업자", desc: "1인 사업자, 프리랜서", icon: "🏪" },
                { key: "corporate" as const, label: "법인사업자", desc: "법인 기업", icon: "🏢" },
                { key: "individual" as const, label: "개인", desc: "취업·복지·주거 등", icon: "👤" },
                { key: "unknown" as const, label: "모름", desc: "AI가 대화로 파악", icon: "💬" },
              ]).map(opt => (
                <button
                  key={opt.key}
                  onClick={() => {
                    setClientCategory(opt.key);
                    setConsultantTab("chat");
                    const catLabel = opt.label;
                    const isInd = opt.key === "individual";
                    setMessages([{
                      role: "assistant",
                      text: opt.key === "unknown"
                        ? "고객 유형을 모르셔도 괜찮습니다.\n\n고객에 대해 아는 정보를 자유롭게 알려주세요. AI가 대화를 통해 파악하겠습니다."
                        : `**${catLabel}** 고객이시군요.\n\n자료가 있으시면 아래에서 첨부해 주세요.\n없으면 바로 대화로 시작할게요.`,
                      choices: opt.key === "unknown"
                        ? ["기업 고객이에요", "개인 고객이에요", "사업을 준비 중이에요"]
                        : isInd
                          ? ["자료 없이 바로 시작", "이름부터 알려줄게요", "관심 분야가 취업이에요"]
                          : ["자료 없이 바로 시작", "기업명부터 알려줄게요", "매출이 1억 미만이에요"],
                    }]);
                    setFormProfile(prev => ({ ...prev, _systemContext: `[고객유형: ${catLabel}]` } as any));
                  }}
                  className="p-4 rounded-xl border-2 border-slate-200 hover:border-violet-400 hover:bg-violet-50 transition-all text-left active:scale-[0.98]"
                >
                  <span className="text-2xl">{opt.icon}</span>
                  <p className="text-[13px] font-bold text-slate-800 mt-2">{opt.label}</p>
                  <p className="text-[10px] text-slate-400 mt-0.5">{opt.desc}</p>
                </button>
              ))}
            </div>
          </div>

        ) : mode === "consultant" && consultantTab === "form" && false ? (
          <>
            {/* Legacy form — 비활성 (대화형으로 전환됨) */}
            <div className="flex-shrink-0 px-4 pt-3 pb-1 border-b border-slate-100 bg-slate-50/80">
              <div className="flex gap-1 p-0.5 bg-slate-200/80 rounded-xl">
                <button onClick={() => setClientCategory("")} className="px-3 py-2 text-[12px] font-bold text-slate-500 hover:text-violet-700">
                  ← 유형변경
                </button>
                <button
                  onClick={() => setConsultantTab("form")}
                  className="flex-1 py-2 text-[14px] font-bold rounded-lg transition-all bg-white text-violet-700 shadow-sm"
                >
                  직접 입력
                </button>
                <button
                  onClick={() => switchToConsultantChat()}
                  className="flex-1 py-2 text-[14px] font-bold rounded-lg transition-all text-slate-500 hover:text-slate-700"
                >
                  대화로 입력
                </button>
              </div>
            </div>

            {/* Direct Input Form */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
              {/* 이름/기업명 */}
              <div>
                <label className="block text-[14px] font-bold text-slate-700 mb-1.5">
                  {clientCategory === "individual" ? "이름" : "기업명"} <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={formProfile.company_name}
                  onChange={(e) => updateForm("company_name", e.target.value)}
                  placeholder={isIndividual ? "예: 홍길동" : "예: (주)테스트기업"}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-[16px] text-slate-700 placeholder-slate-400 outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-300 transition-all"
                />
              </div>

              {/* 생년월일/설립일 */}
              <div>
                <label className="block text-[14px] font-bold text-slate-700 mb-1.5">
                  {isIndividual ? "생년월일" : "설립일"} <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={10}
                  value={formProfile.establishment_date}
                  onChange={(e) => {
                    const raw = e.target.value.replace(/[^0-9]/g, "").slice(0, 8);
                    let formatted = raw;
                    if (raw.length >= 5) formatted = raw.slice(0, 4) + "-" + raw.slice(4);
                    if (raw.length >= 7) formatted = raw.slice(0, 4) + "-" + raw.slice(4, 6) + "-" + raw.slice(6);
                    updateForm("establishment_date", formatted);
                  }}
                  placeholder={isIndividual ? "예: 19900101" : "예: 20230315"}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-[16px] text-slate-700 outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-300 transition-all"
                />
              </div>

              {/* 업종 — 사업자만 */}
              {!isIndividual && (
                <div>
                  <label className="block text-[14px] font-bold text-slate-700 mb-1.5">업종 <span className="text-red-400">*</span></label>
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
              )}

              {/* 매출규모 & 직원수 — 사업자만 */}
              {!isIndividual && (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[14px] font-bold text-slate-700 mb-1.5">매출규모 <span className="text-red-400">*</span></label>
                    <select
                      value={formProfile.revenue_bracket}
                      onChange={(e) => updateForm("revenue_bracket", e.target.value)}
                      className="w-full px-2.5 py-2 bg-white border border-slate-200 rounded-xl text-[15px] text-slate-700 outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-300 transition-all appearance-none"
                    >
                      <option value="">선택</option>
                      {REVENUE_OPTIONS.map((opt) => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-[14px] font-bold text-slate-700 mb-1.5">직원수 <span className="text-red-400">*</span></label>
                    <select
                      value={formProfile.employee_count_bracket}
                      onChange={(e) => updateForm("employee_count_bracket", e.target.value)}
                      className="w-full px-2.5 py-2 bg-white border border-slate-200 rounded-xl text-[15px] text-slate-700 outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-300 transition-all appearance-none"
                    >
                      <option value="">선택</option>
                      {EMPLOYEE_OPTIONS.map((opt) => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              {/* 관심지역 — 복수선택 */}
              <div>
                <label className="block text-[14px] font-bold text-slate-700 mb-1.5">
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
                        className={`px-3 py-1.5 rounded-lg text-[14px] font-semibold border transition-all active:scale-95 ${
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

              {/* 관심분야 — 자동완성 입력 */}
              <div>
                <label className="block text-[14px] font-bold text-slate-700 mb-1.5">
                  관심분야 <span className="text-red-400">*</span>
                </label>
                {/* 선택된 태그 */}
                {formProfile.interests.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {formProfile.interests.map((tag) => (
                      <span key={tag} className="inline-flex items-center gap-1 px-2.5 py-1 bg-violet-100 text-violet-700 rounded-full text-[13px] font-semibold">
                        {tag}
                        <button type="button" onClick={() => updateForm("interests", formProfile.interests.filter(t => t !== tag))} className="hover:text-violet-900 text-violet-400">×</button>
                      </span>
                    ))}
                  </div>
                )}
                {/* 입력 + 드롭다운 + AI fallback */}
                <div className="relative">
                  <input
                    type="text"
                    value={formProfile._interestInput || ""}
                    onChange={(e) => updateForm("_interestInput", e.target.value)}
                    onKeyDown={async (e) => {
                      if (e.key !== "Enter") return;
                      e.preventDefault();
                      const q = (formProfile._interestInput || "").toLowerCase();
                      const options = (isIndividual ? INDIVIDUAL_INTEREST_OPTIONS : INTEREST_OPTIONS)
                        .filter(opt => opt.toLowerCase().includes(q) && !formProfile.interests.includes(opt));
                      if (options.length > 0) {
                        updateForm("interests", [...formProfile.interests, options[0]]);
                        updateForm("_interestInput", "");
                      } else if (formProfile._interestInput?.trim()) {
                        try {
                          const res = await fetch(`${API}/api/ai/parse-interests`, {
                            method: "POST", headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ text: formProfile._interestInput.trim(), user_type: isIndividual ? "individual" : "business" }),
                          });
                          if (res.ok) {
                            const data = await res.json();
                            const mapped = (data.interests || []) as string[];
                            const newInterests = [...formProfile.interests, ...mapped.filter((m: string) => !formProfile.interests.includes(m))];
                            updateForm("interests", newInterests);
                          }
                        } catch {}
                        updateForm("_interestInput", "");
                      }
                    }}
                    placeholder="입력하면 추천이 나타납니다"
                    className="w-full px-3 py-2.5 bg-white border border-slate-200 rounded-xl text-[16px] text-slate-700 placeholder-slate-400 outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-300 transition-all"
                  />
                  {formProfile._interestInput && (formProfile._interestInput?.length || 0) > 0 && (() => {
                    const q = (formProfile._interestInput || "").toLowerCase();
                    const options = (isIndividual ? INDIVIDUAL_INTEREST_OPTIONS : INTEREST_OPTIONS)
                      .filter(opt => opt.toLowerCase().includes(q) && !formProfile.interests.includes(opt));
                    return options.length > 0 ? (
                      <div className="absolute z-20 w-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg max-h-48 overflow-y-auto">
                        {options.map(opt => (
                          <button
                            key={opt} type="button"
                            onClick={() => {
                              updateForm("interests", [...formProfile.interests, opt]);
                              updateForm("_interestInput", "");
                            }}
                            className="w-full px-3 py-2 text-left text-[14px] text-slate-700 hover:bg-violet-50 hover:text-violet-700 transition-all"
                          >
                            {opt}
                          </button>
                        ))}
                      </div>
                    ) : (q.length >= 2 ? (
                      <div className="absolute z-20 w-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg p-3">
                        <p className="text-sm text-violet-600 font-semibold">"{formProfile._interestInput}" → Enter로 AI 자동 분류</p>
                      </div>
                    ) : null);
                  })()}
                </div>
                <p className="text-[11px] text-slate-400 mt-1">키워드를 입력하면 추천 목록이 나타납니다. 없으면 Enter로 AI가 자동 분류합니다.</p>
              </div>
            </div>

            {/* 자료 첨부 */}
            <div className="flex-shrink-0 px-4 py-3 border-t border-slate-100 bg-slate-50/50">
              <ConsultantFileUpload
                clientId={selectedExistingClient}
                onFileText={(text) => {
                  if (text) setFormProfile(prev => ({ ...prev, _attachedText: text } as any));
                }}
              />
            </div>

            {/* 상담 시작 버튼 */}
            <div className="flex-shrink-0 border-t border-slate-100 bg-white px-4 py-3 space-y-2">
              <button
                onClick={() => {
                  // 고객 정보 + 자료 요약을 포함한 AI 상담 시작
                  const fp = formProfile;
                  const catLabel = clientCategory === "individual_biz" ? "개인사업자" : clientCategory === "corporate" ? "법인사업자" : clientCategory === "individual" ? "개인" : "고객";
                  const profile = [
                    fp.company_name && `${clientCategory === "individual" ? "이름" : "기업명"}: ${fp.company_name}`,
                    fp.establishment_date && `${clientCategory === "individual" ? "생년월일" : "설립일"}: ${fp.establishment_date}`,
                    fp.address_city && `지역: ${fp.address_city}`,
                    fp.industry_code && `업종: ${fp.industry_code}`,
                    fp.revenue_bracket && `매출: ${fp.revenue_bracket}`,
                    fp.employee_count_bracket && `직원수: ${fp.employee_count_bracket}`,
                    fp.interests?.length && `관심분야: ${fp.interests.join(",")}`,
                  ].filter(Boolean).join("\n");
                  const attached = (fp as any)._attachedText ? `\n\n[첨부 자료]\n${(fp as any)._attachedText.substring(0, 3000)}` : "";

                  setConsultantTab("chat");
                  setMessages([{
                    role: "assistant",
                    text: `**${catLabel} 고객 정보가 등록되었습니다.**\n\n${profile}\n\n어떤 상담을 도와드릴까요?`,
                    choices: ["이 고객에 맞는 지원사업 찾아줘", "첨부 자료 분석해줘", "사업 전략 상담", "자격요건 판단해줘"],
                  }]);

                  // 시스템 메시지로 고객 정보를 AI에 전달 (첫 메시지에 포함)
                  setFormProfile(prev => ({ ...prev, _systemContext: `[${catLabel} 고객]\n${profile}${attached}` } as any));
                }}
                disabled={!isFormValid()}
                className="w-full py-3 bg-gradient-to-r from-violet-600 to-purple-600 text-white text-[16px] font-bold rounded-xl hover:from-violet-700 hover:to-purple-700 transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                💬 상담 시작
              </button>
              <button
                onClick={handleFormSubmit}
                disabled={!isFormValid() || matchingInProgress}
                className="w-full py-2.5 bg-white border-2 border-violet-200 text-violet-700 text-[14px] font-bold rounded-xl hover:bg-violet-50 transition-all active:scale-[0.98] disabled:opacity-40 flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                </svg>
                바로 매칭 실행
              </button>
            </div>
          </>
        ) : (
          <>
            {/* 유형 변경 버튼 (consultant 대화 모드) */}
            {mode === "consultant" && !matchingInProgress && messages.length <= 3 && (
              <div className="flex-shrink-0 px-4 pt-2 pb-1 border-b border-slate-100 bg-slate-50/80">
                <button onClick={() => { setClientCategory(""); setMessages([]); }} className="text-[12px] font-bold text-slate-400 hover:text-violet-600 transition-all">
                  ← 유형 변경 / 새 고객
                </button>
              </div>
            )}

            {/* Chat + Tool Panel wrapper */}
            <div className={`flex-1 flex ${mode === "consultant" && clientCategory ? "flex-row" : "flex-col"} overflow-hidden`}>

            {/* 우측 도구 패널 — consultant 전체화면일 때만 */}
            {mode === "consultant" && clientCategory && (
              <div className="hidden lg:flex flex-col w-[260px] border-r border-slate-100 bg-slate-50/30 p-4 flex-shrink-0 overflow-y-auto order-2">
                <p className="text-[13px] font-bold text-violet-700 mb-2">📎 고객 자료 첨부</p>
                <p className="text-[11px] text-slate-500 leading-relaxed mb-4">
                  재무제표, 사업계획서, 회사소개서 등을 첨부하면<br/>
                  <strong className="text-violet-600">AI가 자동 분석</strong>하여 상담에 반영합니다.
                </p>
                <label
                  className="flex-1 min-h-[200px] flex flex-col items-center justify-center border-2 border-dashed border-violet-300 rounded-2xl bg-white hover:bg-violet-50 hover:border-violet-500 cursor-pointer transition-all"
                  onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("bg-violet-100", "border-violet-500"); }}
                  onDragLeave={(e) => { e.currentTarget.classList.remove("bg-violet-100", "border-violet-500"); }}
                  onDrop={async (e) => { e.preventDefault(); e.currentTarget.classList.remove("bg-violet-100", "border-violet-500"); const f = e.dataTransfer.files?.[0]; if (f) await handleFileAttach(f); }}
                >
                  <div className="text-center p-4">
                    <span className="text-4xl block mb-3">📄</span>
                    <p className="text-[13px] font-bold text-violet-700">파일을 드래그하거나 클릭</p>
                    <p className="text-[11px] text-slate-400 mt-1">PDF, HWP, DOCX, TXT (10MB)</p>
                  </div>
                  <input type="file" className="hidden" accept=".pdf,.hwp,.hwpx,.docx,.doc,.xlsx,.txt"
                    onChange={async (e) => { const f = e.target.files?.[0]; if (f) await handleFileAttach(f); e.target.value = ""; }} />
                </label>
              </div>
            )}

            {/* Chat area */}
            <div ref={scrollRef} className={`flex-1 overflow-y-auto px-4 py-4 space-y-3 order-1 ${mode === "consultant" && clientCategory ? "px-6 py-5" : ""}`}>
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`${mode === "consultant" && clientCategory ? "max-w-[80%]" : "max-w-[88%]"} ${msg.role === "user" ? "order-1" : ""}`}>
                    {/* Message bubble */}
                    <div className={`px-3.5 py-2.5 rounded-2xl ${mode === "consultant" && clientCategory ? "text-[15px]" : "text-[13px]"} leading-relaxed ${
                      msg.role === "user"
                        ? mode === "consultant" ? "bg-violet-600 text-white rounded-br-md" : "bg-indigo-600 text-white rounded-br-md"
                        : "bg-slate-100 text-slate-800 rounded-bl-md"
                    }`}>
                      {msg.role === "user" ? msg.text : (
                        <span dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(renderMarkdown(msg.text)) }} />
                      )}
                    </div>

                    {/* Related announcements — 공고 카드 + AI 상세 공고분석 버튼 */}
                    {msg.role === "assistant" && msg.announcements && msg.announcements.length > 0 && (
                      <div className="mt-3 space-y-2">
                        <p className="text-[10px] font-semibold text-indigo-500 px-1">관련 공고</p>
                        {msg.announcements.map((ann) => (
                          <div key={ann.announcement_id} className="p-3 bg-white rounded-xl border border-slate-200 hover:border-indigo-200 transition-all shadow-sm">
                            <p className="text-[12px] font-bold text-slate-800 leading-snug mb-1.5">{ann.title}</p>
                            <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-slate-500 mb-2">
                              {ann.support_amount && <span>{ann.support_amount}</span>}
                              {ann.deadline_date && <span>마감 {ann.deadline_date}</span>}
                              {ann.department && <span>{ann.department}</span>}
                            </div>
                            {ann.summary_text && (
                              <p className="text-[11px] text-slate-600 leading-relaxed mb-2 line-clamp-2">{ann.summary_text}</p>
                            )}
                            <button
                              onClick={() => {
                                setOpen(false);
                                window.dispatchEvent(new CustomEvent("open-ai-consult", {
                                  detail: { announcement: {
                                    announcement_id: ann.announcement_id,
                                    title: ann.title,
                                    support_amount: ann.support_amount,
                                    deadline_date: ann.deadline_date,
                                    department: ann.department,
                                    category: ann.category,
                                  }}
                                }));
                              }}
                              className="w-full py-1.5 bg-indigo-50 text-indigo-700 rounded-lg text-[11px] font-bold hover:bg-indigo-100 transition-all active:scale-[0.98]"
                            >
                              AI 상세 공고분석
                            </button>
                          </div>
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
                    <p className="text-[11px] text-slate-400 mt-1">
                      {matchingInProgress ? "수집한 조건으로 매칭 엔진을 실행하고 있습니다" : "AI가 응답을 생성하고 있습니다"}
                    </p>
                  </div>
                </div>
              )}
            </div>
            </div>{/* Chat + Tool Panel wrapper 닫기 */}

            {/* Input area — 드래그&드롭 지원 (consultant 모드) */}
            <div
              className="flex-shrink-0 border-t border-slate-100 bg-white px-3 py-2.5 transition-all"
              onDragOver={mode === "consultant" ? (e) => { e.preventDefault(); e.currentTarget.style.background = "#f5f3ff"; e.currentTarget.style.borderColor = "#8b5cf6"; } : undefined}
              onDragLeave={mode === "consultant" ? (e) => { e.currentTarget.style.background = ""; e.currentTarget.style.borderColor = ""; } : undefined}
              onDrop={mode === "consultant" ? async (e) => { e.preventDefault(); e.currentTarget.style.background = ""; e.currentTarget.style.borderColor = ""; const f = e.dataTransfer.files?.[0]; if (f) await handleFileAttach(f); } : undefined}
            >
              {isDone ? (
                <div className="space-y-2">
                  <button
                    onClick={() => setShowReport(true)}
                    className={`w-full py-2.5 text-white rounded-xl font-bold text-[13px] transition-all active:scale-[0.98] ${
                      mode === "consultant" ? "bg-violet-600 hover:bg-violet-700" : "bg-indigo-600 hover:bg-indigo-700"
                    }`}
                  >
                    상담 보고서 보기
                  </button>
                  <button
                    onClick={handleReset}
                    className="w-full py-2 text-slate-400 text-[12px] font-medium hover:text-slate-600 transition-all"
                  >
                    새 상담 시작
                  </button>
                </div>
              ) : (
                <>
                  {mode !== "free" && userMsgCount > 0 && (
                    <div className={`text-[10px] font-medium mb-1.5 text-right ${isAtMsgLimit ? "text-rose-500" : "text-slate-400"}`}>
                      {isAtMsgLimit ? "메시지 한도에 도달했습니다" : `${userMsgCount} / ${CONSULT_MSG_LIMIT}`}
                    </div>
                  )}
                  {isAtMsgLimit && mode !== "free" ? (
                    <div className="text-center py-2 px-3 bg-rose-50 border border-rose-200 rounded-xl">
                      <p className="text-rose-600 text-[11px] font-bold">상담 메시지 한도({CONSULT_MSG_LIMIT}회)를 모두 사용했습니다.</p>
                      <p className="text-rose-500 text-[10px] mt-0.5">새 공고에서 상담을 시작해 주세요.</p>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      {/* 파일 첨부 버튼 (consultant 모드) */}
                      {mode === "consultant" && (
                        <label className="p-2.5 text-violet-500 hover:text-violet-700 hover:bg-violet-50 rounded-xl cursor-pointer transition-all flex-shrink-0" title="자료 첨부">
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
                          </svg>
                          <input type="file" className="hidden" accept=".pdf,.hwp,.hwpx,.docx,.doc,.xlsx,.txt"
                            onChange={async (e) => { const f = e.target.files?.[0]; if (f) await handleFileAttach(f); e.target.value = ""; }} />
                        </label>
                      )}
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
                        placeholder={mode === "consultant" ? "고객 정보를 입력하거나 질문하세요..." : "지원사업에 대해 자유롭게 질문하세요..."}
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
                  )}
                  {/* 상담 종료 버튼 */}
                  {messages.length >= 2 && !loading && !matchingInProgress && (
                    <button
                      onClick={handleEndConsultation}
                      className="w-full mt-2 py-1.5 text-slate-400 hover:text-slate-600 text-[11px] font-medium transition-all text-center hover:bg-slate-50 rounded-lg"
                    >
                      상담 종료
                    </button>
                  )}
                </>
              )}
            </div>
          </>
        )}
      </div>

      {/* 상담 보고서 모달 */}
      {showReport && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowReport(false)} />
          <div className="relative w-full max-w-2xl max-h-[85vh] bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-300">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 bg-gradient-to-r from-indigo-50 to-violet-50 flex-shrink-0">
              <div>
                <p className="text-[14px] font-bold text-slate-800">상담 보고서</p>
                <p className="text-[11px] text-slate-500">{new Date().toLocaleString("ko-KR")}</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    const w = window.open("", "_blank");
                    if (w) { w.document.write(generateReportHtml()); w.document.close(); w.print(); }
                  }}
                  className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-[11px] font-bold hover:bg-indigo-700 transition-all"
                >
                  인쇄 / PDF
                </button>
                <button onClick={() => setShowReport(false)} className="p-1.5 hover:bg-slate-100 rounded-lg transition-all">
                  <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {messages.filter((m) => !m.done && m.text).map((m, i) => (
                <div key={i} className={`mb-3 p-3 rounded-xl ${m.role === "user" ? "bg-indigo-50 border-l-[3px] border-indigo-400" : "bg-slate-50 border-l-[3px] border-emerald-400"}`}>
                  <p className="text-[10px] font-bold mb-1" style={{ color: m.role === "user" ? "#4f46e5" : "#059669" }}>
                    {m.role === "user" ? "Q." : "A."}
                  </p>
                  {m.role === "user" ? (
                    <p className="text-[13px] text-slate-700">{m.text}</p>
                  ) : (
                    <div className="text-[13px] text-slate-700 leading-relaxed" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(renderMarkdown(m.text)) }} />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


// ━━━━━━━━━━━━━━ 상담 폼 내 자료 첨부 + AI 요약 ━━━━━━━━━━━━━━

const FILE_TYPE_OPTIONS = [
  { value: "financial", label: "재무제표" },
  { value: "business_plan", label: "사업계획서" },
  { value: "ir", label: "IR자료" },
  { value: "company_intro", label: "회사소개서" },
  { value: "other", label: "기타" },
];

function ConsultantFileUpload({ clientId, onFileText }: { clientId: number | null; onFileText: (text: string) => void }) {
  const [files, setFiles] = useState<{ name: string; type: string; summary: string; uploading: boolean }[]>([]);
  const [fileType, setFileType] = useState("other");

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { alert("10MB 이하 파일만 가능합니다."); return; }

    const idx = files.length;
    setFiles(prev => [...prev, { name: file.name, type: fileType, summary: "", uploading: true }]);

    try {
      const token = localStorage.getItem("auth_token") || "";

      let extractedText = "";

      if (clientId) {
        // 기존 고객이면 서버에 저장 + 텍스트 추출
        const formData = new FormData();
        formData.append("file", file);
        formData.append("file_type", fileType);
        formData.append("memo", "");
        const res = await fetch(`${API}/api/pro/clients/${clientId}/files`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });
        if (res.ok) {
          const data = await res.json();
          if (data.extracted_chars > 0) {
            extractedText = `[서버 추출 ${data.extracted_chars}자]`;
            setFiles(prev => prev.map((f, i) => i === idx ? { ...f, summary: "AI 분석 중..." } : f));
          } else {
            setFiles(prev => prev.map((f, i) => i === idx ? { ...f, uploading: false, summary: "텍스트 추출 불가" } : f));
            return;
          }
        }
      } else {
        // 새 고객 — 클라이언트에서 파일 읽기
        extractedText = await new Promise<string>((resolve) => {
          const reader = new FileReader();
          reader.onload = () => resolve((reader.result as string || "").substring(0, 8000));
          reader.onerror = () => resolve("");
          reader.readAsText(file);
        });
        if (!extractedText) {
          setFiles(prev => prev.map((f, i) => i === idx ? { ...f, uploading: false, summary: "텍스트 읽기 실패" } : f));
          return;
        }
        onFileText(extractedText.substring(0, 5000));
        setFiles(prev => prev.map((f, i) => i === idx ? { ...f, summary: "AI 분석 중..." } : f));
      }

      // AI 요약 분석 호출
      try {
        const analyzeRes = await fetch(`${API}/api/pro/files/analyze`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: JSON.stringify({ text: extractedText.substring(0, 8000), file_name: file.name, file_type: fileType }),
        });
        if (analyzeRes.ok) {
          const analyzeData = await analyzeRes.json();
          setFiles(prev => prev.map((f, i) => i === idx ? { ...f, uploading: false, summary: analyzeData.summary || "분석 완료" } : f));
        } else {
          setFiles(prev => prev.map((f, i) => i === idx ? { ...f, uploading: false, summary: "분석 실패" } : f));
        }
      } catch {
        setFiles(prev => prev.map((f, i) => i === idx ? { ...f, uploading: false, summary: extractedText ? "업로드 완료" : "분석 실패" } : f));
      }
    } catch {
      setFiles(prev => prev.map((f, i) => i === idx ? { ...f, uploading: false, summary: "업로드 실패" } : f));
    }
    e.target.value = "";
  };

  return (
    <div className="space-y-2">
      <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">자료 첨부 (선택)</p>
      <div className="flex items-center gap-2">
        <select value={fileType} onChange={(e) => setFileType(e.target.value)}
          className="px-2 py-1.5 border rounded-lg text-[11px] focus:ring-2 focus:ring-violet-300 outline-none">
          {FILE_TYPE_OPTIONS.map(ft => <option key={ft.value} value={ft.value}>{ft.label}</option>)}
        </select>
        <label className="flex-1 px-3 py-1.5 text-center border-2 border-dashed border-violet-300 rounded-lg text-[11px] font-semibold text-violet-600 cursor-pointer hover:bg-violet-50 transition-all">
          파일 선택 (PDF, HWP, DOCX)
          <input type="file" className="hidden" accept=".pdf,.hwp,.hwpx,.docx,.doc,.xlsx,.txt" onChange={handleUpload} />
        </label>
      </div>
      {files.length > 0 && (
        <div className="space-y-1">
          {files.map((f, i) => (
            <div key={i} className="flex items-center gap-2 px-2 py-1.5 bg-white rounded-lg border text-[11px]">
              <span className="px-1.5 py-0.5 bg-violet-100 text-violet-600 text-[9px] font-bold rounded">
                {FILE_TYPE_OPTIONS.find(ft => ft.value === f.type)?.label || f.type}
              </span>
              <span className="truncate text-slate-700 flex-1">{f.name}</span>
              {f.uploading ? (
                <span className="text-violet-500 animate-pulse text-[10px]">분석 중...</span>
              ) : f.summary.includes("\n") || f.summary.length > 50 ? (
                <details className="text-[10px] text-emerald-700">
                  <summary className="cursor-pointer font-medium">AI 분석 완료 ▼</summary>
                  <div className="mt-1 p-2 bg-emerald-50 rounded text-[10px] whitespace-pre-wrap">{f.summary}</div>
                </details>
              ) : (
                <span className="text-emerald-600 font-medium text-[10px]">{f.summary}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
