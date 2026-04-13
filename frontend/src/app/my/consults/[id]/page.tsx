"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { useToast } from "@/components/ui/Toast";
import { generateConsultReportHTML } from "@/components/consult/reportTemplate";

const API = process.env.NEXT_PUBLIC_API_URL;

interface ConsultMessage {
  role: "user" | "assistant";
  text: string;
  done?: boolean;
}

interface ConsultDetail {
  id: number;
  announcement_id: number;
  announcement_title: string;
  category: string;
  department: string;
  region: string;
  deadline_date: string;
  support_amount: string;
  origin_url: string;
  conclusion: string;
  feedback: string;
  created_at: string;
  messages: ConsultMessage[];
}

const CONC_BADGE: Record<string, { label: string; color: string; emoji: string }> = {
  eligible: { label: "신청 가능", color: "bg-emerald-500", emoji: "✅" },
  conditional: { label: "조건부 가능", color: "bg-amber-500", emoji: "⚠️" },
  ineligible: { label: "대상 아님", color: "bg-slate-500", emoji: "❌" },
};

export default function ConsultDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { toast } = useToast();
  const id = params?.id as string;

  const [consult, setConsult] = useState<ConsultDetail | null>(null);
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const token = localStorage.getItem("auth_token");
    if (!token) { router.replace("/"); return; }
    setLoading(true);
    try {
      const [consultRes, profileRes] = await Promise.all([
        fetch(`${API}/api/my/consults/${id}`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (!consultRes.ok) {
        toast("상담 기록을 찾을 수 없습니다", "error");
        router.replace("/my/consults");
        return;
      }
      const data = await consultRes.json();
      setConsult(data.consult);
      if (profileRes.ok) {
        const pd = await profileRes.json();
        setProfile(pd.user);
      }
    } catch {
      toast("불러오기 실패", "error");
    } finally {
      setLoading(false);
    }
  }, [id, router, toast]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async () => {
    if (!confirm("이 상담 기록을 삭제하시겠습니까?")) return;
    const token = localStorage.getItem("auth_token");
    try {
      const res = await fetch(`${API}/api/my/consults/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error();
      toast("삭제되었습니다", "success");
      router.replace("/my/consults");
    } catch {
      toast("삭제 실패", "error");
    }
  };

  const handlePrint = () => {
    if (!consult) return;
    const html = generateConsultReportHTML({
      announcement: {
        title: consult.announcement_title,
        department: consult.department,
        category: consult.category,
        region: consult.region,
        deadline_date: consult.deadline_date,
        support_amount: consult.support_amount,
      },
      profile: profile || {},
      messages: consult.messages,
      conclusion: consult.conclusion,
      created_at: consult.created_at,
    });
    const w = window.open("", "_blank");
    if (w) {
      w.document.write(html);
      w.document.close();
      setTimeout(() => w.print(), 500);
    }
  };

  if (loading || !consult) {
    return (
      <main className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-slate-400 text-[14px]">불러오는 중...</div>
      </main>
    );
  }

  const badge = CONC_BADGE[consult.conclusion];

  return (
    <main className="min-h-screen bg-slate-50 py-6 md:py-10 px-4 pb-24">
      <div className="max-w-3xl mx-auto">
        <Link href="/my/consults" className="text-[12px] text-slate-500 hover:text-indigo-600 mb-4 inline-block">
          ← 상담 기록 목록
        </Link>

        {/* 헤더 카드 */}
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden mb-5">
          <div className="p-5 bg-gradient-to-br from-indigo-50 to-violet-50 border-b border-slate-100">
            {badge && (
              <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-white text-[11px] font-bold ${badge.color} mb-3`}>
                <span>{badge.emoji}</span>
                <span>{badge.label}</span>
              </div>
            )}
            <h1 className="text-lg md:text-xl font-black text-slate-900 mb-2 leading-tight">
              {consult.announcement_title}
            </h1>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-[12px] text-slate-600">
              {consult.department && <span>🏛 {consult.department}</span>}
              {consult.support_amount && <span className="text-emerald-600 font-semibold">💰 {consult.support_amount}</span>}
              {consult.deadline_date && consult.deadline_date !== "None" && <span>📅 마감 {consult.deadline_date.slice(0, 10)}</span>}
            </div>
          </div>
          <div className="p-4 flex items-center justify-between text-[11px] text-slate-500">
            <span>상담일시: {new Date(consult.created_at).toLocaleString("ko-KR")}</span>
            <span>총 {consult.messages.length}개 메시지</span>
          </div>
        </div>

        {/* 대화 내용 */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 mb-5">
          <h2 className="text-[13px] font-bold text-slate-800 mb-4 flex items-center gap-2">
            <span>💬</span> 상담 내용
          </h2>
          <div className="space-y-4">
            {consult.messages.filter(m => !m.done).map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] ${msg.role === "user" ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-800"} rounded-2xl px-4 py-2.5`}>
                  <div className="text-[10px] font-bold opacity-70 mb-1">
                    {msg.role === "user" ? "질문" : "AI 상담사"}
                  </div>
                  <div className="text-[13px] whitespace-pre-wrap leading-relaxed">
                    {msg.text}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 액션 버튼 */}
        <div className="flex gap-2">
          <button
            onClick={handlePrint}
            className="flex-1 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold text-[13px] transition-all active:scale-[0.98] flex items-center justify-center gap-2"
          >
            <span>📄</span>
            <span>보고서 PDF 출력</span>
          </button>
          <button
            onClick={() => router.push(`/?aid=${consult.announcement_id}`)}
            className="flex-1 py-3 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-xl font-bold text-[13px] transition-all active:scale-[0.98]"
          >
            🔗 공고로 이동
          </button>
          <button
            onClick={handleDelete}
            className="py-3 px-4 bg-white border border-rose-200 text-rose-500 hover:bg-rose-50 rounded-xl font-bold text-[13px] transition-all active:scale-[0.98]"
          >
            삭제
          </button>
        </div>
      </div>
    </main>
  );
}
