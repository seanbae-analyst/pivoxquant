"use client";

/**
 * /settings v2 — Editorial CFO room · Operational dials.
 *
 * Source of truth: `frontend/design-mockups/settings-v2/{mockup.html, SPEC.md, MIGRATION.md}`.
 * Toggle: `NEXT_PUBLIC_SETTINGS_V2=true`. Default off; v1 remains live.
 *
 * 5 sections (sticky anchor rail):
 *   A · Identity & security      (SettingsIdentityCardV2 + SignInProvidersCard)
 *   B · Brokers · BYOK · RO      (BrokerCardV2 — wraps AlpacaCard + KisCard v1)
 *   C · Notifications matrix     (NotificationsMatrix + Push/Email sub-cards)
 *   D · Subscription · Stripe    (SubscriptionCardV2)
 *   E · Privacy · PIPA · GDPR    (PrivacyCardV2 — Cookie/Export/Danger zone)
 *
 * Reused (zero-modification imports):
 *   AlpacaCard · AlpacaConnectModal · KisCard · KisConnectModal
 *   ModalShell · TopTicker · LivingCFOStatusBar · FootSignature · ErrorBoundary
 *
 * 11 CEO settings features mapped per MIGRATION §1; 6 GAPs surfaced as UI
 * with graceful fallbacks (mailto / localStorage / "TBD" hint).
 *
 * Legal: persona vocabulary only. POSITIVE / NEGATIVE / NEUTRAL — never BUY/SELL.
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth";
import { useBrokerConnections } from "@/lib/hooks";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { useLocale } from "@/lib/locale";
import {
  isPushSupported,
  subscribeToPush,
  unsubscribeFromPush,
  getPushSubscription,
} from "@/lib/push";

import { ErrorBoundary } from "@/components/ui/error-boundary";
import { FootSignature } from "@/components/ui/editorial";
import { TopTicker } from "@/components/terminal/top-ticker";
import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";

import { AlpacaCard } from "@/components/broker/alpaca-card";
import { AlpacaConnectModal } from "@/components/broker/alpaca-connect-modal";
import { KisCard } from "@/components/broker/kis-card";
import { KisConnectModal } from "@/components/broker/kis-connect-modal";

import { SettingsHeroV2 } from "@/components/settings/v2/settings-hero-v2";
import { AnchorRail } from "@/components/settings/v2/anchor-rail";
import { SettingsIdentityCardV2 } from "@/components/settings/v2/identity-card-v2";
import { SignInProvidersCard } from "@/components/settings/v2/signin-providers-card";
import { BrokerCardV2 } from "@/components/settings/v2/broker-card-v2";
import { NotificationsMatrix } from "@/components/settings/v2/notifications-matrix";
import { MarketingConsentCardV2 } from "@/components/settings/v2/marketing-consent-card";
import { SubscriptionCardV2 } from "@/components/settings/v2/subscription-card-v2";
import { PrivacyCardV2 } from "@/components/settings/v2/privacy-card-v2";

interface SubscriptionResponse {
  tier: string;
  status: string;
  current_period_end?: string;
  cancel_at_period_end?: boolean;
}

const fetcher = async (url: string): Promise<SubscriptionResponse> => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

/**
 * 2026-04-27 (per CEO + legal): Alpaca operates on a Bring-Your-Own-Key
 * (BYOK) model. Each user connects their own Alpaca paper account; we
 * forward read-only requests under the user's own license. Surface gated
 * by NEXT_PUBLIC_ALPACA_ENABLED so the BYO flow can be enabled per-env.
 */
const ALPACA_ENABLED = process.env.NEXT_PUBLIC_ALPACA_ENABLED === "1";

export default function SettingsPageV2() {
  const router = useRouter();
  const { user, loading: authLoading, logout } = useAuth();
  const { locale, setLocale } = useLocale();

  /* ── Subscription ── */
  const { data: subData } = useSWR<SubscriptionResponse>(
    API.billing.subscription,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );
  const tier = (
    user?.subscription_tier ||
    subData?.tier ||
    "free"
  ).toLowerCase();
  const currentTier: "free" | "pro" | "premium" =
    tier === "pro" || tier === "operator"
      ? "pro"
      : tier === "premium" || tier === "partner"
        ? "premium"
        : "free";

  const { t } = useLocale();
  const renewalLine = React.useMemo(() => {
    if (!subData?.current_period_end) return null;
    if (currentTier === "free") return null;
    const d = new Date(subData.current_period_end);
    if (Number.isNaN(d.getTime())) return null;
    const formatted = d.toLocaleDateString(
      locale === "ko" ? "ko-KR" : "en-US",
      { day: "2-digit", month: "short", year: "numeric" },
    );
    return subData.cancel_at_period_end
      ? `${t("settings.subscription.cancelsOn")} ${formatted}`
      : `${t("settings.subscription.renewsOn")} ${formatted}`;
  }, [subData, currentTier, locale, t]);

  /* ── Brokers ── */
  const { data: brokerData, mutate: refreshBrokers } = useBrokerConnections();
  const [kisModalOpen, setKisModalOpen] = React.useState(false);
  const [kisSyncing, setKisSyncing] = React.useState(false);
  const [kisDisconnecting, setKisDisconnecting] = React.useState(false);
  const [alpacaModalOpen, setAlpacaModalOpen] = React.useState(false);
  const [alpacaSyncing, setAlpacaSyncing] = React.useState(false);
  const [alpacaDisconnecting, setAlpacaDisconnecting] = React.useState(false);

  const handleKisSync = React.useCallback(async () => {
    setKisSyncing(true);
    try {
      await apiFetch(API.broker.kisSync, { method: "POST" });
      await refreshBrokers();
      toast.success("KIS synchronized.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sync failed.");
    } finally {
      setKisSyncing(false);
    }
  }, [refreshBrokers]);

  const handleKisDisconnect = React.useCallback(async () => {
    if (typeof window !== "undefined" && !window.confirm("Disconnect KIS?")) {
      return;
    }
    setKisDisconnecting(true);
    try {
      await apiFetch(API.broker.kisDisconnect, { method: "DELETE" });
      await refreshBrokers();
      toast.success("KIS disconnected.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Disconnect failed.");
    } finally {
      setKisDisconnecting(false);
    }
  }, [refreshBrokers]);

  const handleAlpacaSync = React.useCallback(async () => {
    setAlpacaSyncing(true);
    try {
      await apiFetch(API.broker.alpacaSync, { method: "POST" });
      await refreshBrokers();
      toast.success("Alpaca synchronized.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sync failed.");
    } finally {
      setAlpacaSyncing(false);
    }
  }, [refreshBrokers]);

  const handleAlpacaDisconnect = React.useCallback(async () => {
    if (typeof window !== "undefined" && !window.confirm("Disconnect Alpaca?")) {
      return;
    }
    setAlpacaDisconnecting(true);
    try {
      await apiFetch(API.broker.alpacaDisconnect, { method: "DELETE" });
      await refreshBrokers();
      toast.success("Alpaca disconnected.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Disconnect failed.");
    } finally {
      setAlpacaDisconnecting(false);
    }
  }, [refreshBrokers]);

  /* ── Push (C1) ── */
  const [pushEnabled, setPushEnabled] = React.useState(false);
  const [pushSupported, setPushSupported] = React.useState(true);
  const [pushLoading, setPushLoading] = React.useState(false);
  /* C2 email delivery is now backend-truth. `emailEnabled === !email_opt_out`.
     Hydrate from /api/profile on mount so users see their actual server-side
     opt-out state, not a localStorage shadow that drifts. */
  const [emailEnabled, setEmailEnabled] = React.useState(false);
  const [emailSaving, setEmailSaving] = React.useState(false);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const supported = isPushSupported();
    setPushSupported(supported);
    if (supported) {
      getPushSubscription()
        .then((s) => setPushEnabled(!!s))
        .catch(() => setPushEnabled(false));
    }
    /* Optimistic hydration from localStorage for first paint, then
       authoritative hydration from backend. Prefer the new pq_ prefix
       and fall back to the legacy StockPilot-era sp_mb_email key for
       migration. */
    const cached =
      window.localStorage.getItem("pq_email_delivery") ??
      window.localStorage.getItem("sp_mb_email");
    if (cached === "1" || cached === "0") {
      setEmailEnabled(cached === "1");
    }
    apiFetch<{
      profile?: { email_opt_out?: boolean };
      email_opt_out?: boolean;
    }>(API.profile.get)
      .then((data) => {
        const optOut =
          data?.email_opt_out ?? data?.profile?.email_opt_out ?? false;
        setEmailEnabled(!optOut);
      })
      .catch(() => {
        /* Best-effort hydrate; localStorage cache wins on failure. */
      });
  }, []);

  const handlePushToggle = React.useCallback(
    async (next: boolean) => {
      if (!pushSupported) {
        toast.error("Push notifications not supported here.");
        return;
      }
      setPushLoading(true);
      try {
        if (next) {
          const sub = await subscribeToPush();
          if (!sub) {
            toast.error("Permission denied.");
            setPushEnabled(false);
            return;
          }
          setPushEnabled(true);
          toast.success("Push enabled.");
        } else {
          await unsubscribeFromPush();
          setPushEnabled(false);
          toast.success("Push disabled.");
        }
      } catch {
        toast.error("Could not update push.");
      } finally {
        setPushLoading(false);
      }
    },
    [pushSupported],
  );

  const handleEmailToggle = React.useCallback(async (next: boolean) => {
    /* Backend-of-truth wire (Bug-hunter 2026-05-05 HIGH): the V1 settings
       page always called PATCH /api/profile/email-preferences but V2 only
       wrote localStorage — so V2 users toggling "off" still received
       email. 정통망법 §50 + PIPA opt-out compliance requires the server
       to know. Optimistic-update locally, persist via PATCH, rollback on
       failure. */
    const prev = emailEnabled;
    setEmailEnabled(next);
    setEmailSaving(true);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("pq_email_delivery", next ? "1" : "0");
      window.localStorage.removeItem("sp_mb_email"); /* cleanup legacy key */
    }
    try {
      await apiFetch<{
        ok: boolean;
        preferences: { email_opt_out: boolean };
      }>(API.profile.emailPreferences, {
        method: "PATCH",
        body: JSON.stringify({ email_opt_out: !next }),
      });
      toast.success(next ? "Email enabled." : "Email disabled.");
    } catch (err) {
      setEmailEnabled(prev);
      if (typeof window !== "undefined") {
        window.localStorage.setItem("pq_email_delivery", prev ? "1" : "0");
      }
      toast.error(
        err instanceof Error
          ? err.message
          : "Could not save email preference.",
      );
    } finally {
      setEmailSaving(false);
    }
  }, [emailEnabled]);

  /* ── Subscription actions ── */
  const handleManageBilling = React.useCallback(async () => {
    try {
      const r = await apiFetch<{ url: string }>(API.billing.portal, {
        method: "POST",
      });
      if (r.url && typeof window !== "undefined") {
        window.location.href = r.url;
      }
    } catch {
      toast.error("Could not open billing portal.");
    }
  }, []);

  /* ── Sign in providers (GAP-D) ── */
  const handleProviderConnect = React.useCallback(
    (provider: "google" | "kakao") => {
      const target =
        provider === "google" ? API.auth.google : API.auth.kakao;
      if (typeof window !== "undefined") {
        window.location.href = target;
      }
    },
    [],
  );
  const handleProviderDisconnect = React.useCallback(() => {
    // GAP-D: backend disconnect endpoint not present.
    // Surface a graceful TBD toast pointing the user to support; queued for
    // resolution per settings-v2/MIGRATION §2.
    toast.error(
      "Disconnecting an OAuth provider is not yet supported. Email support to remove a provider.",
    );
  }, []);

  /* ── Sign out (E3) ── */
  const [signingOut, setSigningOut] = React.useState(false);
  const handleSignOut = React.useCallback(async () => {
    setSigningOut(true);
    try {
      await logout();
      router.replace("/");
    } catch {
      setSigningOut(false);
    }
  }, [logout, router]);

  /* ── Data export (GAP-X) ── */
  const handleRequestExport = React.useCallback(async () => {
    try {
      // Best-effort: backend `/api/profile/export` not yet declared (GAP-X).
      // Try the agent export endpoint as a graceful fallback so the button is
      // not a dead-end.
      const data: unknown = await apiFetch("/api/agent/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `pivoxquant-export-${new Date()
        .toISOString()
        .slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Export ready.");
    } catch {
      toast.error(
        "Export endpoint coming soon. Email support for a manual archive.",
      );
    }
  }, []);

  /* ── Auth gate ── */
  React.useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  if (authLoading || !user) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <span
          className="font-mono uppercase"
          style={{
            fontSize: 11,
            letterSpacing: "0.22em",
            color: "var(--pq-bronze)",
          }}
        >
          Loading…
        </span>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      {/* TOP TICKER */}
      <div
        className="-mx-4 md:-ml-10 md:-mr-10 mb-4"
        style={{ maxWidth: "100vw" }}
      >
        <TopTicker />
      </div>

      {/* LIVING CFO STATUS — sticky hairline */}
      <div
        className="sticky z-40 -mx-4 md:-ml-8 md:-mr-10 mb-2"
        style={{
          top: 0,
          background: "rgba(5,5,5,0.78)",
          backdropFilter: "blur(6px)",
          WebkitBackdropFilter: "blur(6px)",
        }}
      >
        <LivingCFOStatusBar />
      </div>

      {/* HERO */}
      <SettingsHeroV2 />

      {/* MAIN — sticky rail + 5 sections.
          Mobile fix (2026-05-05): the 12-col grid + 2-col AnchorRail makes
          the rail ~57px wide at 375px — unreadable. Hide the rail entirely
          on mobile (a sticky 2-col label list adds no value when the user
          is already paging through linearly), and let the body span the
          whole row instead of `span 10`. md+ keeps the original layout. */}
      <main
        style={{
          display: "grid",
          gap: 32,
          paddingTop: 48,
        }}
        className="pq-settings-grid grid-cols-1 md:[grid-template-columns:repeat(12,minmax(0,1fr))]"
      >
        <div
          style={{ gridColumn: "span 2" }}
          className="pq-settings-rail hidden md:block"
        >
          <AnchorRail />
        </div>

        <div
          className="pq-settings-body md:[grid-column:span_10]"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 64,
          }}
        >
          {/* SECTION A — Identity & security */}
          <section
            id="section-a"
            style={{ scrollMarginTop: 96 }}
            aria-label="Identity and security"
          >
            <div
              style={{
                display: "flex",
                alignItems: "flex-end",
                justifyContent: "space-between",
                marginBottom: 16,
                flexWrap: "wrap",
                gap: 12,
              }}
            >
              <div>
                <div
                  className="font-mono uppercase"
                  style={{
                    fontFamily:
                      '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                    fontSize: 10.5,
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                    marginBottom: 8,
                  }}
                >
                  A · Identity &amp; security
                </div>
                <div
                  className="font-serif"
                  style={{
                    fontFamily:
                      '"Playfair Display","Source Serif 4",Georgia,serif',
                    fontWeight: 500,
                    fontSize: 30,
                    lineHeight: 1.15,
                    letterSpacing: "-0.02em",
                    color: "var(--pq-ivory)",
                  }}
                >
                  Who is signed in.
                </div>
              </div>
              <a
                href="/profile"
                className="font-mono uppercase"
                style={{
                  fontFamily:
                    '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                  fontSize: 11,
                  letterSpacing: "0.18em",
                  color: "var(--pq-bronze)",
                  borderBottom: "1px solid rgba(184,149,106,0.15)",
                  paddingBottom: 2,
                  textDecoration: "none",
                }}
              >
                Profile detail ›
              </a>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                gap: 12,
              }}
              className="pq-section-a-grid"
            >
              <SettingsIdentityCardV2
                displayName={user.name}
                email={user.email}
                locale={locale}
                onLocaleChange={(next) => {
                  setLocale(next);
                  toast.success("Language updated.");
                }}
              />
              <SignInProvidersCard
                oauthProvider={user.oauth_provider}
                email={user.email}
                onConnect={handleProviderConnect}
                onDisconnect={handleProviderDisconnect}
              />
            </div>
          </section>

          {/* SECTION B — Brokers
              `id="section-b"` anchor required by AnchorRail (2026-04-28 fix).
              Without it, /settings#section-b URL changes but no scroll. */}
          <section
            id="section-b"
            style={{ scrollMarginTop: 96 }}
            aria-label="Brokers"
          >
            <BrokerCardV2
              alpacaSlot={
                ALPACA_ENABLED ? (
                  <AlpacaCard
                    connected={Boolean(brokerData?.alpaca_connected)}
                    mode={brokerData?.alpaca_mode ?? "paper"}
                    lastSync={brokerData?.alpaca_last_sync ?? null}
                    onConnect={() => setAlpacaModalOpen(true)}
                    onSync={handleAlpacaSync}
                    onDisconnect={handleAlpacaDisconnect}
                    syncing={alpacaSyncing}
                    disconnecting={alpacaDisconnecting}
                  />
                ) : (
                  <p
                    className="font-serif"
                    style={{
                      fontFamily:
                        '"Source Serif 4","Iowan Old Style",Georgia,serif',
                      fontSize: 13,
                      color: "rgba(245,240,232,0.55)",
                    }}
                  >
                    Alpaca BYOK is not enabled in this environment.
                  </p>
                )
              }
              kisSlot={
                <KisCard
                  connected={Boolean(brokerData?.kis_connected)}
                  lastSync={brokerData?.kis_last_sync ?? null}
                  onConnect={() => setKisModalOpen(true)}
                  onSync={handleKisSync}
                  onDisconnect={handleKisDisconnect}
                  syncing={kisSyncing}
                  disconnecting={kisDisconnecting}
                />
              }
            />
          </section>

          {/* SECTION C — Notifications */}
          <section
            id="section-c"
            style={{ scrollMarginTop: 96 }}
            aria-label="Notifications"
          >
            <div
              style={{
                display: "flex",
                alignItems: "flex-end",
                justifyContent: "space-between",
                marginBottom: 16,
                flexWrap: "wrap",
                gap: 12,
              }}
            >
              <div>
                <div
                  className="font-mono uppercase"
                  style={{
                    fontFamily:
                      '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                    fontSize: 10.5,
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                    marginBottom: 8,
                  }}
                >
                  C · Notifications · Channels × Events
                </div>
                <div
                  className="font-serif"
                  style={{
                    fontFamily:
                      '"Playfair Display","Source Serif 4",Georgia,serif',
                    fontWeight: 500,
                    fontSize: 30,
                    lineHeight: 1.15,
                    letterSpacing: "-0.02em",
                    color: "var(--pq-ivory)",
                  }}
                >
                  When the CFO{" "}
                  <span
                    style={{
                      color: "var(--pq-bronze)",
                      fontStyle: "italic",
                    }}
                  >
                    should reach you.
                  </span>
                </div>
              </div>
            </div>

            <NotificationsMatrix />

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                gap: 12,
                marginTop: 12,
              }}
              className="pq-section-c-grid"
            >
              {/* C1 · Push device permission */}
              <div
                style={{
                  background: "rgba(255,255,255,0.02)",
                  border: "1px solid rgba(245,240,232,0.08)",
                  borderRadius: 4,
                  padding: 24,
                  position: "relative",
                }}
              >
                <span
                  className="font-mono uppercase"
                  style={{
                    position: "absolute",
                    top: 14,
                    right: 14,
                    fontFamily:
                      '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                    fontSize: 9.5,
                    letterSpacing: "0.2em",
                    color: "rgba(245,240,232,0.40)",
                  }}
                >
                  C1 · Push
                </span>
                <div
                  className="font-mono uppercase"
                  style={{
                    fontFamily:
                      '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                    fontSize: 10.5,
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                    marginBottom: 12,
                  }}
                >
                  Push channel · device permission
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 14,
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div
                      className="font-serif"
                      style={{
                        fontFamily:
                          '"Source Serif 4","Iowan Old Style",Georgia,serif',
                        fontSize: 14,
                        color: "var(--pq-ivory)",
                      }}
                    >
                      Browser push
                    </div>
                    <div
                      className="font-serif"
                      style={{
                        fontFamily:
                          '"Source Serif 4","Iowan Old Style",Georgia,serif',
                        fontSize: 12.5,
                        color: "rgba(245,240,232,0.40)",
                        marginTop: 2,
                      }}
                    >
                      {pushSupported
                        ? pushEnabled
                          ? "Granted on this device."
                          : "Tap to grant device permission."
                        : "Not supported on this device."}
                    </div>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={pushEnabled}
                    aria-label="Browser push"
                    onClick={() => handlePushToggle(!pushEnabled)}
                    disabled={pushLoading || !pushSupported}
                    style={{
                      position: "relative",
                      display: "inline-block",
                      width: 36,
                      height: 20,
                      background: pushEnabled
                        ? "var(--pq-bronze)"
                        : "rgba(245,240,232,0.10)",
                      borderRadius: 999,
                      transition: "background 200ms",
                      flexShrink: 0,
                      border: "none",
                      cursor:
                        pushLoading || !pushSupported
                          ? "not-allowed"
                          : "pointer",
                      opacity: pushLoading || !pushSupported ? 0.4 : 1,
                    }}
                  >
                    <span
                      style={{
                        position: "absolute",
                        top: 3,
                        left: 3,
                        width: 14,
                        height: 14,
                        background: "var(--pq-ivory)",
                        borderRadius: 999,
                        transition: "transform 200ms",
                        transform: pushEnabled
                          ? "translateX(16px)"
                          : "translateX(0)",
                      }}
                    />
                  </button>
                </div>
              </div>

              {/* C2 · Email delivery */}
              <div
                style={{
                  background: "rgba(255,255,255,0.02)",
                  border: "1px solid rgba(245,240,232,0.08)",
                  borderRadius: 4,
                  padding: 24,
                  position: "relative",
                }}
              >
                <span
                  className="font-mono uppercase"
                  style={{
                    position: "absolute",
                    top: 14,
                    right: 14,
                    fontFamily:
                      '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                    fontSize: 9.5,
                    letterSpacing: "0.2em",
                    color: "rgba(245,240,232,0.40)",
                  }}
                >
                  C2 · Email
                </span>
                <div
                  className="font-mono uppercase"
                  style={{
                    fontFamily:
                      '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                    fontSize: 10.5,
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                    marginBottom: 12,
                  }}
                >
                  Email delivery
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 14,
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div
                      className="font-serif"
                      style={{
                        fontFamily:
                          '"Source Serif 4","Iowan Old Style",Georgia,serif',
                        fontSize: 14,
                        color: "var(--pq-ivory)",
                      }}
                    >
                      Send to {user.email ?? "your email"}
                    </div>
                    <div
                      className="font-serif"
                      style={{
                        fontFamily:
                          '"Source Serif 4","Iowan Old Style",Georgia,serif',
                        fontSize: 12.5,
                        color: "rgba(245,240,232,0.40)",
                        marginTop: 2,
                      }}
                    >
                      All artifacts arrive in your inbox as PDF + HTML.
                    </div>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={emailEnabled}
                    aria-label="Email delivery"
                    aria-busy={emailSaving || undefined}
                    disabled={emailSaving}
                    onClick={() => handleEmailToggle(!emailEnabled)}
                    style={{
                      position: "relative",
                      display: "inline-block",
                      width: 36,
                      height: 20,
                      background: emailEnabled
                        ? "var(--pq-bronze)"
                        : "rgba(245,240,232,0.10)",
                      borderRadius: 999,
                      transition: "background 200ms",
                      flexShrink: 0,
                      border: "none",
                      cursor: emailSaving ? "wait" : "pointer",
                      opacity: emailSaving ? 0.6 : 1,
                    }}
                  >
                    <span
                      style={{
                        position: "absolute",
                        top: 3,
                        left: 3,
                        width: 14,
                        height: 14,
                        background: "var(--pq-ivory)",
                        borderRadius: 999,
                        transition: "transform 200ms",
                        transform: emailEnabled
                          ? "translateX(16px)"
                          : "translateX(0)",
                      }}
                    />
                  </button>
                </div>
              </div>
            </div>

            {/* C3 · Marketing-consent record (정통망법 §50 ① · PR #73 backend).
                Sits below the C1/C2 split because the audit-trail surface
                is wider than 2 columns and the timestamp line needs the
                full row for legibility on mobile. */}
            <div style={{ marginTop: 12 }}>
              <MarketingConsentCardV2 />
            </div>
          </section>

          {/* SECTION D — Subscription
              `id="section-d"` anchor required by AnchorRail (2026-04-28 fix). */}
          <section
            id="section-d"
            style={{ scrollMarginTop: 96 }}
            aria-label="Subscription"
          >
            <SubscriptionCardV2
              currentTier={currentTier}
              renewalLine={renewalLine}
              onManageBilling={handleManageBilling}
            />
          </section>

          {/* SECTION E — Privacy
              `id="section-e"` anchor required by AnchorRail (2026-04-28 fix). */}
          <section
            id="section-e"
            style={{ scrollMarginTop: 96 }}
            aria-label="Privacy"
          >
            <PrivacyCardV2
              onRequestExport={handleRequestExport}
              onSignOut={handleSignOut}
              signingOut={signingOut}
            />
          </section>

          {/* DISCLAIMER */}
          <div
            style={{
              marginTop: 32,
              padding: "18px 24px",
              border: "1px dashed rgba(245,240,232,0.14)",
              fontFamily:
                '"Source Serif 4","Iowan Old Style",Georgia,serif',
              fontSize: 12.5,
              lineHeight: 1.6,
              color: "rgba(245,240,232,0.40)",
            }}
          >
            <strong
              style={{
                color: "rgba(245,240,232,0.82)",
                fontFamily:
                  '"Source Serif 4","Iowan Old Style",Georgia,serif',
                fontStyle: "italic",
              }}
            >
              Notice / 면책 고지.
            </strong>{" "}
            PivoxQuant produces editorial memos and analytical artifacts for
            the user&rsquo;s own record-keeping. Brokerage connections are
            read-only — no order routing, no investment advice, no
            recommendation to buy or sell. 본 서비스는 자본시장과 금융투자업에
            관한 법률상의 투자자문업·투자일임업이 아니며, 모든 의사결정과
            책임은 이용자 본인에게 있습니다.
          </div>

          {/* FOOT */}
          <div className="mt-2">
            <FootSignature note="PivoxQuant · Settings · Vol. 14 — Seoul" />
          </div>
        </div>
      </main>

      {/* Broker connect modals */}
      {kisModalOpen && (
        <KisConnectModal
          onClose={() => setKisModalOpen(false)}
          onSuccess={() => refreshBrokers()}
        />
      )}
      {ALPACA_ENABLED && alpacaModalOpen && (
        <AlpacaConnectModal
          onClose={() => setAlpacaModalOpen(false)}
          onSuccess={() => refreshBrokers()}
        />
      )}

      {/* Mobile/tablet collapse */}
      <style jsx>{`
        @media (max-width: 1023px) {
          :global(.pq-settings-grid) {
            grid-template-columns: 1fr !important;
            gap: 16px !important;
          }
          :global(.pq-settings-rail) {
            grid-column: span 12 !important;
            position: static !important;
          }
          :global(.pq-settings-body) {
            grid-column: span 12 !important;
          }
          :global(.pq-section-a-grid),
          :global(.pq-section-c-grid) {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </ErrorBoundary>
  );
}
