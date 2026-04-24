"use client";

import { SWRConfig } from "swr";
import { AuthProvider } from "@/lib/auth";
import { RealtimeProvider } from "@/lib/realtime";
import { LocaleProvider } from "@/lib/locale";
import { apiFetch } from "@/lib/api";

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
 */
const DEFAULT_FETCHER = <T,>(url: string) => apiFetch<T>(url);

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        fetcher: DEFAULT_FETCHER,
        dedupingInterval: 6_000,
        revalidateOnFocus: false,
        errorRetryCount: 2,
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
