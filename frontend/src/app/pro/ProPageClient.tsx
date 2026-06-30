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
  const [showLogin, setShowLogin] = useState(false);  // '상담 시작하기' 클릭 전엔 로그인 폼 숨김
  const [loginReason, setLoginReason] = useState("");  // 왜 로그인이 필요한지(메뉴/상담시작 액션 사유)
  const [showEmail, setShowEmail] = useState(false);  // 소셜이 메인, 이메일은 기존 회원용 fallback

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
          setShowLogin(false);
      setAuthState(cur => cur === "pro" ? "pro" : "dashboard");
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
      setShowLogin(false);
      setAuthState(cur => cur === "pro" ? "pro" : "dashboard");
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
      setShowLogin(false);
      setAuthState(cur => cur === "pro" ? "pro" : "dashboard");
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
  const trialRemaining = planStatus?.pro_trial_remaining ?? 3;

  // ── 2 제품 카드 진입 ──
  const goConsult = () => setAuthState("pro");
  const goSmartDoc = async () => {
    try {
      const token = localStorage.getItem("auth_token");
      const res = await fetch(`${API}/api/smartdoc/handoff`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (data?.url) window.location.href = data.url;
      else setError("SmartDoc 연결에 실패했습니다.");
    } catch { setError("SmartDoc 연결에 실패했습니다."); }
  };
  // SmartDoc 배포 전엔 "곧 출시" (배포 후 NEXT_PUBLIC_SMARTDOC_READY=true 로 활성화)
  const SMARTDOC_READY = process.env.NEXT_PUBLIC_SMARTDOC_READY === "true";
  // 비로그인이면 로그인(모달) → 로그인 후 카드 다시 클릭하면 진입
  const onCardClick = (action: "smartdoc" | "consult") => {
    if (action === "smartdoc" && !SMARTDOC_READY) {
      alert("정책자금 융자신청서 자동 작성(SmartDoc)은 곧 출시 예정입니다.");
      return;
    }
    // 상담 프로그램: 비로그인도 상담 대시보드 진입 허용 → '상담 시작' 액션에서 로그인 요구
    if (action === "consult") { goConsult(); return; }
    // SmartDoc(핸드오프)은 로그인 필요
    if (!planStatus) { setLoginReason(""); setShowLogin(true); setError(""); return; }
    goSmartDoc();
  };

  const ProductCards = (
    <div className="grid sm:grid-cols-2 gap-4">
      {SMARTDOC_READY ? (
        <button type="button" onClick={() => onCardClick("smartdoc")}
          className="relative text-left rounded-2xl border border-violet-200 bg-white hover:border-violet-400 hover:shadow-md p-5 transition-all active:scale-[0.99]">
          <div className="text-3xl mb-2">📝</div>
          <p className="text-[15px] font-black text-gray-900">정책자금 융자신청서 자동 작성</p>
          <p className="text-[12px] text-gray-500 mt-1 leading-relaxed">공고 첨부 양식을 AI가 분석해 기업 정보 기반 맞춤 신청서 초안을 자동 생성 <span className="text-violet-600 font-bold">(SmartDoc)</span></p>
        </button>
      ) : (
        <a href="/" target="_blank" rel="noopener noreferrer"
          className="block text-left rounded-2xl border border-violet-200 bg-white hover:border-violet-400 hover:shadow-md p-5 transition-all active:scale-[0.99]">
          <div className="text-3xl mb-2">🔎</div>
          <p className="text-[15px] font-black text-gray-900">지원금AI — 모든 지원금 찾기</p>
          <p className="text-[12px] text-gray-500 mt-1 leading-relaxed">내 기업·상황에 맞는 정부지원금·정책자금을 AI가 한 번에 찾아드립니다</p>
        </a>
      )}
      <button type="button" onClick={() => onCardClick("consult")}
        className="text-left rounded-2xl border border-indigo-200 bg-white hover:border-indigo-400 hover:shadow-md p-5 transition-all active:scale-[0.99]">
        <div className="text-3xl mb-2">💼</div>
        <p className="text-[15px] font-black text-gray-900">정부 지원사업 상담 프로그램</p>
        <p className="text-[12px] text-gray-500 mt-1 leading-relaxed">고객 조건만 입력하면 맞춤 공고 매칭·자격판정·전문가 인사이트·보고서까지 한 번에</p>
      </button>
    </div>
  );

  const inputCls = "w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent transition-shadow";
  const btnPrimary = { backgroundColor: "#111827", color: "#ffffff" };

  // 로그인/회원가입 모달 — 비로그인 랜딩과 상담 화면(ProSecretary) 위 오버레이 양쪽에서 재사용
  const LoginModal = showLogin && (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={() => { setShowLogin(false); setShowEmail(false); setError(""); setLoginReason(""); }}>
      <div className="bg-white rounded-2xl w-full max-w-sm p-6 space-y-5 shadow-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">GovMatch</h1>
            <p className="text-xs text-gray-400">전문상담툴 · 로그인</p>
          </div>
          <button type="button" onClick={() => { setShowLogin(false); setShowEmail(false); setError(""); setLoginReason(""); }} className="text-gray-400 hover:text-gray-700 text-2xl leading-none -mt-1">×</button>
        </div>

        {loginReason && (
          <div className="rounded-lg bg-violet-50 border border-violet-100 px-3 py-2.5 text-[12px] text-violet-700 text-center font-medium leading-relaxed">
            {loginReason}
          </div>
        )}

        {/* 소셜 로그인 (메인 — 가입·로그인 한 번에) */}
        <div className="max-w-sm mx-auto space-y-3 pt-2">
          <button onClick={() => { sessionStorage.setItem("social_redirect", "/pro"); window.location.href = `${API}/api/auth/social/kakao`; }}
            className="w-full py-3.5 bg-[#FEE500] rounded-xl flex items-center justify-center gap-2 text-[#191919] text-[15px] font-bold hover:brightness-95 transition-all active:scale-[0.99]">
            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="#191919"><path d="M12 3C6.48 3 2 6.58 2 10.9c0 2.78 1.86 5.22 4.65 6.6l-.96 3.56c-.08.3.26.54.52.37l4.23-2.82c.51.05 1.03.09 1.56.09 5.52 0 10-3.58 10-7.9C22 6.58 17.52 3 12 3z" /></svg>
            카카오로 시작하기
          </button>
          <button onClick={() => { sessionStorage.setItem("social_redirect", "/pro"); window.location.href = `${API}/api/auth/social/naver`; }}
            className="w-full py-3.5 bg-[#03C75A] rounded-xl flex items-center justify-center gap-2 text-white text-[15px] font-bold hover:brightness-95 transition-all active:scale-[0.99]">
            <span className="text-base font-black">N</span> 네이버로 시작하기
          </button>
          <button onClick={() => { sessionStorage.setItem("social_redirect", "/pro"); window.location.href = `${API}/api/auth/social/google`; }}
            className="w-full py-3.5 bg-white border border-gray-300 rounded-xl flex items-center justify-center gap-2 text-gray-700 text-[15px] font-bold hover:bg-gray-50 transition-all active:scale-[0.99]">
            <svg viewBox="0 0 24 24" className="w-5 h-5"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" /><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" /><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" /><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" /></svg>
            Google로 시작하기
          </button>
          <p className="text-center text-xs text-gray-400 pt-1 leading-relaxed">별도 아이디·비밀번호 없이 카카오·네이버·구글 계정으로<br />회원가입과 로그인을 한 번에.</p>
        </div>

        {/* 기존 이메일 회원 (작은 fallback) */}
        <div className="max-w-sm mx-auto text-center">
          <button type="button" onClick={() => setShowEmail(s => !s)} className="text-xs text-gray-400 underline hover:text-gray-600 transition-colors">기존 이메일 회원이신가요?</button>
        </div>

        {showEmail && (
        <div className="max-w-sm mx-auto space-y-4">
            <div className="flex rounded-lg border border-gray-200 p-0.5 bg-gray-50">
              {(["login", "signup"] as AuthTab[]).map(t => (
                <button key={t} onClick={() => { setAuthTab(t); setError(""); }}
                  className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${authTab === t ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}>
                  {t === "login" ? "로그인" : "회원가입"}
                </button>
              ))}
            </div>

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
        )}
      </div>
    </div>
  );

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
      <>
        <ProSecretary
          onClose={handleLogout}
          planStatus={planStatus}
          onUpgrade={() => setShowPayment(true)}
          userType={userData?.user_type || "business"}
          onRequireLogin={(reason?: string) => { setLoginReason(reason || ""); setShowLogin(true); setError(""); }}
        />
        {/* 무료 체험 소진 등으로 onUpgrade 호출 시 결제 모달이 떠야 함 (pro 분기에도 렌더 필수) */}
        {showPayment && (
          <PaymentModal
            mode="pro"
            planStatus={planStatus}
            userType={userData?.user_type || "business"}
            onSuccess={handlePaymentSuccess}
            onClose={() => setShowPayment(false)}
          />
        )}
        {/* 비로그인 상담 진입 → '상담 시작' 시점 로그인 (상담 화면 위 오버레이) */}
        {LoginModal}
      </>
    );
  }

  // ── 로그인 / 회원가입 ──
  if (authState === "auth") {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center px-4 py-12">
        <div className="w-full max-w-2xl space-y-10">

          {/* ── 2 제품 카드 (첫 진입) ── */}
          <div className="space-y-3">
            <div>
              <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-violet-100 text-violet-700 text-[11px] font-bold">전문가 전용 · PRO</span>
              <h2 className="mt-3 text-2xl font-bold text-gray-900">무엇을 시작하시겠습니까?</h2>
              <p className="mt-1 text-sm text-gray-500">카드를 선택하면 시작됩니다. (로그인이 필요하면 그때 안내됩니다)</p>
            </div>
            {ProductCards}
          </div>

          {LoginModal}
        </div>
      </div>
    );
  }

  // ── 대시보드 ──
  return (
    <>
      <div className="min-h-screen bg-white flex flex-col items-center justify-center px-4 py-12">
        <div className="w-full max-w-2xl space-y-6">

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

          {/* 2 제품 카드 */}
          <h2 className="text-lg font-bold text-gray-900 text-center">무엇을 시작하시겠습니까?</h2>
          {ProductCards}

          {/* 상담 프로그램 플랜 상태 (작게) */}
          {!isPro && (
            trialRemaining > 0 ? (
              <p className="text-center text-[12px] text-gray-500">
                상담 프로그램 무료 체험 <span className="font-bold text-violet-700">{trialRemaining}회</span> 남음 ·{" "}
                <button onClick={() => setShowPayment(true)} className="text-violet-700 underline hover:text-violet-900">PRO 결제</button>
              </p>
            ) : (
              <p className="text-center text-[12px] text-gray-500">
                이번 달 무료 체험 소진 ·{" "}
                <button onClick={() => setShowPayment(true)} className="text-violet-700 underline hover:text-violet-900 font-semibold">PRO 플랜 결제하기</button>
              </p>
            )
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
