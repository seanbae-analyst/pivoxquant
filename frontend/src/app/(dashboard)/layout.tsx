"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { DashboardSkeleton } from "@/components/ui/loading-skeleton";
import { PushPermission } from "@/components/pwa/push-permission";

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
      <PushPermission />
    </DashboardLayout>
  );
}
