import { readdirSync, writeFileSync, readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
const files = readdirSync('dist/assets').map(f => '/assets/'+f)
const version = createHash('sha256').update(files.join()).digest('hex').slice(0,12)
writeFileSync('dist/sw.js', `const CACHE='workleave-${version}'; const ASSETS=${JSON.stringify(['/', '/index.html', '/icon.svg', '/manifest.webmanifest', ...files])};
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS))));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('workleave-')&&k!==CACHE).map(k=>caches.delete(k))))));
self.addEventListener('fetch',event=>{const u=new URL(event.request.url);if(event.request.method!=='GET'||u.origin!==self.location.origin||u.pathname.startsWith('/api')||u.search)return;if(event.request.mode==='navigate'){event.respondWith(fetch(event.request).catch(()=>caches.match('/index.html')));return;}if(ASSETS.includes(u.pathname))event.respondWith(caches.match(event.request).then(c=>c||fetch(event.request)));});`)
