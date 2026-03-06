/**
 * Qubitcoin Service Worker
 * Provides offline-first capability with stale-while-revalidate for API data
 * and cache-first for static assets.
 */

const CACHE_VERSION = "qbc-v2";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE = `${CACHE_VERSION}-api`;
const OFFLINE_URL = "/offline.html";

/** Static assets to precache on install (app shell). */
const PRECACHE_URLS = [
  "/",
  "/offline.html",
  "/manifest.json",
];

/** API path prefixes that should use stale-while-revalidate. */
const CACHEABLE_API_PATHS = [
  "/api/chain/info",
  "/api/chain/tip",
  "/api/balance/",
  "/api/block/",
  "/api/aether/phi",
  "/api/aether/knowledge",
  "/api/aether/consciousness",
  "/api/economics/emission",
  "/api/mining/stats",
  "/api/qvm/info",
  "/api/health",
  "/api/info",
];

/**
 * Max age for cached API responses (in milliseconds).
 * After this, the cache entry is considered expired and must be revalidated.
 */
const API_CACHE_MAX_AGE_MS = 30_000; // 30 seconds

// -----------------------------------------------------------------------
// Install: precache static assets
// -----------------------------------------------------------------------
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// -----------------------------------------------------------------------
// Activate: clean old caches
// -----------------------------------------------------------------------
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== STATIC_CACHE && key !== API_CACHE)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

// -----------------------------------------------------------------------
// Fetch: strategy depends on request type
// -----------------------------------------------------------------------
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle GET requests
  if (request.method !== "GET") return;

  // Skip chrome-extension and other non-http schemes
  if (!url.protocol.startsWith("http")) return;

  // API requests: stale-while-revalidate
  if (isCacheableApiRequest(url)) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }

  // Navigation requests: network-first with offline fallback
  if (request.mode === "navigate") {
    event.respondWith(networkFirstWithOfflineFallback(request));
    return;
  }

  // Static assets: cache-first
  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(request));
    return;
  }
});

// -----------------------------------------------------------------------
// Strategy: stale-while-revalidate (for API data)
// Returns cached response immediately, then updates the cache in background.
// -----------------------------------------------------------------------
async function staleWhileRevalidate(request) {
  const cache = await caches.open(API_CACHE);
  const cachedResponse = await cache.match(request);

  // Start network fetch in background regardless
  const networkPromise = fetch(request)
    .then((networkResponse) => {
      if (networkResponse.ok) {
        // Clone and store with timestamp header
        const responseToCache = networkResponse.clone();
        const headers = new Headers(responseToCache.headers);
        headers.set("sw-cached-at", Date.now().toString());
        const timedResponse = new Response(responseToCache.body, {
          status: responseToCache.status,
          statusText: responseToCache.statusText,
          headers,
        });
        cache.put(request, timedResponse);
      }
      return networkResponse;
    })
    .catch(() => null);

  // If we have a cached response, return it immediately
  if (cachedResponse) {
    // Check if cache is fresh enough
    const cachedAt = parseInt(
      cachedResponse.headers.get("sw-cached-at") || "0",
      10
    );
    const age = Date.now() - cachedAt;

    if (age < API_CACHE_MAX_AGE_MS) {
      // Cache is fresh — return cached, still revalidate in background
      return cachedResponse;
    }

    // Cache is stale — try network first, fall back to stale cache
    const networkResponse = await networkPromise;
    return networkResponse || cachedResponse;
  }

  // No cache — must wait for network
  const networkResponse = await networkPromise;
  if (networkResponse) return networkResponse;

  // Both cache and network failed
  return new Response(
    JSON.stringify({ error: "offline", message: "No cached data available" }),
    {
      status: 503,
      headers: { "Content-Type": "application/json" },
    }
  );
}

// -----------------------------------------------------------------------
// Strategy: cache-first (for static assets)
// -----------------------------------------------------------------------
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch {
    return new Response("", { status: 503 });
  }
}

// -----------------------------------------------------------------------
// Strategy: network-first with offline fallback (for navigation)
// -----------------------------------------------------------------------
async function networkFirstWithOfflineFallback(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch {
    // Try cached page
    const cached = await caches.match(request);
    if (cached) return cached;

    // Fall back to offline page
    const offlinePage = await caches.match(OFFLINE_URL);
    if (offlinePage) return offlinePage;

    return new Response("Offline", {
      status: 503,
      headers: { "Content-Type": "text/plain" },
    });
  }
}

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------
function isCacheableApiRequest(url) {
  // Check if any of the cacheable API paths match
  return CACHEABLE_API_PATHS.some(
    (path) => url.pathname === path || url.pathname.startsWith(path)
  );
}

function isStaticAsset(url) {
  const ext = url.pathname.split(".").pop();
  const staticExtensions = [
    "js",
    "css",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "svg",
    "ico",
    "woff",
    "woff2",
    "ttf",
    "eot",
    "webp",
    "avif",
  ];
  return staticExtensions.includes(ext);
}

// -----------------------------------------------------------------------
// Background Sync: retry offline transactions when back online
// -----------------------------------------------------------------------
self.addEventListener("sync", (event) => {
  if (event.tag === "qbc-offline-tx-sync") {
    event.waitUntil(syncOfflineTransactions());
  }
});

async function syncOfflineTransactions() {
  // Notify all clients to broadcast pending transactions
  const clients = await self.clients.matchAll({ type: "window" });
  for (const client of clients) {
    client.postMessage({ type: "SYNC_OFFLINE_TX" });
  }
}

// -----------------------------------------------------------------------
// Push Notification handler
// -----------------------------------------------------------------------
self.addEventListener("push", (event) => {
  if (!event.data) return;

  try {
    const payload = event.data.json();
    const title = payload.title || "Qubitcoin";
    const options = {
      body: payload.body || "",
      icon: "/icons/icon-192x192.png",
      badge: "/icons/icon-192x192.png",
      tag: payload.type || "qbc-notification",
      data: payload.data || {},
      vibrate: [100, 50, 100],
    };
    event.waitUntil(self.registration.showNotification(title, options));
  } catch {
    // Non-JSON push — ignore
  }
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clients) => {
      if (clients.length > 0) {
        clients[0].focus();
      } else {
        self.clients.openWindow("/");
      }
    })
  );
});

// -----------------------------------------------------------------------
// Message handler: allows the app to communicate with the SW
// -----------------------------------------------------------------------
self.addEventListener("message", (event) => {
  if (event.data === "skipWaiting") {
    self.skipWaiting();
  }

  if (event.data === "clearApiCache") {
    caches.delete(API_CACHE);
  }
});
