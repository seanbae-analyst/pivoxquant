"use client";

/**
 * ReportsGallery — 18 artifacts gallery section for LandingV2.
 * ---------------------------------------------------------------------------
 * Supanova tone: large whitespace + Pretendard-anchored mono eyebrows + card
 * gallery + cool minimalism. Mirrors the v2 home-card hover pattern (bronze
 * border + bronze-08 background fade).
 *
 * Source of truth: frontend/src/app/(dashboard)/reports/_v1/page-v1.tsx CATALOG
 * (lines 51-70). All 18 artifacts mapped 1:1 — slug, title, cadence, minTier.
 *
 * Legal: observation-only labels. POSITIVE / NEGATIVE / NEUTRAL only. No
 * BUY/SELL/HOLD/recommend/advice copy permitted in card text.
 *
 * Tokens: --pq-ink, --pq-ivory, --pq-bronze, --pq-bronze-rgb,
 *         --pq-text-eyebrow, --pq-track-eyebrow, --pq-hairline-ink.
 * Fonts:  Playfair Display (serif headings) + Source Serif 4 (deck/body)
 *         + JetBrains Mono (eyebrow + tier badge). Pretendard available.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowUpRight } from "lucide-react";

import { Eyebrow } from "./eyebrow";
import { fadeUp, stagger } from "@/lib/motion";

/* ── 18 artifacts mirrored from /reports v1 CATALOG ── */

type Tier = "Free" | "Pro" | "Premium";

interface ReportEntry {
  slug: string;          // matches v1 CATALOG slug
  type: string;          // mono eyebrow label (kind of artifact)
  title: string;         // serif title
  cadence: string;       // serif body
  tier: Tier;            // mono tier badge
}

// Group ordering matches the dashboard catalog: Free → Pro → Premium.
const REPORTS: readonly ReportEntry[] = [
  // — Free (10) —
  { slug: "weekly-memo",           type: "Memo",           title: "Weekly Memo",            cadence: "Every Sunday",          tier: "Free" },
  { slug: "brag-card",             type: "Brag Card",      title: "Brag Card",              cadence: "Monthly",               tier: "Free" },
  { slug: "earnings-prebrief",     type: "Pre-Brief",      title: "Earnings Pre-Brief",     cadence: "On earnings ±24h",      tier: "Pro" },
  { slug: "dd-checklist",          type: "Checklist",      title: "DD Checklist",           cadence: "On demand",             tier: "Pro" },
  { slug: "risk-board",            type: "Risk",           title: "Risk Board",             cadence: "Weekly",                tier: "Pro" },
  { slug: "sp500-backtest",        type: "Backtest",       title: "S&P 500 Backtest",       cadence: "On demand",             tier: "Pro" },
  { slug: "portfolio-segment",     type: "Segment",        title: "Portfolio Segment",      cadence: "Monthly",               tier: "Pro" },
  { slug: "dividend-income",       type: "Income",         title: "Dividend Income",        cadence: "Monthly",               tier: "Pro" },
  { slug: "monthly-finance",       type: "Finance",        title: "Monthly Finance",        cadence: "Monthly",               tier: "Premium" },
  // — Pro (4) —
  { slug: "insider-mirror",        type: "Mirror",         title: "Insider Mirror",         cadence: "Weekly",                tier: "Pro" },
  { slug: "kpi-dashboard",         type: "KPI",            title: "KPI Dashboard",          cadence: "Weekly",                tier: "Premium" },
  { slug: "capital-allocation",    type: "Allocation",     title: "Capital Allocation",     cadence: "Quarterly",             tier: "Premium" },
  { slug: "credit-rating",         type: "Rating",         title: "Credit Rating",          cadence: "Quarterly",             tier: "Premium" },
  // — Premium (4) —
  { slug: "quarterly-self-report", type: "Self-Report",    title: "Quarterly Self Report",  cadence: "Quarterly",             tier: "Pro" },
  { slug: "year-end-letter",       type: "Letter",         title: "Year-End Letter",        cadence: "Annual",                tier: "Premium" },
  { slug: "burn-rate",             type: "Burn",           title: "Burn Rate",              cadence: "Monthly",               tier: "Premium" },
  { slug: "self-audit",            type: "Audit",          title: "Self Audit",             cadence: "On demand",             tier: "Pro" },
] as const;

/* ── Tier badge ── */

function TierBadge({ tier }: { tier: Tier }) {
  return (
    <span
      aria-label={`Tier ${tier}`}
      className="font-mono uppercase"
      style={{
        fontFamily:
          '"JetBrains Mono","SF Mono",ui-monospace,monospace',
        fontSize: "9.5px",
        letterSpacing: "0.22em",
        color: "var(--pq-bronze)",
        border: "0.5px solid rgba(var(--pq-bronze-rgb), 0.45)",
        padding: "3px 8px",
        borderRadius: 999,
        whiteSpace: "nowrap",
      }}
    >
      {tier}
    </span>
  );
}

/* ── Card ── */

function ReportCard({ entry }: { entry: ReportEntry }) {
  return (
    <Link
      href={`/reports/preview/${entry.slug}`}
      aria-label={`${entry.title} — sample preview`}
      className="pq-reports-gallery-card group relative flex flex-col rounded-sm"
      style={{
        backgroundColor: "rgba(255,255,255,0.02)",
        border: "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.08))",
        padding: "26px 24px 22px",
        minHeight: 220,
        textDecoration: "none",
        color: "inherit",
        transition:
          "border-color 240ms cubic-bezier(0.16,1,0.3,1), background-color 240ms cubic-bezier(0.16,1,0.3,1)",
      }}
    >
      {/* eyebrow — mono uppercase 10.5px Bronze */}
      <div className="mb-5 flex items-start justify-between gap-3">
        <span
          className="font-mono uppercase"
          style={{
            fontFamily:
              '"JetBrains Mono","SF Mono",ui-monospace,monospace',
            fontSize: "10.5px",
            letterSpacing: "0.22em",
            color: "var(--pq-bronze)",
          }}
        >
          {entry.type}
        </span>
        <TierBadge tier={entry.tier} />
      </div>

      {/* Title — Playfair 18-22px ivory */}
      <h3
        className="font-serif"
        style={{
          color: "var(--pq-ivory)",
          fontSize: "clamp(18px, 1.6vw, 22px)",
          lineHeight: 1.18,
          letterSpacing: "-0.01em",
          fontWeight: 500,
          marginBottom: 10,
        }}
      >
        {entry.title}
      </h3>

      {/* Cadence — Source Serif 13px ivory-soft */}
      <p
        className="font-serif"
        style={{
          fontFamily: '"Source Serif 4","Source Serif Pro",Georgia,serif',
          color: "rgba(245,240,232,0.6)",
          fontSize: "13px",
          lineHeight: 1.55,
          marginBottom: 22,
        }}
      >
        {entry.cadence}
      </p>

      <span
        className="pq-reports-gallery-card__cta mt-auto inline-flex items-center gap-1.5 font-serif"
        style={{
          color: "var(--pq-bronze)",
          fontSize: "12.5px",
          letterSpacing: "0.04em",
          transition: "color 240ms",
        }}
      >
        Sample preview
        <ArrowUpRight
          className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
          aria-hidden
        />
      </span>
    </Link>
  );
}

/* ── Section ── */

export default function ReportsGallery() {
  const reduce = useReducedMotion();

  return (
    <section
      id="reports-gallery"
      className="relative py-28 md:py-40"
      style={{ backgroundColor: "#050505", color: "var(--pq-ivory)" }}
    >
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        {/* Header block */}
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mb-16 max-w-2xl md:mb-24"
        >
          <Eyebrow className="mb-6">Eighteen Artifacts</Eyebrow>
          <p className="pq-deck mb-4">
            Weekly memos. Quarterly self-reports. Year-end letters.
          </p>
          <h2
            className="pq-silver-matte font-serif"
            style={{
              fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
              lineHeight: 1.08,
              letterSpacing: "-0.02em",
              fontWeight: 500,
              marginBottom: 24,
            }}
          >
            18 artifacts
            <br />
            your CFO publishes.
          </h2>
          <p
            className="font-serif"
            style={{
              fontFamily:
                '"Source Serif 4","Source Serif Pro",Georgia,serif',
              fontSize: "clamp(15px, 1.3vw, 17px)",
              lineHeight: 1.65,
              color: "rgba(245,240,232,0.65)",
              maxWidth: 560,
            }}
          >
            Each one observation only — never advice. Labels are POSITIVE,
            NEGATIVE, or NEUTRAL. Decisions remain with you.
          </p>
        </motion.div>

        {/* Grid: 1 col mobile · 2 col md · 3 col lg → 6 rows × 3 = 18 */}
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
          className="grid grid-cols-1 gap-4 sm:gap-5 md:grid-cols-2 md:gap-5 lg:grid-cols-3 lg:gap-6"
        >
          {REPORTS.map((entry) => (
            <motion.div key={entry.slug} variants={fadeUp}>
              <ReportCard entry={entry} />
            </motion.div>
          ))}
        </motion.div>

        {/* Footnote / link */}
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={fadeUp}
          className="mt-14 flex flex-wrap items-center gap-x-8 gap-y-3 md:mt-20"
        >
          <Link
            href="/features/reports"
            className="group inline-flex items-center gap-2 font-serif transition-colors"
            style={{
              color: "var(--pq-bronze)",
              fontSize: "13.5px",
              letterSpacing: "0.04em",
            }}
          >
            Browse the full library
            <ArrowUpRight
              className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
              aria-hidden
            />
          </Link>
          <span
            className="font-mono uppercase"
            style={{
              fontFamily:
                '"JetBrains Mono","SF Mono",ui-monospace,monospace',
              fontSize: "10px",
              letterSpacing: "0.22em",
              color: "rgba(245,240,232,0.4)",
            }}
          >
            10 Free · 4 Pro · 4 Premium
          </span>
        </motion.div>
      </div>

      {/* Hover styling — mirrors home-card.tsx pattern */}
      <style jsx global>{`
        .pq-reports-gallery-card:hover {
          border-color: var(--pq-bronze) !important;
          background-color: rgba(184, 149, 106, 0.025) !important;
        }
        .pq-reports-gallery-card:hover .pq-reports-gallery-card__cta {
          color: var(--pq-bronze-light, #a3845c) !important;
        }
        @media (prefers-reduced-motion: reduce) {
          .pq-reports-gallery-card {
            transition: none !important;
          }
        }
      `}</style>
    </section>
  );
}
