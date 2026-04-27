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
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  Caption,
  Fleuron,
  FootSignature,
  RuledKicker,
} from "@/components/ui/editorial";
import { SectionFeedbackBar } from "@/components/artifacts/section-feedback";
import { PeerBenchmarkBlock } from "@/components/shared/peer-benchmark-block";
import { usePersona, PERSONA_LABELS, type PersonaId } from "@/lib/cfo/hooks";
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
  /** Personas this artifact is optimised for. `"all"` = persona-agnostic. */
  personas: (PersonaId | "all")[];
}

const CATALOG: CatalogEntry[] = [
  { slug: "weekly_memo",           type: "weekly_memo",          title: "Weekly Memo",             cadence: "Every Sunday",   minTier: "free",    personas: ["all"] },
  { slug: "morning_brief_plus",    type: "morning_brief",        title: "Morning Brief Plus",      cadence: "Every weekday",  minTier: "free",    personas: ["all"] },
  { slug: "brag_card",             type: "monthly_brag",         title: "Brag Card",               cadence: "Monthly",        minTier: "free",    personas: ["all"] },
  { slug: "earnings_prebrief",     type: "earnings_prebrief",    title: "Earnings Pre-Brief",      cadence: "Per event",      minTier: "pro",     personas: ["growth", "quant"] },
  { slug: "risk_board",            type: "risk_report",          title: "Risk Board",              cadence: "Weekly",         minTier: "pro",     personas: ["beginner", "balanced"] },
  { slug: "quarterly_self_report", type: "quarterly_review",     title: "Quarterly Self Report",   cadence: "Quarterly",      minTier: "pro",     personas: ["all"] },
  { slug: "self_audit",            type: "custom",               title: "Self Audit",              cadence: "On demand",      minTier: "pro",     personas: ["all"] },
  { slug: "dd_checklist",          type: "custom",               title: "DD Checklist",            cadence: "On demand",      minTier: "pro",     personas: ["value", "growth"] },
  { slug: "dividend_income",       type: "custom",               title: "Dividend Income",         cadence: "Monthly",        minTier: "pro",     personas: ["income"] },
  { slug: "insider_mirror",        type: "custom",               title: "Insider Mirror",          cadence: "Weekly",         minTier: "pro",     personas: ["value", "growth"] },
  { slug: "sp500_backtest",        type: "custom",               title: "S&P 500 Backtest",        cadence: "On demand",      minTier: "pro",     personas: ["balanced", "beginner"] },
  { slug: "portfolio_segment",     type: "custom",               title: "Portfolio Segment",       cadence: "Monthly",        minTier: "pro",     personas: ["all"] },
  { slug: "capital_allocation",    type: "custom",               title: "Capital Allocation",      cadence: "Quarterly",      minTier: "premium", personas: ["value", "balanced"] },
  { slug: "credit_rating",         type: "custom",               title: "Credit Rating",           cadence: "Quarterly",      minTier: "premium", personas: ["beginner", "income"] },
  { slug: "burn_rate",             type: "custom",               title: "Burn Rate",               cadence: "Monthly",        minTier: "premium", personas: ["growth"] },
  { slug: "monthly_finance",       type: "custom",               title: "Monthly Finance",         cadence: "Monthly",        minTier: "premium", personas: ["all"] },
  { slug: "kpi_dashboard",         type: "custom",               title: "KPI Dashboard",           cadence: "Weekly",         minTier: "premium", personas: ["growth", "quant"] },
  { slug: "year_end_letter",       type: "custom",               title: "Year-End Letter",         cadence: "Annual",         minTier: "premium", personas: ["all"] },
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
  declaredPersona,
}: {
  entry: CatalogEntry;
  live?: Artifact;
  locked: boolean;
  declaredPersona: PersonaId | null;
}) {
  const personaMatch =
    declaredPersona !== null &&
    !entry.personas.includes("all") &&
    entry.personas.includes(declaredPersona);
  // New PDF design system — see design_handoff_pdf_reports/. React preview routes
  // (kebab-cased) live at /reports/preview/{slug}; legacy PDF samples remain in
  // /public/samples/ (underscored) until headless-Chrome rebuild lands.
  const previewRoute = `/reports/preview/${entry.slug.replace(/_/g, "-")}`;
  const samplePdf = `/samples/${entry.slug}.pdf`;
  const viewHref = live ? API.artifacts.preview(live.id) : previewRoute;
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
      {personaMatch && declaredPersona && (
        <p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
          Optimised for {PERSONA_LABELS[declaredPersona]}
        </p>
      )}
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

      {/* Section feedback — wiring Layer 2 learning */}
      {!locked && (
        <div className="mt-4 pt-3 border-t border-[rgba(245,240,232,0.06)]">
          <SectionFeedbackBar
            artifactId={live?.id ? String(live.id) : entry.slug}
            section={entry.slug}
            compact
          />
        </div>
      )}
    </article>
  );
}

/* ── Page ── */

function ReportsPageInner() {
  const { user } = useAuth();
  const tier = ((user?.subscription_tier as Tier) || "free") as Tier;
  const { artifacts, isLoading } = useArtifacts({ type: "all", since: "all" });
  const { data: personaData } = usePersona();
  const declaredPersona = (personaData?.declared?.persona as PersonaId) ?? null;
  const [filter, setFilter] = useState<"all" | Tier>("all");
  const [personaFilter, setPersonaFilter] = useState<"all" | PersonaId>("all");

  // Index live artifacts by type for quick lookup
  const liveByType = useMemo(() => {
    const map = new Map<string, Artifact>();
    for (const a of artifacts) {
      if (!map.has(a.type)) map.set(a.type, a); // keep most recent (list is desc)
    }
    return map;
  }, [artifacts]);

  const visible = useMemo(() => {
    let rows = CATALOG;
    if (filter !== "all") rows = rows.filter((c) => c.minTier === filter);
    if (personaFilter !== "all") {
      rows = rows.filter(
        (c) => c.personas.includes("all") || c.personas.includes(personaFilter),
      );
    }
    return rows;
  }, [filter, personaFilter]);

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

      {/* Legal disclaimer mounted by (dashboard)/layout.tsx (type="ai-analysis") */}

      {/* ── Peer benchmark context ──
           Weekly Memo / Brag Card are persona-aware artifacts. Surfacing the
           anonymized peer-group median here lets the reader see the reference
           point those artifacts quietly compare their trading against —
           without ever leaking an individual record (N >= 20 floor). */}
      {declaredPersona && (
        <PeerBenchmarkBlock
          personaLabel={PERSONA_LABELS[declaredPersona]}
          ownCagr={null}
          ownSharpe={null}
          ownHolding={null}
          windowDays={90}
          kicker="Weekly Memo · peer context · 90-day"
        />
      )}

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

      {/* ── Persona filter — Layer 1 targeting ── */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] uppercase tracking-[0.22em] text-[var(--pq-bronze)] mr-1">
          Persona
        </span>
        {(
          [
            "all",
            "growth",
            "value",
            "balanced",
            "income",
            "quant",
            "beginner",
          ] as const
        ).map((p) => {
          const active = personaFilter === p;
          const label = p === "all" ? "All personas" : PERSONA_LABELS[p];
          return (
            <button
              key={p}
              type="button"
              onClick={() => setPersonaFilter(p)}
              aria-pressed={active}
              className="text-[10.5px] uppercase tracking-[0.18em] px-2.5 py-1 rounded-[2px] border transition-colors"
              style={{
                borderColor: active
                  ? "var(--pq-bronze)"
                  : "rgba(245,240,232,0.1)",
                background: active
                  ? "rgba(139,111,71,0.18)"
                  : "rgba(255,255,255,0.02)",
                color: active ? "var(--pq-ivory)" : "rgba(245,240,232,0.55)",
              }}
            >
              {label}
            </button>
          );
        })}
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
              declaredPersona={declaredPersona}
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
