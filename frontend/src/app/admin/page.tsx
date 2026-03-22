'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { FiPlus, FiTrash2, FiRefreshCw, FiExternalLink, FiDatabase, FiGlobe, FiCpu, FiLink, FiMail, FiLock, FiUsers, FiLogOut } from 'react-icons/fi';
import { useToast } from '@/components/ui/Toast';

interface AdminURL {
  id: number;
  url: string;
  source_name: string;
  last_scraped: string | null;
  is_active: boolean;
}

interface SourceItem {
  id: string;
  name: string;
  type: string;
  status: string;
  description: string;
}

interface SourceStat {
  source: string;
  count: number;
}

interface Stats {
  total_announcements: number;
  by_source: SourceStat[];
  user_count: number;
  active_manual_urls: number;
}

interface UserRow {
  user_id: number;
  business_number: string;
  company_name: string | null;
  address_city: string | null;
  industry_code: string | null;
  revenue_bracket: string | null;
  employee_count_bracket: string | null;
  updated_at: string | null;
  email: string | null;
  channel: string | null;
  notify_active: number | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL;

const STATUS_BADGE: Record<string, string> = {
  LIVE: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  ACTIVE: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  SIMULATED: 'bg-amber-50 text-amber-700 border-amber-200',
  KEY_REQUIRED: 'bg-rose-50 text-rose-600 border-rose-200',
};

const STATUS_LABEL: Record<string, string> = {
  LIVE: '연동 완료',
  ACTIVE: '활성',
  SIMULATED: '시뮬레이션',
  KEY_REQUIRED: 'API 키 필요',
};

function getSourceCount(stats: Stats | null, sourceId: string): number {
  if (!stats) return 0;
  const found = stats.by_source.find(s => s.source === sourceId);
  return found ? found.count : 0;
}

/* ────────────── Login Gate ────────────── */
function LoginGate({ onLogin }: { onLogin: () => void }) {
  const [pw, setPw] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pw) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/admin/auth`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pw }),
      });
      if (res.ok) {
        const data = await res.json();
        sessionStorage.setItem('admin_authed', '1');
        sessionStorage.setItem('admin_token', data.token);
        onLogin();
      } else {
        const data = await res.json();
        setError(data.detail || '인증 실패');
      }
    } catch {
      setError('서버 연결 오류');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <form onSubmit={handleSubmit} className="bg-white w-full max-w-sm rounded-2xl shadow-lg border border-slate-200 p-8">
        <div className="flex justify-center mb-6">
          <div className="p-4 rounded-2xl bg-indigo-50 text-indigo-600">
            <FiLock size={32} />
          </div>
        </div>
        <h1 className="text-xl font-bold text-center text-slate-800 mb-1">관리자 로그인</h1>
        <p className="text-xs text-center text-slate-400 mb-6">관리자 비밀번호를 입력하세요</p>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-50 text-rose-600 text-sm font-medium border border-rose-200 text-center">
            {error}
          </div>
        )}

        <input
          type="password"
          placeholder="비밀번호"
          className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm outline-none focus:border-indigo-500 transition-colors mb-4"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          autoFocus
        />

        <button
          type="submit"
          disabled={loading || !pw}
          className="w-full py-3 rounded-xl font-bold text-sm bg-indigo-600 text-white hover:bg-indigo-700 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? '확인 중...' : '로그인'}
        </button>
      </form>
    </div>
  );
}

/* ────────────── Main Admin Page ────────────── */
export default function AdminPage() {
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    if (sessionStorage.getItem('admin_authed') === '1') setAuthed(true);
  }, []);

  const handleLogout = () => {
    sessionStorage.removeItem('admin_authed');
    sessionStorage.removeItem('admin_token');
    setAuthed(false);
  };

  if (!authed) return <LoginGate onLogin={() => setAuthed(true)} />;

  return <AdminDashboard onLogout={handleLogout} />;
}

function AdminDashboard({ onLogout }: { onLogout: () => void }) {
  const { toast } = useToast();
  const [urls, setUrls] = useState<AdminURL[]>([]);
  const [apis, setApis] = useState<SourceItem[]>([]);
  const [scrapers, setScrapers] = useState<SourceItem[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [newUrl, setNewUrl] = useState('');
  const [sourceName, setSourceName] = useState('');
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [manualSyncing, setManualSyncing] = useState(false);
  const [digestSending, setDigestSending] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [reanalyzeProgress, setReanalyzeProgress] = useState<{ done: number; total: number; result: string | null } | null>(null);

  const authHeaders = useCallback((): Record<string, string> => {
    const token = sessionStorage.getItem('admin_token') || '';
    return { 'Authorization': `Bearer ${token}` };
  }, []);

  const authFetch = useCallback((url: string, opts?: RequestInit) => {
    const headers = { ...authHeaders(), ...(opts?.headers || {}) };
    return fetch(url, { ...opts, headers });
  }, [authHeaders]);

  const fetchData = useCallback(async () => {
    try {
      const [urlRes, systemRes, statsRes, usersRes] = await Promise.all([
        authFetch(`${API_URL}/api/admin/urls`),
        authFetch(`${API_URL}/api/admin/system-sources`),
        authFetch(`${API_URL}/api/admin/stats`),
        authFetch(`${API_URL}/api/admin/users`),
      ]);

      if (urlRes.status === 401 || statsRes.status === 401) {
        onLogout();
        return;
      }

      const urlData = await urlRes.json();
      const systemData = await systemRes.json();
      const statsData = await statsRes.json();
      const usersData = await usersRes.json();

      if (urlData.status === 'SUCCESS') setUrls(urlData.data);
      if (systemData.status === 'SUCCESS') {
        setApis(systemData.data.apis || []);
        setScrapers(systemData.data.scrapers || []);
      }
      if (statsData.status === 'SUCCESS') setStats(statsData.data);
      if (usersData.status === 'SUCCESS') setUsers(usersData.data);
    } catch (err) {
      console.error('Failed to fetch admin data', err);
    } finally {
      setInitialLoading(false);
    }
  }, [authFetch, onLogout]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAddUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUrl || !sourceName) return;
    setLoading(true);
    try {
      const res = await authFetch(`${API_URL}/api/admin/urls`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: newUrl, source_name: sourceName }),
      });
      const data = await res.json();
      if (data.status === 'SUCCESS') {
        setNewUrl('');
        setSourceName('');
        fetchData();
      } else {
        toast(data.detail || '등록 실패', 'error');
      }
    } catch {
      toast('서버 연결 오류', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('정말 삭제하시겠습니까?')) return;
    try {
      const res = await authFetch(`${API_URL}/api/admin/urls/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.status === 'SUCCESS') {
        toast('URL이 삭제되었습니다.', 'success');
        fetchData();
      }
    } catch {
      toast('삭제 실패', 'error');
    }
  };

  const handleDeleteUser = async (userId: number) => {
    if (!confirm('이 사용자를 삭제하시겠습니까? 알림 설정도 함께 삭제됩니다.')) return;
    try {
      const res = await authFetch(`${API_URL}/api/admin/users/${userId}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.status === 'SUCCESS') {
        toast('사용자가 삭제되었습니다.', 'success');
        fetchData();
      }
    } catch {
      toast('삭제 실패', 'error');
    }
  };

  const pollManualSyncStatus = useCallback(async () => {
    const poll = async () => {
      try {
        const res = await authFetch(`${API_URL}/api/admin/sync-manual-status`);
        const data = await res.json();
        if (data.data?.running) {
          setTimeout(poll, 3000);
        } else {
          setManualSyncing(false);
          fetchData();
          toast(`수동 URL 수집 ${data.data?.last_result || '완료'}`, 'success');
        }
      } catch {
        setManualSyncing(false);
      }
    };
    setTimeout(poll, 3000);
  }, [authFetch, fetchData]);

  const handleManualSync = async () => {
    setManualSyncing(true);
    try {
      const res = await authFetch(`${API_URL}/api/admin/sync-manual`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'ALREADY_RUNNING') {
        toast('수동 URL 수집이 이미 진행 중입니다.', 'info');
        pollManualSyncStatus();
      } else if (data.status === 'STARTED') {
        pollManualSyncStatus();
      }
    } catch {
      toast('수동 URL 수집 오류', 'error');
      setManualSyncing(false);
    }
  };

  const pollReanalyzeStatus = useCallback(async () => {
    const poll = async () => {
      try {
        const res = await authFetch(`${API_URL}/api/admin/reanalyze-status`);
        const data = await res.json();
        const d = data.data;
        setReanalyzeProgress({ done: d?.done ?? 0, total: d?.total ?? 0, result: d?.last_result ?? null });
        if (d?.running) {
          setTimeout(poll, 2000);
        } else {
          setReanalyzing(false);
          fetchData();
          if (d?.last_result) toast(d.last_result, 'success');
        }
      } catch {
        setReanalyzing(false);
      }
    };
    setTimeout(poll, 2000);
  }, [authFetch, fetchData]);

  const handleReanalyze = async (limit = 200) => {
    if (!confirm(`AI 미분석 공고를 최대 ${limit}건 재분석합니다. 약 ${Math.ceil(limit * 0.5 / 60)}~${Math.ceil(limit * 1 / 60)}분 소요됩니다. 시작할까요?`)) return;
    setReanalyzing(true);
    setReanalyzeProgress({ done: 0, total: 0, result: null });
    try {
      const res = await authFetch(`${API_URL}/api/admin/reanalyze?limit=${limit}`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'ALREADY_RUNNING') {
        toast('재분석이 이미 진행 중입니다.', 'info');
        pollReanalyzeStatus();
      } else if (data.status === 'STARTED') {
        pollReanalyzeStatus();
      }
    } catch {
      toast('재분석 오류', 'error');
      setReanalyzing(false);
    }
  };

  const pollSyncStatus = useCallback(async () => {
    const poll = async () => {
      try {
        const res = await authFetch(`${API_URL}/api/admin/sync-status`);
        const data = await res.json();
        if (data.data?.running) {
          setTimeout(poll, 3000);
        } else {
          setSyncing(false);
          fetchData();
          toast(`동기화 ${data.data?.last_result || '완료'}`, 'success');
        }
      } catch {
        setSyncing(false);
      }
    };
    setTimeout(poll, 3000);
  }, [authFetch, fetchData]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await authFetch(`${API_URL}/api/sync`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'ALREADY_RUNNING') {
        toast('동기화가 이미 진행 중입니다.', 'info');
        pollSyncStatus();
      } else if (data.status === 'STARTED') {
        pollSyncStatus();
      }
    } catch {
      toast('동기화 오류', 'error');
      setSyncing(false);
    }
  };

  const handleDigest = async () => {
    if (!confirm('등록된 사용자에게 다이제스트 이메일을 발송합니다. 계속할까요?')) return;
    setDigestSending(true);
    try {
      const res = await authFetch(`${API_URL}/api/admin/send-digest`, { method: 'POST' });
      const data = await res.json();
      toast(data.message || '발송 완료', 'success');
    } catch {
      toast('다이제스트 발송 오류', 'error');
    } finally {
      setDigestSending(false);
    }
  };

  const apiCount = stats ? stats.by_source.filter(s => s.source.includes('api')).reduce((sum, s) => sum + s.count, 0) : 0;
  const scraperCount = stats ? stats.by_source.filter(s => !s.source.includes('api') && !s.source.includes('admin')).reduce((sum, s) => sum + s.count, 0) : 0;
  const manualCount = stats ? stats.by_source.filter(s => s.source.includes('admin')).reduce((sum, s) => sum + s.count, 0) : 0;

  if (initialLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-10 h-10 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto" />
          <p className="text-sm font-medium text-slate-500">데이터 불러오는 중...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6 md:p-8 text-slate-900">
      <div className="max-w-5xl mx-auto space-y-10">

        {/* Header */}
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight mb-1">관리자 대시보드</h1>
            <p className="text-slate-500 text-sm">데이터 소스 관리 및 수집 현황</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={onLogout}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm transition-all border border-slate-200 bg-white text-slate-500 hover:bg-slate-100"
              title="로그아웃"
            >
              <FiLogOut size={16} />
              <span className="hidden md:inline">로그아웃</span>
            </button>
            <button
              onClick={handleDigest}
              disabled={digestSending}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <FiMail className={digestSending ? 'animate-pulse' : ''} />
              {digestSending ? '발송 중...' : '다이제스트 발송'}
            </button>
            <button
              onClick={handleSync}
              disabled={syncing}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all shadow-md ${
                syncing
                  ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  : 'bg-indigo-600 text-white hover:bg-indigo-700 active:scale-95'
              }`}
            >
              <FiRefreshCw className={syncing ? 'animate-spin' : ''} size={16} />
              {syncing ? '수집 중...' : '전체 데이터 수집'}
            </button>
          </div>
        </header>

        {/* Stats Cards */}
        {stats && (
          <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: '총 공고', value: stats.total_announcements, icon: <FiDatabase />, color: 'text-indigo-600 bg-indigo-50' },
              { label: 'API 수집', value: apiCount, icon: <FiGlobe />, color: 'text-emerald-600 bg-emerald-50' },
              { label: '스크래퍼 수집', value: scraperCount, icon: <FiCpu />, color: 'text-amber-600 bg-amber-50' },
              { label: '등록 사용자', value: stats.user_count, icon: <FiUsers />, color: 'text-blue-600 bg-blue-50' },
            ].map((card, i) => (
              <div key={i} className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200">
                <div className="flex items-center gap-3 mb-3">
                  <div className={`p-2 rounded-lg ${card.color}`}>{card.icon}</div>
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">{card.label}</span>
                </div>
                <p className="text-2xl font-black text-slate-900">{card.value.toLocaleString()}</p>
              </div>
            ))}
          </section>
        )}

        {/* AI 재분석 패널 */}
        <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-slate-800 flex items-center gap-2 mb-1">
                <FiCpu className="text-purple-500" /> AI 공고 재분석
              </h2>
              <p className="text-xs text-slate-400">
                AI 분석이 없는 공고에 eligibility_logic, 대상기업 유형, 키워드를 추출합니다.
                {stats && (
                  <span className="ml-2 font-bold text-purple-600">
                    (약 {stats.total_announcements}건 중 미분석 다수)
                  </span>
                )}
              </p>
            </div>
            <div className="flex gap-2 flex-shrink-0">
              <button
                onClick={() => handleReanalyze(200)}
                disabled={reanalyzing}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl font-semibold text-sm border transition-all ${
                  reanalyzing
                    ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                    : 'bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100'
                }`}
              >
                <FiRefreshCw className={reanalyzing ? 'animate-spin' : ''} size={14} />
                {reanalyzing ? '분석 중...' : '200건 재분석'}
              </button>
              <button
                onClick={() => handleReanalyze(1100)}
                disabled={reanalyzing}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl font-semibold text-sm border transition-all ${
                  reanalyzing
                    ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                    : 'bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-100'
                }`}
              >
                전체 재분석
              </button>
            </div>
          </div>

          {(reanalyzing || reanalyzeProgress?.result) && (
            <div className="mt-5">
              {reanalyzeProgress && reanalyzeProgress.total > 0 && (
                <div className="mb-2">
                  <div className="flex justify-between text-xs text-slate-500 mb-1">
                    <span>진행 중: {reanalyzeProgress.done} / {reanalyzeProgress.total}건</span>
                    <span>{Math.round((reanalyzeProgress.done / reanalyzeProgress.total) * 100)}%</span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-2">
                    <div
                      className="bg-purple-500 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${Math.round((reanalyzeProgress.done / reanalyzeProgress.total) * 100)}%` }}
                    />
                  </div>
                </div>
              )}
              {reanalyzeProgress?.result && (
                <p className="text-xs font-bold text-emerald-600">{reanalyzeProgress.result}</p>
              )}
            </div>
          )}
        </section>

        {/* Section: Users */}
        <section>
          <h2 className="text-lg font-bold text-slate-800 mb-5 flex items-center gap-2">
            <FiUsers className="text-blue-600" /> 등록 사용자 관리
            <span className="text-xs font-bold text-slate-400 ml-1">{users.length}명</span>
          </h2>
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            {users.length === 0 ? (
              <div className="p-10 text-center text-slate-400 text-sm">등록된 사용자가 없습니다.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50 text-left">
                      <th className="px-5 py-3 font-bold text-slate-500 text-xs uppercase tracking-wider">기업명</th>
                      <th className="px-5 py-3 font-bold text-slate-500 text-xs uppercase tracking-wider">사업자번호</th>
                      <th className="px-5 py-3 font-bold text-slate-500 text-xs uppercase tracking-wider">지역</th>
                      <th className="px-5 py-3 font-bold text-slate-500 text-xs uppercase tracking-wider">업종</th>
                      <th className="px-5 py-3 font-bold text-slate-500 text-xs uppercase tracking-wider">이메일</th>
                      <th className="px-5 py-3 font-bold text-slate-500 text-xs uppercase tracking-wider">알림</th>
                      <th className="px-5 py-3 font-bold text-slate-500 text-xs uppercase tracking-wider">등록일</th>
                      <th className="px-5 py-3 font-bold text-slate-500 text-xs uppercase tracking-wider text-right">관리</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {users.map(u => (
                      <tr key={u.user_id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-5 py-3 font-medium text-slate-800">{u.company_name || '-'}</td>
                        <td className="px-5 py-3 text-slate-600 font-mono text-xs">{u.business_number}</td>
                        <td className="px-5 py-3 text-slate-600">{u.address_city || '-'}</td>
                        <td className="px-5 py-3 text-slate-600">{u.industry_code || '-'}</td>
                        <td className="px-5 py-3 text-slate-600 text-xs">{u.email || '-'}</td>
                        <td className="px-5 py-3">
                          {u.notify_active === 1 ? (
                            <span className="px-2 py-0.5 rounded-md text-[11px] font-bold border bg-emerald-50 text-emerald-700 border-emerald-200">ON</span>
                          ) : u.email ? (
                            <span className="px-2 py-0.5 rounded-md text-[11px] font-bold border bg-slate-100 text-slate-500 border-slate-200">OFF</span>
                          ) : (
                            <span className="text-slate-300 text-xs">-</span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-slate-400 text-xs font-mono">
                          {u.updated_at ? new Date(u.updated_at).toLocaleDateString('ko-KR') : '-'}
                        </td>
                        <td className="px-5 py-3 text-right">
                          <button
                            onClick={() => handleDeleteUser(u.user_id)}
                            className="p-2 text-rose-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-all"
                            title="삭제"
                          >
                            <FiTrash2 size={16} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>

        {/* Section: API Sources */}
        <section>
          <h2 className="text-lg font-bold text-slate-800 mb-5 flex items-center gap-2">
            <FiGlobe className="text-emerald-600" /> 공식 API 연동 현황
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {apis.map(source => (
              <div key={source.id} className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-bold text-slate-800 text-sm">{source.name}</h3>
                  <span className={`px-2 py-0.5 rounded-md text-[11px] font-bold border ${STATUS_BADGE[source.status] || 'bg-slate-100 text-slate-500 border-slate-200'}`}>
                    {STATUS_LABEL[source.status] || source.status}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mb-3">{source.description}</p>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-400">수집 건수:</span>
                  <span className="text-sm font-black text-slate-800">{getSourceCount(stats, source.id).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Section: Scrapers */}
        <section>
          <h2 className="text-lg font-bold text-slate-800 mb-5 flex items-center gap-2">
            <FiCpu className="text-amber-600" /> 웹 스크래퍼 현황
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {scrapers.map(source => (
              <div key={source.id} className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-bold text-slate-800 text-sm">{source.name}</h3>
                  <span className={`px-2 py-0.5 rounded-md text-[11px] font-bold border ${STATUS_BADGE[source.status] || 'bg-slate-100 text-slate-500 border-slate-200'}`}>
                    {STATUS_LABEL[source.status] || source.status}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mb-3">{source.description}</p>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-400">수집 건수:</span>
                  <span className="text-sm font-black text-slate-800">{getSourceCount(stats, source.id).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Section: Manual URLs */}
        <section>
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
              <FiPlus className="text-indigo-600" /> 수동 수집 관리 (URL)
              {manualCount > 0 && (
                <span className="text-xs font-bold text-slate-400 ml-2">{manualCount}건 수집됨</span>
              )}
            </h2>
            <button
              onClick={handleManualSync}
              disabled={manualSyncing}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl font-semibold text-sm transition-all border ${
                manualSyncing
                  ? 'border-slate-200 bg-slate-100 text-slate-400 cursor-not-allowed'
                  : 'border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
              }`}
            >
              <FiRefreshCw className={manualSyncing ? 'animate-spin' : ''} size={14} />
              {manualSyncing ? '수집 중...' : 'URL 공고 수집'}
            </button>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 mb-5">
            <form onSubmit={handleAddUrl} className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-4 items-end">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">사이트 명칭</label>
                <input
                  type="text"
                  placeholder="예: 부산시 일자리 정보망"
                  className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-indigo-500 transition-colors"
                  value={sourceName}
                  onChange={(e) => setSourceName(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">공고 상세 URL</label>
                <input
                  type="url"
                  placeholder="https://..."
                  className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-indigo-500 transition-colors"
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="px-6 py-2.5 bg-indigo-50 text-indigo-700 font-bold rounded-xl hover:bg-indigo-100 transition-all border border-indigo-100 text-sm whitespace-nowrap"
              >
                {loading ? '등록 중...' : 'URL 추가'}
              </button>
            </form>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="divide-y divide-slate-100">
              {urls.length === 0 ? (
                <div className="p-10 text-center text-slate-400 text-sm">
                  등록된 수동 수집 URL이 없습니다.
                </div>
              ) : (
                urls.map((item) => (
                  <div key={item.id} className="p-5 flex justify-between items-center hover:bg-slate-50 transition-colors">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-bold text-slate-800 text-sm">{item.source_name}</span>
                        <a href={item.url} target="_blank" rel="noreferrer" className="text-indigo-400 hover:text-indigo-600">
                          <FiExternalLink size={14} />
                        </a>
                      </div>
                      <div className="text-xs text-slate-400 truncate max-w-md">{item.url}</div>
                      <div className="text-[11px] text-slate-300 mt-1 font-mono">
                        최종 수집: {item.last_scraped || '없음'}
                      </div>
                    </div>
                    <button
                      onClick={() => handleDelete(item.id)}
                      className="p-2.5 text-rose-400 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition-all flex-shrink-0"
                      title="삭제"
                    >
                      <FiTrash2 size={18} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        {/* Source breakdown */}
        {stats && stats.by_source.length > 0 && (
          <section>
            <h2 className="text-lg font-bold text-slate-800 mb-5 flex items-center gap-2">
              <FiDatabase className="text-indigo-600" /> 소스별 수집 현황 상세
            </h2>
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 text-left">
                    <th className="px-5 py-3 font-bold text-slate-500 text-xs uppercase tracking-wider">소스</th>
                    <th className="px-5 py-3 font-bold text-slate-500 text-xs uppercase tracking-wider text-right">공고 수</th>
                    <th className="px-5 py-3 font-bold text-slate-500 text-xs uppercase tracking-wider text-right">비율</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {stats.by_source.map((s, i) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="px-5 py-3 font-medium text-slate-800">{s.source || '(미분류)'}</td>
                      <td className="px-5 py-3 text-right font-bold text-slate-900">{s.count.toLocaleString()}</td>
                      <td className="px-5 py-3 text-right text-slate-500">
                        {stats.total_announcements > 0 ? ((s.count / stats.total_announcements) * 100).toFixed(1) : 0}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        <footer className="text-center text-slate-400 text-xs pt-4 pb-8">
          &copy; 2026 지원금톡톡 &mdash; Admin Panel
        </footer>
      </div>
    </div>
  );
}
