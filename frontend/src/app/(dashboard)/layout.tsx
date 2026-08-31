"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { DashboardSkeleton } from "@/components/ui/loading-skeleton";
import { PushPermission } from "@/components/pwa/push-permission";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { RealtimeStatusBanner } from "@/components/ui/realtime-status-banner";
import { DataStaleBanner } from "@/components/ui/data-stale-banner";
import {
  clearStagedSnapshot,
  flushPendingCrossBorderConsent,
  flushPendingMarketingConsent,
  readStagedSnapshot,
} from "@/lib/consents";
import { useKeyboardNav } from "@/lib/use-keyboard-nav";

/* ──────────────────────────────────────────────────────────────────
   Path → DisclaimerBanner type resolver

   Single-source legal disclaimer — mounted once per (dashboard) route.
   Pages do NOT mount their own page-level DisclaimerBanner; the layout
   picks the correct legal variant by pathname so each page gets the
   most appropriate copy. Pages MAY still mount a DisclaimerBanner
   inline INSIDE a section (e.g. SWOT box, hero strip) when the
   contextual disclaimer is part of that section's content — those
   are distinct from the page-level footer mounted here.
   ────────────────────────────────────────────────────────────────── */

// REMOVED 2026-04-27 per CEO + legal: "auto-trade" disclaimer kind retired
// alongside the autotrade feature removal (투자일임업 등록 회피).
type DisclaimerKind = "signal" | "coaching" | "behavior-mirror";

/** Longest-prefix matching: more specific paths first. */
const PATH_TO_TYPE: ReadonlyArray<readonly [string, DisclaimerKind]> = [
  // most specific / multi-segment first
  ["/pre-trade", "coaching"],  // behavioural pre-trade surface — educational AI framing, not the default "signal"
  // /journal and /mirror show statistics computed from the user's own trades
  // and holdings, so they take the legally-tuned "behavior-mirror" copy (not a
  // medical / psychological service, not a recommendation). Both pages used to
  // ALSO mount that banner inline; since a collapsed banner shows the common
  // sentence, the user saw the same line twice and the tuned copy stayed
  // hidden. Mounting it once, here, from the path map fixes both.
  ["/journal", "behavior-mirror"],
  ["/mirror", "behavior-mirror"],
  ["/portfolio", "signal"],
  ["/settings", "signal"],
  ["/profile", "signal"],
  ["/mirror", "signal"],
];

/** Routes that need the banner force-expanded (highest-risk surfaces). */
// REMOVED 2026-04-27 per CEO + legal: previously forced /autotrade banner expanded.
const ALWAYS_EXPANDED_PREFIXES: ReadonlyArray<string> = [];

/* ──────────────────────────────────────────────────────────────────
   Auth-guard redirect resolver (F#3, 2026-05-26)

   Pure decision function so the priority order is unit-testable. The
   (dashboard) layout sits OUTSIDE the OAuth-finalize route, so sending an
   unfinalized user to /signup/oauth-finalize cannot loop. Priority:
     1. no user                       → /login
     2. birthdate_required === true   → /signup/oauth-finalize  (PIPA §22)
     3. onboarding_completed === false → /onboarding/broker
   Returns null when the user may stay on the current dashboard route.
   ────────────────────────────────────────────────────────────────── */
type GuardUser = {
  birthdate_required?: boolean;
  onboarding_completed?: boolean;
};

export function nextAuthRedirect(
  user: GuardUser | null | undefined,
): string | null {
  if (!user) return "/login";
  // PIPA §22 minor-protection gate: OAuth provisioned the account but the
  // age/birthdate step is still outstanding. The backend already returns 403
  // on data endpoints; this completes the front-end UX so the user lands on
  // the finalize step instead of a broken-looking dashboard.
  if (user.birthdate_required === true) return "/signup/oauth-finalize";
  if (user.onboarding_completed === false) return "/onboarding/broker";
  return null;
}

function resolveDisclaimerType(pathname: string | null): DisclaimerKind {
  if (!pathname) return "signal";
  for (const [prefix, kind] of PATH_TO_TYPE) {
    if (pathname === prefix || pathname.startsWith(prefix + "/")) return kind;
  }
  return "signal";
}

function shouldAlwaysExpand(pathname: string | null): boolean {
  if (!pathname) return false;
  return ALWAYS_EXPANDED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(p + "/"),
  );
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  // Bug #17 (Wave 3c, fix 2026-05-09): Wires the "G then H/P/W" goto
  // sequences advertised by `ShortcutsModal` (profile-dropdown.tsx).
  // Single mount point — listener guards against editable targets and
  // modifier chords so palette ⌘K and normal typing are unaffected.
  useKeyboardNav();

  useEffect(() => {
    if (loading) return;
    // Single prioritized guard: login → birthdate finalize (PIPA §22) →
    // onboarding broker. Step 0 of onboarding is the broker-connect screen,
    // which then routes into the 20-question wizard.
    const dest = nextAuthRedirect(user);
    if (dest) router.replace(dest);
  }, [user, loading, router]);

  // 정통망법 §50 ① — flush the staged signup-time consent snapshot to the
  // backend the first time we see an authenticated user. The signup gate
  // writes localStorage["pivox_signup_consents"] *before* the OAuth
  // round-trip (when no session exists yet); this is the second leg that
  // promotes the staged record to the server-side audit trail. Helper is
  // idempotent and silent on failure — the user has already cleared the
  // legal gate, and /settings/v2 marketing toggle is the recovery
  // surface if Railway is cold during the flush. Depends on PR #73
  // backend `/api/consents/marketing` POST endpoint.
  useEffect(() => {
    if (!loading && user) {
      // 2026-05-17 Wave F-4 Bug #2 P0 — previously parallel `void` calls
      // caused a deterministic race: flushPendingMarketingConsent cleared
      // localStorage synchronously BEFORE its first await, so the second
      // call read null and exited without ever sending the PIPA §28-8
      // cross-border consent. Now we read the snapshot once, pass it to
      // both flushes, and clear only after both settle.
      void (async () => {
        const snapshot = readStagedSnapshot();
        if (!snapshot) return;
        // Clear the staged snapshot ONLY when both flushes reached their
        // desired end-state (true = sent or nothing-to-send). If either
        // failed (false — e.g. 401 before auth settles, cold backend), keep
        // the snapshot so this effect retries on the next mount instead of
        // silently dropping a consent the user gave at signup.
        const [mkt, xb] = await Promise.allSettled([
          flushPendingMarketingConsent(snapshot),
          flushPendingCrossBorderConsent(snapshot),
        ]);
        const ok = (r: PromiseSettledResult<boolean>) =>
          r.status === "fulfilled" && r.value === true;
        if (ok(mkt) && ok(xb)) {
          clearStagedSnapshot();
        }
      })();
    }
  }, [loading, user]);

  if (loading) {
    return (
      <DashboardLayout>
        <DashboardSkeleton />
      </DashboardLayout>
    );
  }

  if (!user) {
    return null;
  }

  const disclaimerType = resolveDisclaimerType(pathname);
  const alwaysExpanded = shouldAlwaysExpand(pathname);

  return (
    <DashboardLayout>
      {/*
        Realtime SSE connection indicator — mounted at the top of every
        (dashboard) route so users immediately see when the price stream
        is degraded (yellow = reconnecting) or failed (red = stale prices).
        Renders nothing on the happy path. Subscribes only to status
        slice via useRealtimeStatus() so price ticks don't re-render it.
      */}
      <RealtimeStatusBanner />
      {/*
        Upstream vendor-feed stale banner (Wave G C-CS3). Polls
        /api/data/stale-status every 5 min, renders only when the nightly
        ticker_health cron reports an above-threshold stale ratio. Dismiss
        button stores a 1 h LocalStorage cap so the user isn't nagged
        across page changes. Distinct from RealtimeStatusBanner — that one
        is transport-layer (SSE), this one is upstream KIS / FMP feed.
      */}
      <DataStaleBanner />
      {children}
      {/*
        Single-source legal disclaimer footer — mounted once for every
        (dashboard) route, with the variant chosen by pathname.
        Pages MAY mount their own <DisclaimerBanner /> inline INSIDE a
        <section> when the disclaimer is part of that section's content
        (e.g. detail-page SWOT box, hero strip, coaching tools). Those
        contextual instances are intentional and live alongside this
        layout-level footer.
      */}
      <div className="px-4 pb-6 md:px-10 md:pb-8">
        <DisclaimerBanner type={disclaimerType} alwaysExpanded={alwaysExpanded} />
      </div>
      <PushPermission />
    </DashboardLayout>
  );
}
