const CACHE_VERSION = 'v2.2.0';
const STATIC_CACHE = `strike-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `strike-dynamic-${CACHE_VERSION}`;

// Core assets to pre-cache immediately on SW installation (App Shell)
const APP_SHELL = [
  '/',
  '/index.html',
  '/offline.html',
  '/manifest.json',
  '/favicon.svg',
  '/assets/icons/icon-192x192.png',
  '/assets/icons/icon-512x512.png',
  '/logo-128.png',
  '/logo.webp'
];

// Install Event: Open static cache and store the App Shell
self.addEventListener('install', (event) => {
  console.log('[SW] Installing Strike Tips service worker...');
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      console.log('[SW] Pre-caching application shell');
      return cache.addAll(APP_SHELL).catch((err) => {
        console.error('[SW] Failed to pre-cache some shell assets:', err);
      });
    })
  );
  // Don't skipWaiting here — let the app prompt the user first
});

// Limit total cache storage to 30 MB — evict oldest entries when exceeded
const MAX_CACHE_SIZE = 30 * 1024 * 1024; // 30 MB

async function enforceCacheLimit() {
  const cacheNames = await caches.keys();
  const targetCaches = cacheNames.filter((n) => n === STATIC_CACHE || n === DYNAMIC_CACHE);
  const entries = [];

  for (const name of targetCaches) {
    const cache = await caches.open(name);
    const keys = await cache.keys();
    for (const req of keys) {
      const resp = await cache.match(req);
      const size = resp ? parseInt(resp.headers.get('content-length') || '0', 10) || 0 : 0;
      entries.push({ cache, request: req, size });
    }
  }

  const total = entries.reduce((s, e) => s + e.size, 0);
  if (total <= MAX_CACHE_SIZE) return;

  // Sort oldest-first (by Storage API estimate — not perfect, but works)
  entries.sort((a, b) => (a.size - b.size));
  let toFree = total - MAX_CACHE_SIZE;
  for (const entry of entries) {
    if (toFree <= 0) break;
    await entry.cache.delete(entry.request);
    toFree -= entry.size;
  }
}

// Listen for clear-cache commands from the app
self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  if (event.data?.type === 'CLEAR_CACHE') {
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n.startsWith('strike-')).map((n) => caches.delete(n)))
    ).then(() => {
      self.clients.matchAll().then((clients) =>
        clients.forEach((client) => client.postMessage({ type: 'CACHE_CLEARED' }))
      );
    });
  }
});

// Activate Event: Clean up old caches, enforce storage limit
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name.startsWith('strike-') && name !== STATIC_CACHE && name !== DYNAMIC_CACHE)
          .map((name) => {
            console.log('[SW] Deleting deprecated cache:', name);
            return caches.delete(name);
          })
      );
    }).then(() => enforceCacheLimit())
  );
  // Claim clients immediately to manage pages under its scope
  self.clients.claim();
});

// Fetch Event: Apply cache/network strategy based on URL pattern
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 1. Only intercept GET requests
  if (request.method !== 'GET') return;

  // 2. Ignore Chrome extensions, dev-server HMR websockets, or Ollama requests
  if (url.origin !== location.origin) {
    // For external static assets (e.g., Telegram scripts or Web Fonts), we can cache them dynamically
    if (url.pathname.endsWith('.js') || url.hostname.includes('telegram.org') || url.hostname.includes('fonts.')) {
      event.respondWith(staleWhileRevalidate(request));
    }
    return;
  }

  // Local development HMR websocket (Vite)
  if (url.pathname.startsWith('/@vite') || url.pathname.startsWith('/src/')) {
    return;
  }

  // 3. Skip caching for Ollama local endpoints or FastAPI docs/openapi
  if (
    url.pathname.startsWith('/ollama') ||
    url.pathname.startsWith('/docs') ||
    url.pathname.startsWith('/openapi.json')
  ) {
    return;
  }

  // 4. API Requests Strategy: Network First with offline fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // 5. Skip caching large lazy-loaded Three.js chunk (dashboard needs internet anyway)
  if (url.pathname.match(/\/assets\/vendor-three-/)) {
    return;
  }

  // 6. Small static assets (CSS, JS, Images, Fonts) Strategy: Cache First
  if (url.pathname.match(/\.(css|js|png|jpg|jpeg|svg|webp|woff2?)$/) || url.pathname.includes('/assets/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // 6. Page navigation requests (HTML): Network First, falling back to cache or offline.html
  if (request.headers.get('Accept')?.includes('text/html')) {
    event.respondWith(networkFirst(request));
    return;
  }
});

// ─── Strategy Implementations ──────────────────────────────────────────────

// Strategy: Cache First, fallback to Network, then Cache write
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    const cache = await caches.open(STATIC_CACHE);
    // Cache the retrieved resource
    cache.put(request, response.clone());
    return response;
  } catch (err) {
    return new Response('Asset unavailable offline', { status: 503 });
  }
}

// Strategy: Network First, fallback to Cache, then fallback to offline.html
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    // Only cache successful standard responses
    if (response && response.status === 200) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;

    // If it's a page navigation request, show the offline fallback page
    if (request.headers.get('Accept')?.includes('text/html')) {
      const fallback = await caches.match('/offline.html');
      if (fallback) return fallback;
    }

    return new Response('Offline connection failed', { status: 503 });
  }
}

// Strategy: Stale While Revalidate
async function staleWhileRevalidate(request) {
  const cache = await caches.open(DYNAMIC_CACHE);
  const cached = await cache.match(request);
  const fetchPromise = fetch(request).then((response) => {
    if (response && response.status === 200) {
      cache.put(request, response.clone());
    }
    return response;
  }).catch(() => null);

  return cached || fetchPromise;
}
