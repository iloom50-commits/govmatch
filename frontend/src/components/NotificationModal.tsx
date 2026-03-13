"use client";

import { useState, useEffect } from "react";
import { useToast } from "@/components/ui/Toast";

const API = process.env.NEXT_PUBLIC_API_URL;

interface NotificationSettings {
  email: string;
  phone_number: string;
  channel: string;
  is_active: number;
}

async function subscribePush(bn: string): Promise<boolean> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return false;
  try {
    const reg = await navigator.serviceWorker.register("/sw.js");
    const existing = await reg.pushManager.getSubscription();
    if (existing) return true;

    const res = await fetch(`${API}/api/push/vapid-key`);
    const { publicKey } = await res.json();
    if (!publicKey) return false;

    const perm = await Notification.requestPermission();
    if (perm !== "granted") return false;

    const padding = "=".repeat((4 - (publicKey.length % 4)) % 4);
    const base64 = (publicKey + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(base64);
    const applicationServerKey = Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));

    const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey });
    const subJson = sub.toJSON();
    await fetch(`${API}/api/push/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business_number: bn, endpoint: subJson.endpoint, keys: subJson.keys }),
    });
    return true;
  } catch (e) {
    console.warn("Push subscription failed:", e);
    return false;
  }
}

async function unsubscribePush(): Promise<boolean> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return false;
  try {
    const reg = await navigator.serviceWorker.getRegistration("/sw.js");
    if (!reg) return true;
    const existing = await reg.pushManager.getSubscription();
    if (!existing) return true;

    const endpoint = existing.endpoint;
    await existing.unsubscribe();
    await fetch(`${API}/api/push/unsubscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint }),
    });
    return true;
  } catch (e) {
    console.warn("Push unsubscribe failed:", e);
    return false;
  }
}

async function isPushSubscribed(): Promise<boolean> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return false;
  try {
    const reg = await navigator.serviceWorker.getRegistration("/sw.js");
    if (!reg) return false;
    const sub = await reg.pushManager.getSubscription();
    return !!sub;
  } catch {
    return false;
  }
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
  const { toast } = useToast();
  const [settings, setSettings] = useState<NotificationSettings>({
    email: "",
    phone_number: "",
    channel: "BOTH",
    is_active: 1
  });
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushLoading, setPushLoading] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && businessNumber) {
      fetch(`${API}/api/notification-settings/${businessNumber}`)
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

      // 현재 브라우저 푸시 구독 상태 확인
      isPushSubscribed().then(setPushEnabled);
    }
  }, [isOpen, businessNumber]);

  const handlePushToggle = async (enabled: boolean) => {
    setPushLoading(true);
    try {
      if (enabled) {
        const ok = await subscribePush(businessNumber);
        if (ok) {
          setPushEnabled(true);
          toast("브라우저 푸시 알림이 활성화되었습니다.", "success");
        } else {
          toast("푸시 알림 권한이 거부되었거나 지원되지 않습니다.", "error");
        }
      } else {
        const ok = await unsubscribePush();
        if (ok) {
          setPushEnabled(false);
          toast("브라우저 푸시 알림이 해제되었습니다.", "success");
        }
      }
    } finally {
      setPushLoading(false);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/notification-settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_number: businessNumber,
          ...settings
        })
      });
      const result = await res.json();
      if (result.status === "SUCCESS") {
        toast("알림 설정이 저장되었습니다.", "success");
        onSave(settings);
        onClose();
      } else {
        toast("저장 실패: " + result.detail, "error");
      }
    } catch {
      toast("서버 연결 오류가 발생했습니다.", "error");
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

            {/* Web Push Section */}
            <div className="space-y-2">
              <div className="flex items-center justify-between px-1">
                <div className="flex items-center gap-2">
                  <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Browser Push</label>
                  {"Notification" in window && Notification.permission === "denied" && (
                    <span className="px-1.5 py-0.5 bg-red-100 text-red-600 text-[8px] font-black rounded italic">BLOCKED</span>
                  )}
                </div>
                <button
                  disabled={pushLoading}
                  onClick={() => handlePushToggle(!pushEnabled)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
                    pushEnabled ? "bg-indigo-600" : "bg-slate-200"
                  } ${pushLoading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                      pushEnabled ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>
              <p className="text-[9px] text-slate-400 font-medium px-1 leading-relaxed">
                * 이 브라우저/기기에서 새 공고 알림을 즉시 받습니다. iOS는 홈화면 추가(PWA) 후 사용 가능합니다.
              </p>
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
