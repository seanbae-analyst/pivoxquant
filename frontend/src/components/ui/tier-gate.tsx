"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Lock } from "lucide-react";
import { useAuth } from "@/lib/auth";

interface TierGateProps {
  tier: "pro" | "premium";
  children: ReactNode;
  fallback?: ReactNode;
}

const TIER_LEVEL: Record<string, number> = {
  free: 0,
  pro: 1,
  premium: 2,
};

export function TierGate({ tier, children, fallback }: TierGateProps) {
  const { user } = useAuth();
  const userTier = user?.subscription_tier || "free";

  if ((TIER_LEVEL[userTier] ?? 0) >= TIER_LEVEL[tier]) {
    return <>{children}</>;
  }

  return (
    fallback || (
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-8 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary-gradient">
          <Lock className="h-5 w-5 text-white" />
        </div>
        <h3 className="text-lg font-bold text-slate-900 mb-2">
          {tier === "pro" ? "Pro" : "Premium"}로 잠금 해제
        </h3>
        <p className="text-slate-500 text-sm mb-5">
          이 기능을 사용하려면 플랜을 업그레이드하세요.
        </p>
        <Link
          href="/pricing"
          className="inline-block px-6 py-2.5 rounded-full bg-slate-900 text-white text-sm font-semibold transition-all duration-200 hover:bg-slate-800 active:scale-[0.97]"
        >
          요금제 보기
        </Link>
      </div>
    )
  );
}
