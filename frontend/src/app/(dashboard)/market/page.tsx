"use client";

/**
 * /market — Morning Papers gazette.
 *
 * Cascades the /home Dossier concept into Market. The page is no longer
 * a grid of ink cards; it is a stack of three ivory "papers" on the
 * Vantablack desk:
 *
 *   Paper 1 — OverviewPaper          — front sheet: hero index +
 *                                      at-a-glance strip for the region
 *   Paper 2 — IndicesDetailPaper     — mid sheet (rotated): full level
 *                                      table with sparklines + 52W ranges;
 *                                      KR tab carries the derivatives block
 *   Paper 3 — CalendarNewsPaper      — back sheet (tilted further): FX,
 *                                      earnings calendar, market pulse
 *
 * All SWR hooks, real-time cadence (liveRefresh), and observational
 * language from the prior implementation are preserved verbatim. Only
 * the render layer has been redesigned.
 *
 * Region tabs (US / KR) and the header live/closed status strip remain.
 * DisclaimerBanner type="signal" preserved at the foot.
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL toning only. No BUY/SELL/HOLD
 * language anywhere on the page.
 */

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";

import { apiFetch } from "@/lib/api";
import { MARKET_INDICES, API } from "@/lib/endpoints";
import { sanitizeKrIndex } from "@/lib/format";
import { isMarketOpen, liveRefresh } from "@/lib/market-hours";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { FootSignature } from "@/components/ui/editorial";
import { cn } from "@/lib/utils";

import { DossierDesk } from "@/components/home/dossier-desk";
import { PaperDocument } from "@/components/home/paper-document";

import type { IndexQuote } from "@/components/market/index-card";
import { useNowTick } from "@/components/market/index-card";

import { OverviewPaper } from "@/components/market/overview-paper";
import { IndicesDetailPaper } from "@/components/market/indices-detail-paper";
import { CalendarNewsPaper } from "@/components/market/calendar-news-paper";

type MarketTab = "US" | "KR";

interface FxResponse {
  ok: boolean;
  usd_krw: number;
  last_updated: string | null;
  last_updated_ts: number;
  age_seconds: number;
  is_stale: boolean;
}

interface BackendIndex {
  ticker: string;
  name: string;
  level: number;
  change_1d_pct: number;
  range_52w: [number, number];
  sparkline_30d: number[];
  observed_at?: string;
  is_stale?: boolean;
  /**
   * Liquid ETF proxy used to source the level (US indices only).
   * Backend contract: routes/market.py::_etf_snapshot returns
   * `{"ticker": "^GSPC", "proxy_ticker": "SPY", "level": <SPY price>, …}`.
   * Absent on KR indices and FX pairs.
   */
  proxy_ticker?: string;
}

const fetcher = <T,>(url: string) => apiFetch<T>(url);

function toQuote(b: BackendIndex, region: MarketTab): IndexQuote {
  const [lo, hi] = b.range_52w ?? [0, 0];
  return {
    symbol: b.ticker,
    name: b.name,
    level: b.level,
    changePct: b.change_1d_pct,
    weekHigh52: hi,
    weekLow52: lo,
    spark: (b.sparkline_30d ?? []).slice(-30),
    format: region === "KR" ? "kr" : "en",
    unit: b.ticker === "USDKRW" ? "KRW" : undefined,
    observed_at: b.observed_at,
    is_stale: b.is_stale,
    // US indices arrive with `proxy_ticker` (SPY/QQQ/DIA/IWM/VIXY) because
    // FMP Starter gates ^GSPC/^IXIC/^DJI/^RUT/^VIX. The `level` is the ETF
    // price — NEVER ratio-converted (routes/market.py:529). UI must surface
    // the proxy so users don't read SPY $708 as S&P 500 (actual ≈ 7108).
    proxy_ticker: b.proxy_ticker,
  };
}

function weekTag(): string {
  const d = new Date();
  const first = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - first.getTime()) / 86400000);
  const w = Math.ceil((days + first.getDay() + 1) / 7);
  return `${d.getFullYear()} · W${String(w).padStart(2, "0")}`;
}

export default function MarketPage() {
  const router = useRouter();
  const [tab, setTab] = useState<MarketTab>("US");
  const region = tab === "US" ? "us" : "kr";

  /* ────────────────────────────────────────────────────────────────
   * SWR — DO NOT MODIFY. Same keys, same cadence, same fallbacks.
   * ──────────────────────────────────────────────────────────────── */
  const { data } = useSWR<BackendIndex[]>(
    `${MARKET_INDICES}?region=${region}`,
    fetcher,
    {
      keepPreviousData: true,
      // Market open → 5s aggressive refresh; closed → 60s relaxed.
      refreshInterval: () => liveRefresh(5_000, 60_000),
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 2_000,
      errorRetryCount: 2,
      errorRetryInterval: 5_000,
    },
  );

  const { data: earningsData } = useSWR<{
    earnings?: Array<{ ticker: string; name?: string; date: string }>;
  }>(API.market.earnings, fetcher, {
    refreshInterval: 300_000,
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 60_000,
    errorRetryCount: 2,
    errorRetryInterval: 10_000,
  });

  const { data: fxData } = useSWR<FxResponse>(API.market.fx, fetcher, {
    refreshInterval: () => liveRefresh(5_000, 60_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    dedupingInterval: 2_000,
    errorRetryCount: 2,
    errorRetryInterval: 10_000,
  });

  const quotes: IndexQuote[] = useMemo(() => {
    // No mock fallback (2026-04-28). Static US_INDICES / KR_INDICES carried
    // 2024-vintage levels. Render an empty board and let the editorial empty
    // state surface "data unavailable" instead.
    if (!Array.isArray(data) || data.length < 3) return [];
    // KR sanity guard (2026-04-28 KIS scaling glitch defense). Backend now
    // drops out-of-range readings, but a second guard at the display
    // boundary protects against any cached payload or alt path.
    return data
      .filter((b) => {
        if (b.ticker === "^KS11" || b.name === "KOSPI") {
          return sanitizeKrIndex("KOSPI", b.level) !== null;
        }
        if (b.ticker === "^KQ11" || b.name === "KOSDAQ") {
          return sanitizeKrIndex("KOSDAQ", b.level) !== null;
        }
        return true;
      })
      .map((b) => toQuote(b, tab));
  }, [data, tab]);

  const upcomingEarnings = (earningsData?.earnings ?? []).slice(0, 6);

  // Format FX observation timestamp for the header and sidebar paper.
  const fxStatus = useMemo(() => {
    if (!fxData?.last_updated_ts) return null;
    const d = new Date(fxData.last_updated_ts * 1000);
    const hh = d.toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      timeZone: "Asia/Seoul",
      hour12: false,
    });
    const stale = fxData.is_stale || fxData.age_seconds > 300;
    return {
      label: `Last observed ${hh} KST`,
      rate: fxData.usd_krw,
      stale,
      hh,
    };
  }, [fxData]);

  // Live status — 30s tick so the cadence label flips across open/close.
  useNowTick(30_000);
  const marketOpen = isMarketOpen();
  const liveLabel = marketOpen
    ? "Live · refreshing every 5s"
    : fxStatus?.hh
      ? `Market closed · last observed ${fxStatus.hh} KST`
      : "Market closed";

  /* ────────────────────────────────────────────────────────────────
   * Active-paper controller (same pattern as /home).
   * ──────────────────────────────────────────────────────────────── */
  type PaperId = "overview" | "detail" | "sidebar";
  const [active, setActive] = useState<PaperId | null>(null);
  const onSelect = (id: PaperId) =>
    setActive((cur) => (cur === id ? null : id));

  // Pulse rows previously hard-coded fabricated headlines + times — removed
  // 2026-04-28 (legal: cannot publish editorial-looking news copy invented in
  // the front-end). Until a real news feed is wired in, the section renders
  // an editorial empty state.
  const pulse: { time: string; text: string }[] = [];

  return (
    <ErrorBoundary>
      {/* ═══════════ MASTHEAD — title + region tabs + status strip ═══════════ */}
      <header
        style={{
          marginTop: "-8px",
          marginBottom: 24,
          borderBottom: "0.5px solid rgba(184,149,106,0.22)",
          paddingBottom: 14,
        }}
      >
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <span className="pq-emboss-seal" aria-hidden>
              PivoxQuant
            </span>
            <h1
              className="pq-ink-h1"
              style={{ marginTop: 8, fontSize: "clamp(1.6rem, 3vw, 2.2rem)" }}
            >
              Morning Papers &middot; Indices
            </h1>
            <p
              className="mt-1 font-serif"
              style={{ fontSize: 14, color: "rgba(245,240,232,0.68)" }}
            >
              Levels across US and Korean markets, observed at last print.
            </p>
          </div>
          <div className="flex flex-col items-end gap-1.5">
            <span
              className="font-mono uppercase"
              style={{
                fontSize: 9.5,
                letterSpacing: "0.22em",
                color: "var(--pq-bronze)",
              }}
            >
              {weekTag()}
            </span>
            <div className="flex items-center gap-2">
              <span
                aria-label={marketOpen ? "Live" : "Market closed"}
                className={cn(
                  "inline-block h-2 w-2 rounded-full",
                  marketOpen
                    ? "pq-live-dot bg-[#7db487]"
                    : "bg-yellow-500/60",
                )}
              />
              <span
                className="font-mono uppercase"
                style={{
                  fontSize: 10,
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                }}
              >
                {liveLabel}
              </span>
            </div>
            {fxStatus ? (
              <div className="flex items-center gap-2">
                {fxStatus.stale ? (
                  <span
                    aria-label="Stale data"
                    title="FX rate has not refreshed in over 5 minutes"
                    className="inline-block h-1.5 w-1.5 rounded-full bg-[#d1a750]"
                  />
                ) : null}
                <span
                  className="font-mono tabular-nums"
                  style={{
                    fontSize: 10,
                    color: "rgba(245,240,232,0.55)",
                  }}
                >
                  USD/KRW{" "}
                  {fxStatus.rate.toLocaleString("ko-KR", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}{" "}
                  &middot; {fxStatus.label}
                  {fxStatus.stale ? " · Stale" : ""}
                </span>
              </div>
            ) : null}
          </div>
        </div>

        {/* Region tabs — preserved pill/underline style */}
        <div className="pq-ink-tabs mt-6 flex items-center gap-2">
          {(["US", "KR"] as MarketTab[]).map((t, idx) => (
            <div key={t} className="flex items-center gap-2">
              {idx === 1 && (
                <span
                  aria-hidden="true"
                  className="mx-1 text-[var(--pq-bronze)]"
                  style={{ opacity: 0.45, fontSize: "11px" }}
                >
                  &#10086;
                </span>
              )}
              <button
                type="button"
                onClick={() => {
                  setTab(t);
                  setActive(null); // reset active paper on region switch
                }}
                data-active={tab === t}
                className="pq-ink-tab"
              >
                {t === "US" ? "United States" : "Korea"}
              </button>
            </div>
          ))}
        </div>
      </header>

      {/* ═══════════ THE DESK — three stacked papers ═══════════ */}
      <DossierDesk>
        {/* ── Desktop: 3D stacked papers ── */}
        <div
          className="hidden md:block relative"
          style={{ margin: "0 auto", maxWidth: 1040, padding: "48px 0 32px" }}
        >
          {/* Paper 3 — Sidebar (back, left fan) */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              top: 90,
              zIndex: active === "sidebar" ? 30 : 1,
            }}
          >
            <PaperDocument
              rotation={-6.5}
              zOffset={-90}
              xOffset={-60}
              active={active === "sidebar"}
              dimmed={active !== null && active !== "sidebar"}
              onClick={() => onSelect("sidebar")}
              ariaLabel="FX, calendar and pulse paper"
            >
              <CalendarNewsPaper
                fxStatus={fxStatus}
                upcomingEarnings={upcomingEarnings}
                pulse={pulse}
                onEarningsClick={(ticker) => router.push(`/detail/${ticker}`)}
              />
            </PaperDocument>
          </div>

          {/* Paper 2 — Indices detail (mid, right fan) */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              top: 44,
              zIndex: active === "detail" ? 30 : 2,
            }}
          >
            <PaperDocument
              rotation={-3.5}
              zOffset={-40}
              xOffset={52}
              active={active === "detail"}
              dimmed={active !== null && active !== "detail"}
              onClick={() => onSelect("detail")}
              ariaLabel="Indices detail paper"
            >
              <IndicesDetailPaper
                region={tab}
                quotes={quotes}
                derivatives={undefined /* KR derivatives feed not yet wired */}
              />
            </PaperDocument>
          </div>

          {/* Paper 1 — Overview (front) */}
          <div
            style={{
              position: "relative",
              zIndex: active === "overview" || active === null ? 20 : 10,
            }}
          >
            <PaperDocument
              rotation={0}
              zOffset={0}
              xOffset={0}
              active={active === "overview"}
              dimmed={active !== null && active !== "overview"}
              onClick={() => onSelect("overview")}
              ariaLabel="Overview editorial paper"
            >
              <OverviewPaper
                region={tab}
                quotes={quotes}
                marketOpen={marketOpen}
                liveLabel={liveLabel}
                weekTag={weekTag()}
              />
            </PaperDocument>
          </div>

          {/* Spacer reserves footprint for the deepest paper */}
          <div aria-hidden style={{ height: 620 }} />

          <p
            style={{
              textAlign: "center",
              fontSize: 11.5,
              color: "rgba(245,240,232,0.4)",
              letterSpacing: "0.02em",
              marginTop: 32,
            }}
          className="font-serif" >
            {active
              ? "Click the surfaced sheet again to return it to the stack."
              : "Click any sheet to draw it forward."}
          </p>
        </div>

        {/* ── Mobile: vertical flat stack ── */}
        <div
          className="md:hidden flex flex-col gap-5"
          style={{ padding: "16px 0 24px" }}
        >
          <PaperDocument
            rotation={0}
            zOffset={0}
            xOffset={0}
            ariaLabel="Overview editorial paper"
          >
            <OverviewPaper
              region={tab}
              quotes={quotes}
              marketOpen={marketOpen}
              liveLabel={liveLabel}
              weekTag={weekTag()}
            />
          </PaperDocument>

          <PaperDocument
            rotation={0}
            zOffset={0}
            xOffset={0}
            ariaLabel="Indices detail paper"
          >
            <IndicesDetailPaper
              region={tab}
              quotes={quotes}
              derivatives={undefined /* KR derivatives feed not yet wired */}
            />
          </PaperDocument>

          <PaperDocument
            rotation={0}
            zOffset={0}
            xOffset={0}
            ariaLabel="FX, calendar and pulse paper"
          >
            <CalendarNewsPaper
              fxStatus={fxStatus}
              upcomingEarnings={upcomingEarnings}
              pulse={pulse}
              onEarningsClick={(ticker) => router.push(`/detail/${ticker}`)}
            />
          </PaperDocument>
        </div>
      </DossierDesk>

      {/* Foot signature — legal disclaimer mounted by (dashboard)/layout.tsx */}
      <FootSignature />
    </ErrorBoundary>
  );
}
