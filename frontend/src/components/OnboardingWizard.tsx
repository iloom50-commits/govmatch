"use client";

import { useState } from "react";
import { useToast } from "@/components/ui/Toast";

interface OnboardingWizardProps {
  initialBusinessNumber?: string;
  initialEmail?: string;
  onComplete: (data: any) => void;
  onLogout?: () => void;
}

const GENDER_OPTIONS = ["남성", "여성"];
const AGE_OPTIONS = ["10대", "20대", "30대", "40대", "50대", "60대 이상"];

export default function OnboardingWizard({ initialBusinessNumber = "", initialEmail = "", onComplete, onLogout }: OnboardingWizardProps) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(0); // 0: 계정, 1: 성별/연령대
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [gender, setGender] = useState("");
  const [ageRange, setAgeRange] = useState("");

  const handleNext = () => {
    if (!email) { toast("이메일을 입력해주세요.", "error"); return; }
    if (!password || password.length < 6) { toast("비밀번호를 6자 이상 입력해주세요.", "error"); return; }
    if (password !== confirmPassword) { toast("비밀번호가 일치하지 않습니다.", "error"); return; }
    setStep(1);
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      await onComplete({
        email,
        password,
        business_number: initialBusinessNumber || `U${Date.now().toString().slice(-9)}`,
        gender,
        age_range: ageRange,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-sm mx-auto animate-in fade-in duration-500">
      <div className="bg-white/80 backdrop-blur-xl rounded-2xl shadow-xl border border-white/60 p-6 sm:p-8">

        {step === 0 ? (
          <>
            <div className="text-center mb-6">
              <p className="text-xs text-indigo-500 font-bold mb-1">1 / 2</p>
              <h2 className="text-xl font-black text-slate-900">무료 가입으로 시작하세요</h2>
              <p className="text-sm text-slate-500 mt-1">내 조건에 딱 맞는 지원금 매칭 + 새 공고 알림까지, 무료!</p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-sm font-bold text-slate-700 mb-1.5 block">이메일</label>
                <input
                  type="email" value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="email@example.com"
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
                  autoFocus
                />
              </div>
              <div>
                <label className="text-sm font-bold text-slate-700 mb-1.5 block">비밀번호</label>
                <input
                  type="password" value={password} onChange={e => setPassword(e.target.value)}
                  placeholder="6자 이상"
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
                />
              </div>
              <div>
                <label className="text-sm font-bold text-slate-700 mb-1.5 block">비밀번호 확인</label>
                <input
                  type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)}
                  placeholder="비밀번호 재입력"
                  onKeyDown={e => e.key === "Enter" && handleNext()}
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
                />
              </div>
              <button
                onClick={handleNext}
                className="w-full py-3.5 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all active:scale-[0.98] shadow-lg shadow-indigo-200"
              >
                다음
              </button>
            </div>

            <div className="mt-5 pt-5 border-t border-slate-100 text-center">
              <p className="text-xs text-slate-400 mb-3">또는 간편 로그인</p>
              {onLogout && (
                <button onClick={onLogout} className="text-xs text-indigo-500 hover:text-indigo-700 font-semibold">
                  다른 방법으로 로그인
                </button>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="text-center mb-6">
              <p className="text-xs text-indigo-500 font-bold mb-1">2 / 2</p>
              <h2 className="text-xl font-black text-slate-900">맞춤 매칭을 위한 정보</h2>
              <p className="text-sm text-slate-500 mt-1">선택사항이에요. 건너뛰어도 됩니다.</p>
            </div>

            <div className="space-y-5">
              {/* 성별 */}
              <div>
                <label className="text-sm font-bold text-slate-700 mb-2 block">성별</label>
                <div className="flex gap-2">
                  {GENDER_OPTIONS.map(g => (
                    <button
                      key={g} type="button" onClick={() => setGender(gender === g ? "" : g)}
                      className={`flex-1 py-3 rounded-xl text-sm font-semibold border transition-all active:scale-95 ${
                        gender === g
                          ? "bg-indigo-600 text-white border-indigo-600"
                          : "bg-white text-slate-600 border-slate-200 hover:border-indigo-300"
                      }`}
                    >{g}</button>
                  ))}
                </div>
              </div>

              {/* 연령대 */}
              <div>
                <label className="text-sm font-bold text-slate-700 mb-2 block">연령대</label>
                <div className="grid grid-cols-3 gap-2">
                  {AGE_OPTIONS.map(a => (
                    <button
                      key={a} type="button" onClick={() => setAgeRange(ageRange === a ? "" : a)}
                      className={`py-2.5 rounded-xl text-sm font-semibold border transition-all active:scale-95 ${
                        ageRange === a
                          ? "bg-indigo-600 text-white border-indigo-600"
                          : "bg-white text-slate-600 border-slate-200 hover:border-indigo-300"
                      }`}
                    >{a}</button>
                  ))}
                </div>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  onClick={() => setStep(0)}
                  className="flex-1 py-3 bg-slate-100 text-slate-600 rounded-xl font-bold text-sm hover:bg-slate-200 transition-all"
                >
                  이전
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="flex-[2] py-3 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all active:scale-[0.98] disabled:opacity-50 shadow-lg shadow-indigo-200"
                >
                  {loading ? "가입 중..." : "무료로 시작하기"}
                </button>
              </div>
              <button
                onClick={handleSubmit}
                className="w-full py-2 text-xs text-slate-400 hover:text-slate-600 font-medium transition-all"
              >
                건너뛰기
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
