import Link from "next/link";
import type { Metadata } from "next";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { SectionCurtain } from "@/components/landing/section-curtain";
import {
  ArrowLeft,
  ArrowRight,
  User,
  CheckCircle2,
  Clock,
  SlidersHorizontal,
  Target,
  BarChart3,
  ShieldCheck,
  Zap,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Find Your Investor Type",
  description:
    "8 distinct investor profiles. Each gets a customized strategy tailored to your risk tolerance and goals.",
};

const profiles = [
  {
    code: "PX",
    title: "Passive Index Hugger",
    quote: "I want steady compounding with minimal effort.",
    strategy: "Quarterly rebalancing, widest stops, hold winners for years.",
    tag: "Low effort",
  },
  {
    code: "ST",
    title: "Steady Accumulator",
    quote: "I invest monthly and want moderate compounding.",
    strategy: "Monthly check-ins, balanced approach, dollar-cost averaging.",
    tag: "Balanced",
  },
  {
    code: "SW",
    title: "Swing Trader",
    quote: "I actively trade on weekly patterns.",
    strategy: "Technical focus, medium-term holds, weekly rebalancing.",
    tag: "Active",
  },
  {
    code: "MO",
    title: "Momentum Rider",
    quote: "I ride trends for weeks to months.",
    strategy: "Trend-following signals, wide trailing stops, ride momentum.",
    tag: "Momentum",
  },
  {
    code: "VA",
    title: "Value Hunter",
    quote: "I look for great companies priced below their intrinsic value.",
    strategy: "Contrarian picks, fundamentals-heavy analysis, patient holding.",
    tag: "Value",
  },
  {
    code: "RM",
    title: "Risk-Managed Compounder",
    quote: "Performance, but with strict loss limits.",
    strategy: "Hard 11% max drawdown cap, performance-oriented with guardrails.",
    tag: "Guardrailed",
  },
  {
    code: "AS",
    title: "Aggressive Scalper",
    quote: "I trade frequently for small gains.",
    strategy: "Tight stops, high frequency signals, quick entries and exits.",
    tag: "High frequency",
  },
  {
    code: "MR",
    title: "Macro Rotator",
    quote: "I shift between sectors based on the economy.",
    strategy: "Regime-driven rotation, sector momentum, macro signals.",
    tag: "Macro",
  },
];

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
          <span className="text-sm font-medium text-[var(--pq-ivory)]">Investor Profiles</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-20">
        {/* ── Disclaimer ── */}
        <DisclaimerBanner type="ai-analysis" className="mb-8" />

        {/* ── Title ── */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-sm bg-[rgba(184,149,106,0.08)] border border-[rgba(184,149,106,0.18)] mb-6">
            <User className="w-6 h-6 text-[var(--pq-bronze)]" />
          </div>
          <h1 className="font-[var(--font-display)] italic text-3xl sm:text-4xl font-medium text-[var(--pq-ivory)] mb-4 tracking-tight">
            Find Your Investor Type
          </h1>
          <p className="text-base text-[rgba(245,240,232,0.62)] max-w-xl mx-auto">
            8 distinct profiles. Each gets a customized strategy.
          </p>
        </div>

        {/* ── Assessment intro ── */}
        <SectionCurtain divider={false}>
        <section className="mb-12">
          <div className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-6 sm:p-8">
            <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-3">How it works</h2>
            <p className="text-[rgba(245,240,232,0.82)] leading-relaxed">
              Take our <span className="font-semibold text-[var(--pq-ivory)]">20-question assessment</span> to
              discover your investor type. Questions cover your experience level, risk tolerance,
              time horizon, and trading style. It takes about 3 minutes, and you can retake it anytime
              your situation changes.
            </p>
          </div>
        </section>
        </SectionCurtain>

        {/* ── 8 Profile Cards ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-6">The 8 Profiles</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {profiles.map((profile, idx) => {
              const ordinal = String(idx + 1).padStart(2, "0");
              return (
                <div
                  key={profile.title}
                  className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-5"
                >
                  <div className="flex items-start gap-4">
                    <div className="shrink-0 flex flex-col items-start gap-1">
                      <span className="font-[var(--font-serif)] text-[18px] tracking-[0.04em] text-[var(--pq-ivory)]">
                        {profile.code}
                      </span>
                      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.48)] tabular-nums">
                        {ordinal} / 08
                      </span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <h3 className="text-sm font-semibold text-[var(--pq-ivory)]">{profile.title}</h3>
                        <span className="text-[10px] font-medium uppercase tracking-[0.16em] px-2 py-0.5 border border-[rgba(184,149,106,0.28)] text-[var(--pq-bronze)] rounded-sm">
                          {profile.tag}
                        </span>
                      </div>
                      <p className="text-sm text-[rgba(245,240,232,0.62)] italic mb-2">
                        &ldquo;{profile.quote}&rdquo;
                      </p>
                      <p className="text-xs text-[rgba(245,240,232,0.55)] leading-relaxed">
                        {profile.strategy}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
        </SectionCurtain>

        {/* ── What each profile customizes ── */}
        <SectionCurtain>
        <section className="mb-16">
          <div className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-6 sm:p-8">
            <h2 className="font-[var(--font-serif)] text-lg font-medium text-[var(--pq-ivory)] mb-2">Each profile gets different...</h2>
            <p className="text-sm text-[rgba(245,240,232,0.62)] mb-6">
              Your profile does not just change labels. It changes how the entire system behaves for you.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {customizations.map((item) => (
                <div key={item.label} className="flex items-center gap-3 rounded-sm px-4 py-3 border border-[rgba(245,240,232,0.08)] bg-[rgba(0,0,0,0.18)]">
                  <CheckCircle2 className="w-4 h-4 text-[var(--pq-bronze)] shrink-0" />
                  <span className="text-sm text-[rgba(245,240,232,0.82)]">{item.label}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
        </SectionCurtain>

        {/* ── CTA ── */}
        <SectionCurtain>
        <section className="text-center py-12 px-6 rounded-sm border border-[rgba(184,149,106,0.18)] bg-[rgba(184,149,106,0.04)]">
          <h2 className="font-[var(--font-display)] italic text-2xl font-medium text-[var(--pq-ivory)] mb-3">
            Discover your investor type
          </h2>
          <p className="text-[rgba(245,240,232,0.62)] mb-6 max-w-md mx-auto">
            3 minutes, 20 questions. Get a strategy built for the way you
            actually invest.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-sm bg-[var(--pq-bronze)] text-[var(--pq-ink)] text-sm font-semibold hover:bg-[var(--pq-bronze-light)] transition-all"
          >
            Take the Assessment
            <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
        </SectionCurtain>
      </main>
    </div>
  );
}
