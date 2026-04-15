// PivoxQuant Service Worker v1
const CACHE_VERSION = "sp-v1";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE = `${CACHE_VERSION}-api`;
const OFFLINE_URL = "/offline.html";

// Static assets to precache on install
const PRECACHE_ASSETS = [OFFLINE_URL];

// ── Cache strategy config ──────────────────────────────────────
const NETWORK_ONLY_PATTERNS = [
  /\/api\/auth\//,
  /\/api\/ai\//,
  /\/api\/daytrade\//,
  /\/api\/realtime\//,
  /\/api\/autotrade\//,
];

const CACHE_FIRST_PATTERNS = [/\/api\/morning-brief/];

const STALE_WHILE_REVALIDATE_CONFIG = {
  "/api/portfolio": 5 * 60 * 1000,
  "/api/portfolio/analytics": 5 * 60 * 1000,
  "/api/portfolio/history": 10 * 60 * 1000,
  "/api/market/overview": 2 * 60 * 1000,
  "/api/sectors": 2 * 60 * 1000,
  "/api/macro": 2 * 60 * 1000,
  "/api/watchlist": 10 * 60 * 1000,
  "/api/discover": 30 * 60 * 1000,
  "/api/profile": 60 * 60 * 1000,
  "/api/earnings": 15 * 60 * 1000,
  "/api/alerts": 3 * 60 * 1000,
  "/api/trades": 3 * 60 * 1000,
};

const NETWORK_FIRST_CONFIG = {
  "/api/signals": 5 * 60 * 1000,
  "/api/scan": 5 * 60 * 1000,
  "/api/news": 15 * 60 * 1000,
};

// ── Install ────────────────────────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_ASSETS))
      .then(() => self.skipWaiting()),
  );
});

// ── Activate ───────────────────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== STATIC_CACHE && k !== API_CACHE)
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

// ── Fetch ──────────────────────────────────────────────────────
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle same-origin
  if (url.origin !== self.location.origin) return;

  // Skip non-GET
  if (request.method !== "GET") return;

  // Network-only patterns (auth, AI, realtime, trading)
  if (NETWORK_ONLY_PATTERNS.some((p) => p.test(url.pathname))) return;

  // API routes
  if (url.pathname.startsWith("/api/")) {
    // Cache-first (morning brief)
    if (CACHE_FIRST_PATTERNS.some((p) => p.test(url.pathname))) {
      event.respondWith(cacheFirst(request, API_CACHE, 60 * 60 * 1000));
      return;
    }

    // Stale-while-revalidate
    const swrKey = Object.keys(STALE_WHILE_REVALIDATE_CONFIG).find((k) =>
      url.pathname.startsWith(k),
    );
    if (swrKey) {
      event.respondWith(
        staleWhileRevalidate(
          request,
          API_CACHE,
          STALE_WHILE_REVALIDATE_CONFIG[swrKey],
        ),
      );
      return;
    }

    // Network-first with cache fallback
    const nfKey = Object.keys(NETWORK_FIRST_CONFIG).find((k) =>
      url.pathname.startsWith(k),
    );
    if (nfKey) {
      event.respondWith(
        networkFirst(request, API_CACHE, NETWORK_FIRST_CONFIG[nfKey]),
      );
      return;
    }

    // Default: network-only for unknown API routes
    return;
  }

  // Static assets (JS, CSS, images, fonts) — cache-first
  if (isStaticAsset(url.pathname)) {
    event.respondWith(cacheFirst(request, STATIC_CACHE, 30 * 24 * 60 * 60 * 1000));
    return;
  }

  // HTML navigation — network-first with offline fallback
  if (request.mode === "navigate") {
    event.respondWith(navigationHandler(request));
    return;
  }
});

// ── Strategies ─────────────────────────────────────────────────

async function cacheFirst(request, cacheName, maxAge) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  if (cached) {
    const cachedTime = cached.headers.get("sw-cached-at");
    if (cachedTime && Date.now() - parseInt(cachedTime) < maxAge) {
      return cached;
    }
  }

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cloned = response.clone();
      const headers = new Headers(cloned.headers);
      headers.set("sw-cached-at", Date.now().toString());
      const body = await cloned.blob();
      await cache.put(
        request,
        new Response(body, { status: cloned.status, headers }),
      );
    }
    return response;
  } catch {
    return cached || new Response("Offline", { status: 503 });
  }
}

async function staleWhileRevalidate(request, cacheName, maxAge) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  const fetchPromise = fetch(request)
    .then((response) => {
      if (response.ok) {
        const cloned = response.clone();
        const headers = new Headers(cloned.headers);
        headers.set("sw-cached-at", Date.now().toString());
        cloned.blob().then((body) => {
          cache.put(
            request,
            new Response(body, { status: cloned.status, headers }),
          );
        });
      }
      return response;
    })
    .catch(() => cached);

  if (cached) {
    const cachedTime = cached.headers.get("sw-cached-at");
    if (cachedTime && Date.now() - parseInt(cachedTime) < maxAge) {
      return cached;
    }
  }

  return fetchPromise;
}

async function networkFirst(request, cacheName, maxAge) {
  const cache = await caches.open(cacheName);

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cloned = response.clone();
      const headers = new Headers(cloned.headers);
      headers.set("sw-cached-at", Date.now().toString());
      const body = await cloned.blob();
      await cache.put(
        request,
        new Response(body, { status: cloned.status, headers }),
      );
    }
    return response;
  } catch {
    const cached = await cache.match(request);
    return cached || new Response(JSON.stringify({ error: "offline" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

async function navigationHandler(request) {
  try {
    const response = await fetch(request);
    const cache = await caches.open(STATIC_CACHE);
    cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await caches.match(request);
    return cached || caches.match(OFFLINE_URL);
  }
}

function isStaticAsset(pathname) {
  return /\.(js|css|png|jpg|jpeg|svg|gif|ico|woff|woff2|ttf|eot)$/.test(
    pathname,
  );
}

// ── Push Notifications ─────────────────────────────────────────
self.addEventListener("push", (event) => {
  if (!event.data) return;

  const data = event.data.json();
  const options = {
    body: data.body || "",
    icon: "/icons/icon-192x192.png",
    badge: "/icons/icon-96x96.png",
    vibrate: [100, 50, 100],
    data: { url: data.url || "/" },
    actions: data.actions || [],
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/";

  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clients) => {
      const existing = clients.find(
        (c) => new URL(c.url).pathname === url && "focus" in c,
      );
      if (existing) return existing.focus();
      return self.clients.openWindow(url);
    }),
  );
});
