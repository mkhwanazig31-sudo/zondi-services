self.addEventListener('install', e=>self.skipWaiting())
// Background sync - when internet comes back, send queued locations
self.addEventListener('sync', e=>{
  if(e.tag==='zondi-track') e.waitUntil(fetch('/api/sos/queue').then(r=>r.json()).then(q=>{/* send queued */}))
})
