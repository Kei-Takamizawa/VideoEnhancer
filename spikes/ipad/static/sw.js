// Tag browser-managed media, download and SSE requests as well as app fetches.
self.addEventListener('fetch', event => {
  if (new URL(event.request.url).origin !== self.location.origin) return;
  event.respondWith((async () => {
    const client = await self.clients.get(event.clientId);
    let mode = event.request.headers.get('X-Display-Mode');
    if (!mode && client) {
      mode = await new Promise(resolve => {
        const channel = new MessageChannel();
        const timer = setTimeout(() => { channel.port1.close(); resolve('unknown'); }, 1000);
        channel.port1.onmessage = message => {
          clearTimeout(timer); channel.port1.close(); resolve(message.data);
        };
        client.postMessage({type:'display-mode'}, [channel.port2]);
      });
    }
    const headers = new Headers(event.request.headers);
    headers.set('X-Display-Mode', mode || 'unknown');
    const response = await fetch(new Request(event.request, {headers}));
    if (response.status === 401) client?.postMessage({type:'unpaired'});
    return response;
  })());
});
// Do not cache authenticated data or media. The private CA must also work here.
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('push', event => {
  event.waitUntil((async () => {
    let data;
    try { data = event.data.json(); } catch { data = {title:'VideoEnhancer spike',body:'Test notification'}; }
    await self.registration.showNotification(data.title, {body:data.body, data:{url:'/'}});
    try {
      await fetch('/api/results', {method:'POST', credentials:'include', headers:{'Content-Type':'application/json','X-Display-Mode':'standalone'},
        body:JSON.stringify({test:'T3',display_mode:'standalone',notification_permission:Notification.permission,push_manager:'PushManager' in self,phase:'received',run:data.run,delay:data.delay,pass:true})});
    } catch { /* Reopening the app still allows the owner to report visible delivery. */ }
  })());
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow('/'));
});
