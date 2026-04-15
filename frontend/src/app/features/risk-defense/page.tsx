import Link from "next/link";
import type { Metadata } from "next";
import {
  ArrowLeft,
  ArrowRight,
  Shield,
  AlertTriangle,
  Activity,
  GitBranch,
  Gauge,
  PieChart,
  Radio,
  OctagonAlert,
} from "lucide-react";

export const metadata: Metadata = {
  title: "7-Layer Risk Defense — PivoxQuant",
  description:
    "Protecting your portfolio is just as important as growing it. Learn about our 7-layer automatic defense system.",
};

/* ── 7 Layers ── */
const layers = [
  {
    number: 1,
    icon: Gauge,
    title: "VaR Monitor",
    question: "How much could I lose today?",
    description:
      "Value at Risk calculates your worst-case daily loss at 95% confidence. If your VaR exceeds your comfort zone, you get an immediate alert so you can act before losses pile up.",
    color: "text-violet-600 bg-violet-50",
  },
  {
    number: 2,
    icon: GitBranch,
    title: "Correlation Watch",
    question: "Are all my stocks moving together?",
    description:
      "If all your holdings rise and fall at the same time, your diversification is an illusion. This layer warns when portfolio correlations spike above safe levels.",
    color: "text-blue-600 bg-blue-50",
  },
  {
    number: 3,
    icon: Activity,
    title: "VIX Shield",
    question: "Is the market scared?",
    description:
      "The VIX measures market fear. When it spikes, this layer automatically suggests raising your cash position to weather the storm.",
    color: "text-pink-600 bg-pink-50",
  },
  {
    number: 4,
    icon: AlertTriangle,
    title: "Tail Risk Guard",
    question: "Which stock could hurt me most?",
    description:
      "Identifies the single position contributing the most risk to your portfolio. Even one bad apple can drag down everything else.",
    color: "text-amber-600 bg-amber-50",
  },
  {
    number: 5,
    icon: OctagonAlert,
    title: "Daily Loss Limit",
    question: "Stop the bleeding.",
    description:
      "Sets a hard cap on daily losses. If your portfolio drops past your threshold in a single day, the system halts all trading activity to prevent panic decisions.",
    color: "text-red-600 bg-red-50",
  },
  {
    number: 6,
    icon: PieChart,
    title: "Sector Balance",
    question: "Don't put all eggs in one basket.",
    description:
      "Monitors how much of your portfolio is in any single sector. If technology reaches 50% of your portfolio, you get an alert before concentration becomes dangerous.",
    color: "text-emerald-600 bg-emerald-50",
  },
  {
    number: 7,
    icon: Radio,
    title: "Regime Radar",
    question: "What phase is the market in?",
    description:
      "Markets cycle between bull runs, corrections, and crashes. This layer detects the current regime and adjusts all defense settings accordingly.",
    color: "text-indigo-600 bg-indigo-50",
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
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-violet-50 mb-6">
            <Shield className="w-7 h-7 text-violet-600" />
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">
            7-Layer <span className="gradient-text">Risk Defense</span>
          </h1>
          <p className="text-lg text-slate-500 max-w-xl mx-auto">
            Protecting your portfolio is just as important as growing it.
          </p>
        </div>

        {/* ── The Problem ── */}
        <section className="mb-16">
          <div className="sp-card rounded-2xl p-6 sm:p-8 border-l-4 border-l-amber-400">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
              <div>
                <h2 className="text-lg font-bold text-slate-900 mb-2">The Problem</h2>
                <p className="text-slate-600 leading-relaxed">
                  The average investor panics and sells at the worst possible time, losing
                  4&ndash;8% more than necessary during market drops. Emotions take over when
                  you have no system protecting you.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ── 7 Defense Layers ── */}
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-2">Our Solution: 7 Automatic Defense Layers</h2>
          <p className="text-sm text-slate-500 mb-8">
            Each layer works independently. Together, they form a comprehensive safety net.
          </p>
          <div className="space-y-4">
            {layers.map((layer) => {
              const Icon = layer.icon;
              return (
                <div key={layer.number} className="sp-card rounded-2xl p-6">
                  <div className="flex items-start gap-4">
                    <div className="shrink-0">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${layer.color.split(" ")[1]}`}>
                        <Icon className={`w-5 h-5 ${layer.color.split(" ")[0]}`} />
                      </div>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold text-violet-600 bg-violet-50 px-2 py-0.5 rounded">
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

        {/* ── Results Comparison ── */}
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

        {/* ── CTA ── */}
        <section className="text-center py-12 px-6 bg-slate-50 rounded-2xl">
          <h2 className="text-2xl font-bold text-slate-900 mb-3">
            Protect your portfolio today
          </h2>
          <p className="text-slate-500 mb-6 max-w-md mx-auto">
            All 7 defense layers are active on the free plan. Sign up
            and sleep better knowing your investments are protected.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-all active:scale-[0.97]"
          >
            Protect My Portfolio
            <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
      </main>
    </div>
  );
}
