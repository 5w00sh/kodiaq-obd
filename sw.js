// Offline cache: network-first, falls back to cache (so it opens with no signal in the car)
const C = 'kodiaq-obd-v16';
const FILES = ['./', './index.html', './manifest.json', './icon.svg'];
self.addEventListener('install', e => { e.waitUntil(caches.open(C).then(c => c.addAll(FILES)).catch(()=>{})); });   // no skipWaiting here: the page offers the update and sends SKIP_WAITING when the user taps
self.addEventListener('message', e => { if (e.data && e.data.type === 'SKIP_WAITING') self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== C).map(k => caches.delete(k))))); self.clients.claim(); });
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;   // never touch weather/map look-ups
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok && r.type === 'basic') { const copy = r.clone(); caches.open(C).then(c => c.put(e.request, copy)); }
    return r;
  }).catch(() => caches.match(e.request).then(m => m || caches.match('./index.html'))));
});
