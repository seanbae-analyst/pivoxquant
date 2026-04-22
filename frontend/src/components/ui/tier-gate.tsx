"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Lock } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/locale";
import { cn } from "@/lib/utils";

interface TierGateProps {
  tier: "pro" | "premium";
  children: ReactNode;
  fallback?: ReactNode;
  /** Theme — defaults to dark (Vantablack dashboard). */
  theme?: "dark" | "light";
}

const TIER_LEVEL: Record<string, number> = {
  free: 0,
  pro: 1,
  premium: 2,
};

export function TierGate({ tier, children, fallback, theme = "dark" }: TierGateProps) {
  const { user } = useAuth();
  const t = useT();
  const userTier = user?.subscription_tier || "free";

  if ((TIER_LEVEL[userTier] ?? 0) >= TIER_LEVEL[tier]) {
    return <>{children}</>;
  }

  if (fallback) return <>{fallback}</>;

  const isDark = theme === "dark";

  return (
    <div
      className={cn(
        "p-8 text-center backdrop-blur-[6px]",
        isDark
          ? "rounded-[2px] border border-[rgba(245,240,232,0.12)] bg-[rgba(10,10,10,0.72)]"
          : "rounded-2xl border border-slate-200 bg-slate-50",
      )}
    >
      <div
        className={cn(
          "mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full",
          isDark
            ? "bg-[rgba(139,111,71,0.18)] border border-[rgba(139,111,71,0.35)]"
            : "bg-primary-gradient",
        )}
      >
        <Lock
          className={cn(
            "h-5 w-5",
            isDark ? "text-[var(--pq-bronze-light)]" : "text-white",
          )}
        />
      </div>
      <h3
        className={cn(
          "text-lg font-bold mb-2",
          isDark ? "text-[var(--pq-ivory)]" : "text-slate-900",
        )}
      >
        {tier === "pro" ? t("tierGate.unlockPro") : t("tierGate.unlockPremium")}
      </h3>
      <p
        className={cn(
          "text-sm mb-5",
          isDark ? "text-[rgba(245,240,232,0.6)]" : "text-slate-500",
        )}
      >
        {t("tierGate.upgradeDesc")}
      </p>
      <Link
        href="/pricing"
        className={cn(
          "inline-block px-6 py-2.5 text-sm font-semibold transition-all duration-200 active:scale-[0.97]",
          isDark
            ? "rounded-[2px] bg-[var(--pq-bronze)] text-[var(--pq-ink)] hover:bg-[var(--pq-bronze-light)]"
            : "rounded-full bg-slate-900 text-white hover:bg-slate-800",
        )}
      >
        {t("tierGate.viewPlans")}
      </Link>
    </div>
  );
}
