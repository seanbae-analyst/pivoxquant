"use client";

import { cn, isKoreanTicker } from "@/lib/utils";
import { fmtPct } from "@/lib/format";
import { ArrowLeft, TrendingUp, TrendingDown } from "lucide-react";
import { useRouter } from "next/navigation";
import { Skeleton } from "@/components/ui/loading-skeleton";

interface StockHeaderProps {
  ticker: string;
  name?: string;
  price?: number;
  changePct?: number;
  sector?: string;
  currency?: "USD" | "KRW";
  isKorean?: boolean;
  isLoading?: boolean;
}

export function StockHeader({
  ticker,
  name,
  price,
  changePct,
  sector,
  currency = "USD",
  isKorean,
  isLoading,
}: StockHeaderProps) {
  const router = useRouter();

  if (isLoading) {
    return (
      <div className="flex items-start gap-4">
        <Skeleton className="h-10 w-10 rounded-xl" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-20" />
        </div>
      </div>
    );
  }

  const isPositive = (changePct ?? 0) >= 0;
  const priceDisplay =
    currency === "KRW"
      ? `₩${Math.round(price ?? 0).toLocaleString("ko-KR")}`
      : `$${(price ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <div className="flex items-start gap-4">
      <button
        type="button"
        onClick={() => router.back()}
        className="mt-1 flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-600 transition-colors hover:bg-slate-200"
        aria-label="Go back"
      >
        <ArrowLeft className="h-5 w-5" />
      </button>

      <div className="flex-1 min-w-0">
        {isKoreanTicker(ticker, isKorean) ? (
          <>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-900">{name || ticker}</h1>
              {sector && (
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-500">
                  {sector}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-sm text-slate-500 truncate">
              {ticker} · KRX
            </p>
          </>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-900">{ticker}</h1>
              {sector && (
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-500">
                  {sector}
                </span>
              )}
            </div>
            {name && (
              <p className="mt-0.5 text-sm text-slate-500 truncate">{name}</p>
            )}
          </>
        )}

        <div className="mt-2 flex items-baseline gap-3">
          <span className="text-3xl font-bold text-slate-900 tabular-nums">
            {priceDisplay}
          </span>
          <span
            className={cn(
              "inline-flex items-center gap-1 text-sm font-semibold tabular-nums",
              isPositive ? "text-emerald-600" : "text-red-500",
            )}
          >
            {isPositive ? (
              <TrendingUp className="h-4 w-4" />
            ) : (
              <TrendingDown className="h-4 w-4" />
            )}
            {fmtPct(changePct)}
          </span>
        </div>
      </div>
    </div>
  );
}
