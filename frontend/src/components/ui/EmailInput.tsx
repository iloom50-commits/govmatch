"use client";

import { useState, useEffect } from "react";

const DOMAINS = [
  "naver.com",
  "gmail.com",
  "daum.net",
  "kakao.com",
  "hanmail.net",
  "nate.com",
];

interface EmailInputProps {
  value: string;
  onChange: (email: string) => void;
  label?: string;
}

export default function EmailInput({ value, onChange, label = "매칭 리포트 수신 이메일" }: EmailInputProps) {
  const [emailId, setEmailId] = useState("");
  const [domain, setDomain] = useState("naver.com");
  const [customDomain, setCustomDomain] = useState("");

  useEffect(() => {
    if (value && value.includes("@") && !emailId) {
      const [id, dom] = value.split("@");
      setEmailId(id);
      if (DOMAINS.includes(dom)) {
        setDomain(dom);
      } else if (dom) {
        setDomain("direct");
        setCustomDomain(dom);
      }
    }
  }, [value]);

  const updateEmail = (id: string, dom: string, custom: string) => {
    const finalDomain = dom === "direct" ? custom : dom;
    if (id && finalDomain) {
      onChange(`${id}@${finalDomain}`);
    } else if (id) {
      onChange(id);
    } else {
      onChange("");
    }
  };

  const inputBase =
    "p-3.5 border border-white/80 rounded-2xl bg-white/50 focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-bold outline-none shadow-inner";

  return (
    <div className="space-y-1.5">
      <label className="text-[10px] font-black text-indigo-500 uppercase tracking-[0.2em] ml-2">
        {label}
      </label>
      <div className="flex items-center gap-1.5">
        <input
          type="text"
          placeholder="아이디"
          className={`flex-1 min-w-0 ${inputBase}`}
          value={emailId}
          onChange={(e) => {
            const id = e.target.value.replace(/[@\s]/g, "");
            setEmailId(id);
            updateEmail(id, domain, customDomain);
          }}
        />
        <span className="text-slate-400 font-black text-sm flex-shrink-0">@</span>
        {domain === "direct" ? (
          <input
            type="text"
            placeholder="도메인 입력"
            className={`flex-1 min-w-0 ${inputBase}`}
            value={customDomain}
            onChange={(e) => {
              const val = e.target.value.replace(/[@\s]/g, "");
              setCustomDomain(val);
              updateEmail(emailId, "direct", val);
            }}
          />
        ) : (
          <select
            className={`flex-1 min-w-0 ${inputBase} appearance-none cursor-pointer`}
            value={domain}
            onChange={(e) => {
              setDomain(e.target.value);
              updateEmail(emailId, e.target.value, customDomain);
            }}
          >
            {DOMAINS.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
            <option value="direct">직접입력</option>
          </select>
        )}
      </div>
      {domain === "direct" && (
        <button
          type="button"
          onClick={() => {
            setDomain("naver.com");
            updateEmail(emailId, "naver.com", "");
          }}
          className="text-[10px] text-indigo-500 font-black ml-2 hover:text-indigo-700 transition-colors"
        >
          목록에서 선택
        </button>
      )}
    </div>
  );
}
