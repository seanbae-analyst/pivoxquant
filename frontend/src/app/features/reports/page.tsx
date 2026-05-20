"use client";

import { motion, useReducedMotion } from "motion/react";
import FeaturePageShell from "@/components/landing/feature-page-shell";
import { SectionCurtain } from "@/components/landing/section-curtain";
import ReportFlipCard, {
  type FlipSample,
} from "@/components/landing/report-flip-card";
import { fadeUp, stagger } from "@/lib/motion";
import { WEEKLY_MEMO_WHEN_SHORT } from "@/lib/cfo/memo-schedule";

const SAMPLES: readonly FlipSample[] = [
  {
    name: "Weekly Memo",
    subtitle: "Weekend briefing · 5 pages",
    pageCount: "5 pages",
    cadence: `Delivered ${WEEKLY_MEMO_WHEN_SHORT}`,
    excerpt:
      "Realized P&L from the last seven days, position drift, earnings events on your names, dividend calendar. Observation summary — never a recommendation.",
    href: "/sample-reports/weekly-memo",
    preview: {
      kicker: "Week 16 · Investor Memo",
      heading: "Seven days on the page.",
      lede: "A weekend reading of the Example Portfolio: what compounded, what drifted, and the calendar that matters this week.",
      bullets: [
        "Realized P&L across the week, decomposed by position cohort.",
        "Drift log: holdings that moved outside their entry thesis band.",
        "Earnings and dividend events on names currently held.",
      ],
      closer: "Observation only. No allocation instructions.",
    },
  },
  {
    name: "Earnings Pre-Brief",
    subtitle: "Day-before · 6 pages",
    pageCount: "6 pages",
    cadence: "Eve of print",
    excerpt:
      "Consensus revenue and EPS range, YoY comparisons, four-quarter guidance, business-specific metrics, prior earnings reaction pattern.",
    href: "/sample-reports/earnings-prebrief",
    preview: {
      kicker: "Earnings · Pre-Brief",
      heading: "What the Street expects tomorrow.",
      lede: "Consensus bands, four-quarter guidance cadence, and the reaction pattern from the last eight prints for a held name.",
      bullets: [
        "Revenue and EPS consensus range with standard deviation.",
        "Guidance history: how prior quarters landed vs. guidance given.",
        "Post-print drift window observed across the last eight reports.",
      ],
      closer: "A reading of expectations — not a directional call.",
    },
  },
  {
    name: "Risk Board Deck",
    subtitle: "Board-grade · 12 slides",
    pageCount: "12 slides",
    cadence: "Quarterly board cut",
    excerpt:
      "Concentration, drawdown history, factor tilts, correlation map, tail clustering, regime badge. The deck a CIO reads before the risk committee.",
    href: "/sample-reports/risk-board",
    preview: {
      kicker: "Risk Board · Q2",
      heading: "The deck a committee reads.",
      lede: "Seven defensive layers rendered as a board-grade presentation: concentration, tail, correlation, regime.",
      bullets: [
        "Concentration by position and by sector, with Herfindahl band.",
        "Drawdown history across three lookback windows, annotated.",
        "Correlation map with tail-clustering flags marked for review.",
      ],
      closer: "Formatted to open on a boardroom screen.",
    },
  },
  {
    name: "Quarterly Self-Report",
    subtitle: "Own-decisions audit · 10 pages",
    pageCount: "10 pages",
    cadence: "End of quarter",
    excerpt:
      "Decisions logged during the quarter, position changes with rationale, realized outcomes against entry notes, pattern observations across trades.",
    href: "/sample-reports/quarterly-self-report",
    preview: {
      kicker: "Q-Review · Self-Audit",
      heading: "A quarter of your own decisions.",
      lede: "Every logged decision, traced from rationale at entry to the realized outcome by quarter end.",
      bullets: [
        "Decision log with entry thesis and exit disposition side by side.",
        "Realized outcomes grouped by thesis type for pattern reading.",
        "Style-drift observations against your declared investor profile.",
      ],
      closer: "A mirror held up to three months of your own hand.",
    },
  },
  {
    name: "Year-End Letter",
    subtitle: "Letter to next year's self · 14 pages",
    pageCount: "14 pages",
    cadence: "Delivered January 15",
    excerpt:
      "Annual P&L recap, decisions that compounded and those that didn't, patterns drawn from the decision log, observations on style drift.",
    href: "/sample-reports/year-end-letter",
    preview: {
      kicker: "FY · Annual Letter",
      heading: "A letter to next year's self.",
      lede: "Twelve months compressed into a reflective accounting — what the portfolio did, and a reading of why.",
      bullets: [
        "Annual P&L recap against the year-open allocation baseline.",
        "Decisions that compounded and the ones that cost carry.",
        "Style-drift notes and a calendar for the year ahead.",
      ],
      closer: "Written in the voice of your chosen persona.",
    },
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
        {
          eyebrow: "Catalogue",
          title: "Feature Explorer",
          description: "All 17 artifacts, opened one at a time.",
          href: "/features/explorer",
        },
        {
          eyebrow: "Identity",
          title: "8 CFO Personas",
          description: "Read the same artifact in each of eight voices.",
          href: "/features/personas",
        },
        {
          eyebrow: "Preview",
          title: "Dashboard Preview",
          description: "The terminal that hosts the artifacts.",
          href: "/features/dashboard",
        },
      ]}
    >
      <SectionCurtain divider={false}>
      <section
        id="sample-reports"
        className="py-20 md:py-28"
        style={{ backgroundColor: "#050505" }}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-10 flex items-center justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <span
                aria-hidden
                className="h-px w-7"
                style={{ backgroundColor: "rgba(184,149,106,0.7)" }}
              />
              <span
                className="font-serif uppercase"
                style={{
                  color: "var(--pq-bronze)",
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.22em",
                }}
              >
                Hover · focus · or tap to preview
              </span>
            </div>
            <span
              className="hidden font-serif italic sm:inline"
              style={{
                color: "rgba(245,240,232,0.45)",
                fontSize: "var(--pq-text-eyebrow)",
              }}
            >
              Six samples. Flip a card to read a page.
            </span>
          </div>

          <motion.div
            initial={reduce ? undefined : "hidden"}
            whileInView={reduce ? undefined : "visible"}
            viewport={{ once: true, margin: "-60px" }}
            variants={stagger}
            className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3"
          >
            {SAMPLES.map((s) => (
              <motion.div key={s.name} variants={fadeUp}>
                <ReportFlipCard s={s} />
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>
      </SectionCurtain>
    </FeaturePageShell>
  );
}
