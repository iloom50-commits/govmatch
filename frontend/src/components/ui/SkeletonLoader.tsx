"use client";

export default function SkeletonLoader() {
  return (
    <div className="w-full max-w-md p-8 bg-white rounded-[2rem] shadow-2xl border border-indigo-50 animate-in fade-in zoom-in duration-500">
      <div className="flex flex-col items-center text-center">
        {/* Pulsing AI Icon */}
        <div className="relative mb-8">
          <div className="absolute inset-0 bg-indigo-500 rounded-full blur-xl opacity-20 animate-pulse"></div>
          <div className="relative w-20 h-20 bg-gradient-to-tr from-indigo-600 to-violet-500 rounded-full flex items-center justify-center text-3xl shadow-xl shadow-indigo-100 animate-bounce duration-[2000ms]">
            ✨
          </div>
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
