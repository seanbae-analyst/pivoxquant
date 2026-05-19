import Link from "next/link";
import type { Metadata } from "next";
import {
  ArrowLeft,
  ArrowRight,
  Shield,
} from "lucide-react";
import { Eyebrow } from "@/components/landing/eyebrow";
import { SectionCurtain } from "@/components/landing/section-curtain";

export const metadata: Metadata = {
  title: "7-Layer Risk Defense",
  description:
    "Monitoring downside risk is the other half of return. A seven-layer observation system that surfaces risk concentrations in your portfolio.",
  alternates: { canonical: "/features/risk-defense" },
};

const layers = [
  {
    number: 1,
    code: "VR",
    title: "VaR Monitor",
    question: "How much could I lose today?",
    description:
      "Value at Risk computes your worst-case daily loss at 95% confidence. When VaR moves outside your comfort range, an observation is surfaced so you can review the position before losses compound.",
  },
  {
    number: 2,
    code: "CW",
    title: "Correlation Watch",
    question: "Are all my stocks moving together?",
    description:
      "If holdings rise and fall in lockstep, diversification is an illusion. This layer surfaces an observation when portfolio correlations cross safe thresholds.",
  },
  {
    number: 3,
    code: "VX",
    title: "VIX Shield",
    question: "Is the market scared?",
    description:
      "The VIX measures market fear. When it spikes, this layer surfaces an observation about elevated-fear regimes so you can review your own cash posture.",
  },
  {
    number: 4,
    code: "TR",
    title: "Tail Risk Guard",
    question: "Which stock could hurt me most?",
    description:
      "Identifies the single position contributing the most risk to the book. One outlier can drag the rest with it.",
  },
  {
    number: 5,
    code: "DL",
    title: "Daily Loss Limit",
    question: "Stop the bleeding.",
    description:
      "Sets a hard cap on daily losses. If the portfolio crosses your threshold in a single session, the system halts further trading activity until the next review.",
  },
  {
    number: 6,
    code: "SB",
    title: "Sector Balance",
    question: "Don't put all eggs in one basket.",
    description:
      "Monitors how much of the portfolio sits in any single sector. When technology reaches 50%, an observation is surfaced before concentration compounds.",
  },
  {
    number: 7,
    code: "RR",
    title: "Regime Radar",
    question: "What phase is the market in?",
    description:
      "Markets cycle between bull runs, corrections, and crashes. This layer detects the current regime and adjusts the rest of the dossier accordingly.",
  },
];

export default function RiskDefensePage() {
  return (
    <div className="min-h-screen bg-[var(--pq-ink)] text-[var(--pq-ivory)]">
      {/* ── Header ── */}
      <header className="border-b border-[var(--pq-ivory-line)] bg-[rgba(5,5,5,0.85)] backdrop-blur-xl sticky top-0 z-30">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
          <Link
            href="/#features"
            className="inline-flex items-center gap-1.5 text-sm text-[rgba(245,240,232,0.55)] hover:text-[var(--pq-bronze)] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Link>
          <span className="text-[rgba(245,240,232,0.55)]">/</span>
          <span className="text-sm font-medium text-[var(--pq-ivory)]">Risk Defense</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-20">
        {/* ── Title ── */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-sm bg-[rgba(184,149,106,0.08)] border border-[rgba(184,149,106,0.18)] mb-6">
            <Shield className="w-6 h-6 text-[var(--pq-bronze)]" />
          </div>
          <h1 className="font-[var(--font-display)] italic text-3xl sm:text-4xl font-medium text-[var(--pq-ivory)] mb-4 tracking-tight">
            7-Layer Risk Defense
          </h1>
          <p className="text-base text-[rgba(245,240,232,0.62)] max-w-xl mx-auto">
            Monitoring downside risk is the other half of return.
          </p>
        </div>

        {/* ── The Problem ── */}
        <SectionCurtain divider={false}>
        <section className="mb-16">
          <div className="border-y border-[rgba(245,240,232,0.12)] py-6 sm:py-8">
            <Eyebrow withDashLeft={false} className="mb-3 flex">
              Observation
            </Eyebrow>
            <h2 className="font-[var(--font-serif)] text-lg font-medium text-[var(--pq-ivory)] mb-2">The Problem</h2>
            <p className="text-[rgba(245,240,232,0.82)] leading-relaxed">
              The average investor sells at the worst possible time, surrendering
              4&ndash;8% more than necessary during market drops. Emotion fills the
              vacuum left by a missing observation system.
            </p>
          </div>
        </section>
        </SectionCurtain>

        {/* ── 7 Defense Layers ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-2">Our Solution: 7 Automatic Defense Layers</h2>
          <p className="text-sm text-[rgba(245,240,232,0.62)] mb-8">
            Each layer works independently. Together, they form a comprehensive safety net.
          </p>
          <div className="space-y-4">
            {layers.map((layer, idx) => {
              const ordinal = String(idx + 1).padStart(2, "0");
              return (
                <div
                  key={layer.number}
                  className="rounded-sm border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-5"
                >
                  <div className="flex items-start gap-4">
                    <div className="shrink-0 flex flex-col items-start gap-1">
                      <span className="font-[var(--font-serif)] text-pq-h5 tracking-[0.04em] text-[var(--pq-ivory)]">
                        {layer.code}
                      </span>
                      <span className="font-mono text-pq-eyebrow uppercase tracking-[0.18em] text-[rgba(245,240,232,0.65)] tabular-nums">
                        {ordinal} / 07
                      </span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-pq-eyebrow font-medium uppercase tracking-[0.16em] px-2 py-0.5 border border-[rgba(245,240,232,0.18)] text-[var(--pq-bronze)] rounded-sm">
                          Layer {layer.number}
                        </span>
                        <h3 className="text-base font-semibold text-[var(--pq-ivory)]">{layer.title}</h3>
                      </div>
                      <p className="text-sm text-[rgba(245,240,232,0.62)] italic mb-2">
                        &ldquo;{layer.question}&rdquo;
                      </p>
                      <p className="text-sm text-[rgba(245,240,232,0.82)] leading-relaxed">
                        {layer.description}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
        </SectionCurtain>

        {/* ── Results Comparison (KR convention: indigo down / carmine up) ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-6">Results</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Without */}
            <div className="rounded-sm p-6 bg-[rgba(122,160,200,0.06)] border border-[rgba(122,160,200,0.22)]">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-2 h-2 rounded-full bg-[var(--down)]" />
                <h3 className="text-sm font-semibold text-[var(--down)] tracking-wide uppercase">Without Defense</h3>
              </div>
              <div className="space-y-3">
                <div className="flex justify-between items-baseline">
                  <span className="text-sm text-[rgba(245,240,232,0.62)]">Max Drawdown</span>
                  <span className="text-2xl font-mono font-medium text-[var(--down)] tabular-nums">-20%</span>
                </div>
                <hr className="border-[rgba(122,160,200,0.18)]" />
                <div className="flex justify-between items-baseline">
                  <span className="text-sm text-[rgba(245,240,232,0.62)]">Worst Month</span>
                  <span className="text-2xl font-mono font-medium text-[var(--down)] tabular-nums">-10%</span>
                </div>
              </div>
            </div>

            {/* With */}
            <div className="rounded-sm p-6 bg-[rgba(184,149,106,0.06)] border border-[rgba(184,149,106,0.22)]">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-2 h-2 rounded-full bg-[var(--pq-bronze)]" />
                <h3 className="text-sm font-semibold text-[var(--pq-bronze)] tracking-wide uppercase">With Risk Defense</h3>
              </div>
              <div className="space-y-3">
                <div className="flex justify-between items-baseline">
                  <span className="text-sm text-[rgba(245,240,232,0.62)]">Max Drawdown</span>
                  <span className="text-2xl font-mono font-medium text-[var(--pq-bronze)] tabular-nums">-10%</span>
                </div>
                <hr className="border-[rgba(184,149,106,0.18)]" />
                <div className="flex justify-between items-baseline">
                  <span className="text-sm text-[rgba(245,240,232,0.62)]">Worst Month</span>
                  <span className="text-2xl font-mono font-medium text-[var(--pq-bronze)] tabular-nums">-5%</span>
                </div>
              </div>
            </div>
          </div>
          <p className="text-xs text-[rgba(245,240,232,0.65)] mt-3 text-center">
            Based on backtested data across 6-month market correction periods. Past performance does not guarantee future results.
          </p>
        </section>
        </SectionCurtain>

        {/* ── CTA ── */}
        <SectionCurtain>
        <section className="text-center py-12 px-6 rounded-sm border border-[rgba(184,149,106,0.18)] bg-[rgba(184,149,106,0.04)]">
          <h2 className="font-[var(--font-display)] italic text-2xl font-medium text-[var(--pq-ivory)] mb-3">
            Run a risk simulation today
          </h2>
          <p className="text-[rgba(245,240,232,0.62)] mb-6 max-w-md mx-auto">
            All seven observation layers are active on the free tier. Sign in
            and see your portfolio surfaced through the same lens.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-sm bg-[var(--pq-bronze)] text-[var(--pq-ink)] text-sm font-semibold hover:bg-[var(--pq-bronze-light)] transition-all"
          >
            Run Risk Simulation
            <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
        </SectionCurtain>
      </main>
    </div>
  );
}
