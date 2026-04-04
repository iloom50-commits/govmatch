"use client";

import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import EmailInput from "@/components/ui/EmailInput";

const API = process.env.NEXT_PUBLIC_API_URL;

interface LoginModalProps {
  onLoginSuccess: (token: string, user: any, plan: any) => void;
  onClose: () => void;
  onGoToRegister: () => void;
}

export default function LoginModal({ onLoginSuccess, onClose, onGoToRegister }: LoginModalProps) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"login" | "register">("login");
  const [showReset, setShowReset] = useState(false);
  const [form, setForm] = useState({ email: "", password: "" });
  const [resetEmail, setResetEmail] = useState("");
  const [resetPw, setResetPw] = useState("");
  const [resetPwConfirm, setResetPwConfirm] = useState("");

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

  const handleReset = async () => {
    if (!resetEmail) { toast("이메일을 입력해주세요.", "error"); return; }
    if (!resetPw || resetPw.length < 6) { toast("비밀번호를 6자 이상 입력해주세요.", "error"); return; }
    if (resetPw !== resetPwConfirm) { toast("비밀번호가 일치하지 않습니다.", "error"); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: resetEmail, new_password: resetPw }),
      });
      const data = await res.json();
      if (res.ok) {
        toast(data.message, "success");
        setShowReset(false);
        setForm({ ...form, email: resetEmail });
      } else {
        toast(data.detail || "재설정 실패", "error");
      }
    } catch { toast("서버 오류", "error"); }
    finally { setLoading(false); }
  };

  const inputClass =
    "w-full p-3.5 border border-slate-200 rounded-xl bg-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 transition-all text-sm font-medium outline-none";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl border border-white/60 overflow-hidden animate-in zoom-in-95 duration-300">
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-indigo-500/10 blur-[60px] rounded-full pointer-events-none" />

        <div className="relative z-10 p-6 sm:p-8">
          <div className="text-center mb-6">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">
              무료 가입으로 시작하세요
            </h2>
            <p className="text-slate-500 text-xs font-medium">
              내 조건에 딱 맞는 지원금 매칭 + 새 공고 알림까지, 무료!
            </p>
          </div>

          {/* 탭 */}
          {!showReset && (
            <div className="flex mb-5 bg-slate-100 rounded-xl p-1">
              <button
                onClick={() => setTab("login")}
                className={`flex-1 py-2.5 rounded-lg text-sm font-bold transition-all ${
                  tab === "login"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-400 hover:text-slate-600"
                }`}
              >
                로그인
              </button>
              <button
                onClick={() => setTab("register")}
                className={`flex-1 py-2.5 rounded-lg text-sm font-bold transition-all ${
                  tab === "register"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-600"
                }`}
              >
                30초 무료가입
              </button>
            </div>
          )}

          {showReset ? (
            <>
              <button
                onClick={() => setShowReset(false)}
                className="flex items-center gap-1 text-xs text-slate-400 hover:text-indigo-600 font-bold transition-all mb-4"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                </svg>
                로그인으로 돌아가기
              </button>

              <div className="text-center mb-4">
                <h3 className="text-lg font-bold text-slate-900">비밀번호 재설정</h3>
                <p className="text-xs text-slate-400 mt-1">가입한 이메일로 새 비밀번호를 설정하세요</p>
              </div>

              <div className="space-y-3">
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">이메일</label>
                  <input
                    type="email"
                    placeholder="가입한 이메일"
                    className={inputClass}
                    value={resetEmail}
                    onChange={(e) => setResetEmail(e.target.value)}
                    autoFocus
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">새 비밀번호</label>
                  <input
                    type="password"
                    placeholder="6자 이상"
                    className={inputClass}
                    value={resetPw}
                    onChange={(e) => setResetPw(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">새 비밀번호 확인</label>
                  <input
                    type="password"
                    placeholder="비밀번호 재입력"
                    className={inputClass}
                    value={resetPwConfirm}
                    onChange={(e) => setResetPwConfirm(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleReset()}
                  />
                </div>
                <button
                  onClick={handleReset}
                  disabled={loading}
                  className="w-full py-3 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all active:scale-[0.98] disabled:opacity-50"
                >
                  {loading ? "처리 중..." : "비밀번호 재설정"}
                </button>
              </div>
            </>
          ) : tab === "login" ? (
            <>
              {/* 소셜 로그인 */}
              <div className="flex items-center justify-center gap-4 mb-4">
                <button
                  onClick={() => window.location.href = `${API}/api/auth/social/kakao`}
                  className="w-12 h-12 bg-[#FEE500] rounded-full flex items-center justify-center hover:brightness-95 transition-all active:scale-95 shadow-md"
                  title="카카오 로그인"
                >
                  <svg viewBox="0 0 24 24" className="w-5 h-5" fill="#191919">
                    <path d="M12 3C6.48 3 2 6.58 2 10.9c0 2.78 1.86 5.22 4.65 6.6l-.96 3.56c-.08.3.26.54.52.37l4.23-2.82c.51.05 1.03.09 1.56.09 5.52 0 10-3.58 10-7.9C22 6.58 17.52 3 12 3z" />
                  </svg>
                </button>
                <button
                  onClick={() => window.location.href = `${API}/api/auth/social/naver`}
                  className="w-12 h-12 bg-[#03C75A] rounded-full flex items-center justify-center hover:brightness-95 transition-all active:scale-95 shadow-md"
                  title="네이버 로그인"
                >
                  <span className="text-white text-lg font-black">N</span>
                </button>
                <button
                  onClick={() => window.location.href = `${API}/api/auth/social/google`}
                  className="w-12 h-12 bg-white border border-slate-200 rounded-full flex items-center justify-center hover:bg-slate-50 transition-all active:scale-95 shadow-md"
                  title="Google 로그인"
                >
                  <svg viewBox="0 0 24 24" className="w-5 h-5">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                  </svg>
                </button>
              </div>

              <div className="flex items-center gap-3 mb-4">
                <div className="flex-1 h-px bg-slate-200" />
                <span className="text-[11px] text-slate-400 font-medium">또는 이메일로</span>
                <div className="flex-1 h-px bg-slate-200" />
              </div>

              {/* 이메일 로그인 폼 */}
              <form onSubmit={handleSubmit} className="space-y-3">
                <EmailInput
                  value={form.email}
                  onChange={(email) => setForm({ ...form, email })}
                  label="이메일"
                />
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">비밀번호</label>
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
                  className="w-full py-3 bg-slate-900 text-white rounded-xl font-bold text-sm hover:bg-indigo-600 transition-all active:scale-[0.98]"
                >
                  {loading ? <span className="animate-pulse">로그인 중...</span> : "로그인"}
                </button>
              </form>

              <div className="text-center mt-4">
                <button
                  onClick={() => { setShowReset(true); setResetEmail(form.email); }}
                  className="text-xs text-slate-400 hover:text-indigo-600 font-medium transition-all"
                >
                  비밀번호를 잊으셨나요?
                </button>
              </div>
            </>
          ) : (
            <>
              {/* 회원가입 안내 */}
              <div className="text-center space-y-4">
                {/* 소셜 로그인 */}
                <div className="flex items-center justify-center gap-4 mb-2">
                  <button
                    onClick={() => window.location.href = `${API}/api/auth/social/kakao`}
                    className="w-12 h-12 bg-[#FEE500] rounded-full flex items-center justify-center hover:brightness-95 transition-all active:scale-95 shadow-md"
                  >
                    <svg viewBox="0 0 24 24" className="w-5 h-5" fill="#191919">
                      <path d="M12 3C6.48 3 2 6.58 2 10.9c0 2.78 1.86 5.22 4.65 6.6l-.96 3.56c-.08.3.26.54.52.37l4.23-2.82c.51.05 1.03.09 1.56.09 5.52 0 10-3.58 10-7.9C22 6.58 17.52 3 12 3z" />
                    </svg>
                  </button>
                  <button
                    onClick={() => window.location.href = `${API}/api/auth/social/naver`}
                    className="w-12 h-12 bg-[#03C75A] rounded-full flex items-center justify-center hover:brightness-95 transition-all active:scale-95 shadow-md"
                  >
                    <span className="text-white text-lg font-black">N</span>
                  </button>
                  <button
                    onClick={() => window.location.href = `${API}/api/auth/social/google`}
                    className="w-12 h-12 bg-white border border-slate-200 rounded-full flex items-center justify-center hover:bg-slate-50 transition-all active:scale-95 shadow-md"
                  >
                    <svg viewBox="0 0 24 24" className="w-5 h-5">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                    </svg>
                  </button>
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex-1 h-px bg-slate-200" />
                  <span className="text-[11px] text-slate-400 font-medium">또는</span>
                  <div className="flex-1 h-px bg-slate-200" />
                </div>

                <button
                  onClick={onGoToRegister}
                  className="w-full py-3 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all active:scale-[0.98]"
                >
                  이메일로 가입하기
                </button>

                <button
                  onClick={onClose}
                  className="text-xs text-slate-400 hover:text-slate-600 font-medium transition-all"
                >
                  나중에 하기
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
