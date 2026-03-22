"use client";

import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import EmailInput from "@/components/ui/EmailInput";

const API = process.env.NEXT_PUBLIC_API_URL;

interface AuthPageProps {
  onLoginSuccess: (token: string, user: any, plan: any) => void;
  onGoToRegister: () => void;
  initialEmail?: string;
}

export default function AuthPage({ onLoginSuccess, onGoToRegister, initialEmail }: AuthPageProps) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ email: initialEmail || "", password: "" });
  const [mode, setMode] = useState<"login" | "reset">("login");
  const [resetForm, setResetForm] = useState({ email: "", company_name: "", new_password: "" });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await fetch(`${API}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();

      if (!res.ok) {
        toast(data.detail || "로그인 실패", "error");
        return;
      }

      onLoginSuccess(data.token, data.user, data.plan);
    } catch {
      toast("서버와 통신 중 오류가 발생했습니다.", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await fetch(`${API}/api/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(resetForm),
      });
      const data = await res.json();

      if (!res.ok) {
        toast(data.detail || "비밀번호 재설정 실패", "error");
        return;
      }

      toast("비밀번호가 재설정되었습니다.", "success");
      setForm({ email: resetForm.email, password: "" });
      setMode("login");
    } catch {
      toast("서버와 통신 중 오류가 발생했습니다.", "error");
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    "w-full p-4 border border-white/80 rounded-2xl bg-white/50 focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-bold outline-none shadow-inner";

  return (
    <div className="w-full max-w-md bg-white/70 backdrop-blur-3xl rounded-[2rem] sm:rounded-[2.5rem] p-5 sm:p-8 md:p-10 shadow-2xl border border-white/60 animate-in zoom-in-95 duration-500 relative overflow-hidden">
      <div className="absolute -top-24 -right-24 w-48 h-48 bg-indigo-500/10 blur-[80px] rounded-full pointer-events-none" />

      <div className="relative z-10">
        {mode === "login" ? (
          <>
            <div className="text-center mb-6 sm:mb-8">
              <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight mb-1">
                다시 오셨군요!
              </h2>
              <p className="text-slate-500 text-xs font-bold opacity-60">
                이메일과 비밀번호로 로그인하세요
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <EmailInput
                value={form.email}
                onChange={(email) => setForm({ ...form, email })}
                label="이메일"
              />

              <div className="space-y-1.5">
                <label className="text-[11px] font-black text-indigo-500 uppercase tracking-[0.2em] ml-2">
                  비밀번호
                </label>
                <input
                  type="password"
                  required
                  placeholder="비밀번호 입력"
                  className={inputClass}
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 mt-2 bg-slate-900 text-white rounded-2xl font-black text-base shadow-xl shadow-indigo-100 hover:bg-indigo-600 transition-all active:scale-95 flex items-center justify-center group"
              >
                {loading ? (
                  <span className="animate-pulse">로그인 중...</span>
                ) : (
                  <>로그인<span className="ml-2 group-hover:translate-x-1 transition-transform">→</span></>
                )}
              </button>
            </form>

            <div className="flex justify-between mt-4">
              <button
                onClick={onGoToRegister}
                className="py-2 text-slate-400 hover:text-indigo-600 text-xs font-black transition-all"
              >
                처음이신가요? 30초 무료가입
              </button>
              <button
                onClick={() => { setResetForm({ ...resetForm, email: form.email }); setMode("reset"); }}
                className="py-2 text-slate-400 hover:text-rose-500 text-xs font-bold transition-all"
              >
                비밀번호 찾기
              </button>
            </div>

            {process.env.NEXT_PUBLIC_DEV_MODE === "true" && (
              <button
                onClick={() => setForm({ email: "demo@test.com", password: "test1234" })}
                className="w-full mt-2 py-2 text-orange-400 hover:text-orange-600 text-[11px] font-bold transition-all text-center border border-dashed border-orange-200 rounded-xl"
              >
                [DEV] 테스트 계정 자동입력
              </button>
            )}
          </>
        ) : (
          <>
            <div className="text-center mb-6 sm:mb-8">
              <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight mb-1">
                비밀번호 재설정
              </h2>
              <p className="text-slate-500 text-xs font-bold opacity-60">
                가입 시 사용한 이메일과 회사명으로 본인 확인
              </p>
            </div>

            <form onSubmit={handleReset} className="space-y-4">
              <EmailInput
                value={resetForm.email}
                onChange={(email) => setResetForm({ ...resetForm, email })}
                label="이메일"
              />

              <div className="space-y-1.5">
                <label className="text-[11px] font-black text-indigo-500 uppercase tracking-[0.2em] ml-2">
                  회사명
                </label>
                <input
                  type="text"
                  required
                  placeholder="가입 시 입력한 회사명"
                  className={inputClass}
                  value={resetForm.company_name}
                  onChange={(e) => setResetForm({ ...resetForm, company_name: e.target.value })}
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[11px] font-black text-indigo-500 uppercase tracking-[0.2em] ml-2">
                  새 비밀번호
                </label>
                <input
                  type="password"
                  required
                  minLength={6}
                  placeholder="새 비밀번호 (6자 이상)"
                  className={inputClass}
                  value={resetForm.new_password}
                  onChange={(e) => setResetForm({ ...resetForm, new_password: e.target.value })}
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 mt-2 bg-slate-900 text-white rounded-2xl font-black text-base shadow-xl shadow-indigo-100 hover:bg-indigo-600 transition-all active:scale-95 flex items-center justify-center group"
              >
                {loading ? (
                  <span className="animate-pulse">처리 중...</span>
                ) : (
                  <>비밀번호 재설정<span className="ml-2 group-hover:translate-x-1 transition-transform">→</span></>
                )}
              </button>
            </form>

            <button
              onClick={() => setMode("login")}
              className="w-full mt-4 py-2 text-slate-400 hover:text-indigo-600 text-xs font-black transition-all text-center"
            >
              로그인으로 돌아가기
            </button>
          </>
        )}
      </div>
    </div>
  );
}
