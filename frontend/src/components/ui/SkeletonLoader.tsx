"use client";

export default function SkeletonLoader() {
  return (
    <div className="w-full max-w-md p-8 bg-white rounded-[2rem] shadow-2xl border border-indigo-50 animate-in fade-in zoom-in duration-500">
      <div className="flex flex-col items-center text-center">
        {/* 컴퓨터 타이핑 봇 */}
        <div className="relative mb-8">
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
        
        <div className="w-full space-y-4 mb-8">
          <div className="h-4 bg-slate-100 rounded-full w-3/4 mx-auto animate-pulse"></div>
          <div className="h-3 bg-slate-50 rounded-full w-1/2 mx-auto animate-pulse delay-75"></div>
        </div>

        <div className="w-full grid grid-cols-2 gap-4">
          <div className="h-16 bg-slate-50 rounded-2xl animate-pulse"></div>
          <div className="h-16 bg-slate-50 rounded-2xl animate-pulse delay-150"></div>
        </div>
        
        <div className="w-full h-14 bg-indigo-50/50 rounded-2xl mt-8 flex items-center justify-center">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce"></div>
            <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce delay-100"></div>
            <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce delay-200"></div>
          </div>
        </div>
        
        <div className="mt-8 space-y-1">
          <p className="text-sm font-black text-slate-800 uppercase tracking-widest">Processing</p>
          <p className="text-xs text-slate-400 font-medium tracking-tight">잠시만 기다려 주세요...</p>
        </div>
      </div>
    </div>
  );
}
