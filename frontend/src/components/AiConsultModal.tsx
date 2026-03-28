"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useToast } from "@/components/ui/Toast";
import DOMPurify from "dompurify";

const API = process.env.NEXT_PUBLIC_API_URL;

/** 마크다운 → 보고서 스타일 HTML 변환 */
function renderMarkdown(text: string): string {
  // 0) (None) 링크 패턴 제거: ([텍스트](None)) or [텍스트](None)
  text = text.replace(/\(\[.*?\]\(None\)\)/g, "").replace(/\[.*?\]\(None\)/g, "");

  // 1) 이스케이프
  let html = text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // 2) 인라인: bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="text-slate-900 font-semibold">$1</strong>');

  const lines = html.split("\n");
  const result: string[] = [];
  let listType: "ul" | "ol" | null = null;

  const closeList = () => {
    if (listType) { result.push(listType === "ol" ? "</ol>" : "</ul>"); listType = null; }
  };

  for (const line of lines) {
    const trimmed = line.trim();

    // 번호 리스트
    const olMatch = trimmed.match(/^(\d+)[.\)]\s+(.*)/);
    // 불릿 리스트
    const ulMatch = !olMatch && trimmed.match(/^[*\-•]\s+(.*)/);

    if (olMatch) {
      if (listType !== "ol") { closeList(); result.push('<ol class="ml-4 mt-2 mb-2 space-y-1.5 list-decimal list-outside">'); listType = "ol"; }
      result.push(`<li class="text-slate-700 leading-relaxed">${olMatch[2]}</li>`);
    } else if (ulMatch) {
      if (listType !== "ul") { closeList(); result.push('<ul class="ml-4 mt-1 mb-1 space-y-1 list-disc list-outside">'); listType = "ul"; }
      result.push(`<li class="text-slate-700 leading-relaxed">${ulMatch[1]}</li>`);
    } else {
      closeList();
      // 섹션 제목
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

interface Announcement {
  announcement_id: number;
  title: string;
  support_amount?: string;
  deadline_date?: string;
  department?: string;
  category?: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  choices?: string[];
  done?: boolean;
}

export default function AiConsultModal() {
  const [open, setOpen] = useState(false);
  const [announcement, setAnnouncement] = useState<Announcement | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [consultLogId, setConsultLogId] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // 드래그 이동
  const [dragPos, setDragPos] = useState<{ x: number; y: number } | null>(null);
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    const panel = e.currentTarget.closest("[data-consult-panel]") as HTMLElement;
    if (!panel) return;
    const rect = panel.getBoundingClientRect();
    dragRef.current = { startX: e.clientX, startY: e.clientY, origX: rect.left, origY: rect.top };
    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      setDragPos({
        x: dragRef.current.origX + ev.clientX - dragRef.current.startX,
        y: dragRef.current.origY + ev.clientY - dragRef.current.startY,
      });
    };
    const onUp = () => {
      dragRef.current = null;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, []);
  const { toast } = useToast();

  // 이벤트 리스너
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.announcement) {
        setAnnouncement(detail.announcement);
        setMessages([]);
        setInput("");
        setIsDone(false);
        setFeedbackSent(false);
        setConsultLogId(null);
        setDragPos(null);
        setOpen(true);
      }
    };
    window.addEventListener("open-ai-consult", handler);
    return () => window.removeEventListener("open-ai-consult", handler);
  }, []);

  // 모달 열리면 첫 AI 메시지 요청
  useEffect(() => {
    if (open && announcement && messages.length === 0) {
      sendToAI([{ role: "user", text: "이 공고에 대해 상담을 시작합니다." }]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, announcement]);

  // 스크롤 하단 유지
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const sendToAI = useCallback(async (chatHistory: ChatMessage[]) => {
    if (!announcement) return;
    setLoading(true);
    const token = localStorage.getItem("auth_token");

    try {
      const res = await fetch(`${API}/api/ai/consult`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          announcement_id: announcement.announcement_id,
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
        done: data.done || false,
      };

      setMessages([...chatHistory, aiMsg]);
      if (data.done) {
        setIsDone(true);
        if (data.consult_log_id) setConsultLogId(data.consult_log_id);
      }
    } catch {
      toast("서버 연결에 실패했습니다.", "error");
    }
    setLoading(false);
  }, [announcement, toast]);

  const handleSend = (text: string) => {
    if (!text.trim() || loading || isDone) return;
    const userMsg: ChatMessage = { role: "user", text: text.trim() };
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInput("");
    sendToAI(newHistory);
  };

  const sendFeedback = async (feedback: "helpful" | "inaccurate") => {
    if (!consultLogId || feedbackSent) return;
    const token = localStorage.getItem("auth_token");
    try {
      await fetch(`${API}/api/ai/consult/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ consult_log_id: consultLogId, feedback }),
      });
      setFeedbackSent(true);
      toast(feedback === "helpful" ? "감사합니다! 피드백이 반영되었습니다." : "피드백이 저장되었습니다. 더 나은 상담을 위해 개선하겠습니다.", "success");
    } catch {
      toast("피드백 전송에 실패했습니다.", "error");
    }
  };

  const handleClose = () => {
    setOpen(false);
    setMessages([]);
    setAnnouncement(null);
    setIsDone(false);
    setFeedbackSent(false);
    setConsultLogId(null);
  };

  if (!open || !announcement) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 lg:pointer-events-none">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm lg:hidden" onClick={handleClose} />

      <div
        data-consult-panel
        className={`bg-white shadow-2xl border border-white/60 overflow-hidden flex flex-col pointer-events-auto ${
          dragPos ? "fixed rounded-2xl" : "relative w-full sm:max-w-4xl h-[90vh] sm:h-[85vh] sm:rounded-2xl animate-in slide-in-from-bottom sm:zoom-in-95 duration-300"
        }`}
        style={dragPos ? { left: dragPos.x, top: dragPos.y, width: 700, height: "80vh", zIndex: 60, borderRadius: 16 } : undefined}
      >

        {/* Header — 드래그 핸들 */}
        <div
          className="relative z-10 px-4 py-3 border-b border-slate-100 bg-gradient-to-r from-indigo-50 to-violet-50 flex-shrink-0 cursor-grab active:cursor-grabbing select-none"
          onMouseDown={handleDragStart}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-bold text-indigo-700 truncate">AI 지원대상 상담</p>
                <p className="text-[11px] text-slate-500 font-medium truncate">{announcement.title}</p>
              </div>
            </div>
            <button onClick={handleClose} className="p-1.5 hover:bg-white/60 rounded-lg transition-all flex-shrink-0">
              <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Chat area */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`${msg.role === "user" ? "max-w-[75%] order-1" : "max-w-[95%]"}`}>
                {/* Message bubble */}
                <div className={`rounded-2xl text-[13px] leading-relaxed ${
                  msg.role === "user"
                    ? "px-3.5 py-2.5 bg-indigo-600 text-white rounded-br-md"
                    : "px-4 py-3 bg-slate-50 border border-slate-200 text-slate-800 rounded-bl-md"
                }`}>
                  {msg.role === "user" ? msg.text : (
                    <div className="prose-sm" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(renderMarkdown(msg.text)) }} />
                  )}
                </div>

                {/* Choice buttons (AI messages only) */}
                {msg.role === "assistant" && msg.choices && msg.choices.length > 0 && i === messages.length - 1 && !isDone && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {msg.choices.map((choice, ci) => (
                      <button
                        key={ci}
                        onClick={() => handleSend(choice)}
                        disabled={loading}
                        className="px-3 py-1.5 bg-white border border-indigo-200 text-indigo-700 rounded-full text-[11px] font-semibold hover:bg-indigo-50 hover:border-indigo-300 transition-all active:scale-95 disabled:opacity-50"
                      >
                        {choice}
                      </button>
                    ))}
                  </div>
                )}

                {/* Done indicator */}
                {msg.role === "assistant" && msg.done && (
                  <div className="mt-2 px-3 py-1.5 bg-emerald-50 border border-emerald-200 rounded-lg">
                    <p className="text-[11px] font-bold text-emerald-700">상담 완료</p>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Loading indicator */}
          {loading && (
            <div className="flex justify-start">
              <div className="px-4 py-3 bg-slate-100 rounded-2xl rounded-bl-md">
                {messages.length === 0 ? (
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                      <p className="text-[12px] font-semibold text-indigo-600">공고문 분석 중...</p>
                    </div>
                    <p className="text-[11px] text-slate-400">첨부파일을 수집하고 정밀 분석하고 있습니다</p>
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="flex-shrink-0 border-t border-slate-100 bg-white px-3 py-3">
          {isDone ? (
            <div className="space-y-2">
              {!feedbackSent && consultLogId ? (
                <div className="space-y-2">
                  <p className="text-[11px] text-center text-slate-500 font-medium">상담이 도움이 되셨나요?</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => sendFeedback("helpful")}
                      className="flex-1 py-2 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-xl font-bold text-[12px] hover:bg-emerald-100 transition-all active:scale-[0.98]"
                    >
                      도움됐어요
                    </button>
                    <button
                      onClick={() => sendFeedback("inaccurate")}
                      className="flex-1 py-2 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl font-bold text-[12px] hover:bg-rose-100 transition-all active:scale-[0.98]"
                    >
                      부정확해요
                    </button>
                  </div>
                </div>
              ) : feedbackSent ? (
                <p className="text-[11px] text-center text-slate-400">피드백이 저장되었습니다</p>
              ) : null}
              <button
                onClick={handleClose}
                className="w-full py-2.5 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all active:scale-[0.98]"
              >
                상담 종료
              </button>
            </div>
          ) : (
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
                placeholder="질문을 입력하세요..."
                disabled={loading}
                className="flex-1 px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-[13px] text-slate-700 placeholder-slate-400 outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300 transition-all disabled:opacity-50"
              />
              <button
                onClick={() => handleSend(input)}
                disabled={loading || !input.trim()}
                className="p-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                </svg>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
