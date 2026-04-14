"use client";
import { useCallback, useEffect, useRef, useState } from "react";

interface Candidate {
  code: string;
  name: string;
  description?: string;
  similarity?: number;
  reason?: string;
}

interface IndustryPickerProps {
  // 현재 선택된 업종 라벨 (표시용). 부모가 관리.
  value?: string;
  // 선택된 code만 반환 (없으면 null)
  selectedCode?: string;
  onSelect: (code: string, name: string) => void;
  placeholder?: string;
  dark?: boolean;
  label?: string;
  sublabel?: string;
}

// KSIC 임베딩 기반 업종 추천 — 자유 입력 → Top 5 카드 → 클릭 선택
export default function IndustryPicker({
  value,
  selectedCode,
  onSelect,
  placeholder = "예: 화장품, IT서비스, 음식점",
  dark = false,
  label = "사업내용",
  sublabel = "(선택 — AI가 유사 업종 추천)",
}: IndustryPickerProps) {
  const [query, setQuery] = useState(value || "");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const timerRef = useRef<any>(null);
  const API = process.env.NEXT_PUBLIC_API_URL;

  const search = useCallback(async (q: string) => {
    if (!q || q.trim().length < 1) {
      setCandidates([]);
      setSearched(false);
      return;
    }
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/industry-recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company_name: q, business_content: q }),
      });
      if (r.ok) {
        const d = await r.json();
        const items: Candidate[] = Array.isArray(d.data?.candidates)
          ? d.data.candidates
          : Array.isArray(d.data)
            ? d.data
            : [];
        setCandidates(items.slice(0, 5));
        setSearched(true);
      }
    } catch (e) {
      console.error("[IndustryPicker]", e);
    } finally {
      setLoading(false);
    }
  }, [API]);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => search(query), 500);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [query, search]);

  const clearSelection = () => {
    onSelect("", "");
    setQuery("");
    setCandidates([]);
    setSearched(false);
  };

  const inputCls = dark
    ? "w-full bg-white/[0.03] border border-white/10 rounded-xl px-4 py-3 text-[14px] text-slate-100 placeholder:text-slate-500 focus:border-violet-400/50 focus:outline-none"
    : "w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-[14px] text-slate-800 placeholder:text-slate-400 focus:border-violet-400 focus:outline-none";

  return (
    <div>
      <p className={`text-[12px] font-bold mb-1.5 ${dark ? "text-slate-300" : "text-slate-600"}`}>
        {label} <span className={dark ? "text-slate-500" : "text-slate-400"}>{sublabel}</span>
      </p>

      {/* 현재 선택된 업종 표시 */}
      {selectedCode && value ? (
        <div className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border ${
          dark ? "bg-violet-500/10 border-violet-500/30" : "bg-violet-50 border-violet-200"
        }`}>
          <div className="flex-1 min-w-0">
            <p className={`text-[13px] font-bold ${dark ? "text-violet-200" : "text-violet-800"} truncate`}>
              {value}
            </p>
            <p className={`text-[11px] ${dark ? "text-violet-400" : "text-violet-600"}`}>
              KSIC {selectedCode}
            </p>
          </div>
          <button
            type="button"
            onClick={clearSelection}
            className={`text-[11px] px-2 py-1 rounded-full ${
              dark ? "bg-white/5 text-slate-300 hover:bg-white/10" : "bg-white text-slate-600 hover:bg-slate-50"
            } border ${dark ? "border-white/10" : "border-slate-200"}`}
          >
            변경
          </button>
        </div>
      ) : (
        <>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={placeholder}
            className={inputCls}
          />
          {loading && (
            <p className={`text-[11px] mt-1.5 ${dark ? "text-slate-500" : "text-slate-400"}`}>
              🔎 유사 업종 검색 중...
            </p>
          )}
          {!loading && searched && candidates.length === 0 && (
            <p className={`text-[11px] mt-1.5 ${dark ? "text-amber-400" : "text-amber-600"}`}>
              일치하는 업종을 찾지 못했습니다. 다른 키워드로 시도해보세요.
            </p>
          )}
          {!loading && candidates.length > 0 && (
            <div className="mt-2 space-y-1.5">
              {candidates.map((c) => (
                <button
                  key={c.code}
                  type="button"
                  onClick={() => onSelect(c.code, c.name)}
                  className={`w-full text-left p-2.5 rounded-xl border transition-all active:scale-[0.98] ${
                    dark
                      ? "bg-white/[0.03] border-white/10 hover:border-violet-400/50 hover:bg-violet-500/10"
                      : "bg-white border-slate-200 hover:border-violet-300 hover:bg-violet-50"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className={`text-[13px] font-bold ${dark ? "text-slate-100" : "text-slate-800"} truncate`}>
                        {c.name}
                      </p>
                      {c.description && c.description !== c.name && (
                        <p className={`text-[11px] mt-0.5 ${dark ? "text-slate-400" : "text-slate-500"} truncate`}>
                          {c.description}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-0.5 flex-shrink-0">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono ${
                        dark ? "bg-white/5 text-slate-400" : "bg-slate-100 text-slate-500"
                      }`}>
                        {c.code}
                      </span>
                      {c.similarity !== undefined && c.similarity > 0 && (
                        <span className={`text-[10px] ${
                          dark ? "text-violet-400" : "text-violet-600"
                        } font-semibold`}>
                          {Math.round(c.similarity * 100)}%
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
