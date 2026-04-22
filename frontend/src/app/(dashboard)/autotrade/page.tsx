"use client";

/**
 * Autotrade — Vantablack ink engine console.
 *
 * Paper execution only. Uses /api/autotrade/* endpoints:
 *   status, start, stop, pending, approve/:id, reject/:id, sell-all (kill switch).
 *
 * Language is strictly neutral: "paper execution", "observed thresholds",
 * "recorded order" — no advice / recommendation wording.
 */

import { useState, useCallback } from "react";
import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { TierGate } from "@/components/ui/tier-gate";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  Bot,
  Play,
  Square,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldAlert,
} from "lucide-react";

/* ── Types ── */

interface AutoTradeStatus {
  running: boolean;
  mode: string;
  last_run?: string;
  trades_today?: number;
  pending_count?: number;
}

interface PendingTrade {
  id: string;
  ticker: string;
  name?: string;
  action: string;
  shares: number;
  price: number;
  reason: string;
  created_at: string;
  currency?: "USD" | "KRW";
  is_korean?: boolean;
}

interface PendingResponse {
  ok?: boolean;
  pending?: PendingTrade[];
  trades?: PendingTrade[];
}

/* ── Fetcher ── */

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

function weekTag(): string {
  const d = new Date();
  const first = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - first.getTime()) / 86400000);
  const w = Math.ceil((days + first.getDay() + 1) / 7);
  return `${d.getFullYear()} · W${String(w).padStart(2, "0")}`;
}

/* ── Circuit breakers (static ladder) ── */

const CIRCUIT_BREAKERS = [
  { name: "Daily Loss", threshold: "-3.0%", status: "nominal" as const },
  { name: "Portfolio VaR 1D", threshold: "-5.0%", status: "nominal" as const },
  { name: "Correlation Index", threshold: "0.85", status: "nominal" as const },
  { name: "VIX Regime", threshold: "> 30", status: "nominal" as const },
  { name: "Tail Ratio", threshold: "< 0.8", status: "nominal" as const },
];

/* ── Pending trade row ── */

function PendingTradeRow({
  trade,
  onApprove,
  onReject,
}: {
  trade: PendingTrade;
  onApprove: () => void;
  onReject: () => void;
}) {
  const isBuy = trade.action?.toLowerCase() === "buy";
  const sign = trade.is_korean || trade.currency === "KRW" ? "₩" : "$";
  return (
    <div className="grid grid-cols-[1.4fr_auto_auto_auto] items-center gap-4 border-b border-[rgba(245,240,232,0.06)] px-4 py-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate font-serif text-[14px] text-[var(--pq-ivory)]">
            {trade.name || trade.ticker}
          </span>
          <span
            className={
              "pq-ink-pill " +
              (isBuy ? "pq-ink-pill--pos" : "pq-ink-pill--neg")
            }
          >
            {isBuy ? "Entry order" : "Exit order"}
          </span>
        </div>
        <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.45)]">
          {trade.ticker} · {trade?.shares ?? 0} shares @ {sign}
          {trade?.price?.toLocaleString(undefined, { maximumFractionDigits: 2 }) ??
            "—"}
        </div>
        {trade.reason ? (
          <p className="mt-1 font-serif italic text-[12px] text-[rgba(245,240,232,0.55)]">
            Observed threshold: {trade.reason}
          </p>
        ) : null}
      </div>

      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.4)]">
        {new Date(trade.created_at).toLocaleTimeString()}
      </span>

      <button
        type="button"
        onClick={onApprove}
        className="pq-ink-btn-bronze"
        style={{ height: 32, padding: "0 14px" }}
      >
        <CheckCircle2 className="h-3.5 w-3.5" />
        <span>Log</span>
      </button>
      <button
        type="button"
        onClick={onReject}
        className="pq-ink-btn-ghost"
        style={{ height: 32, padding: "0 14px" }}
      >
        <XCircle className="h-3.5 w-3.5" />
        <span>Skip</span>
      </button>
    </div>
  );
}

/* ── Content ── */

function AutoTradeContent() {
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [killing, setKilling] = useState(false);

  const {
    data: status,
    isLoading: statusLoading,
    mutate: mutateStatus,
  } = useSWR<AutoTradeStatus>(API.autotrade.status, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 10_000,
  });

  const {
    data: pendingData,
    mutate: mutatePending,
  } = useSWR<PendingResponse>(API.autotrade.pending, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 10_000,
  });

  const pendingTrades = pendingData?.pending ?? pendingData?.trades ?? [];
  const isRunning = status?.running ?? false;

  const handleStart = useCallback(async () => {
    setStarting(true);
    try {
      await apiFetch(API.autotrade.start, {
        method: "POST",
        body: JSON.stringify({ mode: "paper" }),
      });
      await mutateStatus();
    } catch {
      // silent
    } finally {
      setStarting(false);
    }
  }, [mutateStatus]);

  const handleStop = useCallback(async () => {
    setStopping(true);
    try {
      await apiFetch(API.autotrade.stop, { method: "POST" });
      await mutateStatus();
    } catch {
      // silent
    } finally {
      setStopping(false);
    }
  }, [mutateStatus]);

  const handleKill = useCallback(async () => {
    const confirmed = window.confirm(
      "Kill Switch: flatten all paper positions and stop the engine?\n\nThis will log paper exit orders for every open position and halt automation.",
    );
    if (!confirmed) return;
    setKilling(true);
    try {
      await apiFetch(API.autotrade.sellAll, { method: "POST" });
      await apiFetch(API.autotrade.stop, { method: "POST" });
      await Promise.all([mutateStatus(), mutatePending()]);
    } catch {
      // silent
    } finally {
      setKilling(false);
    }
  }, [mutateStatus, mutatePending]);

  const handleApprove = useCallback(
    async (tradeId: string) => {
      try {
        await apiFetch(API.autotrade.approve(tradeId), { method: "POST" });
        await mutatePending();
      } catch {
        // silent
      }
    },
    [mutatePending],
  );

  const handleReject = useCallback(
    async (tradeId: string) => {
      try {
        await apiFetch(API.autotrade.reject(tradeId), { method: "POST" });
        await mutatePending();
      } catch {
        // silent
      }
    },
    [mutatePending],
  );

  return (
    <>
      <header className="mb-8 flex items-end justify-between gap-4">
        <div>
          <div className="pq-ink-kicker">AUTOMATION · 2026 · {weekTag().split("·")[1]?.trim() ?? ""}</div>
          <h1 className="pq-ink-h1 mt-2">Paper Execution Engine</h1>
          <p className="mt-2 font-serif italic text-sm text-[rgba(245,240,232,0.55)]">
            Algorithmic paper execution against observed thresholds. No live brokerage routing.
          </p>
        </div>

        <button
          type="button"
          onClick={handleKill}
          disabled={killing}
          className="inline-flex items-center gap-1.5 px-4 text-[11px] uppercase tracking-[0.18em] font-medium"
          style={{
            height: 36,
            background: "transparent",
            color: "#d18888",
            border: "0.5px solid rgba(209, 136, 136, 0.4)",
            borderRadius: 2,
          }}
        >
          <ShieldAlert className="h-4 w-4" />
          <span>{killing ? "Halting…" : "Kill Switch"}</span>
        </button>
      </header>

      {/* Paper mode banner */}
      <div
        className="mb-8 flex items-start gap-3 border px-4 py-3"
        style={{
          borderColor: "rgba(139, 111, 71, 0.35)",
          background: "rgba(139, 111, 71, 0.06)",
        }}
      >
        <AlertTriangle className="h-4 w-4 shrink-0 text-[var(--pq-bronze)] mt-0.5" strokeWidth={1.4} />
        <div>
          <div className="pq-ink-label" style={{ color: "var(--pq-bronze)" }}>
            Paper Mode Only
          </div>
          <p className="mt-1 font-serif italic text-[13px] leading-relaxed text-[rgba(245,240,232,0.7)]">
            All automation runs against simulated fills. No real brokerage is connected.
            Executions are logged as observations; no advice is provided.
          </p>
        </div>
      </div>

      {/* Status row */}
      {statusLoading ? (
        <div className="py-16 text-center font-serif italic text-[13px] text-[rgba(245,240,232,0.4)]">
          Loading engine status…
        </div>
      ) : (
        <section className="mb-10 grid grid-cols-1 gap-6 border-y border-[rgba(245,240,232,0.1)] py-6 md:grid-cols-4">
          <div>
            <div className="pq-ink-label">Engine</div>
            <div className="mt-1 flex items-center gap-2 font-serif italic text-[22px] text-[var(--pq-ivory)]">
              <span
                className="h-2 w-2 rounded-full"
                style={{
                  background: isRunning ? "#7db487" : "rgba(245,240,232,0.3)",
                }}
              />
              {isRunning ? "Running" : "Idle"}
            </div>
          </div>
          <div>
            <div className="pq-ink-label">Mode</div>
            <div className="mt-1 font-serif italic text-[22px] text-[var(--pq-ivory)]">
              {status?.mode === "paper" ? "Paper" : status?.mode ?? "Paper"}
            </div>
          </div>
          <div>
            <div className="pq-ink-label">Logged Today</div>
            <div className="mt-1 font-serif italic text-[22px] tabular-nums text-[var(--pq-ivory)]">
              {status?.trades_today ?? 0}
            </div>
          </div>
          <div>
            <div className="pq-ink-label">Pending</div>
            <div className="mt-1 font-serif italic text-[22px] tabular-nums text-[var(--pq-ivory)]">
              {status?.pending_count ?? pendingTrades.length}
            </div>
          </div>
        </section>
      )}

      {/* Engine controls */}
      <section className="mb-10 flex items-center gap-3">
        {!isRunning ? (
          <button
            type="button"
            onClick={handleStart}
            disabled={starting}
            className="pq-ink-btn-bronze disabled:opacity-40"
          >
            <Play className="h-4 w-4" />
            <span>{starting ? "Starting…" : "Start Paper Engine"}</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={handleStop}
            disabled={stopping}
            className="pq-ink-btn-ghost disabled:opacity-40"
          >
            <Square className="h-4 w-4" />
            <span>{stopping ? "Stopping…" : "Stop Engine"}</span>
          </button>
        )}
        {status?.last_run && (
          <span className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.45)]">
            <Clock className="h-3 w-3" />
            Last run · {new Date(status.last_run).toLocaleString()}
          </span>
        )}
      </section>

      {/* Circuit Breakers */}
      <section className="mb-10">
        <div className="mb-3">
          <div className="pq-ink-label">Circuit Breakers</div>
          <h2 className="pq-ink-h2 mt-1">Five-Layer Risk Ladder</h2>
        </div>
        <div className="border-t border-[rgba(245,240,232,0.1)]">
          {CIRCUIT_BREAKERS.map((b) => (
            <div
              key={b.name}
              className="grid grid-cols-[1.5fr_auto_auto] items-center gap-4 border-b border-[rgba(245,240,232,0.06)] px-4 py-3"
            >
              <span className="font-serif text-[13px] text-[var(--pq-ivory)]">
                {b.name}
              </span>
              <span className="font-mono text-[12px] tabular-nums text-[rgba(245,240,232,0.7)]">
                {b.threshold}
              </span>
              <span className="pq-ink-pill pq-ink-pill--neu">Nominal</span>
            </div>
          ))}
        </div>
      </section>

      {/* Pending trades */}
      <section className="mb-10">
        <div className="mb-3 flex items-baseline justify-between">
          <div>
            <div className="pq-ink-label">Pending Log</div>
            <h2 className="pq-ink-h2 mt-1">Awaiting Confirmation</h2>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[rgba(245,240,232,0.45)]">
            {pendingTrades.length}
          </span>
        </div>

        {pendingTrades.length === 0 ? (
          <div className="border-y border-[rgba(245,240,232,0.1)] py-10 text-center font-serif italic text-[13px] text-[rgba(245,240,232,0.4)]">
            {isRunning
              ? "Engine running. Observed orders will appear here for manual logging."
              : "Start the engine to surface threshold-crossed orders for review."}
          </div>
        ) : (
          <div className="border-t border-[rgba(245,240,232,0.1)]">
            {pendingTrades.map((trade) => (
              <PendingTradeRow
                key={trade.id}
                trade={trade}
                onApprove={() => handleApprove(trade.id)}
                onReject={() => handleReject(trade.id)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Disclaimer */}
      <div className="border-t border-[rgba(245,240,232,0.1)] pt-6 text-[rgba(245,240,232,0.7)]">
        <DisclaimerBanner type="auto-trade" alwaysExpanded />
      </div>
    </>
  );
}

export default function AutoTradePage() {
  return (
    <ErrorBoundary>
      <TierGate tier="premium">
        <AutoTradeContent />
      </TierGate>
    </ErrorBoundary>
  );
}

// Suppress unused warning for icon used in pill-era layouts.
void Bot;
