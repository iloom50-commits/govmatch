'use client';

import React, { useState, useEffect } from 'react';
import { FiPlus, FiTrash2, FiRefreshCw, FiExternalLink, FiSettings } from 'react-icons/fi';

interface AdminURL {
  id: number;
  url: string;
  source_name: string;
  last_scraped: string | null;
  is_active: boolean;
}

interface SystemSource {
  id: string;
  name: string;
  type: string;
  status: string;
  description: string;
}

export default function AdminPage() {
  const [urls, setUrls] = useState<AdminURL[]>([]);
  const [systemSources, setSystemSources] = useState<SystemSource[]>([]);
  const [newUrl, setNewUrl] = useState('');
  const [sourceName, setSourceName] = useState('');
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [urlRes, systemRes] = await Promise.all([
        fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/admin/urls`),
        fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/admin/system-sources`)
      ]);
      const urlData = await urlRes.json();
      const systemData = await systemRes.json();
      
      if (urlData.status === 'SUCCESS') setUrls(urlData.data);
      if (systemData.status === 'SUCCESS') setSystemSources(systemData.data);
    } catch (err) {
      console.error('Failed to fetch data', err);
    }
  };

  const handleAddUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUrl || !sourceName) return;

    setLoading(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/admin/urls`, {
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
    } catch (err) {
      alert('서버 연결 오류');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('정말 삭제하시겠습니까?')) return;
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/admin/urls/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.status === 'SUCCESS') fetchData();
    } catch (err) {
      alert('삭제 실패');
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/admin/sync-manual`, { method: 'POST' });
      const data = await res.json();
      alert(data.message);
      fetchData();
    } catch (err) {
      alert('동기화 오류');
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-8 text-slate-900">
      <div className="max-w-4xl mx-auto">
        <header className="flex justify-between items-center mb-12">
          <div>
            <h1 className="text-3xl font-bold tracking-tight mb-2">관리자 대시보드</h1>
            <p className="text-slate-500 text-sm">수동 수집 URL 및 AI 추출 엔진 통합 관리</p>
          </div>
          <button 
            onClick={handleSync}
            disabled={syncing}
            className={`flex items-center gap-2 px-6 py-3 rounded-xl font-semibold transition-all shadow-lg ${
              syncing 
                ? 'bg-slate-200 text-slate-400 cursor-not-allowed' 
                : 'bg-indigo-600 text-white hover:bg-indigo-700 hover:scale-105 active:scale-95'
            }`}
          >
            <FiRefreshCw className={syncing ? 'animate-spin' : ''} />
            {syncing ? 'AI 추출 중...' : '데이터 수집(API+URL) 실행'}
          </button>
        </header>

        {/* 1. 공식 API 연동 현황 */}
        <section className="mb-12">
          <h2 className="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
            <FiRefreshCw className="text-indigo-600" /> 공식 API 연동 현황
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {systemSources.map(source => (
              <div key={source.id} className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex justify-between items-start">
                <div>
                  <h3 className="font-bold text-slate-800 mb-1">{source.name}</h3>
                  <p className="text-xs text-slate-500 mb-3">{source.description}</p>
                  <span className={`px-2 py-1 rounded-md text-[10px] font-bold ${
                    source.status === 'LIVE' ? 'bg-emerald-50 text-emerald-600 border border-emerald-100' : 'bg-amber-50 text-amber-600 border border-amber-100'
                  }`}>
                    {source.status === 'LIVE' ? '연동 완료 (LIVE)' : '시뮬레이션 모드'}
                  </span>
                </div>
                <div className="p-2 bg-slate-50 rounded-lg">
                  <FiSettings className="text-slate-300" />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 2. 수동 수집 관리 */}
        <section className="mb-8">
          <div className="flex justify-between items-end mb-6">
            <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
              <FiPlus className="text-indigo-600" /> 수동 수집 관리 (URL 기반)
            </h2>
          </div>
          
          <div className="bg-white rounded-2xl p-8 shadow-sm border border-slate-200 mb-6">
            <form onSubmit={handleAddUrl} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">대상 사이트 명칭</label>
                <input 
                  type="text" 
                  placeholder="예: 부산시 일자리 정보망"
                  className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 outline-none focus:border-indigo-500 transition-colors"
                  value={sourceName}
                  onChange={(e) => setSourceName(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">공고 상세 URL</label>
                <input 
                  type="url" 
                  placeholder="https://..."
                  className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 outline-none focus:border-indigo-500 transition-colors"
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                />
              </div>
              <div className="md:col-span-2 flex justify-end mt-4">
                <button 
                  type="submit"
                  disabled={loading}
                  className="px-8 py-3 bg-indigo-50 text-indigo-700 font-bold rounded-xl hover:bg-indigo-100 transition-all border border-indigo-100"
                >
                  {loading ? '등록 중...' : 'URL 추가하기'}
                </button>
              </div>
            </form>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="divide-y divide-slate-100">
              {urls.length === 0 ? (
                <div className="p-12 text-center text-slate-400 italic">
                  등록된 수동 수집 URL이 없습니다.
                </div>
              ) : (
                urls.map((item) => (
                  <div key={item.id} className="p-6 flex justify-between items-center hover:bg-slate-50 transition-colors">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-bold text-slate-800">{item.source_name}</span>
                        <a href={item.url} target="_blank" rel="noreferrer" className="text-indigo-400 hover:text-indigo-600">
                          <FiExternalLink size={14} />
                        </a>
                      </div>
                      <div className="text-xs text-slate-400 truncate max-w-md">{item.url}</div>
                      <div className="text-[10px] text-slate-300 mt-2 font-mono">
                        Last Scraped: {item.last_scraped || 'Never'}
                      </div>
                    </div>
                    <button 
                      onClick={() => handleDelete(item.id)}
                      className="p-3 text-rose-400 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition-all"
                      title="삭제"
                    >
                      <FiTrash2 size={20} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        <footer className="mt-12 text-center text-slate-400 text-xs">
          Built with Gemini 2.0 Dynamic Engine &copy; 2026 Admin Panel
        </footer>
      </div>
    </div>
  );
}
