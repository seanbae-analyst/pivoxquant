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
 * Form-based KIS connection modal.
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

  const accountNoValid = /^\d{6,12}$/.test(accountNo);
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
      toast.success(t("brokerOnboarding.kis.connectSuccess"));
      onSuccess?.();
      onClose();
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : t("brokerOnboarding.kis.connectError");
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell onClose={onClose} ariaLabel="KIS 연결">
      <div className="sp-card my-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-md overflow-y-auto p-5 sm:p-6 sm:max-h-[90vh]">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-slate-900">
              {t("brokerOnboarding.kis.modalTitle")}
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              {t("brokerOnboarding.kis.modalSubtitle")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label
              htmlFor="kis-app-key"
              className="block text-xs font-medium text-slate-600 mb-1"
            >
              {t("brokerOnboarding.kis.appKey")}
            </label>
            <input
              id="kis-app-key"
              type="text"
              value={appKey}
              onChange={(e) => setAppKey(e.target.value)}
              placeholder="PSxxxxxxxxxxxxxx..."
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 transition-colors"
            />
          </div>

          <div>
            <label
              htmlFor="kis-app-secret"
              className="block text-xs font-medium text-slate-600 mb-1"
            >
              {t("brokerOnboarding.kis.appSecret")}
            </label>
            <input
              id="kis-app-secret"
              type="password"
              value={appSecret}
              onChange={(e) => setAppSecret(e.target.value)}
              placeholder="••••••••••••••••••••"
              autoComplete="off"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 transition-colors"
            />
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div className="col-span-2">
              <label
                htmlFor="kis-account-no"
                className="block text-xs font-medium text-slate-600 mb-1"
              >
                {t("brokerOnboarding.kis.accountNo")}
              </label>
              <input
                id="kis-account-no"
                type="text"
                inputMode="numeric"
                value={accountNo}
                onChange={(e) =>
                  setAccountNo(e.target.value.replace(/[^0-9]/g, "").slice(0, 12))
                }
                placeholder="XXXXXXXX"
                autoComplete="off"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm tabular-nums text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 transition-colors"
              />
              {accountNo.length > 0 && !accountNoValid && (
                <p className="mt-1 text-[10px] text-red-500">
                  {t("brokerOnboarding.kis.accountNoHint")}
                </p>
              )}
            </div>
            <div>
              <label
                htmlFor="kis-account-prod"
                className="block text-xs font-medium text-slate-600 mb-1"
              >
                {t("brokerOnboarding.kis.accountProd")}
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
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm tabular-nums text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 transition-colors"
              />
            </div>
          </div>

          <a
            href="https://apiportal.koreainvestment.com"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ExternalLink className="h-3 w-3" />
            {t("brokerOnboarding.kis.helpLink")}
          </a>

          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              disabled={!canSubmit}
              className="flex-1 flex items-center justify-center gap-2 rounded-full bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-slate-800 active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {submitting
                ? t("brokerOnboarding.kis.connecting")
                : t("brokerOnboarding.kis.connectBtn")}
            </button>
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t("brokerOnboarding.cancel")}
            </button>
          </div>
        </form>
      </div>
    </ModalShell>
  );
}
