"use client";

/**
 * /signals v2 — "Signals stream" editorial layout.
 *
 * Source of truth: frontend/design-mockups/signals-v2/{SPEC.md, MIGRATION.md, mockup.html}.
 * Toggle: NEXT_PUBLIC_SIGNALS_V2=true. Default off; v1 remains live.
 *
 * Surface map (matches v1 inventory + signals-v2 SPEC §0):
 *   - TopTicker                 (reused, full-bleed)
 *   - LivingCFOStatusBar        (reused, sticky)
 *   - SignalsHeroV2             (new — editorial 48px Playfair hero)
 *   - SignalsFilterBar          (new — sticky, 4-col filter rail + Refresh)
 *   - TopMoversStrip            (new — top-5 by strength)
 *   - SignalsTimelineGrid       (new — chrono stream + day-rule + cards)
 *   - WeeklyPulseCard           (reused, invisible Mon trigger)
 *   - UpsellPlus                (reused, conditional)
 *   - FootSignature             (reused, page foot)
 *   - DisclaimerBanner          (mounted by (dashboard)/layout.tsx — NOT here)
 *
 * v1 inventory mapping (per task SPEC §8):
 *   - 3 ClipboardPaper (pos/neu/neg)        → label color in each card
 *   - SignalMemoStrip 4-pillar expand       → carded rationale (Phase 2: expand)
 *   - Filter pills 4개                      → SignalsFilterBar chips
 *   - Refresh 버튼                          → SignalsFilterBar Refresh button
 *   - isLoading / empty 상태                 → SignalsTimelineGrid skeleton/empty
 *   - 데스크톱 3D 스택 vs 모바일 flat        → polished off in v2; v1 fallback preserves it
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. No BUY/SELL/HOLD/recommend/advice.
 */

import * as React from "react";

import { ErrorBoundary } from "@/components/ui/error-boundary";
import { FootSignature } from "@/components/ui/editorial";

import { TopTicker } from "@/components/terminal/top-ticker";
import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";
import { WeeklyPulseCard } from "@/components/dashboard/weekly-pulse";
import { UpsellPlus } from "@/components/dashboard/upsell-plus";

import {
  useSignals,
  usePortfolioPositions,
  useWatchlist,
  resolveTickerName,
} from "@/lib/hooks";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import type {
  SignalEntry,
  SignalLabel,
  Position,
  PortfolioResponse,
} from "@/lib/types";

import { SignalsHeroV2 } from "@/components/signals/v2/signals-hero-v2";
import { SignalsFilterBar } from "@/components/signals/v2/signals-filter-bar";
import { TopMoversStrip } from "@/components/signals/v2/top-movers-strip";
import { SignalsTimelineGrid } from "@/components/signals/v2/signals-timeline-grid";

interface FilterState {
  labels: Set<SignalLabel>;
  strengthMin: number;
  strengthMax: number;
  symbol: string | null;
  window: "today" | "7d" | "30d";
}

const DEFAULT_FILTERS: FilterState = {
  labels: new Set<SignalLabel>(),
  strengthMin: 0,
  strengthMax: 1,
  symbol: null,
  window: "today",
};

function strengthOf(s: SignalEntry): number {
  if (typeof s.strength === "number") return Math.max(0, Math.min(1, s.strength));
  if (typeof s.score === "number") return Math.max(0, Math.min(1, s.score / 100));
  return 0;
}

function labelOf(s: SignalEntry): SignalLabel {
  const v = (s.label ?? s.signal ?? "").toString().toUpperCase();
  if (v === "POSITIVE") return "POSITIVE";
  if (v === "NEGATIVE") return "NEGATIVE";
  return "NEUTRAL";
}

function isWithinWindow(s: SignalEntry, window: FilterState["window"]): boolean {
  if (!s.observed_at) return true; // no timestamp — keep visible
  try {
    const ts = new Date(s.observed_at).getTime();
    if (isNaN(ts)) return true;
    const now = Date.now();
    if (window === "today") {
      const day = 24 * 60 * 60 * 1000;
      return now - ts <= day;
    }
    if (window === "7d") return now - ts <= 7 * 24 * 60 * 60 * 1000;
    if (window === "30d") return now - ts <= 30 * 24 * 60 * 60 * 1000;
  } catch {
    return true;
  }
  return true;
}

export default function SignalsPageV2() {
  const [filters, setFilters] = React.useState<FilterState>(DEFAULT_FILTERS);
  const [refreshing, setRefreshing] = React.useState(false);

  const swr = useSignals(filters);
  const positionsSwr = usePortfolioPositions<PortfolioResponse>();
  const watchlistSwr = useWatchlist();

  const positions: Position[] = React.useMemo(
    () => positionsSwr.data?.positions ?? [],
    [positionsSwr.data?.positions],
  );
  const watchlist = React.useMemo(
    () => watchlistSwr.data?.watchlist ?? [],
    [watchlistSwr.data?.watchlist],
  );

  const resolveName = React.useCallback(
    (ticker: string) => resolveTickerName(ticker, positions, watchlist),
    [positions, watchlist],
  );

  // Backend may not honor query params yet — apply client-side filter as
  // a defensive layer. If the backend already filtered, this is a no-op.
  const allSignals: SignalEntry[] = React.useMemo(
    () => swr.data?.signals ?? [],
    [swr.data?.signals],
  );
  const filtered = React.useMemo(() => {
    return allSignals.filter((s) => {
      const lbl = labelOf(s);
      if (filters.labels.size > 0 && !filters.labels.has(lbl)) return false;
      const str = strengthOf(s);
      if (str < filters.strengthMin || str > filters.strengthMax) return false;
      if (filters.symbol) {
        const want = filters.symbol.trim().toUpperCase();
        if (want && s.ticker.toUpperCase() !== want) return false;
      }
      if (!isWithinWindow(s, filters.window)) return false;
      return true;
    });
  }, [allSignals, filters]);

  const counts = React.useMemo(() => {
    let positive = 0;
    let negative = 0;
    let neutral = 0;
    const symbols = new Set<string>();
    for (const s of filtered) {
      const lbl = labelOf(s);
      if (lbl === "POSITIVE") positive++;
      else if (lbl === "NEGATIVE") negative++;
      else neutral++;
      symbols.add(s.ticker.toUpperCase());
    }
    return { positive, negative, neutral, symbols: symbols.size };
  }, [filtered]);

  const symbolHints = React.useMemo(() => {
    const set = new Set<string>();
    for (const p of positions) if (p?.ticker) set.add(p.ticker);
    for (const w of watchlist) if (w?.ticker) set.add(w.ticker);
    for (const s of allSignals) if (s?.ticker) set.add(s.ticker);
    return Array.from(set).sort();
  }, [positions, watchlist, allSignals]);

  const handleRefresh = React.useCallback(async () => {
    setRefreshing(true);
    try {
      await apiFetch(API.signals.refresh, { method: "POST" });
    } catch {
      // silent — SWR keeps stale view
    } finally {
      await swr.mutate();
      setRefreshing(false);
    }
  }, [swr]);

  return (
    <ErrorBoundary>
      {/* TOP TICKER — full bleed */}
      <div
        className="-mx-4 md:-ml-10 md:-mr-10 mb-4"
        style={{ maxWidth: "100vw" }}
      >
        <TopTicker />
      </div>

      {/* LIVING CFO STATUS — sticky */}
      <div
        className="sticky z-40 -mx-4 md:-ml-8 md:-mr-10 mb-2"
        style={{
          top: 56,
          background: "rgba(5,5,5,0.78)",
          backdropFilter: "blur(6px)",
          WebkitBackdropFilter: "blur(6px)",
        }}
      >
        <LivingCFOStatusBar />
      </div>

      {/* HERO */}
      <SignalsHeroV2
        eyebrow="Signals · live"
        counts={counts}
        loading={swr.isLoading && allSignals.length === 0}
      />

      {/* MAIN — filter, movers, timeline */}
      <main style={{ paddingTop: 32 }}>
        <SignalsFilterBar
          value={filters}
          onChange={setFilters}
          counts={{
            positive: counts.positive,
            negative: counts.negative,
            neutral: counts.neutral,
          }}
          symbolHints={symbolHints}
          onRefresh={handleRefresh}
          refreshing={refreshing}
        />

        <TopMoversStrip entries={filtered} resolveName={resolveName} />

        <SignalsTimelineGrid
          entries={filtered}
          isLoading={swr.isLoading}
          resolveName={resolveName}
        />
      </main>

      {/* Pulse + upsell (reused, conditional) */}
      <UpsellPlus />
      <WeeklyPulseCard />

      {/* Foot signature — DisclaimerBanner mounted by (dashboard)/layout.tsx */}
      <FootSignature />
    </ErrorBoundary>
  );
}
