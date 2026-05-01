// PivoxQuant Service Worker v6 (2026-05-02 — bug-fix wave + cold-start fix)
// v5 → v6: invalidate v5 caches now that the round of fixes shipped:
//   - frontend/src/lib/auth.tsx        (8s timeout on /api/auth/me)
//   - reports v2 latest-artifact-card  (Open full memo routing)
//   - /detail Related Observations     (real artefacts, no decoy PDFs)
//   - dd_checklist email body          (separate from PDF template)
//   - companion premium gate           (DEV_FOUNDING_EMAILS backdoor)
// PWA-installed users on v5 were locked to the pre-fix HTML/JS bundles
// even after Vercel redeployed; bumping CACHE_VERSION purges every
// `sp-v5-*` cache the moment the new SW activates so users get the
// new build artefacts on first navigation.
//
// v4 → v5: invalidate v4 caches now that home/portfolio/risk/signals/reports
// shipped their v2 redesigns. PWA-installed users were holding v4 caches with
// the old static asset hashes + the old cached navigation HTML, which would
// keep serving v1 markup until next route fetch. Bumping CACHE_VERSION makes
// the activate step delete every `sp-v4-*` cache the moment the new SW takes
// control, so users get a clean slate against the new build artefacts.
//
// v3 → v4: networkFirst/cacheFirst no longer synthesize fake 503 "offline"
// responses when fetch rejects. A fake 503 with Content-Type: application/json
// and body `{"error":"offline"}` was being delivered to SWR as a *successful*
// HTTP response, so SWR never entered its error state and the UI stayed stuck
// on skeletons forever (dashboard / portfolio / watchlist / risk / home).
// Now: serve cached response if we have one, otherwise re-throw the network
// error so SWR error handling (retry + error UI) actually runs. Bumping the
// version string evicts the v3 caches via the activate step so users never
// see a stale pre-fix cached 503 after upgrade.
const CACHE_VERSION = "sp-v6";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE = `${CACHE_VERSION}-api`;
const OFFLINE_URL = "/offline.html";

// Static assets to precache on install
const PRECACHE_ASSETS = [OFFLINE_URL];

// ── Cache strategy config ──────────────────────────────────────
// NETWORK_ONLY covers anything sensitive (auth), live (realtime/daytrade),
// LLM-generated (/api/ai), or inherently user-specific + mutating enough
// that a stale cache is worse than an offline error. Broker KIS endpoints
// land here because the payload includes encrypted account state.
const NETWORK_ONLY_PATTERNS = [
  /\/api\/auth\//,
  /\/api\/ai\//,
  /\/api\/daytrade\//,
  /\/api\/realtime\//,
  /\/api\/autotrade\//,
  /\/api\/broker\/kis\//,
];

const CACHE_FIRST_PATTERNS = [];

// Read-mostly endpoints (no user mutations): SWR safe.
// FRED macro data refreshes daily so a 2-hour SWR window is plenty, and
// we eat the cache hit on repeated macro-page visits.
const STALE_WHILE_REVALIDATE_CONFIG = {
  "/api/market/overview": 2 * 60 * 1000,
  "/api/sectors": 2 * 60 * 1000,
  "/api/macro": 2 * 60 * 1000,
  "/api/discover": 30 * 60 * 1000,
  "/api/profile": 60 * 60 * 1000,
  "/api/earnings": 15 * 60 * 1000,
  "/api/alt-data/macro": 2 * 60 * 60 * 1000,
};

// Write-affected / per-user endpoints: network-first with cache fallback
// so mutations reflect immediately AND users still see something offline.
const NETWORK_FIRST_CONFIG = {
  "/api/portfolio": 5 * 60 * 1000,
  "/api/portfolio/analytics": 5 * 60 * 1000,
  "/api/portfolio/history": 10 * 60 * 1000,
  "/api/watchlist": 10 * 60 * 1000,
  "/api/alerts": 3 * 60 * 1000,
  "/api/trades": 3 * 60 * 1000,
  "/api/signals": 5 * 60 * 1000,
  "/api/scan": 5 * 60 * 1000,
  "/api/news": 15 * 60 * 1000,
  "/api/artifacts": 5 * 60 * 1000,
  "/api/growth": 5 * 60 * 1000,
  "/api/alt-data/kr": 5 * 60 * 1000,
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
  } catch (err) {
    // Same fix as networkFirst: prefer cached, otherwise propagate the real
    // error so SWR (or the caller) can reject cleanly instead of treating a
    // fabricated 503 as a successful response.
    if (cached) return cached;
    throw err;
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
    .catch((err) => {
      // Same principle as networkFirst/cacheFirst: fall back to cached only
      // if we actually have one, otherwise let the real network error reach
      // the caller so SWR fires its error path instead of the page silently
      // hanging on skeletons.
      if (cached) return cached;
      throw err;
    });

  if (cached) {
    const cachedTime = cached.headers.get("sw-cached-at");
    if (cachedTime && Date.now() - parseInt(cachedTime) < maxAge) {
      return cached;
    }
  }

  return fetchPromise;
}

async function networkFirst(request, cacheName) {
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
  } catch (err) {
    // Critical: do NOT synthesize a 503 response here. A fabricated Response
    // (even with status 503) is delivered to fetch()/SWR as a *resolved*
    // promise, which SWR interprets as "the request completed, here's your
    // data" — it never enters the error state, so retry/error UI never fire
    // and skeletons stay on screen forever. Serve a genuine cache hit when we
    // have one, otherwise let the real network error propagate so SWR can
    // reject, retry, and show an error state.
    const cached = await cache.match(request);
    if (cached) return cached;
    throw err;
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
