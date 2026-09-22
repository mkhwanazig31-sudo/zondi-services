self.addEventListener('install', e=>{e.waitUntil(caches.open('zondi-v1').then(c=>c.addAll(['/','/shop','/login','/clients','/patrollers','/sos'])));});
self.addEventListener('fetch', e=>{e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));});
