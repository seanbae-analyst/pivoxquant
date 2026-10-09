// PivoxQuant Service Worker (CACHE_VERSION auto-injected at build time)
//
// CACHE_VERSION is rewritten by `scripts/inject-sw-version.mjs` (wired into
// the `prebuild` npm script) to `pq-build-<git-sha>` on every Vercel /
// GitHub / local build. The activate step keeps STATIC_CACHE for the
// *current* version and deletes every other cache, so any prior
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
const OFFLINE_URL = "/offline.html";

// Static assets to precache on install
const PRECACHE_ASSETS = [OFFLINE_URL];

// App shells of the phone tab destinations (2026-10-09). Measured before:
// tapping 기록 offline replaced the whole app with offline.html — a client
// navigation whose RSC fetch fails falls back to a full page load, and only
// offline.html was cached. These pages render their content client-side from
// /api (which this worker never caches — see the fetch handler), so the
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

// ── API: never cached (2026-10-09) ─────────────────────────────
// Every /api/* request goes straight to the network. This worker used to
// keep per-user JSON (/api/portfolio*, /api/alerts, /api/trades, /api/profile…)
// in a Cache Storage bucket keyed by URL only — readable by whoever next used
// the device until a logout cleared it, and a second, unscoped copy of data
// the app now keeps itself: lib/persisted-swr-cache.ts stores the last-seen
// screens per user id (allowlisted keys, size/age caps) and clears them on
// logout, deletion request and user change. One place, scoped, clearable.
// The activate step below also deletes any API cache an older build left.

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
            .filter((k) => k !== STATIC_CACHE)
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

// ── Message ────────────────────────────────────────────────────
// The logout flow (lib/auth.tsx) still posts CLEAR_API_CACHE. Nothing is
// cached under /api any more, but a device that installed an older build may
// hold its "*-api" bucket until this worker activates — drop any such bucket.
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "CLEAR_API_CACHE") {
    event.waitUntil(
      caches
        .keys()
        .then((keys) => Promise.all(keys.filter((k) => k.endsWith("-api")).map((k) => caches.delete(k)))),
    );
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

  // API: always network, never cached (see "API: never cached" above).
  if (url.pathname.startsWith("/api/")) return;

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
