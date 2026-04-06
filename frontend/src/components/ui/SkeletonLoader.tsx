"use client";

import { useState, useEffect } from "react";

const MESSAGES = [
  { title: "AI가 구석구석 모든 지원금을 찾고 있어요", sub: "수만 건의 지원금 공고를 살펴보는 중..." },
  { title: "나에게 딱 맞는 지원금 찾는 중", sub: "조건에 맞는 공고를 골라내고 있어요" },
  { title: "거의 다 됐어요!", sub: "맞춤 결과를 정리하고 있어요" },
  { title: "조금만 더 기다려주세요", sub: "최적의 공고를 선별하고 있어요" },
];

const HIGHLIGHTS = [
  { num: "17,000+", label: "정부 지원금 공고", desc: "실시간 분석" },
  { num: "AI", label: "자동 매칭", desc: "내 조건에 딱 맞게" },
  { num: "24/7", label: "새 공고 알림", desc: "놓치지 않게" },
];

export default function SkeletonLoader() {
  const [msgIdx, setMsgIdx] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setMsgIdx(prev => (prev < MESSAGES.length - 1 ? prev + 1 : prev));
    }, 2500);
    return () => clearInterval(timer);
  }, []);

  const { title, sub } = MESSAGES[msgIdx];

  return (
    <div className="w-full max-w-md p-8 bg-white rounded-[2rem] shadow-2xl border border-indigo-50 animate-in fade-in zoom-in duration-500">
      <div className="flex flex-col items-center text-center">
        {/* 로봇 캐릭터 */}
        <div className="relative mb-6">
          <svg width="120" height="100" viewBox="0 0 70 60" fill="none" style={{ overflow: "visible", filter: "drop-shadow(0 4px 8px rgba(0,0,0,0.15))" }}>
            <path d="M 5 50 L 65 50" stroke="#06B6D4" strokeWidth="2" opacity="0.6" style={{ filter: "drop-shadow(0 0 4px #22D3EE)" }} />
            <path d="M 10 54 L 60 54" stroke="#06B6D4" strokeWidth="1" opacity="0.3" />
            <ellipse cx="20" cy="46" rx="10" ry="2" fill="#22D3EE" opacity="0.1" style={{ filter: "blur(2px)" }} />
            <path d="M 40 48 L 46 22 L 66 22 L 60 48 Z" fill="#0EA5E9" opacity="0.1" />
            <path d="M 40 48 L 46 22 L 66 22 L 60 48 Z" stroke="#22D3EE" strokeWidth="1" opacity="0.8" style={{ filter: "drop-shadow(0 0 2px #22D3EE)" }} />
            <g style={{ transform: "skewX(-13deg)" }}>
              <rect x="52" y="26" width="10" height="2" rx="1" fill="#22D3EE" opacity="0.9" style={{ animation: "codeLine 1.5s ease-in-out infinite" }} />
              <rect x="52" y="30" width="14" height="2" rx="1" fill="#67E8F9" opacity="0.7" style={{ animation: "codeLine 1.5s 0.3s ease-in-out infinite" }} />
              <rect x="52" y="34" width="8" height="2" rx="1" fill="#22D3EE" opacity="0.8" style={{ animation: "codeLine 1.5s 0.6s ease-in-out infinite" }} />
              <rect x="52" y="38" width="12" height="2" rx="1" fill="#BAE6FD" opacity="0.6" style={{ animation: "codeLine 1.5s 0.9s ease-in-out infinite" }} />
            </g>
            <line x1="22" y1="6" x2="22" y2="12" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" />
            <circle cx="22" cy="6" r="3" fill="#22D3EE" style={{ filter: "drop-shadow(0 0 4px #22D3EE)" }} className="animate-pulse" />
            <g style={{ transformOrigin: "22px 24px", animation: "headBob 2s ease-in-out infinite" }}>
              <path d="M12 20 C 12 14, 32 14, 32 20 L 34 28 C 34 32, 30 34, 22 34 C 14 34, 10 32, 10 28 Z" fill="#1E293B" stroke="#334155" strokeWidth="1" />
              <path d="M14 22 C 14 20, 30 20, 30 22 L 30 26 C 30 28, 14 28, 14 26 Z" fill="#0F172A" />
              <path d="M16 23 C 16 22, 28 22, 28 23 L 28 25 C 28 26, 16 26, 16 25 Z" fill="#22D3EE" opacity="0.8" style={{ filter: "drop-shadow(0 0 6px #06B6D4)" }} />
              <line x1="18" y1="24" x2="26" y2="24" stroke="white" strokeWidth="2" strokeDasharray="3 2" strokeLinecap="round" opacity="0.9" style={{ animation: "particleFade 1s infinite alternate" }} />
            </g>
            <path d="M16 38 L 28 38 L 30 46 C 30 48, 26 50, 22 50 C 18 50, 14 48, 14 46 Z" fill="#334155" stroke="#475569" strokeWidth="1" />
            <circle cx="22" cy="46" r="2" fill="#22D3EE" style={{ filter: "drop-shadow(0 0 2px #22D3EE)" }} />
            <path d="M 28 48 Q 36 46 44 48" stroke="#06B6D4" strokeWidth="2" fill="none" opacity="0.6" style={{ filter: "drop-shadow(0 0 3px #06B6D4)" }} />
            <g style={{ transformOrigin: "16px 40px", animation: "typingLeft 0.3s ease-in-out infinite alternate" }}>
              <path d="M16 40 C 12 40, 14 46, 28 47" stroke="#64748B" strokeWidth="3" fill="none" strokeLinecap="round" />
            </g>
            <g style={{ transformOrigin: "28px 40px", animation: "typingRight 0.3s 0.15s ease-in-out infinite alternate" }}>
              <path d="M28 40 C 32 40, 38 44, 38 47" stroke="#64748B" strokeWidth="3" fill="none" strokeLinecap="round" />
            </g>
          </svg>
        </div>

        {/* 핵심 가치 제안 */}
        <p className="text-base font-black text-slate-900 tracking-tight mb-1">
          AI가 구석구석 모든 지원금을 찾아서 알려 드립니다
        </p>
        <p className="text-xs text-slate-400 font-medium mb-6">
          내 조건에 딱 맞는 지원금 매칭 + 새 공고 알림까지, 무료!
        </p>

        {/* 핵심 수치 3가지 */}
        <div className="w-full grid grid-cols-3 gap-2 mb-6">
          {HIGHLIGHTS.map((h, i) => (
            <div
              key={h.label}
              className="bg-gradient-to-b from-indigo-50/80 to-white rounded-xl p-3 border border-indigo-100/50 animate-in fade-in duration-500"
              style={{ animationDelay: `${i * 200}ms` }}
            >
              <p className="text-lg font-black text-indigo-600 leading-tight">{h.num}</p>
              <p className="text-[11px] font-bold text-slate-700 mt-0.5">{h.label}</p>
              <p className="text-[10px] text-slate-400">{h.desc}</p>
            </div>
          ))}
        </div>

        {/* 진행바 */}
        <div className="w-full h-2 bg-indigo-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-indigo-500 via-violet-500 to-indigo-500 rounded-full"
            style={{
              animation: "progressBar 3s ease-in-out infinite",
              backgroundSize: "200% 100%",
            }}
          />
        </div>
        <style jsx>{`
          @keyframes progressBar {
            0% { width: 5%; background-position: 0% 50%; }
            50% { width: 80%; background-position: 100% 50%; }
            100% { width: 95%; background-position: 0% 50%; }
          }
        `}</style>

        {/* 상태 메시지 */}
        <div className="mt-5 space-y-1 transition-all duration-500">
          <p className="text-sm font-black text-slate-800 tracking-tight">{title}</p>
          <p className="text-xs text-slate-400 font-medium">{sub}</p>
        </div>
      </div>
    </div>
  );
}
