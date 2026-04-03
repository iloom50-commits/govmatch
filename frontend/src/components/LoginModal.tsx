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
                <div className="space-y-2 text-left">
                  {[
                    { icon: "🎯", text: "내 조건에 맞는 지원금 자동 매칭" },
                    { icon: "🔔", text: "새 공고 & 마감 임박 알림" },
                    { icon: "💬", text: "AI 상담으로 자격요건 즉시 확인" },
                  ].map((item) => (
                    <div key={item.text} className="flex items-center gap-2.5 p-2.5 bg-slate-50 rounded-lg">
                      <span className="text-base">{item.icon}</span>
                      <span className="text-[13px] font-medium text-slate-700">{item.text}</span>
                    </div>
                  ))}
                </div>

                <button
                  onClick={onGoToRegister}
                  className="w-full py-3 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all active:scale-[0.98]"
                >
                  30초 무료가입 시작하기
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
