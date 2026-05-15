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
import { toast } from "sonner";
import { API } from "@/lib/endpoints";
import { apiFetch, ApiError } from "@/lib/api";
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
  window: "today" | "7d" | "30d" | "all";
}

// W6-1 (Wave 6 follow-up, 2026-05-09): default window changed from
// "today" → "all". Backend `routes/signals.py:46` writes
// `observed_at = SignalCache.updated_at` (cache-write timestamp). Any
// ticker not refreshed in the past 24h was filtered out client-side
// even though the backend returned real data, producing a deceptive
// empty state. The new "all" window keeps every entry visible; users
// who want a freshness-scoped view can still pick today/7d/30d. Stale
// entries are now clearly badged via `is_stale` in `signal-card.tsx`
// (W6-3 ships in same PR family) so the user signal-vs-noise call is
// surfaced rather than silently filtered.
const DEFAULT_FILTERS: FilterState = {
  labels: new Set<SignalLabel>(),
  strengthMin: 0,
  strengthMax: 1,
  symbol: null,
  window: "all",
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
  if (window === "all") return true; // W6-1: no time filter
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

  // CEO directive [feedback_ticker_display] (4+ times): the symbol
  // autocomplete dropdown must show human names ("삼성전자"), not naked
  // tickers ("005930.KS"). We collect a {ticker, name} pair per symbol
  // by consulting positions → watchlist → resolver (signals payload has
  // no name). 2026-05-13 CEO 추가: KR 종목 우선 표시.
  const symbolHints = React.useMemo(() => {
    const map = new Map<string, { ticker: string; name: string }>();
    const add = (ticker: string | undefined, name?: string | null) => {
      if (!ticker) return;
      const key = ticker.toUpperCase();
      const existing = map.get(key);
      const resolvedName = name && name.trim() ? name.trim() : "";
      // Prefer the first non-empty name we encounter (positions > watchlist).
      if (!existing || (!existing.name && resolvedName)) {
        map.set(key, { ticker, name: resolvedName || existing?.name || "" });
      }
    };
    for (const p of positions) add(p?.ticker, p?.name);
    for (const w of watchlist) add(w?.ticker, w?.name);
    for (const s of allSignals) {
      if (!s?.ticker) continue;
      const fallback = resolveTickerName(s.ticker, positions, watchlist);
      add(s.ticker, fallback !== s.ticker ? fallback : "");
    }
    const isKrTicker = (t: string) => {
      const u = t.toUpperCase();
      return u.endsWith(".KS") || u.endsWith(".KQ") || u.endsWith(".KRX");
    };
    return Array.from(map.values()).sort((a, b) => {
      const aKr = isKrTicker(a.ticker);
      const bKr = isKrTicker(b.ticker);
      if (aKr !== bKr) return aKr ? -1 : 1;
      return (a.name || a.ticker).localeCompare(b.name || b.ticker, "ko");
    });
  }, [positions, watchlist, allSignals]);

  const handleRefresh = React.useCallback(async () => {
    setRefreshing(true);
    try {
      await apiFetch(API.signals.refresh, { method: "POST" });
    } catch (err) {
      // Bug NEW-A companion fix (2026-05-08): the previous silent catch
      // hid 408/500 from the user — they pressed Refresh, the spinner
      // stopped, and nothing visibly changed. apiFetch handles 401
      // (redirect) and 429 (its own toast); only surface the rest here.
      if (err instanceof ApiError) {
        if (err.status === 408) {
          toast.error("새로고침이 시간 초과되었습니다. 잠시 후 다시 시도해주세요.");
        } else if (err.status >= 500) {
          toast.error("새로고침 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.");
        } else if (err.status !== 401 && err.status !== 429) {
          toast.error(err.message || "새로고침 실패");
        }
      } else {
        toast.error(err instanceof Error ? err.message : "새로고침 실패");
      }
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

      {/* LIVING CFO STATUS — sticky.
       *
       * CEO bug 2026-05-13 "알림 거기 레이어에 겹쳐서 안보여 중간에":
       * the TopBar wrapper `[data-pq-dash-topbar]` is `position: sticky;
       * z-index: 20` (set in globals.css L3665). The NotificationDropdown
       * panel (z-100) lives inside it, so the panel's effective stacking
       * is bounded by that z=20 wrapper. This in-page status bar was at
       * z=40 with `top: 56` (right under the TopBar) — its sticky
       * position creates its OWN stacking context that sat ABOVE the
       * TopBar wrapper, **clipping the dropdown panel** from below.
       *
       * Fix: drop this bar to z-10 (below TopBar's z=20). The bar still
       * sticks correctly because `top: 56` keeps it pinned under the
       * TopBar, and it never needed to be above the TopBar — it sits
       * BENEATH it visually. Pattern mirrored in the other v2 pages
       * (see thorough-fix sweep below). */}
      <div
        className="sticky z-10 -mx-4 md:-ml-8 md:-mr-10 mb-2"
        style={{
          top: 56,
          // FINDING-022: solid ink — semi-transparent bar bled scrolled content.
          background: "var(--pq-ink)",
        }}
      >
        <LivingCFOStatusBar />
      </div>

      {/* HERO */}
      <SignalsHeroV2
        eyebrow="시그널 · 실시간"
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
