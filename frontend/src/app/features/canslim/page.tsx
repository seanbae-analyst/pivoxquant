import Link from "next/link";
import type { Metadata } from "next";
import {
  ArrowLeft,
  ArrowRight,
  Search,
  TrendingUp,
  CalendarDays,
  Sparkles,
  BarChart3,
  Award,
  Building2,
  Activity,
  Star,
  AlertTriangle,
  XCircle,
  CheckCircle2,
} from "lucide-react";

export const metadata: Metadata = {
  title: "CAN SLIM Stock Screener — PivoxQuant",
  description:
    "William O'Neil's systematic 7-factor method, automated. Screen stocks using the CAN SLIM strategy.",
};

/* ── CAN SLIM factors ── */
const factors = [
  {
    letter: "C",
    title: "Current Earnings",
    description: "Quarterly earnings growth of 25% or more. Is the company making more money right now than it did last year at this time?",
    icon: TrendingUp,
    threshold: "25%+ quarterly growth",
    color: "text-accent bg-accent/10 border-accent/20",
  },
  {
    letter: "A",
    title: "Annual Earnings",
    description: "Three or more years of consistent annual earnings growth. One good quarter is not enough. You want a track record.",
    icon: CalendarDays,
    threshold: "3 years consistent growth",
    color: "text-blue-600 bg-blue-50 border-blue-100",
  },
  {
    letter: "N",
    title: "New Highs",
    description: "Stock trading near its 52-week high. Counterintuitively, stocks making new highs tend to go even higher. Momentum matters.",
    icon: Sparkles,
    threshold: "Near 52-week high",
    color: "text-amber-600 bg-amber-50 border-amber-100",
  },
  {
    letter: "S",
    title: "Supply & Demand",
    description: "Strong volume with limited shares available. When lots of people want to buy but few are selling, prices go up.",
    icon: BarChart3,
    threshold: "Strong volume + limited float",
    color: "text-emerald-600 bg-emerald-50 border-emerald-100",
  },
  {
    letter: "L",
    title: "Leader",
    description: "The stock shows higher relative strength versus its sector (benchmark comparison, information only).",
    icon: Award,
    threshold: "Higher relative strength vs sector",
    color: "text-amber-600 bg-amber-50 border-amber-100",
  },
  {
    letter: "I",
    title: "Institutional Interest",
    description: "Mutual funds and hedge funds are buying in. When smart money moves in, it is a strong signal of confidence.",
    icon: Building2,
    threshold: "Smart money is buying",
    color: "text-indigo-600 bg-indigo-50 border-indigo-100",
  },
  {
    letter: "M",
    title: "Market Direction",
    description: "The overall market is in an uptrend. Even the best stock struggles when the whole market is falling.",
    icon: Activity,
    threshold: "Overall market is healthy",
    color: "text-cyan-600 bg-cyan-50 border-cyan-100",
  },
];

/* ── Rating tiers ── */
const ratings = [
  {
    range: "6 - 7",
    label: "STRONG",
    description: "All systems go. The stock passes nearly every check.",
    color: "bg-emerald-50 border-emerald-200 text-emerald-700",
    icon: Star,
    iconColor: "text-emerald-500",
  },
  {
    range: "4 - 5",
    label: "MODERATE",
    description: "Some concerns. Worth watching, but do more research.",
    color: "bg-amber-50 border-amber-200 text-amber-700",
    icon: AlertTriangle,
    iconColor: "text-amber-500",
  },
  {
    range: "2 - 3",
    label: "WEAK",
    description: "Significant risks. Multiple warning signs present.",
    color: "bg-orange-50 border-orange-200 text-orange-700",
    icon: AlertTriangle,
    iconColor: "text-orange-500",
  },
  {
    range: "0 - 1",
    label: "AVOID",
    description: "Too many red flags. The data says stay away for now.",
    color: "bg-red-50 border-red-200 text-red-700",
    icon: XCircle,
    iconColor: "text-red-500",
  },
];

export default function CanslimPage() {
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
          <span className="text-sm font-medium text-slate-700">CAN SLIM Screener</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-20">
        {/* ── Title ── */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-accent/10 mb-6">
            <Search className="w-7 h-7 text-accent" />
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">
            <span className="gradient-text">CAN SLIM</span> Stock Screener
          </h1>
          <p className="text-lg text-slate-500 max-w-xl mx-auto">
            William O&apos;Neil&apos;s systematic 7-factor method, automated.
          </p>
        </div>

        {/* ── What is CAN SLIM? ── */}
        <section className="mb-16">
          <div className="sp-card rounded-2xl p-6 sm:p-8">
            <h2 className="text-xl font-bold text-slate-900 mb-4">What is CAN SLIM?</h2>
            <p className="text-slate-600 leading-relaxed mb-3">
              CAN SLIM is a stock selection method created by William O&apos;Neil, who famously
              turned a small starting investment into significant returns in just 18 months.
            </p>
            <p className="text-slate-500 text-sm leading-relaxed">
              His method picks stocks using 7 specific factors. Each letter stands for one
              factor. A stock either passes or fails each check, giving it a score from 0 to 7.
            </p>
          </div>
        </section>

        {/* ── The 7 Factors ── */}
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-6">The 7 Factors</h2>
          <div className="space-y-4">
            {factors.map((factor) => {
              const colorParts = factor.color.split(" ");
              return (
                <div key={factor.letter} className={`rounded-2xl p-5 border ${colorParts[2]} ${colorParts[1]}`}>
                  <div className="flex items-start gap-4">
                    <div className="shrink-0 w-12 h-12 rounded-xl bg-white flex items-center justify-center border border-slate-100 shadow-sm">
                      <span className="text-xl font-black text-slate-900">{factor.letter}</span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <h3 className="text-base font-semibold text-slate-900">{factor.title}</h3>
                      </div>
                      <p className="text-sm text-slate-600 leading-relaxed mb-2">
                        {factor.description}
                      </p>
                      <div className="flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-accent" />
                        <span className="text-xs font-medium text-accent">{factor.threshold}</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* ── Rating System ── */}
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-6">Rating System</h2>
          <p className="text-sm text-slate-500 mb-6">
            Each stock scores 0 to 7 based on how many factors it passes. Higher means a stronger candidate.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {ratings.map((rating) => {
              const Icon = rating.icon;
              return (
                <div key={rating.label} className={`rounded-2xl p-5 border ${rating.color}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Icon className={`w-5 h-5 ${rating.iconColor}`} />
                    <span className="text-lg font-bold">{rating.range}</span>
                    <span className="text-xs font-bold uppercase">{rating.label}</span>
                  </div>
                  <p className="text-sm opacity-80">{rating.description}</p>
                </div>
              );
            })}
          </div>
        </section>

        {/* ── CTA ── */}
        <section className="text-center py-12 px-6 bg-slate-50 rounded-2xl">
          <h2 className="text-2xl font-bold text-slate-900 mb-3">
            Screen stocks with CAN SLIM
          </h2>
          <p className="text-slate-500 mb-6 max-w-md mx-auto">
            We automate the research that used to take hours. Sign up and start
            screening stocks in seconds.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-all active:scale-[0.97]"
          >
            Try the Screener
            <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
      </main>
    </div>
  );
}
