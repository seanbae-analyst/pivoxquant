"use client";

import { useState } from "react";
import { ExternalLink, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { ModalShell } from "@/components/ui/modal-shell";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";

interface AlpacaConnectModalProps {
  onClose: () => void;
  /** Called after a successful connect so the parent can revalidate status. */
  onSuccess?: () => void;
}

/**
 * Form-based Alpaca (paper) connection modal — Vantablack ink theme.
 * POSTs { key_id, secret_key, env: "paper" } → /api/broker/alpaca/connect.
 * Live environment is intentionally disabled and rejected by the backend.
 *
 * Phase-1 (2026-04-24): Consumers gate mount with NEXT_PUBLIC_ALPACA_ENABLED
 * (see settings/page.tsx). Component body retained for phase-2 reinstatement.
 */
export function AlpacaConnectModal({
  onClose,
  onSuccess,
}: AlpacaConnectModalProps) {
  const [keyId, setKeyId] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const keyIdValid = /^[A-Za-z0-9_-]{10,128}$/.test(keyId.trim());
  const secretValid = secretKey.trim().length >= 20;
  const canSubmit = keyIdValid && secretValid && !submitting;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      await apiFetch(API.broker.alpacaConnect, {
        method: "POST",
        body: JSON.stringify({
          key_id: keyId.trim(),
          secret_key: secretKey.trim(),
          env: "paper",
        }),
      });
      toast.success("Alpaca paper account connected");
      onSuccess?.();
      onClose();
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : "Could not connect Alpaca. Check the keys and try again.";
      setErrorMsg(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell onClose={onClose} ariaLabel="Connect Alpaca paper account">
      <div
        className="my-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-md overflow-y-auto rounded-[2px] border border-[rgba(245,240,232,0.12)] p-5 sm:p-6 sm:max-h-[90vh]"
        style={{ background: "rgba(10,10,10,0.96)" }}
      >
        {/* Header */}
        <div className="mb-5 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-1">
              Alpaca Markets · US
            </div>
            <h3 className="font-serif text-xl text-[var(--pq-ivory)]">
              Connect Alpaca
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[2px] p-1.5 text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-ivory)] hover:bg-[rgba(245,240,232,0.04)] transition-colors"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Description — BYO (Bring Your Own Key) model, per legal 2026-04-27 */}
        <p className="mb-3 text-[12px] leading-relaxed text-[rgba(245,240,232,0.65)]">
          Enter your Alpaca paper trading keys. We store them encrypted and only
          use them to observe your paper account. Live trading is disabled in
          this release.
        </p>
        <p className="mb-5 text-[11px] leading-relaxed text-[rgba(245,240,232,0.55)]">
          Bring Your Own Key (BYO): market data is fetched under your own
          Alpaca account license. PivoxQuant does not redistribute Alpaca
          market data — your keys, your license.
        </p>

        {/* Help link */}
        <a
          href="https://alpaca.markets"
          target="_blank"
          rel="noopener noreferrer"
          className="mb-5 inline-flex items-center gap-1.5 text-[11px] tracking-[0.15em] uppercase text-[var(--pq-bronze)] hover:opacity-80 transition-opacity"
        >
          <ExternalLink className="h-3 w-3" />
          alpaca.markets
        </a>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Environment — paper only */}
          <div>
            <div className="mb-1.5 text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
              Environment
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                disabled
                aria-pressed={true}
                className="pq-ink-btn-bronze text-[11px]"
              >
                Paper
              </button>
              <button
                type="button"
                disabled
                aria-pressed={false}
                className="pq-ink-btn-ghost text-[11px] opacity-40 cursor-not-allowed"
                title="Live trading is disabled in this release."
              >
                Live · disabled
              </button>
            </div>
            <p className="mt-2 text-[10px] leading-relaxed text-[rgba(245,240,232,0.45)]">
              Live brokerage routing is off. This release observes your paper
              account only.
            </p>
          </div>

          {/* Key ID */}
          <div>
            <label
              htmlFor="alpaca-key-id"
              className="mb-1.5 block text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]"
            >
              API Key ID
            </label>
            <input
              id="alpaca-key-id"
              type="text"
              value={keyId}
              onChange={(e) => setKeyId(e.target.value)}
              placeholder="PKXXXXXXXXXXXXXXXXXX"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              className="pq-ink-input w-full"
            />
          </div>

          {/* Secret Key */}
          <div>
            <label
              htmlFor="alpaca-secret"
              className="mb-1.5 block text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]"
            >
              API Secret Key
            </label>
            <input
              id="alpaca-secret"
              type="password"
              value={secretKey}
              onChange={(e) => setSecretKey(e.target.value)}
              placeholder="••••••••••••••••••••••••••••••••"
              autoComplete="off"
              className="pq-ink-input w-full"
            />
          </div>

          {errorMsg && (
            <p className="text-[11px] text-[#d18888] leading-relaxed">
              {errorMsg}
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              disabled={!canSubmit}
              className="pq-ink-btn-bronze flex-1 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {submitting ? "Connecting…" : "Connect paper"}
            </button>
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="pq-ink-btn-ghost disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
          </div>
        </form>

        {/* Disclaimer */}
        <p className="mt-5 pt-4 border-t border-[rgba(245,240,232,0.08)] text-[10px] leading-relaxed text-[rgba(245,240,232,0.4)] tracking-[0.05em]">
          Alpaca integration is paper-only. No live orders will be placed. This
          is not investment advice.
        </p>
      </div>
    </ModalShell>
  );
}
