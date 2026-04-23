"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import type { Variants } from "motion/react";
import { ArrowRight, FileText } from "lucide-react";
import FeaturePageShell from "@/components/landing/feature-page-shell";

const EASE = [0.16, 1, 0.3, 1] as const;
const fadeUp: Variants = {
  hidden: { opacity: 0, y: 18 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.55, ease: EASE } },
};
const stagger: Variants = { hidden: {}, visible: { transition: { staggerChildren: 0.08 } } };

const SAMPLES = [
  {
    name: "Weekly Memo",
    subtitle: "Monday briefing · 5 pages",
    excerpt:
      "Realized P&L from the last seven days, position drift, earnings events on your names, dividend calendar. Observation summary — never a recommendation.",
    href: "/samples/weekly_memo.pdf",
  },
  {
    name: "Earnings Pre-Brief",
    subtitle: "Day-before · 6 pages",
    excerpt:
      "Consensus revenue and EPS range, YoY comparisons, four-quarter guidance, business-specific metrics, prior earnings reaction pattern.",
    href: "/samples/earnings_prebrief.pdf",
  },
  {
    name: "Risk Board Deck",
    subtitle: "Board-grade · 12 slides",
    excerpt:
      "Concentration, drawdown history, factor tilts, correlation map, tail clustering, regime badge. The deck a CIO reads before the risk committee.",
    href: "/samples/risk_board.pdf",
  },
  {
    name: "Quarterly Self-Report",
    subtitle: "Own-decisions audit · 10 pages",
    excerpt:
      "Decisions logged during the quarter, position changes with rationale, realized outcomes against entry notes, pattern observations across trades.",
    href: "/samples/quarterly_self_report.pdf",
  },
  {
    name: "Year-End Letter",
    subtitle: "Letter to next year’s self · 14 pages",
    excerpt:
      "Annual P&L recap, decisions that compounded and those that didn’t, patterns drawn from the decision log, observations on style drift.",
    href: "/samples/year_end_letter.pdf",
  },
  {
    name: "Morning Brief Plus",
    subtitle: "Pre-market · 2 pages",
    excerpt:
      "Overnight tape on your names, futures and dollar index snapshot, earnings day-plan for today’s prints, macro cues drawn from the calendar.",
    href: "/samples/morning_brief_plus.pdf",
  },
];

export default function ReportsPage() {
  const reduce = useReducedMotion();
  return (
    <FeaturePageShell
      eyebrow="Research · Sample Reports"
      title="Open a published PDF from the desk."
      deck="Six public samples. Rendered from anonymized composite portfolios. The formatting, cadence, and voice are exactly what members receive on their own holdings."
      seeAlso={[
        { eyebrow: "Catalogue", title: "Feature Explorer", description: "All 17 artifacts, opened one at a time.", href: "/features/explorer" },
        { eyebrow: "Identity", title: "8 CFO Personas", description: "Read the same artifact in each of eight voices.", href: "/features/personas" },
        { eyebrow: "Preview", title: "Dashboard Preview", description: "The terminal that hosts the artifacts.", href: "/features/dashboard" },
      ]}
    >
      <section
        id="sample-reports"
        className="py-20 md:py-28"
        style={{ backgroundColor: "#0A0A0A" }}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={reduce ? undefined : "hidden"}
            whileInView={reduce ? undefined : "visible"}
            viewport={{ once: true, margin: "-60px" }}
            variants={stagger}
            className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3"
          >
            {SAMPLES.map((s) => (
              <motion.article
                key={s.name}
                variants={fadeUp}
                className="group relative flex flex-col gap-4 overflow-hidden rounded-sm p-7 transition-all hover:-translate-y-0.5"
                style={{
                  backgroundColor: "#0D0D0D",
                  border: "0.5px solid rgba(184,149,106,0.25)",
                  minHeight: 280,
                }}
              >
                <span
                  aria-hidden
                  className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-0 transition-opacity duration-500 group-hover:opacity-100"
                  style={{
                    background:
                      "linear-gradient(90deg, transparent 0%, rgba(184,149,106,0.5) 50%, transparent 100%)",
                  }}
                />
                <div className="flex h-9 w-9 items-center justify-center rounded-sm"
                  style={{
                    backgroundColor: "rgba(184,149,106,0.1)",
                    border: "0.5px solid rgba(184,149,106,0.3)",
                    color: "var(--pq-bronze)",
                  }}
                >
                  <FileText className="h-4 w-4" aria-hidden />
                </div>
                <div>
                  <h3
                    className="font-serif"
                    style={{ color: "var(--pq-ivory)", fontSize: "20px", fontWeight: 500, letterSpacing: "-0.01em", marginBottom: 6 }}
                  >
                    {s.name}
                  </h3>
                  <p className="font-serif italic" style={{ color: "rgba(184,149,106,0.85)", fontSize: "12px" }}>
                    {s.subtitle}
                  </p>
                </div>
                <p
                  className="font-serif"
                  style={{ color: "rgba(245,240,232,0.68)", fontSize: "13.5px", lineHeight: 1.6 }}
                >
                  {s.excerpt}
                </p>
                <Link
                  href={s.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-auto inline-flex items-center gap-1.5 font-serif italic"
                  style={{
                    color: "var(--pq-bronze)",
                    fontSize: "12.5px",
                    borderBottom: "0.5px solid rgba(184,149,106,0.4)",
                    alignSelf: "flex-start",
                    paddingBottom: 2,
                  }}
                >
                  Open PDF
                  <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                </Link>
              </motion.article>
            ))}
          </motion.div>
        </div>
      </section>
    </FeaturePageShell>
  );
}
