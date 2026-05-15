"use client";

import { useState } from "react";
import { ExternalLink, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { ModalShell } from "@/components/ui/modal-shell";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { useT } from "@/lib/locale";

interface KisConnectModalProps {
  onClose: () => void;
  /** Called after a successful connect so the parent can revalidate status. */
  onSuccess?: () => void;
}

/**
 * Form-based KIS connection modal — Vantablack ink theme.
 * POSTs { app_key, app_secret, account_no, account_prod } → /api/broker/kis/connect.
 * Backend stores credentials encrypted (routes/broker_oauth.py).
 */
export function KisConnectModal({ onClose, onSuccess }: KisConnectModalProps) {
  const t = useT();
  const [appKey, setAppKey] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [accountNo, setAccountNo] = useState("");
  const [accountProd, setAccountProd] = useState("01");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // 2026-05-15 (bug-hunter Wave 6 LOW #4): KIS account numbers are
  // strictly 8 digits per the format hint inside this modal
  // ("12345678-01"). The previous 6-12 digit regex accepted invalid
  // entries that would later 4xx at the KIS API. Tighten to exactly 8.
  const accountNoValid = /^\d{8}$/.test(accountNo);
  const accountProdValid = /^\d{2}$/.test(accountProd);
  const canSubmit =
    appKey.trim().length > 0 &&
    appSecret.trim().length > 0 &&
    accountNoValid &&
    accountProdValid &&
    !submitting;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      await apiFetch(API.broker.kisConnect, {
        method: "POST",
        body: JSON.stringify({
          app_key: appKey.trim(),
          app_secret: appSecret.trim(),
          account_no: accountNo.trim(),
          account_prod: accountProd.trim(),
        }),
      });
      toast.success("KIS connected · observing only");
      onSuccess?.();
      onClose();
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : t("brokerOnboarding.kis.connectError");
      setErrorMsg(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell onClose={onClose} ariaLabel="Connect Korea Investment & Securities">
      <div
        className="my-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-md overflow-y-auto rounded-[2px] border border-[rgba(245,240,232,0.12)] p-5 sm:p-6 sm:max-h-[90vh]"
        style={{ background: "rgba(10,10,10,0.96)" }}
      >
        {/* Header */}
        <div className="mb-5 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-1">
              Korea Investment &amp; Securities
            </div>
            <h3 className="font-serif text-xl text-[var(--pq-ivory)]">
              Connect KIS Account
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[2px] p-1.5 text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-ivory)] hover:bg-[var(--pq-ivory-line-faint)] transition-colors"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Description */}
        <p className="mb-5 text-pq-caption leading-relaxed text-[rgba(245,240,232,0.65)]">
          Enter your KIS API credentials to link your brokerage account. This is
          read-only — we observe holdings and transactions without trading.
        </p>

        {/* Help link */}
        <a
          href="https://apiportal.koreainvestment.com"
          target="_blank"
          rel="noopener noreferrer"
          className="mb-5 inline-flex items-center gap-1.5 text-pq-mono-sm tracking-[0.15em] uppercase text-[var(--pq-bronze)] hover:opacity-80 transition-opacity"
        >
          <ExternalLink className="h-3 w-3" />
          KIS OpenAPI portal
        </a>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* APP KEY */}
          <div>
            <label
              htmlFor="kis-app-key"
              className="mb-1.5 block text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]"
            >
              App Key
            </label>
            <input
              id="kis-app-key"
              type="text"
              value={appKey}
              onChange={(e) => setAppKey(e.target.value)}
              placeholder="PSabc123def456..."
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              aria-invalid={!!errorMsg}
              aria-describedby={errorMsg ? "kis-error" : undefined}
              className="pq-ink-input w-full"
            />
          </div>

          {/* APP SECRET */}
          <div>
            <label
              htmlFor="kis-app-secret"
              className="mb-1.5 block text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]"
            >
              App Secret
            </label>
            <input
              id="kis-app-secret"
              type="password"
              value={appSecret}
              onChange={(e) => setAppSecret(e.target.value)}
              placeholder="••••••••••••••••••••"
              autoComplete="off"
              aria-invalid={!!errorMsg}
              aria-describedby={errorMsg ? "kis-error" : undefined}
              className="pq-ink-input w-full"
            />
          </div>

          {/* ACCOUNT NUMBER */}
          <div className="grid grid-cols-3 gap-2">
            <div className="col-span-2">
              <label
                htmlFor="kis-account-no"
                className="mb-1.5 block text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]"
              >
                Account No.
              </label>
              <input
                id="kis-account-no"
                type="text"
                inputMode="numeric"
                value={accountNo}
                onChange={(e) =>
                  setAccountNo(e.target.value.replace(/[^0-9]/g, "").slice(0, 12))
                }
                placeholder="12345678"
                autoComplete="off"
                aria-invalid={accountNo.length > 0 && !accountNoValid}
                aria-describedby={
                  accountNo.length > 0 && !accountNoValid ? "kis-account-no-hint" : undefined
                }
                className="pq-ink-input w-full tabular-nums"
              />
              {accountNo.length > 0 && !accountNoValid && (
                <p id="kis-account-no-hint" role="alert" className="mt-1.5 text-pq-eyebrow text-[#d18888]">
                  {t("brokerOnboarding.kis.accountNoHint")}
                </p>
              )}
            </div>
            <div>
              <label
                htmlFor="kis-account-prod"
                className="mb-1.5 block text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]"
              >
                Product
              </label>
              <input
                id="kis-account-prod"
                type="text"
                inputMode="numeric"
                value={accountProd}
                onChange={(e) =>
                  setAccountProd(e.target.value.replace(/[^0-9]/g, "").slice(0, 2))
                }
                placeholder="01"
                autoComplete="off"
                className="pq-ink-input w-full tabular-nums"
              />
            </div>
          </div>

          {errorMsg && (
            <p id="kis-error" role="alert" className="text-pq-mono-sm text-[#d18888] leading-relaxed">
              {errorMsg}
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              disabled={!canSubmit}
              // 2026-05-15 (bug-hunter Wave 6 P2 #3): the
              // `pq-ink-btn-bronze` class set `cursor: pointer` without
              // a `:disabled { cursor: not-allowed }` selector, so the
              // Tailwind `disabled:cursor-not-allowed` variant lost
              // specificity and the disabled button still showed the
              // pointer cursor. Inline style guarantees not-allowed
              // wins regardless of CSS layer order.
              style={!canSubmit ? { cursor: "not-allowed" } : undefined}
              className="pq-ink-btn-bronze flex-1 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {submitting ? "Connecting…" : "Connect"}
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

        {/* Issuance guide */}
        <details className="group mt-6 pt-5 border-t border-[var(--pq-ivory-line)]">
          <summary className="cursor-pointer list-none text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] hover:text-[var(--pq-bronze-light,var(--pq-bronze))] flex items-center justify-between">
            <span>How to issue KIS API credentials</span>
            <span className="transition-transform group-open:rotate-180" aria-hidden="true">↓</span>
          </summary>
          <ol className="mt-4 space-y-3 text-pq-caption leading-relaxed text-[rgba(245,240,232,0.7)]">
            <li>
              <span className="text-[var(--pq-bronze)] font-serif mr-2">I.</span>
              Visit the KIS OpenAPI portal (apiportal.koreainvestment.com) and sign in with your brokerage account.
            </li>
            <li>
              <span className="text-[var(--pq-bronze)] font-serif mr-2">II.</span>
              Under <span className="text-[var(--pq-ivory)]">API 신청 · Manage Keys</span>, apply for an APP KEY and APP SECRET pair.
              Choose <span className="text-[var(--pq-ivory)]">국내주식 · 해외주식 · 실시간시세</span> (read scope only).
            </li>
            <li>
              <span className="text-[var(--pq-bronze)] font-serif mr-2">III.</span>
              Copy your 8-digit account number in the format{" "}
              <code className="font-mono text-[var(--pq-ivory)] text-pq-mono-sm tabular-nums">12345678-01</code>.
            </li>
            <li>
              <span className="text-[var(--pq-bronze)] font-serif mr-2">IV.</span>
              Paste all three values above. We store them encrypted and never transmit orders.
            </li>
            <li>
              <span className="text-[var(--pq-bronze)] font-serif mr-2">V.</span>
              Click Connect. Your first sync takes ~30 seconds.
            </li>
          </ol>
        </details>

        {/* Disclaimer */}
        <p className="mt-5 pt-4 border-t border-[var(--pq-ivory-line)] text-pq-eyebrow leading-relaxed text-[rgba(245,240,232,0.4)] tracking-[0.05em]">
          KIS integration is read-only. Orders are disabled in this release.
        </p>
      </div>
    </ModalShell>
  );
}
