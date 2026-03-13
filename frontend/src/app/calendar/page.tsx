"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useToast } from "@/components/ui/Toast";

const API = process.env.NEXT_PUBLIC_API_URL;

interface SavedItem {
  id: number;
  announcement_id: number;
  memo: string;
  saved_at: string;
  title: string;
  deadline_date: string | null;
  origin_url: string | null;
  department: string | null;
  category: string | null;
  support_amount: string | null;
  origin_source: string | null;
}

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

function daysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function firstDayOfMonth(year: number, month: number) {
  return new Date(year, month, 1).getDay();
}

function formatDate(y: number, m: number, d: number) {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

function getDDay(dateStr: string | null): string {
  if (!dateStr) return "상시";
  const diff = Math.ceil((new Date(dateStr).getTime() - Date.now()) / 86400000);
  if (diff < 0) return "마감";
  if (diff === 0) return "D-Day";
  return `D-${diff}`;
}

export default function CalendarPage() {
  const { toast } = useToast();
  const [items, setItems] = useState<SavedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const today = new Date();
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth());

  const bn = typeof window !== "undefined" ? localStorage.getItem("saved_bn") || "" : "";

  const fetchItems = useCallback(async () => {
    if (!bn) { setLoading(false); return; }
    try {
      const res = await fetch(`${API}/api/saved/${bn}`);
      const data = await res.json();
      if (data.status === "SUCCESS") setItems(data.data);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [bn]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  const deadlineMap = useMemo(() => {
    const map: Record<string, SavedItem[]> = {};
    items.forEach(item => {
      const key = item.deadline_date || "상시";
      if (!map[key]) map[key] = [];
      map[key].push(item);
    });
    return map;
  }, [items]);

  const handleDelete = async (savedId: number) => {
    try {
      const res = await fetch(`${API}/api/saved/${savedId}`, { method: "DELETE" });
      const data = await res.json();
      if (data.status === "SUCCESS") {
        toast("일정이 삭제되었습니다.", "success");
        fetchItems();
      }
    } catch {
      toast("삭제 실패", "error");
    }
  };

  const prevMonth = () => {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11); }
    else setViewMonth(m => m - 1);
    setSelectedDate(null);
  };

  const nextMonth = () => {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0); }
    else setViewMonth(m => m + 1);
    setSelectedDate(null);
  };

  const totalDays = daysInMonth(viewYear, viewMonth);
  const startDay = firstDayOfMonth(viewYear, viewMonth);
  const todayStr = formatDate(today.getFullYear(), today.getMonth(), today.getDate());

  const selectedItems = selectedDate ? (deadlineMap[selectedDate] || []) : [];

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
      </div>
    );
  }

  if (!bn) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4 p-6">
        <p className="text-slate-500 text-sm font-medium">로그인이 필요합니다.</p>
        <a href="/" className="px-6 py-3 bg-indigo-600 text-white rounded-xl font-bold text-sm hover:bg-indigo-700 transition-all">
          메인으로 이동
        </a>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-4 md:px-8 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <a href="/" className="text-slate-400 hover:text-slate-600 transition-colors text-sm font-bold">
              ← 대시보드
            </a>
            <div className="h-4 w-px bg-slate-200" />
            <h1 className="text-lg md:text-xl font-black text-slate-900 tracking-tight">
              📅 나의 지원 일정
            </h1>
          </div>
          <span className="text-xs font-bold text-slate-400">
            저장 {items.length}건
          </span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto p-4 md:p-8 space-y-6">
        {/* Stats summary */}
        {items.length > 0 && (() => {
          const withDate = items.filter(i => i.deadline_date);
          const noDate = items.filter(i => !i.deadline_date);
          return (
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                <p className="text-2xl font-black text-indigo-600">{items.length}</p>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">전체 저장</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                <p className="text-2xl font-black text-emerald-600">{withDate.length}</p>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">마감일 있음</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                <p className="text-2xl font-black text-sky-600">{noDate.length}</p>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">상시모집</p>
              </div>
            </div>
          );
        })()}

        {/* Calendar */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          {/* Month nav */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
            <button onClick={prevMonth} className="p-2 hover:bg-slate-50 rounded-lg transition-colors text-slate-500 font-bold">
              ‹
            </button>
            <h2 className="text-base md:text-lg font-black text-slate-900">
              {viewYear}년 {viewMonth + 1}월
            </h2>
            <button onClick={nextMonth} className="p-2 hover:bg-slate-50 rounded-lg transition-colors text-slate-500 font-bold">
              ›
            </button>
          </div>

          {/* Weekday headers */}
          <div className="grid grid-cols-7 border-b border-slate-100">
            {WEEKDAYS.map((d, i) => (
              <div key={d} className={`py-2.5 text-center text-[10px] font-black uppercase tracking-wider ${i === 0 ? "text-rose-400" : i === 6 ? "text-blue-400" : "text-slate-400"}`}>
                {d}
              </div>
            ))}
          </div>

          {/* Day grid */}
          <div className="grid grid-cols-7">
            {Array.from({ length: startDay }).map((_, i) => (
              <div key={`empty-${i}`} className="h-16 md:h-20 border-b border-r border-slate-50" />
            ))}
            {Array.from({ length: totalDays }).map((_, i) => {
              const day = i + 1;
              const dateStr = formatDate(viewYear, viewMonth, day);
              const dayOfWeek = (startDay + i) % 7;
              const isToday = dateStr === todayStr;
              const hasSaved = !!deadlineMap[dateStr];
              const isSelected = dateStr === selectedDate;
              const count = deadlineMap[dateStr]?.length || 0;

              return (
                <button
                  key={day}
                  onClick={() => setSelectedDate(isSelected ? null : dateStr)}
                  className={`h-14 sm:h-16 md:h-20 border-b border-r border-slate-50 flex flex-col items-center justify-start pt-1.5 gap-1 transition-all relative ${
                    isSelected ? "bg-indigo-50" : hasSaved ? "hover:bg-slate-50" : "hover:bg-slate-50/50"
                  }`}
                >
                  <span className={`text-xs md:text-sm font-bold leading-none ${
                    isToday ? "bg-indigo-600 text-white w-7 h-7 rounded-full flex items-center justify-center" :
                    dayOfWeek === 0 ? "text-rose-400" :
                    dayOfWeek === 6 ? "text-blue-400" : "text-slate-700"
                  }`}>
                    {day}
                  </span>
                  {hasSaved && (
                    <div className="flex items-center gap-0.5">
                      <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full" />
                      {count > 1 && <span className="text-[8px] font-black text-indigo-500">{count}</span>}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* "상시모집" items — always visible after calendar */}
        {deadlineMap["상시"] && deadlineMap["상시"].length > 0 && (
          <div className="space-y-3">
            <h3 className="text-sm font-black text-slate-800 px-1 flex items-center gap-2">
              <span className="px-2 py-0.5 bg-sky-100 text-sky-600 rounded-full text-[10px] font-black">상시</span>
              상시모집 공고 <span className="text-slate-400 font-bold">— {deadlineMap["상시"].length}건</span>
            </h3>
            {deadlineMap["상시"].map(item => (
              <div key={item.id} className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center gap-3 shadow-sm">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="px-2 py-0.5 text-[9px] font-black rounded-full bg-sky-50 text-sky-600">상시</span>
                    {item.department && (
                      <span className="text-[9px] font-bold text-slate-400">{item.department}</span>
                    )}
                  </div>
                  <h4 className="font-bold text-slate-900 text-sm leading-snug mb-1">{item.title}</h4>
                  <p className="text-[10px] text-slate-400">{item.support_amount || "지원 규모 미정"}</p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {item.origin_url && (
                    <a
                      href={item.origin_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 bg-slate-900 text-white rounded-lg text-xs font-bold hover:bg-indigo-600 transition-all"
                    >
                      상세 보기
                    </a>
                  )}
                  <button
                    onClick={() => handleDelete(item.id)}
                    className="px-3 py-2 text-rose-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-all text-xs font-bold"
                  >
                    삭제
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Selected date items */}
        {selectedDate && (
          <div className="space-y-3 animate-in fade-in slide-in-from-bottom-4 duration-300">
            <h3 className="text-sm font-black text-slate-800 px-1">
              {selectedDate} <span className="text-slate-400 font-bold">— {selectedItems.length}건</span>
            </h3>
            {selectedItems.length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
                <p className="text-sm text-slate-400">이 날짜에 저장된 공고가 없습니다.</p>
              </div>
            ) : (
              selectedItems.map(item => (
                <div key={item.id} className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center gap-3 shadow-sm">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className={`px-2 py-0.5 text-[9px] font-black rounded-full ${
                        getDDay(item.deadline_date).startsWith("D-") && parseInt(getDDay(item.deadline_date).slice(2)) <= 3
                          ? "bg-rose-100 text-rose-700"
                          : "bg-indigo-50 text-indigo-600"
                      }`}>
                        {getDDay(item.deadline_date)}
                      </span>
                      {item.department && (
                        <span className="text-[9px] font-bold text-slate-400">{item.department}</span>
                      )}
                    </div>
                    <h4 className="font-bold text-slate-900 text-sm leading-snug mb-1">{item.title}</h4>
                    <p className="text-[10px] text-slate-400">{item.support_amount || "지원 규모 미정"}</p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {item.origin_url && (
                      <a
                        href={item.origin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-4 py-2 bg-slate-900 text-white rounded-lg text-xs font-bold hover:bg-indigo-600 transition-all"
                      >
                        상세 보기
                      </a>
                    )}
                    <button
                      onClick={() => handleDelete(item.id)}
                      className="px-3 py-2 text-rose-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-all text-xs font-bold"
                    >
                      삭제
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </main>
    </div>
  );
}
