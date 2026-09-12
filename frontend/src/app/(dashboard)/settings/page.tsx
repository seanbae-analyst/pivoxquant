"use client";

/**
 * /settings v2 — Editorial CFO room · Operational dials.
 *
 * Source of truth: `frontend/design-mockups/settings-v2/{mockup.html, SPEC.md, MIGRATION.md}`.
 * Sole /settings surface — the legacy variant was deleted 2026-08-30.
 *
 * 3 sections (sticky anchor rail):
 *   A · Identity & security      (SettingsIdentityCardV2 + SignInProvidersCard)
 *   B · Notifications            (NotificationsMatrix + Push/Email/Marketing sub-cards)
 *   C · Privacy · PIPA           (PrivacyCardV2 — Consent/Export/Sign out)
 *
 * 2026-09-10 — removed three things that did nothing for a user:
 *   - Brokers: broker linking is not offered, so the section was one
 *     sentence saying so.
 *   - Subscription: billing is off for the free beta. The card listed
 *     "Broker sync" as a Pro perk while this page said linking is not
 *     offered, listed the Mirror as Pro while everyone has it, and gave free
 *     users a "Manage billing" button that called the disabled portal.
 *   - Sign-in "Disconnect": there is no backend endpoint; the button only
 *     toasted "not supported".
 *   - Seed capital moved to /portfolio, next to the holdings it constrains.
 * 2026-09-12 — /profile was decomposed and now 308s here. Section A no longer
 * links out to it; data export and account deletion exist only in section C
 * (PrivacyCardV2 — same /api/profile/export call, same DeleteAccountModal).
 * The element ids (section-a / -c / -e) are kept so existing deep links
 * still land; only the visible letters changed. Bring a section back only
 * together with the thing it controls.
 *
 * Legal: persona vocabulary only. POSITIVE / NEGATIVE / NEUTRAL — never BUY/SELL.
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth";
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
import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";


import { SettingsHeroV2 } from "@/components/settings/v2/settings-hero-v2";
import { AnchorRail } from "@/components/settings/v2/anchor-rail";
import { SettingsIdentityCardV2 } from "@/components/settings/v2/identity-card-v2";
import { SignInProvidersCard } from "@/components/settings/v2/signin-providers-card";
import { NotificationsMatrix } from "@/components/settings/v2/notifications-matrix";
import { MarketingConsentCardV2 } from "@/components/settings/v2/marketing-consent-card";
import { PrivacyCardV2, type CsvDataset } from "@/components/settings/v2/privacy-card-v2";


export default function SettingsPageV2() {
  const router = useRouter();
  const { user, loading: authLoading, logout } = useAuth();
  const { locale, setLocale } = useLocale();

  const { t } = useLocale();

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

  const handleExportXlsx = React.useCallback(async () => {
    try {
      // Multi-sheet Excel workbook — a binary attachment, so bypass apiFetch
      // and stream the blob straight to a download (same pattern as CSV).
      const res = await fetch(API.profile.exportXlsx(), {
        credentials: "include",
      });
      if (!res.ok) {
        throw new Error(`XLSX export failed: ${res.status}`);
      }
      const disposition = res.headers.get("Content-Disposition") ?? "";
      const match = disposition.match(/filename="([^"]+)"/);
      const filename =
        match?.[1] ??
        `pivoxquant-export-${new Date().toISOString().slice(0, 10)}.xlsx`;
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
  }, [t]);

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

      {/* MAIN — sticky rail + 3 sections.
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
              />
            </div>

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
              {/* B1 · Push device permission */}
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
                    color: "var(--pq-ivory-dim)",
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
                        color: "var(--pq-ivory-dim)",
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

              {/* B2 · Email delivery */}
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
                    color: "var(--pq-ivory-dim)",
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
                        color: "var(--pq-ivory-dim)",
                        marginTop: 2,
                      }}
                    >
                      {t("settingsV2.emailDelivery.emailsSent")}
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

            {/* B3 · Marketing-consent record (정통망법 §50 ① · PR #73 backend).
                Sits below the C1/C2 split because the audit-trail surface
                is wider than 2 columns and the timestamp line needs the
                full row for legibility on mobile. */}
            <div style={{ marginTop: 12 }}>
              <MarketingConsentCardV2 />
            </div>
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
              onExportXlsx={handleExportXlsx}
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
              color: "var(--pq-ivory-dim)",
            }}
          className="font-serif" >
            <strong
              style={{
                color: "var(--pq-ivory-strong)",
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
