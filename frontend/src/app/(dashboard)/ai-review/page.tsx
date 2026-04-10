"use client";

import { useState } from "react";
import {
  Activity,
  BarChart3,
  Brain,
  DollarSign,
  Loader2,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { usePortfolio, useAnalytics } from "@/lib/hooks";

export default function AIReviewPage() {
  const { data: portfolio } = usePortfolio();
  const { data: analytics } = useAnalytics();
  const [review, setReview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generateReview() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{ insight: string; insight_kr: string }>("/api/ai/coaching", {
        method: "POST",
        body: JSON.stringify({ context: "monthly_review" }),
      });
      setReview(res.insight);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate review");
    } finally {
      setLoading(false);
    }
  }

  // Derive stats from hooks
  const totalValue = analytics?.total_value ?? 0;
  const monthlyReturn = analytics?.ann_return_pct
    ? (analytics.ann_return_pct / 12).toFixed(2)
    : "N/A";
  const sharpe = analytics?.sharpe_ratio?.toFixed(2) ?? "N/A";

  const positions = portfolio?.positions ?? [];
  const topPerformer = positions.length
    ? positions.reduce((best, p) => (p.pnl_pct > best.pnl_pct ? p : best), positions[0])
    : null;
  const worstPerformer = positions.length
    ? positions.reduce((worst, p) => (p.pnl_pct < worst.pnl_pct ? p : worst), positions[0])
    : null;

  const stats = [
    {
      label: "Total Value",
      value: `$${totalValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      icon: DollarSign,
      color: "text-sky-600",
    },
    {
      label: "Monthly Return (est.)",
      value: monthlyReturn === "N/A" ? "N/A" : `${monthlyReturn}%`,
      icon: BarChart3,
      color: "text-purple-600",
    },
    {
      label: "Sharpe Ratio",
      value: sharpe,
      icon: Activity,
      color: "text-amber-600",
    },
    {
      label: "Top Performer",
      value: topPerformer
        ? `${topPerformer.ticker} (${topPerformer.pnl_pct >= 0 ? "+" : ""}${topPerformer.pnl_pct.toFixed(1)}%)`
        : "N/A",
      icon: TrendingUp,
      color: "text-emerald-600",
    },
    {
      label: "Worst Performer",
      value: worstPerformer
        ? `${worstPerformer.ticker} (${worstPerformer.pnl_pct >= 0 ? "+" : ""}${worstPerformer.pnl_pct.toFixed(1)}%)`
        : "N/A",
      icon: TrendingDown,
      color: "text-red-600",
    },
  ];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            AI Portfolio Review
          </h1>
          <p className="mt-1 text-[13px] text-slate-400">
            Get an AI-powered monthly review of your portfolio performance and
            actionable insights
          </p>
        </div>
        <Brain className="h-5 w-5 text-purple-600" />
      </div>

      {/* Portfolio Summary Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="glass-surface rounded-xl p-4 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.08)]"
          >
            <div className="flex items-center gap-2">
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
              <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400">
                {stat.label}
              </span>
            </div>
            <p className="mt-2 text-lg font-bold font-mono text-slate-900">{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Generate Button */}
      <div className="flex justify-center">
        <Button
          onClick={generateReview}
          disabled={loading}
          className="h-12 gap-2.5 bg-gradient-to-r from-sky-500/10 to-emerald-500/10 text-sky-600 border border-sky-500/20 rounded-xl spring-transition px-8 text-sm font-semibold disabled:opacity-60"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating Review...
            </>
          ) : (
            <>
              <Brain className="h-4 w-4" />
              Generate Monthly Review
            </>
          )}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-500/20 bg-red-50 p-5 text-center text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Review Content */}
      {review && (
        <div className="glass-surface rounded-xl p-6">
          <div className="mb-4 flex items-center gap-2 text-sm font-medium text-slate-700">
            <Brain className="h-4 w-4 text-purple-600" />
            AI Monthly Review
          </div>
          <div className="space-y-4">
            {review.split("\n").map((paragraph, i) =>
              paragraph.trim() ? (
                <p key={i} className="text-sm leading-relaxed text-slate-700">
                  {paragraph}
                </p>
              ) : null,
            )}
          </div>
        </div>
      )}
    </div>
  );
}
