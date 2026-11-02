// Do not cache authenticated data or media. The private CA must also work here.
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('push', event => {
  event.waitUntil((async () => {
    let data;
    try { data = event.data.json(); } catch { data = {title:'VideoEnhancer spike',body:'Test notification'}; }
    await self.registration.showNotification(data.title, {body:data.body, data:{url:'/'}});
    try {
      await fetch('/api/results', {method:'POST', credentials:'include', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({test:'T3',phase:'received',run:data.run,delay:data.delay,pass:true})});
    } catch { /* Reopening the app still allows the owner to report visible delivery. */ }
  })());
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow('/'));
});
