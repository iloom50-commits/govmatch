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
 * businessNumber는 백엔드가 구독 row를 사용자와 매칭(WHERE business_number = %s)하는 데 필수다.
 */
export async function ensurePushSubscribed(businessNumber: string): Promise<boolean> {
  if (typeof window === "undefined") return false;
  if (!businessNumber) return false;
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
    // ★ 서버 저장 결과를 확인한다.
    //   전에는 .catch(()=>{}) 로 삼키고 무조건 true 를 돌려줬다. 서버에 구독이
    //   저장되지 않아도 화면의 토글은 켜졌고, 사용자는 알림이 오는 줄 알았다
    //   (2026-08-25 대표 제보 — "설정해도 저장되었다는 메시지가 없다").
    //   브라우저 구독만으로는 알림이 오지 않는다. 서버에 endpoint 가 있어야 한다.
    const res = await fetch(`${API}/api/push/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business_number: businessNumber, endpoint: subJson.endpoint, keys: subJson.keys }),
      signal: AbortSignal.timeout(8000),
    }).catch(() => null);
    return !!res && res.ok;
  } catch {
    return false;
  }
}

/** 브라우저가 웹 푸시를 지원하는지 */
export function isPushSupported(): boolean {
  return typeof window !== "undefined"
    && "serviceWorker" in navigator
    && "PushManager" in window
    && typeof Notification !== "undefined";
}

/** 현재 이 브라우저에서 푸시 구독 중인지 (권한 허용 + 구독 존재) */
export async function isPushSubscribed(): Promise<boolean> {
  if (!isPushSupported() || Notification.permission !== "granted") return false;
  try {
    const reg = await navigator.serviceWorker.getRegistration("/sw.js");
    return !!(reg && await reg.pushManager.getSubscription());
  } catch {
    return false;
  }
}

/** 푸시 켜기 — 권한 요청 후 구독 보장. 권한 거부/미지원 시 false. */
export async function enableWebPush(businessNumber: string): Promise<boolean> {
  if (!isPushSupported()) return false;
  let perm = Notification.permission;
  if (perm === "default") {
    try { perm = await Notification.requestPermission(); } catch { return false; }
  }
  if (perm !== "granted") return false;
  return ensurePushSubscribed(businessNumber);
}

/** 푸시 끄기 — 구독 해지 + 서버 통지 */
export async function disableWebPush(): Promise<boolean> {
  if (!isPushSupported()) return false;
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
    }).catch(() => {});
    return true;
  } catch {
    return false;
  }
}
