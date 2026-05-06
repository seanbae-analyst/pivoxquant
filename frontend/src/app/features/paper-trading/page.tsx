import Link from "next/link";
import type { Metadata } from "next";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { SectionCurtain } from "@/components/landing/section-curtain";
import {
  ArrowLeft,
  ArrowRight,
  FlaskConical,
  CheckCircle2,
  BarChart3,
  Shield,
  Clock,
  ListChecks,
  TrendingUp,
  Activity,
  DollarSign,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Paper Trading",
  description:
    "Practice with real market data. Risk zero real money. Test all 40 quant models before committing real capital.",
};

/* ── Steps (v3 + AutoTrader removal post 2026-04-27 legal review) ── */
const steps = [
  {
    step: "1",
    title: "Open a paper portfolio",
    description: "Create a simulated portfolio inside PivoxQuant in under two minutes. No live broker linkage required.",
  },
  {
    step: "2",
    title: "Quant models surface candidate entries",
    description: "Based on your investor profile, our 40 quant models produce observation-only candidates from real-time market data. You decide.",
  },
  {
    step: "3",
    title: "You confirm each order yourself",
    description: "Every recorded order needs your one-click confirmation. Nothing executes without you. Confirm or dismiss in seconds.",
  },
  {
    step: "4",
    title: "Track performance over time",
    description: "Watch your paper portfolio grow (or learn from losses) over weeks and months with detailed analytics.",
  },
  {
    step: "5",
    title: "Take the journal to your broker",
    description: "When you are ready, run the same thesis in your own brokerage account. PivoxQuant remains observational — no orders are ever routed for you.",
  },
];

/* ── Why paper trade ── */
const reasons = [
  { icon: FlaskConical, label: "Test our 40 quant models before committing real capital" },
  { icon: Shield, label: "See how the 7-layer risk defense surfaces in real time" },
  { icon: Activity, label: "Learn how your investor profile performs in live markets" },
  { icon: TrendingUp, label: "Build confidence in the system at your own pace" },
  { icon: DollarSign, label: "Zero risk. No real money involved at any point" },
];

/* ── Tracking metrics ── */
const metrics = [
  { icon: DollarSign, label: "Daily P&L updates", description: "See exactly how much your paper portfolio gained or lost each day." },
  { icon: BarChart3, label: "Benchmark comparison", description: "How does the recorded strategy compare against a passive index benchmark? Observation only." },
  { icon: Shield, label: "Risk metrics", description: "Max Drawdown, Sharpe Ratio, Calmar Ratio, and more." },
  { icon: ListChecks, label: "Full trade history", description: "Every recorded order is logged with the quant model that surfaced the candidate." },
  { icon: Clock, label: "Performance timeline", description: "View returns over days, weeks, and months." },
  { icon: Activity, label: "Model attribution", description: "See which of the 40 models contributed most to your returns." },
];

export default function PaperTradingPage() {
  return (
    <div className="min-h-screen bg-[var(--pq-ink)] text-[var(--pq-ivory)]">
      {/* ── Header ── */}
      <header className="border-b border-[rgba(245,240,232,0.08)] bg-[rgba(5,5,5,0.85)] backdrop-blur-xl sticky top-0 z-30">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
          <Link
            href="/#features"
            className="inline-flex items-center gap-1.5 text-sm text-[rgba(245,240,232,0.55)] hover:text-[var(--pq-bronze)] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Link>
          <span className="text-[rgba(245,240,232,0.32)]">/</span>
          <span className="text-sm font-medium text-[var(--pq-ivory)]">Paper Trading</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-20">
        {/* ── Disclaimer ── */}
        <DisclaimerBanner type="ai-analysis" className="mb-8" />

        {/* ── Title ── */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-sm bg-[rgba(184,149,106,0.08)] border border-[rgba(184,149,106,0.18)] mb-6">
            <FlaskConical className="w-6 h-6 text-[var(--pq-bronze)]" />
          </div>
          <h1 className="font-[var(--font-display)] italic text-3xl sm:text-4xl font-medium text-[var(--pq-ivory)] mb-4 tracking-tight">
            Paper Trading
          </h1>
          <p className="text-base text-[rgba(245,240,232,0.62)] max-w-xl mx-auto">
            Practice with real market data. Risk zero real money.
          </p>
        </div>

        {/* ── What is Paper Trading? ── */}
        <SectionCurtain divider={false}>
        <section className="mb-16">
          <div className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-6 sm:p-8">
            <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-4">What is Paper Trading?</h2>
            <p className="text-[rgba(245,240,232,0.82)] leading-relaxed mb-3">
              Think of it as a <span className="font-semibold text-[var(--pq-ivory)]">flight simulator for investing</span>.
              You make trades with virtual money using real-time market prices.
              Everything works exactly like real trading, except no actual money is at stake.
            </p>
            <p className="text-[rgba(245,240,232,0.62)] text-sm leading-relaxed">
              Professional traders test new strategies this way before risking real capital.
              Now you can too.
            </p>
          </div>
        </section>
        </SectionCurtain>

        {/* ── Why Paper Trade ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-6">Why Paper Trade?</h2>
          <div className="space-y-3">
            {reasons.map((reason) => (
              <div key={reason.label} className="flex items-center gap-3 p-4 rounded-sm bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)]">
                <CheckCircle2 className="w-4 h-4 text-[var(--pq-bronze)] shrink-0" />
                <span className="text-sm text-[rgba(245,240,232,0.82)]">{reason.label}</span>
              </div>
            ))}
          </div>
        </section>
        </SectionCurtain>

        {/* ── How It Works (steps) ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-6">How It Works</h2>
          <div className="space-y-4">
            {steps.map((item) => (
              <div key={item.step} className="flex items-start gap-4">
                <div className="shrink-0 w-10 h-10 rounded-sm bg-[rgba(184,149,106,0.08)] border border-[rgba(184,149,106,0.18)] flex items-center justify-center">
                  <span className="font-mono text-sm font-medium text-[var(--pq-bronze)] tabular-nums">{item.step}</span>
                </div>
                <div className="pt-1.5 min-w-0 flex-1">
                  <h3 className="text-sm font-semibold text-[var(--pq-ivory)] mb-1">{item.title}</h3>
                  <p className="text-sm text-[rgba(245,240,232,0.62)] leading-relaxed">{item.description}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
        </SectionCurtain>

        {/* ── Live Tracking ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-2">Live Tracking</h2>
          <p className="text-sm text-[rgba(245,240,232,0.62)] mb-6">
            Full transparency into how your paper portfolio performs, with institutional-grade analytics.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {metrics.map((metric) => {
              const Icon = metric.icon;
              return (
                <div key={metric.label} className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-5">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-8 h-8 rounded-sm bg-[rgba(184,149,106,0.08)] border border-[rgba(184,149,106,0.18)] flex items-center justify-center">
                      <Icon className="w-4 h-4 text-[var(--pq-bronze)]" />
                    </div>
                    <h3 className="text-sm font-semibold text-[var(--pq-ivory)]">{metric.label}</h3>
                  </div>
                  <p className="text-sm text-[rgba(245,240,232,0.62)] leading-relaxed">{metric.description}</p>
                </div>
              );
            })}
          </div>
        </section>
        </SectionCurtain>

        {/* ── CTA ── */}
        <SectionCurtain>
        <section className="text-center py-12 px-6 rounded-sm border border-[rgba(184,149,106,0.18)] bg-[rgba(184,149,106,0.04)]">
          <h2 className="font-[var(--font-display)] italic text-2xl font-medium text-[var(--pq-ivory)] mb-3">
            Start paper trading today
          </h2>
          <p className="text-[rgba(245,240,232,0.62)] mb-6 max-w-md mx-auto">
            Free PivoxQuant account. Zero risk.
            See the quant models in action before you invest a single dollar.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-sm bg-[var(--pq-bronze)] text-[var(--pq-ink)] text-sm font-semibold hover:bg-[var(--pq-bronze-light)] transition-all"
          >
            Start Paper Trading
            <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
        </SectionCurtain>
      </main>
    </div>
  );
}
