"use client";

import { Check, Loader2, RefreshCw, Unlink } from "lucide-react";

interface AlpacaCardProps {
  /** Whether Alpaca credentials are currently stored on the backend. */
  connected: boolean;
  /** "paper" (only option in this release). */
  mode?: "paper" | "live";
  /** Human-readable last sync timestamp (ISO string). */
  lastSync?: string | null;
  /** Opens the connect modal. */
  onConnect: () => void;
  /** Triggers a manual sync. */
  onSync?: () => Promise<void> | void;
  /** Disconnects (deletes stored credentials). */
  onDisconnect?: () => Promise<void> | void;
  /** Syncing spinner. */
  syncing?: boolean;
  /** Disconnecting spinner. */
  disconnecting?: boolean;
}

/**
 * Alpaca (US equity paper) connection card — Vantablack ink theme.
 *
 * Hidden by default. Only renders when NEXT_PUBLIC_ALPACA_ENABLED === "1".
 * The component body is retained (2026-04-24 phase-1 UI hide — backend removal
 * is phase-2) so we can re-enable quickly if policy changes, but the public
 * surface area is now zero. Symmetric with KisCard. Paper-only; live is
 * disabled by policy.
 */
export function AlpacaCard({
  connected,
  mode = "paper",
  lastSync,
  onConnect,
  onSync,
  onDisconnect,
  syncing = false,
  disconnecting = false,
}: AlpacaCardProps) {
  // Phase-1: UI completely hidden pending My Data license resolution.
  // Re-enable by setting NEXT_PUBLIC_ALPACA_ENABLED=1.
  if (process.env.NEXT_PUBLIC_ALPACA_ENABLED !== "1") {
    return null;
  }

  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] rounded-[2px] p-5 sm:p-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-1">
            Alpaca Markets · US
          </div>
          <h3 className="font-serif text-lg text-[var(--pq-ivory)]">
            Alpaca
          </h3>
        </div>
        {connected ? (
          <span className="inline-flex items-center gap-1 border border-[var(--pq-bronze)] px-2 py-0.5 text-pq-eyebrow tracking-[0.18em] uppercase text-[var(--pq-bronze)] shrink-0">
            <Check className="h-2.5 w-2.5" />
            {mode === "paper" ? "Paper" : "Connected"}
          </span>
        ) : (
          <span className="inline-flex items-center border border-[rgba(245,240,232,0.2)] px-2 py-0.5 text-pq-eyebrow tracking-[0.18em] uppercase text-[rgba(245,240,232,0.5)] shrink-0">
            Not connected
          </span>
        )}
      </div>

      {/* Description */}
      <p className="mb-5 text-pq-caption leading-relaxed text-[rgba(245,240,232,0.6)]">
        US equity paper trading integration. Observes holdings, historical
        trades, and allows paper order logging. Real-money trading is
        disabled in this release.
      </p>

      {connected && lastSync && (
        <p className="mb-4 text-pq-eyebrow tracking-[0.18em] uppercase text-[rgba(245,240,232,0.4)]">
          Last sync ·{" "}
          <span className="tabular-nums normal-case tracking-normal text-[rgba(245,240,232,0.6)]">
            {new Date(lastSync).toLocaleString()}
          </span>
        </p>
      )}

      {/* Actions */}
      {!connected ? (
        <button
          type="button"
          onClick={onConnect}
          className="pq-ink-btn-bronze w-full"
        >
          Connect Alpaca
        </button>
      ) : (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onSync?.()}
            disabled={syncing || disconnecting}
            className="pq-ink-btn-ghost flex-1 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {syncing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            {syncing ? "Syncing…" : "Sync"}
          </button>
          <button
            type="button"
            onClick={onConnect}
            disabled={syncing || disconnecting}
            className="pq-ink-btn-ghost disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Reconnect
          </button>
          <button
            type="button"
            onClick={() => onDisconnect?.()}
            disabled={syncing || disconnecting}
            className="pq-ink-btn-ghost disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {disconnecting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Unlink className="h-3.5 w-3.5" />
            )}
            Disconnect
          </button>
        </div>
      )}

      {/* Issuance guide */}
      <details className="group mt-5 pt-4 border-t border-[var(--pq-ivory-line)]">
        <summary className="cursor-pointer list-none text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] hover:text-[var(--pq-bronze-light,var(--pq-bronze))] flex items-center justify-between">
          <span>How to issue Alpaca paper keys</span>
          <span
            className="transition-transform group-open:rotate-180"
            aria-hidden="true"
          >
            ↓
          </span>
        </summary>
        <ol className="mt-4 space-y-3 text-pq-caption leading-relaxed text-[rgba(245,240,232,0.7)]">
          <li>
            <span className="text-[var(--pq-bronze)] font-serif mr-2">
              I.
            </span>
            Create a free paper account at{" "}
            <a
              href="https://alpaca.markets"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--pq-bronze)] underline decoration-[rgba(197,164,114,0.4)] underline-offset-2 hover:decoration-[var(--pq-bronze)]"
            >
              alpaca.markets
            </a>
            .
          </li>
          <li>
            <span className="text-[var(--pq-bronze)] font-serif mr-2">
              II.
            </span>
            Dashboard →{" "}
            <span className="text-[var(--pq-ivory)]">Paper Overview</span> →
            &ldquo;Generate New Keys&rdquo;.
          </li>
          <li>
            <span className="text-[var(--pq-bronze)] font-serif mr-2">
              III.
            </span>
            Copy <span className="text-[var(--pq-ivory)]">API Key ID</span> and{" "}
            <span className="text-[var(--pq-ivory)]">API Secret Key</span>.
          </li>
          <li>
            <span className="text-[var(--pq-bronze)] font-serif mr-2">
              IV.
            </span>
            Paste them above. We store them encrypted and never transmit live
            orders.
          </li>
        </ol>
      </details>
    </div>
  );
}
