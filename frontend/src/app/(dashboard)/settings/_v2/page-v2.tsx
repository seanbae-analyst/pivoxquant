"use client";

/**
 * /settings v2 — Editorial CFO room · Operational dials.
 *
 * Source of truth: `frontend/design-mockups/settings-v2/{mockup.html, SPEC.md, MIGRATION.md}`.
 * Toggle: `NEXT_PUBLIC_SETTINGS_V2=true`. Default off; v1 remains live.
 *
 * 5 sections (sticky anchor rail):
 *   A · Identity & security      (SettingsIdentityCardV2 + SignInProvidersCard)
 *   B · Brokers · BYOK · RO      (BrokerCardV2 — wraps KisCard v1)
 *   C · Notifications matrix     (NotificationsMatrix + Push/Email sub-cards)
 *   D · Subscription · Stripe    (SubscriptionCardV2)
 *   E · Privacy · PIPA · GDPR    (PrivacyCardV2 — Cookie/Export/Danger zone)
 *
 * Reused (zero-modification imports):
 *   KisCard · KisConnectModal
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
import { EditorialHead, FootSignature } from "@/components/ui/editorial";
import { TopTicker } from "@/components/terminal/top-ticker";
import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";

import { KisCard } from "@/components/broker/kis-card";
import { KisConnectModal } from "@/components/broker/kis-connect-modal";

import { SettingsHeroV2 } from "@/components/settings/v2/settings-hero-v2";
import { AnchorRail } from "@/components/settings/v2/anchor-rail";
import { SettingsIdentityCardV2 } from "@/components/settings/v2/identity-card-v2";
import { SignInProvidersCard } from "@/components/settings/v2/signin-providers-card";
import { CapitalCardV2 } from "@/components/settings/v2/capital-card-v2";
import { BrokerCardV2 } from "@/components/settings/v2/broker-card-v2";
import { NotificationsMatrix } from "@/components/settings/v2/notifications-matrix";
import { MarketingConsentCardV2 } from "@/components/settings/v2/marketing-consent-card";
import { SubscriptionCardV2 } from "@/components/settings/v2/subscription-card-v2";
import { PrivacyCardV2, type CsvDataset } from "@/components/settings/v2/privacy-card-v2";

// 2026-05-17: keys aligned with backend `routes/billing.py:372` which
// actually returns `subscription_tier` / `subscription_status` /
// `has_active_subscription`. The old `tier` / `status` shape never
// matched, so `subData?.tier` always evaluated `undefined`. The
// fallback chain (`user?.subscription_tier || subData?.tier || "free"`)
// silently masked the bug because `user` SWR almost always loads
// first; but in cold-start or a user-SWR error the tier would lock
// to "free" regardless of the real subscription. `tier` / `status`
// kept as optional aliases so any other transitional consumer still
// type-checks until it's swept.
interface SubscriptionResponse {
  subscription_tier?: string;
  subscription_status?: string;
  has_active_subscription?: boolean;
  tier?: string;
  status?: string;
  current_period_end?: string;
  cancel_at_period_end?: boolean;
}

const fetcher = async (url: string): Promise<SubscriptionResponse> => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

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
  // Prefer the canonical backend key (`subscription_tier`) but keep the
  // legacy `tier` alias as a fallback so any half-deployed env doesn't
  // regress mid-rollout. 2026-05-17 — Wave 8 schema alignment.
  const tier = (
    user?.subscription_tier ||
    subData?.subscription_tier ||
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

  const handleKisSync = React.useCallback(async () => {
    setKisSyncing(true);
    try {
      await apiFetch(API.broker.kisSync, { method: "POST" });
      await refreshBrokers();
      toast.success(t("settingsV2.toast.kisSynced"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("settingsV2.toast.kisSyncFailed"));
    } finally {
      setKisSyncing(false);
    }
  }, [refreshBrokers, t]);

  const handleKisDisconnect = React.useCallback(async () => {
    if (typeof window !== "undefined" && !window.confirm(t("settingsV2.toast.kisDisconnectConfirm"))) {
      return;
    }
    setKisDisconnecting(true);
    try {
      await apiFetch(API.broker.kisDisconnect, { method: "DELETE" });
      await refreshBrokers();
      toast.success(t("settingsV2.toast.kisDisconnected"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("settingsV2.toast.kisDisconnectFailed"));
    } finally {
      setKisDisconnecting(false);
    }
  }, [refreshBrokers, t]);

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
        toast.error(t("settingsV2.toast.pushNotSupported"));
        return;
      }
      setPushLoading(true);
      try {
        if (next) {
          const sub = await subscribeToPush();
          if (!sub) {
            toast.error(t("settingsV2.toast.pushPermDenied"));
            setPushEnabled(false);
            return;
          }
          setPushEnabled(true);
          toast.success(t("settingsV2.toast.pushEnabled"));
        } else {
          await unsubscribeFromPush();
          setPushEnabled(false);
          toast.success(t("settingsV2.toast.pushDisabled"));
        }
      } catch {
        toast.error(t("settingsV2.toast.pushError"));
      } finally {
        setPushLoading(false);
      }
    },
    [pushSupported, t],
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
      toast.success(next ? t("settingsV2.toast.emailEnabled") : t("settingsV2.toast.emailDisabled"));
    } catch (err) {
      setEmailEnabled(prev);
      if (typeof window !== "undefined") {
        window.localStorage.setItem("pq_email_delivery", prev ? "1" : "0");
      }
      toast.error(
        err instanceof Error
          ? err.message
          : t("settingsV2.toast.emailSaveFail"),
      );
    } finally {
      setEmailSaving(false);
    }
  }, [emailEnabled, t]);

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
      toast.error(t("settingsV2.toast.billingError"));
    }
  }, [t]);

  // Wave G-1 Bug #7 (2026-05-18): 전자상거래법 §17 (청약철회 행사 방법 명시
  // 의무) — 구독 취소 경로가 UI 에 노출되어야 한다. Stripe Customer Portal
  // 내부에 cancel section 이 있으므로 그쪽으로 redirect. 사용자 confirm 필수.
  const handleCancelPlan = React.useCallback(async () => {
    if (typeof window === "undefined") return;
    const ok = window.confirm(t("settingsV2.toast.cancelConfirm"));
    if (!ok) return;
    // Portal 내부 cancel flow 로 redirect — 별도 cancel endpoint 추가는
    // migration + 환불 처리 책임 분리 필요 (별 PR). 현재는 portal 경유.
    await handleManageBilling();
  }, [handleManageBilling, t]);

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
    toast.error(t("settingsV2.toast.providerDisconnectUnsupported"));
  }, [t]);

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

  /* ── Data export (PIPA §35 — 정보주체 열람권) ── */
  const handleRequestExport = React.useCallback(async () => {
    try {
      // 2026-05-15 (PIPA compliance fix): the comment+fallback above used
      // to say "GAP-X — /api/profile/export not yet declared" and call
      // the agent-data-only endpoint /api/agent/export. But the full
      // PIPA endpoint IS live (routes/profile.py:1172
      // `@profile_bp.route("/export", methods=["GET"])`) and covers
      // positions + watchlist + trades + alerts + consent state — the
      // exact scope privacy-ko.md §7.1 promises to the user. Calling
      // /api/agent/export returned a SUBSET of the data, which would
      // fail the PIPA §35 ① "complete personal data record" gate if
      // anyone ever audited a user's export.
      const data: unknown = await apiFetch(API.profile.export);
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
      toast.success(t("settingsV2.toast.exportReady"));
    } catch {
      toast.error(t("settingsV2.toast.exportFail"));
    }
  }, [t]);

  const handleExportCsv = React.useCallback(
    async (dataset: CsvDataset) => {
      try {
        // CSV is a binary attachment, not JSON — bypass apiFetch (which
        // assumes a JSON body) and stream the blob straight to a download.
        // Same-origin relative path is proxied to the backend by next.config,
        // and credentials:"include" carries the session cookie.
        const res = await fetch(API.profile.exportCsv(dataset), {
          credentials: "include",
        });
        if (!res.ok) {
          throw new Error(`CSV export failed: ${res.status}`);
        }
        // Honour the server-supplied filename
        // (pivoxquant-<dataset>-<date>.csv) when present.
        const disposition = res.headers.get("Content-Disposition") ?? "";
        const match = disposition.match(/filename="([^"]+)"/);
        const filename = match?.[1]
          ?? `pivoxquant-${dataset}-${new Date().toISOString().slice(0, 10)}.csv`;

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        toast.success(t("settingsV2.toast.exportReady"));
      } catch {
        toast.error(t("settingsV2.toast.exportFail"));
      }
    },
    [t],
  );

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
            fontSize: "var(--pq-text-eyebrow)",
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

      {/* LIVING CFO STATUS — sticky hairline.
       * z-10 (2026-05-13 thorough-fix sweep): was z-40, clipped the
       * NotificationDropdown panel by stacking above the TopBar wrapper
       * (z=20 in globals.css). */}
      <div
        className="sticky z-10 -mx-4 md:-ml-8 md:-mr-10 mb-2"
        style={{
          // Pin beneath the TopBar (56px). On notch PWAs the shell adds
          // safe-area-top padding, so the offset must include it or the bar
          // overlaps the TopBar. Token: --pq-aux-sticky-top (globals.css).
          top: "var(--pq-aux-sticky-top)",
          // FINDING-022: solid ink — semi-transparent bar bled scrolled content.
          background: "var(--pq-ink)",
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
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                    marginBottom: 8,
                  }}
                >
                  {t("settingsV2.sectionA.eyebrow")}
                </div>
                <EditorialHead size={30} as="div">
                  {t("settingsV2.sectionA.heading")}
                </EditorialHead>
              </div>
              <a
                href="/profile"
                className="font-mono uppercase"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.18em",
                  color: "var(--pq-bronze)",
                  borderBottom: "1px solid rgba(184,149,106,0.15)",
                  paddingBottom: 2,
                  textDecoration: "none",
                }}
              >
                {t("settingsV2.sectionA.profileLink")}
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
                  toast.success(t("settingsV2.toast.langUpdated"));
                }}
              />
              <SignInProvidersCard
                oauthProvider={user.oauth_provider}
                email={user.email}
                onConnect={handleProviderConnect}
                onDisconnect={handleProviderDisconnect}
              />
            </div>

            {/* A3 · Seed capital (2026-05-20 Wave 5-B feature_preservation
                restore). V1 had this section; V2 lost it during the editorial
                redesign and breaks the contract that no v1 surface disappears.
                Bound to PUT /api/profile/capital via useAuth().refresh(). */}
            <div style={{ marginTop: 12 }}>
              <CapitalCardV2 />
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
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                    marginBottom: 8,
                  }}
                >
                  {t("settingsV2.sectionC.eyebrow")}
                </div>
                <EditorialHead size={30} as="div">
                  {t("settingsV2.sectionC.heading")}{" "}
                  <span
                    style={{
                      color: "var(--pq-bronze)",
                      fontStyle: "italic",
                    }}
                  >
                    {t("settingsV2.sectionC.headingItalic")}
                  </span>
                </EditorialHead>
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
                  border: "1px solid var(--pq-ivory-line)",
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
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.2em",
                    color: "rgba(245,240,232,0.55)",
                  }}
                >
                  {t("settingsV2.push.sectionLabel")}
                </span>
                <div
                  className="font-mono uppercase"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                    marginBottom: 12,
                  }}
                >
                  {t("settingsV2.push.channelLabel")}
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
                        fontSize: "var(--pq-text-body)",
                        color: "var(--pq-ivory)",
                      }}
                    >
                      {t("settingsV2.push.deviceLabel")}
                    </div>
                    <div
                      className="font-serif"
                      style={{
                        fontSize: "var(--pq-text-body)",
                        color: "rgba(245,240,232,0.55)",
                        marginTop: 2,
                      }}
                    >
                      {pushSupported
                        ? pushEnabled
                          ? t("settingsV2.push.granted")
                          : t("settingsV2.push.tap")
                        : t("settingsV2.push.notSupported")}
                    </div>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={pushEnabled}
                    aria-label={t("settingsV2.push.deviceLabel")}
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
                  border: "1px solid var(--pq-ivory-line)",
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
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.2em",
                    color: "rgba(245,240,232,0.55)",
                  }}
                >
                  {t("settingsV2.emailDelivery.sectionLabel")}
                </span>
                <div
                  className="font-mono uppercase"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                    marginBottom: 12,
                  }}
                >
                  {t("settingsV2.emailDelivery.channelLabel")}
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
                        fontSize: "var(--pq-text-body)",
                        color: "var(--pq-ivory)",
                      }}
                    >
                      {t("settingsV2.emailDelivery.sendToLabel")} {user.email ?? ""}
                    </div>
                    <div
                      className="font-serif"
                      style={{
                        fontSize: "var(--pq-text-body)",
                        color: "rgba(245,240,232,0.55)",
                        marginTop: 2,
                      }}
                    >
                      {t("settingsV2.emailDelivery.allArtifacts")}
                    </div>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={emailEnabled}
                    aria-label={t("settingsV2.emailDelivery.channelLabel")}
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
              onCancel={currentTier !== "free" ? handleCancelPlan : undefined}
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
              onExportCsv={handleExportCsv}
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
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.6,
              color: "rgba(245,240,232,0.55)",
            }}
          className="font-serif" >
            <strong
              style={{
                color: "rgba(245,240,232,0.82)",
                fontStyle: "italic",
              }}
            className="font-serif" >
              {t("settingsV2.notice.title")}
            </strong>{" "}
            {t("settingsV2.notice.body")}
          </div>

          {/* FOOT */}
          <div className="mt-2">
            <FootSignature note="PivoxQuant · Settings · Vol. 14 — Seoul" />
          </div>
        </div>
      </main>

      {/* Broker connect modal */}
      {kisModalOpen && (
        <KisConnectModal
          onClose={() => setKisModalOpen(false)}
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
