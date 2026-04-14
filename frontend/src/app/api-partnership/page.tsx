"use client";

import { useState, useRef, useEffect } from "react";
import { Metadata } from "next";

const API = process.env.NEXT_PUBLIC_API_URL;

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export default function ApiPartnershipPage() {
  // Chat state
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: "안녕하세요! 지원금AI API 제휴 상담입니다.\n\nAPI 요금, 제공 데이터, 연동 방법 등 궁금한 점을 물어보세요." },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Form state
  const [form, setForm] = useState({
    company_name: "",
    contact_name: "",
    email: "",
    phone: "",
    purpose: "",
    expected_volume: "",
    message: "",
  });
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
      const res = await fetch(`${API}/api/partnership/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMsg,
          history: chatMessages.slice(-6),
        }),
      });
      const data = await res.json();
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer || "응답을 받지 못했습니다." },
      ]);
    } catch {
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: "일시적 오류입니다. 잠시 후 다시 시도해주세요." },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const submitForm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.company_name || !form.email || !form.purpose) return;
    setFormLoading(true);
    try {
      const res = await fetch(`${API}/api/partnership/inquiry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (res.ok) {
        setFormSuccess(true);
      } else {
        alert(data.detail || "제출 실패");
      }
    } catch {
      alert("서버 오류가 발생했습니다.");
    } finally {
      setFormLoading(false);
    }
  };

  const apiFeatures = [
    "정부지원금/보조금/정책자금 공고 데이터 (기업+개인)",
    "AI 기반 자격요건 분석 및 조건 매칭",
    "공고 상세 정보 (자격요건, 제출서류, 신청방법 등)",
    "실시간 새 공고 알림 연동",
    "RESTful API (JSON) + Swagger 문서 제공",
    "사용량에 따른 맞춤 요금 협의",
  ];

  const inputClass = "w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400";

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Hero */}
      <section className="max-w-5xl mx-auto px-4 pt-16 pb-12 text-center">
        <div className="inline-block px-3 py-1 bg-indigo-100 text-indigo-700 text-xs font-bold rounded-full mb-4">
          API Partnership
        </div>
        <h1 className="text-3xl md:text-4xl font-black text-slate-900 tracking-tight mb-4">
          17,000+ 정부 지원금 데이터를<br />
          <span className="text-indigo-600">귀사 서비스에 연동하세요</span>
        </h1>
        <p className="text-slate-500 text-sm md:text-base max-w-2xl mx-auto mb-8">
          AI 기반 정부 지원금 매칭 엔진을 RESTful API로 제공합니다.
          핀테크, HR, ERP, 회계 등 다양한 서비스에 손쉽게 연동할 수 있습니다.
        </p>
        <div className="flex gap-3 justify-center">
          <a href="#plans" className="px-6 py-3 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all">
            요금제 보기
          </a>
          <button onClick={() => setChatOpen(true)} className="px-6 py-3 bg-white border-2 border-indigo-200 text-indigo-700 rounded-xl font-bold text-sm hover:bg-indigo-50 transition-all">
            AI 상담하기
          </button>
        </div>
      </section>

      {/* API Features */}
      <section className="max-w-5xl mx-auto px-4 pb-16">
        <h2 className="text-xl font-black text-slate-900 text-center mb-8">제공 API</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { icon: "📋", title: "공고 데이터", desc: "17,000+ 정부지원금/보조금/정책자금 공고. 매일 자동 업데이트." },
            { icon: "🤖", title: "AI 매칭", desc: "기업/개인 조건 입력 → 적합한 공고 자동 매칭. 매칭 점수 포함." },
            { icon: "📊", title: "상세 분석", desc: "자격요건, 제출서류, 신청방법, 선정기준 등 AI 구조화 분석 데이터." },
          ].map((f) => (
            <div key={f.title} className="bg-white rounded-2xl border border-slate-200 p-6 hover:shadow-lg transition-all">
              <div className="text-3xl mb-3">{f.icon}</div>
              <h3 className="font-bold text-slate-900 mb-2">{f.title}</h3>
              <p className="text-sm text-slate-500">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Use Cases */}
      <section className="bg-slate-50 py-16">
        <div className="max-w-5xl mx-auto px-4">
          <h2 className="text-xl font-black text-slate-900 text-center mb-8">활용 사례</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { biz: "핀테크/대출 플랫폼", use: "고객에게 '받을 수 있는 정부지원금' 자동 안내" },
              { biz: "HR/ERP 솔루션", use: "기업 고객별 매칭 가능한 지원금 표시" },
              { biz: "회계/세무 사무소", use: "고객사별 지원금 자동 매칭 리포트" },
              { biz: "블로그/미디어", use: "공고 기반 SEO 콘텐츠 자동 생성" },
            ].map((c) => (
              <div key={c.biz} className="bg-white rounded-xl border border-slate-200 p-5">
                <p className="font-bold text-slate-800 text-sm">{c.biz}</p>
                <p className="text-xs text-slate-500 mt-1">{c.use}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* API 제공 항목 + 문의 안내 */}
      <section id="plans" className="max-w-5xl mx-auto px-4 py-16">
        <h2 className="text-xl font-black text-slate-900 text-center mb-2">API 제공 항목</h2>
        <p className="text-sm text-slate-500 text-center mb-8">사용량과 요구사항에 따라 맞춤 요금을 안내드립니다</p>
        <div className="max-w-2xl mx-auto bg-white rounded-2xl border border-indigo-200 overflow-hidden">
          <div className="bg-indigo-50 px-6 py-4 border-b border-indigo-200">
            <p className="font-bold text-indigo-700">제공 기능</p>
          </div>
          <div className="px-6 py-5 space-y-3">
            {apiFeatures.map((f) => (
              <div key={f} className="flex items-center gap-3 text-sm">
                <span className="text-indigo-500 text-base">&#10003;</span>
                <span className="text-slate-700">{f}</span>
              </div>
            ))}
          </div>
          <div className="bg-slate-50 px-6 py-4 border-t border-slate-200 text-center">
            <p className="text-xs text-slate-500 mb-3">무료 테스트 API Key 발급 가능 | 사용량에 따른 맞춤 요금 협의</p>
            <a href="#contact" className="inline-block px-6 py-2.5 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all">
              제휴 문의하기
            </a>
          </div>
        </div>
      </section>

      {/* Contact Form */}
      <section id="contact" className="bg-slate-50 py-16">
        <div className="max-w-2xl mx-auto px-4">
          <h2 className="text-xl font-black text-slate-900 text-center mb-2">제휴 문의</h2>
          <p className="text-sm text-slate-500 text-center mb-8">문의를 남겨주시면 담당자가 빠르게 연락드립니다</p>

          {formSuccess ? (
            <div className="bg-white rounded-2xl border border-emerald-200 p-8 text-center">
              <div className="text-4xl mb-4">&#10003;</div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">문의가 접수되었습니다</h3>
              <p className="text-sm text-slate-500">담당자가 1영업일 이내 연락드리겠습니다.</p>
            </div>
          ) : (
            <form onSubmit={submitForm} className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-bold text-slate-500 mb-1 block">회사명 *</label>
                  <input className={inputClass} required value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} placeholder="(주)회사명" />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 mb-1 block">담당자명 *</label>
                  <input className={inputClass} required value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} placeholder="홍길동" />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-bold text-slate-500 mb-1 block">이메일 *</label>
                  <input className={inputClass} type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="partner@company.com" />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 mb-1 block">전화번호</label>
                  <input className={inputClass} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="010-1234-5678" />
                </div>
              </div>
              <div>
                <label className="text-xs font-bold text-slate-500 mb-1 block">활용 목적 *</label>
                <select className={inputClass} required value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })}>
                  <option value="">선택해주세요</option>
                  <option value="핀테크/금융">핀테크/금융 서비스 연동</option>
                  <option value="HR/ERP">HR/ERP 솔루션 연동</option>
                  <option value="회계/세무">회계/세무 서비스 연동</option>
                  <option value="미디어/콘텐츠">미디어/콘텐츠 활용</option>
                  <option value="공공기관">공공기관/지자체 연동</option>
                  <option value="기타">기타</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-bold text-slate-500 mb-1 block">예상 사용량</label>
                <select className={inputClass} value={form.expected_volume} onChange={(e) => setForm({ ...form, expected_volume: e.target.value })}>
                  <option value="">선택해주세요</option>
                  <option value="일 100건 이하">일 100건 이하 (Free)</option>
                  <option value="일 1,000건 이하">일 1,000건 이하 (Basic)</option>
                  <option value="일 1,000건 이상">일 1,000건 이상 (Pro)</option>
                  <option value="대규모/맞춤">대규모/맞춤 (Enterprise)</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-bold text-slate-500 mb-1 block">추가 메시지</label>
                <textarea className={`${inputClass} h-24 resize-none`} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} placeholder="추가로 전달할 내용이 있으면 입력해주세요" />
              </div>
              <button type="submit" disabled={formLoading} className="w-full py-3 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all disabled:opacity-50">
                {formLoading ? "제출 중..." : "제휴 문의 보내기"}
              </button>
            </form>
          )}
        </div>
      </section>

      {/* Footer link */}
      <div className="text-center py-8">
        <a href="/" className="text-sm text-indigo-600 font-bold hover:underline">
          ← 지원금AI 서비스로 돌아가기
        </a>
      </div>

      {/* Chat Toggle Button */}
      {!chatOpen && (
        <button
          onClick={() => setChatOpen(true)}
          className="fixed bottom-6 right-6 w-14 h-14 bg-indigo-600 text-white rounded-full shadow-xl hover:bg-indigo-700 transition-all flex items-center justify-center text-xl z-50"
          title="AI 제휴 상담"
        >
          💬
        </button>
      )}

      {/* Chat Panel */}
      {chatOpen && (
        <div className="fixed bottom-6 right-6 w-[360px] max-h-[500px] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col z-50 animate-in slide-in-from-bottom-4 duration-300">
          {/* Header */}
          <div className="bg-indigo-600 text-white px-4 py-3 rounded-t-2xl flex items-center justify-between">
            <div>
              <p className="font-bold text-sm">API 제휴 상담</p>
              <p className="text-[10px] text-indigo-200">AI가 실시간으로 답변드립니다</p>
            </div>
            <button onClick={() => setChatOpen(false)} className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-indigo-500 text-sm">
              ✕
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-[320px]">
            {chatMessages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] px-3.5 py-2.5 rounded-xl text-[14px] leading-relaxed whitespace-pre-wrap ${
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
                <div className="bg-slate-100 text-slate-400 px-3 py-2 rounded-xl rounded-bl-none text-xs">
                  답변 작성 중...
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="border-t border-slate-200 p-3 flex gap-2">
            <input
              className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-xs outline-none focus:ring-1 focus:ring-indigo-300"
              placeholder="질문을 입력하세요..."
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
      )}
    </main>
  );
}
