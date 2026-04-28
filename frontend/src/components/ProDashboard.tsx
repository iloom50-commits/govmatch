"use client";

import { useState, useEffect, useCallback } from "react";
import { useToast } from "@/components/ui/Toast";
import IndustryPicker from "@/components/shared/IndustryPicker";
import EstablishmentDateInput from "@/components/shared/EstablishmentDateInput";

const API = process.env.NEXT_PUBLIC_API_URL;

export type ClientType = "business" | "individual";

export interface ClientProfile {
  id: number;
  client_name: string;
  client_type?: ClientType;
  business_number?: string;
  address_city?: string;
  industry_code?: string;
  industry_name?: string;
  revenue_bracket?: string;
  employee_count_bracket?: string;
  establishment_date?: string;
  interests?: string;
  memo?: string;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  tags?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

const INDIVIDUAL_INTEREST_OPTIONS = ["취업", "주거", "교육", "청년", "출산", "육아", "다자녀", "장학금", "의료", "장애", "저소득", "노인", "문화"];

interface ConsultHistory {
  id: number;
  announcement_id: number | null;
  announcement_title: string | null;
  consult_label?: string;
  category: string;
  conclusion: string;
  feedback: string;
  created_at: string;
  message_count: number;
  last_question: string;
}

interface Report {
  id: number;
  client_profile_id: number;
  client_name: string;
  title: string;
  summary: string;
  total_eligible: number;
  total_conditional: number;
  total_ineligible: number;
  created_at: string;
}

type Tab = "clients" | "history" | "reports";

export default function ProDashboard({ onClose }: { onClose: () => void }) {
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("clients");
  const [token, setToken] = useState("");
  const [clientType, setClientType] = useState<ClientType>("business");

  useEffect(() => {
    setToken(localStorage.getItem("auth_token") || "");
  }, []);

  const headers = useCallback(() => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  }), [token]);

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="w-0 lg:w-[380px] shrink-0" onClick={onClose} />
      <div className="relative flex-1 h-full bg-white shadow-2xl border-l border-slate-200 overflow-hidden flex flex-col animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b bg-gradient-to-r from-violet-50 to-indigo-50">
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-1 bg-violet-600 text-white text-[11px] font-bold rounded-full">PRO</span>
            <h2 className="text-lg font-bold text-slate-900">전문가 도구</h2>
          </div>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-200 transition-colors">
            <svg className="w-5 h-5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        {/* 기업/개인 토글 */}
        <div className="flex items-center gap-1 px-6 pt-3 pb-1">
          {(["business", "individual"] as ClientType[]).map((ct) => (
            <button
              key={ct}
              onClick={() => setClientType(ct)}
              className={`px-4 py-1.5 rounded-full text-[12px] font-bold transition-all ${
                clientType === ct
                  ? "bg-violet-600 text-white shadow-sm"
                  : "bg-slate-100 text-slate-500 hover:bg-slate-200"
              }`}
            >
              {ct === "business" ? "기업 고객" : "개인 고객"}
            </button>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex border-b bg-white px-6">
          {([
            { id: "clients" as Tab, label: "고객사 관리", icon: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" },
            { id: "history" as Tab, label: "상담 이력", icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" },
            { id: "reports" as Tab, label: "종합 리포트", icon: "M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
          ]).map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 transition-all ${
                tab === t.id ? "border-violet-600 text-violet-700" : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d={t.icon} /></svg>
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {tab === "clients" && token && <ClientsTab headers={headers} toast={toast} clientType={clientType} />}
          {tab === "history" && token && <HistoryTab headers={headers} toast={toast} />}
          {tab === "reports" && token && <ReportsTab headers={headers} toast={toast} clientType={clientType} />}
        </div>
      </div>
    </div>
  );
}


// ━━━━━━━━━━━━━━ 고객사 관리 탭 ━━━━━━━━━━━━━━

export function ClientsTab({ headers, toast, clientType }: { headers: () => any; toast: any; clientType: ClientType }) {
  const [clients, setClients] = useState<ClientProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editTarget, setEditTarget] = useState<ClientProfile | null>(null);
  const [expandedClient, setExpandedClient] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [showEmailModal, setShowEmailModal] = useState(false);
  const isInd = clientType === "individual";
  const label = isInd ? "고객" : "고객사";

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };
  const selectAll = () => {
    if (selectedIds.size === clients.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(clients.map(c => c.id)));
  };

  const fetchClients = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/pro/clients?client_type=${clientType}`, { headers: headers() });
      const data = await res.json();
      if (data.clients) setClients(data.clients);
    } catch { /* */ }
    setLoading(false);
  }, [headers, clientType]);

  useEffect(() => { fetchClients(); setShowForm(false); setEditTarget(null); }, [fetchClients]);

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`'${name}' ${label}을(를) 삭제하시겠습니까?`)) return;
    const res = await fetch(`${API}/api/pro/clients/${id}`, { method: "DELETE", headers: headers() });
    if (res.ok) {
      toast("삭제 완료", "success");
      fetchClients();
    }
  };

  if (loading) return <div className="text-center py-12 text-slate-400">불러오는 중...</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-slate-500">{clients.length}개 {label}</p>
        <button
          onClick={() => { setEditTarget(null); setShowForm(true); }}
          className="px-4 py-2 bg-violet-600 text-white text-sm font-bold rounded-lg hover:bg-violet-700 transition-all"
        >
          + {label} 추가
        </button>
      </div>

      {showForm && (
        <ClientForm
          initial={editTarget}
          clientType={clientType}
          headers={headers}
          onDone={() => { setShowForm(false); setEditTarget(null); fetchClients(); }}
          onCancel={() => { setShowForm(false); setEditTarget(null); }}
          toast={toast}
        />
      )}

      {clients.length === 0 && !showForm ? (
        <div className="text-center py-16">
          <p className="text-slate-400 text-sm mb-4">등록된 {label}이(가) 없습니다</p>
          <button onClick={() => setShowForm(true)} className="px-4 py-2 bg-violet-100 text-violet-700 text-sm font-bold rounded-lg hover:bg-violet-200">
            첫 {label} 등록하기
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {/* 전체선택 + 이메일 발송 바 */}
          <div className="flex items-center justify-between px-1">
            <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer">
              <input type="checkbox" checked={selectedIds.size === clients.length && clients.length > 0} onChange={selectAll}
                className="w-4 h-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500" />
              전체 선택 ({selectedIds.size}/{clients.length})
            </label>
            {selectedIds.size > 0 && (
              <button onClick={() => setShowEmailModal(true)}
                className="px-3 py-1.5 bg-violet-600 text-white text-xs font-bold rounded-lg hover:bg-violet-700 transition-all">
                선택 {selectedIds.size}명에게 이메일
              </button>
            )}
          </div>

          {clients.map((c) => (
            <div key={c.id} className="p-4 bg-slate-50 rounded-xl border border-slate-100 hover:border-violet-200 transition-all">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <input type="checkbox" checked={selectedIds.has(c.id)} onChange={() => toggleSelect(c.id)}
                    className="w-4 h-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500 flex-shrink-0" />
                  <p className="font-bold text-slate-900 text-sm truncate">{c.client_name}</p>
                  {c.status && c.status !== "new" && (
                    <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded ${
                      c.status === "consulting" ? "bg-blue-100 text-blue-700" :
                      c.status === "matched" ? "bg-indigo-100 text-indigo-700" :
                      c.status === "applied" ? "bg-amber-100 text-amber-700" :
                      c.status === "selected" ? "bg-emerald-100 text-emerald-700" :
                      "bg-slate-100 text-slate-500"
                    }`}>
                      {{ consulting: "상담중", matched: "매칭", applied: "신청", selected: "선정", new: "신규" }[c.status] || c.status}
                    </span>
                  )}
                </div>
              </div>
              <p className="text-xs text-slate-500">
                {isInd
                  ? `${c.address_city || "지역미등록"} | ${c.interests || "관심분야미등록"}`
                  : `${c.address_city || "지역미등록"} | ${c.industry_name || c.industry_code || "업종미등록"} | ${c.revenue_bracket || "매출미등록"}`
                }
              </p>
              {(c.contact_name || c.contact_phone || c.contact_email) && (
                <p className="text-[11px] text-slate-400 mt-1">
                  {[c.contact_name, c.contact_phone, c.contact_email].filter(Boolean).join(" · ")}
                </p>
              )}
              {c.tags && <div className="flex gap-1 mt-1.5">{c.tags.split(",").filter(Boolean).map((t, i) => <span key={i} className="px-1.5 py-0.5 bg-violet-100 text-violet-600 text-[9px] font-bold rounded">{t.trim()}</span>)}</div>}
              {c.memo && <p className="text-xs text-slate-400 mt-1 truncate">{c.memo}</p>}
              <div className="flex items-center gap-2 mt-2">
                <button onClick={() => { setEditTarget(c); setShowForm(true); }} className="px-3 py-1.5 text-xs font-semibold text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100">
                  수정
                </button>
                <button onClick={() => setExpandedClient(expandedClient === c.id ? null : c.id)} className="px-3 py-1.5 text-xs font-semibold text-violet-600 bg-violet-50 rounded-lg hover:bg-violet-100">
                  자료 {expandedClient === c.id ? "▲" : "▼"}
                </button>
                <button onClick={() => handleDelete(c.id, c.client_name)} className="px-3 py-1.5 text-xs font-semibold text-rose-600 bg-rose-50 rounded-lg hover:bg-rose-100">
                  삭제
                </button>
              </div>
              {/* 자료 첨부 패널 */}
              {expandedClient === c.id && (
                <ClientFilesPanel clientId={c.id} headers={headers} toast={toast} />
              )}
            </div>
          ))}
        </div>
      )}

      {/* 이메일 발송 모달 */}
      {showEmailModal && (
        <EmailModal
          clientIds={Array.from(selectedIds)}
          clientCount={selectedIds.size}
          headers={headers}
          toast={toast}
          onClose={() => setShowEmailModal(false)}
          onDone={() => { setShowEmailModal(false); setSelectedIds(new Set()); }}
        />
      )}
    </div>
  );
}


// ━━━━━━━━━━━━━━ 이메일 발송 모달 ━━━━━━━━━━━━━━

export function EmailModal({ clientIds, clientCount, headers, toast, onClose, onDone }: {
  clientIds: number[]; clientCount: number; headers: () => any; toast: any; onClose: () => void; onDone: () => void;
}) {
  const [subject, setSubject] = useState("지원금AI — 맞춤 지원사업 안내");
  const [body, setBody] = useState(
    `<p>안녕하세요, {{담당자명}}님.</p>\n<p><strong>{{고객명}}</strong>에 맞는 정부 지원사업 정보를 안내해 드립니다.</p>\n<p>자세한 내용은 아래 링크에서 확인하실 수 있습니다.</p>\n<p><a href="https://govmatch.kr" style="color:#5b21b6;font-weight:bold;">지원금AI 바로가기</a></p>\n<p>감사합니다.</p>`
  );
  const [includeReport, setIncludeReport] = useState(true);
  const [sending, setSending] = useState(false);

  const handleSend = async () => {
    if (!subject.trim() || !body.trim()) { toast("제목과 내용을 입력하세요", "error"); return; }
    setSending(true);
    try {
      const res = await fetch(`${API}/api/pro/email/send`, {
        method: "POST", headers: headers(),
        body: JSON.stringify({ client_ids: clientIds, subject, body, include_report: includeReport }),
      });
      const data = await res.json();
      if (res.ok) { toast(data.message, "success"); onDone(); }
      else { toast(data.detail || "발송 실패", "error"); }
    } catch { toast("서버 오류", "error"); }
    setSending(false);
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30 backdrop-blur-[2px]" />
      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-4 border-b bg-violet-50 flex justify-between items-center">
          <h3 className="font-bold text-violet-800">이메일 발송 ({clientCount}명)</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">✕</button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">제목</label>
            <input value={subject} onChange={(e) => setSubject(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 outline-none" />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
              본문 <span className="text-slate-400 font-normal">({"{{고객명}}"}, {"{{담당자명}}"} 자동 치환)</span>
            </label>
            <textarea value={body} onChange={(e) => setBody(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 outline-none resize-none" rows={6} />
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
            <input type="checkbox" checked={includeReport} onChange={(e) => setIncludeReport(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500" />
            최근 AI 분석 리포트 자동 포함
          </label>
        </div>
        <div className="px-5 py-3 border-t bg-slate-50 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-500 hover:text-slate-700">취소</button>
          <button onClick={handleSend} disabled={sending}
            className="px-5 py-2 bg-violet-600 text-white text-sm font-bold rounded-lg hover:bg-violet-700 disabled:opacity-50">
            {sending ? "발송 중..." : `${clientCount}명에게 발송`}
          </button>
        </div>
      </div>
    </div>
  );
}


export function ClientForm({ initial, clientType, headers, onDone, onCancel, toast }: {
  initial: ClientProfile | null; clientType: ClientType; headers: () => any; onDone: () => void; onCancel: () => void; toast: any;
}) {
  const isInd = clientType === "individual";
  const [form, setForm] = useState({
    client_name: initial?.client_name || "",
    client_type: clientType,
    business_number: initial?.business_number || "",
    establishment_date: initial?.establishment_date?.slice(0, 10) || "",
    address_city: initial?.address_city || "",
    industry_code: initial?.industry_code || "",
    industry_name: initial?.industry_name || "",
    revenue_bracket: initial?.revenue_bracket || "",
    employee_count_bracket: initial?.employee_count_bracket || "",
    interests: initial?.interests || "",
    memo: initial?.memo || "",
    contact_name: initial?.contact_name || "",
    contact_email: initial?.contact_email || "",
    contact_phone: initial?.contact_phone || "",
    tags: initial?.tags || "",
    status: initial?.status || "new",
  });
  const [saving, setSaving] = useState(false);

  const toggleInterest = (interest: string) => {
    const arr = form.interests ? form.interests.split(",").filter(Boolean) : [];
    const next = arr.includes(interest) ? arr.filter(i => i !== interest) : [...arr, interest];
    setForm({ ...form, interests: next.join(",") });
  };

  const handleSave = async () => {
    if (!form.client_name.trim()) { toast(isInd ? "이름을 입력하세요" : "고객사명을 입력하세요", "error"); return; }
    setSaving(true);
    const payload = { ...form, client_type: clientType };
    if (isInd) {
      payload.industry_code = "";
      payload.industry_name = "";
      payload.revenue_bracket = "";
      payload.employee_count_bracket = "";
      payload.business_number = "";
    }
    const url = initial ? `${API}/api/pro/clients/${initial.id}` : `${API}/api/pro/clients`;
    const method = initial ? "PUT" : "POST";
    try {
      const res = await fetch(url, { method, headers: headers(), body: JSON.stringify(payload) });
      const data = await res.json();
      if (res.ok) {
        toast(initial ? "수정 완료" : "등록 완료", "success");
        onDone();
      } else {
        toast(data.detail || "오류 발생", "error");
      }
    } catch { toast("서버 오류", "error"); }
    setSaving(false);
  };

  const CITIES = ["서울","부산","대구","인천","광주","대전","울산","세종","경기","강원","충북","충남","전북","전남","경북","경남","제주"];
  const REVENUE = ["1억 미만","1억~5억","5억~10억","10억~50억","50억~100억","100억 이상"];
  const EMP = ["5인 미만","5인~10인","10인~30인","30인~50인","50인~100인","100인 이상"];
  const label = isInd ? "고객" : "고객사";

  return (
    <div className="mb-4 p-5 bg-violet-50/50 rounded-xl border border-violet-200">
      <h3 className="text-sm font-bold text-violet-800 mb-3">{initial ? `${label} 수정` : `새 ${label} 등록`}</h3>
      <div className="grid grid-cols-2 gap-3">
        {/* 이름/기업명 */}
        <div className="col-span-2">
          <label className="block text-[11px] font-semibold text-slate-600 mb-1">{isInd ? "이름" : "고객사명"} *</label>
          <input value={form.client_name} onChange={(e) => setForm({ ...form, client_name: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 focus:border-violet-400 outline-none"
            placeholder={isInd ? "홍길동" : "기업명"} />
        </div>

        {/* 사업자번호 — 기업만 */}
        {!isInd && (
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">사업자번호</label>
            <input value={form.business_number} onChange={(e) => setForm({ ...form, business_number: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 outline-none" placeholder="000-00-00000" />
          </div>
        )}

        {/* 설립일/생년월일 — 입력+달력 */}
        <div className="col-span-2">
          <EstablishmentDateInput
            value={form.establishment_date}
            onChange={(v) => setForm({ ...form, establishment_date: v })}
            label={isInd ? "생년월일" : "설립일"}
            dark={false}
          />
        </div>

        {/* 소재지/거주지 */}
        <div>
          <label className="block text-[11px] font-semibold text-slate-600 mb-1">{isInd ? "거주지" : "소재지"}</label>
          <select value={form.address_city} onChange={(e) => setForm({ ...form, address_city: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 outline-none">
            <option value="">선택</option>
            {CITIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        {/* 업종 — 기업만 · KSIC 임베딩 기반 AI 추천 */}
        {!isInd && (
          <div className="col-span-2">
            <IndustryPicker
              value={form.industry_name}
              selectedCode={form.industry_code}
              onSelect={(code, name) => setForm({ ...form, industry_code: code, industry_name: name })}
              dark={false}
              label="업종"
            />
          </div>
        )}

        {/* 매출/직원 — 기업만 */}
        {!isInd && (
          <>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">매출 규모</label>
              <select value={form.revenue_bracket} onChange={(e) => setForm({ ...form, revenue_bracket: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 outline-none">
                <option value="">선택</option>
                {REVENUE.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">직원 수</label>
              <select value={form.employee_count_bracket} onChange={(e) => setForm({ ...form, employee_count_bracket: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 outline-none">
                <option value="">선택</option>
                {EMP.map((e) => <option key={e} value={e}>{e}</option>)}
              </select>
            </div>
          </>
        )}

        {/* 관심분야 — 개인 고객용 칩 선택 */}
        {isInd && (
          <div className="col-span-2">
            <label className="block text-[11px] font-semibold text-slate-600 mb-1.5">관심분야</label>
            <div className="flex flex-wrap gap-1.5">
              {INDIVIDUAL_INTEREST_OPTIONS.map((interest) => {
                const selected = form.interests.split(",").includes(interest);
                return (
                  <button key={interest} type="button" onClick={() => toggleInterest(interest)}
                    className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-all active:scale-95 ${
                      selected ? "bg-violet-600 text-white border-violet-600" : "bg-white text-slate-600 border-slate-200 hover:border-violet-300"
                    }`}
                  >{interest}</button>
                );
              })}
            </div>
          </div>
        )}

        {/* ── 담당자 연락처 ── */}
        <div className="col-span-2 mt-2 pt-3 border-t border-violet-200/50">
          <p className="text-[10px] font-bold text-violet-500 uppercase tracking-wider mb-2">담당자 연락처</p>
        </div>
        <div>
          <label className="block text-[11px] font-semibold text-slate-600 mb-1">담당자명</label>
          <input value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 outline-none" placeholder="김담당" />
        </div>
        <div>
          <label className="block text-[11px] font-semibold text-slate-600 mb-1">전화번호</label>
          <input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 outline-none" placeholder="010-0000-0000" />
        </div>
        <div className="col-span-2">
          <label className="block text-[11px] font-semibold text-slate-600 mb-1">이메일</label>
          <input type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 outline-none" placeholder="contact@company.com" />
        </div>

        {/* 상태 + 태그 */}
        <div>
          <label className="block text-[11px] font-semibold text-slate-600 mb-1">상태</label>
          <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 outline-none">
            <option value="new">신규</option>
            <option value="consulting">상담중</option>
            <option value="matched">매칭완료</option>
            <option value="applied">신청중</option>
            <option value="selected">선정</option>
          </select>
        </div>
        <div>
          <label className="block text-[11px] font-semibold text-slate-600 mb-1">태그</label>
          <input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 outline-none" placeholder="VIP, IT업종" />
        </div>

        {/* 메모 */}
        <div className="col-span-2">
          <label className="block text-[11px] font-semibold text-slate-600 mb-1">메모</label>
          <textarea value={form.memo} onChange={(e) => setForm({ ...form, memo: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 outline-none resize-none" rows={2} placeholder="상담사 메모" />
        </div>
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onCancel} className="px-4 py-2 text-sm font-semibold text-slate-500 hover:text-slate-700">취소</button>
        <button onClick={handleSave} disabled={saving}
          className="px-5 py-2 bg-violet-600 text-white text-sm font-bold rounded-lg hover:bg-violet-700 disabled:opacity-50">
          {saving ? "저장 중..." : initial ? "수정" : "등록"}
        </button>
      </div>
    </div>
  );
}


// ━━━━━━━━━━━━━━ 자료 첨부 패널 ━━━━━━━━━━━━━━

const FILE_TYPES = [
  { value: "financial", label: "재무제표" },
  { value: "business_plan", label: "사업계획서" },
  { value: "ir", label: "IR자료" },
  { value: "company_intro", label: "회사소개서" },
  { value: "contract", label: "계약서" },
  { value: "consultation", label: "상담기록" },
  { value: "other", label: "기타" },
];

export function ClientFilesPanel({ clientId, headers, toast }: { clientId: number; headers: () => any; toast: any }) {
  const [files, setFiles] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [fileType, setFileType] = useState("other");

  const fetchFiles = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/pro/clients/${clientId}/files`, { headers: headers() });
      const data = await res.json();
      if (data.files) setFiles(data.files);
    } catch { /* */ }
  }, [clientId, headers]);

  useEffect(() => { fetchFiles(); }, [fetchFiles]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { toast("10MB 이하 파일만 가능합니다.", "error"); return; }

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("file_type", fileType);
    formData.append("memo", "");

    try {
      const token = localStorage.getItem("auth_token") || "";
      const res = await fetch(`${API}/api/pro/clients/${clientId}/files`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        toast(`${file.name} 업로드 완료${data.extracted_chars ? ` (${data.extracted_chars}자 추출)` : ""}`, "success");
        fetchFiles();
      } else {
        toast(data.detail || "업로드 실패", "error");
      }
    } catch { toast("서버 오류", "error"); }
    setUploading(false);
    e.target.value = "";
  };

  const handleDelete = async (fileId: number, fileName: string) => {
    if (!confirm(`"${fileName}" 파일을 삭제할까요?`)) return;
    try {
      const res = await fetch(`${API}/api/pro/clients/${clientId}/files/${fileId}`, { method: "DELETE", headers: headers() });
      if (res.ok) { toast("삭제 완료", "success"); fetchFiles(); }
    } catch { toast("삭제 실패", "error"); }
  };

  const handleDownload = (fileId: number, fileName: string) => {
    const token = localStorage.getItem("auth_token") || "";
    window.open(`${API}/api/pro/clients/${clientId}/files/${fileId}/download?token=${token}`, "_blank");
  };

  const typeLabel = (t: string) => FILE_TYPES.find(ft => ft.value === t)?.label || t;

  return (
    <div className="mt-3 p-3 bg-white rounded-lg border border-violet-200 space-y-3">
      <div className="flex items-center gap-2">
        <select value={fileType} onChange={(e) => setFileType(e.target.value)}
          className="px-2 py-1.5 border rounded-lg text-xs focus:ring-2 focus:ring-violet-300 outline-none">
          {FILE_TYPES.map(ft => <option key={ft.value} value={ft.value}>{ft.label}</option>)}
        </select>
        <label className={`flex-1 px-3 py-1.5 text-center border-2 border-dashed rounded-lg text-xs font-semibold cursor-pointer transition-all ${
          uploading ? "border-slate-200 text-slate-400" : "border-violet-300 text-violet-600 hover:bg-violet-50"
        }`}>
          {uploading ? "업로드 중..." : "파일 선택 (PDF, HWP, DOCX, 10MB)"}
          <input type="file" className="hidden" accept=".pdf,.hwp,.hwpx,.docx,.doc,.xlsx,.jpg,.png" onChange={handleUpload} disabled={uploading} />
        </label>
      </div>

      {files.length === 0 ? (
        <p className="text-xs text-slate-400 text-center py-2">첨부된 자료가 없습니다</p>
      ) : (
        <div className="space-y-1.5">
          {files.map(f => (
            <div key={f.id} className="flex items-center justify-between px-3 py-2 bg-slate-50 rounded-lg text-xs">
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <span className="px-1.5 py-0.5 bg-violet-100 text-violet-600 text-[9px] font-bold rounded">{typeLabel(f.file_type)}</span>
                <span className="truncate text-slate-700 font-medium">{f.file_name}</span>
                <span className="text-slate-400 flex-shrink-0">{(f.file_size / 1024).toFixed(0)}KB</span>
              </div>
              <div className="flex gap-1.5 ml-2">
                <button onClick={() => handleDownload(f.id, f.file_name)} className="px-2 py-1 text-indigo-600 bg-indigo-50 rounded hover:bg-indigo-100 text-[10px] font-semibold">다운</button>
                <button onClick={() => handleDelete(f.id, f.file_name)} className="px-2 py-1 text-rose-600 bg-rose-50 rounded hover:bg-rose-100 text-[10px] font-semibold">삭제</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ━━━━━━━━━━━━━━ 상담 이력 탭 ━━━━━━━━━━━━━━

export function HistoryTab({ headers, toast }: { headers: () => any; toast: any }) {
  const [history, setHistory] = useState<ConsultHistory[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/api/pro/consult-history?limit=50`, { headers: headers() });
        const data = await res.json();
        if (data.history) { setHistory(data.history); setTotal(data.total); }
      } catch { /* */ }
      setLoading(false);
    })();
  }, [headers]);

  const handleExport = async () => {
    try {
      const res = await fetch(`${API}/api/pro/consult-history/export`, { headers: headers() });
      if (!res.ok) { toast("다운로드 실패", "error"); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "consult_history.csv";
      a.click();
      URL.revokeObjectURL(url);
      toast("엑셀 다운로드 완료", "success");
    } catch { toast("다운로드 오류", "error"); }
  };

  const conclusionBadge = (c: string) => {
    if (c === "eligible") return <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-[11px] font-bold rounded-full">지원가능</span>;
    if (c === "conditional") return <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-[11px] font-bold rounded-full">조건부</span>;
    if (c === "ineligible") return <span className="px-2 py-0.5 bg-rose-100 text-rose-700 text-[11px] font-bold rounded-full">지원불가</span>;
    return <span className="px-2 py-0.5 bg-slate-100 text-slate-500 text-[11px] font-bold rounded-full">미판정</span>;
  };

  if (loading) return <div className="text-center py-12 text-slate-400">불러오는 중...</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-slate-500">총 {total}건의 상담 이력</p>
        <button onClick={handleExport}
          className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white text-sm font-bold rounded-lg hover:bg-emerald-700 transition-all">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
          엑셀 다운로드
        </button>
      </div>

      {history.length === 0 ? (
        <div className="text-center py-16 text-slate-400 text-sm">상담 이력이 없습니다</div>
      ) : (
        <div className="space-y-2">
          {history.map((h) => (
            <div key={h.id} className="p-4 bg-slate-50 rounded-xl border border-slate-100">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="font-bold text-slate-900 text-sm truncate">{h.announcement_title || h.consult_label || "[일반상담]"}</p>
                  <p className="text-xs text-slate-500 mt-1">{h.category} | 대화 {h.message_count}건 | {h.created_at?.slice(0, 16)}</p>
                  {h.last_question && <p className="text-xs text-slate-400 mt-1 truncate">Q: {h.last_question}</p>}
                </div>
                <div className="ml-3">{conclusionBadge(h.conclusion)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ━━━━━━━━━━━━━━ 종합 리포트 탭 ━━━━━━━━━━━━━━

export function ReportsTab({ headers, toast, clientType }: { headers: () => any; toast: any; clientType: ClientType }) {
  const [reports, setReports] = useState<Report[]>([]);
  const [clients, setClients] = useState<ClientProfile[]>([]);
  const [selectedClient, setSelectedClient] = useState<number | null>(null);
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<any>(null);

  // 상세 진입 시 history entry 추가 → 브라우저 뒤로가기가 목록으로 돌아오게 함
  useEffect(() => {
    if (!detail) return;
    window.history.pushState({ reportDetail: true }, "");
    const onPop = () => setDetail(null);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [detail]);

  const fetchReports = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/pro/reports`, { headers: headers() });
      const data = await res.json();
      if (data.reports) setReports(data.reports);
    } catch { /* */ }
    setLoading(false);
  }, [headers]);

  useEffect(() => {
    fetchReports();
    (async () => {
      try {
        const res = await fetch(`${API}/api/pro/clients?client_type=${clientType}`, { headers: headers() });
        const data = await res.json();
        if (data.clients) setClients(data.clients);
      } catch { /* */ }
    })();
    setSelectedClient(null);
  }, [headers, fetchReports, clientType]);

  const handleGenerate = async (forceRegenerate = false) => {
    if (!selectedClient) { toast("고객사를 선택하세요", "error"); return; }
    setGenerating(true);
    try {
      const res = await fetch(`${API}/api/pro/reports/generate`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ client_profile_id: selectedClient, force_regenerate: forceRegenerate }),
      });
      const data = await res.json();
      if (res.ok) {
        if (data.status === "CACHED") {
          toast("기존 보고서를 불러왔습니다", "success");
        } else {
          toast(`리포트 생성 완료 — ${data.total}건 매칭`, "success");
        }
        await fetchReports();
        // 생성(또는 캐시) 된 보고서를 바로 상세로 이동
        if (data.report_id) handleDetail(data.report_id);
      } else {
        toast(data.detail || "오류 발생", "error");
      }
    } catch { toast("서버 오류", "error"); }
    setGenerating(false);
  };

  const handleDetail = async (reportId: number) => {
    try {
      const res = await fetch(`${API}/api/pro/reports/${reportId}`, { headers: headers() });
      const data = await res.json();
      if (data.report) setDetail(data.report);
    } catch { toast("조회 오류", "error"); }
  };

  if (loading) return <div className="text-center py-12 text-slate-400">불러오는 중...</div>;

  if (detail) {
    return (
      <div>
        <div className="flex items-center justify-between mb-4">
          <button onClick={() => setDetail(null)} className="flex items-center gap-1 text-sm text-violet-600 font-semibold hover:text-violet-800">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
            목록으로
          </button>
          <button
            onClick={async () => {
              if (!detail.client_profile_id) return;
              setGenerating(true);
              try {
                const res = await fetch(`${API}/api/pro/reports/generate`, {
                  method: "POST",
                  headers: headers(),
                  body: JSON.stringify({ client_profile_id: detail.client_profile_id, force_regenerate: true }),
                });
                const data = await res.json();
                if (res.ok && data.report_id) {
                  toast("보고서를 새로 생성했습니다", "success");
                  const r2 = await fetch(`${API}/api/pro/reports/${data.report_id}`, { headers: headers() });
                  const d2 = await r2.json();
                  if (d2.report) setDetail(d2.report);
                  fetchReports();
                } else { toast(data.detail || "오류", "error"); }
              } catch { toast("서버 오류", "error"); }
              setGenerating(false);
            }}
            disabled={generating}
            className="px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-[11px] font-bold hover:bg-slate-200 transition-all disabled:opacity-50"
          >
            {generating ? "생성 중..." : "🔄 다시 생성"}
          </button>
        </div>
        <div className="mb-6">
          <h3 className="text-lg font-bold text-slate-900">{detail.title}</h3>
          <p className="text-sm text-slate-500 mt-1">{detail.client_name} | {detail.address_city} | {detail.revenue_bracket}</p>
          <div className="flex gap-3 mt-3">
            <span className="px-3 py-1 bg-emerald-100 text-emerald-700 text-sm font-bold rounded-lg">지원가능 {detail.total_eligible}건</span>
            <span className="px-3 py-1 bg-amber-100 text-amber-700 text-sm font-bold rounded-lg">조건부 {detail.total_conditional}건</span>
            <span className="px-3 py-1 bg-rose-100 text-rose-700 text-sm font-bold rounded-lg">불가 {detail.total_ineligible}건</span>
          </div>
        </div>

        {/* AI 종합 분석 리포트 (HTML) */}
        {detail.summary && (detail.summary.includes("<h2") || detail.summary.includes("<table") || detail.summary.includes("##")) && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-bold text-violet-700">AI 종합 분석</h4>
              <button
                onClick={() => {
                  const printWin = window.open("", "_blank");
                  if (!printWin) return;
                  const content = detail.summary.split("\n").filter((l: string) => !l.startsWith(detail.client_name + " 기업 분석")).join("\n");
                  printWin.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${detail.title}</title>
                    <style>body{font-family:'Pretendard','Apple SD Gothic Neo',sans-serif;max-width:800px;margin:0 auto;padding:40px 30px;color:#1e293b;font-size:13px;line-height:1.7;}
                    h2{color:#5b21b6;border-bottom:2px solid #c4b5fd;padding-bottom:6px;margin-top:28px;font-size:16px;}
                    table{width:100%;border-collapse:collapse;margin:12px 0;font-size:12px;}
                    th{background:#f5f3ff;color:#5b21b6;padding:8px 10px;border:1px solid #e5e7eb;text-align:left;font-weight:bold;}
                    td{padding:8px 10px;border:1px solid #e5e7eb;}
                    @media print{body{padding:20px;}}</style></head><body>
                    <div style="text-align:center;margin-bottom:30px;border-bottom:3px double #5b21b6;padding-bottom:15px;">
                      <h1 style="color:#5b21b6;font-size:20px;margin:0;">${detail.title}</h1>
                      <p style="color:#64748b;font-size:12px;margin-top:6px;">${detail.client_name} | ${detail.address_city || ""} | ${detail.revenue_bracket || ""} | 작성일: ${new Date().toLocaleDateString("ko-KR")}</p>
                    </div>${content}</body></html>`);
                  printWin.document.close();
                  setTimeout(() => printWin.print(), 500);
                }}
                className="px-3 py-1.5 bg-violet-600 text-white rounded-lg text-[11px] font-bold hover:bg-violet-700 transition-all flex items-center gap-1"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0l.229 2.523a1.125 1.125 0 01-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0021 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 00-1.913-.247M6.34 18H5.25A2.25 2.25 0 013 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 011.913-.247m10.5 0a48.536 48.536 0 00-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18 10.5h.008v.008H18V10.5zm-3 0h.008v.008H15V10.5z" /></svg>
                인쇄
              </button>
              <button
                onClick={() => {
                  const token = localStorage.getItem("auth_token") || "";
                  window.open(`${API}/api/pro/reports/${detail.id}/pdf?authorization=Bearer ${token}`, "_blank");
                }}
                className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-[11px] font-bold hover:bg-indigo-700 transition-all flex items-center gap-1"
              >
                PDF 다운로드
              </button>
            </div>
            <div className="p-5 bg-white rounded-xl border border-violet-200 shadow-sm overflow-x-auto"
              dangerouslySetInnerHTML={{ __html: (() => {
                let html = detail.summary;
                // brief 첫 줄 제거
                const firstNewline = html.indexOf("\n\n");
                if (firstNewline > 0 && firstNewline < 200) html = html.slice(firstNewline + 2);
                // 마크다운 fallback (HTML 태그가 없는 경우)
                if (!html.includes("<h2") && !html.includes("<table")) {
                  html = html.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
                  html = html.replace(/^## (.+)$/gm, '<h2 style="color:#5b21b6;border-bottom:2px solid #c4b5fd;padding-bottom:6px;margin-top:24px;font-size:15px;">$1</h2>');
                  html = html.replace(/^### (.+)$/gm, '<h3 style="color:#334155;font-size:14px;margin-top:16px;">$1</h3>');
                  html = html.replace(/^\* (.+)$/gm, "<li>$1</li>");
                  html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
                  html = html.replace(/\n\n/g, "<br/>");
                }
                return html;
              })() }}
            />
          </div>
        )}

        {/* 매칭 공고 목록 */}
        <h4 className="text-sm font-bold text-slate-700 mb-3">매칭 공고 상세 ({(detail.matched_announcements || []).length}건)</h4>
        <div className="space-y-2">
          {(detail.matched_announcements || []).map((a: any, i: number) => (
            <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-100">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-900 text-sm">{a.title}</p>
                  <p className="text-xs text-slate-500 mt-1">{a.category} | {a.department} | 마감 {a.deadline_date} | {a.support_amount}</p>
                  <p className="text-xs text-slate-600 mt-1">{a.reason}</p>
                </div>
                <div className="ml-3">
                  {a.conclusion === "eligible" && <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-[11px] font-bold rounded-full">가능</span>}
                  {a.conclusion === "conditional" && <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-[11px] font-bold rounded-full">조건부</span>}
                  {a.conclusion === "ineligible" && <span className="px-2 py-0.5 bg-rose-100 text-rose-700 text-[11px] font-bold rounded-full">불가</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Generate */}
      <div className="flex items-center gap-3 mb-5 p-4 bg-violet-50/50 rounded-xl border border-violet-200">
        <select
          value={selectedClient || ""}
          onChange={(e) => setSelectedClient(Number(e.target.value) || null)}
          className="flex-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-violet-300 outline-none"
        >
          <option value="">고객사 선택</option>
          {clients.map((c) => <option key={c.id} value={c.id}>{c.client_name}</option>)}
        </select>
        <button onClick={() => handleGenerate(false)} disabled={generating || !selectedClient}
          className="px-5 py-2 bg-violet-600 text-white text-sm font-bold rounded-lg hover:bg-violet-700 disabled:opacity-50 whitespace-nowrap">
          {generating ? "분석 중..." : "리포트 보기"}
        </button>
      </div>

      {clients.length === 0 && (
        <p className="text-center text-sm text-slate-400 mb-4">고객사를 먼저 등록해주세요 (고객사 관리 탭)</p>
      )}

      {/* Report List */}
      {reports.length === 0 ? (
        <div className="text-center py-12 text-slate-400 text-sm">생성된 리포트가 없습니다</div>
      ) : (
        <div className="space-y-2">
          {reports.map((r) => (
            <button key={r.id} onClick={() => handleDetail(r.id)}
              className="w-full text-left p-4 bg-slate-50 rounded-xl border border-slate-100 hover:border-violet-200 transition-all">
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <p className="font-bold text-slate-900 text-sm truncate">{r.title}</p>
                  <p className="text-xs text-slate-500 mt-1">{r.client_name} | {r.created_at?.slice(0, 16)}</p>
                </div>
                <div className="flex items-center gap-2 ml-3">
                  <span className="text-emerald-600 text-xs font-bold">{r.total_eligible}</span>
                  <span className="text-amber-600 text-xs font-bold">{r.total_conditional}</span>
                  <span className="text-rose-600 text-xs font-bold">{r.total_ineligible}</span>
                  <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
