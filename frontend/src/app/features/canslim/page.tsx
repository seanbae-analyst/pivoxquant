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
import { SectionCurtain } from "@/components/landing/section-curtain";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";

export const metadata: Metadata = {
  title: "CAN SLIM Stock Screener",
  description:
    "William O'Neil's systematic 7-factor method, automated. Screen stocks using the CAN SLIM strategy.",
  alternates: { canonical: "/features/canslim" },
};

/* ── CAN SLIM factors (v3: bronze accent uniform) ── */
const factors = [
  {
    letter: "C",
    title: "Current Earnings",
    description: "Quarterly earnings growth of 25% or more. Is the company making more money right now than it did last year at this time?",
    icon: TrendingUp,
    threshold: "25%+ quarterly growth",
  },
  {
    letter: "A",
    title: "Annual Earnings",
    description: "Three or more years of consistent annual earnings growth. One good quarter is not enough. You want a track record.",
    icon: CalendarDays,
    threshold: "3 years consistent growth",
  },
  {
    letter: "N",
    title: "New Highs",
    description: "Stock trading near its 52-week high. Counterintuitively, stocks making new highs tend to go even higher. Momentum matters.",
    icon: Sparkles,
    threshold: "Near 52-week high",
  },
  {
    letter: "S",
    title: "Supply & Demand",
    description: "Strong volume with limited shares available. When demand outpaces supply, prices historically drift higher — a factor CANSLIM measures, not a prediction.",
    icon: BarChart3,
    threshold: "Strong volume + limited float",
  },
  {
    letter: "L",
    title: "Leader (1m Momentum)",
    description: "The stock has shown a positive 1-month return — a momentum proxy used as a stand-in for relative strength. Information only; not a sector-relative benchmark.",
    icon: Award,
    threshold: "1-month positive return",
  },
  {
    letter: "I",
    title: "Institutional Interest",
    description: "Observes institutional flow — mutual fund and hedge fund position changes in the name. Descriptive factor only; not a signal to act.",
    icon: Building2,
    threshold: "Observed institutional accumulation",
  },
  {
    letter: "M",
    title: "Market Direction",
    description: "The overall market is in an uptrend. Even the best stock struggles when the whole market is falling.",
    icon: Activity,
    threshold: "Overall market is healthy",
  },
];

/* ── Rating tiers (v3 KR convention: indigo for warning, bronze for strong) ── */
const ratings = [
  {
    range: "6 - 7",
    label: "STRONG",
    description: "All systems go. The stock passes nearly every check.",
    accent: "var(--pq-bronze)",
    bg: "rgba(184,149,106,0.08)",
    border: "rgba(184,149,106,0.28)",
    icon: Star,
  },
  {
    range: "4 - 5",
    label: "MODERATE",
    description: "Some concerns. Worth watching, but do more research.",
    accent: "var(--pq-bronze-light)",
    bg: "rgba(184,149,106,0.04)",
    border: "rgba(184,149,106,0.18)",
    icon: AlertTriangle,
  },
  {
    range: "2 - 3",
    label: "WEAK",
    description: "Significant risks. Multiple warning signs present.",
    accent: "#7AA0C8",
    bg: "rgba(122,160,200,0.06)",
    border: "rgba(122,160,200,0.22)",
    icon: AlertTriangle,
  },
  {
    range: "0 - 1",
    label: "AVOID",
    description: "Too many red flags. The data says stay away for now.",
    accent: "#7AA0C8",
    bg: "rgba(122,160,200,0.1)",
    border: "rgba(122,160,200,0.32)",
    icon: XCircle,
  },
];

export default function CanslimPage() {
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
          <span className="text-sm font-medium text-[var(--pq-ivory)]">CAN SLIM Screener</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-20">
        {/* ── Title ── */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-sm bg-[rgba(184,149,106,0.08)] border border-[rgba(184,149,106,0.18)] mb-6">
            <Search className="w-6 h-6 text-[var(--pq-bronze)]" />
          </div>
          <h1 className="font-[var(--font-display)] italic text-3xl sm:text-4xl font-medium text-[var(--pq-ivory)] mb-4 tracking-tight">
            CAN SLIM Stock Screener
          </h1>
          <p className="text-base text-[rgba(245,240,232,0.62)] max-w-xl mx-auto">
            William O&apos;Neil&apos;s systematic 7-factor method, automated.
          </p>
        </div>

        {/* ── What is CAN SLIM? ── */}
        <SectionCurtain divider={false}>
        <section className="mb-16">
          <div className="rounded-sm border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-6 sm:p-8">
            <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-4">What is CAN SLIM?</h2>
            <p className="text-[rgba(245,240,232,0.82)] leading-relaxed mb-3">
              CAN SLIM is a stock selection method created by William O&apos;Neil, who famously
              turned a small starting investment into significant returns in just 18 months.
            </p>
            <p className="text-[rgba(245,240,232,0.62)] text-sm leading-relaxed">
              His method picks stocks using 7 specific factors. Each letter stands for one
              factor. A stock either passes or fails each check, giving it a score from 0 to 7.
            </p>
          </div>
        </section>
        </SectionCurtain>

        {/* ── The 7 Factors ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-6">The 7 Factors</h2>
          <div className="space-y-4">
            {factors.map((factor) => (
              <div key={factor.letter} className="rounded-sm border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-5">
                <div className="flex items-start gap-4">
                  <div className="shrink-0 w-12 h-12 rounded-sm bg-[rgba(184,149,106,0.06)] flex items-center justify-center border border-[rgba(184,149,106,0.18)]">
                    <span className="font-[var(--font-display)] italic text-xl font-medium text-[var(--pq-bronze)]">{factor.letter}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <h3 className="text-base font-semibold text-[var(--pq-ivory)]">{factor.title}</h3>
                    </div>
                    <p className="text-sm text-[rgba(245,240,232,0.82)] leading-relaxed mb-2">
                      {factor.description}
                    </p>
                    <div className="flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-[var(--pq-bronze)]" />
                      <span className="text-xs font-medium text-[var(--pq-bronze)]">{factor.threshold}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
        </SectionCurtain>

        {/* ── Rating System ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-6">Rating System</h2>
          <p className="text-sm text-[rgba(245,240,232,0.62)] mb-6">
            Each stock scores 0 to 7 based on how many factors it passes. Higher means a stronger candidate.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {ratings.map((rating) => {
              const Icon = rating.icon;
              return (
                <div
                  key={rating.label}
                  className="rounded-sm p-5 border"
                  style={{ background: rating.bg, borderColor: rating.border }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Icon className="w-5 h-5" style={{ color: rating.accent }} />
                    <span className="font-mono text-lg font-medium tabular-nums" style={{ color: rating.accent }}>{rating.range}</span>
                    <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: rating.accent }}>{rating.label}</span>
                  </div>
                  <p className="text-sm text-[rgba(245,240,232,0.72)]">{rating.description}</p>
                </div>
              );
            })}
          </div>
        </section>
        </SectionCurtain>

        {/* ── Disclaimer (2026-05-17 P2-05: 자본시장법 §49 광고 표시) ── */}
        <SectionCurtain>
        <section className="mb-12">
          <DisclaimerBanner type="signal" theme="dark" />
        </section>
        </SectionCurtain>

        {/* ── CTA ── */}
        <SectionCurtain>
        <section className="text-center py-12 px-6 rounded-sm border border-[rgba(184,149,106,0.18)] bg-[rgba(184,149,106,0.04)]">
          <h2 className="font-[var(--font-display)] italic text-2xl font-medium text-[var(--pq-ivory)] mb-3">
            Screen stocks with CAN SLIM
          </h2>
          <p className="text-[rgba(245,240,232,0.62)] mb-6 max-w-md mx-auto">
            We automate the research that used to take hours. Sign up and start
            screening stocks in seconds.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-sm bg-[var(--pq-bronze)] text-[var(--pq-ink)] text-sm font-semibold hover:bg-[var(--pq-bronze-light)] transition-all"
          >
            Try the Screener
            <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
        </SectionCurtain>
      </main>
    </div>
  );
}
