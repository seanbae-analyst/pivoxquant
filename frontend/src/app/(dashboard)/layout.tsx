"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { DashboardSkeleton } from "@/components/ui/loading-skeleton";
import { PushPermission } from "@/components/pwa/push-permission";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";

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

type DisclaimerKind = "signal" | "ai-analysis" | "auto-trade" | "coaching";

/** Longest-prefix matching: more specific paths first. */
const PATH_TO_TYPE: ReadonlyArray<readonly [string, DisclaimerKind]> = [
  // most specific / multi-segment first
  ["/morning-brief", "signal"],
  ["/ai-chat", "ai-analysis"],
  ["/autotrade", "auto-trade"],
  ["/watchlist", "signal"],
  ["/portfolio", "signal"],
  ["/companion", "ai-analysis"],
  ["/discover", "signal"],
  ["/settings", "signal"],
  ["/profile", "signal"],
  ["/reports", "ai-analysis"],
  ["/signals", "signal"],
  ["/alerts", "signal"],
  ["/market", "signal"],
  ["/detail", "signal"],
  ["/growth", "signal"],
  ["/risk", "signal"],
  ["/home", "signal"],
  ["/ai", "ai-analysis"],
];

/** Routes that need the banner force-expanded (highest-risk surfaces). */
const ALWAYS_EXPANDED_PREFIXES: ReadonlyArray<string> = ["/autotrade"];

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

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
    // Redirect to onboarding if the user hasn't completed it.
    // Step 0 is the broker-connect screen, which then routes into the 20-question wizard.
    if (!loading && user && user.onboarding_completed === false) {
      router.replace("/onboarding/broker");
    }
  }, [user, loading, router]);

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
