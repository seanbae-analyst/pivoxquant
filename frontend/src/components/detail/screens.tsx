"use client";

/**
 * Detail-page full-screen states + back nav.
 *
 * - BackNav — shared editorial back button (router.back()).
 * - AccessDeniedScreen — §101 회피 (2026-04-29): analysis limited to held /
 *   watched tickers. 1-click watchlist add releases the gate. Legal gate.
 * - NoTickerScreen / NoDataScreen — graceful empty fallbacks. Name-first
 *   ticker display (never a naked code).
 */

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, Eye, Plus, SearchX } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { WATCHLIST } from "@/lib/endpoints";
import { tickerToName, normalizeTicker } from "@/lib/format";

export function BackNav() {
  const router = useRouter();
  return (
    <button
      type="button"
      onClick={() => router.back()}
      className="inline-flex min-h-[44px] items-center gap-1.5 -mx-2 px-2 py-2 text-pq-mono-xs tracking-[0.12em] uppercase text-[var(--pq-ivory-dim)] hover:text-[var(--pq-bronze)] transition-colors"
    >
      <ArrowLeft className="h-3.5 w-3.5" />
      Back
    </button>
  );
}

export function AccessDeniedScreen({
  ticker,
  onAddedToWatchlist,
}: {
  ticker: string;
  onAddedToWatchlist: () => void;
}) {
  const router = useRouter();
  const [adding, setAdding] = useState(false);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const handleAdd = useCallback(async () => {
    setAdding(true);
    setErrMsg(null);
    try {
      await apiFetch(WATCHLIST, {
        method: "POST",
        body: JSON.stringify({ ticker }),
      });
      toast.success("Added to watchlist");
      onAddedToWatchlist();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed";
      setErrMsg(msg);
      toast.error(msg);
    } finally {
      setAdding(false);
    }
  }, [ticker, onAddedToWatchlist]);

  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-10 md:p-12 rounded-sm text-center max-w-2xl mx-auto">
      <Eye className="mx-auto h-8 w-8 text-[var(--pq-bronze)]" strokeWidth={1.2} />
      <p className="mt-4 font-serif text-xl text-[var(--pq-ivory)]">
        분석은 보유/관심 종목 한정입니다.
      </p>
      <p className="mt-3 text-pq-body-sm leading-relaxed text-[var(--pq-ivory-mid)]">
        {/* Name-first (FINDING-026): "Apple (AAPL)" not a naked code. */}
        <span className="text-[var(--pq-bronze)]">
          {(() => {
            const nm = tickerToName(ticker);
            const display = normalizeTicker(ticker);
            return nm ? `${nm} (${display})` : display;
          })()}
        </span>{" "}
        분석은 관심종목 또는 보유 포지션으로 등록한 후 이용 가능합니다. 한 번
        추가하면 즉시 분석을 볼 수 있습니다.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <button
          type="button"
          onClick={handleAdd}
          disabled={adding}
          className="pq-ink-btn-bronze inline-flex items-center gap-1.5 disabled:opacity-40"
        >
          <Plus className="h-3.5 w-3.5" />
          {adding ? "Adding…" : "관심 종목 추가"}
        </button>
        <button
          type="button"
          onClick={() => router.back()}
          className="pq-ink-btn-ghost inline-flex items-center gap-1.5"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </button>
      </div>
      {errMsg ? (
        <p className="mt-4 text-pq-mono-xs text-[rgba(209,136,136,0.8)]">{errMsg}</p>
      ) : null}
      <p className="mt-6 text-pq-eyebrow uppercase tracking-[0.22em] text-[var(--pq-ivory-faint)]">
        Observational research only · Not investment advice
      </p>
    </div>
  );
}

export function NoTickerScreen() {
  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-12 rounded-sm text-center">
      <SearchX className="mx-auto h-8 w-8 text-[var(--pq-bronze)]" strokeWidth={1.2} />
      <p className="mt-4 font-serif text-xl text-[var(--pq-ivory)]">
        No ticker specified
      </p>
      <Link href="/discover" className="mt-6 inline-block pq-ink-btn-bronze">
        Browse discover
      </Link>
    </div>
  );
}

export function NoDataScreen({ displayTicker }: { displayTicker: string }) {
  const router = useRouter();
  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-12 rounded-sm text-center">
      <SearchX className="mx-auto h-8 w-8 text-[var(--pq-bronze)]" strokeWidth={1.2} />
      <p className="mt-4 font-serif text-xl text-[var(--pq-ivory)]">
        No data for &ldquo;{displayTicker}&rdquo;
      </p>
      <p className="mt-2 text-sm text-[var(--pq-ivory-dim)]">
        Ticker may be unsupported or temporarily unavailable.
      </p>
      <button
        type="button"
        onClick={() => router.back()}
        className="mt-6 pq-ink-btn-ghost inline-flex items-center gap-1.5"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back
      </button>
    </div>
  );
}
