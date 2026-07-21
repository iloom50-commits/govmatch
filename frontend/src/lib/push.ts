// 웹 푸시 구독 유틸 — AiConsultModal 등에서 재사용
// 주의: 이 함수는 알림 권한 요청(Notification.requestPermission)을 하지 않는다.
// 호출 전에 권한이 "granted"인지 호출부에서 확인해야 한다.
const API = process.env.NEXT_PUBLIC_API_URL;

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

/**
 * 이미 권한이 허용된 상태에서 푸시 구독을 보장한다.
 * 기존 구독이 있으면 서버에 재전송(idempotent)하고, 없으면 새로 구독한다.
 */
export async function ensurePushSubscribed(): Promise<boolean> {
  if (typeof window === "undefined") return false;
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return false;
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return false;

  try {
    const reg = await navigator.serviceWorker.getRegistration("/sw.js")
      || await navigator.serviceWorker.register("/sw.js");
    if (!reg) return false;

    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      const vapidRes = await fetch(`${API}/api/push/vapid-key`).then(r => r.json()).catch(() => null);
      if (!vapidRes?.publicKey) return false;
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidRes.publicKey) as BufferSource,
      });
    }

    const subJson = sub.toJSON();
    await fetch(`${API}/api/push/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint: subJson.endpoint, keys: subJson.keys }),
    }).catch(() => {});
    return true;
  } catch {
    return false;
  }
}
