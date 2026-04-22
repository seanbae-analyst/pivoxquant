"use client";

import { Check, Loader2, RefreshCw, Unlink } from "lucide-react";
import { useT } from "@/lib/locale";

interface KisCardProps {
  /** Whether a KIS credential is currently stored on the backend. */
  connected: boolean;
  /** Human-readable last sync timestamp (optional). */
  lastSync?: string | null;
  /** Opens the connect modal. */
  onConnect: () => void;
  /** Triggers a manual sync; may return a Promise for spinner state. */
  onSync?: () => Promise<void> | void;
  /** Disconnects (deletes stored credential). */
  onDisconnect?: () => Promise<void> | void;
  /** Syncing spinner. */
  syncing?: boolean;
  /** Disconnecting spinner. */
  disconnecting?: boolean;
}

/**
 * KIS (한국투자증권) connection card in the Vantablack ink theme.
 *
 * Used in both onboarding (/onboarding/broker) and settings (/settings).
 * Read-only integration: observes holdings, transactions, balances.
 * Order execution is disabled by regulation — informational only.
 */
export function KisCard({
  connected,
  lastSync,
  onConnect,
  onSync,
  onDisconnect,
  syncing = false,
  disconnecting = false,
}: KisCardProps) {
  const t = useT();
  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] rounded-[2px] p-5 sm:p-6">
      {/* Header — kicker + name + status */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-1">
            Korea Investment &amp; Securities
          </div>
          <h3 className="font-serif italic text-lg text-[var(--pq-ivory)]">
            {t("brokerOnboarding.kis.name")}
          </h3>
        </div>
        {connected ? (
          <span className="inline-flex items-center gap-1 border border-[var(--pq-bronze)] px-2 py-0.5 text-[10px] tracking-[0.18em] uppercase text-[var(--pq-bronze)] shrink-0">
            <Check className="h-2.5 w-2.5" />
            Connected
          </span>
        ) : (
          <span className="inline-flex items-center border border-[rgba(245,240,232,0.2)] px-2 py-0.5 text-[10px] tracking-[0.18em] uppercase text-[rgba(245,240,232,0.5)] shrink-0">
            Not connected
          </span>
        )}
      </div>

      {/* Description */}
      <p className="mb-5 text-[12px] leading-relaxed text-[rgba(245,240,232,0.6)]">
        Read-only account integration. Observes holdings, transactions, and
        balances. Order execution is disabled — informational only.
      </p>

      {connected && lastSync && (
        <p className="mb-4 text-[10px] tracking-[0.18em] uppercase text-[rgba(245,240,232,0.4)]">
          Last sync · <span className="tabular-nums normal-case tracking-normal text-[rgba(245,240,232,0.6)]">{lastSync}</span>
        </p>
      )}

      {/* Actions */}
      {!connected ? (
        <button
          type="button"
          onClick={onConnect}
          className="pq-ink-btn-bronze w-full"
        >
          Connect KIS Account
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
            {syncing
              ? t("brokerOnboarding.kis.syncing")
              : t("brokerOnboarding.kis.sync")}
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
            {t("brokerOnboarding.kis.disconnect")}
          </button>
        </div>
      )}

      {/* Issuance guide — expandable */}
      <details className="group mt-5 pt-4 border-t border-[rgba(245,240,232,0.08)]">
        <summary className="cursor-pointer list-none text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)] hover:text-[var(--pq-bronze-light,var(--pq-bronze))] flex items-center justify-between">
          <span>How to issue KIS API credentials</span>
          <span className="transition-transform group-open:rotate-180" aria-hidden="true">↓</span>
        </summary>
        <ol className="mt-4 space-y-3 text-[12px] leading-relaxed text-[rgba(245,240,232,0.7)]">
          <li>
            <span className="text-[var(--pq-bronze)] font-serif italic mr-2">I.</span>
            Visit the KIS OpenAPI portal (
            <a
              href="https://apiportal.koreainvestment.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--pq-bronze)] underline decoration-[rgba(197,164,114,0.4)] underline-offset-2 hover:decoration-[var(--pq-bronze)]"
            >
              apiportal.koreainvestment.com
            </a>
            ) and sign in with your brokerage account.
          </li>
          <li>
            <span className="text-[var(--pq-bronze)] font-serif italic mr-2">II.</span>
            Under <span className="text-[var(--pq-ivory)]">API 신청 · Manage Keys</span>, apply for an APP KEY and APP SECRET pair.
            Choose <span className="text-[var(--pq-ivory)]">국내주식 · 해외주식 · 실시간시세</span> (read scope only).
          </li>
          <li>
            <span className="text-[var(--pq-bronze)] font-serif italic mr-2">III.</span>
            Copy your 8-digit account number in the format{" "}
            <code className="font-mono text-[var(--pq-ivory)] text-[11px] tabular-nums">12345678-01</code>.
          </li>
          <li>
            <span className="text-[var(--pq-bronze)] font-serif italic mr-2">IV.</span>
            Paste all three values above. We store them encrypted and never transmit orders.
          </li>
          <li>
            <span className="text-[var(--pq-bronze)] font-serif italic mr-2">V.</span>
            Click Connect. Your first sync takes ~30 seconds.
          </li>
        </ol>
      </details>
    </div>
  );
}
