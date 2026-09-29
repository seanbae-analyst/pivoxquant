"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ChevronRight } from "lucide-react";

import { mutate as swrMutate } from "swr";

import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { API, PORTFOLIO_POSITIONS } from "@/lib/endpoints";
import { fetcher, useBrokerConnections, usePortfolioPositions } from "@/lib/hooks";
import { useT } from "@/lib/locale";
import { currentLocationPath, loginHref } from "@/lib/login-redirect";
import { KisCard } from "@/components/broker/kis-card";
import { KisConnectModal } from "@/components/broker/kis-connect-modal";
import { HoldingsImportPanel } from "@/components/portfolio/v2/holdings-import-panel";
import { AddPositionModalV2 } from "@/components/portfolio/v2/add-position-modal-v2";
import { toPosition, type BackendPositionRow } from "@/components/portfolio/types";
import {
  LegalConsentModal,
  hasLocalConsent,
} from "@/components/ui/legal-consent-modal";

/**
 * Step 0 of the onboarding flow — the user's holdings. Ink theme.
 *
 * Flow:
 *   /login success → /onboarding/broker (Step 0, required) → /onboarding (5 Q's)
 *
 * 2026-09-28 CEO — "무조건 포트폴리오 작성하고 가게끔". There is no skip: the
 * product starts from the portfolio the user already holds, so "next" stays
 * disabled until at least one position is saved. Upload is the holdings-screen
 * capture (HoldingsImportPanel); one-at-a-time entry opens the /portfolio
 * add dialog in holding-only mode. The server enforces the same rule
 * (routes/profile.py::submit_onboarding → ONBOARDING_HOLDINGS_REQUIRED).
 */
/**
 * DORMANT since 237a1b67, and unlikely to return in this form.
 *
 * The five KIS connect/sync/disconnect/status routes were deleted for a legal
 * reason, not a technical one: KIS states partnership is unavailable to
 * non-licensed firms, and Toss's Open API terms §5② forbid handing the app key
 * to a third party — the key is an 접근매체 under 전자금융거래법, and §16③ voids
 * the broker's liability once it is shared. Asking a user to paste brokerage
 * credentials asks them to breach their own broker's terms.
 *
 * So this step keeps everything it is still responsible for — the legal consent
 * gate, the progress header, the skip path, manual entry — and stops offering
 * the connection. KisCard and KisConnectModal stay imported and intact; only
 * the offer is withheld.
 */
const BROKER_LINKING_AVAILABLE = false;

export default function OnboardingBrokerPage() {
  const router = useRouter();
  const t = useT();
  const { user, loading: authLoading } = useAuth();
  const { data, mutate, isLoading } = useBrokerConnections();

  const { data: posData } = usePortfolioPositions<{ positions?: BackendPositionRow[] }>();
  const held = (posData?.positions ?? []).map(toPosition);
  const [manualOpen, setManualOpen] = useState(false);
  // Remounts the capture panel after a save so it starts clean for the next batch.
  const [panelKey, setPanelKey] = useState(0);

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
      router.replace(loginHref(currentLocationPath()));
      return;
    }
    if (!authLoading && user?.onboarding_completed === true) {
      router.replace("/mirror");
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

  // Bypass the positions dedupe window so a just-saved holding shows (and
  // unlocks "next") immediately — same approach as /portfolio refreshAll.
  const refreshHeld = useCallback(async () => {
    try {
      swrMutate(PORTFOLIO_POSITIONS, await fetcher(PORTFOLIO_POSITIONS), { revalidate: false });
    } catch {
      swrMutate(PORTFOLIO_POSITIONS);
    }
  }, []);

  const canContinue = held.length > 0;
  const goNext = useCallback(() => {
    if (!canContinue) return;
    router.push("/onboarding");
  }, [router, canContinue]);

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
          </div>

          <div className="mb-3 flex items-center justify-between">
            <span className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
              {t("brokerOnboarding.stepLabel")}
            </span>
            <span className="text-pq-mono-sm tabular-nums text-[var(--pq-ivory-faint)]">
              0 · 5
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
              Step 0 · Holdings
            </div>
            <h1 className="font-serif text-3xl text-[var(--pq-ivory)] sm:text-4xl">
              {t(BROKER_LINKING_AVAILABLE ? "brokerOnboarding.title" : "brokerOnboarding.titleDormant")}
            </h1>
            <p className="mt-3 text-sm text-[rgba(245,240,232,0.6)] leading-relaxed sm:text-base">
              {t(BROKER_LINKING_AVAILABLE ? "brokerOnboarding.subtitle" : "brokerOnboarding.subtitleDormant")}
            </p>
          </div>

          {BROKER_LINKING_AVAILABLE && (isLoading ? (
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
            <div
              className={
                BROKER_LINKING_AVAILABLE
                  ? "grid gap-4 md:grid-cols-2 items-start"
                  : "grid gap-4 items-start"
              }
            >
              {BROKER_LINKING_AVAILABLE && (
                <KisCard
                  connected={kisConnected}
                  onConnect={() => setKisModalOpen(true)}
                  onSync={handleSync}
                  onDisconnect={handleDisconnect}
                  syncing={syncing}
                  disconnecting={disconnecting}
                />
              )}
            </div>
          ))}

          {/* Saved so far — the thing "next" waits on. */}
          <div
            className="mb-6 rounded-[2px] border border-[var(--pq-ivory-line)] px-4 py-3"
            data-testid="onboarding-held"
          >
            <div className="text-pq-mono-sm text-[var(--pq-bronze)]">
              {t("brokerOnboarding.heldCount").replace("{n}", String(held.length))}
            </div>
            <div className="mt-1 text-pq-mono-sm text-[var(--pq-ivory-mid)] [overflow-wrap:anywhere]">
              {held.length > 0
                ? held.map((p) => p.name || p.symbol).join(" · ")
                : t("brokerOnboarding.heldNone")}
            </div>
          </div>

          <div className="rounded-[2px] border border-[var(--pq-ivory-line)] p-4 sm:p-6">
            <HoldingsImportPanel key={panelKey} onDone={() => { void refreshHeld(); setPanelKey((k) => k + 1); }} />
          </div>

          <button
            type="button"
            onClick={() => setManualOpen(true)}
            className="mt-4 w-full text-left text-pq-mono-sm text-[var(--pq-ivory-mid)] underline underline-offset-4 hover:text-[var(--pq-ivory)]"
            data-testid="onboarding-manual"
          >
            {t("brokerOnboarding.manualLink")}
          </button>

          <p className="mt-6 text-pq-mono-sm text-[rgba(245,240,232,0.4)] text-center leading-relaxed">
            {t(BROKER_LINKING_AVAILABLE ? "brokerOnboarding.note" : "brokerOnboarding.noteDormant")}
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
          {!canContinue && (
            <span className="text-pq-mono-sm text-[var(--pq-ivory-faint)]">
              {t("brokerOnboarding.nextLocked")}
            </span>
          )}
          <button
            type="button"
            onClick={goNext}
            disabled={!canContinue}
            aria-disabled={!canContinue}
            className="pq-ink-btn-bronze inline-flex items-center gap-1 disabled:opacity-30 disabled:cursor-not-allowed"
            data-testid="onboarding-next"
          >
            {!BROKER_LINKING_AVAILABLE
              ? t("brokerOnboarding.nextStep")
              : kisConnected
                ? t("brokerOnboarding.nextStep")
                : "브로커 없이 계속하기"}
            <ChevronRight size={14} />
          </button>
        </div>
      </footer>

      <AddPositionModalV2
        open={manualOpen}
        holdingOnly
        onClose={() => setManualOpen(false)}
        onSuccess={() => void refreshHeld()}
      />

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
