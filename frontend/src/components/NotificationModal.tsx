"use client";

import { useState, useEffect } from "react";

interface NotificationSettings {
  email: string;
  phone_number: string;
  channel: string;
  is_active: number;
}

export default function NotificationModal({ 
  isOpen, 
  onClose, 
  businessNumber,
  onSave 
}: { 
  isOpen: boolean; 
  onClose: () => void; 
  businessNumber: string;
  onSave: (data: any) => void;
}) {
  const [settings, setSettings] = useState<NotificationSettings>({
    email: "",
    phone_number: "",
    channel: "BOTH",
    is_active: 1
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && businessNumber) {
      fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/notification-settings/${businessNumber}`)
        .then(res => res.json())
        .then(result => {
          if (result.status === "SUCCESS" && result.data) {
            setSettings({
              email: result.data.email || "",
              phone_number: result.data.phone_number || "",
              channel: result.data.channel || "BOTH",
              is_active: result.data.is_active ?? 1
            });
          }
        })
        .catch(err => console.error("알림 설정 로드 실패:", err));
    }
  }, [isOpen, businessNumber]);

  const handleSave = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/notification-settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_number: businessNumber,
          ...settings
        })
      });
      const result = await res.json();
      if (result.status === "SUCCESS") {
        alert("알림 설정이 저장되었습니다. 🔔");
        onSave(settings);
        onClose();
      } else {
        alert("저장 실패: " + result.detail);
      }
    } catch (err) {
      alert("서버 연결 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-300"
        onClick={onClose}
      />
      
      {/* Modal Content */}
      <div className="relative w-full max-w-md bg-white rounded-[2rem] shadow-2xl border border-white/50 overflow-hidden animate-in zoom-in-95 duration-300">
        <div className="p-8 space-y-7">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-[10px] font-black text-indigo-500 uppercase tracking-widest">Settings</p>
              <h2 className="text-2xl font-black text-slate-900 tracking-tighter italic">알림 설정 <span className="text-indigo-600">Beta</span></h2>
            </div>
            <button 
              onClick={onClose}
              className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-slate-50 transition-colors text-slate-400"
            >
              ✕
            </button>
          </div>

          <div className="space-y-5">
            {/* Email Section */}
            <div className="space-y-2">
              <div className="flex items-center justify-between px-1">
                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Email Alert</label>
                <input 
                  type="checkbox" 
                  checked={settings.channel === "EMAIL" || settings.channel === "BOTH"}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    setSettings(prev => ({
                      ...prev,
                      channel: checked 
                        ? (prev.channel === "KAKAO" ? "BOTH" : "EMAIL")
                        : (prev.channel === "BOTH" ? "KAKAO" : "NONE")
                    }));
                  }}
                  className="w-5 h-5 rounded-md border-slate-200 text-indigo-600 focus:ring-indigo-500"
                />
              </div>
              <input 
                type="email"
                placeholder="email@example.com"
                value={settings.email}
                onChange={(e) => setSettings({...settings, email: e.target.value})}
                className="w-full p-4 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-bold focus:ring-4 focus:ring-indigo-500/5 focus:border-indigo-500 transition-all outline-none"
              />
            </div>

            {/* Kakao Section */}
            <div className="space-y-2">
              <div className="flex items-center justify-between px-1">
                <div className="flex items-center gap-2">
                  <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">KakaoTalk Alert</label>
                  <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 text-[8px] font-black rounded italic">PREP</span>
                </div>
                <input 
                  type="checkbox" 
                  checked={settings.channel === "KAKAO" || settings.channel === "BOTH"}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    setSettings(prev => ({
                      ...prev,
                      channel: checked 
                        ? (prev.channel === "EMAIL" ? "BOTH" : "KAKAO")
                        : (prev.channel === "BOTH" ? "EMAIL" : "NONE")
                    }));
                  }}
                  className="w-5 h-5 rounded-md border-slate-200 text-amber-500 focus:ring-amber-500"
                />
              </div>
              <input 
                type="tel"
                placeholder="010-0000-0000"
                value={settings.phone_number}
                onChange={(e) => setSettings({...settings, phone_number: e.target.value.replace(/[^0-9-]/g, "")})}
                className="w-full p-4 bg-slate-50 border border-slate-100 rounded-2xl text-sm font-bold focus:ring-4 focus:ring-indigo-500/5 focus:border-indigo-500 transition-all outline-none"
              />
              <p className="text-[9px] text-slate-400 font-medium px-1 leading-relaxed">
                * 카카오톡 알림은 현재 기술 검토 중이며, 번호를 등록해 두시면 서비스 개시 시 가장 먼저 알려드립니다.
              </p>
            </div>
          </div>

          <div className="pt-2">
            <button 
              onClick={handleSave}
              disabled={loading}
              className={`w-full py-5 bg-slate-900 text-white rounded-2xl font-black text-sm shadow-xl hover:bg-indigo-600 transition-all active:scale-95 flex items-center justify-center gap-2 ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {loading ? (
                <span className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
              ) : (
                <>설정 저장하기 <span className="italic">Apply</span></>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
