"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useModalBack } from "@/hooks/useModalBack";
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

  // 2b) URL → 바로가기 링크 버튼
  html = html.replace(
    /(https?:\/\/[^\s<)"]+)/g,
    '<a href="$1" target="_blank" rel="noopener" class="inline-flex items-center gap-1 px-2 py-0.5 bg-indigo-50 text-indigo-600 text-[11px] font-bold rounded-md border border-indigo-200 hover:bg-indigo-100 transition-all no-underline break-all">'
    + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>'
    + '바로가기</a>'
  );

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

interface AiConsultModalProps {
  planStatus?: { plan: string } | null;
  onUpgrade?: () => void;
  onPlanUpdate?: (updated: any) => void;
}

export default function AiConsultModal({ planStatus, onUpgrade, onPlanUpdate }: AiConsultModalProps) {
  const isPro = planStatus && ["pro", "biz"].includes(planStatus.plan);
  const [open, setOpen] = useState(false);
  const [announcement, setAnnouncement] = useState<Announcement | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStartTime, setLoadingStartTime] = useState<number>(0);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [isDone, setIsDone] = useState(false);
  const [limitReached, setLimitReached] = useState(false);
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
        setLimitReached(false);
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

  // 프로그레시브 로딩 (단계별 진행바 + 메시지)
  useEffect(() => {
    if (!loading) {
      setLoadingProgress(0);
      setLoadingMessage("");
      return;
    }

    const steps = messages.length === 0
      ? [
          { at: 0, pct: 10, msg: "공고 원문을 가져오는 중..." },
          { at: 3000, pct: 25, msg: "첨부파일(PDF/HWP) 다운로드 중..." },
          { at: 8000, pct: 45, msg: "문서 내용을 추출하고 있습니다..." },
          { at: 15000, pct: 65, msg: "AI가 지원요건을 정리하고 있습니다..." },
          { at: 25000, pct: 80, msg: "분석 결과를 정리하는 중..." },
          { at: 35000, pct: 90, msg: "거의 다 됐어요! 잠시만요..." },
          { at: 50000, pct: 95, msg: "응답을 생성하고 있습니다..." },
        ]
      : [
          { at: 0, pct: 30, msg: "답변을 준비하고 있습니다..." },
          { at: 3000, pct: 60, msg: "AI가 분석 중..." },
          { at: 8000, pct: 85, msg: "거의 다 됐어요!" },
        ];

    // 즉시 첫 단계 적용
    setLoadingProgress(steps[0].pct);
    setLoadingMessage(steps[0].msg);

    const timers = steps.slice(1).map((step) =>
      setTimeout(() => {
        setLoadingProgress(step.pct);
        setLoadingMessage(step.msg);
      }, step.at)
    );

    return () => timers.forEach(clearTimeout);
  }, [loading, messages.length]);

  const sendToAI = useCallback(async (chatHistory: ChatMessage[]) => {
    if (!announcement) return;
    setLoading(true);
    setLoadingStartTime(Date.now());
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
        setLimitReached(true);
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
      const aiMsg: ChatMessage = {
        role: "assistant",
        text: data.reply || "응답을 처리할 수 없습니다.",
        choices: data.choices || [],
        done: data.done || false,
      };

      setMessages([...chatHistory, aiMsg]);
      // 사용량 갱신
      if (data.ai_used !== undefined) {
        onPlanUpdate?.({ ai_used: data.ai_used, consult_limit: data.ai_limit });
      }
      // AI가 done=true를 반환해도 자동 종료하지 않음 — 사용자가 직접 "상담 종료" 클릭
      if (data.consult_log_id) setConsultLogId(data.consult_log_id);
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

  const handleClose = useCallback(() => {
    setOpen(false);
    setMessages([]);
    setAnnouncement(null);
    setIsDone(false);
    setLimitReached(false);
    setFeedbackSent(false);
    setConsultLogId(null);
  }, []);

  // 모바일 뒤로가기 시 모달만 닫기 (앱 종료 방지)
  useModalBack(open, handleClose);

  // 사용자가 직접 상담 종료
  const handleManualEnd = () => {
    setIsDone(true);

    // 마지막 AI 메시지에서 결론 추출
    const lastAiMsg = [...messages].reverse().find(m => m.role === "assistant");
    const lastText = lastAiMsg?.text || "";

    // 결과를 이벤트로 발행 → 고객사 상담에서 수신 가능
    window.dispatchEvent(new CustomEvent("consult-result", {
      detail: {
        announcement_id: announcement?.announcement_id,
        title: announcement?.title,
        summary: lastText.substring(0, 500),
        consult_log_id: consultLogId,
      }
    }));

    setMessages(prev => [...prev, {
      role: "assistant" as const,
      text: "상담이 종료되었습니다.\n\n이 공고에 대해 다시 상담을 원하시면 공고 카드에서 **'나도 받을 수 있나?'**를 클릭하세요.",
      done: true,
    }]);
  };

  // 상담 보고서 인쇄 (PDF 저장 가능)
  const handlePrintReport = () => {
    const aiMessages = messages.filter(m => m.role === "assistant" && !m.done);
    const userMessages = messages.filter(m => m.role === "user");
    const now = new Date().toLocaleString("ko-KR");

    const html = `<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>상담 보고서 — ${announcement?.title || ""}</title>
<style>
  @page { margin: 20mm; }
  body { font-family: 'Pretendard', 'Apple SD Gothic Neo', sans-serif; color: #1e293b; line-height: 1.7; font-size: 13px; }
  h1 { font-size: 18px; color: #4f46e5; border-bottom: 2px solid #4f46e5; padding-bottom: 8px; margin-bottom: 16px; }
  .meta { color: #64748b; font-size: 12px; margin-bottom: 20px; }
  .meta span { margin-right: 16px; }
  .section { margin-bottom: 20px; }
  .section h2 { font-size: 14px; color: #334155; background: #f1f5f9; padding: 6px 12px; border-radius: 6px; margin-bottom: 8px; }
  .msg { margin-bottom: 12px; padding: 10px 14px; border-radius: 8px; }
  .msg.user { background: #eef2ff; border-left: 3px solid #6366f1; }
  .msg.ai { background: #f8fafc; border-left: 3px solid #10b981; }
  .msg .role { font-size: 11px; font-weight: bold; color: #64748b; margin-bottom: 4px; }
  .footer { margin-top: 30px; padding-top: 12px; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 11px; text-align: center; }
</style></head><body>
<h1>AI 지원대상 상담 보고서</h1>
<div class="meta">
  <span>공고: <strong>${announcement?.title || ""}</strong></span><br/>
  <span>부처: ${announcement?.department || "-"}</span>
  <span>카테고리: ${announcement?.category || "-"}</span>
  <span>마감: ${announcement?.deadline_date || "상시"}</span><br/>
  <span>상담일시: ${now}</span>
</div>
<div class="section"><h2>상담 내용</h2>
${messages.filter(m => !m.done).map(m => `<div class="msg ${m.role === "user" ? "user" : "ai"}">
  <div class="role">${m.role === "user" ? "질문" : "AI 상담사"}</div>
  <div>${m.role === "user" ? m.text.replace(/</g, "&lt;") : renderMarkdown(m.text)}</div>
</div>`).join("")}
</div>
<div class="footer">지원금AI — AI 맞춤 지원금 매칭 (govmatch.kr) | 본 보고서는 AI가 생성한 참고용 자료이며, 최종 판단은 주관기관의 심사에 따릅니다.</div>
</body></html>`;

    const printWindow = window.open("", "_blank");
    if (printWindow) {
      printWindow.document.write(html);
      printWindow.document.close();
      setTimeout(() => printWindow.print(), 500);
    }
  };

  if (!open || !announcement) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center lg:justify-end p-0 sm:p-4 lg:pr-6 lg:pointer-events-none">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm lg:hidden" onClick={handleClose} />

      <div
        data-consult-panel
        className={`bg-white shadow-2xl border border-white/60 overflow-hidden flex flex-col pointer-events-auto ${
          dragPos ? "fixed rounded-2xl" : "relative w-full sm:max-w-3xl lg:max-w-[820px] h-[90vh] sm:h-[88vh] sm:rounded-2xl animate-in slide-in-from-bottom sm:zoom-in-95 lg:slide-in-from-right duration-300"
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

          {/* 무료 상담 소진 안내 */}
          {limitReached && (
            <div className="flex justify-center my-4">
              <div className="w-full max-w-[300px] p-5 bg-gradient-to-b from-indigo-50 to-white rounded-2xl border border-indigo-100 text-center space-y-3">
                <div className="w-12 h-12 mx-auto bg-indigo-100 rounded-full flex items-center justify-center">
                  <span className="text-2xl">💬</span>
                </div>
                <p className="text-[14px] font-bold text-slate-800">무료 상담 3회를 모두 사용했어요</p>
                <div className="space-y-2 text-[12px]">
                  <div className="p-3 bg-white rounded-xl border border-indigo-100 text-left space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-indigo-700">LITE</span>
                      <span className="font-bold text-indigo-600 text-[11px]">4,900원/월</span>
                    </div>
                    <div className="space-y-0.5 text-[11px] text-slate-600">
                      <p>· AI 상담 <strong>월 10회</strong></p>
                      <p>· 맞춤 공고 알림 무제한</p>
                      <p>· 카카오톡/이메일 알림</p>
                    </div>
                  </div>
                  <div className="p-3 bg-white rounded-xl border border-violet-100 text-left space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-violet-700">PRO</span>
                      <span className="font-bold text-violet-600 text-[11px]">준비 중</span>
                    </div>
                    <div className="space-y-0.5 text-[11px] text-slate-600">
                      <p>· AI 상담 <strong>무제한</strong></p>
                      <p>· AI 신청서 자동작성 (준비 중)</p>
                      <p>· 전문가 1:1 매칭 상담</p>
                      <p>· 맞춤 공고 알림 무제한</p>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setOpen(false);
                    setLimitReached(false);
                    onUpgrade?.();
                  }}
                  className="w-full py-2.5 bg-indigo-600 text-white rounded-xl font-bold text-[13px] hover:bg-indigo-700 transition-all active:scale-[0.98]"
                >
                  플랜 보기
                </button>
                <button
                  onClick={() => { setOpen(false); setLimitReached(false); }}
                  className="text-[11px] text-slate-400 hover:text-slate-600 font-medium transition-all"
                >
                  나중에 하기
                </button>
              </div>
            </div>
          )}

          {/* Loading indicator — 프로그레스 바 + 단계별 메시지 */}
          {loading && (
            <div className="flex justify-start">
              <div className="w-full max-w-[280px] px-4 py-3.5 bg-slate-100 rounded-2xl rounded-bl-md space-y-2.5">
                <div className="flex items-center justify-between">
                  <p className="text-[12px] font-semibold text-indigo-600">{loadingMessage || "준비 중..."}</p>
                  <span className="text-[11px] font-bold text-indigo-400 tabular-nums">{loadingProgress}%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full transition-all duration-700 ease-out"
                    style={{ width: `${loadingProgress}%` }}
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="flex-shrink-0 border-t border-slate-100 bg-white px-3 py-3">
          {isDone ? (
            <div className="space-y-2">
              {/* 피드백 — PRO(전문 상담사)는 제외 */}
              {!isPro && !feedbackSent && consultLogId ? (
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
              ) : !isPro && feedbackSent ? (
                <p className="text-[11px] text-center text-slate-400">피드백이 저장되었습니다</p>
              ) : null}
              <div className="flex gap-2">
                <button
                  onClick={handlePrintReport}
                  className="flex-1 py-2.5 bg-emerald-600 text-white rounded-xl font-bold text-sm hover:bg-emerald-700 transition-all active:scale-[0.98] flex items-center justify-center gap-1.5"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
                  </svg>
                  보고서 출력
                </button>
                <button
                  onClick={handleClose}
                  className="flex-1 py-2.5 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all active:scale-[0.98]"
                >
                  닫기
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
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
              {/* 상담 중 종료 버튼 — 첫 AI 응답 이후 표시 */}
              {messages.length >= 2 && !loading && (
                <button
                  onClick={handleManualEnd}
                  className="w-full py-2 text-slate-400 hover:text-slate-600 text-[12px] font-semibold transition-all text-center hover:bg-slate-50 rounded-lg"
                >
                  상담 종료
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
