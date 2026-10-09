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
const CACHE_VERSION = "pq-build-10664adb";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE = `${CACHE_VERSION}-api`;
const OFFLINE_URL = "/offline.html";

// Static assets to precache on install
const PRECACHE_ASSETS = [OFFLINE_URL];

// App shells of the phone tab destinations (2026-10-09). Measured before:
// tapping 기록 offline replaced the whole app with offline.html — a client
// navigation whose RSC fetch fails falls back to a full page load, and only
// offline.html was cached. These pages render their content client-side from
// /api (which is never cached here as a success — see networkFirst), so the
// HTML is the same shell for everyone: no user data, only the locale cookie's
// <html lang> and the per-response CSP nonce, which travels with the cached
// response's own CSP header. With the shell cached, the app stays on screen
// offline and says so inline (components/pwa/offline-banner.tsx), and a
// launch opens from the cached shell at once while the network refreshes it
// (stale-while-revalidate, navigationHandler). A deploy changes CACHE_VERSION
// and the activate step drops every older shell along with the old caches.
//
// Best-effort: a shell that fails, redirects (beta gate / login) or is not
// HTML is skipped and never blocks install. Each cached shell also pulls in
// the /_next/static chunks and stylesheets it references.
const APP_SHELL_ROUTES = ["/mirror", "/pre-trade", "/journal", "/portfolio", "/settings"];

// A navigation that takes longer than this falls back to the cached shell
// (when there is one) while the network response still refreshes the cache.
const NAVIGATION_TIMEOUT_MS = 4000;

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
      .then((cache) =>
        cache
          .addAll(PRECACHE_ASSETS)
          .then(() => Promise.allSettled(APP_SHELL_ROUTES.map((r) => precacheShell(cache, r)))),
      )
      .then(() => self.skipWaiting()),
  );
});

/** True for a same-origin, non-redirected HTML 200 — the only shell we keep. */
function isCacheableShell(response) {
  if (!response || !response.ok || response.redirected) return false;
  if (response.status !== 200) return false;
  const type = response.headers.get("content-type") || "";
  return type.includes("text/html");
}

/** Stamp `sw-cached-at` so cacheFirst can age the entry like its own. */
async function putStamped(cache, request, response) {
  const headers = new Headers(response.headers);
  headers.set("sw-cached-at", Date.now().toString());
  const body = await response.blob();
  await cache.put(request, new Response(body, { status: response.status, headers }));
}

/** `/_next/static/...` script and stylesheet URLs referenced by an HTML page. */
function staticChunkUrls(html) {
  const urls = new Set();
  const re = /(?:src|href)="(\/_next\/static\/[^"]+\.(?:js|css))"/g;
  let m;
  while ((m = re.exec(html)) !== null) urls.add(m[1]);
  return [...urls];
}

async function precacheShell(cache, route) {
  const response = await fetch(route, { credentials: "same-origin" });
  if (!isCacheableShell(response)) return;
  const html = await response.clone().text();
  await cache.put(route, response);
  await Promise.allSettled(
    staticChunkUrls(html).map(async (url) => {
      if (await cache.match(url)) return;
      const res = await fetch(url);
      if (res.ok) await putStamped(cache, url, res);
    }),
  );
}

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
    event.respondWith(navigationHandler(request, event));
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

async function navigationHandler(request, event) {
  const cache = await caches.open(STATIC_CACHE);
  const path = new URL(request.url).pathname;
  // Shells are keyed by path; a query string (?tab=…) does not change them.
  const cached = await cache.match(request, { ignoreSearch: true });

  const network = fetch(request).then((response) => {
    // Only cache a successful, non-redirected HTML navigation. A transient
    // 500/502 must not be replayed offline, and a redirect (beta gate, login)
    // must never be stored under the page's own URL.
    if (isCacheableShell(response)) {
      return cache.put(path, response.clone()).then(() => response);
    }
    return response;
  });
  // A failure after a cached answer was already served is expected.
  network.catch(() => {});

  // The phone tab destinations open from the cached shell at once
  // (stale-while-revalidate): a launch no longer waits for a server render.
  // The shell carries its own CSP header + nonce pair, so it stays
  // self-consistent; its data comes from /api, never from this cache. The
  // network answer refreshes the shell for the next launch.
  if (cached && APP_SHELL_ROUTES.includes(path)) {
    event.waitUntil(network.catch(() => {}));
    return cached;
  }

  if (!cached) {
    try {
      return await network;
    } catch {
      return caches.match(OFFLINE_URL);
    }
  }

  // Other cached pages: the network still wins when it answers in time; on a
  // stalled connection or offline the cached copy keeps the app on screen.
  const timeout = new Promise((resolve) =>
    setTimeout(() => resolve(null), NAVIGATION_TIMEOUT_MS),
  );
  try {
    const first = await Promise.race([network, timeout]);
    return first || cached;
  } catch {
    return cached;
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
