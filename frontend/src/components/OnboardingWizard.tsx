"use client";

import { useState, useEffect } from "react";
import { useToast } from "@/components/ui/Toast";

interface OnboardingWizardProps {
  initialBusinessNumber?: string;
  initialEmail?: string;
  onComplete: (data: any) => void;
  onLogout?: () => void;
}

export default function OnboardingWizard({ initialBusinessNumber = "", initialEmail = "", onComplete, onLogout }: OnboardingWizardProps) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [referredBy, setReferredBy] = useState<string | null>(null);

  // URL 파라미터에서 추천 코드 읽기
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const ref = params.get("ref");
    if (ref) {
      setReferredBy(ref);
    }
  }, []);

  const handleSubmit = async () => {
    if (!email) {
      toast("이메일을 입력해주세요.", "error");
      return;
    }
    if (!password || password.length < 6) {
      toast("비밀번호를 6자 이상 입력해주세요.", "error");
      return;
    }
    if (password !== confirmPassword) {
      toast("비밀번호가 일치하지 않습니다.", "error");
      return;
    }

    setLoading(true);
    try {
      await onComplete({
        email,
        password,
        business_number: initialBusinessNumber || `U${Date.now().toString().slice(-9)}`,
        referred_by: referredBy || undefined,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-sm mx-auto animate-in fade-in duration-500">
      <div className="bg-white/80 backdrop-blur-xl rounded-2xl shadow-xl border border-white/60 p-6 sm:p-8">
        <div className="text-center mb-6">
          <h2 className="text-xl font-black text-slate-900">무료 가입으로 시작하세요</h2>
          <p className="text-sm text-slate-500 mt-1">내 조건에 딱 맞는 지원금 매칭 + 새 공고 알림까지, 무료!</p>
        </div>

        <div className="space-y-4">
          {/* 이메일 */}
          <div>
            <label className="text-sm font-bold text-slate-700 mb-1.5 block">이메일</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="email@example.com"
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
              autoFocus
            />
          </div>

          {/* 비밀번호 */}
          <div>
            <label className="text-sm font-bold text-slate-700 mb-1.5 block">비밀번호</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="6자 이상"
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
            />
          </div>

          {/* 비밀번호 확인 */}
          <div>
            <label className="text-sm font-bold text-slate-700 mb-1.5 block">비밀번호 확인</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              placeholder="비밀번호 재입력"
              onKeyDown={e => e.key === "Enter" && handleSubmit()}
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
            />
          </div>

          {/* 가입 버튼 */}
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="w-full py-3.5 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all active:scale-[0.98] disabled:opacity-50 shadow-lg shadow-indigo-200"
          >
            {loading ? "가입 중..." : "무료로 시작하기"}
          </button>
        </div>

        {/* 소셜 로그인 안내 */}
        <div className="mt-5 pt-5 border-t border-slate-100 text-center">
          <p className="text-xs text-slate-400 mb-3">또는 간편 로그인</p>
          {onLogout && (
            <button
              onClick={onLogout}
              className="text-xs text-indigo-500 hover:text-indigo-700 font-semibold"
            >
              다른 방법으로 로그인
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
