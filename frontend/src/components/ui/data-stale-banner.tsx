"use client";

/**
 * <DataStaleBanner /> — Surface KIS / FMP stale-feed state to the user.
 *
 * Wave G C-CS3. Companion to <RealtimeStatusBanner />, but covers a
 * different failure mode: the SSE stream may be healthy while the
 * *upstream* market-data feed (KIS for KR, FMP for US) is degraded. The
 * nightly ticker_health cron probes a representative basket and writes a
 * JSONL artifact; ``routes/data_status.py`` summarises it. We poll that
 * summary every 5 min and render a top banner when the stale ratio
 * exceeds the operator threshold (currently 5 %).
 *
 * Why separate from RealtimeStatusBanner:
 *   - SSE banner = transport-layer (browser ↔ Railway).
 *   - Data-stale banner = upstream-vendor layer (Railway ↔ KIS / FMP).
 *   Both can be green while the other is red. Users need both.
 *
 * Dismiss model:
 *   - X button stores `pivox_stale_banner_dismissed_until` = now + 1 h
 *     in localStorage. While that timestamp is in the future the banner
 *     stays hidden even on subsequent SWR refreshes. The hour cap is a
 *     deliberate compromise: long enough that the user isn't nagged on
 *     every page change, short enough that a multi-hour outage will
 *     re-surface for their next session.
 *   - SSR-safe: localStorage reads are gated on `typeof window`.
 *
 * Graceful failure:
 *   - SWR error or backend 500 → render nothing. The banner exists to
 *     surface real stale data, not to spook users with monitoring noise.
 *   - is_stale=false → render nothing (happy path).
 *
 * Design v3 (project_design_v3):
 *   - rounded-sm (4px), Vantablack base, KR-tone amber accents.
 *   - Tokens only: --pq-ivory-* for text, raw rgba for the amber accent
 *     (kept consistent with the existing realtime "재연결 중" yellow so
 *     two warning banners can co-exist without colour-clashing).
 *   - No emojis, no purple/violet, no neon glow (THE LILA BAN).
 *
 * Law / neutrality:
 *   - "데이터 지연" only — no advice, no guarantee language, no BUY/SELL.
 */

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import useSWR from "swr";
import { DATA_STALE_STATUS } from "@/lib/endpoints";
import {
  isMarketDataDisplayEnabled,
  resolveMarketDataDisplay,
  routeUsesMarketData,
} from "@/lib/market-display";

const DISMISS_KEY = "pivox_stale_banner_dismissed_until";
const DISMISS_DURATION_MS = 60 * 60 * 1000; // 1 h
const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 min

export interface DataStaleStatus {
  is_stale: boolean;
  stale_ratio: number;
  affected_markets: Array<"KR" | "US">;
  updated_at: string | null;
  threshold_pct: number;
  /** 2026-09-19 vendor-display gate. `false` = the backend is not showing
   *  vendor prices at all, so a staleness warning about them is noise. */
  market_data_display?: boolean;
}

// `credentials: "omit"` mirrors the publicFetcher pattern in lib/hooks.ts —
// the stale-status route is public and must not pin a session cookie.
const staleFetcher = async (url: string): Promise<DataStaleStatus> => {
  const r = await fetch(url, { credentials: "omit" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

function readDismissedUntil(): number {
  if (typeof window === "undefined") return 0;
  try {
    const raw = window.localStorage.getItem(DISMISS_KEY);
    if (!raw) return 0;
    const n = Number(raw);
    return Number.isFinite(n) ? n : 0;
  } catch {
    return 0;
  }
}

function writeDismissedUntil(ts: number): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(DISMISS_KEY, String(ts));
  } catch {
    // localStorage unavailable (Safari private mode etc.) — accept that the
    // user will see the banner on next render. Better than throwing.
  }
}

function formatMarkets(markets: ReadonlyArray<"KR" | "US">): string {
  if (markets.length === 0) return "";
  const labels = markets.map((m) => (m === "KR" ? "한국" : "미국"));
  if (labels.length === 1) return labels[0]!;
  return labels.join(" · ");
}

export function DataStaleBanner() {
  // QA finding P3 (2026-09-19): this banner is mounted in the (dashboard)
  // layout, so "한국 시세 데이터가 지연되고 있어요" appeared on /pre-trade and
  // /settings — two screens that never read a price. A warning about prices
  // is only true on a screen that shows prices, so it is scoped to the
  // routes that do (lib/market-display.ts::MARKET_DATA_ROUTES), and it is
  // silent altogether while the vendor-display gate is off.
  const pathname = usePathname();
  // `dismissed` derives from the persisted expiry timestamp. A lazy useState
  // initializer keeps Date.now() OUT of the render body (react-hooks/purity),
  // and because SWR `data` is undefined on the server + first client paint the
  // banner renders null during hydration regardless of this value — so the
  // client-only localStorage read never causes an SSR/CSR mismatch. The effect
  // only arms a re-show timer; its setState lives inside the timeout callback,
  // never synchronously in the effect body (react-hooks set-state-in-effect).
  const [dismissed, setDismissed] = useState(() => readDismissedUntil() > Date.now());
  const reshowTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const remaining = readDismissedUntil() - Date.now();
    if (remaining > 0) {
      reshowTimer.current = setTimeout(() => setDismissed(false), remaining);
    }
    return () => {
      if (reshowTimer.current) clearTimeout(reshowTimer.current);
    };
  }, []);

  // A null key stops SWR fetching entirely: with the gate off, or on a screen
  // that shows no prices, the 5-minute poll would be a request whose answer
  // can never change what the user sees.
  const gateOpen =
    isMarketDataDisplayEnabled() && routeUsesMarketData(pathname);

  const { data, error } = useSWR<DataStaleStatus>(
    gateOpen ? DATA_STALE_STATUS : null,
    staleFetcher,
    {
      refreshInterval: REFRESH_INTERVAL_MS,
      revalidateOnFocus: false,
      // Suppress error retries — a 500 here is monitoring noise, not a
      // user-actionable bug.
      shouldRetryOnError: false,
    },
  );

  if (error || !data) return null;
  if (!resolveMarketDataDisplay(data.market_data_display)) return null;
  if (!routeUsesMarketData(pathname)) return null;
  if (!data.is_stale) return null;
  if (dismissed) return null;

  const handleDismiss = () => {
    writeDismissedUntil(Date.now() + DISMISS_DURATION_MS);
    setDismissed(true);
    if (reshowTimer.current) clearTimeout(reshowTimer.current);
    reshowTimer.current = setTimeout(
      () => setDismissed(false),
      DISMISS_DURATION_MS,
    );
  };

  const marketLabel = formatMarkets(data.affected_markets);
  const headline = marketLabel
    ? `${marketLabel} 시세 데이터가 지연되고 있어요`
    : "일부 시세 데이터가 지연되고 있어요";

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="data-stale-banner"
      className="mx-4 mt-3 rounded-sm border px-3 py-2 md:mx-10"
      style={{
        borderColor: "rgba(234, 179, 8, 0.35)",
        backgroundColor: "rgba(234, 179, 8, 0.06)",
      }}
    >
      <div className="flex items-start gap-2.5">
        <span
          className="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full"
          style={{ backgroundColor: "rgba(234, 179, 8, 0.85)" }}
          aria-hidden
        />
        <div className="flex-1 min-w-0">
          <p
            className="font-mono uppercase tracking-[0.22em]"
            style={{
              fontSize: "var(--pq-text-caption)",
              color: "rgba(234, 179, 8, 0.85)",
            }}
          >
            {headline}
          </p>
          <p
            className="mt-1 leading-relaxed"
            style={{
              fontSize: "var(--pq-text-caption)",
              color: "var(--pq-ivory-mid)",
            }}
          >
            표시된 가격이 최신이 아닐 수 있습니다. 잠시 후 다시 시도해 주세요.
          </p>
        </div>
        <button
          type="button"
          onClick={handleDismiss}
          aria-label="알림 닫기"
          data-testid="data-stale-banner-dismiss"
          className="shrink-0 rounded-sm border px-2 py-1 font-mono uppercase tracking-[0.18em] transition-colors hover:bg-white/5"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            borderColor: "rgba(234, 179, 8, 0.35)",
            color: "rgba(234, 179, 8, 0.85)",
          }}
        >
          닫기
        </button>
      </div>
    </div>
  );
}
