"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import type { Variants } from "motion/react";
import { ArrowRight, FileText, Lock } from "lucide-react";
import FeaturePageShell from "@/components/landing/feature-page-shell";
import { SectionCurtain } from "@/components/landing/section-curtain";

const EASE = [0.16, 1, 0.3, 1] as const;
const fadeUp: Variants = {
  hidden: { opacity: 0, y: 18 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.55, ease: EASE } },
};
const stagger: Variants = { hidden: {}, visible: { transition: { staggerChildren: 0.04 } } };

// Tier truth: backend `@require_tier` decorators in `routes/artifacts.py` +
// per-service `_PAID_TIERS` constants. AI Suite removed 2026-05-07 — no
// backend service, was a phantom marketing entry. KPI Dashboard added —
// backend has @require_tier("pro") on kpi_dashboard_preview.
const ARTIFACTS = [
  { name: "Weekly Memo", tier: "PRO", tagline: "Monday briefing", format: "5-page PDF · Monday 07:00 KST", sampleUrl: "/sample-reports/weekly-memo" },
  { name: "Earnings Pre-Brief", tier: "PRO", tagline: "Day-before setup", format: "6-page PDF · day before earnings", sampleUrl: "/sample-reports/earnings-prebrief" },
  { name: "Morning Brief Plus", tier: "PRO", tagline: "Pre-market priorities", format: "1-page PDF · daily 07:00 KST", sampleUrl: "/sample-reports/morning-brief-plus" },
  { name: "DD Checklist", tier: "PRO", tagline: "10-K / 10-Q reading aid", format: "Interactive · PDF export", sampleUrl: null },
  { name: "KPI Dashboard", tier: "PRO", tagline: "YTD / Sharpe / MDD snapshot", format: "Monthly · in-app + PDF", sampleUrl: null },
  { name: "Burn Rate", tier: "PRO", tagline: "Cash runway worksheet", format: "In-app · PDF on demand", sampleUrl: null },
  { name: "Credit Rating", tier: "PRO", tagline: "Altman Z + coverage", format: "1-page PDF", sampleUrl: null },
  { name: "Monthly Finance", tier: "PREMIUM", tagline: "Month-in-review ledger", format: "8-page PDF · first of month", sampleUrl: null },
  { name: "Risk Board Deck", tier: "PREMIUM", tagline: "Board-grade risk review", format: "12-slide PDF · weekly", sampleUrl: "/sample-reports/risk-board" },
  { name: "Quarterly Self-Report", tier: "PREMIUM", tagline: "Own-decisions audit", format: "10-page PDF · quarterly", sampleUrl: "/sample-reports/quarterly-self-report" },
  { name: "Year-End Letter", tier: "PREMIUM", tagline: "A letter to next year’s self", format: "14-page PDF · December", sampleUrl: "/sample-reports/year-end-letter" },
  { name: "Capital Allocation", tier: "PREMIUM", tagline: "Allocation what-if", format: "In-app · PDF export", sampleUrl: null },
  { name: "Insider Mirror", tier: "PREMIUM", tagline: "Form 4 · DART feed", format: "Feed · weekly digest", sampleUrl: null },
  { name: "Portfolio Segment", tier: "PREMIUM", tagline: "Sector + region breakdown", format: "4-page PDF · weekly", sampleUrl: null },
  { name: "Dividend Income", tier: "PREMIUM", tagline: "Twelve-month income ledger", format: "6-page PDF · monthly", sampleUrl: null },
  { name: "Self Audit", tier: "PREMIUM", tagline: "Quarterly decision review", format: "8-page PDF · quarterly", sampleUrl: null },
  { name: "Brag Card", tier: "FREE", tagline: "Monthly highlight digest", format: "1-page PDF · monthly", sampleUrl: null },
];

export default function ExplorerPage() {
  const reduce = useReducedMotion();
  return (
    <FeaturePageShell
      eyebrow={`Catalogue · ${ARTIFACTS.length} Artifacts`}
      title="Every artifact, opened one at a time."
      deck="Each artifact is a PDF or an in-app workbook, drawn from your actual holdings. No watchlists to curate. No recommendations."
      seeAlso={[
        { eyebrow: "Architecture", title: "40-Model Engine", description: "The quant, risk, and AI stack.", href: "/features/engine" },
        { eyebrow: "Research", title: "Sample Reports", description: "Open a published PDF from the desk.", href: "/features/reports" },
        { eyebrow: "Preview", title: "Dashboard Preview", description: "Where the artifacts land.", href: "/features/dashboard" },
      ]}
    >
      <SectionCurtain divider={false}>
      <section className="py-20 md:py-28" style={{ backgroundColor: "#050505" }}>
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={reduce ? undefined : "hidden"}
            whileInView={reduce ? undefined : "visible"}
            viewport={{ once: true, margin: "-60px" }}
            variants={stagger}
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
          >
            {ARTIFACTS.map((a, i) => (
              <motion.article
                key={a.name}
                variants={fadeUp}
                className="group relative flex flex-col gap-3 overflow-hidden rounded-sm p-6 transition-all hover:-translate-y-0.5"
                style={{
                  backgroundColor: "#0D0D0D",
                  border: "0.5px solid rgba(184,149,106,0.22)",
                  minHeight: 180,
                }}
              >
                <div className="flex items-center justify-between">
                  <span
                    className="font-mono uppercase"
                    style={{ color: "rgba(184,149,106,0.6)", fontSize: "10px", letterSpacing: "0.22em" }}
                  >
                    {String(i + 1).padStart(2, "0")} / {String(ARTIFACTS.length).padStart(2, "0")}
                  </span>
                  <span
                    className="font-mono uppercase"
                    style={{
                      color: a.tier === "PREMIUM" ? "var(--pq-bronze)" : "rgba(245,240,232,0.5)",
                      fontSize: "12px",
                      letterSpacing: "0.24em",
                      padding: "3px 8px",
                      border: "0.5px solid rgba(184,149,106,0.38)",
                      borderRadius: 999,
                    }}
                  >
                    {a.tier}
                  </span>
                </div>
                <h3
                  className="font-serif"
                  style={{ color: "var(--pq-ivory)", fontSize: "18px", fontWeight: 500, letterSpacing: "-0.01em" }}
                >
                  {a.name}
                </h3>
                <p className="font-serif italic" style={{ color: "rgba(184,149,106,0.8)", fontSize: "13px" }}>
                  {a.tagline}
                </p>
                <p
                  className="font-serif"
                  style={{ color: "rgba(245,240,232,0.55)", fontSize: "14px", lineHeight: 1.5 }}
                >
                  {a.format}
                </p>
                <div className="mt-auto pt-3">
                  {a.sampleUrl ? (
                    <Link
                      href={a.sampleUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 font-serif italic"
                      style={{
                        color: "var(--pq-bronze)",
                        fontSize: "13px",
                        borderBottom: "0.5px solid rgba(184,149,106,0.4)",
                      }}
                    >
                      <FileText className="h-3 w-3" aria-hidden />
                      Open sample PDF
                      <ArrowRight className="h-3 w-3" aria-hidden />
                    </Link>
                  ) : (
                    <span
                      className="inline-flex items-center gap-1.5 font-serif italic"
                      style={{ color: "rgba(245,240,232,0.4)", fontSize: "13px" }}
                    >
                      <Lock className="h-3 w-3" aria-hidden />
                      In-app only
                    </span>
                  )}
                </div>
              </motion.article>
            ))}
          </motion.div>
        </div>
      </section>
      </SectionCurtain>
    </FeaturePageShell>
  );
}
