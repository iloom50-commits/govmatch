'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { FiPlus, FiTrash2, FiRefreshCw, FiExternalLink, FiDatabase, FiGlobe, FiCpu, FiLink, FiMail } from 'react-icons/fi';

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

export default function AdminPage() {
  const [urls, setUrls] = useState<AdminURL[]>([]);
  const [apis, setApis] = useState<SourceItem[]>([]);
  const [scrapers, setScrapers] = useState<SourceItem[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [newUrl, setNewUrl] = useState('');
  const [sourceName, setSourceName] = useState('');
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [digestSending, setDigestSending] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [urlRes, systemRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/urls`),
        fetch(`${API_URL}/api/admin/system-sources`),
        fetch(`${API_URL}/api/admin/stats`),
      ]);
      const urlData = await urlRes.json();
      const systemData = await systemRes.json();
      const statsData = await statsRes.json();

      if (urlData.status === 'SUCCESS') setUrls(urlData.data);
      if (systemData.status === 'SUCCESS') {
        setApis(systemData.data.apis || []);
        setScrapers(systemData.data.scrapers || []);
      }
      if (statsData.status === 'SUCCESS') setStats(statsData.data);
    } catch (err) {
      console.error('Failed to fetch admin data', err);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAddUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUrl || !sourceName) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/urls`, {
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
        alert(data.detail || '등록 실패');
      }
    } catch {
      alert('서버 연결 오류');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('정말 삭제하시겠습니까?')) return;
    try {
      const res = await fetch(`${API_URL}/api/admin/urls/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.status === 'SUCCESS') fetchData();
    } catch {
      alert('삭제 실패');
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await fetch(`${API_URL}/api/sync`, { method: 'POST' });
      const data = await res.json();
      alert(data.message || '동기화 완료');
      fetchData();
    } catch {
      alert('동기화 오류');
    } finally {
      setSyncing(false);
    }
  };

  const handleDigest = async () => {
    if (!confirm('등록된 사용자에게 다이제스트 이메일을 발송합니다. 계속할까요?')) return;
    setDigestSending(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/send-digest`, { method: 'POST' });
      const data = await res.json();
      alert(data.message || '발송 완료');
    } catch {
      alert('다이제스트 발송 오류');
    } finally {
      setDigestSending(false);
    }
  };

  const apiCount = stats ? stats.by_source.filter(s => s.source.includes('api')).reduce((sum, s) => sum + s.count, 0) : 0;
  const scraperCount = stats ? stats.by_source.filter(s => !s.source.includes('api') && !s.source.includes('admin')).reduce((sum, s) => sum + s.count, 0) : 0;
  const manualCount = stats ? stats.by_source.filter(s => s.source.includes('admin')).reduce((sum, s) => sum + s.count, 0) : 0;

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
              { label: '등록 사용자', value: stats.user_count, icon: <FiLink />, color: 'text-blue-600 bg-blue-50' },
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

        {/* Section 1: API Sources */}
        <section>
          <h2 className="text-lg font-bold text-slate-800 mb-5 flex items-center gap-2">
            <FiGlobe className="text-emerald-600" /> 공식 API 연동 현황
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {apis.map(source => (
              <div key={source.id} className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-bold text-slate-800 text-sm">{source.name}</h3>
                  <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border ${STATUS_BADGE[source.status] || 'bg-slate-100 text-slate-500 border-slate-200'}`}>
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

        {/* Section 2: Scrapers */}
        <section>
          <h2 className="text-lg font-bold text-slate-800 mb-5 flex items-center gap-2">
            <FiCpu className="text-amber-600" /> 웹 스크래퍼 현황
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {scrapers.map(source => (
              <div key={source.id} className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-bold text-slate-800 text-sm">{source.name}</h3>
                  <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border ${STATUS_BADGE[source.status] || 'bg-slate-100 text-slate-500 border-slate-200'}`}>
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

        {/* Section 3: Manual URLs */}
        <section>
          <h2 className="text-lg font-bold text-slate-800 mb-5 flex items-center gap-2">
            <FiPlus className="text-indigo-600" /> 수동 수집 관리 (URL)
            {manualCount > 0 && (
              <span className="text-xs font-bold text-slate-400 ml-2">{manualCount}건 수집됨</span>
            )}
          </h2>

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
                      <div className="text-[10px] text-slate-300 mt-1 font-mono">
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
          &copy; 2026 AI 맞춤 정부지원금 매칭 &mdash; Admin Panel
        </footer>
      </div>
    </div>
  );
}
