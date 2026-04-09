"use client";

import { useState, useEffect, useCallback, useRef } from "react";
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
      const aiMsg: ChatMessage = {
        role: "assistant",
        text: data.reply || "",
        choices: data.choices || [],
        done: data.done || false,
      };
      setMessages([...chatHistory, aiMsg]);

      if (data.done && data.profile) {
        setFlowState("matching");
      }
    } catch {
      toast("서버 연결에 실패했습니다.", "error");
    }
    setLoading(false);
  }, [headers, systemContext, toast]);

  // ─── 메시지 전송 ───
  const handleSend = (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: ChatMessage = { role: "user", text: text.trim() };
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInput("");
    sendToAI(newHistory);
    if (flowState === "idle") setFlowState("info_collect");
  };

  // ─── 파일 첨부 ───
  const handleFileAttach = async (file: File) => {
    if (file.size > 10 * 1024 * 1024) { toast("10MB 이하만 가능", "error"); return; }
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
        headers: headers(),
        body: JSON.stringify({ text: text.substring(0, 8000), file_name: file.name, file_type: "other" }),
      });
      const analyzeData = analyzeRes.ok ? await analyzeRes.json() : { summary: "분석 실패" };
      setMessages(prev => [...prev, {
        role: "assistant",
        text: `📊 **${file.name}** 분석 결과:\n\n${analyzeData.summary}\n\n이 정보를 바탕으로 어떤 상담을 원하시나요?`,
        choices: ["이 고객에 맞는 지원사업 찾아줘", "자격요건 판단해줘", "추가 자료를 올릴게요"],
      }]);
      setSystemContext(prev => `${prev}\n\n[첨부: ${file.name}]\n${text.substring(0, 5000)}`);
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
    setSystemContext(client ? `[기존 고객: ${client.client_name}]\n지역: ${client.address_city || ""}\n업종: ${client.industry_name || ""}\n매출: ${client.revenue_bracket || ""}` : `[고객유형: ${category}]`);
    setSelectedClient(client || null);
    setLeftOpen(false);

    const catLabel = category === "individual_biz" ? "개인사업자" : category === "corporate" ? "법인사업자" : category === "individual" ? "개인" : "고객";

    if (client) {
      setMessages([{
        role: "assistant",
        text: `**${client.client_name}** 고객 정보를 불러왔습니다.\n\n지역: ${client.address_city || "미등록"}\n업종: ${client.industry_name || "미등록"}\n매출: ${client.revenue_bracket || "미등록"}\n\n어떤 상담을 도와드릴까요?`,
        choices: ["이 고객에 맞는 지원사업 찾아줘", "첨부 자료 분석해줘", "자격요건 판단해줘"],
      }]);
    } else if (category === "unknown") {
      setMessages([{
        role: "assistant",
        text: "고객 유형을 모르셔도 괜찮습니다.\n\n고객에 대해 아는 정보를 자유롭게 알려주세요.",
        choices: ["기업 고객이에요", "개인 고객이에요", "사업을 준비 중이에요"],
      }]);
    } else {
      setMessages([{
        role: "assistant",
        text: `**${catLabel}** 고객이시군요.\n\n자료가 있으시면 우측에서 첨부해 주세요.\n없으면 바로 대화로 시작할게요.`,
        choices: category === "individual"
          ? ["이름부터 알려줄게요", "관심 분야가 취업이에요", "자료 없이 바로 시작"]
          : ["기업명부터 알려줄게요", "매출이 1억 미만이에요", "자료 없이 바로 시작"],
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

  // ─── 플로우 상태 라벨 ───
  const flowSteps = [
    { key: "idle", label: "대기" },
    { key: "info_collect", label: "정보 수집" },
    { key: "matching", label: "공고 매칭" },
    { key: "analysis", label: "상세 분석" },
    { key: "done", label: "완료" },
  ];

  return (
    <div className={`fixed inset-0 z-[60] flex flex-col transition-colors duration-300 ${dark ? "bg-[#1a1b2e] text-slate-200" : "bg-slate-50 text-slate-800"}`}>
      {/* ─── 헤더 ─── */}
      <div className={`flex items-center justify-between px-4 py-2.5 flex-shrink-0 ${dark ? "bg-[#12131f] border-b border-white/10" : "bg-gradient-to-r from-violet-700 to-purple-700"} text-white`}>
        <div className="flex items-center gap-3">
          {/* 모바일 햄버거 */}
          <button onClick={() => setLeftOpen(!leftOpen)} className="lg:hidden p-1.5 hover:bg-white/20 rounded-lg">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" /></svg>
          </button>
          <span className="px-2 py-0.5 bg-white/20 text-[10px] font-bold rounded">PRO</span>
          <div>
            <p className="text-[14px] font-bold">전문가 대시보드</p>
            <p className="text-[10px] text-white/70">AI 기반 지원사업 컨설팅 도구</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-white/60 hidden sm:block">상담 {planStatus?.ai_used || 0}/{planStatus?.consult_limit || 50}회</span>
          {/* 다크모드 토글 */}
          <button onClick={toggleDark} className="p-1.5 hover:bg-white/20 rounded-lg transition-all" title={dark ? "라이트 모드" : "다크 모드"}>
            {dark ? (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" /></svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" /></svg>
            )}
          </button>
          {/* 모바일 우측 패널 토글 */}
          <button onClick={() => setRightOpen(!rightOpen)} className="lg:hidden p-1.5 hover:bg-white/20 rounded-lg">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" /></svg>
          </button>
          <button onClick={onClose} className="p-1.5 hover:bg-white/20 rounded-lg">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      </div>

      {/* ─── 3패널 그리드 ─── */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[220px_1fr_280px] overflow-hidden">

        {/* ═══ 좌측 네비 ═══ */}
        <nav className={`${leftOpen ? "fixed inset-0 z-50 bg-black/30 lg:relative lg:bg-transparent" : "hidden lg:flex"} lg:flex flex-col overflow-y-auto ${dark ? "bg-[#151625] border-r border-white/10" : "bg-white border-r border-slate-200 shadow-sm"}`}>
          <div className={`${leftOpen ? `w-[260px] h-full shadow-2xl ${dark ? "bg-[#151625]" : "bg-white"}` : "w-full"} flex flex-col`}>
            {leftOpen && <button onClick={() => setLeftOpen(false)} className="lg:hidden self-end p-2 m-2 text-slate-400">✕</button>}

            <div className={`p-3 border-b ${dark ? "border-white/10" : "border-slate-200"}`}>
              <button
                onClick={() => { setClientCategory(""); setMessages([]); setActiveView("chat"); setLeftOpen(false); }}
                className="w-full py-2.5 bg-violet-600 text-white rounded-xl text-[13px] font-bold hover:bg-violet-700 transition-all active:scale-[0.98]"
              >
                + 새 상담 시작
              </button>
            </div>

            {/* 고객 선택 */}
            {existingClients.length > 0 && (
              <div className={`p-3 border-b ${dark ? "border-white/10" : "border-slate-200"}`}>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">기존 고객</p>
                <select
                  onChange={(e) => {
                    const c = existingClients.find(c => c.id === Number(e.target.value));
                    if (c) startNewChat(c.client_type === "individual" ? "individual" : "corporate", c);
                  }}
                  className="w-full px-2 py-2 border rounded-lg text-[12px] focus:ring-2 focus:ring-violet-300 outline-none"
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
              {[
                { view: "chat" as ActiveView, icon: "💬", label: "상담", active: activeView === "chat" },
                { view: "clients" as ActiveView, icon: "👥", label: "고객 관리", active: activeView === "clients" },
                { view: "history" as ActiveView, icon: "📋", label: "상담 이력", active: activeView === "history" },
                { view: "reports" as ActiveView, icon: "📊", label: "보고서", active: activeView === "reports" },
              ].map(item => (
                <button
                  key={item.view}
                  onClick={() => { setActiveView(item.view); setLeftOpen(false); }}
                  className={`w-full px-4 py-2.5 flex items-center gap-3 text-left transition-all ${
                    item.active
                      ? dark ? "bg-violet-900/30 text-violet-300 border-r-2 border-violet-500" : "bg-violet-50 text-violet-700 border-r-2 border-violet-600"
                      : dark ? "text-slate-400 hover:bg-white/5" : "text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  <span className="text-base">{item.icon}</span>
                  <span className="text-[13px] font-semibold">{item.label}</span>
                </button>
              ))}
            </div>

            {/* 연동 서비스 */}
            <div className={`p-3 border-t hidden lg:block ${dark ? "border-white/10" : "border-slate-200"}`}>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">연동 서비스</p>
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 px-2 py-1.5 bg-violet-50 rounded-lg text-[11px]">
                  <span>🏛</span><span className="font-semibold text-violet-700">GovMatch</span><span className="text-emerald-500 text-[9px] ml-auto">연동됨</span>
                </div>
                <div className="flex items-center gap-2 px-2 py-1.5 bg-slate-50 rounded-lg text-[11px]">
                  <span>📄</span><span className="font-semibold text-slate-500">SmartDoc</span><span className="text-slate-400 text-[9px] ml-auto">준비 중</span>
                </div>
                <div className="flex items-center gap-2 px-2 py-1.5 bg-slate-50 rounded-lg text-[11px]">
                  <span>🧠</span><span className="font-semibold text-slate-500">AI Expert</span><span className="text-slate-400 text-[9px] ml-auto">준비 중</span>
                </div>
              </div>
            </div>
          </div>
        </nav>

        {/* ═══ 중앙 메인 ═══ */}
        <div className={`flex flex-col overflow-hidden ${dark ? "bg-[#1e1f33]" : "bg-white"}`}>
          {activeView === "chat" ? (
            <>
              {/* 유형 선택 (상담 미시작) */}
              {!clientCategory && messages.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center px-6 overflow-y-auto">
                  <div className="max-w-md text-center">
                    <div className="w-16 h-16 mx-auto mb-4 bg-violet-100 rounded-2xl flex items-center justify-center">
                      <span className="text-3xl">✨</span>
                    </div>
                    <h2 className="text-xl font-bold text-slate-800 mb-2">새 상담을 시작하세요</h2>
                    <p className="text-[13px] text-slate-500 mb-6">고객 유형을 선택하면 AI 상담이 시작됩니다</p>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { key: "individual_biz" as ClientCategory, label: "개인사업자", icon: "🏪", desc: "1인 사업자, 프리랜서" },
                        { key: "corporate" as ClientCategory, label: "법인사업자", icon: "🏢", desc: "법인 기업" },
                        { key: "individual" as ClientCategory, label: "개인", icon: "👤", desc: "취업·복지·주거" },
                        { key: "unknown" as ClientCategory, label: "모름", icon: "💬", desc: "AI가 대화로 파악" },
                      ].map(opt => (
                        <button key={opt.key} onClick={() => startNewChat(opt.key)}
                          className={`p-4 rounded-xl border-2 transition-all text-left active:scale-[0.98] ${dark ? "border-white/10 hover:border-violet-500 hover:bg-violet-900/20" : "border-slate-200 hover:border-violet-400 hover:bg-violet-50"}`}>
                          <span className="text-2xl">{opt.icon}</span>
                          <p className="text-[13px] font-bold text-slate-800 mt-2">{opt.label}</p>
                          <p className="text-[10px] text-slate-400 mt-0.5">{opt.desc}</p>
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
                        <div className={`max-w-[80%]`}>
                          <div className={`px-4 py-3 rounded-2xl text-[13px] leading-relaxed ${
                            msg.role === "user"
                              ? "bg-violet-600 text-white rounded-br-md"
                              : dark ? "bg-[#252640] text-slate-200 rounded-bl-md" : "bg-slate-100 text-slate-800 rounded-bl-md"
                          }`} dangerouslySetInnerHTML={{ __html: renderText(msg.text) }} />
                          {/* 선택지 */}
                          {msg.role === "assistant" && msg.choices && msg.choices.length > 0 && i === messages.length - 1 && !loading && (
                            <div className="flex flex-wrap gap-2 mt-2">
                              {msg.choices.map((choice, ci) => (
                                <button key={ci} onClick={() => handleSend(choice)}
                                  className="px-3 py-1.5 bg-white border border-violet-200 text-violet-700 rounded-full text-[12px] font-semibold hover:bg-violet-50 hover:border-violet-400 transition-all active:scale-95">
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
                        <div className="px-4 py-3 bg-slate-100 rounded-2xl rounded-bl-md">
                          <div className="flex gap-1.5">
                            <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                            <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                            <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                          </div>
                        </div>
                      </div>
                    )}
                    {/* 인라인 입력 위젯 — AI 질문에 따라 자동 표시 */}
                    {!loading && messages.length > 0 && messages[messages.length - 1].role === "assistant" && (() => {
                      const lastText = messages[messages.length - 1].text.toLowerCase();
                      const fields: { key: string; label: string; type: "text" | "select" | "date"; options?: string[] }[] = [];

                      if (lastText.includes("설립일") || lastText.includes("생년월일")) fields.push({ key: "date", label: "설립일/생년월일", type: "date" });
                      if (lastText.includes("직원") || lastText.includes("인원")) fields.push({ key: "emp", label: "직원수", type: "select", options: ["5인 미만", "5~10인", "10~30인", "30~50인", "50인 이상"] });
                      if (lastText.includes("매출")) fields.push({ key: "rev", label: "매출 규모", type: "select", options: ["1억 미만", "1억~5억", "5억~10억", "10억~50억", "50억 이상"] });
                      if (lastText.includes("업종") || lastText.includes("분야") || lastText.includes("관심")) fields.push({ key: "interest", label: lastText.includes("업종") ? "업종" : "관심분야", type: "text" });
                      if (lastText.includes("지역") || lastText.includes("소재지") || lastText.includes("거주")) fields.push({ key: "city", label: "지역", type: "select", options: ["서울", "경기", "부산", "인천", "대구", "대전", "광주", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"] });
                      if (lastText.includes("기업명") || lastText.includes("이름")) fields.push({ key: "name", label: lastText.includes("기업명") ? "기업명" : "이름", type: "text" });

                      if (fields.length === 0) return null;
                      return (
                        <InlineInputWidget fields={fields} dark={dark} onSubmit={(values) => {
                          const text = Object.entries(values).filter(([, v]) => v).map(([, v]) => v).join(", ");
                          if (text) handleSend(text);
                        }} />
                      );
                    })()}
                  </div>

                  {/* 입력 영역 */}
                  <div className={`flex-shrink-0 border-t px-4 py-3 ${dark ? "border-white/10 bg-[#1a1b2e]" : "border-slate-200 bg-white"}`}
                    onDragOver={(e) => { e.preventDefault(); e.currentTarget.style.background = "#f5f3ff"; }}
                    onDragLeave={(e) => { e.currentTarget.style.background = ""; }}
                    onDrop={async (e) => { e.preventDefault(); e.currentTarget.style.background = ""; const f = e.dataTransfer.files?.[0]; if (f) await handleFileAttach(f); }}
                  >
                    <div className="flex items-center gap-2">
                      <label className="p-2.5 text-violet-500 hover:text-violet-700 hover:bg-violet-50 rounded-xl cursor-pointer transition-all flex-shrink-0" title="자료 첨부">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
                        </svg>
                        <input type="file" className="hidden" accept=".pdf,.hwp,.hwpx,.docx,.doc,.xlsx,.txt"
                          onChange={async (e) => { const f = e.target.files?.[0]; if (f) await handleFileAttach(f); e.target.value = ""; }} />
                      </label>
                      <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) { e.preventDefault(); handleSend(input); } }}
                        placeholder="고객 정보를 입력하거나 질문하세요..."
                        disabled={loading}
                        className={`flex-1 px-4 py-2.5 rounded-xl text-[14px] outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-300 transition-all disabled:opacity-50 ${dark ? "bg-[#252640] border border-white/10 text-slate-200 placeholder-slate-500" : "bg-slate-50 border border-slate-200 text-slate-700 placeholder-slate-400"}`}
                      />
                      <button
                        onClick={() => handleSend(input)}
                        disabled={loading || !input.trim()}
                        className="p-2.5 bg-violet-600 text-white rounded-xl hover:bg-violet-700 transition-all active:scale-95 disabled:opacity-40 flex-shrink-0"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </>
              )}
            </>
          ) : (
            /* 고객관리 / 상담이력 / 보고서 — ProDashboard 서브컴포넌트 재사용 */
            <div className="flex-1 overflow-y-auto p-4">
              {activeView === "clients" && (
                <ClientsTabWrapper headers={headers} toast={toast} />
              )}
              {activeView === "history" && (
                <HistoryTabWrapper headers={headers} toast={toast} />
              )}
              {activeView === "reports" && (
                <ReportsTabWrapper headers={headers} toast={toast} />
              )}
            </div>
          )}
        </div>

        {/* ═══ 우측 컨텍스트 패널 ═══ */}
        <aside className={`${rightOpen ? "fixed right-0 top-0 h-full z-50 w-[280px] shadow-2xl" : "hidden lg:flex"} lg:flex flex-col overflow-y-auto ${dark ? "bg-[#151625] border-l border-white/10" : "bg-slate-50 border-l border-slate-200 shadow-sm"}`}>
          {rightOpen && <button onClick={() => setRightOpen(false)} className="lg:hidden self-end p-2 m-2 text-slate-400">✕</button>}

          {/* 상담 플로우 */}
          <div className={`p-3 border-b ${dark ? "border-white/10" : "border-slate-200"}`}>
            <p className={`text-[10px] font-bold uppercase tracking-wider mb-2 ${dark ? "text-slate-500" : "text-slate-400"}`}>상담 플로우</p>
            <div className="space-y-1">
              {flowSteps.map((step, i) => (
                <div key={step.key} className={`flex items-center gap-2 py-1.5 px-2 rounded-lg text-[11px] ${
                  flowState === step.key ? "bg-violet-100 text-violet-700 font-bold" :
                  flowSteps.findIndex(s => s.key === flowState) > i ? "text-emerald-600" : "text-slate-400"
                }`}>
                  <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center text-[8px] ${
                    flowState === step.key ? "border-violet-500 bg-violet-500 text-white" :
                    flowSteps.findIndex(s => s.key === flowState) > i ? "border-emerald-500 bg-emerald-500 text-white" : "border-slate-300"
                  }`}>
                    {flowSteps.findIndex(s => s.key === flowState) > i ? "✓" : ""}
                  </div>
                  {step.label}
                </div>
              ))}
            </div>
          </div>

          {/* 현재 고객 정보 */}
          {selectedClient && (
            <div className="p-3 border-b border-slate-100">
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">현재 고객</p>
              <div className="space-y-1 text-[11px]">
                <p className="font-bold text-slate-700">{selectedClient.client_name}</p>
                <p className="text-slate-500">{selectedClient.address_city || ""} · {selectedClient.industry_name || ""}</p>
                {selectedClient.contact_name && <p className="text-slate-400">{selectedClient.contact_name} · {selectedClient.contact_email || ""}</p>}
              </div>
            </div>
          )}

          {/* 자료 첨부 */}
          <div className="p-3 border-b border-slate-100">
            <p className="text-[10px] font-bold text-violet-600 uppercase tracking-wider mb-1">📎 자료 첨부</p>
            <p className="text-[10px] text-slate-400 mb-3">재무제표, 사업계획서 등을 첨부하면 AI가 분석합니다</p>
            <label
              className={`block w-full min-h-[120px] flex flex-col items-center justify-center border-2 border-dashed rounded-xl cursor-pointer transition-all ${dark ? "border-violet-500/50 bg-[#1e1f33] hover:bg-violet-900/20" : "border-violet-300 bg-white hover:bg-violet-50"}`}
              onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("bg-violet-100"); }}
              onDragLeave={(e) => { e.currentTarget.classList.remove("bg-violet-100"); }}
              onDrop={async (e) => { e.preventDefault(); e.currentTarget.classList.remove("bg-violet-100"); const f = e.dataTransfer.files?.[0]; if (f) await handleFileAttach(f); }}
            >
              <span className="text-2xl mb-1">📄</span>
              <p className="text-[11px] font-bold text-violet-600">드래그 또는 클릭</p>
              <p className="text-[9px] text-slate-400">PDF, HWP, DOCX (10MB)</p>
              <input type="file" className="hidden" accept=".pdf,.hwp,.hwpx,.docx,.doc,.xlsx,.txt"
                onChange={async (e) => { const f = e.target.files?.[0]; if (f) await handleFileAttach(f); e.target.value = ""; }} />
            </label>
          </div>

          {/* 연동 서비스 (모바일용) */}
          <div className="p-3 lg:hidden">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">연동 서비스</p>
            <div className="space-y-1.5 text-[11px]">
              <div className="flex items-center gap-2 px-2 py-1.5 bg-violet-50 rounded-lg">
                <span>🏛</span><span className="font-semibold text-violet-700">GovMatch</span><span className="text-emerald-500 text-[9px] ml-auto">연동됨</span>
              </div>
              <div className="flex items-center gap-2 px-2 py-1.5 bg-slate-50 rounded-lg">
                <span>📄</span><span className="font-semibold text-slate-500">SmartDoc</span><span className="text-slate-400 text-[9px] ml-auto">준비 중</span>
              </div>
              <div className="flex items-center gap-2 px-2 py-1.5 bg-slate-50 rounded-lg">
                <span>🧠</span><span className="font-semibold text-slate-500">AI Expert</span><span className="text-slate-400 text-[9px] ml-auto">준비 중</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

// ─── ProDashboard 서브컴포넌트 래퍼 ───
function ClientsTabWrapper({ headers, toast }: { headers: () => any; toast: any }) {
  const { ClientsTab } = require("@/components/ProDashboard");
  return <ClientsTab headers={headers} toast={toast} clientType="business" />;
}

function HistoryTabWrapper({ headers, toast }: { headers: () => any; toast: any }) {
  const { HistoryTab } = require("@/components/ProDashboard");
  return <HistoryTab headers={headers} toast={toast} />;
}

function ReportsTabWrapper({ headers, toast }: { headers: () => any; toast: any }) {
  const { ReportsTab } = require("@/components/ProDashboard");
  return <ReportsTab headers={headers} toast={toast} clientType="business" />;
}


// ─── 인라인 입력 위젯 ───
function InlineInputWidget({ fields, dark, onSubmit }: {
  fields: { key: string; label: string; type: "text" | "select" | "date"; options?: string[] }[];
  dark: boolean;
  onSubmit: (values: Record<string, string>) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});

  const update = (key: string, val: string) => setValues(prev => ({ ...prev, [key]: val }));

  const inputCls = `px-3 py-2 rounded-lg text-[13px] outline-none focus:ring-2 focus:ring-violet-300 transition-all ${
    dark ? "bg-[#252640] border border-white/10 text-slate-200" : "bg-white border border-slate-200 text-slate-700"
  }`;

  return (
    <div className={`mx-4 mb-3 p-3 rounded-xl border ${dark ? "bg-[#1e1f33] border-violet-500/30" : "bg-violet-50/50 border-violet-200"}`}>
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
        <button
          onClick={() => onSubmit(values)}
          disabled={Object.values(values).every(v => !v)}
          className="px-4 py-2 bg-violet-600 text-white rounded-lg text-[12px] font-bold hover:bg-violet-700 transition-all active:scale-95 disabled:opacity-40 self-end"
        >
          전송
        </button>
      </div>
    </div>
  );
}
