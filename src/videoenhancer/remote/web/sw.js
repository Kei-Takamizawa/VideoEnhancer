const CACHE = 've-shell-r1c-v1';
const SHELL = ['/', '/style.css', '/app.mjs', '/logic.mjs', '/add.mjs', '/add-ui.mjs', '/platform.mjs', '/player.mjs', '/manifest.webmanifest', '/icon.svg', '/apple-touch-icon.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.search || !SHELL.includes(url.pathname)) return;
  event.respondWith(fetch(request).catch(() => caches.match(url.pathname).then(response => response || Response.error())));
});

self.addEventListener('push', event => {
  let payload;
  try { payload = event.data?.json(); } catch { return; }
  if (!payload || typeof payload.title !== 'string' || typeof payload.body !== 'string') return;
  const url = /^\/#item=[A-Za-z0-9_-]{1,128}$/.test(payload.url) ? payload.url : '/';
  event.waitUntil(self.registration.showNotification(payload.title, {
    body: payload.body, icon: '/apple-touch-icon.png', data: {url},
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const path = event.notification.data?.url;
  const safe = /^\/#item=[A-Za-z0-9_-]{1,128}$/.test(path) ? path : '/';
  const url = new URL(safe, self.location.origin).href;
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({type: 'window', includeUncontrolled: true});
    const existing = windows.find(client => new URL(client.url).origin === self.location.origin);
    if (existing) {
      await existing.navigate(url);
      return existing.focus();
    }
    return self.clients.openWindow(url);
  })());
});
