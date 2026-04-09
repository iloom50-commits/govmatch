"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useToast } from "@/components/ui/Toast";
import { useModalBack } from "@/hooks/useModalBack";
import DOMPurify from "dompurify";

const API = process.env.NEXT_PUBLIC_API_URL;

// ─── 타입 ───
interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  choices?: string[];
  announcements?: any[];
  done?: boolean;
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

type ActiveView = "chat" | "clients" | "history" | "reports";
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
    root: "bg-[#0d0e1a] text-slate-200",
    header: "bg-[#0d0e1a] border-b border-white/[0.06]",
    leftNav: "bg-[#111222] border-r border-white/[0.06]",
    center: "bg-[#151628]",
    right: "bg-[#111222] border-l border-white/[0.06]",
    card: "bg-[#1a1c30]",
    cardHover: "hover:bg-[#1f2140]",
    cardBorder: "border-white/[0.06]",
    input: "bg-[#1a1c30] border-white/[0.08] text-slate-200 placeholder-slate-500 focus:border-violet-500/50 focus:ring-violet-500/20",
    bubble: "bg-[#1e2040] text-slate-200",
    menuActive: "bg-violet-500/10 text-violet-400 border-l-2 border-violet-500",
    menuInactive: "text-slate-500 hover:text-slate-300 hover:bg-white/[0.03]",
    sectionTitle: "text-slate-500",
    border: "border-white/[0.06]",
    muted: "text-slate-500",
    flowActive: "bg-violet-500/15 text-violet-400 border border-violet-500/30",
    flowDone: "text-emerald-400",
    flowPending: "text-slate-600",
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
  useModalBack(true, onClose);

  // 상태
  const [activeView, setActiveView] = useState<ActiveView>("chat");
  const [selectedClient, setSelectedClient] = useState<ClientProfile | null>(null);
  const [existingClients, setExistingClients] = useState<ClientProfile[]>([]);
  const [flowState, setFlowState] = useState<FlowState>("idle");
  const [clientCategory, setClientCategory] = useState<ClientCategory>("");

  // 대화
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [systemContext, setSystemContext] = useState("");
  const [typing, setTyping] = useState(false); // 타이핑 애니메이션 중
  const [typingText, setTypingText] = useState(""); // 현재까지 타이핑된 텍스트
  const typingRef = useRef<NodeJS.Timeout | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // 모바일
  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(false);

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

  const getToken = () => localStorage.getItem("auth_token") || "";
  const headers = useCallback(() => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${getToken()}`,
  }), []);

  // 스크롤
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  // 기존 고객 목록 로드
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/api/pro/clients`, { headers: headers() });
        if (res.ok) {
          const data = await res.json();
          setExistingClients(data.clients || []);
        }
      } catch { /* */ }
    })();
  }, [headers]);

  // ─── AI 대화 전송 ───
  const sendToAI = useCallback(async (chatHistory: ChatMessage[]) => {
    setLoading(true);
    try {
      const messagesPayload = chatHistory.map((m, i) => ({
        role: m.role,
        text: (i === 0 && m.role === "user" && systemContext) ? `${systemContext}\n\n${m.text}` : m.text,
      }));

      const res = await fetch(`${API}/api/ai/consultant/chat`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ messages: messagesPayload }),
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
          // 타이핑 완료 — choices 표시
          setMessages(prev => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.role === "assistant") {
              updated[updated.length - 1] = { ...last, text: fullText, choices };
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
  }, [headers, systemContext, toast]);

  // ─── 메시지 전송 ───
  const handleSend = (text: string) => {
    if (!text.trim() || loading || typing) return;
    const userMsg: ChatMessage = { role: "user", text: text.trim() };
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInput("");
    sendToAI(newHistory);
    if (flowState === "idle") setFlowState("info_collect");
  };

  // ─── 파일 첨부 (multipart 업로드 → 서버에서 텍스트 추출) ───
  const handleFileAttach = async (file: File) => {
    if (file.size > 10 * 1024 * 1024) { toast("10MB 이하만 가능", "error"); return; }
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
    setSystemContext(client
      ? `[전문가 상담 모드] 당신은 지원사업 컨설턴트의 AI 어시스턴트입니다. 컨설턴트가 고객 상담을 진행하고 있습니다.\n기존 고객: ${client.client_name}\n지역: ${client.address_city || ""}\n업종: ${client.industry_name || ""}\n매출: ${client.revenue_bracket || ""}\n\n이미 수집된 정보는 다시 묻지 말고, 추가로 필요한 정보만 질문하세요. 존댓말을 사용하세요.`
      : `[전문가 상담 모드] 당신은 지원사업 컨설턴트의 AI 어시스턴트입니다. 컨설턴트가 고객 상담을 진행하고 있습니다.\n고객유형: ${category}\n\n컨설턴트에게 고객 정보를 하나씩 질문하세요. 이미 답한 정보는 다시 묻지 마세요. 존댓말을 사용하세요.`);
    setSelectedClient(client || null);
    setLeftOpen(false);

    const catLabel = category === "individual_biz" ? "개인사업자" : category === "corporate" ? "법인사업자" : category === "individual" ? "개인" : "고객";

    if (client) {
      setMessages([{
        role: "assistant",
        text: `**${client.client_name}** 고객 정보를 불러왔습니다.\n\n지역: ${client.address_city || "미등록"}\n업종: ${client.industry_name || "미등록"}\n매출: ${client.revenue_bracket || "미등록"}\n\n어떤 상담을 진행하시겠습니까?`,
        choices: ["맞춤 지원사업 매칭", "첨부 자료 분석", "자격요건 검토"],
      }]);
    } else if (category === "unknown") {
      setMessages([{
        role: "assistant",
        text: "고객 유형이 아직 파악되지 않았습니다.\n\n고객에 대해 알고 계신 정보를 알려주세요.",
        choices: ["기업 고객입니다", "개인 고객입니다", "사업 준비 중인 고객입니다"],
      }]);
    } else {
      setMessages([{
        role: "assistant",
        text: `**${catLabel}** 상담을 시작합니다.\n\n고객사 서류가 있으시면 우측에서 첨부해 주세요.\n고객사의 기업명은 무엇인가요?`,
        choices: category === "individual"
          ? ["서류가 있습니다", "구두 정보만 있습니다"]
          : ["서류가 있습니다", "구두 정보만 있습니다"],
      }]);
    }
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
          <button onClick={toggleDark} className="p-2 hover:bg-white/10 rounded-lg transition-colors" title={dark ? "라이트 모드" : "다크 모드"}>
            {dark ? Icons.sun : Icons.moon}
          </button>
          <button onClick={() => setRightOpen(!rightOpen)} className="lg:hidden p-2 hover:bg-white/10 rounded-lg transition-colors">
            {Icons.info}
          </button>
          <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
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
                onClick={() => { setClientCategory(""); setMessages([]); setActiveView("chat"); setLeftOpen(false); }}
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
                { view: "chat" as ActiveView, icon: Icons.chat, label: "상담" },
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

            {/* 연동 서비스 — AI Secretary 스타일 */}
            <div className={`p-3 border-t hidden lg:block ${t.border}`}>
              <p className={`text-[10px] font-bold uppercase tracking-wider mb-2.5 ${t.sectionTitle}`}>연동 서비스</p>
              <div className="space-y-2">
                {[
                  { name: "GovMatch", desc: "정부지원사업 매칭", active: true },
                  { name: "SmartDoc", desc: "신청서 작성 도구", active: false },
                  { name: "노무 AI", desc: "근로/4대보험 자문", active: false },
                  { name: "세무 AI", desc: "법인세/부가세 자문", active: false },
                  { name: "법무 AI", desc: "계약/규제 자문", active: false },
                  { name: "산업안전 AI", desc: "산업재해/안전법 자문", active: false },
                ].map(svc => (
                  <div key={svc.name} className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-[11px] transition-colors ${svc.active ? t.serviceActive : t.serviceInactive}`}>
                    <div className={`w-7 h-7 rounded-md flex items-center justify-center text-[11px] font-bold ${
                      svc.active
                        ? "bg-violet-600 text-white"
                        : dark ? "bg-white/[0.05] text-slate-500" : "bg-slate-100 text-slate-400"
                    }`}>
                      {svc.name[0]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`font-semibold truncate ${svc.active ? (dark ? "text-slate-200" : "text-slate-700") : t.muted}`}>{svc.name}</p>
                      <p className={`text-[9px] truncate ${t.muted}`}>{svc.desc}</p>
                    </div>
                    {svc.active ? (
                      <span className="text-emerald-500 flex-shrink-0">{Icons.link}</span>
                    ) : (
                      <span className={`text-[9px] flex-shrink-0 ${t.muted}`}>준비 중</span>
                    )}
                  </div>
                ))}
              </div>
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

              {/* 유형 선택 (상담 미시작) */}
              {!clientCategory && messages.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center px-6 overflow-y-auto">
                  <div className="max-w-md text-center">
                    <div className={`w-16 h-16 mx-auto mb-5 rounded-2xl flex items-center justify-center ${t.emptyIcon}`}>
                      <svg className="w-8 h-8 text-violet-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155" />
                      </svg>
                    </div>
                    <h2 className={`text-xl font-bold mb-2 ${dark ? "text-slate-100" : "text-slate-800"}`}>고객 유형을 선택하면</h2>
                    <h2 className={`text-xl font-bold mb-2 ${dark ? "text-slate-100" : "text-slate-800"}`}>AI 상담이 시작됩니다.</h2>
                    <p className={`text-[13px] mb-8 ${t.muted}`}>
                      고객 정보 수집 → 맞춤 지원사업 매칭 → 자격요건 분석까지 한번에
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { key: "individual_biz" as ClientCategory, label: "개인사업자", icon: "🏪", desc: "1인 사업자, 프리랜서" },
                        { key: "corporate" as ClientCategory, label: "법인사업자", icon: "🏢", desc: "법인 기업" },
                        { key: "individual" as ClientCategory, label: "개인", icon: "👤", desc: "취업·복지·주거" },
                        { key: "unknown" as ClientCategory, label: "모름", icon: "💬", desc: "AI가 대화로 파악" },
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
              ) : (
                <>
                  {/* 대화 영역 */}
                  <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 lg:px-6 py-4 space-y-3">
                    {messages.map((msg, i) => (
                      <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                        <div className="max-w-[80%]">
                          <div className={`px-4 py-3 rounded-2xl text-[13px] leading-relaxed ${
                            msg.role === "user"
                              ? "bg-violet-600 text-white rounded-br-md"
                              : `${t.bubble} rounded-bl-md`
                          }`} dangerouslySetInnerHTML={{ __html: renderText(msg.text) }} />
                          {/* 선택지 */}
                          {msg.role === "assistant" && msg.choices && msg.choices.length > 0 && i === messages.length - 1 && !loading && (
                            <div className="flex flex-wrap gap-2 mt-2">
                              {msg.choices.map((choice, ci) => (
                                <button key={ci} onClick={() => handleSend(choice)}
                                  className={`px-3 py-1.5 rounded-full text-[12px] font-semibold transition-all active:scale-95 border ${
                                    dark
                                      ? "bg-violet-500/10 border-violet-500/30 text-violet-400 hover:bg-violet-500/20"
                                      : "bg-white border-violet-200 text-violet-700 hover:bg-violet-50 hover:border-violet-400"
                                  }`}>
                                  {choice}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
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

                      // AI가 특정 정보를 "요청"하는 경우만 위젯 표시
                      // 확인/완료/분석 응답은 제외
                      const confirmWords = ["이군요", "이시군요", "군요", "입니다", "입력하셨", "확인했", "접수", "감사합니다", "찾아보", "분석", "매칭", "추천", "결과", "선정", "지원사업"];
                      if (confirmWords.some(w => lastText.includes(w))) return null;

                      // 질문 패턴이 있어야 위젯 표시
                      const askWords = ["알려주세요", "입력해주세요", "선택해주세요", "어떻게 되나요", "무엇인가요", "어디인가요"];
                      const isAsking = lastText.includes("?") || askWords.some(w => lastText.includes(w));
                      if (!isAsking) return null;

                      // 각 필드를 "요청"하는 패턴만 감지 (확인 언급 제외)
                      const fields: { key: string; label: string; type: "text" | "select" | "date"; options?: string[] }[] = [];
                      const asking = (keyword: string) => {
                        // "기업명을 알려주세요" → true / "기업명이 dd이군요" → false
                        const idx = lastText.indexOf(keyword);
                        if (idx === -1) return false;
                        const after = lastText.substring(idx + keyword.length, idx + keyword.length + 5);
                        // 확인 패턴: "이", "은 ", "는 " 뒤에 값이 오는 경우
                        if (/^(이|은\s|는\s)/.test(after)) return false;
                        return true;
                      };

                      if (asking("설립일") || asking("생년월일")) fields.push({ key: "date", label: "설립일/생년월일", type: "date" });
                      if (asking("직원") || asking("인원")) fields.push({ key: "emp", label: "직원수", type: "select", options: ["5인 미만", "5~10인", "10~30인", "30~50인", "50인 이상"] });
                      if (asking("매출")) fields.push({ key: "rev", label: "매출 규모", type: "select", options: ["1억 미만", "1억~5억", "5억~10억", "10억~50억", "50억 이상"] });
                      if (asking("업종") || asking("분야") || asking("관심")) fields.push({ key: "interest", label: lastText.includes("업종") ? "업종" : "관심분야", type: "text" });
                      if (asking("지역") || asking("소재지") || asking("거주")) fields.push({ key: "city", label: "지역", type: "select", options: ["서울", "경기", "부산", "인천", "대구", "대전", "광주", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"] });
                      if (asking("기업명") || asking("이름")) fields.push({ key: "name", label: lastText.includes("기업명") ? "기업명" : "이름", type: "text" });

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

                  {/* 입력 영역 — AI Secretary 스타일 */}
                  <div className={`flex-shrink-0 border-t px-4 lg:px-6 py-3 ${t.border} ${dark ? "bg-[#0d0e1a]" : "bg-white"}`}
                    onDragOver={(e) => { e.preventDefault(); }}
                    onDrop={async (e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) await handleFileAttach(f); }}
                  >
                    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border transition-colors ${
                      dark ? "bg-[#1a1c30] border-white/[0.08] focus-within:border-violet-500/40" : "bg-slate-50 border-slate-200 focus-within:border-violet-400"
                    }`}>
                      <label className={`p-1.5 rounded-lg cursor-pointer transition-colors flex-shrink-0 ${dark ? "text-slate-500 hover:text-violet-400 hover:bg-white/5" : "text-slate-400 hover:text-violet-600 hover:bg-violet-50"}`} title="자료 첨부">
                        {Icons.attach}
                        <input type="file" className="hidden" accept=".pdf,.hwp,.hwpx,.docx,.doc,.xlsx,.txt"
                          onChange={async (e) => { const f = e.target.files?.[0]; if (f) await handleFileAttach(f); e.target.value = ""; }} />
                      </label>
                      <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) { e.preventDefault(); handleSend(input); } }}
                        placeholder="고객 정보를 입력하거나 질문하세요... (Enter: 전송)"
                        disabled={loading || typing}
                        className={`flex-1 py-2 text-[14px] outline-none bg-transparent transition-all disabled:opacity-50 ${dark ? "text-slate-200 placeholder-slate-500" : "text-slate-700 placeholder-slate-400"}`}
                      />
                      <button
                        onClick={() => handleSend(input)}
                        disabled={loading || typing || !input.trim()}
                        className="px-4 py-2 bg-violet-600 text-white rounded-xl text-[13px] font-bold hover:bg-violet-500 transition-all active:scale-95 disabled:opacity-30 flex-shrink-0 flex items-center gap-1.5"
                      >
                        전송 {Icons.send}
                      </button>
                    </div>
                  </div>
                </>
              )}
            </>
          ) : (
            /* 고객관리 / 상담이력 / 보고서 */
            <div className={`flex-1 overflow-y-auto p-4 ${dark ? "text-slate-200" : ""}`}>
              {activeView === "clients" && <ClientsTabWrapper headers={headers} toast={toast} dark={dark} t={t} />}
              {activeView === "history" && <HistoryTabWrapper headers={headers} toast={toast} />}
              {activeView === "reports" && <ReportsTabWrapper headers={headers} toast={toast} />}
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

          {/* 자료 첨부 */}
          <div className={`p-4 border-b ${t.border}`}>
            <p className={`text-[10px] font-bold uppercase tracking-wider mb-1.5 ${t.sectionTitle}`}>자료 첨부</p>
            <p className={`text-[10px] mb-3 ${t.muted}`}>재무제표, 사업계획서 등을 첨부하면 AI가 분석합니다</p>
            <label
              className={`block w-full min-h-[100px] flex flex-col items-center justify-center border-2 border-dashed rounded-xl cursor-pointer transition-all ${
                dark ? "border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.04] hover:border-violet-500/30" : "border-slate-200 bg-white hover:bg-violet-50 hover:border-violet-300"
              }`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={async (e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) await handleFileAttach(f); }}
            >
              <svg className={`w-6 h-6 mb-1 ${t.muted}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
              </svg>
              <p className={`text-[11px] font-semibold ${dark ? "text-violet-400" : "text-violet-600"}`}>파일을 드래그하거나 클릭하여 선택</p>
              <p className={`text-[9px] mt-0.5 ${t.muted}`}>PDF, HWP, DOCX (10MB)</p>
              <input type="file" className="hidden" accept=".pdf,.hwp,.hwpx,.docx,.doc,.xlsx,.txt"
                onChange={async (e) => { const f = e.target.files?.[0]; if (f) await handleFileAttach(f); e.target.value = ""; }} />
            </label>
          </div>

          {/* 연동 서비스 (모바일) */}
          <div className={`p-4 lg:hidden`}>
            <p className={`text-[10px] font-bold uppercase tracking-wider mb-2.5 ${t.sectionTitle}`}>연동 서비스</p>
            <div className="space-y-2">
              {[
                { name: "GovMatch", desc: "정부지원사업 매칭", active: true },
                { name: "SmartDoc", desc: "신청서 작성 도구", active: false },
                { name: "노무 AI", desc: "근로/4대보험 자문", active: false },
                { name: "세무 AI", desc: "법인세/부가세 자문", active: false },
                { name: "법무 AI", desc: "계약/규제 자문", active: false },
                { name: "산업안전 AI", desc: "산업재해/안전법 자문", active: false },
              ].map(svc => (
                <div key={svc.name} className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-[11px] ${svc.active ? t.serviceActive : t.serviceInactive}`}>
                  <div className={`w-7 h-7 rounded-md flex items-center justify-center text-[11px] font-bold ${
                    svc.active ? "bg-violet-600 text-white" : dark ? "bg-white/[0.05] text-slate-500" : "bg-slate-100 text-slate-400"
                  }`}>{svc.name[0]}</div>
                  <div className="flex-1 min-w-0">
                    <p className={`font-semibold ${svc.active ? (dark ? "text-slate-200" : "text-slate-700") : t.muted}`}>{svc.name}</p>
                    <p className={`text-[9px] ${t.muted}`}>{svc.desc}</p>
                  </div>
                  {svc.active ? <span className="text-emerald-500">{Icons.link}</span> : <span className={`text-[9px] ${t.muted}`}>준비 중</span>}
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

// ─── ProDashboard 서브컴포넌트 래퍼 ───
function ClientsTabWrapper({ headers, toast, dark, t }: { headers: () => any; toast: any; dark: boolean; t: any }) {
  const [clients, setClients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [showEmail, setShowEmail] = useState(false);

  const fetchClients = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/pro/clients/with-history`, { headers: headers() });
      if (res.ok) {
        const data = await res.json();
        setClients(data.clients || []);
      }
    } catch { /* */ }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchClients(); }, [fetchClients]);

  const toggleSelect = (id: number) => setSelectedIds(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const selectAll = () => setSelectedIds(selectedIds.size === clients.length ? new Set() : new Set(clients.map(c => c.id)));

  const handleExport = () => {
    const token = localStorage.getItem("auth_token") || "";
    window.open(`${API}/api/pro/clients/export?authorization=Bearer ${token}`, "_blank");
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
            <button onClick={() => setShowEmail(true)} className="px-3 py-1.5 bg-violet-600 text-white text-xs font-bold rounded-lg hover:bg-violet-500">
              선택 {selectedIds.size}명 이메일
            </button>
          )}
          <button onClick={handleExport} className={`px-3 py-1.5 text-xs font-bold rounded-lg ${dark ? "bg-white/[0.05] text-slate-300 hover:bg-white/[0.08]" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
            CSV 다운로드
          </button>
          <button onClick={() => { toast("고객 추가는 상담에서 자동 등록됩니다", "info"); }}
            className="px-3 py-1.5 bg-violet-600 text-white text-xs font-bold rounded-lg hover:bg-violet-500">
            + 고객 추가
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
              {["기업명", "업종", "지역", "매출", "전화", "최근상담", "상담수", "상태"].map((h, i) => (
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
                </tr>
                {expanded === c.id && (
                  <tr>
                    <td colSpan={9} className={`px-4 py-3 border-b ${dark ? "bg-white/[0.02] border-white/[0.04]" : "bg-slate-50 border-slate-200"}`}>
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
function InlineInputWidget({ fields, dark, t, onSubmit, onSkip }: {
  fields: { key: string; label: string; type: "text" | "select" | "date"; options?: string[] }[];
  dark: boolean;
  t: any;
  onSubmit: (values: Record<string, string>) => void;
  onSkip: () => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const update = (key: string, val: string) => setValues(prev => ({ ...prev, [key]: val }));

  const inputCls = `px-3 py-2 rounded-lg text-[13px] outline-none border transition-all focus:ring-2 focus:ring-violet-500/20 ${
    dark ? "bg-[#1a1c30] border-white/[0.08] text-slate-200 focus:border-violet-500/40" : "bg-white border-slate-200 text-slate-700 focus:border-violet-400"
  }`;

  return (
    <div className={`mx-4 mb-3 p-3 rounded-xl border ${dark ? "bg-[#1a1c30] border-violet-500/20" : "bg-violet-50/50 border-violet-200"}`}>
      <div className="flex flex-wrap gap-2 items-end">
        {fields.map(f => (
          <div key={f.key} className="flex-1 min-w-[120px]">
            <label className={`block text-[10px] font-bold mb-1 ${dark ? "text-violet-400" : "text-violet-600"}`}>{f.label}</label>
            {f.type === "select" && f.options ? (
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
