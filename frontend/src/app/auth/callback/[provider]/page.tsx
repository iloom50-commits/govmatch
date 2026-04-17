"use client";

import { Suspense, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL;

export default function SocialCallbackPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen flex items-center justify-center p-6">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-slate-500 text-sm font-medium">로그인 처리 중...</p>
        </div>
      </main>
    }>
      <SocialCallbackInner />
    </Suspense>
  );
}

function SocialCallbackInner() {
  const params = useParams();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"loading" | "error">("loading");
  const [errorMsg, setErrorMsg] = useState("");

  const provider = params.provider as string;
  const code = searchParams.get("code");

  useEffect(() => {
    if (!code || !provider) {
      setStatus("error");
      setErrorMsg("인증 정보가 없습니다.");
      return;
    }

    (async () => {
      try {
        const res = await fetch(`${API}/api/auth/social/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, provider }),
        });
        const data = await res.json();

        if (data.status === "SUCCESS" && data.token) {
          localStorage.setItem("auth_token", data.token);
          if (data.user?.email) localStorage.setItem("last_email", data.user.email);

          // is_new_user면 온보딩 필요 플래그 설정
          if (data.is_new_user) {
            localStorage.setItem("needs_onboarding", "true");
          }

          // 메인 페이지로 리다이렉트
          window.location.href = "/";
        } else {
          setStatus("error");
          setErrorMsg(data.detail || "로그인에 실패했습니다.");
        }
      } catch {
        setStatus("error");
        setErrorMsg("서버와 통신 중 오류가 발생했습니다.");
      }
    })();
  }, [code, provider]);

  if (status === "error") {
    return (
      <main className="min-h-screen flex items-center justify-center p-6">
        <div className="text-center">
          <p className="text-rose-500 font-bold mb-2">{errorMsg}</p>
          <button
            onClick={() => window.location.href = "/"}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-bold"
          >
            홈으로 돌아가기
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-6">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-slate-500 text-sm font-medium">로그인 처리 중...</p>
      </div>
    </main>
  );
}
