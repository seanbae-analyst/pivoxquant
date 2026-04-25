"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { DashboardSkeleton } from "@/components/ui/loading-skeleton";
import { PushPermission } from "@/components/pwa/push-permission";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

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

  return (
    <DashboardLayout>
      {children}
      {/*
        Single-source legal disclaimer footer — mounted once for every
        (dashboard) route. Pages that need a contextual variant (signal,
        ai-analysis, coaching, auto-trade) still mount their own
        <DisclaimerBanner /> inline at the relevant section; this layout-level
        instance guarantees the legally-required common notice appears on
        every dashboard page even if a page is added without one.
        Variant: "ai-analysis" — broadest applicability across analytics,
        coaching, settings, growth, and profile surfaces. Theme: dark to
        match the Vantablack dashboard shell (--pq-ink).
      */}
      <div className="px-4 pb-6 md:px-10 md:pb-8">
        <DisclaimerBanner type="ai-analysis" />
      </div>
      <PushPermission />
    </DashboardLayout>
  );
}
