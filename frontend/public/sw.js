// PivoxQuant Service Worker (CACHE_VERSION auto-injected at build time)
//
// CACHE_VERSION is rewritten by `scripts/inject-sw-version.mjs` (wired into
// the `prebuild` npm script) to `pq-build-<git-sha>` on every Vercel /
// GitHub / local build. The activate step keeps STATIC_CACHE + API_CACHE
// for the *current* version and deletes every other cache, so any prior
// build's caches (legacy `sp-v*` or older `pq-build-*`) are purged the
// instant the new SW takes control. PWA-installed users always pick up
// the latest HTML/JS/CSS hashes on first navigation after deploy without
// requiring a manual version bump in this file.
//
// Historical context (do not delete — explains strategy decisions):
//   - v3 → v4: networkFirst/cacheFirst stopped synthesizing fake 503
//     "offline" responses when fetch rejects. A fabricated 503 with
//     `{"error":"offline"}` was reaching SWR as a *successful* HTTP
//     response, so SWR never entered its error state and the UI stayed
//     stuck on skeletons forever. We now serve cached response if we
//     have one, otherwise re-throw the network error so SWR error
//     handling (retry + error UI) actually runs.
//   - v4 → v5: home/portfolio/risk/signals/reports shipped v2 redesigns;
//     bumping invalidated stale navigation HTML cached on PWAs.
//   - v5 → v6: bug-fix wave (auth.tsx 8s timeout, reports routing,
//     companion premium gate, etc.) needed cache flush.
// Going forward, the build script does this work — no manual bump.
const CACHE_VERSION = "pq-build-9c67a1a4";
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
  // Wave-3 P2 (2026-06-10): the "/api/profile" SWR prefix also matched the
  // PIPA full personal-data export — a 60-minute disk cache of the most
  // sensitive payload in the product (and a cross-user window on account
  // switch without logout). Never cache it.
  /\/api\/profile\/export/,
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

// ── Message ────────────────────────────────────────────────────
// PIPA P1 (2026-05-22): on a shared device, the API_CACHE retains per-user
// SWR responses (/api/profile 60min, /api/earnings 15min, /api/discover 30min)
// keyed by URL only. After User A logs out and User B logs in within the
// window, B's first render would be served A's cached payload. The logout
// flow (lib/auth.tsx) posts CLEAR_API_CACHE so we drop+recreate the API cache
// on demand. STATIC_CACHE (HTML/JS/CSS/fonts) is untouched.
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "CLEAR_API_CACHE") {
    event.waitUntil(caches.delete(API_CACHE).then(() => caches.open(API_CACHE)));
  }
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
  } catch (err) {
    // Critical: do NOT synthesize a 503 response here. A fabricated Response
    // (even with status 503) is delivered to fetch()/SWR as a *resolved*
    // promise, which SWR interprets as "the request completed, here's your
    // data" — it never enters the error state, so retry/error UI never fire
    // and skeletons stay on screen forever. Serve a genuine cache hit when we
    // have one, otherwise let the real network error propagate so SWR can
    // reject, retry, and show an error state.
    //
    // 2026-05-17 wave C-3 P0: previously the maxAge argument from
    // NETWORK_FIRST_CONFIG was silently dropped — any cached entry,
    // even days old, would be served on offline fallback. For mutation-
    // sensitive endpoints (portfolio, watchlist, alerts, trades) this
    // is a data-freshness risk. Honor maxAge: if the cache entry is
    // older than the configured budget, propagate the network error
    // instead so SWR can show "offline / stale" UI rather than
    // pretending stale data is live. Entries without a `sw-cached-at`
    // stamp (legacy) are treated as fresh to avoid a one-time mass
    // expiry the moment this code ships.
    const cached = await cache.match(request);
    if (cached) {
      if (maxAge) {
        const cachedAt = cached.headers.get("sw-cached-at");
        if (cachedAt) {
          const age = Date.now() - parseInt(cachedAt, 10);
          if (Number.isFinite(age) && age >= maxAge) {
            throw err;
          }
        }
      }
      return cached;
    }
    throw err;
  }
}

async function navigationHandler(request) {
  try {
    const response = await fetch(request);
    // Only cache successful navigations. Previously we cached every
    // response regardless of status, which meant a transient 500/502
    // could be served from cache on the next offline reload — users
    // would see the broken page instead of offline.html. Status 0
    // (opaque) is also excluded since we cannot inspect it.
    if (response.ok && response.status >= 200 && response.status < 300) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
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

  // F3-07 (2026-05-17): wrap event.data.json() — a malformed payload
  // (non-JSON body, encoding mismatch) previously crashed the push
  // handler silently, dropping the notification with no diagnostics.
  let data;
  try {
    data = event.data.json();
  } catch (err) {
    console.error("[sw] push payload parse failed:", err);
    return;
  }

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
