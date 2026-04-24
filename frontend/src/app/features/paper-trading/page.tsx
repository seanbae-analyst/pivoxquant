import Link from "next/link";
import type { Metadata } from "next";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
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
  title: "Paper Trading — PivoxQuant",
  description:
    "Practice with real market data. Risk zero real money. Test all 58 quant models before committing real capital.",
};

/* ── Steps ── */
const steps = [
  {
    step: "1",
    title: "Open a paper portfolio",
    description: "Create a simulated portfolio inside PivoxQuant in under two minutes. No live broker linkage required.",
  },
  {
    step: "2",
    title: "AutoTrader surfaces candidate entries",
    description: "Based on your investor profile, our 58 quant models produce observation-only candidates from real-time market data. You decide.",
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
  { icon: FlaskConical, label: "Test our 58 quant models before committing real capital" },
  { icon: Shield, label: "See how the 7-layer risk defense protects in real time" },
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
  { icon: Activity, label: "Model attribution", description: "See which of the 58 models contributed most to your returns." },
];

export default function PaperTradingPage() {
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
          <span className="text-sm font-medium text-slate-700">Paper Trading</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-20">
        {/* ── Disclaimer ── */}
        <DisclaimerBanner type="ai-analysis" theme="light" className="mb-8" />

        {/* ── Title ── */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-accent/10 mb-6">
            <FlaskConical className="w-7 h-7 text-accent" />
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">
            <span className="gradient-text">Paper Trading</span>
          </h1>
          <p className="text-lg text-slate-500 max-w-xl mx-auto">
            Practice with real market data. Risk zero real money.
          </p>
        </div>

        {/* ── What is Paper Trading? ── */}
        <section className="mb-16">
          <div className="sp-card rounded-2xl p-6 sm:p-8">
            <h2 className="text-xl font-bold text-slate-900 mb-4">What is Paper Trading?</h2>
            <p className="text-slate-600 leading-relaxed mb-3">
              Think of it as a <span className="font-semibold text-slate-900">flight simulator for investing</span>.
              You make trades with virtual money using real-time market prices.
              Everything works exactly like real trading, except no actual money is at stake.
            </p>
            <p className="text-slate-500 text-sm leading-relaxed">
              Professional traders test new strategies this way before risking real capital.
              Now you can too.
            </p>
          </div>
        </section>

        {/* ── Why Paper Trade ── */}
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-6">Why Paper Trade?</h2>
          <div className="space-y-3">
            {reasons.map((reason) => {
              return (
                <div key={reason.label} className="flex items-center gap-3 p-4 rounded-xl bg-slate-50 border border-slate-100">
                  <CheckCircle2 className="w-4.5 h-4.5 text-emerald-500 shrink-0" />
                  <span className="text-sm text-slate-700">{reason.label}</span>
                </div>
              );
            })}
          </div>
        </section>

        {/* ── How It Works (steps) ── */}
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-6">How It Works</h2>
          <div className="space-y-4">
            {steps.map((item) => (
              <div key={item.step} className="flex items-start gap-4">
                <div className="shrink-0 w-10 h-10 rounded-full bg-accent/10 flex items-center justify-center">
                  <span className="text-sm font-bold text-accent">{item.step}</span>
                </div>
                <div className="pt-1.5 min-w-0 flex-1">
                  <h3 className="text-sm font-semibold text-slate-900 mb-1">{item.title}</h3>
                  <p className="text-sm text-slate-500 leading-relaxed">{item.description}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Live Tracking ── */}
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-2">Live Tracking</h2>
          <p className="text-sm text-slate-500 mb-6">
            Full transparency into how your paper portfolio performs, with institutional-grade analytics.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {metrics.map((metric) => {
              const Icon = metric.icon;
              return (
                <div key={metric.label} className="sp-card rounded-2xl p-5">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                      <Icon className="w-4 h-4 text-accent" />
                    </div>
                    <h3 className="text-sm font-semibold text-slate-900">{metric.label}</h3>
                  </div>
                  <p className="text-sm text-slate-500 leading-relaxed">{metric.description}</p>
                </div>
              );
            })}
          </div>
        </section>

        {/* ── CTA ── */}
        <section className="text-center py-12 px-6 bg-slate-50 rounded-2xl">
          <h2 className="text-2xl font-bold text-slate-900 mb-3">
            Start paper trading today
          </h2>
          <p className="text-slate-500 mb-6 max-w-md mx-auto">
            Free PivoxQuant account. Zero risk.
            See the quant models in action before you invest a single dollar.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-all active:scale-[0.97]"
          >
            Start Paper Trading
            <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
      </main>
    </div>
  );
}
