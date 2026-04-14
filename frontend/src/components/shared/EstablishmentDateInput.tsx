"use client";
import { useState } from "react";

interface Props {
  value: string;               // 'YYYY-MM-DD' | 'YYYY'
  onChange: (v: string) => void;
  dark?: boolean;
  label?: string;
}

// 설립연도/일자 입력 — 텍스트 + 달력 모두 지원
// 사용자가 "2020"처럼 연도만 입력해도 허용하고, 달력 아이콘 클릭 시 날짜 선택
export default function EstablishmentDateInput({
  value,
  onChange,
  dark = false,
  label = "설립연도",
}: Props) {
  const [text, setText] = useState(value || "");
  const [showPicker, setShowPicker] = useState(false);

  const handleTextChange = (v: string) => {
    // 숫자와 하이픈만 허용
    let clean = v.replace(/[^0-9-]/g, "");
    if (clean.length > 10) clean = clean.slice(0, 10);
    // YYYY / YYYY-MM / YYYY-MM-DD 허용
    setText(clean);
    onChange(clean);
  };

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value; // YYYY-MM-DD
    setText(v);
    onChange(v);
    setShowPicker(false);
  };

  const inputCls = dark
    ? "flex-1 bg-white/[0.03] border border-white/10 rounded-xl px-4 py-3 text-[14px] text-slate-100 placeholder:text-slate-500 focus:border-violet-400/50 focus:outline-none"
    : "flex-1 bg-white border border-slate-200 rounded-xl px-4 py-3 text-[14px] text-slate-800 placeholder:text-slate-400 focus:border-violet-400 focus:outline-none";

  const btnCls = dark
    ? "px-3 py-3 rounded-xl bg-violet-500/10 border border-violet-500/30 text-violet-300 hover:bg-violet-500/20 transition-all"
    : "px-3 py-3 rounded-xl bg-violet-50 border border-violet-200 text-violet-600 hover:bg-violet-100 transition-all";

  return (
    <div>
      <p className={`text-[12px] font-bold mb-1.5 ${dark ? "text-slate-300" : "text-slate-600"}`}>
        {label} <span className={dark ? "text-slate-500" : "text-slate-400"}>(선택 — 연도만 or 전체 날짜)</span>
      </p>
      <div className="flex gap-2 relative">
        <input
          type="text"
          value={text}
          onChange={(e) => handleTextChange(e.target.value)}
          placeholder="2020 또는 2020-05-10"
          className={inputCls}
        />
        <button
          type="button"
          onClick={() => setShowPicker(!showPicker)}
          className={btnCls}
          title="달력에서 선택"
        >
          📅
        </button>
        {showPicker && (
          <div className={`absolute right-0 top-full mt-2 z-50 p-3 rounded-xl shadow-lg border ${
            dark ? "bg-[#1a1c30] border-white/10" : "bg-white border-slate-200"
          }`}>
            <input
              type="date"
              value={text.length === 10 ? text : ""}
              onChange={handleDateChange}
              className={`text-[13px] px-3 py-2 rounded-lg border ${
                dark ? "bg-white/[0.03] border-white/10 text-slate-100" : "bg-white border-slate-200 text-slate-800"
              }`}
            />
            <button
              type="button"
              onClick={() => setShowPicker(false)}
              className={`ml-2 text-[11px] px-2 py-1 rounded ${
                dark ? "text-slate-400 hover:text-slate-200" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              닫기
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
