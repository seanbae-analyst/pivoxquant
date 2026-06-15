"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight } from "lucide-react";
import FeaturePageShell from "@/components/landing/feature-page-shell";
import { SectionCurtain } from "@/components/landing/section-curtain";
import { fadeUp } from "@/lib/motion";

const PANES = [
  { code: "01", title: "Equity curve", blurb: "Ten-year observational backtest, re-rendered nightly on your book." },
  { code: "02", title: "Signals ledger", blurb: "POSITIVE · NEGATIVE · NEUTRAL — one row per position, time-stamped." },
  { code: "03", title: "Risk board", blurb: "VaR, ES, tail clustering, concentration, correlation — at a glance." },
  { code: "04", title: "Earnings calendar", blurb: "Upcoming prints, consensus range, day-before brief trigger." },
  { code: "05", title: "Decision log", blurb: "Your own entries, exits, and rationale — the source of the self-audit." },
  { code: "06", title: "Global desk", blurb: "KRW and USD side by side. FX, coverage, dual-market rotation." },
];

export default function DashboardPreviewPage() {
  const reduce = useReducedMotion();
  return (
    <FeaturePageShell
      eyebrow="Preview · The Research Terminal"
      title="Where the artifacts land."
      deck="The dashboard is a reading surface, not a trading console. Six panes, each sourced from the same models that render the PDFs. Nothing to click, nothing to recommend — observation only."
      seeAlso={[
        { eyebrow: "Catalogue", title: "Feature Explorer", description: "Browse all 17 artifacts.", href: "/features/explorer" },
        { eyebrow: "Architecture", title: "40-Model Engine", description: "The stack under every pane.", href: "/features/engine" },
        { eyebrow: "Research", title: "Sample Reports", description: "Read what the panes publish.", href: "/features/reports" },
      ]}
    >
      <SectionCurtain divider={false}>
      <section
        id="dashboard-preview"
        className="py-20 md:py-28"
        style={{ backgroundColor: "#050505" }}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={reduce ? undefined : "hidden"}
            whileInView={reduce ? undefined : "visible"}
            viewport={{ once: true, margin: "-60px" }}
            variants={fadeUp}
            className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3"
          >
            {PANES.map((p) => (
              <article
                key={p.code}
                className="group relative flex flex-col gap-3 overflow-hidden rounded-sm p-7 transition-all hover:-translate-y-0.5"
                style={{
                  backgroundColor: "var(--pq-card-veil)",
                  border: "0.5px solid rgba(184,149,106,0.24)",
                  minHeight: 200,
                }}
              >
                <span
                  className="font-mono uppercase"
                  style={{ color: "var(--pq-bronze)", fontSize: "var(--pq-text-eyebrow)", letterSpacing: "0.24em" }}
                >
                  Pane {p.code}
                </span>
                <h3
                  className="font-serif"
                  style={{ color: "var(--pq-ivory)", fontSize: "var(--pq-text-h4)", fontWeight: 500, letterSpacing: "-0.01em" }}
                >
                  {p.title}
                </h3>
                <p
                  className="font-serif"
                  style={{ color: "rgba(245,240,232,0.68)", fontSize: "var(--pq-text-body)", lineHeight: 1.6 }}
                >
                  {p.blurb}
                </p>

                {/* Mock grid line */}
                <svg
                  aria-hidden
                  viewBox="0 0 300 60"
                  className="mt-auto w-full"
                  preserveAspectRatio="none"
                  style={{ height: 40 }}
                >
                  <defs>
                    <linearGradient id={`g-${p.code}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#B8956A" stopOpacity="0.28" />
                      <stop offset="100%" stopColor="#B8956A" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <path
                    d="M0 50 C40 44, 80 40, 120 32 C160 24, 200 28, 240 20 C260 16, 280 14, 300 10 L300 60 L0 60 Z"
                    fill={`url(#g-${p.code})`}
                  />
                  <path
                    d="M0 50 C40 44, 80 40, 120 32 C160 24, 200 28, 240 20 C260 16, 280 14, 300 10"
                    stroke="#B8956A"
                    strokeWidth="1"
                    fill="none"
                  />
                </svg>
              </article>
            ))}
          </motion.div>

          <div className="mt-12 flex flex-wrap items-center justify-between gap-4">
            <p className="font-serif" style={{ color: "rgba(245,240,232,0.55)", fontSize: "var(--pq-text-body)" }}>
              Live dashboard opens after account creation. Every pane respects your persona.
            </p>
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 rounded-sm px-5 py-3 font-serif transition-colors"
              style={{
                border: "0.5pt solid rgba(184,149,106,0.5)",
                color: "var(--pq-ivory)",
                fontSize: "var(--pq-text-body)",
                letterSpacing: "0.02em",
              }}
            >
              Open the desk
              <ArrowRight className="h-4 w-4" style={{ color: "var(--pq-bronze)" }} aria-hidden />
            </Link>
          </div>
        </div>
      </section>
      </SectionCurtain>
    </FeaturePageShell>
  );
}
