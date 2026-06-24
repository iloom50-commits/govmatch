"use client";
import { useState, useEffect } from "react";
import PaymentModal from "@/components/PaymentModal";

const API = process.env.NEXT_PUBLIC_API_URL;

type AuthState = "loading" | "auth" | "dashboard" | "pro";
type AuthTab = "login" | "signup";

export default function ProPageClient() {
  const [authState, setAuthState] = useState<AuthState>("loading");
  const [authTab, setAuthTab] = useState<AuthTab>("login");
  const [planStatus, setPlanStatus] = useState<any>(null);
  const [userData, setUserData] = useState<any>(null);
  const [showPayment, setShowPayment] = useState(false);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [businessNumber, setBusinessNumber] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) { setAuthState("auth"); return; }
    fetch(`${API}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(data => {
        if (data.status === "SUCCESS" && data.plan) {
          setPlanStatus(data.plan);
          setUserData(data.user);
          setAuthState("dashboard");
        } else {
          localStorage.removeItem("auth_token");
          setAuthState("auth");
        }
      })
      .catch(() => { localStorage.removeItem("auth_token"); setAuthState("auth"); });
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true); setError("");
    try {
      const res = await fetch(`${API}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok || !data.token) {
        setError(data.detail || "이메일 또는 비밀번호를 확인해주세요."); return;
      }
      localStorage.setItem("auth_token", data.token);
      setPlanStatus(data.plan); setUserData(data.user);
      setAuthState("dashboard");
    } catch { setError("서버 연결에 실패했습니다."); }
    finally { setSubmitting(false); }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!businessNumber.trim()) { setError("사업자번호를 입력해주세요."); return; }
    setSubmitting(true); setError("");
    try {
      const res = await fetch(`${API}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          business_number: businessNumber.replace(/-/g, ""),
          company_name: companyName,
          user_type: "business",
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.token) {
        setError(data.detail || "회원가입에 실패했습니다."); return;
      }
      localStorage.setItem("auth_token", data.token);
      setPlanStatus(data.plan); setUserData(data.user);
      setAuthState("dashboard");
    } catch { setError("서버 연결에 실패했습니다."); }
    finally { setSubmitting(false); }
  };

  const handlePaymentSuccess = (token: string, plan: any) => {
    localStorage.setItem("auth_token", token);
    setPlanStatus(plan);
    setShowPayment(false);
    if (["pro", "biz"].includes(plan?.plan)) setAuthState("pro");
  };

  const handleLogout = () => {
    localStorage.removeItem("auth_token");
    setPlanStatus(null); setUserData(null);
    setEmail(""); setPassword(""); setError("");
    setAuthState("auth");
  };

  const isPro = planStatus && ["pro", "biz"].includes(planStatus.plan);

  const inputCls = "w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent transition-shadow";
  const btnPrimary = { backgroundColor: "#111827", color: "#ffffff" };

  // ── 로딩 ──
  if (authState === "loading") {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-gray-200 border-t-gray-600 rounded-full animate-spin" />
      </div>
    );
  }

  // ── PRO → ProSecretary 전체화면 ──
  if (authState === "pro") {
    const ProSecretary = require("@/components/pro/ProSecretary").default;
    return (
      <ProSecretary
        onClose={handleLogout}
        planStatus={planStatus}
        onUpgrade={() => setShowPayment(true)}
        userType={userData?.user_type || "business"}
      />
    );
  }

  // ── 로그인 / 회원가입 ──
  if (authState === "auth") {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center px-4 py-12">
        <div className="w-full max-w-2xl space-y-10">

          {/* ── PRO 가치 제안 (비로그인 방문자 설득 · 실제 기능/가격만) ── */}
          <div className="space-y-6">
            <div>
              <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-violet-100 text-violet-700 text-[11px] font-bold mb-3">전문가 전용 · PRO</span>
              <h2 className="text-2xl lg:text-[26px] font-bold text-gray-900 leading-snug">고객사 정부지원사업 상담,<br />전문가처럼 빠르게.</h2>
              <p className="mt-3 text-sm text-gray-500 leading-relaxed">컨설턴트·세무·노무 전문가를 위한 상담 도구. 고객 조건만 입력하면 맞춤 공고 매칭부터 자격 판정·전문가 인사이트·보고서까지 한 번에.</p>
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              {[
                { i: "🎯", t: "고객사별 맞춤 매칭", d: "업종·지역·매출 조건으로 적합 공고 자동 선별" },
                { i: "📋", t: "자격 판정 + 전문가 인사이트", d: "선정률 추정·평가 배점·흔한 실수·신청 팁" },
                { i: "👥", t: "고객 관리 · 보고서", d: "고객별 상담 이력 관리, 컨설팅 보고서 PDF" },
                { i: "💰", t: "자금 상담 AI", d: "정책자금·보증·대출 전문 Q&A" },
              ].map(f => (
                <div key={f.t} className="rounded-xl border border-gray-100 bg-gray-50/60 p-3.5">
                  <div className="text-lg mb-1">{f.i}</div>
                  <p className="text-[13px] font-bold text-gray-800">{f.t}</p>
                  <p className="text-[11px] text-gray-500 mt-0.5 leading-relaxed">{f.d}</p>
                </div>
              ))}
            </div>
            <div className="rounded-xl border border-violet-200 bg-violet-50/50 p-4 flex items-center justify-between gap-3">
              <div>
                <div className="flex items-baseline gap-1.5">
                  <span className="text-xl font-black text-gray-900">₩29,000</span>
                  <span className="text-xs text-gray-400">/ 월</span>
                  <span className="text-xs text-gray-400 line-through">₩49,000</span>
                </div>
                <p className="text-[11px] text-violet-700 font-medium mt-0.5">7일 무료체험 · 언제든 취소 가능</p>
              </div>
              <button onClick={() => { setAuthTab("signup"); setError(""); }}
                className="flex-shrink-0 px-4 py-2.5 bg-violet-600 text-white rounded-lg text-[13px] font-bold hover:bg-violet-700 transition-all active:scale-[0.98]">
                7일 무료로 시작 →
              </button>
            </div>
          </div>

          {/* ── 오른쪽: 로그인/회원가입 ── */}
          <div className="w-full max-w-sm mx-auto lg:mx-0 space-y-8">

          <div className="text-center space-y-1">
            <h1 className="text-3xl font-semibold text-gray-900 tracking-tight">GovMatch</h1>
            <p className="text-sm text-gray-400">전문상담툴</p>
          </div>

          {/* 소셜 로그인 */}
          <div className="space-y-3">
            <p className="text-center text-xs text-gray-400">간편 로그인</p>
            <div className="flex justify-center gap-3">
              <button
                onClick={() => { sessionStorage.setItem("social_redirect", "/pro"); window.location.href = `${API}/api/auth/social/kakao`; }}
                className="w-11 h-11 bg-[#FEE500] rounded-full flex items-center justify-center hover:brightness-95 transition-all active:scale-95 shadow-sm" title="카카오로 로그인">
                <svg viewBox="0 0 24 24" className="w-5 h-5" fill="#191919"><path d="M12 3C6.48 3 2 6.58 2 10.9c0 2.78 1.86 5.22 4.65 6.6l-.96 3.56c-.08.3.26.54.52.37l4.23-2.82c.51.05 1.03.09 1.56.09 5.52 0 10-3.58 10-7.9C22 6.58 17.52 3 12 3z" /></svg>
              </button>
              <button
                onClick={() => { sessionStorage.setItem("social_redirect", "/pro"); window.location.href = `${API}/api/auth/social/naver`; }}
                className="w-11 h-11 bg-[#03C75A] rounded-full flex items-center justify-center hover:brightness-95 transition-all active:scale-95 shadow-sm" title="네이버로 로그인">
                <span className="text-white text-base font-black">N</span>
              </button>
              <button
                onClick={() => { sessionStorage.setItem("social_redirect", "/pro"); window.location.href = `${API}/api/auth/social/google`; }}
                className="w-11 h-11 bg-white border border-gray-200 rounded-full flex items-center justify-center hover:bg-gray-50 transition-all active:scale-95 shadow-sm" title="Google로 로그인">
                <svg viewBox="0 0 24 24" className="w-5 h-5"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" /><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" /><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" /><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" /></svg>
              </button>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex-1 h-px bg-gray-200" />
              <span className="text-xs text-gray-400">또는</span>
              <div className="flex-1 h-px bg-gray-200" />
            </div>
          </div>

          {/* 탭 */}
          <div className="flex rounded-lg border border-gray-200 p-0.5 bg-gray-50">
            {(["login", "signup"] as AuthTab[]).map(t => (
              <button key={t} onClick={() => { setAuthTab(t); setError(""); }}
                className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${authTab === t ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}>
                {t === "login" ? "로그인" : "회원가입"}
              </button>
            ))}
          </div>

          {/* 로그인 */}
          {authTab === "login" && (
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">이메일</label>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="name@company.com" required autoComplete="email" className={inputCls} />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">비밀번호</label>
                <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••" required autoComplete="current-password" className={inputCls} />
              </div>
              {error && <p className="text-sm text-red-500">{error}</p>}
              <button type="submit" disabled={submitting} style={btnPrimary}
                className="w-full py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-40">
                {submitting ? "로그인 중..." : "로그인"}
              </button>
            </form>
          )}

          {/* 회원가입 */}
          {authTab === "signup" && (
            <form onSubmit={handleSignup} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">이메일</label>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="name@company.com" required autoComplete="email" className={inputCls} />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">비밀번호</label>
                <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                  placeholder="8자 이상" required autoComplete="new-password" minLength={8} className={inputCls} />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">사업자번호</label>
                <input type="text" value={businessNumber} onChange={e => setBusinessNumber(e.target.value)}
                  placeholder="000-00-00000" required className={inputCls} />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">회사명 <span className="text-gray-400 font-normal">(선택)</span></label>
                <input type="text" value={companyName} onChange={e => setCompanyName(e.target.value)}
                  placeholder="회사명" className={inputCls} />
              </div>
              {error && <p className="text-sm text-red-500">{error}</p>}
              <button type="submit" disabled={submitting} style={btnPrimary}
                className="w-full py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-40">
                {submitting ? "가입 중..." : "회원가입"}
              </button>
            </form>
          )}

          </div>
        </div>
      </div>
    );
  }

  // ── 대시보드 ──
  return (
    <>
      <div className="min-h-screen bg-white flex flex-col items-center justify-center px-4">
        <div className="w-full max-w-sm space-y-6">

          <div className="text-center space-y-1">
            <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">GovMatch</h1>
            <p className="text-sm text-gray-400">전문상담툴</p>
          </div>

          {/* 사용자 + 플랜 */}
          <div className="rounded-xl border border-gray-100 bg-gray-50 px-5 py-4 space-y-1">
            <div className="flex items-center justify-between">
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {userData?.company_name || userData?.email || "사용자"}
                </p>
                {userData?.company_name && (
                  <p className="text-xs text-gray-400 truncate">{userData.email}</p>
                )}
              </div>
              <span className={`ml-3 flex-shrink-0 px-2.5 py-1 rounded-full text-xs font-semibold ${isPro ? "bg-violet-100 text-violet-700" : "bg-gray-100 text-gray-500"}`}>
                {planStatus?.label || "FREE"}
              </span>
            </div>
          </div>

          {/* 액션 */}
          {isPro ? (
            <button onClick={() => setAuthState("pro")} style={btnPrimary}
              className="w-full py-3 rounded-lg text-sm font-semibold transition-colors">
              전문상담툴 시작하기 →
            </button>
          ) : (
            <div className="space-y-3">
              <div className="rounded-xl border border-gray-100 bg-gray-50 px-5 py-4 text-center">
                <p className="text-sm text-gray-600 leading-relaxed">
                  전문상담툴은 <span className="font-semibold text-gray-900">PRO 플랜</span> 전용입니다.
                </p>
              </div>
              <button onClick={() => setShowPayment(true)} style={btnPrimary}
                className="w-full py-3 rounded-lg text-sm font-semibold transition-colors">
                PRO 플랜 결제하기
              </button>
            </div>
          )}

          <button onClick={handleLogout}
            className="w-full text-xs text-gray-400 hover:text-gray-600 transition-colors py-1">
            로그아웃
          </button>
        </div>
      </div>

      {showPayment && (
        <PaymentModal
          mode="pro"
          planStatus={planStatus}
          userType={userData?.user_type || "business"}
          onSuccess={handlePaymentSuccess}
          onClose={() => setShowPayment(false)}
        />
      )}
    </>
  );
}
