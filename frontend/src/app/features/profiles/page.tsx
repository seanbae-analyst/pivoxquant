import Link from "next/link";
import type { Metadata } from "next";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import {
  ArrowLeft,
  ArrowRight,
  User,
  Turtle,
  TrendingUp,
  Zap,
  Rocket,
  Gem,
  ShieldCheck,
  Swords,
  Globe,
  CheckCircle2,
  Clock,
  SlidersHorizontal,
  Target,
  BarChart3,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Find Your Investor Type — PivoxQuant",
  description:
    "8 distinct investor profiles. Each gets a customized strategy tailored to your risk tolerance and goals.",
};

/* ── Profile data ── */
const profiles = [
  {
    icon: Turtle,
    title: "Passive Index Hugger",
    quote: "I want steady growth with minimal effort.",
    strategy: "Quarterly rebalancing, widest stops, let winners run for years.",
    colorBg: "bg-emerald-50",
    colorBorder: "border-emerald-100",
    colorIcon: "text-emerald-600",
    colorTag: "bg-emerald-100 text-emerald-700",
    tag: "Low effort",
  },
  {
    icon: TrendingUp,
    title: "Steady Accumulator",
    quote: "I invest monthly and want moderate growth.",
    strategy: "Monthly check-ins, balanced approach, dollar-cost averaging.",
    colorBg: "bg-blue-50",
    colorBorder: "border-blue-100",
    colorIcon: "text-blue-600",
    colorTag: "bg-blue-100 text-blue-700",
    tag: "Balanced",
  },
  {
    icon: Zap,
    title: "Swing Trader",
    quote: "I actively trade on weekly patterns.",
    strategy: "Technical focus, medium-term holds, weekly rebalancing.",
    colorBg: "bg-amber-50",
    colorBorder: "border-amber-100",
    colorIcon: "text-amber-600",
    colorTag: "bg-amber-100 text-amber-700",
    tag: "Active",
  },
  {
    icon: Rocket,
    title: "Momentum Rider",
    quote: "I ride trends for weeks to months.",
    strategy: "Trend-following signals, wide trailing stops, ride momentum.",
    colorBg: "bg-accent/10",
    colorBorder: "border-accent/20",
    colorIcon: "text-accent",
    colorTag: "bg-accent/15 text-accent",
    tag: "Momentum",
  },
  {
    icon: Gem,
    title: "Value Hunter",
    quote: "I look for great companies priced below their intrinsic value.",
    strategy: "Contrarian picks, fundamentals-heavy analysis, patient holding.",
    colorBg: "bg-cyan-50",
    colorBorder: "border-cyan-100",
    colorIcon: "text-cyan-600",
    colorTag: "bg-cyan-100 text-cyan-700",
    tag: "Value",
  },
  {
    icon: ShieldCheck,
    title: "Risk-Managed Growth",
    quote: "Growth, but with strict loss limits.",
    strategy: "Hard 11% max drawdown cap, growth-oriented with guardrails.",
    colorBg: "bg-rose-50",
    colorBorder: "border-rose-100",
    colorIcon: "text-rose-600",
    colorTag: "bg-rose-100 text-rose-700",
    tag: "Protected",
  },
  {
    icon: Swords,
    title: "Aggressive Scalper",
    quote: "I trade frequently for small gains.",
    strategy: "Tight stops, high frequency signals, quick entries and exits.",
    colorBg: "bg-red-50",
    colorBorder: "border-red-100",
    colorIcon: "text-red-600",
    colorTag: "bg-red-100 text-red-700",
    tag: "High frequency",
  },
  {
    icon: Globe,
    title: "Macro Rotator",
    quote: "I shift between sectors based on the economy.",
    strategy: "Regime-driven rotation, sector momentum, macro signals.",
    colorBg: "bg-indigo-50",
    colorBorder: "border-indigo-100",
    colorIcon: "text-indigo-600",
    colorTag: "bg-indigo-100 text-indigo-700",
    tag: "Macro",
  },
];

/* ── What each profile customizes ── */
const customizations = [
  { icon: Target, label: "Signal thresholds (POSITIVE/NEGATIVE)" },
  { icon: ShieldCheck, label: "Risk defense settings" },
  { icon: BarChart3, label: "Model activation" },
  { icon: SlidersHorizontal, label: "Position sizing" },
  { icon: Clock, label: "Rebalancing frequency" },
  { icon: Zap, label: "Alert sensitivity" },
];

export default function ProfilesPage() {
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
          <span className="text-sm font-medium text-slate-700">Investor Profiles</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-20">
        {/* ── Disclaimer ── */}
        <DisclaimerBanner type="ai-analysis" theme="light" className="mb-8" />

        {/* ── Title ── */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-accent/10 mb-6">
            <User className="w-7 h-7 text-accent" />
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">
            Find Your <span className="gradient-text">Investor Type</span>
          </h1>
          <p className="text-lg text-slate-500 max-w-xl mx-auto">
            8 distinct profiles. Each gets a customized strategy.
          </p>
        </div>

        {/* ── Assessment intro ── */}
        <section className="mb-12">
          <div className="sp-card rounded-2xl p-6 sm:p-8">
            <h2 className="text-xl font-bold text-slate-900 mb-3">How it works</h2>
            <p className="text-slate-600 leading-relaxed">
              Take our <span className="font-semibold text-slate-900">20-question assessment</span> to
              discover your investor type. Questions cover your experience level, risk tolerance,
              time horizon, and trading style. It takes about 3 minutes, and you can retake it anytime
              your situation changes.
            </p>
          </div>
        </section>

        {/* ── 8 Profile Cards ── */}
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-6">The 8 Profiles</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {profiles.map((profile) => {
              const Icon = profile.icon;
              return (
                <div key={profile.title} className={`sp-card rounded-2xl p-5 border ${profile.colorBorder}`}>
                  <div className="flex items-start gap-3">
                    <div className={`shrink-0 w-10 h-10 rounded-xl flex items-center justify-center ${profile.colorBg}`}>
                      <Icon className={`w-5 h-5 ${profile.colorIcon}`} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <h3 className="text-sm font-semibold text-slate-900">{profile.title}</h3>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${profile.colorTag}`}>
                          {profile.tag}
                        </span>
                      </div>
                      <p className="text-sm text-slate-500 italic mb-2">
                        &ldquo;{profile.quote}&rdquo;
                      </p>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        {profile.strategy}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* ── What each profile customizes ── */}
        <section className="mb-16">
          <div className="bg-slate-50 rounded-2xl p-6 sm:p-8">
            <h2 className="text-lg font-bold text-slate-900 mb-2">Each profile gets different...</h2>
            <p className="text-sm text-slate-500 mb-6">
              Your profile does not just change labels. It changes how the entire system behaves for you.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {customizations.map((item) => {
                return (
                  <div key={item.label} className="flex items-center gap-3 bg-white rounded-xl px-4 py-3 border border-slate-100">
                    <CheckCircle2 className="w-4 h-4 text-accent shrink-0" />
                    <span className="text-sm text-slate-700">{item.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── CTA ── */}
        <section className="text-center py-12 px-6 bg-slate-50 rounded-2xl">
          <h2 className="text-2xl font-bold text-slate-900 mb-3">
            Discover your investor type
          </h2>
          <p className="text-slate-500 mb-6 max-w-md mx-auto">
            3 minutes, 20 questions. Get a strategy built for the way you
            actually invest.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-all active:scale-[0.97]"
          >
            Take the Assessment
            <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
      </main>
    </div>
  );
}
