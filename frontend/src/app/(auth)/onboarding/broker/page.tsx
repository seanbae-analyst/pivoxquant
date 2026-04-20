"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ChevronRight, Loader2 } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { useBrokerConnections } from "@/lib/hooks";
import { useT } from "@/lib/locale";
import { KisCard } from "@/components/broker/kis-card";
import { ManualCard } from "@/components/broker/manual-card";
import { KisConnectModal } from "@/components/broker/kis-connect-modal";
import {
  LegalConsentModal,
  hasLocalConsent,
} from "@/components/ui/legal-consent-modal";

/**
 * Step 0 of the onboarding flow — broker connection.
 *
 * Flow:
 *   /login success → /onboarding/broker (Step 0, optional) → /onboarding (20 Q's)
 *
 * Skip is always allowed; the user can connect a broker later from Settings.
 * The 21-step counter keeps visual continuity with the 20-question wizard.
 *
 * 2026-04-20: Simplified to KIS-only. Kiwoom CSV + Alpaca connection flows
 * were removed — US market data still comes from Alpaca Market Data but is
 * not a per-user broker connection.
 */
export default function OnboardingBrokerPage() {
  const router = useRouter();
  const t = useT();
  const { user, loading: authLoading } = useAuth();
  const { data, mutate, isLoading } = useBrokerConnections();

  const [kisModalOpen, setKisModalOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  // Legal consent gate — blocks first-time OAuth users who bypassed the
  // signup consent checkboxes. Initialized false on the server to match SSR,
  // then reconciled on mount.
  const [needsLegalConsent, setNeedsLegalConsent] = useState(false);

  useEffect(() => {
    if (!hasLocalConsent()) {
      setNeedsLegalConsent(true);
    }
  }, []);

  // Redirect unauthenticated visitors to login; send already-onboarded users home.
  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
      return;
    }
    if (!authLoading && user?.onboarding_completed === true) {
      router.replace("/home");
    }
  }, [authLoading, user, router]);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    try {
      await apiFetch(API.broker.kisSync, { method: "POST" });
      await mutate();
      toast.success(t("brokerOnboarding.kis.syncSuccess"));
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : t("brokerOnboarding.kis.syncError");
      toast.error(msg);
    } finally {
      setSyncing(false);
    }
  }, [mutate, t]);

  const handleDisconnect = useCallback(async () => {
    if (!confirm(t("brokerOnboarding.kis.disconnectConfirm"))) return;
    setDisconnecting(true);
    try {
      await apiFetch(API.broker.kisDisconnect, { method: "DELETE" });
      await mutate();
      toast.success(t("brokerOnboarding.kis.disconnectSuccess"));
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : t("brokerOnboarding.kis.disconnectError");
      toast.error(msg);
    } finally {
      setDisconnecting(false);
    }
  }, [mutate, t]);

  const goNext = useCallback(() => {
    router.push("/onboarding");
  }, [router]);

  const handleSkip = useCallback(() => {
    router.push("/onboarding");
  }, [router]);

  if (authLoading) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[#8b5cf6]" />
      </div>
    );
  }

  if (!user) return null;
  if (user.onboarding_completed === true) return null;

  const kisConnected = Boolean(data?.kis_connected);

  return (
    <div className="flex min-h-[100dvh] flex-col bg-white">
      {/* Top bar — mirrors /onboarding header */}
      <header className="sticky top-0 z-20 border-b border-slate-100 bg-white/80 backdrop-blur-xl px-4 py-3 sm:px-6">
        <div className="mx-auto max-w-3xl">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-base font-bold text-slate-900">
              PivoxQuant
            </span>
            <button
              type="button"
              onClick={handleSkip}
              className="text-xs font-medium text-slate-400 transition-colors hover:text-slate-600"
            >
              {t("brokerOnboarding.skip")}
            </button>
          </div>

          {/* Step counter — Step 0 of 21 to keep continuity with 20-question wizard */}
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              {t("brokerOnboarding.stepLabel")}
            </span>
            <span className="text-xs tabular-nums font-medium text-slate-500">
              0 of 21
            </span>
          </div>
          <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="absolute inset-y-0 left-0 rounded-full"
              style={{
                width: "2%",
                background: "linear-gradient(90deg, #8b5cf6, #3b82f6)",
              }}
            />
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto px-4 sm:px-6">
        <div className="mx-auto max-w-3xl py-8">
          <div className="mb-8">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              {t("brokerOnboarding.title")}
            </h1>
            <p className="mt-2 text-sm text-slate-500 sm:text-base">
              {t("brokerOnboarding.subtitle")}
            </p>
          </div>

          {isLoading ? (
            <div className="flex min-h-[240px] items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              <KisCard
                connected={kisConnected}
                onConnect={() => setKisModalOpen(true)}
                onSync={handleSync}
                onDisconnect={handleDisconnect}
                syncing={syncing}
                disconnecting={disconnecting}
              />
              <ManualCard onSelect={goNext} />
            </div>
          )}

          <p className="mt-6 text-xs text-slate-400 text-center">
            {t("brokerOnboarding.note")}
          </p>
        </div>
      </main>

      {/* Footer navigation — optional proceed; connection is not required */}
      <footer className="sticky bottom-0 z-20 border-t border-slate-100 bg-white/80 backdrop-blur-xl px-4 py-4 sm:px-6">
        <div className="mx-auto flex max-w-3xl items-center justify-end gap-3">
          <button
            type="button"
            onClick={goNext}
            className="flex items-center gap-1 rounded-full bg-slate-950 px-7 py-2.5 text-sm font-bold text-white shadow-md transition-all duration-300 hover:bg-slate-800 active:scale-[0.97]"
            style={{ transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)" }}
          >
            {t("brokerOnboarding.nextStep")}
            <ChevronRight size={16} />
          </button>
        </div>
      </footer>

      {kisModalOpen && (
        <KisConnectModal
          onClose={() => setKisModalOpen(false)}
          onSuccess={() => mutate()}
        />
      )}

      {needsLegalConsent && (
        <LegalConsentModal onAgree={() => setNeedsLegalConsent(false)} />
      )}
    </div>
  );
}
