import Link from "next/link";
import type { Metadata } from "next";
import {
  ArrowLeft,
  ArrowRight,
  Shield,
} from "lucide-react";
import { SectionCurtain } from "@/components/landing/section-curtain";

export const metadata: Metadata = {
  title: "7-Layer Risk Defense — PivoxQuant",
  description:
    "Monitoring downside risk is the other half of return. A seven-layer observation system that surfaces risk concentrations in your portfolio.",
};

/* ── 7 Layers ──
   Editorial pattern: 2-letter abbrev + ledger numbering ("01 / 07"),
   no icon-in-colored-box. Mirrors features/profiles/page.tsx. Action
   verbs neutralized to observation language ("monitor", "surface"). */
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
    <div className="min-h-screen bg-white">
      {/* ── Header ── */}
      <header className="border-b border-slate-100 bg-white/80 backdrop-blur-xl sticky top-0 z-30">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
          <Link
            href="/#features"
            className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Link>
          <span className="text-slate-300">/</span>
          <span className="text-sm font-medium text-slate-700">Risk Defense</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-20">
        {/* ── Title ── */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-accent/10 mb-6">
            <Shield className="w-7 h-7 text-accent" />
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">
            7-Layer <span className="gradient-text">Risk Defense</span>
          </h1>
          <p className="text-lg text-slate-500 max-w-xl mx-auto">
            Monitoring downside risk is the other half of return.
          </p>
        </div>

        {/* ── The Problem ── */}
        <SectionCurtain divider={false}>
        <section className="mb-16">
          {/* Bronze hairline editorial box — replaced earlier amber left-border
              + rounded-2xl pattern (read as AI-generated alert card). The
              hairline + small-caps eyebrow keeps the editorial register and
              removes the colored bubble cue. */}
          <div className="border-y border-slate-200 py-6 sm:py-8">
            <div className="text-[10.5px] uppercase tracking-[0.22em] text-slate-400 mb-3">
              Observation
            </div>
            <h2 className="text-lg font-bold text-slate-900 mb-2">The Problem</h2>
            <p className="text-slate-600 leading-relaxed">
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
          <h2 className="text-xl font-bold text-slate-900 mb-2">Our Solution: 7 Automatic Defense Layers</h2>
          <p className="text-sm text-slate-500 mb-8">
            Each layer works independently. Together, they form a comprehensive safety net.
          </p>
          <div className="space-y-4">
            {layers.map((layer, idx) => {
              const ordinal = String(idx + 1).padStart(2, "0");
              return (
                <div
                  key={layer.number}
                  className="rounded-sm border border-slate-200 bg-white p-5"
                >
                  <div className="flex items-start gap-4">
                    <div className="shrink-0 flex flex-col items-start gap-1">
                      <span
                        className="font-serif text-[18px] tracking-[0.04em] text-slate-900"
                        style={{ letterSpacing: "0.04em" }}
                      >
                        {layer.code}
                      </span>
                      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-400 tabular-nums">
                        {ordinal} / 07
                      </span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-[10px] font-semibold uppercase tracking-[0.16em] px-2 py-0.5 border border-slate-200 text-slate-500 rounded-sm">
                          Layer {layer.number}
                        </span>
                        <h3 className="text-base font-semibold text-slate-900">{layer.title}</h3>
                      </div>
                      <p className="text-sm text-slate-500 italic mb-2">
                        &ldquo;{layer.question}&rdquo;
                      </p>
                      <p className="text-sm text-slate-600 leading-relaxed">
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

        {/* ── Results Comparison ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-6">Results</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Without */}
            <div className="rounded-2xl p-6 bg-red-50/50 border border-red-100">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-3 h-3 rounded-full bg-red-400" />
                <h3 className="text-sm font-bold text-red-700">Without Defense</h3>
              </div>
              <div className="space-y-3">
                <div className="flex justify-between items-baseline">
                  <span className="text-sm text-red-600">Max Drawdown</span>
                  <span className="text-2xl font-bold text-red-700 tabular-nums">-20%</span>
                </div>
                <hr className="border-red-100" />
                <div className="flex justify-between items-baseline">
                  <span className="text-sm text-red-600">Worst Month</span>
                  <span className="text-2xl font-bold text-red-700 tabular-nums">-10%</span>
                </div>
              </div>
            </div>

            {/* With */}
            <div className="rounded-2xl p-6 bg-emerald-50/50 border border-emerald-100">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-3 h-3 rounded-full bg-emerald-400" />
                <h3 className="text-sm font-bold text-emerald-700">With Risk Defense</h3>
              </div>
              <div className="space-y-3">
                <div className="flex justify-between items-baseline">
                  <span className="text-sm text-emerald-600">Max Drawdown</span>
                  <span className="text-2xl font-bold text-emerald-700 tabular-nums">-10%</span>
                </div>
                <hr className="border-emerald-100" />
                <div className="flex justify-between items-baseline">
                  <span className="text-sm text-emerald-600">Worst Month</span>
                  <span className="text-2xl font-bold text-emerald-700 tabular-nums">-5%</span>
                </div>
              </div>
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-3 text-center">
            Based on backtested data across 6-month market correction periods. Past performance does not guarantee future results.
          </p>
        </section>
        </SectionCurtain>

        {/* ── CTA ── */}
        <SectionCurtain>
        <section className="text-center py-12 px-6 bg-slate-50 rounded-2xl">
          <h2 className="text-2xl font-bold text-slate-900 mb-3">
            Run a risk simulation today
          </h2>
          <p className="text-slate-500 mb-6 max-w-md mx-auto">
            All seven observation layers are active on the free tier. Sign in
            and see your portfolio surfaced through the same lens.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-all active:scale-[0.97]"
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
