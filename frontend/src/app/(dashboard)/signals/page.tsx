"use client";

/**
 * Signals — Vantablack ink terminal on dashboard shell.
 *
 * Quantitative observations (POSITIVE / NEGATIVE / NEUTRAL). No advice
 * language. Signals are fetched from /api/signals and segmented into
 * three columns: Top Positive, Neutral zone, Top Negative.
 *
 * Filters: All / Positive / Negative / Neutral (pill row).
 * Each row is clickable → /detail/{ticker}.
 */

import { useState, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { fmtPct } from "@/lib/format";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { RefreshCw, Zap } from "lucide-react";

/* ── Types ── */

interface SignalItem {
  ticker: string;
  name: string;
  signal: string;
  score: number;
  price: number;
  change_pct: number;
  sector: string;
  currency: "USD" | "KRW";
  is_korean: boolean;
  tech_score?: number;
  fund_score?: number;
  news_score?: number;
  quant_score?: number;
}

interface SignalsListResponse {
  signals: SignalItem[];
}

/* ── Fetcher ── */

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

/* ── Filters ── */

const FILTERS = ["All", "POSITIVE", "NEUTRAL", "NEGATIVE"] as const;
type FilterValue = (typeof FILTERS)[number];

function filterLabel(f: FilterValue) {
  if (f === "All") return "All";
  return f.charAt(0) + f.slice(1).toLowerCase();
}

function weekTag(): string {
  const d = new Date();
  const first = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - first.getTime()) / 86400000);
  const w = Math.ceil((days + first.getDay() + 1) / 7);
  return `${d.getFullYear()} · W${String(w).padStart(2, "0")}`;
}

function signalPillClass(sig: string) {
  if (sig === "POSITIVE") return "pq-ink-pill pq-ink-pill--pos";
  if (sig === "NEGATIVE") return "pq-ink-pill pq-ink-pill--neg";
  return "pq-ink-pill pq-ink-pill--neu";
}

function signalLabel(sig: string) {
  if (sig === "POSITIVE") return "Positive";
  if (sig === "NEGATIVE") return "Negative";
  return "Neutral";
}

function formatPrice(item: SignalItem): string {
  if (item?.price == null) return "—";
  if (item.currency === "KRW") {
    return `₩${Math.round(item.price).toLocaleString("ko-KR")}`;
  }
  return `$${item.price.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/* ── Row ── */

function SignalRow({ item, onClick }: { item: SignalItem; onClick: () => void }) {
  const isPositive = (item?.change_pct ?? 0) >= 0;
  return (
    <button
      type="button"
      onClick={onClick}
      className="group w-full border-b border-[rgba(245,240,232,0.06)] px-4 py-3 text-left transition-colors hover:bg-[rgba(245,240,232,0.03)]"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-serif text-[14px] text-[var(--pq-ivory)]">
              {item.name || item.ticker}
            </span>
            <span className={signalPillClass(item.signal)}>
              {signalLabel(item.signal)}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.45)]">
            <span>{item.ticker}</span>
            {item.sector ? <span>· {item.sector}</span> : null}
          </div>
        </div>

        <div className="text-right">
          <div className="font-mono text-[13px] tabular-nums text-[var(--pq-ivory)]">
            {formatPrice(item)}
          </div>
          <div
            className="mt-0.5 font-mono text-[11px] tabular-nums"
            style={{
              color: isPositive ? "#7db487" : "#d18888",
            }}
          >
            {fmtPct(item?.change_pct ?? 0)}
          </div>
        </div>

        {/* Composite score */}
        <div className="w-[60px] text-right">
          <div className="pq-ink-label" style={{ fontSize: "9px" }}>
            Score
          </div>
          <div className="mt-0.5 font-serif italic text-[18px] tabular-nums text-[var(--pq-ivory)]">
            {Math.round(item.score ?? 0)}
          </div>
        </div>
      </div>
    </button>
  );
}

/* ── Column ── */

function SignalColumn({
  title,
  kicker,
  items,
  onClick,
}: {
  title: string;
  kicker: string;
  items: SignalItem[];
  onClick: (ticker: string) => void;
}) {
  return (
    <section>
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <div className="pq-ink-label">{kicker}</div>
          <h2 className="pq-ink-h2 mt-1">{title}</h2>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[rgba(245,240,232,0.45)]">
          {items.length}
        </span>
      </div>

      {items.length === 0 ? (
        <div className="border-t border-[rgba(245,240,232,0.1)] py-10 text-center font-serif italic text-[12px] text-[rgba(245,240,232,0.4)]">
          No observations in this band.
        </div>
      ) : (
        <div className="border-t border-[rgba(245,240,232,0.1)]">
          {items.map((item) => (
            <SignalRow
              key={item.ticker}
              item={item}
              onClick={() => onClick(item.ticker)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

/* ── Page ── */

export default function SignalsPage() {
  const router = useRouter();
  const [filter, setFilter] = useState<FilterValue>("All");
  const [refreshing, setRefreshing] = useState(false);

  const { data, isLoading, mutate } = useSWR<SignalsListResponse>(
    API.signals.all,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  );

  const signals = useMemo(() => data?.signals ?? [], [data?.signals]);

  const { positive, neutral, negative } = useMemo(() => {
    const p: SignalItem[] = [];
    const n: SignalItem[] = [];
    const neu: SignalItem[] = [];
    for (const s of signals) {
      if (s.signal === "POSITIVE") p.push(s);
      else if (s.signal === "NEGATIVE") n.push(s);
      else neu.push(s);
    }
    const byScore = (a: SignalItem, b: SignalItem) =>
      (b.score ?? 0) - (a.score ?? 0);
    return {
      positive: p.sort(byScore).slice(0, 12),
      neutral: neu.sort(byScore).slice(0, 12),
      negative: n.sort((a, b) => (a.score ?? 0) - (b.score ?? 0)).slice(0, 12),
    };
  }, [signals]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await apiFetch(API.signals.refresh, { method: "POST" });
      await mutate();
    } catch {
      // silent — SWR keeps stale view
    } finally {
      setRefreshing(false);
    }
  }, [mutate]);

  const onRowClick = useCallback(
    (ticker: string) => router.push(`/detail/${ticker}`),
    [router],
  );

  const showAll = filter === "All";
  const showPos = showAll || filter === "POSITIVE";
  const showNeu = showAll || filter === "NEUTRAL";
  const showNeg = showAll || filter === "NEGATIVE";

  return (
    <ErrorBoundary>
      <header className="mb-8 flex items-end justify-between gap-4">
        <div>
          <div className="pq-ink-kicker">SIGNALS · 2026 · {weekTag().split("·")[1]?.trim() ?? ""}</div>
          <h1 className="pq-ink-h1 mt-2">Observation Board</h1>
          <p className="mt-2 font-serif italic text-sm text-[rgba(245,240,232,0.55)]">
            Quantitative observations across {signals.length} covered tickers. Neutral language only.
          </p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          className="pq-ink-btn-ghost disabled:opacity-40"
        >
          <RefreshCw className={"h-3.5 w-3.5 " + (refreshing ? "animate-spin" : "")} />
          <span>Refresh</span>
        </button>
      </header>

      {/* Stats strip */}
      <div className="mb-8 grid grid-cols-3 gap-6 border-y border-[rgba(245,240,232,0.1)] py-5">
        <div>
          <div className="pq-ink-label">Positive</div>
          <div className="mt-1 font-serif italic text-[28px] tabular-nums text-[#7db487]">
            {positive.length}
          </div>
        </div>
        <div>
          <div className="pq-ink-label">Neutral</div>
          <div className="mt-1 font-serif italic text-[28px] tabular-nums text-[var(--pq-ivory)]">
            {neutral.length}
          </div>
        </div>
        <div>
          <div className="pq-ink-label">Negative</div>
          <div className="mt-1 font-serif italic text-[28px] tabular-nums text-[#d18888]">
            {negative.length}
          </div>
        </div>
      </div>

      {/* Filter pills */}
      <div className="pq-ink-tabs mb-8">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            data-active={filter === f}
            className="pq-ink-tab"
          >
            {filterLabel(f)}
          </button>
        ))}
      </div>

      {/* Loading */}
      {isLoading && signals.length === 0 ? (
        <div className="py-24 text-center font-serif italic text-[13px] text-[rgba(245,240,232,0.4)]">
          Loading observations…
        </div>
      ) : signals.length === 0 ? (
        <div className="py-24 text-center">
          <Zap className="mx-auto h-8 w-8 text-[var(--pq-bronze)]" strokeWidth={1.3} />
          <div className="mt-3 font-serif italic text-[14px] text-[rgba(245,240,232,0.6)]">
            No observations on record.
          </div>
          <p className="mt-1 text-[12px] text-[rgba(245,240,232,0.4)]">
            Add positions or tickers to your watchlist to generate signals.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-3 lg:gap-8">
          {showPos && (
            <SignalColumn
              title="Top Positive"
              kicker="Above Threshold"
              items={positive}
              onClick={onRowClick}
            />
          )}
          {showNeu && (
            <SignalColumn
              title="Neutral Zone"
              kicker="Within Band"
              items={neutral}
              onClick={onRowClick}
            />
          )}
          {showNeg && (
            <SignalColumn
              title="Top Negative"
              kicker="Below Threshold"
              items={negative}
              onClick={onRowClick}
            />
          )}
        </div>
      )}

      <div className="mt-12 border-t border-[rgba(245,240,232,0.1)] pt-6 text-[rgba(245,240,232,0.7)]">
        <DisclaimerBanner type="signal" />
      </div>
    </ErrorBoundary>
  );
}
