// PWA 설치 조건: fetch 핸들러가 반드시 있어야 함
self.addEventListener('fetch', (event) => {
  // 네트워크 우선 전략 (캐싱 없이 pass-through)
  event.respondWith(fetch(event.request));
});

self.addEventListener('push', (event) => {
  let data = { title: '지원금AI', body: '새로운 알림이 있습니다.', url: '/' };
  try {
    data = event.data.json();
  } catch (e) { /* use defaults */ }

  event.waitUntil(
    self.registration.showNotification(data.title || '지원금AI', {
      body: data.body,
      icon: 'https://www.govmatch.kr/icon-192.png',
      badge: 'https://www.govmatch.kr/icon-128.png',
      tag: 'govmatch',
      renotify: true,
      data: { url: data.url || '/' },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // 이미 열린 탭이 있으면 포커스, 없으면 새 탭
      for (const client of clientList) {
        if (client.url === url && 'focus' in client) {
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
