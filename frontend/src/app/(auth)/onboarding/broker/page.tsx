"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ChevronRight } from "lucide-react";

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
 * Step 0 of the onboarding flow — broker connection. Ink theme.
 *
 * Flow:
 *   /login success → /onboarding/broker (Step 0, optional) → /onboarding (20 Q's)
 *
 * Skip is always allowed; the user can connect a broker later from Settings.
 */
export default function OnboardingBrokerPage() {
  const router = useRouter();
  const t = useT();
  const { user, loading: authLoading } = useAuth();
  const { data, mutate, isLoading } = useBrokerConnections();

  const [kisModalOpen, setKisModalOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  // Legal consent gate
  const [needsLegalConsent, setNeedsLegalConsent] = useState(false);

  useEffect(() => {
    if (!hasLocalConsent()) {
      setNeedsLegalConsent(true);
    }
  }, []);

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
    // Page-load skeleton — Vantablack ink surface matching the broker step
    // header (eyebrow + headline + 2-card grid). Replaces the legacy
    // Loader2 spinner so layout shift on mount is minimal.
    return (
      <div
        className="flex min-h-[100dvh] flex-col px-6 pt-10"
        style={{ backgroundColor: "var(--pq-ink)" }}
        role="status"
        aria-live="polite"
        aria-label="Loading broker connection"
      >
        <div className="mx-auto w-full max-w-3xl flex flex-col gap-4">
          <div className="pq-skeleton-dark h-3 w-32 rounded" />
          <div className="pq-skeleton-dark h-9 w-3/4 rounded" />
          <div className="pq-skeleton-dark h-4 w-2/3 rounded" />
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="pq-skeleton-dark h-56 w-full rounded-sm" />
            <div className="pq-skeleton-dark h-56 w-full rounded-sm" />
          </div>
          <span className="sr-only">Loading broker connection…</span>
        </div>
      </div>
    );
  }

  if (!user) return null;
  if (user.onboarding_completed === true) return null;

  const kisConnected = Boolean(data?.kis_connected);

  return (
    <div className="flex min-h-[100dvh] flex-col bg-[var(--pq-ink)] text-[var(--pq-ivory)]">
      {/* Top bar */}
      <header className="sticky top-0 z-20 border-b border-[var(--pq-ivory-line)] bg-[rgba(10,10,10,0.9)] backdrop-blur-xl px-4 py-3 sm:px-6">
        <div className="mx-auto max-w-3xl">
          <div className="mb-3 flex items-center justify-between">
            <span className="font-serif text-base text-[var(--pq-ivory)]">
              PivoxQuant
            </span>
            <button
              type="button"
              onClick={handleSkip}
              className="text-pq-eyebrow tracking-[0.22em] uppercase text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-ivory)] transition-colors"
            >
              {t("brokerOnboarding.skip")}
            </button>
          </div>

          <div className="mb-3 flex items-center justify-between">
            <span className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
              {t("brokerOnboarding.stepLabel")}
            </span>
            <span className="text-pq-mono-sm tabular-nums text-[rgba(245,240,232,0.5)]">
              0 · 20
            </span>
          </div>
          <div className="relative h-[2px] w-full overflow-hidden bg-[var(--pq-ivory-line)]">
            <div
              className="absolute inset-y-0 left-0"
              style={{
                width: "2%",
                background: "var(--pq-bronze)",
              }}
            />
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto px-4 sm:px-6">
        <div className="mx-auto max-w-3xl py-10">
          <div className="mb-8">
            <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-2">
              Step 0 · Connection
            </div>
            <h1 className="font-serif italic text-3xl text-[var(--pq-ivory)] sm:text-4xl">
              {t("brokerOnboarding.title")}
            </h1>
            <p className="mt-3 text-sm text-[rgba(245,240,232,0.6)] leading-relaxed sm:text-base">
              {t("brokerOnboarding.subtitle")}
            </p>
          </div>

          {isLoading ? (
            // Card-grid skeleton — mirrors the KisCard + ManualCard layout
            // below so the page does not jump when the live data lands.
            <div
              className="grid gap-4 md:grid-cols-2"
              role="status"
              aria-live="polite"
              aria-label="Loading broker connections"
            >
              <div className="pq-skeleton-dark h-56 w-full rounded-sm" />
              <div className="pq-skeleton-dark h-56 w-full rounded-sm" />
              <span className="sr-only">Loading broker connections…</span>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 items-start">
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

          <p className="mt-6 text-pq-mono-sm text-[rgba(245,240,232,0.4)] text-center leading-relaxed">
            {t("brokerOnboarding.note")}
          </p>
        </div>
      </main>

      {/* Footer
          2026-05-17 wave 12 UX P1: pre-fix had two buttons (Next + Skip)
          that did the EXACT same thing — both routed to /onboarding without
          any state change. Users could mistake "Next" for "broker connected,
          proceed". Now: when not connected, label clarifies the action
          ("Continue without broker"); when connected, plain "Continue". */}
      <footer className="sticky bottom-0 z-20 border-t border-[var(--pq-ivory-line)] bg-[rgba(10,10,10,0.9)] backdrop-blur-xl px-4 py-4 sm:px-6">
        <div className="mx-auto flex max-w-3xl items-center justify-end gap-3">
          <button
            type="button"
            onClick={goNext}
            className="pq-ink-btn-bronze inline-flex items-center gap-1"
          >
            {kisConnected
              ? t("brokerOnboarding.nextStep")
              : "브로커 없이 계속하기"}
            <ChevronRight size={14} />
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
