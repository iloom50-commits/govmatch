"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useToast } from "@/components/ui/Toast";
import DOMPurify from "dompurify";
import IndustryPicker from "@/components/shared/IndustryPicker";
import EstablishmentDateInput from "@/components/shared/EstablishmentDateInput";

const API = process.env.NEXT_PUBLIC_API_URL;

// ─── 타입 ───
interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  choices?: string[];
  announcements?: any[];
  matched?: any[];          // 매칭 결과 카드 표시용
  showReportButton?: boolean; // 보고서 생성 버튼 표시용
  done?: boolean;
  rag_sources?: any[];      // 답변에 참고한 출처 (공고 섹션) 카드
  // [재설계 05] PRO 공고상담 V2 — 전문가 인사이트
  verdict_for_client?: "eligible" | "conditional" | "ineligible" | null;
  expert_insights?: {
    selection_rate_estimate?: string;
    evaluation_weights?: Array<{ criterion: string; weight: number; focus?: string }>;
    common_pitfalls?: string[];
    application_tips?: string[];
    similar_programs?: Array<{ title: string; reason: string }>;
    document_checklist?: string[];
  } | null;
}

interface ClientProfile {
  id: number;
  client_name: string;
  client_type?: string;
  address_city?: string;
  industry_name?: string;
  revenue_bracket?: string;
  contact_name?: string;
  contact_email?: string;
  status?: string;
}

type ActiveView = "chat" | "clients" | "history" | "reports" | "announce_search";
type FlowState = "idle" | "info_collect" | "matching" | "analysis" | "done";
type ClientCategory = "" | "individual_biz" | "corporate" | "individual" | "unknown";

// ─── SVG 아이콘 ───
const Icons = {
  chat: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-12.375 0c0 4.556 3.694 8.25 8.25 8.25 1.302 0 2.533-.302 3.63-.844l4.37 1.094-1.094-4.37A8.21 8.21 0 0020.25 12c0-4.556-3.694-8.25-8.25-8.25S3.75 7.444 3.75 12z" /></svg>,
  clients: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" /></svg>,
  history: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
  reports: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" /></svg>,
  workflow: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z" /></svg>,
  link: <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" /></svg>,
  attach: <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" /></svg>,
  send: <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" /></svg>,
  sun: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" /></svg>,
  moon: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" /></svg>,
  close: <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>,
  menu: <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" /></svg>,
  info: <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" /></svg>,
  plus: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>,
  check: <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>,
};

// ─── 다크/라이트 테마 토큰 ───
const theme = {
  dark: {
    root: "bg-[#0d0e1a] text-slate-100",
    header: "bg-[#0d0e1a] border-b border-white/[0.06]",
    leftNav: "bg-[#111222] border-r border-white/[0.06]",
    center: "bg-[#151628]",
    right: "bg-[#111222] border-l border-white/[0.06]",
    card: "bg-[#1a1c30]",
    cardHover: "hover:bg-[#1f2140]",
    cardBorder: "border-white/[0.06]",
    input: "bg-[#1a1c30] border-white/[0.08] text-slate-100 placeholder-slate-400 focus:border-violet-500/50 focus:ring-violet-500/20",
    bubble: "bg-[#1e2040] text-slate-100",
    menuActive: "bg-violet-500/10 text-violet-300 border-l-2 border-violet-500",
    menuInactive: "text-slate-300 hover:text-white hover:bg-white/[0.03]",
    sectionTitle: "text-slate-300",
    border: "border-white/[0.06]",
    muted: "text-slate-300",
    flowActive: "bg-violet-500/15 text-violet-300 border border-violet-500/30",
    flowDone: "text-emerald-300",
    flowPending: "text-slate-400",
    serviceActive: "bg-violet-500/10 border border-violet-500/20",
    serviceInactive: "bg-white/[0.03] border border-white/[0.06]",
    emptyIcon: "bg-[#1a1c30] border border-white/[0.08]",
  },
  light: {
    root: "bg-slate-50 text-slate-800",
    header: "bg-gradient-to-r from-violet-700 to-purple-700",
    leftNav: "bg-white border-r border-slate-200 shadow-sm",
    center: "bg-white",
    right: "bg-slate-50 border-l border-slate-200",
    card: "bg-white",
    cardHover: "hover:bg-slate-50",
    cardBorder: "border-slate-200",
    input: "bg-slate-50 border-slate-200 text-slate-700 placeholder-slate-400 focus:border-violet-400 focus:ring-violet-200",
    bubble: "bg-slate-100 text-slate-800",
    menuActive: "bg-violet-50 text-violet-700 border-l-2 border-violet-600",
    menuInactive: "text-slate-600 hover:bg-slate-50",
    sectionTitle: "text-slate-400",
    border: "border-slate-200",
    muted: "text-slate-400",
    flowActive: "bg-violet-100 text-violet-700",
    flowDone: "text-emerald-600",
    flowPending: "text-slate-400",
    serviceActive: "bg-violet-50 border border-violet-200",
    serviceInactive: "bg-slate-50 border border-slate-200",
    emptyIcon: "bg-violet-50 border border-violet-100",
  },
};

// ─── 메인 컴포넌트 ───
export default function ProSecretary({ onClose, planStatus, onUpgrade, userType }: {
  onClose: () => void;
  planStatus?: any;
  onUpgrade?: () => void;
  userType?: string | null;
}) {
  const { toast } = useToast();

  // 상태
  const [activeView, setActiveView] = useState<ActiveView>("chat");
  const [selectedClient, setSelectedClient] = useState<ClientProfile | null>(null);
  const [existingClients, setExistingClients] = useState<ClientProfile[]>([]);
  const [flowState, setFlowState] = useState<FlowState>("idle");
  const [clientCategory, setClientCategory] = useState<ClientCategory>("");
  // 상담 종류 선택 (첫 화면 2카드)
  const [consultType, setConsultType] = useState<"matching" | "announcement" | null>(null);

  // 입력 폼 (고객 정보 수집)
  const [showProfileForm, setShowProfileForm] = useState(false);
  const PROFILE_FORM_STORAGE_KEY = "pro_secretary_profile_form_v1";
  const [profileForm, setProfileForm] = useState(() => {
    // localStorage에서 복원 (브라우저 새로고침/뒤로가기 방어)
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(PROFILE_FORM_STORAGE_KEY);
        if (saved) return JSON.parse(saved);
      } catch {}
    }
    return {
      company_name: "",
      establishment_year: "",
      establishment_date: "",
      industry: "",           // 표시용 라벨
      industry_code: "",      // KSIC 코드 (5자리)
      industry_name: "",      // KSIC 이름
      revenue_bracket: "",
      employee_bracket: "",
      address_city: "",
      interests: [] as string[],
      // 선택 필드 — 우대·제외 판정용
      representative_age: "",         // 대표 연령대
      is_women_enterprise: false,     // 여성기업
      is_youth_enterprise: false,     // 청년기업 (대표 만39세 이하)
      certifications: [] as string[], // 벤처/이노비즈/사회적기업 등
      is_restart: false,              // 재창업 여부
      memo: "",                       // 컨설턴트 메모
    };
  });

  // profileForm 변경 시 localStorage 자동 저장
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem(PROFILE_FORM_STORAGE_KEY, JSON.stringify(profileForm));
    } catch {}
  }, [profileForm]);

  // 입력 중인 값이 있으면 페이지 이탈 시 경고
  useEffect(() => {
    if (typeof window === "undefined") return;
    const hasInput = !!(profileForm.company_name?.trim() || profileForm.industry?.trim() || (profileForm.interests && profileForm.interests.length > 0) || profileForm.address_city?.trim());
    if (!hasInput || !showProfileForm) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [profileForm, showProfileForm]);

  // 대화
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [collectedProfile, setCollectedProfile] = useState<any>({});  // 백그라운드 수집 정보
  const [showMatchModal, setShowMatchModal] = useState(false);  // 매칭 확인 모달
  const [matchProfile, setMatchProfile] = useState<any>({});  // 모달에서 편집 중인 프로필
  const [loading, setLoading] = useState(false);
  const [systemContext, setSystemContext] = useState("");
  const [activeAnnouncementId, setActiveAnnouncementId] = useState<number | null>(null);
  const [typing, setTyping] = useState(false); // 타이핑 애니메이션 중
  const [typingText, setTypingText] = useState(""); // 현재까지 타이핑된 텍스트
  const typingRef = useRef<NodeJS.Timeout | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // 모바일
  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(false);

  // 최소화 상태
  const [minimized, setMinimized] = useState(false);

  // 다크모드
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const saved = localStorage.getItem("pro_dark_mode");
    if (saved === "true") setDark(true);
  }, []);
  const toggleDark = () => {
    setDark(d => { localStorage.setItem("pro_dark_mode", String(!d)); return !d; });
  };

  const t = dark ? theme.dark : theme.light;

  // 상담 종료 — 명시적 종료
  const handleEndConsult = useCallback(() => {
    if (messages.length === 0 && !clientCategory) return;
    if (!window.confirm("이 상담을 종료하시겠습니까?\n(상담 내용은 자동 저장됩니다)")) return;
    setClientCategory("");
    setMessages([]);
    setFlowState("idle");
    setSelectedClient(null);
    setSystemContext("");
    setActiveAnnouncementId(null);
    setShowProfileForm(false);
    setActiveView("chat");
    setSessionId(null);
    setConsultType(null);
    localStorage.removeItem("pro_session_id");
    toast("상담이 종료되었습니다", "info");
  }, [messages.length, clientCategory, toast]);

  // 뒤로가기: 단계별 복귀 (상담중→고객유형→상담종류→닫기)
  const handleBack = useCallback(() => {
    if (activeView !== "chat") {
      setActiveView("chat");
      window.history.pushState({ proDash: true }, "");
      return;
    }
    if (clientCategory || messages.length > 0) {
      setClientCategory("");
      setMessages([]);
      setFlowState("idle");
      setSelectedClient(null);
      setSystemContext("");
      setSessionId(null);
      localStorage.removeItem("pro_session_id");
      window.history.pushState({ proDash: true }, "");
      return;
    }
    if (consultType) {
      // 고객 유형 선택 화면에서 뒤로 → 상담 종류 선택으로
      setConsultType(null);
      window.history.pushState({ proDash: true }, "");
      return;
    }
    onClose();
  }, [activeView, clientCategory, messages.length, consultType, onClose]);

  useEffect(() => {
    window.history.pushState({ proDash: true }, "");
    const onPopState = () => handleBack();
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [handleBack]);

  const getToken = () => localStorage.getItem("auth_token") || "";
  const headers = useCallback(() => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${getToken()}`,
  }), []);

  // 스크롤
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  // 기존 고객 목록 로드 (마운트 시 1회)
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/api/pro/clients`, { headers: headers() });
        if (res.ok) {
          const data = await res.json();
          setExistingClients(data.clients || []);
        }
      } catch (e) { console.error("[PRO]", e); }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 세션 ID 상태 — localStorage에 유지하여 새로고침 후에도 대화 맥락 이어짐
  const [sessionId, setSessionId] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("pro_session_id") || null;
    }
    return null;
  });
  // sessionId 변경 시 localStorage에 동기화
  useEffect(() => {
    if (sessionId) {
      localStorage.setItem("pro_session_id", sessionId);
    }
  }, [sessionId]);

  // ─── AI 대화 전송 ───
  const sendToAI = useCallback(async (chatHistory: ChatMessage[], options?: { action?: "match" | "consult"; profile_override?: any; announcement_id?: number }) => {
    setLoading(true);
    try {
      const messagesPayload = chatHistory.map((m, i) => ({
        role: m.role,
        text: (i === 0 && m.role === "user" && systemContext) ? `${systemContext}\n\n${m.text}` : m.text,
      }));

      // [재설계 04] action 결정 — 명시적 override 우선 (React state 비동기 문제 우회)
      const annId = options?.announcement_id ?? activeAnnouncementId;
      const action = options?.action || (annId ? "consult" : "match");

      const res = await fetch(`${API}/api/pro/consultant/chat`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          messages: messagesPayload,
          announcement_id: annId,
          action,
          profile_override: options?.profile_override || null,
          session_id: sessionId,
          client_category: clientCategory || null,
          client_id: selectedClient?.id || null,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast(err.detail || "AI 응답 오류", "error");
        setLoading(false);
        return;
      }

      const data = await res.json();
      const fullText = data.reply || "";
      const choices = data.choices || [];
      const done = data.done || false;

      // 세션 ID 저장 (첫 응답에서만 세팅됨)
      if (data.session_id && !sessionId) {
        setSessionId(data.session_id);
      }

      // 백그라운드 수집 정보 업데이트 (모든 응답에서)
      if (data.collected || data.profile) {
        const newCollected = { ...collectedProfile, ...(data.collected || {}), ...(data.profile || {}) };
        setCollectedProfile(newCollected);
      }

      // 타이핑 애니메이션 시작
      setLoading(false);
      setTyping(true);
      setTypingText("");

      // 타이핑 중인 메시지를 messages에 추가 (빈 텍스트로 시작)
      const typingMsg: ChatMessage = { role: "assistant", text: "", choices: [], done };
      setMessages([...chatHistory, typingMsg]);

      let charIdx = 0;
      const speed = Math.max(10, Math.min(30, 1500 / fullText.length)); // 전체 1.5초 내외
      if (typingRef.current) clearInterval(typingRef.current);
      typingRef.current = setInterval(() => {
        charIdx += 1;
        const current = fullText.slice(0, charIdx);
        setTypingText(current);
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === "assistant") {
            updated[updated.length - 1] = { ...last, text: current };
          }
          return updated;
        });

        if (charIdx >= fullText.length) {
          clearInterval(typingRef.current!);
          typingRef.current = null;
          // 타이핑 완료 — choices + 매칭 결과 + 보고서 버튼 표시
          setMessages(prev => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.role === "assistant") {
              const matched = data.matched_announcements || [];
              const ragSources = data.rag_sources || [];
              updated[updated.length - 1] = {
                ...last,
                text: fullText,
                choices,
                matched: matched.length > 0 ? matched : undefined,
                showReportButton: matched.length > 0,
                rag_sources: ragSources.length > 0 ? ragSources : undefined,
                // [재설계 05] PRO 공고상담 V2 — 전문가 인사이트 저장
                verdict_for_client: data.verdict_for_client || undefined,
                expert_insights: data.expert_insights || undefined,
              };
            }
            return updated;
          });
          setTyping(false);
          setTypingText("");
        }
      }, speed);

      if (done && data.profile) {
        setFlowState("matching");
      }
    } catch {
      toast("서버 연결에 실패했습니다.", "error");
      setLoading(false);
    }
  }, [headers, systemContext, toast, sessionId, clientCategory, activeAnnouncementId, collectedProfile]);

  // ─── 메시지 전송 ───
  const handleSend = (text: string) => {
    if (!text.trim() || loading || typing) return;
    const userMsg: ChatMessage = { role: "user", text: text.trim() };
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInput("");
    // [재설계 04] 재매칭 키워드 감지 시 action=match + 현재 프로필로 재매칭
    const rematchKeywords = ["재매칭", "다시 매칭", "매칭 진행", "이 조건으로 매칭", "매칭해"];
    const isRematch = rematchKeywords.some(kw => text.includes(kw));
    if (isRematch) {
      sendToAI(newHistory, { action: "match", profile_override: collectedProfile });
    } else {
      sendToAI(newHistory);
    }
    if (flowState === "idle") setFlowState("info_collect");
  };

  // ─── 파일 첨부 (multipart 업로드 → 서버에서 텍스트 추출) ───
  const handleFileAttach = async (file: File) => {
    if (file.size > 20 * 1024 * 1024) { toast("20MB 이하만 가능", "error"); return; }
    setMessages(prev => [...prev, { role: "user", text: `📎 ${file.name} 첨부` }]);
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const analyzeRes = await fetch(`${API}/api/pro/files/upload-analyze`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: formData,
      });
      const analyzeData = analyzeRes.ok ? await analyzeRes.json() : { summary: "분석 실패", extracted_text: "" };
      setMessages(prev => [...prev, {
        role: "assistant",
        text: `📊 **${file.name}** 분석 결과:\n\n${analyzeData.summary}\n\n이 정보를 바탕으로 어떤 작업을 진행하시겠습니까?`,
        choices: ["맞춤 지원사업 매칭", "자격요건 검토", "추가 자료 첨부"],
      }]);
      const extractedText = analyzeData.extracted_text || analyzeData.summary || "";
      if (extractedText) {
        setSystemContext(prev => `${prev}\n\n[첨부: ${file.name}]\n${extractedText.substring(0, 5000)}`);
      }
    } catch {
      setMessages(prev => [...prev, { role: "assistant", text: "파일 분석에 실패했습니다." }]);
    }
    setLoading(false);
  };

  // ─── 새 상담 시작 ───
  const startNewChat = (category: ClientCategory, client?: ClientProfile) => {
    setActiveView("chat");
    setClientCategory(category);
    setFlowState("idle");
    setSelectedClient(client || null);
    setLeftOpen(false);
    setMessages([]);

    if (client) {
      // 기존 고객 → 정보 이미 있으므로 바로 대화 시작
      setShowProfileForm(false);
      setSystemContext(`[전문가 상담 모드] 기존 고객: ${client.client_name}\n지역: ${client.address_city || ""}\n업종: ${client.industry_name || ""}\n매출: ${client.revenue_bracket || ""}`);
      setMessages([{
        role: "assistant",
        text: `**${client.client_name}** 고객 정보를 불러왔습니다.\n\n지역: ${client.address_city || "미등록"}\n업종: ${client.industry_name || "미등록"}\n매출: ${client.revenue_bracket || "미등록"}\n\n어떤 상담을 진행하시겠습니까?`,
        choices: ["맞춤 지원사업 매칭", "첨부 자료 분석", "자격요건 검토"],
      }]);
    } else {
      // 신규 고객 → 입력 폼 표시
      setShowProfileForm(true);
      setProfileForm({
        company_name: "",
        establishment_year: "",
        establishment_date: "",
        industry: "",
        industry_code: "",
        industry_name: "",
        revenue_bracket: "",
        employee_bracket: "",
        address_city: "",
        interests: [],
      });
    }
  };

  // ─── 입력 폼 제출 → 즉시 매칭 실행 (재설계 04) ───
  const handleProfileSubmit = () => {
    const f = profileForm;
    setShowProfileForm(false);
    setFlowState("matching");
    try { if (typeof window !== "undefined") localStorage.removeItem(PROFILE_FORM_STORAGE_KEY); } catch {}

    const isIndiv = clientCategory === "individual";
    const dateValue = f.establishment_date || (f.establishment_year ? `${f.establishment_year}-01-01` : "");

    // 최소한의 필수 필드 체크
    const hasAnyInfo = !!(f.company_name?.trim() || dateValue || f.industry_code || f.revenue_bracket || f.employee_bracket || f.address_city || (f.interests && f.interests.length > 0));
    if (!hasAnyInfo) {
      toast("고객 정보를 먼저 입력해주세요. (최소 1개 필드 필수)", "error");
      setShowProfileForm(true);
      return;
    }

    // 매칭 엔진이 받을 프로필 구조
    const matchProfile = {
      company_name: f.company_name?.trim() || (isIndiv ? "개인" : ""),
      industry_code: f.industry_code || "",
      address_city: f.address_city || "",
      establishment_date: dateValue,
      revenue_bracket: f.revenue_bracket || "",
      employee_count_bracket: f.employee_bracket || "",
      interests: (f.interests || []).join(","),
      certifications: (f.certifications || []).join(","),
      user_type: isIndiv ? "individual" : (clientCategory === "individual_biz" ? "sole_proprietor" : "corporate"),
      // 우대/제외 판정용 선택 필드
      representative_age_range: f.representative_age_range || "",
      is_women_enterprise: f.is_women_enterprise || false,
      is_youth_enterprise: f.is_youth_enterprise || false,
      is_restart: f.is_restart || false,
    };

    // 사용자 시각화용 요약 메시지 (messages에 기록)
    const catLabel = clientCategory === "individual_biz" ? "개인사업자" : clientCategory === "corporate" ? "법인사업자" : clientCategory === "individual" ? "개인" : "고객";
    const summaryLines = [`📋 **${catLabel} 고객 프로필로 매칭 실행**`];
    if (matchProfile.company_name) summaryLines.push(`• ${isIndiv ? "이름" : "기업명"}: ${matchProfile.company_name}`);
    if (matchProfile.industry_code) summaryLines.push(`• 업종: ${f.industry || matchProfile.industry_code}`);
    if (dateValue) summaryLines.push(`• ${isIndiv ? "생년월일" : "설립일"}: ${dateValue}`);
    if (matchProfile.revenue_bracket) summaryLines.push(`• 매출: ${matchProfile.revenue_bracket}`);
    if (matchProfile.employee_count_bracket) summaryLines.push(`• 직원수: ${matchProfile.employee_count_bracket}`);
    if (matchProfile.address_city) summaryLines.push(`• 지역: ${matchProfile.address_city}`);
    if (matchProfile.interests) summaryLines.push(`• 관심분야: ${matchProfile.interests}`);

    const seedHistory: ChatMessage[] = [
      { role: "user", text: summaryLines.join("\n") },
    ];
    setMessages(seedHistory);
    // [재설계 04] Mode A 제거 — 자연어 수집 없이 즉시 매칭 엔진 호출
    sendToAI(seedHistory, { action: "match", profile_override: matchProfile });
  };

  // ─── 마크다운 렌더링 ───
  const renderText = (text: string) => {
    let html = text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br/>");
    return DOMPurify.sanitize(html);
  };

  // ─── 플로우 상태 ───
  const flowSteps = [
    { key: "idle", label: "대기" },
    { key: "info_collect", label: "정보 수집" },
    { key: "matching", label: "공고 매칭" },
    { key: "analysis", label: "상세 분석" },
    { key: "done", label: "완료" },
  ];

  // 최소화 상태일 때 — 우측 하단 플로팅 바
  if (minimized) {
    const isWorking = loading || typing;
    return (
      <button
        onClick={() => setMinimized(false)}
        className={`fixed bottom-4 right-4 z-[60] flex items-center gap-3 px-4 py-3 rounded-2xl shadow-2xl transition-all hover:scale-105 active:scale-95 ${
          dark ? "bg-[#111222] border border-violet-500/30 text-slate-100" : "bg-white border border-violet-300 text-slate-800"
        }`}
        title="PRO 대시보드 펼치기"
      >
        <div className="w-8 h-8 rounded-lg bg-violet-600 flex items-center justify-center text-white text-[10px] font-black">
          PRO
        </div>
        <div className="text-left">
          <p className="text-[12px] font-bold">전문가 대시보드</p>
          <p className={`text-[10px] ${isWorking ? "text-violet-400" : (dark ? "text-slate-300" : "text-slate-500")}`}>
            {isWorking ? "AI 분석 중..." : (clientCategory ? "상담 진행 중" : "대기 중")}
          </p>
        </div>
        <svg className="w-4 h-4 text-violet-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
        </svg>
      </button>
    );
  }

  return (
    <div className={`fixed inset-0 z-[60] flex flex-col transition-colors duration-300 ${t.root}`}>
      {/* ─── 헤더 ─── */}
      <header className={`flex items-center justify-between px-4 h-12 flex-shrink-0 ${t.header} ${dark ? "text-slate-200" : "text-white"}`}>
        <div className="flex items-center gap-3">
          <button onClick={() => setLeftOpen(!leftOpen)} className="lg:hidden p-1.5 hover:bg-white/10 rounded-lg transition-colors">
            {Icons.menu}
          </button>
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-violet-600 flex items-center justify-center text-white text-[10px] font-black tracking-tight">
              PRO
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[14px] font-bold tracking-tight">전문가 대시보드</span>
              <span className="flex items-center gap-1 text-[10px] text-emerald-400 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                연결됨
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {/* 상담 종료 (상담 진행 중에만 표시) */}
          {(clientCategory || messages.length > 0) && (
            <button onClick={handleEndConsult}
              className="px-3 py-1.5 bg-red-500/15 hover:bg-red-500/25 text-red-300 hover:text-red-200 rounded-lg text-[11px] font-bold transition-colors border border-red-500/30 hidden sm:flex items-center gap-1"
              title="현재 상담 종료">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              상담 종료
            </button>
          )}
          <button onClick={toggleDark} className="p-2 hover:bg-white/10 rounded-lg transition-colors" title={dark ? "라이트 모드" : "다크 모드"}>
            {dark ? Icons.sun : Icons.moon}
          </button>
          <button onClick={() => setRightOpen(!rightOpen)} className="lg:hidden p-2 hover:bg-white/10 rounded-lg transition-colors">
            {Icons.info}
          </button>
          <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg transition-colors" title="닫기">
            {Icons.close}
          </button>
        </div>
      </header>

      {/* ─── 3패널 그리드 ─── */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[220px_1fr_280px] overflow-hidden">

        {/* ═══ 좌측 네비 ═══ */}
        <nav className={`${leftOpen ? "fixed inset-0 z-50 bg-black/40 lg:relative lg:bg-transparent" : "hidden lg:flex"} lg:flex flex-col overflow-y-auto ${t.leftNav}`}>
          <div className={`${leftOpen ? `w-[240px] h-full shadow-2xl ${dark ? "bg-[#111222]" : "bg-white"}` : "w-full"} flex flex-col`}>
            {leftOpen && (
              <button onClick={() => setLeftOpen(false)} className="lg:hidden self-end p-2 m-2 text-slate-400 hover:text-slate-200">
                {Icons.close}
              </button>
            )}

            {/* 새 상담 버튼 */}
            <div className={`p-3 border-b ${t.border}`}>
              <button
                onClick={() => { setClientCategory(""); setMessages([]); setActiveView("chat"); setLeftOpen(false); setConsultType(null); }}
                className="w-full py-2.5 bg-violet-600 text-white rounded-xl text-[13px] font-bold hover:bg-violet-500 transition-all active:scale-[0.98] flex items-center justify-center gap-1.5"
              >
                {Icons.plus}
                <span>새 상담</span>
              </button>
            </div>

            {/* 기존 고객 선택 */}
            {existingClients.length > 0 && (
              <div className={`p-3 border-b ${t.border}`}>
                <p className={`text-[10px] font-bold uppercase tracking-wider mb-1.5 ${t.sectionTitle}`}>기존 고객</p>
                <select
                  onChange={(e) => {
                    const c = existingClients.find(c => c.id === Number(e.target.value));
                    if (c) startNewChat(c.client_type === "individual" ? "individual" : "corporate", c);
                  }}
                  className={`w-full px-2.5 py-2 rounded-lg text-[12px] outline-none border transition-colors ${t.input}`}
                  value=""
                >
                  <option value="">고객 선택...</option>
                  {existingClients.map(c => (
                    <option key={c.id} value={c.id}>{c.client_name} ({c.address_city || ""})</option>
                  ))}
                </select>
              </div>
            )}

            {/* 메뉴 */}
            <div className="flex-1 py-2">
              {([
                { view: "chat" as ActiveView, icon: Icons.chat, label: "지원사업 매칭 상담" },
                { view: "announce_search" as ActiveView, icon: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>, label: "특정 공고 상담" },
                { view: "clients" as ActiveView, icon: Icons.clients, label: "고객 관리" },
                { view: "history" as ActiveView, icon: Icons.history, label: "상담 이력" },
                { view: "reports" as ActiveView, icon: Icons.reports, label: "보고서" },
              ]).map(item => (
                <button
                  key={item.view}
                  onClick={() => { setActiveView(item.view); setLeftOpen(false); }}
                  className={`w-full px-4 py-2.5 flex items-center gap-3 text-left transition-all text-[13px] font-medium ${
                    activeView === item.view ? t.menuActive : t.menuInactive
                  }`}
                >
                  {item.icon}
                  <span>{item.label}</span>
                  {item.view === "chat" && messages.length > 0 && (
                    <span className={`ml-auto text-[9px] px-1.5 py-0.5 rounded-full font-bold ${dark ? "bg-violet-500/20 text-violet-400" : "bg-violet-100 text-violet-600"}`}>
                      {messages.length}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* 연동 서비스 — 향후 제공 */}
            <div className={`p-3 border-t hidden lg:block ${t.border}`}>
            </div>
          </div>
        </nav>

        {/* ═══ 중앙 메인 ═══ */}
        <div className={`flex flex-col overflow-hidden ${t.center}`}>
          {activeView === "chat" ? (
            <>
              {/* 상단 바 — 현재 상태 */}
              {clientCategory && (
                <div className={`flex items-center justify-between px-4 lg:px-6 h-10 border-b flex-shrink-0 ${t.border}`}>
                  <div className="flex items-center gap-2 text-[12px]">
                    <span className={`font-semibold ${dark ? "text-violet-400" : "text-violet-700"}`}>
                      {selectedClient ? selectedClient.client_name : clientCategory === "individual_biz" ? "개인사업자" : clientCategory === "corporate" ? "법인사업자" : clientCategory === "individual" ? "개인" : "유형 미정"}
                    </span>
                    <span className={`${t.muted}`}>·</span>
                    <span className={`${t.muted}`}>{flowSteps.find(s => s.key === flowState)?.label || "대기"}</span>
                  </div>
                  <span className={`text-[11px] ${t.muted}`}>{flowSteps.find(s => s.key === flowState)?.label}</span>
                </div>
              )}

              {/* Step 1: 상담 종류 선택 (2카드) — consultType이 null일 때 */}
              {!clientCategory && messages.length === 0 && !showProfileForm && !consultType ? (
                <div className="flex-1 flex flex-col items-center justify-center px-6 overflow-y-auto">
                  <div className="max-w-2xl text-center w-full">
                    <div className={`w-16 h-16 mx-auto mb-5 rounded-2xl flex items-center justify-center ${t.emptyIcon}`}>
                      <span className="text-3xl">👋</span>
                    </div>
                    <h2 className={`text-xl font-bold mb-2 ${dark ? "text-slate-100" : "text-slate-800"}`}>어떤 상담을 도와드릴까요?</h2>
                    <p className={`text-[13px] mb-8 ${t.muted}`}>
                      상담 종류를 선택하시면 AI 상담이 시작됩니다.
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-xl mx-auto">
                      <button
                        onClick={() => setConsultType("matching")}
                        className={`p-6 rounded-2xl border-2 transition-all text-left active:scale-[0.98] ${dark ? `${t.cardBorder} border ${t.card} hover:border-violet-500/60 hover:bg-violet-500/10` : "border-slate-200 hover:border-violet-500 hover:bg-violet-50 bg-white"} hover:shadow-lg`}>
                        <div className="text-4xl mb-3">🏢</div>
                        <p className={`text-base font-bold mb-1 ${dark ? "text-slate-100" : "text-slate-800"}`}>지원사업 매칭 상담</p>
                        <p className={`text-[12px] mb-3 ${t.muted}`}>고객 정보로 맞춤 공고 찾기</p>
                        <p className={`text-[11px] leading-relaxed ${dark ? "text-slate-400" : "text-slate-500"}`}>
                          고객 프로필 수집 → 조건에 맞는 지원사업 매칭 → 자격 요건 심화 상담
                        </p>
                      </button>
                      <button
                        onClick={() => { setActiveView("announce_search"); }}
                        className={`p-6 rounded-2xl border-2 transition-all text-left active:scale-[0.98] ${dark ? `${t.cardBorder} border ${t.card} hover:border-indigo-500/60 hover:bg-indigo-500/10` : "border-slate-200 hover:border-indigo-500 hover:bg-indigo-50 bg-white"} hover:shadow-lg`}>
                        <div className="text-4xl mb-3">📋</div>
                        <p className={`text-base font-bold mb-1 ${dark ? "text-slate-100" : "text-slate-800"}`}>특정 공고 상담</p>
                        <p className={`text-[12px] mb-3 ${t.muted}`}>알고 있는 공고 분석·자격 판정</p>
                        <p className={`text-[11px] leading-relaxed ${dark ? "text-slate-400" : "text-slate-500"}`}>
                          공고명·기관·키워드로 검색 → 12섹션 상세 보고서 → 자격 요건 질문
                        </p>
                      </button>
                    </div>
                  </div>
                </div>
              ) : /* Step 2: 고객 유형 선택 (매칭 선택 후) */
              !clientCategory && messages.length === 0 && !showProfileForm && consultType === "matching" ? (
                <div className="flex-1 flex flex-col items-center justify-center px-6 overflow-y-auto">
                  <div className="max-w-md text-center">
                    <button
                      onClick={() => setConsultType(null)}
                      className={`mb-4 text-[12px] font-medium flex items-center gap-1 mx-auto ${dark ? "text-slate-400 hover:text-slate-200" : "text-slate-500 hover:text-slate-700"}`}
                    >
                      ← 상담 종류 다시 선택
                    </button>
                    <div className={`w-16 h-16 mx-auto mb-5 rounded-2xl flex items-center justify-center ${t.emptyIcon}`}>
                      <svg className="w-8 h-8 text-violet-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155" />
                      </svg>
                    </div>
                    <h2 className={`text-xl font-bold mb-2 ${dark ? "text-slate-100" : "text-slate-800"}`}>고객 유형을 선택해 주세요</h2>
                    <p className={`text-[13px] mb-8 ${t.muted}`}>
                      고객 정보 수집 → 맞춤 지원사업 매칭 → 자격 요건 분석
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { key: "corporate" as ClientCategory, label: "사업자", icon: "🏢", desc: "법인 · 개인사업자" },
                        { key: "individual" as ClientCategory, label: "개인", icon: "👤", desc: "취업·복지·주거" },
                      ].map(opt => (
                        <button key={opt.key} onClick={() => startNewChat(opt.key)}
                          className={`p-4 rounded-xl border transition-all text-left active:scale-[0.98] ${dark ? `${t.cardBorder} border ${t.card} hover:border-violet-500/40 hover:bg-violet-500/10` : "border-slate-200 hover:border-violet-400 hover:bg-violet-50 bg-white"}`}>
                          <span className="text-2xl">{opt.icon}</span>
                          <p className={`text-[13px] font-bold mt-2 ${dark ? "text-slate-200" : "text-slate-800"}`}>{opt.label}</p>
                          <p className={`text-[10px] mt-0.5 ${t.muted}`}>{opt.desc}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : showProfileForm ? (
                /* ═══ 고객 정보 입력 폼 (버튼식) ═══ */
                <ProfileInputForm
                  dark={dark}
                  t={t}
                  clientCategory={clientCategory}
                  profileForm={profileForm}
                  setProfileForm={setProfileForm}
                  onSubmit={handleProfileSubmit}
                  onBack={() => { setShowProfileForm(false); setClientCategory(""); }}
                />
              ) : (
                <>
                  {/* 대화 영역 */}
                  <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 lg:px-6 py-4 space-y-3">
                    {messages.map((msg, i) => {
                      // 시드용 시스템 메시지(`[새 케이스 시작]`)는 채팅에 표시하지 않음
                      if (msg.role === "user" && msg.text.startsWith("[새 케이스 시작]")) return null;
                      return (
                      <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                        <div className="max-w-[80%] overflow-hidden">
                          <div className={`px-4 py-3 rounded-2xl text-[15px] md:text-[14px] leading-relaxed break-words overflow-wrap-anywhere ${
                            msg.role === "user"
                              ? "bg-violet-600 text-white rounded-br-md"
                              : `${t.bubble} rounded-bl-md`
                          }`} dangerouslySetInnerHTML={{ __html: renderText(msg.text) }} />
                          {/* 답변 근거 패널 제거 (RAG 관련도 낮아 UX 혼선 유발) */}
                          {/* [재설계 05] PRO 공고상담 V2 — 전문가 인사이트 패널 */}
                          {msg.role === "assistant" && msg.expert_insights && (
                            <div className={`mt-2 rounded-xl border overflow-hidden ${dark ? "border-violet-500/30 bg-violet-500/5" : "border-violet-200 bg-violet-50/50"}`}>
                              {/* 적합성 배지 */}
                              {msg.verdict_for_client && (
                                <div className={`px-3 py-2 border-b text-[12px] font-bold flex items-center gap-2 ${dark ? "border-violet-500/20" : "border-violet-200"}`}>
                                  {msg.verdict_for_client === "eligible" && <span className="text-emerald-500">✅ 신청 가능</span>}
                                  {msg.verdict_for_client === "conditional" && <span className="text-amber-500">⚠️ 조건부 가능</span>}
                                  {msg.verdict_for_client === "ineligible" && <span className="text-rose-500">⊘ 신청 불가</span>}
                                  {msg.expert_insights.selection_rate_estimate && (
                                    <span className={`ml-auto text-[11px] font-semibold ${dark ? "text-violet-300" : "text-violet-700"}`}>
                                      예상 선정률 {msg.expert_insights.selection_rate_estimate}
                                    </span>
                                  )}
                                </div>
                              )}
                              <div className="p-3 space-y-3 text-[12px]">
                                {msg.expert_insights.common_pitfalls && msg.expert_insights.common_pitfalls.length > 0 && (
                                  <div>
                                    <div className={`font-bold mb-1 ${dark ? "text-rose-400" : "text-rose-600"}`}>⚠️ 자주 떨어지는 이유</div>
                                    <ul className={`space-y-0.5 pl-4 list-disc ${dark ? "text-slate-300" : "text-slate-700"}`}>
                                      {msg.expert_insights.common_pitfalls.map((p, pi) => <li key={pi}>{p}</li>)}
                                    </ul>
                                  </div>
                                )}
                                {msg.expert_insights.application_tips && msg.expert_insights.application_tips.length > 0 && (
                                  <div>
                                    <div className={`font-bold mb-1 ${dark ? "text-emerald-400" : "text-emerald-600"}`}>💡 전문가 팁</div>
                                    <ul className={`space-y-0.5 pl-4 list-disc ${dark ? "text-slate-300" : "text-slate-700"}`}>
                                      {msg.expert_insights.application_tips.map((p, pi) => <li key={pi}>{p}</li>)}
                                    </ul>
                                  </div>
                                )}
                                {msg.expert_insights.evaluation_weights && msg.expert_insights.evaluation_weights.length > 0 && (
                                  <div>
                                    <div className={`font-bold mb-1 ${dark ? "text-violet-400" : "text-violet-600"}`}>📊 평가 배점</div>
                                    <div className="space-y-1">
                                      {msg.expert_insights.evaluation_weights.map((w, wi) => (
                                        <div key={wi} className={`flex items-center gap-2 ${dark ? "text-slate-300" : "text-slate-700"}`}>
                                          <span className="font-semibold min-w-[80px]">{w.criterion}</span>
                                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${dark ? "bg-violet-500/20 text-violet-300" : "bg-violet-100 text-violet-700"}`}>{w.weight}%</span>
                                          {w.focus && <span className="text-[11px] opacity-80 flex-1 truncate">{w.focus}</span>}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {msg.expert_insights.document_checklist && msg.expert_insights.document_checklist.length > 0 && (
                                  <div>
                                    <div className={`font-bold mb-1 ${dark ? "text-amber-400" : "text-amber-600"}`}>📋 필수 서류</div>
                                    <div className="flex flex-wrap gap-1">
                                      {msg.expert_insights.document_checklist.map((d, di) => (
                                        <span key={di} className={`px-2 py-0.5 rounded-full text-[11px] ${dark ? "bg-amber-500/10 text-amber-300 border border-amber-500/30" : "bg-amber-50 text-amber-700 border border-amber-200"}`}>{d}</span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {msg.expert_insights.similar_programs && msg.expert_insights.similar_programs.length > 0 && (
                                  <div>
                                    <div className={`font-bold mb-1 ${dark ? "text-sky-400" : "text-sky-600"}`}>🔗 유사 프로그램</div>
                                    <ul className={`space-y-1 ${dark ? "text-slate-300" : "text-slate-700"}`}>
                                      {msg.expert_insights.similar_programs.map((s, si) => (
                                        <li key={si} className="text-[11px]"><strong>{s.title}</strong> — {s.reason}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                          {/* 선택지 */}
                          {msg.role === "assistant" && msg.choices && msg.choices.length > 0 && i === messages.length - 1 && !loading && (
                            <div className="flex flex-wrap gap-2 mt-2">
                              {msg.choices.map((choice, ci) => (
                                <button key={ci} onClick={() => {
                                  // [재설계 04] "조건 수정 후 재매칭" 클릭 → 폼으로 복귀
                                  if (choice.includes("조건 수정") || choice.includes("조건 변경")) {
                                    setShowProfileForm(true);
                                    setFlowState("info_collect");
                                    return;
                                  }
                                  handleSend(choice);
                                }}
                                  className={`px-3 py-1.5 rounded-full text-[13px] md:text-[12px] font-semibold transition-all active:scale-95 border ${
                                    dark
                                      ? "bg-violet-500/10 border-violet-500/30 text-violet-400 hover:bg-violet-500/20"
                                      : "bg-white border-violet-200 text-violet-700 hover:bg-violet-50 hover:border-violet-400"
                                  }`}>
                                  {choice}
                                </button>
                              ))}
                            </div>
                          )}
                          {/* 매칭 결과 카드 + 보고서 생성 버튼 — 버킷 배지로 그룹 시각화 */}
                          {msg.role === "assistant" && msg.matched && msg.matched.length > 0 && (
                            <div className="mt-3 space-y-2">
                              {msg.matched.slice(0, 20).map((m: any, mi: number) => {
                                const bucket = m.bucket || "";
                                const bucketBadge = (() => {
                                  if (bucket === "interest_match") return { icon: "🎯", label: "관심 일치", color: "bg-violet-500/10 text-violet-600 border-violet-400/30" };
                                  if (bucket === "deadline_urgent") return { icon: "⏰", label: "마감 임박", color: "bg-red-500/10 text-red-600 border-red-400/30" };
                                  if (bucket === "qualified_other") return { icon: "✅", label: "참고", color: "bg-slate-500/10 text-slate-500 border-slate-400/30" };
                                  return null;
                                })();
                                const interestTags = (m.matched_interests || []).slice(0, 2);
                                return (
                                <button key={mi}
                                  onClick={() => {
                                    const aid = m.announcement_id || m.id;
                                    if (!aid) return;
                                    // [재설계 04] 카드 클릭 → 즉시 action=consult (React state 비동기 우회)
                                    setActiveAnnouncementId(aid);
                                    const consultMsg = `『${m.title || m.program_title || "공고"}』 상세 상담을 시작합니다. 이 공고에 대해 신청 가능 여부, 평가 포인트, 흔한 실수, 필수 서류, 유사 프로그램을 분석해주세요.`;
                                    const newHistory = [...messages, { role: "user" as const, text: consultMsg }];
                                    setMessages(newHistory);
                                    sendToAI(newHistory, { action: "consult", announcement_id: aid });
                                  }}
                                  className={`w-full text-left p-3 rounded-xl border transition-all hover:shadow-md cursor-pointer ${dark ? "bg-white/[0.03] border-white/[0.08] hover:border-violet-500/30" : "bg-white border-slate-200 hover:border-violet-400"}`}>
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="flex-1 min-w-0">
                                      {/* 상단: 버킷 배지 + 관심 태그 */}
                                      <div className="flex flex-wrap items-center gap-1.5 mb-1">
                                        {bucketBadge && (
                                          <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded border text-[10px] font-bold ${bucketBadge.color}`}>
                                            <span>{bucketBadge.icon}</span><span>{bucketBadge.label}</span>
                                          </span>
                                        )}
                                        {interestTags.map((tag: string, ti: number) => (
                                          <span key={ti} className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-semibold ${dark ? "bg-emerald-500/10 text-emerald-400 border-emerald-400/20" : "bg-emerald-50 text-emerald-700 border-emerald-200"}`}>
                                            #{tag}
                                          </span>
                                        ))}
                                      </div>
                                      <p className={`text-[13px] font-bold ${dark ? "text-slate-100" : "text-slate-800"} truncate`}>
                                        {m.title || m.program_title || "공고"}
                                      </p>
                                      <div className="flex flex-wrap gap-2 mt-1 text-[11px]">
                                        {m.support_amount && <span className="text-emerald-500 font-semibold">💰 {m.support_amount}</span>}
                                        {m.deadline_date && m.deadline_date !== "None" && <span className={t.muted}>📅 {String(m.deadline_date).slice(0,10)}</span>}
                                        {m.eligibility_status === "ineligible" ? (
                                          <span className="text-slate-400 font-semibold">⊘ 대상 아님</span>
                                        ) : (
                                          <span className="text-violet-500 font-semibold">✓ 신청 가능</span>
                                        )}
                                      </div>
                                    </div>
                                    <span className={`text-[10px] flex-shrink-0 ${dark ? "text-violet-400" : "text-violet-600"}`}>상담 →</span>
                                  </div>
                                </button>
                              );
                              })}
                              {msg.showReportButton && (
                                <button
                                  onClick={async () => {
                                    if (loading || typing) return;
                                    setLoading(true);
                                    try {
                                      // 임시 client_profile 생성 후 reports/generate 호출
                                      const isIndiv = clientCategory === "individual";
                                      const tempName = `상담${new Date().toLocaleString("ko-KR", {month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"})}`;
                                      const cf = await fetch(`${API}/api/pro/clients`, {
                                        method: "POST",
                                        headers: headers(),
                                        body: JSON.stringify({
                                          client_name: profileForm.company_name || tempName,
                                          client_type: isIndiv ? "individual" : "business",
                                          establishment_date: profileForm.establishment_date || (profileForm.establishment_year ? `${profileForm.establishment_year}-01-01` : null),
                                          address_city: profileForm.address_city || collectedProfile.address_city || "",
                                          industry_code: profileForm.industry_code || collectedProfile.industry_code || "",
                                          revenue_bracket: profileForm.revenue_bracket || (isIndiv ? "1억 미만" : ""),
                                          employee_count_bracket: profileForm.employee_bracket || (isIndiv ? "5인 미만" : ""),
                                          interests: (profileForm.interests && profileForm.interests.length > 0)
                                            ? profileForm.interests.join(",")
                                            : (collectedProfile.interests || ""),
                                          memo: "ProSecretary 매칭에서 자동 생성",
                                        }),
                                      });
                                      if (!cf.ok) throw new Error("client_profile 생성 실패");
                                      const cfData = await cf.json();
                                      const cid = cfData.id;
                                      // 보고서 생성
                                      const rg = await fetch(`${API}/api/pro/reports/generate`, {
                                        method: "POST",
                                        headers: headers(),
                                        body: JSON.stringify({ client_profile_id: cid }),
                                      });
                                      if (!rg.ok) throw new Error("보고서 생성 실패");
                                      const rgData = await rg.json();
                                      toast(`📄 보고서 생성 완료 (${rgData.total}건 매칭, ${rgData.eligible}건 적합)`, "success");
                                      // 보고서 탭으로 이동
                                      setActiveView("reports");
                                    } catch (e: any) {
                                      toast(e?.message || "보고서 생성 실패", "error");
                                    } finally {
                                      setLoading(false);
                                    }
                                  }}
                                  className="w-full mt-2 py-2.5 bg-gradient-to-r from-violet-600 to-purple-600 text-white text-[13px] font-bold rounded-xl hover:from-violet-700 hover:to-purple-700 transition-all active:scale-[0.98] flex items-center justify-center gap-2"
                                >
                                  📄 이 매칭 결과로 보고서 생성
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                      );
                    })}
                    {loading && (
                      <div className="flex justify-start">
                        <div className={`px-4 py-3 rounded-2xl rounded-bl-md ${t.bubble}`}>
                          <div className="flex items-center gap-2.5">
                            <svg className="w-4 h-4 text-violet-500 animate-spin" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                            </svg>
                            <span className={`text-[13px] ${dark ? "text-violet-400" : "text-violet-600"}`}>AI가 분석하고 있습니다...</span>
                          </div>
                        </div>
                      </div>
                    )}
                    {/* 인라인 입력 위젯 — AI가 질문할 때만 표시 */}
                    {!loading && !typing && messages.length > 0 && messages[messages.length - 1].role === "assistant" && (() => {
                      const lastText = messages[messages.length - 1].text.toLowerCase();

                      // 확인/요약/완료 메시지는 위젯 표시 안 함
                      const summaryWords = ["진행할까요", "정리한", "프로파일", "확인해", "매칭을 진행", "조건으로 매칭", "이군요", "이시군요", "군요", "입력하셨", "확인했", "접수", "감사합니다", "찾아보", "분석 중", "매칭 중", "결과를", "선정", "등록되었", "등록되", "정보가 등록", "어떤 작업을 진행"];
                      if (summaryWords.some(w => lastText.includes(w))) return null;

                      // [기업 정보] 같은 구조화된 양식 요청은 위젯 표시
                      const hasFormBlock = /\[기업.?정보\]|\[개인.?정보\]|\[고객.?정보\]/.test(lastText);

                      // 질문 패턴이 있어야 위젯 표시
                      const askWords = ["알려주세요", "입력해주세요", "선택해주세요", "어떻게 되나요", "무엇인가요", "어디인가요", "정보를 알려", "정보 알려"];
                      const isAsking = hasFormBlock || lastText.includes("?") || askWords.some(w => lastText.includes(w));
                      if (!isAsking) return null;

                      // 각 필드를 "요청"하는 패턴만 감지 (확인 언급 제외)
                      const fields: { key: string; label: string; type: "text" | "select" | "date" | "multiselect"; options?: string[] }[] = [];
                      const asking = (keyword: string) => {
                        // "기업명을 알려주세요" → true / "기업명이 dd이군요" → false
                        const idx = lastText.indexOf(keyword);
                        if (idx === -1) return false;
                        const after = lastText.substring(idx + keyword.length, idx + keyword.length + 5);
                        // 확인 패턴: "이", "은 ", "는 " 뒤에 값이 오는 경우
                        if (/^(이|은\s|는\s)/.test(after)) return false;
                        return true;
                      };

                      // 구조화 블록(* 업종: 등)에서는 빈 항목만 위젯으로 표시
                      const hasField = (kw: string) => hasFormBlock ? lastText.includes(kw) : asking(kw);

                      if (hasField("설립일") || hasField("업력") || hasField("생년월일")) fields.push({ key: "date", label: "설립일/생년월일", type: "date" });
                      if (hasField("직원") || hasField("인원")) fields.push({ key: "emp", label: "직원수", type: "select", options: ["5인 미만", "5~10인", "10~30인", "30~50인", "50인 이상"] });
                      if (hasField("매출")) fields.push({ key: "rev", label: "매출 규모", type: "select", options: ["1억 미만", "1억~5억", "5억~10억", "10억~50억", "50억 이상"] });
                      if (hasField("업종") || hasField("분야") || hasField("관심")) fields.push({ key: "interest", label: lastText.includes("업종") ? "업종" : "관심분야", type: "text" });
                      if (hasField("지역") || hasField("소재지") || hasField("거주")) fields.push({ key: "city", label: "지역 (복수 선택)", type: "multiselect", options: ["서울", "경기", "부산", "인천", "대구", "대전", "광주", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"] });
                      if (hasField("기업명") || hasField("이름")) fields.push({ key: "name", label: lastText.includes("기업명") ? "기업명" : "이름", type: "text" });
                      if (hasField("인증") || hasField("자격")) fields.push({ key: "cert", label: "보유 인증/자격", type: "text" });

                      if (fields.length === 0) return null;
                      return (
                        <InlineInputWidget fields={fields} dark={dark} t={t} onSubmit={(values) => {
                          const text = Object.entries(values).filter(([, v]) => v).map(([, v]) => v).join(", ");
                          if (text) handleSend(text);
                        }} onSkip={() => {
                          handleSend("건너뛰기 — 다음 질문으로 넘어갈게요");
                        }} />
                      );
                    })()}
                  </div>

                  {/* 입력 영역 — AI Secretary 스타일 (자료 첨부 제거) */}
                  <div className={`flex-shrink-0 border-t px-4 lg:px-6 py-3 ${t.border} ${dark ? "bg-[#0d0e1a]" : "bg-white"}`}>
                    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border transition-colors ${
                      dark ? "bg-[#1a1c30] border-white/[0.08] focus-within:border-violet-500/40" : "bg-slate-50 border-slate-200 focus-within:border-violet-400"
                    }`}>{/* 파일 첨부 아이콘 제거됨 (사장님 요청) */}
                      <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) { e.preventDefault(); handleSend(input); } }}
                        placeholder="입력 후 전송 또는 매칭"
                        disabled={loading || typing}
                        className={`flex-1 min-w-0 py-2 text-[16px] md:text-[14px] outline-none bg-transparent transition-all disabled:opacity-50 ${dark ? "text-slate-200 placeholder-slate-500" : "text-slate-700 placeholder-slate-400"}`}
                      />
                      <button
                        onClick={() => handleSend(input)}
                        disabled={loading || typing || !input.trim()}
                        className="p-2 sm:px-4 sm:py-2 bg-violet-600 text-white rounded-xl text-[13px] font-bold hover:bg-violet-500 transition-all active:scale-95 disabled:opacity-30 flex-shrink-0 flex items-center gap-1.5"
                        title="메시지 전송"
                        aria-label="전송"
                      >
                        <span className="hidden sm:inline">전송</span>
                        {Icons.send}
                      </button>
                      {(() => {
                        const hasMatched = messages.some(m => m.role === "assistant" && m.matched && m.matched.length > 0);
                        return (
                          <button
                            onClick={() => {
                              setMatchProfile({ ...collectedProfile });
                              setShowMatchModal(true);
                            }}
                            disabled={loading || typing}
                            className="p-2 sm:px-3 sm:py-2 border border-violet-500 text-violet-600 rounded-xl text-[12px] font-bold hover:bg-violet-50 transition-all active:scale-95 disabled:opacity-30 flex-shrink-0"
                            title={hasMatched ? "조건 변경 후 재매칭" : "수집된 정보로 공고 매칭"}
                            aria-label={hasMatched ? "재매칭" : "매칭 실행"}
                          >
                            <span className="sm:hidden">{hasMatched ? "🔄" : "📋"}</span>
                            <span className="hidden sm:inline">{hasMatched ? "🔄 재매칭" : "📋 매칭"}</span>
                          </button>
                        );
                      })()}
                    </div>
                  </div>
                </>
              )}
            </>
          ) : (
            /* 고객관리 / 상담이력 / 보고서 / 특정 공고 상담 */
            <div className={`flex-1 overflow-y-auto p-4 ${dark ? "text-slate-200" : ""}`}>
              {activeView === "clients" && <ClientsTabWrapper headers={headers} toast={toast} dark={dark} t={t}
                onResumeConsult={(client) => {
                  // 고객 정보를 ClientProfile 형태로 변환하여 startNewChat에 전달
                  const profile: ClientProfile = {
                    id: client.id,
                    client_name: client.client_name,
                    client_type: client.client_type || "business",
                    address_city: client.address_city || "",
                    industry_name: client.industry_name || "",
                    revenue_bracket: client.revenue_bracket || "",
                    contact_name: client.contact_name || "",
                    contact_email: client.contact_email || "",
                    status: client.status || "consulting",
                  };
                  const cat: ClientCategory = client.client_type === "individual" ? "individual" : "corporate";
                  startNewChat(cat, profile);
                }} />}
              {activeView === "history" && <HistoryTabWrapper headers={headers} toast={toast} />}
              {activeView === "reports" && <ReportsTabWrapper headers={headers} toast={toast} />}
              {activeView === "announce_search" && <AnnounceSearchPanel headers={headers} toast={toast} dark={dark} t={t} onStartConsult={(ann) => {
                // 공고 선택 → 상담 시작
                setActiveView("chat");
                setClientCategory("corporate");
                setFlowState("analysis");
                setActiveAnnouncementId(ann.id);
                setSystemContext(`[전문가 상담 모드] 특정 공고 상담\n공고명: ${ann.title}\n공고ID: ${ann.id}\n\n이 공고의 분석 데이터를 바탕으로 고객 자격요건을 검토합니다.`);
                setMessages([{
                  role: "assistant",
                  text: `**${ann.title}**\n\n${ann.summary || "공고 상세 정보를 불러왔습니다."}\n\n이 공고로 어떤 작업을 진행하시겠습니까?`,
                  choices: ["고객 자격요건 검토", "공고 상세 분석", "다른 고객에게 추천"],
                }]);
              }} />}
            </div>
          )}
        </div>

        {/* ═══ 우측 컨텍스트 패널 ═══ */}
        <aside className={`${rightOpen ? "fixed right-0 top-0 h-full z-50 w-[280px] shadow-2xl" : "hidden lg:flex"} lg:flex flex-col overflow-y-auto ${t.right}`}>
          {rightOpen && (
            <button onClick={() => setRightOpen(false)} className="lg:hidden self-end p-2 m-2 text-slate-400 hover:text-slate-200">
              {Icons.close}
            </button>
          )}

          {/* 워크플로우 — AI Secretary 스타일 타임라인 */}
          <div className={`p-4 border-b ${t.border}`}>
            <p className={`text-[10px] font-bold uppercase tracking-wider mb-3 ${t.sectionTitle}`}>워크플로우</p>
            <div className="relative">
              {/* 세로 연결선 */}
              <div className={`absolute left-[11px] top-3 bottom-3 w-[2px] ${dark ? "bg-white/[0.06]" : "bg-slate-200"}`} />
              <div className="space-y-0.5 relative">
                {flowSteps.map((step, i) => {
                  const currentIdx = flowSteps.findIndex(s => s.key === flowState);
                  const isDone = currentIdx > i;
                  const isActive = flowState === step.key;
                  return (
                    <div key={step.key} className={`flex items-center gap-3 py-2 px-2 rounded-lg text-[12px] transition-all ${
                      isActive ? t.flowActive : ""
                    }`}>
                      <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 border-2 transition-all ${
                        isActive ? "border-violet-500 bg-violet-500 text-white shadow-lg shadow-violet-500/30"
                        : isDone ? "border-emerald-500 bg-emerald-500 text-white"
                        : dark ? "border-white/10 bg-transparent" : "border-slate-200 bg-white"
                      }`}>
                        {isDone ? Icons.check : isActive ? <span className="w-2 h-2 bg-white rounded-full" /> : null}
                      </div>
                      <span className={`font-medium ${isActive ? (dark ? "text-violet-400" : "text-violet-700") : isDone ? t.flowDone : t.flowPending}`}>
                        {step.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* 현재 고객 정보 */}
          {selectedClient && (
            <div className={`p-4 border-b ${t.border}`}>
              <p className={`text-[10px] font-bold uppercase tracking-wider mb-2 ${t.sectionTitle}`}>현재 고객</p>
              <div className={`space-y-1.5 text-[12px]`}>
                <p className={`font-bold ${dark ? "text-slate-200" : "text-slate-700"}`}>{selectedClient.client_name}</p>
                <p className={t.muted}>{selectedClient.address_city || ""} · {selectedClient.industry_name || ""}</p>
                {selectedClient.contact_name && <p className={t.muted}>{selectedClient.contact_name} · {selectedClient.contact_email || ""}</p>}
              </div>
            </div>
          )}

          {/* 수집된 정보 — 실시간 */}
          {Object.keys(collectedProfile).filter(k => collectedProfile[k]).length > 0 && (
            <div className={`p-4 border-b ${t.border}`}>
              <p className={`text-[10px] font-bold uppercase tracking-wider mb-2 ${t.sectionTitle}`}>수집된 정보</p>
              <div className={`space-y-1 text-[11px]`}>
                {Object.entries({
                  company_name: "고객명",
                  industry_code: "업종",
                  address_city: "지역",
                  revenue_bracket: "매출",
                  employee_count_bracket: "직원",
                  age_range: "연령",
                  income_level: "소득",
                  family_type: "가구",
                  employment_status: "고용",
                  housing_status: "주거",
                  interests: "관심",
                  special_conditions: "특수자격",
                }).map(([k, label]) => {
                  const v = collectedProfile[k];
                  if (!v) return null;
                  return (
                    <div key={k} className="flex gap-1.5">
                      <span className={`flex-shrink-0 ${t.muted}`}>{label}</span>
                      <span className={`truncate ${dark ? "text-slate-300" : "text-slate-700"}`}>{String(v)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 답변 근거 사이드바 섹션 제거 (RAG 관련도 낮아 UX 혼선 유발) */}

          {/* 빠른 액션 — 상담 진행 중일 때 */}
          {messages.length > 1 && (
            <div className={`p-4 border-b ${t.border}`}>
              <p className={`text-[10px] font-bold uppercase tracking-wider mb-2 ${t.sectionTitle}`}>빠른 액션</p>
              <div className="grid grid-cols-3 gap-1.5">
                {(() => {
                  // 매칭 완료 여부 = 최근 assistant 메시지에 matched 배열이 있음
                  const hasMatched = messages.some(m => m.role === "assistant" && m.matched && m.matched.length > 0);
                  const disabledCls = "opacity-40 cursor-not-allowed";
                  const enabledCls = (color: string) => dark
                    ? `bg-${color}-500/10 border border-${color}-500/30 text-${color}-300 hover:bg-${color}-500/20`
                    : `bg-${color}-50 border border-${color}-200 text-${color}-700 hover:bg-${color}-100`;
                  return (
                    <>
                      <button
                        onClick={() => hasMatched && handleSend("[상담 진행 경과 요약 요청] 지금까지 파악한 고객사 프로필, 관심분야, 매칭 결과(건수만), 남은 상담 포인트를 간단히 정리해줘. 공고 제목 나열 금지. 상위 카드는 이미 화면에 있음.")}
                        disabled={!hasMatched}
                        title={hasMatched ? "상담 진행 경과 정리" : "매칭 완료 후 활성화"}
                        className={`text-[11px] py-2 px-2 rounded-lg font-semibold transition-all active:scale-95 ${hasMatched ? (dark ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/20" : "bg-emerald-50 border border-emerald-200 text-emerald-700 hover:bg-emerald-100") : disabledCls + " bg-slate-100 border border-slate-200 text-slate-400"}`}
                      >
                        📋 정리
                      </button>
                      <button
                        onClick={() => hasMatched && handleSend("위 매칭된 공고들의 자격요건을 자세히 설명해주세요")}
                        disabled={!hasMatched}
                        title={hasMatched ? "자격요건 상세" : "매칭 완료 후 활성화"}
                        className={`text-[11px] py-2 px-2 rounded-lg font-semibold transition-all active:scale-95 ${hasMatched ? (dark ? "bg-blue-500/10 border border-blue-500/30 text-blue-300 hover:bg-blue-500/20" : "bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100") : disabledCls + " bg-slate-100 border border-slate-200 text-slate-400"}`}
                      >
                        ✅ 자격
                      </button>
                      <button
                        onClick={() => hasMatched && handleSend("위 매칭된 공고들의 필요 서류를 알려주세요")}
                        disabled={!hasMatched}
                        title={hasMatched ? "서류 안내" : "매칭 완료 후 활성화"}
                        className={`text-[11px] py-2 px-2 rounded-lg font-semibold transition-all active:scale-95 ${hasMatched ? (dark ? "bg-amber-500/10 border border-amber-500/30 text-amber-300 hover:bg-amber-500/20" : "bg-amber-50 border border-amber-200 text-amber-700 hover:bg-amber-100") : disabledCls + " bg-slate-100 border border-slate-200 text-slate-400"}`}
                      >
                        📄 서류
                      </button>
                    </>
                  );
                })()}
              </div>
            </div>
          )}

          {/* 자료 첨부 섹션 제거 (사장님 요청 — AI 파일 파싱 품질 이슈) */}

          {/* 연동 서비스 — 향후 제공 */}
        </aside>
      </div>

      {/* 매칭 확인 모달 */}
      {showMatchModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" onClick={() => setShowMatchModal(false)}>
          <div className={`relative w-full max-w-md rounded-2xl p-6 shadow-2xl ${dark ? "bg-[#0d0e1f] border border-white/10" : "bg-white"}`} onClick={(e) => e.stopPropagation()}>
            <h3 className={`text-lg font-bold mb-2 ${dark ? "text-slate-100" : "text-slate-800"}`}>📋 매칭 정보 확인</h3>
            <p className={`text-[12px] mb-4 ${t.muted}`}>아래 정보로 공고 매칭을 진행합니다. 수정 가능합니다.</p>

            <div className="space-y-3 max-h-[60vh] overflow-y-auto">
              {[
                { key: "company_name", label: "기업명", placeholder: "(미입력)" },
                { key: "industry_code", label: "업종코드", placeholder: "(미입력 — 전체 검색)" },
                { key: "revenue_bracket", label: "매출 규모", placeholder: "(미입력)" },
                { key: "employee_count_bracket", label: "직원수", placeholder: "(미입력)" },
                { key: "address_city", label: "소재지", placeholder: "(미입력 — 전국)" },
                { key: "interests", label: "관심분야", placeholder: "(미입력)" },
              ].map(field => (
                <div key={field.key}>
                  <label className={`block text-[11px] font-bold mb-1 ${dark ? "text-violet-400" : "text-violet-600"}`}>{field.label}</label>
                  <input
                    type="text"
                    value={matchProfile[field.key] || ""}
                    onChange={(e) => setMatchProfile((prev: any) => ({ ...prev, [field.key]: e.target.value }))}
                    placeholder={field.placeholder}
                    className={`w-full px-3 py-2 rounded-lg text-[13px] outline-none border transition-all focus:ring-2 focus:ring-violet-500/20 ${
                      dark ? "bg-[#1a1c30] border-white/[0.08] text-slate-200 focus:border-violet-500/40" : "bg-white border-slate-200 text-slate-700 focus:border-violet-400"
                    }`}
                  />
                </div>
              ))}
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setShowMatchModal(false)}
                className={`flex-1 py-2.5 rounded-lg text-[13px] font-bold transition-all ${dark ? "text-slate-400 hover:bg-white/[0.05]" : "text-slate-500 hover:bg-slate-100"}`}
              >
                취소
              </button>
              <button
                onClick={() => {
                  // [재설계 04] action=match로 매칭 실행
                  setShowMatchModal(false);
                  const newHistory = [...messages, { role: "user" as const, text: "📋 수집된 정보로 공고 매칭 실행" }];
                  setMessages(newHistory);
                  sendToAI(newHistory, { action: "match", profile_override: matchProfile });
                }}
                className="flex-[2] py-2.5 bg-violet-600 text-white rounded-lg text-[13px] font-bold hover:bg-violet-500 transition-all active:scale-95"
              >
                ✅ 이대로 매칭 실행
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── ProDashboard 서브컴포넌트 래퍼 ───
function ClientsTabWrapper({ headers, toast, dark, t, onResumeConsult }: {
  headers: () => any; toast: any; dark: boolean; t: any;
  onResumeConsult?: (client: any) => void;
}) {
  const [clients, setClients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [showEmail, setShowEmail] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const fetchClients = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/pro/clients/with-history`, { headers: headers() });
      if (res.ok) {
        const data = await res.json();
        setClients(data.clients || []);
      }
    } catch (e) { console.error("[PRO]", e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchClients(); }, [fetchClients]);

  const toggleSelect = (id: number) => setSelectedIds(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const selectAll = () => setSelectedIds(selectedIds.size === clients.length ? new Set() : new Set(clients.map(c => c.id)));

  const handleExport = () => {
    const token = localStorage.getItem("auth_token") || "";
    window.open(`${API}/api/pro/clients/export?authorization=Bearer ${token}`, "_blank");
  };

  const handleDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!window.confirm(`선택한 ${selectedIds.size}개 고객사를 삭제하시겠습니까?\n(상담 이력은 유지됩니다)`)) return;
    setDeleting(true);
    let success = 0, failed = 0;
    for (const id of Array.from(selectedIds)) {
      try {
        const r = await fetch(`${API}/api/pro/clients/${id}`, { method: "DELETE", headers: headers() });
        if (r.ok) success++;
        else failed++;
      } catch { failed++; }
    }
    setDeleting(false);
    setSelectedIds(new Set());
    if (success > 0) toast(`${success}개 고객사 삭제됨${failed > 0 ? ` (${failed}개 실패)` : ""}`, "success");
    else toast("삭제 실패", "error");
    fetchClients();
  };

  const handleResume = (client: any) => {
    if (onResumeConsult) onResumeConsult(client);
  };

  const statusLabel: Record<string, string> = { new: "신규", consulting: "상담중", matched: "매칭", applied: "신청", selected: "선정" };
  const statusColor: Record<string, string> = {
    new: dark ? "bg-slate-700/50 text-slate-300" : "bg-slate-100 text-slate-600",
    consulting: dark ? "bg-blue-900/30 text-blue-400" : "bg-blue-100 text-blue-700",
    matched: dark ? "bg-indigo-900/30 text-indigo-400" : "bg-indigo-100 text-indigo-700",
    applied: dark ? "bg-amber-900/30 text-amber-400" : "bg-amber-100 text-amber-700",
    selected: dark ? "bg-emerald-900/30 text-emerald-400" : "bg-emerald-100 text-emerald-700",
  };

  if (loading) return <div className={`text-center py-10 ${dark ? "text-slate-500" : "text-slate-400"}`}>로딩 중...</div>;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className={`text-sm font-bold ${dark ? "text-slate-200" : "text-slate-700"}`}>{clients.length}개 고객사</p>
        <div className="flex gap-2">
          {selectedIds.size > 0 && (
            <>
              <button onClick={() => setShowEmail(true)} className="px-3 py-1.5 bg-violet-600 text-white text-xs font-bold rounded-lg hover:bg-violet-500">
                {selectedIds.size}명 이메일
              </button>
              <button onClick={handleDelete} disabled={deleting}
                className="px-3 py-1.5 bg-red-500/15 text-red-400 border border-red-500/30 text-xs font-bold rounded-lg hover:bg-red-500/25 disabled:opacity-50">
                {deleting ? "삭제 중..." : `${selectedIds.size}개 삭제`}
              </button>
            </>
          )}
          <button onClick={handleExport} className={`px-3 py-1.5 text-xs font-bold rounded-lg ${dark ? "bg-white/[0.05] text-slate-300 hover:bg-white/[0.08]" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
            CSV 다운로드
          </button>
        </div>
      </div>

      <div className={`overflow-x-auto rounded-xl border ${dark ? "border-white/[0.06]" : "border-slate-200"}`}>
        <table className="w-full text-[12px]">
          <thead>
            <tr className={dark ? "bg-white/[0.03] border-b border-white/[0.06]" : "bg-slate-50 border-b border-slate-200"}>
              <th className="py-2.5 px-2 text-left w-8">
                <input type="checkbox" checked={selectedIds.size === clients.length && clients.length > 0} onChange={selectAll}
                  className="w-3.5 h-3.5 rounded border-slate-300 text-violet-600" />
              </th>
              {["기업명", "업종", "지역", "매출", "전화", "최근상담", "상담수", "상태", "액션"].map((h, i) => (
                <th key={h} className={`py-2.5 px-2 text-left font-bold ${dark ? "text-slate-500" : "text-slate-400"} ${i >= 1 && i <= 4 ? "hidden md:table-cell" : ""}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {clients.map(c => (
              <React.Fragment key={c.id}>
                <tr className={`border-b ${dark ? "border-white/[0.04] hover:bg-white/[0.03]" : "border-slate-100 hover:bg-violet-50/30"} cursor-pointer transition-all ${expanded === c.id ? (dark ? "bg-white/[0.03]" : "bg-violet-50/50") : ""}`}
                  onClick={() => setExpanded(expanded === c.id ? null : c.id)}>
                  <td className="py-2.5 px-2" onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={selectedIds.has(c.id)} onChange={() => toggleSelect(c.id)}
                      className="w-3.5 h-3.5 rounded border-slate-300 text-violet-600" />
                  </td>
                  <td className={`py-2.5 px-2 font-bold ${dark ? "text-slate-200" : "text-slate-800"}`}>{c.client_name}</td>
                  <td className={`py-2.5 px-2 hidden md:table-cell ${dark ? "text-slate-400" : "text-slate-500"}`}>{c.industry_name || "-"}</td>
                  <td className={`py-2.5 px-2 hidden md:table-cell ${dark ? "text-slate-400" : "text-slate-500"}`}>{c.address_city || "-"}</td>
                  <td className={`py-2.5 px-2 hidden md:table-cell ${dark ? "text-slate-400" : "text-slate-500"}`}>{c.revenue_bracket || "-"}</td>
                  <td className={`py-2.5 px-2 hidden md:table-cell ${dark ? "text-slate-400" : "text-slate-500"}`}>{c.contact_phone || "-"}</td>
                  <td className={`py-2.5 px-2 ${dark ? "text-slate-400" : "text-slate-500"}`}>{c.last_consult_date ? String(c.last_consult_date).slice(5, 10) : "-"}</td>
                  <td className={`py-2.5 px-2 ${dark ? "text-slate-400" : "text-slate-500"}`}>{c.consult_count || 0}회</td>
                  <td className="py-2.5 px-2">
                    <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded ${statusColor[c.status] || (dark ? "bg-slate-700/50 text-slate-400" : "bg-slate-100 text-slate-500")}`}>
                      {statusLabel[c.status] || c.status || "신규"}
                    </span>
                  </td>
                  <td className="py-2.5 px-2" onClick={(e) => e.stopPropagation()}>
                    <button onClick={() => handleResume(c)}
                      className="px-2 py-1 bg-violet-600 hover:bg-violet-500 text-white text-[10px] font-bold rounded-md transition-colors flex items-center gap-1"
                      title={c.status === "consulting" ? "상담 재개" : "상담 시작"}>
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                      </svg>
                      {c.status === "consulting" ? "재개" : "상담"}
                    </button>
                  </td>
                </tr>
                {expanded === c.id && (
                  <tr>
                    <td colSpan={10} className={`px-4 py-3 border-b ${dark ? "bg-white/[0.02] border-white/[0.04]" : "bg-slate-50 border-slate-200"}`}>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[11px]">
                        <div className="space-y-1.5">
                          <p className={`text-[10px] font-bold uppercase ${dark ? "text-slate-500" : "text-slate-400"}`}>기본 정보</p>
                          {[
                            ["담당자", c.contact_name],
                            ["이메일", c.contact_email],
                            ["전화", c.contact_phone],
                            ["설립일", c.establishment_date ? String(c.establishment_date).slice(0, 10) : null],
                            ["직원수", c.employee_count_bracket],
                          ].map(([label, val]) => (
                            <p key={label as string}><span className={dark ? "text-slate-500" : "text-slate-400"}>{label}:</span> <span className="font-semibold">{val || "-"}</span></p>
                          ))}
                          {c.tags && <p><span className={dark ? "text-slate-500" : "text-slate-400"}>태그:</span> {c.tags.split(",").map((tag: string, i: number) => <span key={i} className={`ml-1 px-1.5 py-0.5 text-[9px] font-bold rounded ${dark ? "bg-violet-500/20 text-violet-400" : "bg-violet-100 text-violet-600"}`}>{tag.trim()}</span>)}</p>}
                          {c.memo && <p><span className={dark ? "text-slate-500" : "text-slate-400"}>메모:</span> <span className={dark ? "text-slate-300" : "text-slate-600"}>{c.memo}</span></p>}
                        </div>
                        <div className="space-y-1.5">
                          <p className={`text-[10px] font-bold uppercase ${dark ? "text-slate-500" : "text-slate-400"}`}>최근 상담</p>
                          {c.last_consult_summary ? (
                            <p className={`leading-relaxed ${dark ? "text-slate-300" : "text-slate-600"}`}>{c.last_consult_summary}</p>
                          ) : (
                            <p className={dark ? "text-slate-600" : "text-slate-400"}>상담 이력이 없습니다</p>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {showEmail && (() => {
        const { EmailModal } = require("@/components/ProDashboard");
        return <EmailModal clientIds={Array.from(selectedIds)} clientCount={selectedIds.size} headers={headers} toast={toast}
          onClose={() => setShowEmail(false)} onDone={() => { setShowEmail(false); setSelectedIds(new Set()); }} />;
      })()}
    </div>
  );
}

function HistoryTabWrapper({ headers, toast }: { headers: () => any; toast: any }) {
  const { HistoryTab } = require("@/components/ProDashboard");
  return <HistoryTab headers={headers} toast={toast} />;
}

function ReportsTabWrapper({ headers, toast }: { headers: () => any; toast: any }) {
  const { ReportsTab } = require("@/components/ProDashboard");
  return <ReportsTab headers={headers} toast={toast} clientType="business" />;
}


// ─── 인라인 입력 위젯 (건너뛰기 추가) ───
// (구 IndustryAutocomplete → @/components/shared/IndustryPicker 로 교체됨)

function InlineInputWidget({ fields, dark, t, onSubmit, onSkip }: {
  fields: { key: string; label: string; type: "text" | "select" | "date" | "multiselect"; options?: string[] }[];
  dark: boolean;
  t: any;
  onSubmit: (values: Record<string, string>) => void;
  onSkip: () => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const update = (key: string, val: string) => setValues(prev => ({ ...prev, [key]: val }));
  const toggleMulti = (key: string, opt: string) => {
    setValues(prev => {
      const current = (prev[key] || "").split(",").filter(Boolean);
      const next = current.includes(opt) ? current.filter((c: string) => c !== opt) : [...current, opt];
      return { ...prev, [key]: next.join(",") };
    });
  };

  const inputCls = `px-3 py-2 rounded-lg text-[13px] outline-none border transition-all focus:ring-2 focus:ring-violet-500/20 ${
    dark ? "bg-[#1a1c30] border-white/[0.08] text-slate-200 focus:border-violet-500/40" : "bg-white border-slate-200 text-slate-700 focus:border-violet-400"
  }`;
  const chipCls = (selected: boolean) => `px-2 py-1 rounded text-[11px] font-semibold transition-all cursor-pointer ${
    selected
      ? (dark ? "bg-violet-600 text-white" : "bg-violet-600 text-white")
      : (dark ? "bg-white/[0.05] text-slate-400 hover:bg-white/10" : "bg-slate-100 text-slate-500 hover:bg-slate-200")
  }`;

  return (
    <div className={`mx-4 mb-3 p-3 rounded-xl border ${dark ? "bg-[#1a1c30] border-violet-500/20" : "bg-violet-50/50 border-violet-200"}`}>
      <div className="flex flex-wrap gap-2 items-end">
        {fields.map(f => (
          <div key={f.key} className={f.type === "multiselect" ? "w-full" : "flex-1 min-w-[120px]"}>
            <label className={`block text-[10px] font-bold mb-1 ${dark ? "text-violet-400" : "text-violet-600"}`}>{f.label}</label>
            {f.type === "multiselect" && f.options ? (
              <div className="flex flex-wrap gap-1">
                {f.options.map(opt => (
                  <button key={opt} type="button" onClick={() => toggleMulti(f.key, opt)}
                    className={chipCls((values[f.key] || "").split(",").includes(opt))}>{opt}</button>
                ))}
              </div>
            ) : f.type === "select" && f.options ? (
              <select value={values[f.key] || ""} onChange={(e) => update(f.key, e.target.value)} className={`w-full ${inputCls}`}>
                <option value="">선택</option>
                {f.options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
              </select>
            ) : f.type === "date" ? (
              <input type="date" value={values[f.key] || ""} onChange={(e) => update(f.key, e.target.value)} className={`w-full ${inputCls}`} />
            ) : (
              <input type="text" value={values[f.key] || ""} onChange={(e) => update(f.key, e.target.value)}
                placeholder={f.label} className={`w-full ${inputCls}`} />
            )}
          </div>
        ))}
        <div className="flex gap-1.5 self-end">
          <button
            onClick={onSkip}
            className={`px-3 py-2 rounded-lg text-[12px] font-semibold transition-all active:scale-95 ${
              dark ? "text-slate-400 hover:text-slate-200 hover:bg-white/[0.05]" : "text-slate-500 hover:text-slate-700 hover:bg-slate-100"
            }`}
          >
            건너뛰기
          </button>
          <button
            onClick={() => onSubmit(values)}
            disabled={Object.values(values).every(v => !v)}
            className="px-4 py-2 bg-violet-600 text-white rounded-lg text-[12px] font-bold hover:bg-violet-500 transition-all active:scale-95 disabled:opacity-30"
          >
            전송
          </button>
        </div>
      </div>
    </div>
  );
}


// ─── 고객 정보 입력 폼 (버튼식) ───
function ProfileInputForm({ dark, t, clientCategory, profileForm, setProfileForm, onSubmit, onBack }: {
  dark: boolean; t: any; clientCategory: string;
  profileForm: any; setProfileForm: (f: any) => void;
  onSubmit: () => void; onBack: () => void;
}) {
  const isIndiv = clientCategory === "individual";
  const catLabel = clientCategory === "individual_biz" ? "개인사업자" : clientCategory === "corporate" ? "법인사업자" : isIndiv ? "개인" : "고객";
  const update = (key: string, val: string) => setProfileForm((prev: any) => ({ ...prev, [key]: val }));
  const toggleInterest = (v: string) => setProfileForm((prev: any) => ({
    ...prev,
    interests: prev.interests.includes(v) ? prev.interests.filter((i: string) => i !== v) : [...prev.interests, v],
  }));

  const btnCls = (selected: boolean) => `px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-all active:scale-95 border ${
    selected
      ? "bg-violet-600 text-white border-violet-600"
      : dark ? "bg-white/[0.03] border-white/[0.08] text-slate-400 hover:border-violet-500/40" : "bg-white border-slate-200 text-slate-600 hover:border-violet-400"
  }`;

  const inputCls = `w-full px-3 py-2.5 rounded-lg text-[13px] outline-none border transition-all focus:ring-2 focus:ring-violet-500/20 ${
    dark ? "bg-[#1a1c30] border-white/[0.08] text-slate-200 focus:border-violet-500/40" : "bg-white border-slate-200 text-slate-700 focus:border-violet-400"
  }`;

  const sectionTitle = `text-[11px] font-bold mb-2 ${dark ? "text-slate-200" : "text-slate-500"}`;

  const revenueOptions = ["1억 미만", "1억~5억", "5억~10억", "10억~50억", "50억 이상"];
  const employeeOptions = ["5인 미만", "5~10인", "10~30인", "30~50인", "50인 이상"];
  const cityOptions = ["서울", "경기", "부산", "인천", "대구", "대전", "광주", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"];
  const bizInterests = ["창업지원", "기술개발", "정책자금", "고용지원", "수출마케팅", "디지털전환", "판로개척", "시설개선", "교육훈련", "에너지환경", "소상공인", "R&D"];
  const indivInterests = ["취업", "주거", "교육", "청년", "출산/육아", "장학금", "의료", "장애", "저소득", "노인", "문화", "다자녀"];

  return (
    <div className="flex-1 overflow-y-auto px-4 lg:px-8 py-6">
      <div className="max-w-lg mx-auto space-y-5">
        {/* 헤더 */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className={`text-lg font-bold ${dark ? "text-slate-100" : "text-slate-800"}`}>{catLabel} 고객 정보</h3>
            <p className={`text-[12px] mt-0.5 ${t.muted}`}>모든 항목 선택입니다. 입력 없이 바로 시작하실 수 있어요.</p>
          </div>
          <button onClick={onBack} className={`text-[12px] px-3 py-1.5 rounded-lg ${dark ? "text-slate-400 hover:bg-white/5" : "text-slate-500 hover:bg-slate-100"}`}>
            뒤로
          </button>
        </div>

        {/* 빠른 시작 — 정보 입력 없이 바로 AI와 대화 */}
        <button
          onClick={onSubmit}
          className="w-full py-3 bg-gradient-to-r from-violet-500 to-purple-500 text-white text-[14px] font-bold rounded-xl hover:from-violet-600 hover:to-purple-600 transition-all active:scale-[0.98] shadow-md flex items-center justify-center gap-2"
        >
          🚀 정보 입력 건너뛰고 바로 상담하기
        </button>
        <p className={`text-[11px] text-center -mt-3 ${t.muted}`}>
          AI가 대화 중에 필요한 정보를 자연스럽게 물어봅니다
        </p>

        {/* 기업명/이름 (선택) */}
        <div>
          <p className={sectionTitle}>{isIndiv ? "고객 이름" : "기업명 (상호명)"} <span className={t.muted}>(선택)</span></p>
          <input type="text" value={profileForm.company_name} onChange={(e) => update("company_name", e.target.value)}
            placeholder={isIndiv ? "홍길동" : "주식회사 스마트팜코리아"} className={inputCls} />
        </div>

        {/* 설립일/생년월일 — 사업자 모드에서만 (개인은 AI가 대화 중 수집) */}
        {!isIndiv && (
          <EstablishmentDateInput
            value={profileForm.establishment_date || profileForm.establishment_year}
            onChange={(v) => {
              // YYYY만 입력 → establishment_year 세팅, YYYY-MM-DD → establishment_date 세팅
              if (/^\d{4}$/.test(v)) {
                update("establishment_year", v);
                update("establishment_date", `${v}-01-01`);
              } else if (/^\d{4}-\d{2}-\d{2}$/.test(v)) {
                update("establishment_date", v);
                update("establishment_year", v.slice(0, 4));
              } else {
                update("establishment_date", v);
                update("establishment_year", v.slice(0, 4));
              }
            }}
            dark={dark}
            label="설립연도"
          />
        )}

        {/* 업종 (사업자만) — KSIC 임베딩 기반 AI 추천 */}
        {!isIndiv && (
          <IndustryPicker
            value={profileForm.industry_name || profileForm.industry}
            selectedCode={profileForm.industry_code}
            onSelect={(code, name) => {
              setProfileForm((prev: any) => ({
                ...prev,
                industry_code: code,
                industry_name: name,
                industry: code ? `${name} (${code})` : "",
              }));
            }}
            dark={dark}
          />
        )}

        {/* 매출 규모 (사업자만) */}
        {!isIndiv && (
          <div>
            <p className={sectionTitle}>매출 규모 <span className={t.muted}>(선택)</span></p>
            <div className="flex flex-wrap gap-2">
              {revenueOptions.map(opt => (
                <button key={opt} onClick={() => update("revenue_bracket", profileForm.revenue_bracket === opt ? "" : opt)}
                  className={btnCls(profileForm.revenue_bracket === opt)}>{opt}</button>
              ))}
            </div>
          </div>
        )}

        {/* 직원수 (사업자만) */}
        {!isIndiv && (
          <div>
            <p className={sectionTitle}>직원수 <span className={t.muted}>(선택)</span></p>
            <div className="flex flex-wrap gap-2">
              {employeeOptions.map(opt => (
                <button key={opt} onClick={() => update("employee_bracket", profileForm.employee_bracket === opt ? "" : opt)}
                  className={btnCls(profileForm.employee_bracket === opt)}>{opt}</button>
              ))}
            </div>
          </div>
        )}

        {/* 지역 — 소재지 선택 (전국은 기본 포함, 소재지 공고 우선) */}
        <div>
          <p className={sectionTitle}>{isIndiv ? "거주 지역" : "소재지"} <span className={t.muted}>(선택 — 전국 공고는 항상 포함, 선택 지역 우선 표시)</span></p>
          <div className="flex flex-wrap gap-1.5">
            {cityOptions.map(opt => {
              const currentCities = (profileForm.address_city || "").split(",").map((s: string) => s.trim()).filter(Boolean);
              const isSelected = currentCities.includes(opt);
              return (
                <button key={opt} onClick={() => {
                  let next: string[];
                  if (isSelected) {
                    next = currentCities.filter((c: string) => c !== opt);
                  } else {
                    next = [...currentCities, opt];
                  }
                  // 항상 전국 포함
                  if (!next.includes("전국")) next = ["전국", ...next];
                  update("address_city", next.join(","));
                }}
                  className={btnCls(isSelected)}>{opt}</button>
              );
            })}
          </div>
          {(() => {
            const selected = (profileForm.address_city || "").split(",").map((s: string) => s.trim()).filter((s: string) => s && s !== "전국");
            return selected.length > 0 ? (
              <p className={`text-[10px] mt-1 ${dark ? "text-violet-300" : "text-violet-600"}`}>
                전국 공고 + <strong>{selected.join(", ")}</strong> 지역 공고 우선 표시
              </p>
            ) : (
              <p className={`text-[10px] mt-1 ${t.muted}`}>
                전국 공고 전체 표시 (소재지 선택 시 해당 지역 우선)
              </p>
            );
          })()}
        </div>

        {/* 관심분야 (복수 선택) */}
        <div>
          <p className={sectionTitle}>관심분야 <span className={t.muted}>(복수 선택)</span></p>
          <div className="flex flex-wrap gap-1.5">
            {(isIndiv ? indivInterests : bizInterests).map(opt => (
              <button key={opt} onClick={() => toggleInterest(opt)}
                className={btnCls(profileForm.interests.includes(opt))}>{opt}</button>
            ))}
          </div>
        </div>

        {/* 추가 조건 — 사업자 모드: 우대·제외 판정용 */}
        {!isIndiv && (
          <details className={`rounded-lg border ${dark ? "border-white/[0.06] bg-white/[0.02]" : "border-slate-200 bg-slate-50/50"} p-3`}>
            <summary className={`text-[12px] font-semibold cursor-pointer ${dark ? "text-slate-300" : "text-slate-600"}`}>
              추가 조건 (선택) — 정확한 매칭을 위한 보조 정보
            </summary>
            <div className="space-y-3 mt-3">
              {/* 대표 연령대 */}
              <div>
                <p className={sectionTitle}>대표 연령대</p>
                <div className="flex flex-wrap gap-1.5">
                  {["20대", "30대", "40대", "50대", "60대 이상"].map(opt => (
                    <button key={opt} onClick={() => update("representative_age", profileForm.representative_age === opt ? "" : opt)}
                      className={btnCls(profileForm.representative_age === opt)}>{opt}</button>
                  ))}
                </div>
              </div>

              {/* 특별 자격 */}
              <div>
                <p className={sectionTitle}>특별 자격 (우대 적용)</p>
                <div className="flex flex-wrap gap-1.5">
                  <button onClick={() => setProfileForm((p: any) => ({ ...p, is_women_enterprise: !p.is_women_enterprise }))}
                    className={btnCls(profileForm.is_women_enterprise)}>여성기업</button>
                  <button onClick={() => setProfileForm((p: any) => ({ ...p, is_youth_enterprise: !p.is_youth_enterprise }))}
                    className={btnCls(profileForm.is_youth_enterprise)}>청년기업(만39세↓)</button>
                  <button onClick={() => setProfileForm((p: any) => ({ ...p, is_restart: !p.is_restart }))}
                    className={btnCls(profileForm.is_restart)}>재창업</button>
                </div>
              </div>

              {/* 인증 */}
              <div>
                <p className={sectionTitle}>보유 인증 (복수 선택)</p>
                <div className="flex flex-wrap gap-1.5">
                  {["벤처", "이노비즈", "메인비즈", "사회적기업", "예비사회적기업", "장애인기업"].map(opt => {
                    const on = (profileForm.certifications || []).includes(opt);
                    return (
                      <button key={opt} onClick={() => setProfileForm((p: any) => ({
                        ...p,
                        certifications: on ? (p.certifications || []).filter((c: string) => c !== opt)
                                           : [...(p.certifications || []), opt],
                      }))}
                        className={btnCls(on)}>{opt}</button>
                    );
                  })}
                </div>
              </div>

              {/* 메모 */}
              <div>
                <p className={sectionTitle}>컨설턴트 메모</p>
                <textarea value={profileForm.memo || ""} onChange={(e) => update("memo", e.target.value)}
                  placeholder="특이사항·우선순위·이전 신청 이력 등"
                  rows={2}
                  className={inputCls + " resize-none"} />
              </div>
            </div>
          </details>
        )}

        {/* 제출 */}
        <div className="flex gap-3 pt-2">
          <button onClick={onSubmit}
            className="flex-1 py-3 bg-violet-600 text-white rounded-xl text-[14px] font-bold hover:bg-violet-500 transition-all active:scale-[0.98]">
            상담 시작
          </button>
        </div>
      </div>
    </div>
  );
}


// ─── 특정 공고 검색 패널 ───
function AnnounceSearchPanel({ headers, toast, dark, t, onStartConsult }: {
  headers: () => any; toast: any; dark: boolean; t: any;
  onStartConsult: (ann: { id: number; title: string; summary?: string }) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedAnn, setSelectedAnn] = useState<any>(null);
  const [analysisData, setAnalysisData] = useState<any>(null);
  // 자동완성
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // 입력 시 자동완성
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!query.trim() || query.trim().length < 2 || selectedAnn) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`${API}/api/announcements/search?q=${encodeURIComponent(query)}&limit=8`, { headers: headers() });
        if (res.ok) {
          const data = await res.json();
          const items = data.data || data.announcements || (Array.isArray(data) ? data : []);
          const normalized = items.map((a: any) => ({ ...a, id: a.announcement_id || a.id }));
          setSuggestions(normalized);
          setShowSuggestions(normalized.length > 0);
        }
      } catch {/* */}
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, headers, selectedAnn]);

  const search = async (overrideQ?: string) => {
    const q = (overrideQ ?? query).trim();
    if (!q) return;
    if (overrideQ !== undefined) setQuery(overrideQ);
    setLoading(true);
    setSelectedAnn(null);
    setAnalysisData(null);
    setShowSuggestions(false);
    try {
      const res = await fetch(`${API}/api/announcements/search?q=${encodeURIComponent(q)}&limit=20`, { headers: headers() });
      if (res.ok) {
        const data = await res.json();
        const items = data.data || data.announcements || (Array.isArray(data) ? data : []);
        const normalized = items.map((a: any) => ({ ...a, id: a.announcement_id || a.id }));
        setResults(normalized);
      }
    } catch { toast("검색 실패", "error"); }
    setLoading(false);
  };

  const QUICK_FILTERS = [
    { emoji: "💰", label: "정책자금", q: "정책자금" },
    { emoji: "🔬", label: "R&D", q: "R&D" },
    { emoji: "🚀", label: "창업", q: "창업" },
    { emoji: "🌐", label: "수출", q: "수출" },
    { emoji: "👥", label: "고용", q: "고용" },
    { emoji: "🏗️", label: "시설", q: "시설" },
  ];

  // 자동완성 항목 클릭 → 즉시 분석
  const pickSuggestion = (ann: any) => {
    setQuery(ann.title);
    setShowSuggestions(false);
    setResults([]);
    loadAnalysis(ann);
  };

  const loadAnalysis = async (ann: any) => {
    setSelectedAnn(ann);
    setAnalysisData(null);
    try {
      const annId = ann.id || ann.announcement_id;
      // PRO 전용 — DB의 deep_analysis 우선 사용
      const res = await fetch(`${API}/api/pro/announcements/${annId}/analyze`, { headers: headers() });
      if (res.ok) {
        const data = await res.json();
        setAnalysisData(data);
      }
    } catch (e) { console.error("[PRO]", e); }
  };

  const inputCls = `flex-1 px-4 py-2.5 rounded-lg text-[16px] md:text-[13px] outline-none border transition-all ${
    dark ? "bg-[#1a1c30] border-white/[0.08] text-slate-200 focus:border-violet-500/40" : "bg-white border-slate-200 text-slate-700 focus:border-violet-400"
  }`;

  return (
    <div className="space-y-4">
      <h3 className={`text-sm font-bold ${dark ? "text-slate-200" : "text-slate-700"}`}>특정 공고 상담</h3>
      <p className={`text-[12px] ${t.muted}`}>공고명이나 키워드로 검색하여 상세 상담을 시작하세요</p>

      {/* 검색 + 자동완성 */}
      <div className="relative">
        <div className="flex gap-2">
          <input type="text" value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
            onKeyDown={(e) => { if (e.key === "Enter") { setShowSuggestions(false); search(); } }}
            placeholder="상담할 공고명을 입력하세요 (예: 청년창업)" className={inputCls} />
          <button onClick={() => search()} disabled={loading || !query.trim()}
            className="px-4 py-2.5 bg-violet-600 text-white rounded-lg text-[12px] font-bold hover:bg-violet-500 disabled:opacity-30">
            검색
          </button>
        </div>

        {/* 빠른 필터 칩 */}
        <div className="flex flex-wrap gap-2 mt-3">
          {QUICK_FILTERS.map(f => (
            <button
              key={f.label}
              onClick={() => search(f.q)}
              disabled={loading}
              className={`px-3 py-1.5 rounded-full text-[11px] font-semibold border transition-all ${
                dark
                  ? "bg-white/[0.03] border-white/[0.08] text-slate-300 hover:bg-violet-500/15 hover:border-violet-500/30"
                  : "bg-white border-slate-200 text-slate-600 hover:bg-violet-50 hover:border-violet-300"
              } disabled:opacity-50`}
            >
              {f.emoji} {f.label}
            </button>
          ))}
        </div>

        {/* 자동완성 드롭다운 */}
        {showSuggestions && suggestions.length > 0 && (
          <div className={`absolute left-0 right-16 top-full mt-1 z-20 rounded-lg border shadow-2xl max-h-96 overflow-y-auto ${
            dark ? "bg-[#1a1c30] border-violet-500/30" : "bg-white border-slate-200"
          }`}>
            {suggestions.map((ann: any) => (
              <button key={ann.id}
                onMouseDown={(e) => { e.preventDefault(); pickSuggestion(ann); }}
                className={`w-full text-left px-3 py-2.5 border-b last:border-b-0 transition-colors ${
                  dark ? "border-white/[0.04] hover:bg-violet-500/10" : "border-slate-100 hover:bg-violet-50"
                }`}>
                <p className={`text-[12px] font-semibold truncate ${dark ? "text-slate-100" : "text-slate-800"}`}>
                  {ann.title}
                </p>
                <div className={`flex gap-2 mt-0.5 text-[10px] ${t.muted}`}>
                  {ann.department && <span>{ann.department}</span>}
                  {ann.support_amount && <span>· {ann.support_amount}</span>}
                  {ann.deadline_date && <span>· ~{String(ann.deadline_date).slice(5, 10)}</span>}
                </div>
              </button>
            ))}
            <div className={`px-3 py-1.5 text-[10px] text-center ${t.muted} ${dark ? "bg-white/[0.02]" : "bg-slate-50"}`}>
              제안된 공고 클릭 또는 Enter로 전체 검색
            </div>
          </div>
        )}
      </div>

      {loading && <p className={`text-[12px] ${t.muted}`}>검색 중...</p>}

      {/* 검색 결과 없음 */}
      {!loading && query.trim().length >= 2 && results.length === 0 && !selectedAnn && (
        <p className={`text-[12px] py-4 text-center ${t.muted}`}>검색 결과가 없습니다. 다른 키워드로 검색해보세요.</p>
      )}

      {/* 결과 목록 */}
      {results.length > 0 && !selectedAnn && (
        <div data-testid="pro-search-results" className={`rounded-xl border overflow-hidden ${dark ? "border-white/[0.06]" : "border-slate-200"}`}>
          {results.map((ann: any) => (
            <button key={ann.id} data-testid="pro-search-result-item" onClick={() => loadAnalysis(ann)}
              className={`w-full text-left px-4 py-3 border-b last:border-b-0 transition-all ${dark ? "border-white/[0.04] hover:bg-white/[0.03]" : "border-slate-100 hover:bg-violet-50/30"}`}>
              <p className={`text-[13px] font-semibold truncate ${dark ? "text-slate-200" : "text-slate-800"}`}>{ann.title}</p>
              <div className={`flex gap-3 mt-1 text-[11px] ${t.muted}`}>
                {ann.organization && <span>{ann.organization}</span>}
                {ann.support_amount && <span>{ann.support_amount}</span>}
                {ann.deadline_date && <span>~{String(ann.deadline_date).slice(5, 10)}</span>}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* 선택된 공고 상세 */}
      {selectedAnn && (
        <div className={`p-4 rounded-xl border ${dark ? "bg-[#1a1c30] border-white/[0.08]" : "bg-white border-slate-200"}`}>
          <h4 className={`text-[14px] font-bold mb-2 ${dark ? "text-slate-100" : "text-slate-800"}`}>{selectedAnn.title}</h4>
          {analysisData && (
            <div className={`text-[12px] space-y-1.5 mb-3 ${dark ? "text-slate-300" : "text-slate-600"}`}>
              {analysisData.organization && <p><span className={t.muted}>주관:</span> {analysisData.organization}</p>}
              {analysisData.support_amount && <p><span className={t.muted}>지원금:</span> {analysisData.support_amount}</p>}
              {analysisData.deadline_date && <p><span className={t.muted}>마감:</span> {String(analysisData.deadline_date).slice(0, 10)}</p>}
              {analysisData.has_db_analysis ? (
                <>
                  {analysisData.eligibility && <p><span className={t.muted}>자격요건:</span> {analysisData.eligibility.slice(0, 300)}</p>}
                  {analysisData.support_details && <p><span className={t.muted}>지원내용:</span> {analysisData.support_details.slice(0, 300)}</p>}
                  {analysisData.application_method && <p><span className={t.muted}>신청방법:</span> {analysisData.application_method.slice(0, 200)}</p>}
                  {analysisData.target_summary && <p className="text-emerald-500 text-[11px] mt-2">✓ 분석 데이터 활용</p>}
                </>
              ) : (
                <p className={`text-amber-500 text-[11px]`}>⚠ 상세 분석이 아직 없습니다 — 기본 정보만 표시됩니다</p>
              )}
            </div>
          )}
          <div className="flex gap-2">
            <button onClick={() => onStartConsult({
              id: selectedAnn.id,
              title: selectedAnn.title,
              summary: analysisData ? `주관: ${analysisData.organization || ""}\n지원금: ${analysisData.support_amount || ""}\n자격: ${(analysisData.parsed_sections?.eligibility || analysisData.eligibility || "").slice(0, 300)}` : "",
            })} className="px-4 py-2 bg-violet-600 text-white rounded-lg text-[12px] font-bold hover:bg-violet-500">
              이 공고로 상담 시작
            </button>
            <button onClick={() => { setSelectedAnn(null); setAnalysisData(null); }}
              className={`px-4 py-2 rounded-lg text-[12px] font-semibold ${dark ? "text-slate-400 hover:bg-white/5" : "text-slate-500 hover:bg-slate-100"}`}>
              다른 공고 선택
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
