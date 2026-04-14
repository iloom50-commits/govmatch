"use client";

import { useState, useRef, useEffect } from "react";

const API = process.env.NEXT_PUBLIC_API_URL;

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export default function SupportPage() {
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: "안녕하세요! 지원금AI 고객 상담입니다.\n\n서비스 이용, 매칭, 결제 등 궁금한 점을 물어보세요." },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const [form, setForm] = useState({ name: "", email: "", category: "", message: "" });
  const [formLoading, setFormLoading] = useState(false);
  const [formSuccess, setFormSuccess] = useState(false);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const sendChat = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const userMsg = chatInput.trim();
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setChatLoading(true);
    try {
      const res = await fetch(`${API}/api/support/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg, history: chatMessages.slice(-6) }),
      });
      const data = await res.json();
      setChatMessages((prev) => [...prev, { role: "assistant", content: data.answer || "응답을 받지 못했습니다." }]);
    } catch {
      setChatMessages((prev) => [...prev, { role: "assistant", content: "일시적 오류입니다. 잠시 후 다시 시도해주세요." }]);
    } finally {
      setChatLoading(false);
    }
  };

  const submitForm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name || !form.email || !form.message) return;
    setFormLoading(true);
    try {
      const res = await fetch(`${API}/api/support/inquiry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (res.ok) setFormSuccess(true);
      else alert("제출 실패. 잠시 후 다시 시도해주세요.");
    } catch {
      alert("서버 오류가 발생했습니다.");
    } finally {
      setFormLoading(false);
    }
  };

  const inputClass = "w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400";

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Hero */}
      <section className="max-w-4xl mx-auto px-4 pt-16 pb-8 text-center">
        <h1 className="text-3xl font-black text-slate-900 tracking-tight mb-3">고객 상담</h1>
        <p className="text-slate-500 text-sm">AI 챗봇으로 즉시 답변받거나, 문의 폼을 통해 담당자에게 연락하세요.</p>
      </section>

      <div className="max-w-4xl mx-auto px-4 pb-16 grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* AI 챗봇 */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col h-[500px]">
          <div className="bg-indigo-600 text-white px-5 py-3 rounded-t-2xl">
            <p className="font-bold text-sm">AI 상담</p>
            <p className="text-[10px] text-indigo-200">실시간 자동 응답</p>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {chatMessages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] px-3.5 py-2.5 rounded-xl text-[14px] leading-relaxed whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-indigo-600 text-white rounded-br-none"
                    : "bg-slate-100 text-slate-700 rounded-bl-none"
                }`}>
                  {msg.content}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-slate-100 text-slate-400 px-3 py-2 rounded-xl rounded-bl-none text-xs animate-pulse">
                  답변 작성 중...
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <div className="border-t border-slate-200 p-3 flex gap-2">
            <input
              className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-xs outline-none focus:ring-1 focus:ring-indigo-300"
              placeholder="궁금한 점을 입력하세요..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendChat()}
            />
            <button
              onClick={sendChat}
              disabled={chatLoading || !chatInput.trim()}
              className="px-3 py-2 bg-indigo-600 text-white rounded-lg text-xs font-bold hover:bg-indigo-700 disabled:opacity-50"
            >
              전송
            </button>
          </div>
        </div>

        {/* 문의 폼 */}
        <div>
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h2 className="font-bold text-slate-900 mb-1">문의하기</h2>
            <p className="text-xs text-slate-400 mb-5">AI 상담으로 해결이 어려운 경우 직접 문의해주세요</p>

            {formSuccess ? (
              <div className="text-center py-8">
                <div className="text-4xl mb-3">&#10003;</div>
                <h3 className="font-bold text-slate-900 mb-2">문의가 접수되었습니다</h3>
                <p className="text-xs text-slate-500">1영업일 이내 이메일로 답변드리겠습니다.</p>
              </div>
            ) : (
              <form onSubmit={submitForm} className="space-y-4">
                <div>
                  <label className="text-xs font-bold text-slate-500 mb-1 block">이름 *</label>
                  <input className={inputClass} required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="홍길동" />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 mb-1 block">이메일 *</label>
                  <input className={inputClass} type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="email@example.com" />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 mb-1 block">문의 유형</label>
                  <select className={inputClass} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                    <option value="">선택해주세요</option>
                    <option value="서비스 이용">서비스 이용 방법</option>
                    <option value="매칭/공고">매칭/공고 관련</option>
                    <option value="결제/환불">결제/환불</option>
                    <option value="계정/로그인">계정/로그인</option>
                    <option value="오류 신고">오류 신고</option>
                    <option value="기타">기타</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 mb-1 block">문의 내용 *</label>
                  <textarea className={`${inputClass} h-28 resize-none`} required value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} placeholder="문의 내용을 자세히 작성해주세요" />
                </div>
                <button type="submit" disabled={formLoading} className="w-full py-3 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all disabled:opacity-50">
                  {formLoading ? "제출 중..." : "문의 보내기"}
                </button>
              </form>
            )}
          </div>

          {/* FAQ */}
          <div className="mt-4 bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h3 className="font-bold text-slate-900 mb-3 text-sm">자주 묻는 질문</h3>
            <div className="space-y-3">
              {[
                { q: "회원가입은 어떻게 하나요?", a: "이메일 또는 카카오/네이버/구글 소셜 로그인으로 간편 가입 가능합니다." },
                { q: "매칭 결과가 없어요", a: "프로필 설정(지역, 업종, 매출 등)을 정확히 입력해주세요. 조건에 맞는 공고가 매칭됩니다." },
                { q: "유료 플랜 비용이 궁금해요", a: "Free(무료), Lite(개인 2,900원/사업자 4,900원), Pro(29,000원/월 이벤트가, 정상가 49,000원)입니다. 7일 무료 체험 후 자동결제됩니다." },
                { q: "환불은 어떻게 하나요?", a: "결제 후 7일 이내 전액 환불 가능합니다. 고객 상담으로 문의해주세요." },
              ].map((faq) => (
                <details key={faq.q} className="group">
                  <summary className="cursor-pointer text-xs font-medium text-slate-700 hover:text-indigo-600 transition-all">
                    {faq.q}
                  </summary>
                  <p className="text-[11px] text-slate-500 mt-1 ml-2">{faq.a}</p>
                </details>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Footer link */}
      <div className="text-center pb-8">
        <a href="/" className="text-sm text-indigo-600 font-bold hover:underline">
          ← 지원금AI 서비스로 돌아가기
        </a>
      </div>
    </main>
  );
}
