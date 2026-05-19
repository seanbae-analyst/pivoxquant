import Link from "next/link";
import type { Metadata } from "next";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  CheckCircle2,
} from "lucide-react";
import { SectionCurtain } from "@/components/landing/section-curtain";

export const metadata: Metadata = {
  title: "How Quant Scoring Works",
  description:
    "Every stock gets a score from 0 to 100. Learn the 4 pillars behind PivoxQuant's quant scoring system.",
  alternates: { canonical: "/features/quant-scoring" },
};

/* ── Score range bar (v3: KR convention — carmine ▲ / indigo ▼ band) ── */
function ScoreBar() {
  return (
    <div className="w-full">
      <div className="relative h-3 rounded-sm overflow-hidden bg-[rgba(255,255,255,0.04)] border border-[var(--pq-ivory-line)]">
        <div className="absolute inset-y-0 left-0 w-[30%] bg-[rgba(122,160,200,0.55)]" />
        <div className="absolute inset-y-0 left-[30%] w-[20%] bg-[rgba(184,149,106,0.32)]" />
        <div className="absolute inset-y-0 left-[50%] w-[20%] bg-[rgba(184,149,106,0.5)]" />
        <div className="absolute inset-y-0 left-[70%] w-[30%] bg-[rgba(209,136,136,0.55)]" />
      </div>
      <div className="flex justify-between mt-2 text-pq-mono-sm font-mono tabular-nums text-[rgba(245,240,232,0.55)]">
        <span>0</span>
        <span>30</span>
        <span>50</span>
        <span>70</span>
        <span>100</span>
      </div>
      <div className="flex justify-between mt-1 text-pq-eyebrow uppercase tracking-[0.18em]">
        <span className="text-[var(--down)] font-medium">NEGATIVE</span>
        <span className="text-[rgba(245,240,232,0.55)] font-medium">NEUTRAL</span>
        <span className="text-[var(--up)] font-medium">POSITIVE</span>
      </div>
    </div>
  );
}

/* ── Pillar data ── */
const pillars = [
  {
    code: "TC",
    title: "Technical",
    count: "25 signals",
    question: "Does the chart compound momentum or weakness?",
  },
  {
    code: "FD",
    title: "Fundamental",
    count: "13 ratios",
    question: "Is the underlying business sound?",
  },
  {
    code: "SN",
    title: "Sentiment",
    count: "News tone",
    question: "What is the tape saying about this name?",
  },
  {
    code: "QM",
    title: "Quant Models",
    count: "40 models",
    question: "What do math models observe?",
  },
];

/* ── Technical indicators ── */
const technicalIndicators = [
  { name: "RSI", explanation: "Measures if a stock is overbought or oversold. Like checking if something is on sale or overpriced." },
  { name: "MACD", explanation: "Compares two moving averages to spot when momentum shifts direction. An early warning signal." },
  { name: "Bollinger Bands", explanation: "Shows if a stock's price is unusually high or low compared to its recent range." },
  { name: "Moving Averages", explanation: "Smooths out daily price noise so you can see the real trend underneath." },
  { name: "ADX", explanation: "Tells you how strong a trend is. High ADX means a clear direction, low means it is choppy." },
  { name: "Stochastic", explanation: "Similar to RSI but with a different formula. Confirms if a stock is stretched too far." },
  { name: "OBV (Volume)", explanation: "Tracks whether money is flowing into or out of a stock based on volume." },
  { name: "VWAP", explanation: "The average price weighted by volume. Institutional traders use this as their benchmark." },
];

/* ── Fundamental factors ── */
const fundamentalFactors = [
  { name: "P/E Ratio", explanation: "How many years of earnings would it take to pay back your investment? Lower is usually better." },
  { name: "Revenue Growth", explanation: "Is the company selling more this year than last year? Consistent growth is a great sign." },
  { name: "Profit Margin", explanation: "How much profit the company keeps from each dollar of revenue. Higher means more efficient." },
  { name: "Debt-to-Equity", explanation: "How much the company borrowed vs. what it owns. Too much debt is risky." },
  { name: "ROE", explanation: "How well the company uses your money to generate profit. Higher is better." },
  { name: "Free Cash Flow", explanation: "The actual cash left after running the business. Positive means the company is self-sustaining." },
];

export default function QuantScoringPage() {
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
          <span className="text-sm font-medium text-[var(--pq-ivory)]">Quant Scoring</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-20">
        {/* ── Disclaimer ── */}
        <DisclaimerBanner type="ai-analysis" className="mb-8" />

        {/* ── Title ── */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-sm bg-[rgba(184,149,106,0.08)] border border-[rgba(184,149,106,0.18)] mb-6">
            <BarChart3 className="w-6 h-6 text-[var(--pq-bronze)]" />
          </div>
          <h1 className="font-[var(--font-display)] italic text-3xl sm:text-4xl font-medium text-[var(--pq-ivory)] mb-4 tracking-tight">
            How Quant Scoring Works
          </h1>
          <p className="text-base text-[rgba(245,240,232,0.62)] max-w-xl mx-auto">
            Every stock gets a score from 0 to 100. Here is what goes into it.
          </p>
        </div>

        {/* ── What is a Quant Score? ── */}
        <SectionCurtain divider={false}>
        <section className="mb-16">
          <div className="rounded-sm border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-6 sm:p-8">
            <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-4">What is a Quant Score?</h2>
            <p className="text-[rgba(245,240,232,0.82)] leading-relaxed mb-2">
              Think of it as a <span className="font-semibold text-[var(--pq-ivory)]">health check for stocks</span>.
              Just like a doctor checks your blood pressure, heart rate, and cholesterol,
              we check 38 different &ldquo;vital signs&rdquo; of every stock.
            </p>
            <p className="text-[rgba(245,240,232,0.62)] text-sm leading-relaxed">
              The result? One simple number from 0 to 100 that tells you how healthy a stock looks
              right now, based on data instead of opinions.
            </p>
          </div>
        </section>
        </SectionCurtain>

        {/* ── Score Range ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-6">Score Range</h2>
          <div className="rounded-sm border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-6 sm:p-8">
            <ScoreBar />
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
              <div className="rounded-sm bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] px-4 py-3">
                <p className="font-mono text-2xl font-medium text-[var(--down)] mb-1 tabular-nums">0 &ndash; 30</p>
                <p className="text-sm text-[rgba(245,240,232,0.62)]">Negative signals outweigh positive ones. Caution advised.</p>
              </div>
              <div className="rounded-sm bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] px-4 py-3">
                <p className="font-mono text-2xl font-medium text-[var(--pq-bronze)] mb-1 tabular-nums">31 &ndash; 69</p>
                <p className="text-sm text-[rgba(245,240,232,0.62)]">Mixed signals. The stock could go either way.</p>
              </div>
              <div className="rounded-sm bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] px-4 py-3">
                <p className="font-mono text-2xl font-medium text-[var(--up)] mb-1 tabular-nums">70 &ndash; 100</p>
                <p className="text-sm text-[rgba(245,240,232,0.62)]">Strong positive signals across most indicators.</p>
              </div>
            </div>
          </div>
        </section>
        </SectionCurtain>

        {/* ── The 4 Pillars ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-6">The 4 Pillars</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {pillars.map((pillar, idx) => {
              const ordinal = String(idx + 1).padStart(2, "0");
              return (
                <div
                  key={pillar.title}
                  className="rounded-sm border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-5"
                >
                  <div className="flex items-start gap-4">
                    <div className="shrink-0 flex flex-col items-start gap-1">
                      <span className="font-[var(--font-serif)] text-pq-h5 tracking-[0.04em] text-[var(--pq-ivory)]">
                        {pillar.code}
                      </span>
                      <span className="font-mono text-pq-eyebrow uppercase tracking-[0.18em] text-[rgba(245,240,232,0.65)] tabular-nums">
                        {ordinal} / 04
                      </span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="text-sm font-semibold text-[var(--pq-ivory)] mb-1">{pillar.title}</h3>
                      <p className="text-pq-mono-sm font-medium uppercase tracking-[0.16em] text-[var(--pq-bronze)] mb-2">{pillar.count}</p>
                      <p className="text-sm text-[rgba(245,240,232,0.62)] italic">&ldquo;{pillar.question}&rdquo;</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
        </SectionCurtain>

        {/* ── Technical Indicators ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-2">Technical Indicators (25)</h2>
          <p className="text-sm text-[rgba(245,240,232,0.62)] mb-6">
            These analyze price movement, volume, and momentum patterns.
            Here are the key ones explained simply.
          </p>
          <div className="space-y-3">
            {technicalIndicators.map((ind) => (
              <div key={ind.name} className="flex items-start gap-3 p-4 rounded-sm bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)]">
                <div className="mt-0.5 shrink-0">
                  <CheckCircle2 className="w-4 h-4 text-[var(--pq-bronze)]" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-[var(--pq-ivory)]">{ind.name}</p>
                  <p className="text-sm text-[rgba(245,240,232,0.62)] leading-relaxed">{ind.explanation}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
        </SectionCurtain>

        {/* ── Fundamental Factors ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-2">Fundamental Factors (13)</h2>
          <p className="text-sm text-[rgba(245,240,232,0.62)] mb-6">
            These observe whether the underlying business compounds or contracts.
          </p>
          <div className="space-y-3">
            {fundamentalFactors.map((factor) => (
              <div key={factor.name} className="flex items-start gap-3 p-4 rounded-sm bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)]">
                <div className="mt-0.5 shrink-0">
                  <CheckCircle2 className="w-4 h-4 text-[var(--pq-bronze)]" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-[var(--pq-ivory)]">{factor.name}</p>
                  <p className="text-sm text-[rgba(245,240,232,0.62)] leading-relaxed">{factor.explanation}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
        </SectionCurtain>

        {/* ── CTA ── */}
        <SectionCurtain>
        <section className="text-center py-12 px-6 rounded-sm border border-[rgba(184,149,106,0.18)] bg-[rgba(184,149,106,0.04)]">
          <h2 className="font-[var(--font-display)] italic text-2xl font-medium text-[var(--pq-ivory)] mb-3">
            See scores for any stock — free
          </h2>
          <p className="text-[rgba(245,240,232,0.62)] mb-6 max-w-md mx-auto">
            Sign up in 30 seconds. No credit card required. Get instant quant scores for
            US and Korean stocks.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-sm bg-[var(--pq-bronze)] text-[var(--pq-ink)] text-sm font-semibold hover:bg-[var(--pq-bronze-light)] transition-all"
          >
            Get Started Free
            <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
        </SectionCurtain>
      </main>
    </div>
  );
}
