"use client";

import { useState } from "react";
import { ExternalLink, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { ModalShell } from "@/components/ui/modal-shell";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { useT } from "@/lib/locale";

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
  // 2026-05-18 Wave G-2 P2 Bug #7: Alpaca modal had zero i18n coverage —
  // 100% English hardcoded strings while the rest of the broker surface is
  // KR-first. Added brokerOnboarding.alpaca.* keys mirroring the KIS pattern.
  const t = useT();
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
      toast.success(t("brokerOnboarding.alpaca.connectSuccess"));
      onSuccess?.();
      onClose();
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : t("brokerOnboarding.alpaca.connectError");
      setErrorMsg(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell onClose={onClose} ariaLabel={t("brokerOnboarding.alpaca.modalTitle")}>
      <div
        className="my-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-md overflow-y-auto rounded-[2px] border border-[rgba(245,240,232,0.12)] p-5 sm:p-6 sm:max-h-[90vh]"
        style={{ background: "rgba(10,10,10,0.96)" }}
      >
        {/* Header */}
        <div className="mb-5 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-1">
              {t("brokerOnboarding.alpaca.eyebrow")}
            </div>
            <h3 className="font-serif text-xl text-[var(--pq-ivory)]">
              {t("brokerOnboarding.alpaca.modalTitle")}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[2px] p-1.5 text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-ivory)] hover:bg-[var(--pq-ivory-line-faint)] transition-colors"
            aria-label={t("brokerOnboarding.cancel")}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Description — BYO (Bring Your Own Key) model, per legal 2026-04-27 */}
        <p className="mb-3 text-pq-caption leading-relaxed text-[rgba(245,240,232,0.65)]">
          {t("brokerOnboarding.alpaca.modalSubtitle")}
        </p>
        <p className="mb-5 text-pq-mono-sm leading-relaxed text-[rgba(245,240,232,0.55)]">
          {t("brokerOnboarding.alpaca.byoNote")}
        </p>

        {/* Help link */}
        <a
          href="https://alpaca.markets"
          target="_blank"
          rel="noopener noreferrer"
          className="mb-5 inline-flex items-center gap-1.5 text-pq-mono-sm tracking-[0.15em] uppercase text-[var(--pq-bronze)] hover:opacity-80 transition-opacity"
        >
          <ExternalLink className="h-3 w-3" />
          alpaca.markets
        </a>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Environment — paper only */}
          <div>
            <div className="mb-1.5 text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
              {t("brokerOnboarding.alpaca.envLabel")}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                disabled
                aria-pressed={true}
                className="pq-ink-btn-bronze text-pq-mono-sm"
              >
                {t("brokerOnboarding.alpaca.envPaper")}
              </button>
              <button
                type="button"
                disabled
                aria-pressed={false}
                className="pq-ink-btn-ghost text-pq-mono-sm opacity-40 cursor-not-allowed"
                title={t("brokerOnboarding.alpaca.envLiveDisabledTitle")}
              >
                {t("brokerOnboarding.alpaca.envLiveDisabled")}
              </button>
            </div>
            <p className="mt-2 text-pq-eyebrow leading-relaxed text-[rgba(245,240,232,0.45)]">
              {t("brokerOnboarding.alpaca.envNote")}
            </p>
          </div>

          {/* Key ID */}
          <div>
            <label
              htmlFor="alpaca-key-id"
              className="mb-1.5 block text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]"
            >
              {t("brokerOnboarding.alpaca.keyId")}
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
              aria-invalid={!!errorMsg}
              aria-describedby={errorMsg ? "alpaca-error" : undefined}
              className="pq-ink-input w-full"
            />
          </div>

          {/* Secret Key */}
          <div>
            <label
              htmlFor="alpaca-secret"
              className="mb-1.5 block text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]"
            >
              {t("brokerOnboarding.alpaca.secretKey")}
            </label>
            <input
              id="alpaca-secret"
              type="password"
              value={secretKey}
              onChange={(e) => setSecretKey(e.target.value)}
              placeholder="••••••••••••••••••••••••••••••••"
              autoComplete="off"
              aria-invalid={!!errorMsg}
              aria-describedby={errorMsg ? "alpaca-error" : undefined}
              className="pq-ink-input w-full"
            />
          </div>

          {errorMsg && (
            <p id="alpaca-error" role="alert" className="text-pq-mono-sm text-[#d18888] leading-relaxed">
              {errorMsg}
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              disabled={!canSubmit}
              // 2026-05-18 Wave G-2 P2 Bug #5: mirror the KIS modal fix —
              // `pq-ink-btn-bronze` sets `cursor: pointer` without a
              // `:disabled { cursor: not-allowed }` selector, so the
              // Tailwind `disabled:cursor-not-allowed` variant loses
              // specificity. Inline style guarantees not-allowed wins
              // regardless of CSS layer order.
              style={!canSubmit ? { cursor: "not-allowed" } : undefined}
              className="pq-ink-btn-bronze flex-1 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {submitting
                ? t("brokerOnboarding.alpaca.connecting")
                : t("brokerOnboarding.alpaca.connectBtn")}
            </button>
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="pq-ink-btn-ghost disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {t("brokerOnboarding.cancel")}
            </button>
          </div>
        </form>

        {/* Disclaimer */}
        <p className="mt-5 pt-4 border-t border-[var(--pq-ivory-line)] text-pq-eyebrow leading-relaxed text-[rgba(245,240,232,0.4)] tracking-[0.05em]">
          {t("brokerOnboarding.alpaca.disclaimer")}
        </p>
      </div>
    </ModalShell>
  );
}
