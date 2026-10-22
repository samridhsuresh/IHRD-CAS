const CACHE='campustrack-assets-v1';
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(['/','/icons/icon.svg','/manifest.webmanifest'])));self.skipWaiting()});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))));self.clients.claim()});
self.addEventListener('fetch',event=>{const req=event.request;if(req.method!=='GET'||req.url.includes('/api/')||req.mode==='navigate')return;event.respondWith(caches.match(req).then(cached=>cached||fetch(req).then(response=>{if(response.ok&&new URL(req.url).origin===self.location.origin){const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(req,copy))}return response}))) });
