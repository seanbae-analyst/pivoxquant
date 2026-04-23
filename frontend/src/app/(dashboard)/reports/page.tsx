"use client";

/**
 * /reports — Artifact library in the Vantablack ink theme.
 *
 * Mirrors the 17 artifact types the backend can generate. When a live
 * artifact exists in `useArtifacts()` (the real generation log), we show
 * its sent_at + open/download routes. When it hasn't been generated yet
 * we still render the catalog card with the static `/samples/{name}.pdf`
 * so users can preview the format.
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. DisclaimerBanner at top.
 */

import { useMemo, useState } from "react";
import { FileText, Lock, Download, Eye } from "lucide-react";
import { useArtifacts } from "@/lib/hooks";
import { useAuth } from "@/lib/auth";
import { API } from "@/lib/endpoints";
import { cn } from "@/lib/utils";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  Caption,
  Fleuron,
  FootSignature,
  RuledKicker,
} from "@/components/ui/editorial";
import type { Artifact } from "@/lib/types";
import Link from "next/link";

/* ── Catalog — 17 types + tier gating + sample PDFs ── */

type Tier = "free" | "pro" | "premium";

interface CatalogEntry {
  slug: string;       // file stem under /public/samples
  type: string;       // matches backend `type` when present
  title: string;
  cadence: string;
  minTier: Tier;
}

const CATALOG: CatalogEntry[] = [
  { slug: "weekly_memo",           type: "weekly_memo",          title: "Weekly Memo",             cadence: "Every Sunday",   minTier: "free" },
  { slug: "morning_brief_plus",    type: "morning_brief",        title: "Morning Brief Plus",      cadence: "Every weekday",  minTier: "free" },
  { slug: "brag_card",             type: "monthly_brag",         title: "Brag Card",               cadence: "Monthly",        minTier: "free" },
  { slug: "earnings_prebrief",     type: "earnings_prebrief",    title: "Earnings Pre-Brief",      cadence: "Per event",      minTier: "pro" },
  { slug: "risk_board",            type: "risk_report",          title: "Risk Board",              cadence: "Weekly",         minTier: "pro" },
  { slug: "quarterly_self_report", type: "quarterly_review",     title: "Quarterly Self Report",   cadence: "Quarterly",      minTier: "pro" },
  { slug: "self_audit",            type: "custom",               title: "Self Audit",              cadence: "On demand",      minTier: "pro" },
  { slug: "dd_checklist",          type: "custom",               title: "DD Checklist",            cadence: "On demand",      minTier: "pro" },
  { slug: "dividend_income",       type: "custom",               title: "Dividend Income",         cadence: "Monthly",        minTier: "pro" },
  { slug: "insider_mirror",        type: "custom",               title: "Insider Mirror",          cadence: "Weekly",         minTier: "pro" },
  { slug: "sp500_backtest",        type: "custom",               title: "S&P 500 Backtest",        cadence: "On demand",      minTier: "pro" },
  { slug: "portfolio_segment",     type: "custom",               title: "Portfolio Segment",       cadence: "Monthly",        minTier: "pro" },
  { slug: "capital_allocation",    type: "custom",               title: "Capital Allocation",      cadence: "Quarterly",      minTier: "premium" },
  { slug: "credit_rating",         type: "custom",               title: "Credit Rating",           cadence: "Quarterly",      minTier: "premium" },
  { slug: "burn_rate",             type: "custom",               title: "Burn Rate",               cadence: "Monthly",        minTier: "premium" },
  { slug: "monthly_finance",       type: "custom",               title: "Monthly Finance",         cadence: "Monthly",        minTier: "premium" },
  { slug: "kpi_dashboard",         type: "custom",               title: "KPI Dashboard",           cadence: "Weekly",         minTier: "premium" },
  { slug: "year_end_letter",       type: "custom",               title: "Year-End Letter",         cadence: "Annual",         minTier: "premium" },
];

/* ── Tier gating ── */

const TIER_RANK: Record<Tier, number> = { free: 0, pro: 1, premium: 2 };
function hasAccess(userTier: Tier, required: Tier): boolean {
  return TIER_RANK[userTier] >= TIER_RANK[required];
}

/* ── Card ── */

function ArtifactCard({
  entry,
  live,
  locked,
}: {
  entry: CatalogEntry;
  live?: Artifact;
  locked: boolean;
}) {
  const samplePdf = `/samples/${entry.slug}.pdf`;
  const viewHref = live ? API.artifacts.preview(live.id) : samplePdf;
  const downloadHref = live ? API.artifacts.download(live.id) : samplePdf;

  const lastGenerated =
    live?.sent_at
      ? new Date(live.sent_at).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        })
      : "Sample available";

  return (
    <article
      className={cn(
        "bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 rounded-[2px] relative overflow-hidden transition-colors hover:border-[var(--pq-bronze)]",
        locked && "opacity-60",
      )}
    >
      {/* Locked overlay */}
      {locked && (
        <div className="absolute top-4 right-4">
          <Lock className="h-3.5 w-3.5 text-[var(--pq-bronze)]" />
        </div>
      )}

      <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)] flex items-center gap-2">
        <span aria-hidden="true" style={{ display: "inline-block", width: 16, height: 1, background: "var(--pq-bronze)", opacity: 0.6 }} />
        {entry.cadence} &middot; {entry.minTier}
      </div>
      <h3 className="mt-2 font-serif text-xl text-[var(--pq-ivory)]">
        {entry.title}
      </h3>
      <p className="mt-2 font-serif text-[11.5px] text-[rgba(245,240,232,0.55)]">
        Last generated &mdash; <span className="tabular-nums font-mono">{lastGenerated}</span>
      </p>

      {/* Actions */}
      <div className="mt-5 flex items-center gap-2">
        {locked ? (
          <Link
            href="/pricing"
            className="pq-ink-btn-bronze inline-flex items-center gap-1.5"
          >
            Upgrade to {entry.minTier}
          </Link>
        ) : (
          <>
            <a
              href={viewHref}
              target="_blank"
              rel="noopener noreferrer"
              className="pq-ink-btn-ghost inline-flex items-center gap-1.5"
            >
              <Eye className="h-3.5 w-3.5" />
              Open
            </a>
            <a
              href={downloadHref}
              download
              className="pq-ink-btn-ghost inline-flex items-center gap-1.5"
            >
              <Download className="h-3.5 w-3.5" />
              PDF
            </a>
          </>
        )}
      </div>
    </article>
  );
}

/* ── Page ── */

function ReportsPageInner() {
  const { user } = useAuth();
  const tier = ((user?.subscription_tier as Tier) || "free") as Tier;
  const { artifacts, isLoading } = useArtifacts({ type: "all", since: "all" });
  const [filter, setFilter] = useState<"all" | Tier>("all");

  // Index live artifacts by type for quick lookup
  const liveByType = useMemo(() => {
    const map = new Map<string, Artifact>();
    for (const a of artifacts) {
      if (!map.has(a.type)) map.set(a.type, a); // keep most recent (list is desc)
    }
    return map;
  }, [artifacts]);

  const visible = useMemo(() => {
    if (filter === "all") return CATALOG;
    return CATALOG.filter((c) => c.minTier === filter);
  }, [filter]);

  return (
    <div className="space-y-8">
      {/* ── Header ── */}
      <header>
        <RuledKicker>PDF &middot; Observational archive</RuledKicker>
        <h1 className="mt-2 font-serif text-2xl md:text-3xl text-[var(--pq-ivory)]">
          Reports
        </h1>
        <p className="mt-2 font-serif text-[15px] text-[var(--pq-ivory)] max-w-2xl">
          Every artifact the desk can deliver &mdash; from the weekly memo to the year-end letter.
        </p>
        <Caption className="mt-1 max-w-2xl">
          Free-tier samples are public; Pro and Premium items are generated against your portfolio.
        </Caption>
      </header>

      <DisclaimerBanner type="ai-analysis" />

      {/* ── Tier filter ── */}
      <div className="pq-ink-tabs flex gap-6 border-b border-[rgba(245,240,232,0.08)]">
        {(["all", "free", "pro", "premium"] as const).map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setFilter(k)}
            data-active={filter === k}
            className="pq-ink-tab capitalize"
          >
            {k === "all" ? "All tiers" : k}
          </button>
        ))}
      </div>

      {/* ── Grid ── */}
      {isLoading && artifacts.length === 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-48 rounded-[2px] bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] animate-pulse"
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {visible.map((entry) => (
            <ArtifactCard
              key={entry.slug}
              entry={entry}
              live={liveByType.get(entry.type)}
              locked={!hasAccess(tier, entry.minTier)}
            />
          ))}
        </div>
      )}

      {/* ── Footer note ── */}
      <div className="pt-6 border-t border-[rgba(245,240,232,0.08)] flex items-center gap-2 text-xs text-[rgba(245,240,232,0.4)]">
        <FileText className="h-3.5 w-3.5" />
        {visible.length} artifacts &middot; tier: <span className="text-[var(--pq-bronze)] uppercase tracking-wider">{tier}</span>
      </div>

      {/* Editorial signature */}
      <FootSignature note="PivoxQuant &middot; Observational archive &middot; Not investment advice" />
    </div>
  );
}

export default function ReportsPage() {
  return (
    <ErrorBoundary>
      <ReportsPageInner />
    </ErrorBoundary>
  );
}
