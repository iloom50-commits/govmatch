"use client";

import React from "react";

export default function ProUpsellScreen({
  onClose,
  onUpgrade,
}: {
  onClose: () => void;
  onUpgrade?: () => void;
}) {
  const features = [
    {
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-12.375 0c0 4.556 3.694 8.25 8.25 8.25 1.302 0 2.533-.302 3.63-.844l4.37 1.094-1.094-4.37A8.21 8.21 0 0020.25 12c0-4.556-3.694-8.25-8.25-8.25S3.75 7.444 3.75 12z" />
        </svg>
      ),
      title: "AI 컨설팅 어시스턴트",
      desc: "고객사 정보 입력 → 맞춤 매칭 → 자격 검토를 한 번에",
    },
    {
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
        </svg>
      ),
      title: "고객사 CRM",
      desc: "고객별 상담 이력, 자료 첨부, 일괄 이메일 발송",
    },
    {
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
      ),
      title: "특정 공고 정밀 분석",
      desc: "공고 검색 → DB 분석 데이터 활용 → 자격요건 자동 검토",
    },
    {
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
      ),
      title: "전문 컨설팅 보고서",
      desc: "TOP 10 추천 공고 + 신청 로드맵 + PDF 다운로드",
    },
    {
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
        </svg>
      ),
      title: "5종 전문가 AI 연동",
      desc: "SmartDoc · 노무 · 세무 · 법무 · 산업안전 AI",
    },
    {
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
      ),
      title: "멀티모달 자료 분석",
      desc: "PDF · DOCX · HWP · 이미지(OCR) · 음성(받아쓰기)",
    },
  ];

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="relative w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto bg-[#0d0e1a] text-slate-100 rounded-2xl shadow-2xl border border-violet-500/20"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 닫기 */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors z-10"
          aria-label="닫기"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* 헤더 */}
        <div className="px-6 sm:px-10 pt-10 pb-6 text-center bg-gradient-to-b from-violet-900/20 to-transparent">
          <div className="inline-flex items-center gap-2 px-3 py-1 mb-4 bg-violet-500/15 border border-violet-500/30 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
            <span className="text-[11px] font-bold text-violet-300">전문가용 지원사업 상담 도구</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-black mb-2 bg-gradient-to-r from-violet-300 to-purple-300 bg-clip-text text-transparent">
            지원사업 컨설턴트를 위한 PRO
          </h2>
          <p className="text-[13px] text-slate-400 leading-relaxed">
            혼자서 운영하는 1인 컨설팅부터 팀 운영까지<br className="hidden sm:block" />
            AI가 고객사 상담·매칭·보고서 작성을 함께합니다.
          </p>
        </div>

        {/* 기능 그리드 */}
        <div className="px-6 sm:px-10 py-2 grid grid-cols-1 sm:grid-cols-2 gap-3">
          {features.map((f, i) => (
            <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:border-violet-500/30 transition-colors">
              <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-violet-500/15 text-violet-300 flex items-center justify-center">
                {f.icon}
              </div>
              <div className="min-w-0">
                <p className="text-[13px] font-bold text-slate-100 mb-0.5">{f.title}</p>
                <p className="text-[11px] text-slate-400 leading-relaxed">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>

        {/* 가격 + CTA */}
        <div className="px-6 sm:px-10 py-6 mt-2">
          <div className="p-5 rounded-2xl bg-gradient-to-br from-violet-600/20 to-purple-600/10 border border-violet-500/30 text-center">
            <p className="text-[10px] font-bold text-red-400 mb-1">3개월 오픈 이벤트</p>
            <div className="flex items-baseline justify-center gap-2 mb-1">
              <span className="text-[14px] text-slate-500 line-through">₩49,000</span>
              <span className="text-3xl font-black text-white">₩29,000</span>
              <span className="text-[12px] text-slate-400">/ 월</span>
            </div>
            <p className="text-[11px] text-slate-400 mb-4">AI 상담 무제한 · 고객사 무제한 · 모든 기능 포함</p>
            <button
              onClick={() => {
                onClose();
                if (onUpgrade) onUpgrade();
              }}
              className="w-full py-3 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white rounded-xl text-[14px] font-bold transition-all active:scale-[0.98] shadow-lg shadow-violet-500/30"
            >
              PRO 시작하기 →
            </button>
            <p className="text-[10px] text-slate-500 mt-3">
              언제든 해지 가능 · 7일 무료 체험
            </p>
          </div>
        </div>

        <div className="px-6 sm:px-10 pb-6 text-center">
          <button
            onClick={onClose}
            className="text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
          >
            나중에 보기
          </button>
        </div>
      </div>
    </div>
  );
}
