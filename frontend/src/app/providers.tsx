"use client";

import { SWRConfig } from "swr";
import { AuthProvider } from "@/lib/auth";
import { RealtimeProvider } from "@/lib/realtime";
import { LocaleProvider } from "@/lib/locale";
import { apiFetch } from "@/lib/api";
import { wakeBackendEarly } from "@/lib/early-wake";
import { persistedCacheMiddleware } from "@/lib/persisted-swr-cache";

// Start the sleeping Render backend booting as soon as this bundle evaluates —
// before hydration, before AuthProvider queues /api/auth/me. One deduped,
// cookie-less GET per page load; see lib/early-wake.ts for why it adds no
// instance hours.
if (typeof window !== "undefined") wakeBackendEarly();

/**
 * Global SWR provider.
 *
 * Raises the default `dedupingInterval` from SWR's 2 s baseline to 6 s so
 * that components subscribing to the same URL within ~6 s coalesce to a
 * single network request — even when two components build slightly
 * different query-string variants of the same endpoint (we still dedupe
 * exact-key matches). This fixes BUG-8 flapping where <ArtifactQueue />
 * and <LivingCFOStatusBar /> mounted back-to-back and issued two
 * /api/artifacts requests because one supplied `since=90d&limit=5` and
 * the other `since=all`.
 *
 * Per-hook `dedupingInterval` values still override this baseline when
 * specified (e.g. portfolio hooks use 10 s, artifacts use 30 s, discover
 * uses 600 s).
 *
 * Fetcher is centralised here so useSWR calls that don't pass a custom
 * fetcher inherit the same credential/CSRF/timeout behaviour as apiFetch.
 *
 * `use: [persistedCacheMiddleware]` (2026-10-09): last-known data for the
 * main screens survives an app restart (lib/persisted-swr-cache.ts). It is a
 * middleware on the DEFAULT cache, not a custom `provider`, on purpose: half
 * the app calls the global `mutate` imported from "swr" (portfolio refresh,
 * realtime SSE, pull-to-refresh, import inbox), and that function is bound to
 * the default cache — a provider would silently detach all of them.
 */
const SWR_MIDDLEWARE = [persistedCacheMiddleware];
const DEFAULT_FETCHER = <T,>(url: string) => apiFetch<T>(url);

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        fetcher: DEFAULT_FETCHER,
        dedupingInterval: 6_000,
        revalidateOnFocus: false,
        errorRetryCount: 2,
        use: SWR_MIDDLEWARE,
      }}
    >
      <LocaleProvider>
        <AuthProvider>
          <RealtimeProvider>{children}</RealtimeProvider>
        </AuthProvider>
      </LocaleProvider>
    </SWRConfig>
  );
}
