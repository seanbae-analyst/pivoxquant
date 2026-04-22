import Link from "next/link";
import type { Metadata } from "next";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  LineChart,
  DollarSign,
  Newspaper,
  Brain,
  CheckCircle2,
} from "lucide-react";

export const metadata: Metadata = {
  title: "How Quant Scoring Works — PivoxQuant",
  description:
    "Every stock gets a score from 0 to 100. Learn the 4 pillars behind PivoxQuant's quant scoring system.",
};

/* ── Score range bar ── */
function ScoreBar() {
  return (
    <div className="w-full">
      <div className="relative h-4 rounded-full overflow-hidden bg-slate-100">
        <div className="absolute inset-y-0 left-0 w-[30%] bg-gradient-to-r from-red-400 to-red-300 rounded-l-full" />
        <div className="absolute inset-y-0 left-[30%] w-[20%] bg-gradient-to-r from-amber-300 to-amber-200" />
        <div className="absolute inset-y-0 left-[50%] w-[20%] bg-gradient-to-r from-emerald-300 to-emerald-200" />
        <div className="absolute inset-y-0 left-[70%] w-[30%] bg-gradient-to-r from-emerald-400 to-emerald-500 rounded-r-full" />
      </div>
      <div className="flex justify-between mt-2 text-xs font-medium text-slate-500">
        <span>0</span>
        <span>30</span>
        <span>50</span>
        <span>70</span>
        <span>100</span>
      </div>
      <div className="flex justify-between mt-0.5 text-[11px] text-slate-400">
        <span className="text-red-500 font-semibold">NEGATIVE</span>
        <span className="text-amber-500 font-semibold">NEUTRAL</span>
        <span className="text-emerald-500 font-semibold">POSITIVE</span>
      </div>
    </div>
  );
}

/* ── Pillar data ── */
const pillars = [
  {
    icon: LineChart,
    title: "Technical",
    count: "25 signals",
    question: "Is the chart showing momentum or weakness?",
    color: "bg-accent/10 text-accent",
  },
  {
    icon: DollarSign,
    title: "Fundamental",
    count: "13 ratios",
    question: "Is the business healthy?",
    color: "bg-blue-50 text-blue-600",
  },
  {
    icon: Newspaper,
    title: "Sentiment",
    count: "News tone",
    question: "What are people saying?",
    color: "bg-rose-50 text-rose-600",
  },
  {
    icon: Brain,
    title: "Quant Models",
    count: "58 models",
    question: "What do math models observe?",
    color: "bg-emerald-50 text-emerald-600",
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
          <span className="text-sm font-medium text-slate-700">Quant Scoring</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-20">
        {/* ── Disclaimer ── */}
        <DisclaimerBanner type="ai-analysis" theme="light" className="mb-8" />

        {/* ── Title ── */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-accent/10 mb-6">
            <BarChart3 className="w-7 h-7 text-accent" />
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">
            How <span className="gradient-text">Quant Scoring</span> Works
          </h1>
          <p className="text-lg text-slate-500 max-w-xl mx-auto">
            Every stock gets a score from 0 to 100. Here is what goes into it.
          </p>
        </div>

        {/* ── What is a Quant Score? ── */}
        <section className="mb-16">
          <div className="sp-card rounded-2xl p-6 sm:p-8">
            <h2 className="text-xl font-bold text-slate-900 mb-4">What is a Quant Score?</h2>
            <p className="text-slate-600 leading-relaxed mb-2">
              Think of it as a <span className="font-semibold text-slate-900">health check for stocks</span>.
              Just like a doctor checks your blood pressure, heart rate, and cholesterol,
              we check 38 different &ldquo;vital signs&rdquo; of every stock.
            </p>
            <p className="text-slate-500 text-sm leading-relaxed">
              The result? One simple number from 0 to 100 that tells you how healthy a stock looks
              right now, based on data instead of opinions.
            </p>
          </div>
        </section>

        {/* ── Score Range ── */}
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-6">Score Range</h2>
          <div className="bg-slate-50 rounded-2xl p-6 sm:p-8">
            <ScoreBar />
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
              <div className="rounded-xl bg-white border border-slate-100 px-4 py-3">
                <p className="text-2xl font-bold text-red-500 mb-1">0 &ndash; 30</p>
                <p className="text-sm text-slate-500">Negative signals outweigh positive ones. Caution advised.</p>
              </div>
              <div className="rounded-xl bg-white border border-slate-100 px-4 py-3">
                <p className="text-2xl font-bold text-amber-500 mb-1">31 &ndash; 69</p>
                <p className="text-sm text-slate-500">Mixed signals. The stock could go either way.</p>
              </div>
              <div className="rounded-xl bg-white border border-slate-100 px-4 py-3">
                <p className="text-2xl font-bold text-emerald-500 mb-1">70 &ndash; 100</p>
                <p className="text-sm text-slate-500">Strong positive signals across most indicators.</p>
              </div>
            </div>
          </div>
        </section>

        {/* ── The 4 Pillars ── */}
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-6">The 4 Pillars</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {pillars.map((pillar) => {
              const Icon = pillar.icon;
              return (
                <div key={pillar.title} className="sp-card rounded-2xl p-6">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-3 ${pillar.color.split(" ")[0]}`}>
                    <Icon className={`w-5 h-5 ${pillar.color.split(" ")[1]}`} />
                  </div>
                  <h3 className="text-base font-semibold text-slate-900 mb-1">{pillar.title}</h3>
                  <p className="text-xs font-medium text-accent mb-2">{pillar.count}</p>
                  <p className="text-sm text-slate-500 italic">&ldquo;{pillar.question}&rdquo;</p>
                </div>
              );
            })}
          </div>
        </section>

        {/* ── Technical Indicators ── */}
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-2">Technical Indicators (25)</h2>
          <p className="text-sm text-slate-500 mb-6">
            These analyze price movement, volume, and momentum patterns.
            Here are the key ones explained simply.
          </p>
          <div className="space-y-3">
            {technicalIndicators.map((ind) => (
              <div key={ind.name} className="flex items-start gap-3 p-4 rounded-xl bg-slate-50 border border-slate-100">
                <div className="mt-0.5 shrink-0">
                  <CheckCircle2 className="w-4.5 h-4.5 text-accent" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">{ind.name}</p>
                  <p className="text-sm text-slate-500 leading-relaxed">{ind.explanation}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Fundamental Factors ── */}
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-2">Fundamental Factors (13)</h2>
          <p className="text-sm text-slate-500 mb-6">
            These check if the actual business behind the stock is strong and growing.
          </p>
          <div className="space-y-3">
            {fundamentalFactors.map((factor) => (
              <div key={factor.name} className="flex items-start gap-3 p-4 rounded-xl bg-slate-50 border border-slate-100">
                <div className="mt-0.5 shrink-0">
                  <CheckCircle2 className="w-4.5 h-4.5 text-blue-500" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">{factor.name}</p>
                  <p className="text-sm text-slate-500 leading-relaxed">{factor.explanation}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── CTA ── */}
        <section className="text-center py-12 px-6 bg-slate-50 rounded-2xl">
          <h2 className="text-2xl font-bold text-slate-900 mb-3">
            See scores for any stock — free
          </h2>
          <p className="text-slate-500 mb-6 max-w-md mx-auto">
            Sign up in 30 seconds. No credit card required. Get instant quant scores for
            US and Korean stocks.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-all active:scale-[0.97]"
          >
            Get Started Free
            <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
      </main>
    </div>
  );
}
