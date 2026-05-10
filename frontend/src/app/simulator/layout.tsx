"use client";

/**
 * /simulator/* — public layout (no auth).
 *
 * B-12 fix (2026-05-10): the simulator route had no sidebar/topbar
 * because it sits outside the (dashboard) route group. Moving it under
 * (dashboard) would force authentication via (dashboard)/layout.tsx
 * (`router.replace("/login")` for guests) and break the public viral
 * acquisition flow — middleware.ts already lists `/simulator` in
 * BETA_BYPASS_PREFIXES, and what-if/page.tsx documents itself as
 * `Auth: NOT required. Viral acquisition surface.`
 *
 * Instead, mount the auth-agnostic <DashboardLayout> shell here so the
 * simulator inherits the sidebar/topbar chrome WITHOUT the auth gate.
 * The component is the same one (dashboard)/layout.tsx wraps; only the
 * useAuth() redirect is omitted. <DisclaimerBanner /> for "signal" kind
 * is mounted at the foot for the legal compliance baseline.
 */

import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";

export default function SimulatorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <DashboardLayout>
      {children}
      <div className="px-4 pb-6 md:px-10 md:pb-8">
        <DisclaimerBanner type="signal" />
      </div>
    </DashboardLayout>
  );
}
