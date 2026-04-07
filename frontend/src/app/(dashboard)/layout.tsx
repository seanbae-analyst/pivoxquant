"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Header } from "@/components/layout/header";
import { Sidebar, MobileNav } from "@/components/layout/sidebar";
import { MarketTicker } from "@/components/layout/market-ticker";
import { Logo } from "@/components/ui/logo";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-background">
        <Logo size={48} />
        <div className="mt-4 h-1 w-32 overflow-hidden rounded-full bg-muted">
          <div className="h-full animate-pulse rounded-full bg-primary" style={{ width: "60%" }} />
        </div>
        <span className="mt-3 font-mono text-[10px] tracking-wider text-muted-foreground/50">
          LOADING
        </span>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="flex h-screen flex-col bg-background">
      <Header />
      <MarketTicker />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-4 pb-20 md:p-6 md:pb-6">
          {children}
        </main>
      </div>
      <MobileNav />
    </div>
  );
}
