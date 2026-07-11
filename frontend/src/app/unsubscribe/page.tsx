"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "https://govmatch-production.up.railway.app";

/** 이메일 푸터 수신거부 링크 랜딩 — 로그인 불필요(HMAC 토큰), 원클릭 전 채널 중단 */
export default function UnsubscribePage() {
  const [params, setParams] = useState<{ bn: string; token: string } | null>(null);
  const [state, setState] = useState<"ready" | "busy" | "done" | "error">("ready");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    try {
      const q = new URLSearchParams(window.location.search);
      setParams({ bn: q.get("bn") || "", token: q.get("token") || "" });
    } catch {
      setParams({ bn: "", token: "" });
    }
  }, []);

  const run = async () => {
    if (!params?.bn || !params?.token) {
      setState("error");
      setMsg("잘못된 링크입니다. 이메일의 수신 거부 링크로 다시 접속해주세요.");
      return;
    }
    setState("busy");
    try {
      const res = await fetch(`${API}/api/unsubscribe?bn=${encodeURIComponent(params.bn)}&token=${encodeURIComponent(params.token)}`);
      const data = await res.json();
      if (res.ok) {
        setState("done");
        setMsg(data.message || "수신거부가 완료되었습니다.");
      } else {
        setState("error");
        setMsg(data.detail || "처리에 실패했습니다.");
      }
    } catch {
      setState("error");
      setMsg("서버 연결에 실패했습니다.");
    }
  };

  return (
    <div className="min-h-screen bg-white flex items-center justify-center px-4">
      <div className="w-full max-w-sm text-center space-y-5">
        <h1 className="text-xl font-bold text-slate-900">맞춤 공고 알림 수신 거부</h1>
        {state === "done" ? (
          <>
            <p className="text-sm text-slate-600">{msg}</p>
            <a href="/" className="inline-block text-sm text-indigo-600 underline">지원금AI로 돌아가기</a>
          </>
        ) : (
          <>
            <p className="text-sm text-slate-500 leading-relaxed">
              아래 버튼을 누르면 이메일·푸시·카카오 맞춤 공고 알림이 모두 중단됩니다.
              <br />언제든 마이페이지의 알림 설정에서 다시 켤 수 있습니다.
            </p>
            <button
              onClick={run}
              disabled={state === "busy"}
              className="w-full py-3 rounded-lg bg-slate-900 text-white text-sm font-bold hover:bg-slate-700 transition-all disabled:opacity-50"
            >
              {state === "busy" ? "처리 중..." : "수신 거부하기"}
            </button>
            {state === "error" && <p className="text-sm text-rose-500">{msg}</p>}
          </>
        )}
      </div>
    </div>
  );
}
