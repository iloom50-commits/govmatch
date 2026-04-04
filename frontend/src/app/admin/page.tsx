'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { FiPlus, FiTrash2, FiRefreshCw, FiExternalLink, FiDatabase, FiGlobe, FiCpu, FiMail, FiLock, FiUsers, FiLogOut, FiBarChart2, FiTrendingUp, FiBell, FiPieChart } from 'react-icons/fi';
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

interface AnalyticsData {
  signup_trend: { date: string; count: number }[];
  plan_distribution: { plan: string; count: number }[];
  user_type_distribution: { type: string; count: number }[];
  ai_usage_trend: { date: string; count: number }[];
  ai_stats: { total: number; helpful: number; inaccurate: number };
  notification_trend: { date: string; success: number; failed: number }[];
  notification_stats: { total: number; success: number; failed: number };
  saved_total: number;
  push_subscribers: number;
  notification_active_users: number;
  region_distribution: { region: string; count: number }[];
  crawl_trend: { date: string; count: number }[];
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
  const [activeTab, setActiveTab] = useState<'overview' | 'analytics' | 'strategy' | 'logs'>('overview');
  const [strategyReport, setStrategyReport] = useState<string>('');
  const [strategyLoading, setStrategyLoading] = useState(false);
  const [reportHistory, setReportHistory] = useState<{id:number;report:string;created_at:string}[]>([]);
  const [systemLogs, setSystemLogs] = useState<any[]>([]);
  const [logSummary, setLogSummary] = useState<any[]>([]);
  const [logCategory, setLogCategory] = useState<string>('');
  const [urls, setUrls] = useState<AdminURL[]>([]);
  const [apis, setApis] = useState<SourceItem[]>([]);
  const [scrapers, setScrapers] = useState<SourceItem[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
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
      const [urlRes, systemRes, statsRes, usersRes, analyticsRes] = await Promise.all([
        authFetch(`${API_URL}/api/admin/urls`),
        authFetch(`${API_URL}/api/admin/system-sources`),
        authFetch(`${API_URL}/api/admin/stats`),
        authFetch(`${API_URL}/api/admin/users`),
        authFetch(`${API_URL}/api/admin/analytics`),
      ]);

      if (urlRes.status === 401 || statsRes.status === 401) {
        onLogout();
        return;
      }

      const urlData = await urlRes.json().catch(() => ({}));
      const systemData = await systemRes.json().catch(() => ({}));
      const statsData = await statsRes.json().catch(() => ({}));
      const usersData = await usersRes.json().catch(() => ({}));
      const analyticsData = await analyticsRes.json().catch(() => ({}));

      if (urlData.status === 'SUCCESS') setUrls(urlData.data);
      if (systemData.status === 'SUCCESS') {
        setApis(systemData.data.apis || []);
        setScrapers(systemData.data.scrapers || []);
      }
      if (statsData.status === 'SUCCESS') setStats(statsData.data);
      if (usersData.status === 'SUCCESS') setUsers(usersData.data);
      if (analyticsData.status === 'SUCCESS') setAnalytics(analyticsData.data);
    } catch (err) {
      console.error('Failed to fetch admin data', err);
    } finally {
      setInitialLoading(false);
    }
  }, [authFetch, onLogout]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const generateStrategy = async () => {
    setStrategyLoading(true);
    try {
      const res = await authFetch(`${API_URL}/api/admin/strategy-report`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'SUCCESS') {
        setStrategyReport(data.report);
        toast('AI 전략 보고서가 생성되었습니다.', 'success');
      }
    } catch { toast('보고서 생성 실패', 'error'); }
    finally { setStrategyLoading(false); }
  };

  const loadReportHistory = async () => {
    try {
      const res = await authFetch(`${API_URL}/api/admin/strategy-reports`);
      const data = await res.json();
      if (data.status === 'SUCCESS') setReportHistory(data.data);
    } catch {}
  };

  useEffect(() => { if (activeTab === 'strategy') loadReportHistory(); }, [activeTab]);

  const loadSystemLogs = async (cat?: string) => {
    try {
      const url = cat ? `${API_URL}/api/admin/system-logs?category=${cat}&limit=100` : `${API_URL}/api/admin/system-logs?limit=100`;
      const res = await authFetch(url);
      const data = await res.json().catch(() => ({}));
      if (data.status === 'SUCCESS') {
        setSystemLogs(data.data || []);
        setLogSummary(data.summary || []);
      }
    } catch {}
  };

  useEffect(() => { if (activeTab === 'logs') loadSystemLogs(logCategory || undefined); }, [activeTab, logCategory]);

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
        <header className="flex flex-col gap-4">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
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
          </div>
          {/* Tab Navigation */}
          <div className="flex gap-1 bg-white rounded-xl p-1 border border-slate-200 shadow-sm w-fit">
            <button
              onClick={() => setActiveTab('overview')}
              className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-bold transition-all ${
                activeTab === 'overview'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`}
            >
              <FiDatabase size={15} /> 운영 관리
            </button>
            <button
              onClick={() => setActiveTab('analytics')}
              className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-bold transition-all ${
                activeTab === 'analytics'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`}
            >
              <FiBarChart2 size={15} /> 사용 분석
            </button>
            <button
              onClick={() => setActiveTab('strategy')}
              className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-bold transition-all ${
                activeTab === 'strategy'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`}
            >
              <FiTrendingUp size={15} /> AI 전략
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-bold transition-all ${
                activeTab === 'logs'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`}
            >
              <FiRefreshCw size={15} /> 활동 이력
            </button>
          </div>
        </header>

        {/* Stats Cards — always visible */}
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

        {/* ═══════════ Analytics Tab ═══════════ */}
        {activeTab === 'analytics' && analytics && <AnalyticsPanel data={analytics} />}

        {/* ═══════════ Strategy Tab ═══════════ */}
        {activeTab === 'strategy' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-black text-slate-900">AI 성장 전략 보고서</h2>
              <button
                onClick={generateStrategy}
                disabled={strategyLoading}
                className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-xl text-sm font-bold hover:shadow-lg transition-all disabled:opacity-50"
              >
                {strategyLoading ? (
                  <><span className="animate-spin">&#9881;</span> AI 분석 중... (30초~1분)</>
                ) : (
                  <><FiTrendingUp size={16} /> 새 보고서 생성</>
                )}
              </button>
            </div>

            {strategyReport && (
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 md:p-8">
                <div
                  className="prose prose-sm max-w-none prose-headings:text-slate-900 prose-h2:text-lg prose-h3:text-base prose-p:text-slate-600 prose-li:text-slate-600 prose-strong:text-slate-800"
                  dangerouslySetInnerHTML={{
                    __html: strategyReport
                      .replace(/^### (.*$)/gm, '<h3 class="font-bold mt-6 mb-2">$1</h3>')
                      .replace(/^## (.*$)/gm, '<h2 class="font-black mt-8 mb-3 text-indigo-900 border-b border-indigo-100 pb-2">$1</h2>')
                      .replace(/^# (.*$)/gm, '<h1 class="font-black mt-6 mb-4 text-xl">$1</h1>')
                      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                      .replace(/^- (.*$)/gm, '<li class="ml-4">$1</li>')
                      .replace(/^(\d+)\. (.*$)/gm, '<li class="ml-4"><strong>$1.</strong> $2</li>')
                      .replace(/\n\n/g, '<br/><br/>')
                      .replace(/\n/g, '<br/>')
                  }}
                />
              </div>
            )}

            {reportHistory.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-bold text-slate-500">이전 보고서</h3>
                {reportHistory.map((r) => (
                  <details key={r.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                    <summary className="px-4 py-3 cursor-pointer hover:bg-slate-50 text-sm font-medium text-slate-700">
                      {r.created_at.slice(0, 16).replace('T', ' ')} 보고서
                    </summary>
                    <div className="px-4 pb-4 text-xs text-slate-500 whitespace-pre-wrap max-h-96 overflow-y-auto">
                      {r.report}
                    </div>
                  </details>
                ))}
              </div>
            )}

            {!strategyReport && !strategyLoading && reportHistory.length === 0 && (
              <div className="text-center py-16 text-slate-400">
                <FiTrendingUp size={48} className="mx-auto mb-4 opacity-30" />
                <p className="text-sm font-medium">&quot;새 보고서 생성&quot; 버튼을 눌러 AI 전략 분석을 시작하세요</p>
                <p className="text-xs mt-1">사용자 행동 데이터를 기반으로 서비스 활성화 전략을 제안합니다</p>
              </div>
            )}
          </div>
        )}

        {/* ═══════════ Logs Tab ═══════════ */}
        {activeTab === 'logs' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <h2 className="text-lg font-black text-slate-900">시스템 활동 이력</h2>
              <div className="flex gap-2">
                {['', 'collection', 'analysis', 'notification', 'payment', 'system'].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setLogCategory(cat)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                      logCategory === cat ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                    }`}
                  >
                    {cat === '' ? '전체' : cat === 'collection' ? '수집' : cat === 'analysis' ? '분석' : cat === 'notification' ? '알림' : cat === 'payment' ? '결제' : '시스템'}
                  </button>
                ))}
              </div>
            </div>

            {/* 요약 카드 */}
            {logSummary.length > 0 && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {logSummary.slice(0, 8).map((s: any, i: number) => (
                  <div key={i} className="bg-white rounded-xl border border-slate-200 p-3">
                    <div className="text-[11px] text-slate-400 font-bold uppercase">{s.category} / {s.action}</div>
                    <div className="text-sm font-bold text-slate-800 mt-1">
                      {s.success_count}건 성공 {s.error_count > 0 && <span className="text-red-500">/ {s.error_count} 실패</span>}
                    </div>
                    <div className="text-[10px] text-slate-400 mt-0.5">최근: {s.last_run?.slice(0, 16).replace('T', ' ')}</div>
                  </div>
                ))}
              </div>
            )}

            {/* 이력 테이블 */}
            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="text-left px-4 py-2.5 text-[11px] font-bold text-slate-500 uppercase">시간</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-bold text-slate-500 uppercase">카테고리</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-bold text-slate-500 uppercase">작업</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-bold text-slate-500 uppercase">상세</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-bold text-slate-500 uppercase">결과</th>
                  </tr>
                </thead>
                <tbody>
                  {systemLogs.length === 0 ? (
                    <tr><td colSpan={5} className="text-center py-8 text-slate-400 text-sm">아직 기록된 활동이 없습니다. 수집/분석/알림 실행 후 이력이 쌓입니다.</td></tr>
                  ) : systemLogs.map((log: any) => (
                    <tr key={log.id} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="px-4 py-2 text-xs text-slate-500 whitespace-nowrap">{log.created_at?.slice(0, 16).replace('T', ' ')}</td>
                      <td className="px-4 py-2">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          log.category === 'collection' ? 'bg-blue-50 text-blue-600' :
                          log.category === 'analysis' ? 'bg-violet-50 text-violet-600' :
                          log.category === 'notification' ? 'bg-amber-50 text-amber-600' :
                          log.category === 'payment' ? 'bg-emerald-50 text-emerald-600' :
                          'bg-slate-100 text-slate-500'
                        }`}>{log.category}</span>
                      </td>
                      <td className="px-4 py-2 text-xs font-medium text-slate-700">{log.action}</td>
                      <td className="px-4 py-2 text-xs text-slate-500 max-w-xs truncate">{log.detail}</td>
                      <td className="px-4 py-2">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          log.result === 'success' ? 'bg-green-50 text-green-600' :
                          log.result === 'error' ? 'bg-red-50 text-red-600' :
                          'bg-yellow-50 text-yellow-600'
                        }`}>{log.result}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ═══════════ Overview Tab ═══════════ */}
        {activeTab === 'overview' && <>

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

        </>}

        <footer className="text-center text-slate-400 text-xs pt-4 pb-8">
          &copy; 2026 지원금AI &mdash; Admin Panel
        </footer>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════
   Mini Bar Chart (CSS-only, no chart library)
   ═══════════════════════════════════════════════ */
function MiniBarChart({ data, color = 'bg-indigo-500', height = 120 }: { data: { label: string; value: number }[]; color?: string; height?: number }) {
  const max = Math.max(...data.map(d => d.value), 1);
  return (
    <div className="flex items-end gap-[3px] w-full" style={{ height }}>
      {data.map((d, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1 min-w-0">
          <div
            className={`w-full rounded-t-sm ${color} transition-all duration-300 min-h-[2px]`}
            style={{ height: `${Math.max((d.value / max) * 100, 2)}%` }}
            title={`${d.label}: ${d.value}`}
          />
          {data.length <= 15 && (
            <span className="text-[9px] text-slate-400 truncate w-full text-center">{d.label.slice(5)}</span>
          )}
        </div>
      ))}
    </div>
  );
}

function DonutChart({ segments, size = 100 }: { segments: { label: string; value: number; color: string }[]; size?: number }) {
  const total = segments.reduce((s, seg) => s + seg.value, 0) || 1;
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <svg width={size} height={size} viewBox="0 0 100 100">
      {segments.map((seg, i) => {
        const pct = seg.value / total;
        const dash = pct * circumference;
        const currentOffset = offset;
        offset += dash;
        return (
          <circle
            key={i}
            cx="50" cy="50" r={radius}
            fill="none"
            stroke={seg.color}
            strokeWidth="18"
            strokeDasharray={`${dash} ${circumference - dash}`}
            strokeDashoffset={-currentOffset}
            className="transition-all duration-500"
          />
        );
      })}
      <text x="50" y="50" textAnchor="middle" dominantBaseline="central" className="text-lg font-black fill-slate-800" fontSize="18">
        {total}
      </text>
    </svg>
  );
}

const PLAN_LABELS: Record<string, string> = { free: '무료', basic: '베이직', pro: 'PRO', premium: '프리미엄' };
const PLAN_COLORS: Record<string, string> = { free: '#94a3b8', basic: '#6366f1', pro: '#8b5cf6', premium: '#f59e0b' };
const TYPE_LABELS: Record<string, string> = { business: '기업', individual: '개인', both: '기업+개인' };

function AnalyticsPanel({ data }: { data: AnalyticsData }) {
  return (
    <div className="space-y-8">

      {/* Row 1: Key Metrics */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'AI 상담 총 건수', value: data.ai_stats.total, icon: <FiCpu />, color: 'text-purple-600 bg-purple-50' },
          { label: '알림 발송 총 건수', value: data.notification_stats.total, icon: <FiBell />, color: 'text-amber-600 bg-amber-50' },
          { label: '푸시 구독자', value: data.push_subscribers, icon: <FiTrendingUp />, color: 'text-emerald-600 bg-emerald-50' },
          { label: '저장된 공고', value: data.saved_total, icon: <FiPieChart />, color: 'text-blue-600 bg-blue-50' },
        ].map((card, i) => (
          <div key={i} className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200">
            <div className="flex items-center gap-3 mb-3">
              <div className={`p-2 rounded-lg ${card.color}`}>{card.icon}</div>
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">{card.label}</span>
            </div>
            <p className="text-2xl font-black text-slate-900">{card.value.toLocaleString()}</p>
          </div>
        ))}
      </section>

      {/* Row 2: Signup Trend + AI Usage Trend */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-bold text-slate-800 mb-1 flex items-center gap-2">
            <FiUsers className="text-blue-500" /> 일별 가입자 추이 <span className="text-xs font-normal text-slate-400">(최근 30일)</span>
          </h3>
          {data.signup_trend.length > 0 ? (
            <div className="mt-4">
              <MiniBarChart
                data={data.signup_trend.map(d => ({ label: d.date, value: d.count }))}
                color="bg-blue-500"
              />
              <div className="flex justify-between mt-2 text-[10px] text-slate-400">
                <span>{data.signup_trend[0]?.date.slice(5)}</span>
                <span className="font-bold text-blue-600">
                  총 {data.signup_trend.reduce((s, d) => s + d.count, 0)}명
                </span>
                <span>{data.signup_trend[data.signup_trend.length - 1]?.date.slice(5)}</span>
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-400 mt-4">데이터 없음</p>
          )}
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-bold text-slate-800 mb-1 flex items-center gap-2">
            <FiCpu className="text-purple-500" /> AI 상담 일별 추이 <span className="text-xs font-normal text-slate-400">(최근 30일)</span>
          </h3>
          {data.ai_usage_trend.length > 0 ? (
            <div className="mt-4">
              <MiniBarChart
                data={data.ai_usage_trend.map(d => ({ label: d.date, value: d.count }))}
                color="bg-purple-500"
              />
              <div className="flex justify-between mt-2 text-[10px] text-slate-400">
                <span>{data.ai_usage_trend[0]?.date.slice(5)}</span>
                <span className="font-bold text-purple-600">
                  총 {data.ai_usage_trend.reduce((s, d) => s + d.count, 0)}건
                </span>
                <span>{data.ai_usage_trend[data.ai_usage_trend.length - 1]?.date.slice(5)}</span>
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-400 mt-4">데이터 없음</p>
          )}
        </div>
      </section>

      {/* Row 3: Plan Distribution + User Type + Region */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Plan Distribution */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-bold text-slate-800 mb-4">요금제 분포</h3>
          <div className="flex items-center gap-6">
            <DonutChart
              segments={data.plan_distribution.map(p => ({
                label: PLAN_LABELS[p.plan] || p.plan,
                value: p.count,
                color: PLAN_COLORS[p.plan] || '#cbd5e1',
              }))}
            />
            <div className="space-y-2 flex-1">
              {data.plan_distribution.map((p, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: PLAN_COLORS[p.plan] || '#cbd5e1' }} />
                    <span className="text-xs font-medium text-slate-600">{PLAN_LABELS[p.plan] || p.plan}</span>
                  </div>
                  <span className="text-xs font-black text-slate-800">{p.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* User Type */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-bold text-slate-800 mb-4">사용자 유형</h3>
          <div className="space-y-3">
            {data.user_type_distribution.map((t, i) => {
              const total = data.user_type_distribution.reduce((s, d) => s + d.count, 0) || 1;
              const pct = Math.round((t.count / total) * 100);
              return (
                <div key={i}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-medium text-slate-600">{TYPE_LABELS[t.type] || t.type}</span>
                    <span className="font-black text-slate-800">{t.count}명 ({pct}%)</span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-2">
                    <div className="bg-indigo-500 h-2 rounded-full transition-all" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Region */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-bold text-slate-800 mb-4">지역별 사용자</h3>
          <div className="space-y-2 max-h-[200px] overflow-y-auto">
            {data.region_distribution.map((r, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <span className="text-slate-600">{r.region}</span>
                <div className="flex items-center gap-2">
                  <div className="w-16 bg-slate-100 rounded-full h-1.5">
                    <div
                      className="bg-emerald-500 h-1.5 rounded-full"
                      style={{ width: `${Math.round((r.count / (data.region_distribution[0]?.count || 1)) * 100)}%` }}
                    />
                  </div>
                  <span className="font-black text-slate-800 w-8 text-right">{r.count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Row 4: Notification + AI Feedback + Crawl Trend */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Notification Trend */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-bold text-slate-800 mb-1 flex items-center gap-2">
            <FiBell className="text-amber-500" /> 알림 발송 추이
          </h3>
          <div className="flex gap-4 mt-2 mb-3">
            <div className="text-center">
              <p className="text-lg font-black text-emerald-600">{data.notification_stats.success}</p>
              <p className="text-[10px] text-slate-400">성공</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-black text-rose-500">{data.notification_stats.failed}</p>
              <p className="text-[10px] text-slate-400">실패</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-black text-blue-600">{data.notification_active_users}</p>
              <p className="text-[10px] text-slate-400">활성 구독</p>
            </div>
          </div>
          {data.notification_trend.length > 0 ? (
            <MiniBarChart
              data={data.notification_trend.map(d => ({ label: d.date, value: d.success + d.failed }))}
              color="bg-amber-500"
              height={80}
            />
          ) : (
            <p className="text-xs text-slate-400">발송 이력 없음</p>
          )}
        </div>

        {/* AI Feedback */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-bold text-slate-800 mb-4">AI 상담 피드백</h3>
          <div className="flex items-center justify-center gap-8">
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-emerald-50 border-4 border-emerald-200 flex items-center justify-center mb-2">
                <span className="text-lg font-black text-emerald-600">{data.ai_stats.helpful}</span>
              </div>
              <p className="text-[11px] font-bold text-emerald-600">도움됨</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-rose-50 border-4 border-rose-200 flex items-center justify-center mb-2">
                <span className="text-lg font-black text-rose-500">{data.ai_stats.inaccurate}</span>
              </div>
              <p className="text-[11px] font-bold text-rose-500">부정확</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-slate-50 border-4 border-slate-200 flex items-center justify-center mb-2">
                <span className="text-lg font-black text-slate-600">{data.ai_stats.total - data.ai_stats.helpful - data.ai_stats.inaccurate}</span>
              </div>
              <p className="text-[11px] font-bold text-slate-400">미평가</p>
            </div>
          </div>
          {data.ai_stats.total > 0 && (
            <div className="mt-4 text-center">
              <span className="text-xs text-slate-400">만족도: </span>
              <span className="text-sm font-black text-indigo-600">
                {data.ai_stats.helpful + data.ai_stats.inaccurate > 0
                  ? Math.round((data.ai_stats.helpful / (data.ai_stats.helpful + data.ai_stats.inaccurate)) * 100)
                  : 0}%
              </span>
            </div>
          )}
        </div>

        {/* Crawl Trend */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-bold text-slate-800 mb-1 flex items-center gap-2">
            <FiDatabase className="text-indigo-500" /> 공고 수집 추이 <span className="text-xs font-normal text-slate-400">(14일)</span>
          </h3>
          {data.crawl_trend.length > 0 ? (
            <div className="mt-4">
              <MiniBarChart
                data={data.crawl_trend.map(d => ({ label: d.date, value: d.count }))}
                color="bg-indigo-500"
                height={100}
              />
              <p className="text-[10px] text-slate-400 mt-2 text-center">
                최근 14일간 총 <span className="font-bold text-indigo-600">{data.crawl_trend.reduce((s, d) => s + d.count, 0).toLocaleString()}</span>건 수집
              </p>
            </div>
          ) : (
            <p className="text-xs text-slate-400 mt-4">데이터 없음</p>
          )}
        </div>
      </section>
    </div>
  );
}
