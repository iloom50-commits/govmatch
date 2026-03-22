"use client";

import { useState, useEffect } from "react";

interface Announcement {
  announcement_id: number;
  title: string;
}

export default function SmartDocModal() {
  const [open, setOpen] = useState(false);
  const [announcement, setAnnouncement] = useState<Announcement | null>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setAnnouncement(detail.announcement);
      setOpen(true);
    };
    window.addEventListener("open-smartdoc-modal", handler);
    return () => window.removeEventListener("open-smartdoc-modal", handler);
  }, []);

  if (!open || !announcement) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setOpen(false)} />

      <div className="relative w-full max-w-md bg-white rounded-[2rem] shadow-2xl border border-white/60 overflow-hidden animate-in zoom-in-95 duration-300">
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-violet-500/10 blur-[60px] rounded-full pointer-events-none" />
        <div className="absolute -bottom-20 -left-20 w-40 h-40 bg-indigo-500/10 blur-[60px] rounded-full pointer-events-none" />

        <div className="relative z-10 p-8">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-14 h-14 bg-gradient-to-br from-indigo-100 to-violet-100 rounded-2xl mb-4">
              <svg className="w-7 h-7 text-indigo-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6.23.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0 1 12 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
              </svg>
            </div>
            <h2 className="text-xl font-black text-slate-900 tracking-tight mb-1">
              AI 신청서 자동 작성
            </h2>
            <p className="text-slate-500 text-xs font-medium leading-relaxed">
              AI가 공고 첨부 양식을 분석하고, 기업 정보를 기반으로<br />
              맞춤 신청서 초안을 자동 생성합니다.
            </p>
          </div>

          {/* 공고 정보 */}
          <div className="bg-slate-50 rounded-xl p-4 mb-5 border border-slate-100">
            <span className="text-[11px] font-black text-slate-400 uppercase tracking-widest">대상 공고</span>
            <p className="text-sm font-bold text-slate-900 mt-1 leading-snug">{announcement.title}</p>
          </div>

          {/* 기능 설명 */}
          <div className="space-y-3 mb-6">
            {[
              { icon: "1", label: "공고 첨부 양식 다운로드", desc: "공고문의 신청서 양식 PDF/HWP를 자동 수집" },
              { icon: "2", label: "AI 양식 분석 및 학습", desc: "정부사업 특화 AI가 양식 구조와 요구사항을 파악" },
              { icon: "3", label: "기업 정보 기반 자동 작성", desc: "등록된 프로필 + 학습된 합격 패턴으로 초안 완성" },
              { icon: "4", label: "DOCX 다운로드", desc: "수정 가능한 문서 파일로 바로 제출" },
            ].map((step) => (
              <div key={step.icon} className="flex items-start gap-3">
                <div className="w-6 h-6 bg-indigo-600 text-white rounded-lg flex items-center justify-center text-[11px] font-black flex-shrink-0 mt-0.5">
                  {step.icon}
                </div>
                <div>
                  <p className="text-xs font-black text-slate-900">{step.label}</p>
                  <p className="text-[11px] text-slate-500 font-medium">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* CTA */}
          <button
            disabled
            className="w-full py-4 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-2xl font-black text-base shadow-xl shadow-indigo-200 transition-all flex items-center justify-center gap-2 opacity-70 cursor-not-allowed"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
            곧 출시 예정
          </button>

          <p className="text-[11px] text-slate-500 text-center mt-3 font-bold">
            SmartDoc 엔진 연동 후 서비스가 시작됩니다.
          </p>

          <button
            onClick={() => setOpen(false)}
            className="w-full mt-3 py-2 text-slate-400 hover:text-slate-600 text-xs font-black transition-all text-center"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
