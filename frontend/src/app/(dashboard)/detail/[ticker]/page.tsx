"use client";

/**
 * /detail/[ticker] — Stock detail.
 *
 * Redesigned 2026-05-20 to the "Terminal Above, Editorial Below" 3-zone
 * standard (CEO-approved). The former 1792-line monolith is now pure data
 * orchestration + assembly; all presentation lives in components/detail/*.
 *
 *   Zone1 TERMINAL  — price-first hero cover + tall connected chart.
 *   Zone2 ANALYTICS — 4-pillar bars + dense fundamentals StatRow grid.
 *   Zone3 DOSSIER   — news / insider / SWOT / earnings / companion / artefacts.
 *
 * P0 RESILIENCE (CEO directive): every data source has its OWN loading /
 * error boundary. The signals fetch additionally has a hard 8s timeout and an
 * explicit "다시 시도" retry — a slow /api/signals can no longer blank the
 * price, score, fundamentals AND pillars at once. One section failing renders
 * the rest from their own data (progressive disclosure).
 *
 * Signals: POSITIVE / NEGATIVE / NEUTRAL only — BUY/SELL banned by law.
 */

import { useCallback, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { apiFetch, ApiError } from "@/lib/api";
import { WATCHLIST, WATCHLIST_ITEM } from "@/lib/endpoints";
import { toast } from "sonner";
import { normalizeTicker } from "@/lib/format";
import { liveRefresh } from "@/lib/market-hours";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { FootSignature } from "@/components/ui/editorial";
import { type ChartMarker } from "@/components/charts/interactive-line-chart";
import {
  useWatchlist,
  usePortfolioPositions,
  useArtifacts,
  useSignals,
} from "@/lib/hooks";
import type { Position } from "@/lib/types";

import {
  fetcher,
  isKrw,
  PERIOD_MAP,
  type Period,
  type SignalDetail,
  type ChartResponse,
  type NewsResponse,
  type ProfileData,
  type InsiderResponse,
  type InsiderFiling,
  type EarningsResponse,
  type EarningsItem,
  type SwotResponse,
} from "@/components/detail/types";
import {
  BackNav,
  AccessDeniedScreen,
  NoTickerScreen,
  NoDataScreen,
} from "@/components/detail/screens";
import { DetailHero } from "@/components/detail/DetailHero";
import { DetailChartPanel } from "@/components/detail/DetailChartPanel";
import { PillarGrid } from "@/components/detail/PillarGrid";
import { FundamentalsPanel } from "@/components/detail/FundamentalsPanel";
import { NewsFeed } from "@/components/detail/NewsFeed";
import { InsiderPanel } from "@/components/detail/InsiderPanel";
import { SwotPanel } from "@/components/detail/SwotPanel";
import { EarningsPanel } from "@/components/detail/EarningsPanel";
import { CompanionCta } from "@/components/detail/CompanionCta";
import { RelatedArtefacts } from "@/components/detail/RelatedArtefacts";

/* P0 resilience: an 8s hard-timeout fetcher for the signals source. SWR's
 * errorRetry doesn't bound a single slow request, so a hung /api/signals
 * would keep the hero in skeleton forever. AbortController gives a definite
 * "timed out" → error so the hero can surface a retry instead. */
const signalFetcher = async (url: string) => {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 8_000);
  try {
    const r = await fetch(url, { credentials: "include", signal: ctrl.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  } finally {
    clearTimeout(t);
  }
};

export default function StockDetailPage() {
  const params = useParams<{ ticker: string }>();
  const raw = (params.ticker ?? "").toUpperCase();
  const ticker = /^\d{6}$/.test(raw) ? `${raw}.KS` : raw;
  // KR ticker UI strip (feedback_ticker_display): API uses raw ticker; only
  // user-facing surfaces drop the .KS/.KQ suffix. "005930.KS" → "005930".
  const displayTicker = normalizeTicker(ticker);
  const [period, setPeriod] = useState<Period>("3M");

  /* ── Zone1: signals (price / score / pillars / snapshot) ──
   * INDEPENDENT boundary with 8s timeout + retry. */
  const {
    data: signal,
    isLoading: loadingSignal,
    error: signalErr,
    isValidating: signalValidating,
    mutate: retrySignal,
  } = useSWR<SignalDetail>(ticker ? API.signals.one(ticker) : null, signalFetcher, {
    refreshInterval: () => liveRefresh(5_000, 30_000),
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 5_000,
    errorRetryCount: 2,
    errorRetryInterval: 5_000,
  });
  const signalErrorState = !!signalErr && !signal;

  /* ── Zone1: chart (independent) ── */
  const {
    data: chartRes,
    isLoading: loadingChart,
    error: chartErr,
    isValidating: chartValidating,
    mutate: retryChart,
  } = useSWR<ChartResponse>(
    ticker ? `${API.market.chart(ticker)}?period=${PERIOD_MAP[period]}` : null,
    fetcher,
    {
      refreshInterval: () => liveRefresh(15_000, 120_000),
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 5_000,
      shouldRetryOnError: false,
    },
  );
  const chartErrorState = !!chartErr && !chartRes;

  /* Signal observation markers for the chart — reuses /api/signals scoped to
   * this symbol (no new endpoint / SWR-key change). */
  const { data: signalsRes } = useSignals(
    ticker ? { symbol: ticker, window: "all" } : {},
  );
  const chartMarkers = useMemo<ChartMarker[]>(() => {
    const all = signalsRes?.signals ?? [];
    const norm = normalizeTicker(ticker);
    return all
      .filter((s) => {
        if (!s.observed_at) return false;
        return (
          normalizeTicker(s.ticker) === norm ||
          (s.ticker ?? "").toUpperCase() === (ticker ?? "").toUpperCase()
        );
      })
      .map((s) => {
        const label = (s.label ?? s.signal ?? "").toString().toUpperCase();
        const tone: ChartMarker["tone"] =
          label === "POSITIVE"
            ? "positive"
            : label === "NEGATIVE"
              ? "negative"
              : "neutral";
        const display =
          tone === "positive" ? "긍정" : tone === "negative" ? "부정" : "중립";
        const strength =
          typeof s.strength === "number"
            ? s.strength
            : typeof s.score === "number"
              ? s.score / 100
              : null;
        const clock = s.observed_at
          ? new Date(s.observed_at).toLocaleString("ko-KR", {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })
          : "";
        const parts = [
          `관측 · ${display}`,
          strength != null ? `강도 ${strength.toFixed(2)}` : null,
          clock || null,
        ].filter(Boolean);
        return {
          date: s.observed_at as string,
          tone,
          strength: strength ?? undefined,
          label: parts.join(" · "),
        };
      });
  }, [signalsRes, ticker]);

  /* ── Zone3: news (independent) ── */
  const {
    data: newsRes,
    isLoading: loadingNews,
    error: newsErr,
    isValidating: newsValidating,
    mutate: retryNews,
  } = useSWR<NewsResponse>(ticker ? API.market.news(ticker) : null, fetcher, {
    refreshInterval: 120_000,
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 30_000,
    errorRetryCount: 2,
    errorRetryInterval: 10_000,
  });
  const newsErrorState = !!newsErr && !newsRes;

  /* ── profile (independent) — supplies company summary + sector fallback ── */
  const { data: profile, isLoading: loadingProfile } = useSWR<ProfileData>(
    ticker ? API.market.profile(ticker) : null,
    fetcher,
    {
      refreshInterval: 300_000,
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 60_000,
      errorRetryCount: 2,
      errorRetryInterval: 10_000,
    },
  );

  /* ── Zone3: insider (US only, independent) ── */
  const insiderEligible = !!ticker && !/^\d{6}\.(KS|KQ)$/i.test(ticker);
  const { data: insiderRes } = useSWR<InsiderResponse>(
    insiderEligible ? `/api/alt-data/us/insider-trades/${ticker}?days=90` : null,
    fetcher,
    {
      refreshInterval: 600_000,
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 60_000,
      shouldRetryOnError: false,
    },
  );
  const insiderData: InsiderFiling[] = Array.isArray(insiderRes?.data)
    ? (insiderRes!.data as InsiderFiling[])
    : [];

  /* ── Zone3: earnings (independent) ── */
  const { data: earningsRes } = useSWR<EarningsResponse>(
    ticker ? API.market.earnings : null,
    fetcher,
    {
      refreshInterval: 600_000,
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 60_000,
      shouldRetryOnError: false,
    },
  );
  const earningsForTicker: EarningsItem[] = useMemo(() => {
    const list = earningsRes?.earnings ?? earningsRes?.data ?? [];
    if (!ticker) return [];
    const upper = ticker.toUpperCase();
    return list
      .filter((e) => (e.ticker || e.symbol || "").toUpperCase() === upper)
      .slice(0, 4);
  }, [earningsRes, ticker]);

  /* ── Zone3: AI SWOT — on-demand POST ── */
  const [swot, setSwot] = useState<SwotResponse | null>(null);
  const [swotLoading, setSwotLoading] = useState(false);
  const [swotError, setSwotError] = useState<string | null>(null);
  const handleGenerateSwot = useCallback(async () => {
    if (!ticker) return;
    setSwotLoading(true);
    setSwotError(null);
    try {
      const res = await apiFetch<SwotResponse>(API.ai.swot, {
        method: "POST",
        body: JSON.stringify({ ticker }),
      });
      setSwot(res);
    } catch (e) {
      // 503 (LLM quota / restart) and 429 (rate limit) get graceful copy
      // rather than an alarming "Failed to generate SWOT" on the launch surface.
      let msg: string;
      if (e instanceof ApiError && e.status === 503) {
        msg = "AI service is temporarily busy — please try again in a moment.";
      } else if (e instanceof ApiError && e.status === 429) {
        msg = "Too many requests right now. Please wait a moment and retry.";
      } else if (e instanceof Error) {
        msg = e.message;
      } else {
        msg = "Request failed";
      }
      setSwotError(msg);
    } finally {
      setSwotLoading(false);
    }
  }, [ticker]);

  /* ── Watchlist / portfolio (§101 allowlist) ── */
  const {
    data: watchlistData,
    mutate: refreshWatchlist,
    isLoading: watchlistLoading,
  } = useWatchlist();
  const watchlistEntry = watchlistData?.watchlist?.find((w) => w.ticker === ticker);
  const inWatchlist = Boolean(watchlistEntry);

  const positionsSwr = usePortfolioPositions<{ positions?: Position[] }>();
  const artifactsSwr = useArtifacts({ limit: 3 });
  const allowlistLoading = watchlistLoading || positionsSwr.isLoading;
  const inPortfolio = useMemo(() => {
    const upper = (ticker || "").toUpperCase();
    return (positionsSwr.data?.positions ?? []).some((p) => {
      const t = p as { ticker?: string; symbol?: string };
      return (t.ticker || t.symbol || "").toUpperCase() === upper;
    });
  }, [positionsSwr.data, ticker]);
  const isAllowed = inWatchlist || inPortfolio;

  const krw = isKrw(signal, ticker);

  const handleWatchlistToggle = useCallback(async () => {
    try {
      if (inWatchlist && watchlistEntry) {
        await apiFetch(WATCHLIST_ITEM(watchlistEntry.id), { method: "DELETE" });
        toast.success("Removed from watchlist");
      } else {
        await apiFetch(WATCHLIST, {
          method: "POST",
          body: JSON.stringify({ ticker }),
        });
        toast.success("Added to watchlist");
      }
      refreshWatchlist();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed";
      toast.error(msg);
    }
  }, [inWatchlist, watchlistEntry, ticker, refreshWatchlist]);

  const hasPillars = useMemo(
    () =>
      signal?.tech_score != null ||
      signal?.fund_score != null ||
      signal?.news_score != null ||
      signal?.quant_score != null,
    [signal],
  );

  /* ── No ticker / not-found ── */
  if (!ticker) {
    return (
      <ErrorBoundary>
        <NoTickerScreen />
      </ErrorBoundary>
    );
  }

  /* §101 화이트리스트 가드 — allowlist 로딩 후에 검증. */
  if (!allowlistLoading && !isAllowed) {
    return (
      <ErrorBoundary>
        <div className="space-y-6">
          <BackNav />
          <AccessDeniedScreen
            ticker={ticker}
            onAddedToWatchlist={() => refreshWatchlist()}
          />
        </div>
      </ErrorBoundary>
    );
  }

  /* Hard no-data: both signal AND profile resolved empty. (signalErrorState
   * alone does NOT block — the hero shows a retry and other zones render.) */
  if (!loadingSignal && !loadingProfile && !signal && !profile && !signalErr) {
    return (
      <ErrorBoundary>
        <NoDataScreen displayTicker={displayTicker} />
      </ErrorBoundary>
    );
  }

  /* ── Sector / name resolution ── */
  const sectorRaw = (signal?.sector || profile?.sector || "").trim();
  const sectorLine =
    sectorRaw && sectorRaw.toUpperCase() !== "UNKNOWN"
      ? sectorRaw
      : profile?.sector && profile.sector.toUpperCase() !== "UNKNOWN"
        ? profile.sector
        : "—";
  const displayName = signal?.name || profile?.name || displayTicker;
  const mcap = signal?.snapshot?.market_cap ?? profile?.market_cap ?? null;
  const industry = signal?.snapshot?.industry ?? profile?.industry ?? null;

  return (
    <ErrorBoundary>
      <div>
        {/* Back nav */}
        <BackNav />

        {/* ════ Zone1 TERMINAL — tight rhythm (space-y-6) ════ */}
        <div className="mt-4 space-y-6">
          <DetailHero
            displayTicker={displayTicker}
            displayName={displayName}
            summary={profile?.summary}
            sectorLine={sectorLine}
            industry={industry}
            krw={krw}
            mcap={mcap}
            signal={signal}
            loadingSignal={loadingSignal}
            signalError={signalErrorState}
            onRetrySignal={() => retrySignal()}
            signalRetrying={signalValidating}
            inWatchlist={inWatchlist}
            onWatchlistToggle={handleWatchlistToggle}
          />

          <DetailChartPanel
            period={period}
            onPeriodChange={setPeriod}
            data={chartRes?.data ?? []}
            currency={krw ? "KRW" : (signal?.currency ?? "USD")}
            markers={chartMarkers}
            loading={loadingChart}
            error={chartErrorState}
            onRetry={() => retryChart()}
            retrying={chartValidating}
          />
        </div>

        {/* ════ Zone2 ANALYTICS — big breath above (mt-16), tight inside ════ */}
        <div className="mt-16 space-y-10">
          <PillarGrid signal={signal} hasPillars={hasPillars} />
          <FundamentalsPanel signal={signal} mcap={mcap} krw={krw} />
        </div>

        {/* ════ Zone3 DOSSIER — editorial (mt-16 + space-y-12) ════ */}
        <div className="mt-16 space-y-12">
          <NewsFeed
            news={newsRes?.news}
            loading={loadingNews}
            error={newsErrorState}
            onRetry={() => retryNews()}
            retrying={newsValidating}
          />

          {insiderEligible && <InsiderPanel data={insiderData} />}

          <SwotPanel
            ticker={ticker}
            swot={swot}
            loading={swotLoading}
            error={swotError}
            onGenerate={handleGenerateSwot}
          />

          <EarningsPanel ticker={ticker} items={earningsForTicker} />

          <CompanionCta ticker={ticker} />

          <RelatedArtefacts artifacts={artifactsSwr.artifacts} />

          <FootSignature />
        </div>
      </div>
    </ErrorBoundary>
  );
}
