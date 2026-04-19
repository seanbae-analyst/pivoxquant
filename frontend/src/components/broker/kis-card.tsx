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
 * Shared KIS (한국투자증권) connection card used in both onboarding and settings.
 * Keeps the visual language consistent with the Alpaca card and the 20-question
 * onboarding screens (sp-card shell, rounded-full CTAs, subtle gradient accent).
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
    <div className="sp-card p-4 sm:p-5 relative overflow-hidden">
      {/* Subtle gradient accent in the corner matches onboarding page */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-10 -right-10 h-28 w-28 rounded-full opacity-30 blur-2xl"
        style={{ background: "linear-gradient(135deg, #8b5cf6, #3b82f6)" }}
      />

      <div className="flex items-center gap-3 mb-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-950 text-[11px] font-bold tracking-wide text-white">
          KIS
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-900 truncate">
            {t("brokerOnboarding.kis.name")}
          </p>
          <p className="text-xs text-slate-500 truncate">
            {t("brokerOnboarding.kis.desc")}
          </p>
        </div>
        {connected ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-medium text-emerald-600 shrink-0">
            <Check className="h-3 w-3" />
            {t("brokerOnboarding.badge.connected")}
          </span>
        ) : (
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-500 shrink-0">
            {t("brokerOnboarding.badge.notConnected")}
          </span>
        )}
      </div>

      {connected && lastSync && (
        <p className="mb-3 text-[11px] text-slate-400">
          {t("brokerOnboarding.kis.lastSync")}: {lastSync}
        </p>
      )}

      {!connected ? (
        <button
          type="button"
          onClick={onConnect}
          className="w-full rounded-full bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-slate-800 active:scale-[0.97]"
        >
          {t("brokerOnboarding.kis.connect")}
        </button>
      ) : (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onSync?.()}
            disabled={syncing || disconnecting}
            className="flex-1 flex items-center justify-center gap-1.5 rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {syncing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {syncing
              ? t("brokerOnboarding.kis.syncing")
              : t("brokerOnboarding.kis.sync")}
          </button>
          <button
            type="button"
            onClick={() => onDisconnect?.()}
            disabled={syncing || disconnecting}
            className="flex items-center justify-center gap-1.5 rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-700 active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {disconnecting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Unlink className="h-4 w-4" />
            )}
            {t("brokerOnboarding.kis.disconnect")}
          </button>
        </div>
      )}
    </div>
  );
}
