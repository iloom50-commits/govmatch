"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useToast } from "@/components/ui/Toast";

const API = process.env.NEXT_PUBLIC_API_URL;

interface ConsultItem {
  id: number;
  announcement_id: number;
  announcement_title: string;
  category: string;
  department: string;
  deadline_date: string;
  support_amount: string;
  conclusion: string;
  feedback: string;
  created_at: string;
  preview: string;
  message_count: number;
}

const CONC_MAP: Record<string, { label: string; color: string; emoji: string }> = {
  eligible: { label: "신청 가능", color: "bg-emerald-100 text-emerald-700 border-emerald-200", emoji: "✅" },
  conditional: { label: "조건부", color: "bg-amber-100 text-amber-700 border-amber-200", emoji: "⚠️" },
  ineligible: { label: "대상 아님", color: "bg-slate-100 text-slate-600 border-slate-200", emoji: "❌" },
  free_chat: { label: "자금상담", color: "bg-blue-50 text-blue-600 border-blue-200", emoji: "💰" },
  "": { label: "진행 중", color: "bg-indigo-50 text-indigo-600 border-indigo-200", emoji: "💬" },
};

export default function MyConsultsPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [items, setItems] = useState<ConsultItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    const token = localStorage.getItem("auth_token");
    if (!token) {
      router.replace("/");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/my/consults?filter=${filter}&size=50`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        if (res.status === 401) {
          localStorage.removeItem("auth_token");
          router.replace("/");
          return;
        }
        throw new Error("목록 로딩 실패");
      }
      const data = await res.json();
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      toast("목록을 불러오지 못했습니다.", "error");
    } finally {
      setLoading(false);
    }
  }, [filter, router, toast]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (id: number) => {
    if (!confirm("이 상담 기록을 삭제하시겠습니까?\n삭제 후 복구할 수 없습니다.")) return;
    const token = localStorage.getItem("auth_token");
    try {
      const res = await fetch(`${API}/api/my/consults/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("삭제 실패");
      toast("삭제되었습니다.", "success");
      setItems(prev => prev.filter(item => item.id !== id));
      setTotal(prev => prev - 1);
    } catch {
      toast("삭제에 실패했습니다.", "error");
    }
  };

  const filtered = items.filter(item =>
    !search ||
    item.announcement_title.toLowerCase().includes(search.toLowerCase()) ||
    item.category.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <main className="min-h-screen bg-slate-50 py-6 md:py-10 px-4">
      <div className="max-w-4xl mx-auto">
        {/* 헤더 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <Link href="/" className="text-[12px] text-slate-500 hover:text-indigo-600 mb-1 inline-block">← 홈으로</Link>
            <h1 className="text-xl md:text-2xl font-black text-slate-900 mt-1">
              📋 내 상담 기록
            </h1>
            <p className="text-[12px] text-slate-500 mt-1">총 {total}건의 상담 기록이 있습니다</p>
          </div>
        </div>

        {/* 필터·검색 */}
        <div className="mb-4 flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="공고명 / 자금상담 검색..."
            className="flex-1 px-3.5 py-2 bg-white border border-slate-200 rounded-lg text-[13px] outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300"
          />
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-2 bg-white border border-slate-200 rounded-lg text-[13px] outline-none focus:ring-2 focus:ring-indigo-200"
          >
            <option value="all">전체</option>
            <option value="eligible">✅ 신청 가능</option>
            <option value="conditional">⚠️ 조건부</option>
            <option value="ineligible">❌ 대상 아님</option>
          </select>
        </div>

        {/* 목록 */}
        {loading ? (
          <div className="bg-white rounded-xl p-8 text-center text-slate-400 text-[13px]">
            불러오는 중...
          </div>
        ) : filtered.length === 0 ? (
          <div className="bg-white rounded-xl p-10 text-center">
            <div className="text-4xl mb-2">📭</div>
            <p className="text-slate-500 text-[14px] font-semibold">
              {items.length === 0 ? "아직 상담 기록이 없습니다" : "검색 결과가 없습니다"}
            </p>
            <p className="text-slate-400 text-[12px] mt-1">
              공고 카드에서 AI 상담을 시작하거나, 자금상담 AI를 이용해보세요
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((item) => {
              const conc = CONC_MAP[item.conclusion] || CONC_MAP[""];
              return (
                <div key={item.id} className="bg-white rounded-xl border border-slate-200 hover:border-indigo-300 hover:shadow-md transition-all">
                  <div className="p-4">
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="flex-1 min-w-0">
                        <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${conc.color} mb-1.5`}>
                          <span>{conc.emoji}</span>
                          <span>{conc.label}</span>
                        </div>
                        <h3 className="text-[14px] font-bold text-slate-900 line-clamp-2">
                          {item.announcement_title}
                        </h3>
                      </div>
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-300 hover:text-rose-500 hover:bg-rose-50 transition-all flex-shrink-0"
                        title="삭제"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>

                    <div className="flex flex-wrap gap-2 text-[11px] text-slate-500 mb-2">
                      {item.department && <span>🏛 {item.department}</span>}
                      {item.support_amount && <span className="text-emerald-600 font-semibold">💰 {item.support_amount}</span>}
                      {item.deadline_date && item.deadline_date !== "None" && <span>📅 {item.deadline_date.slice(0, 10)}</span>}
                      <span>💬 {item.message_count}턴</span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-slate-400">
                        {new Date(item.created_at).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </span>
                      <Link
                        href={`/my/consults/${item.id}`}
                        className="px-3 py-1.5 bg-indigo-50 text-indigo-600 hover:bg-indigo-100 rounded-lg text-[11px] font-bold transition-all"
                      >
                        상세 보기 →
                      </Link>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
