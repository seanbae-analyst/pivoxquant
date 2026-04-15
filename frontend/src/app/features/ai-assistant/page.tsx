import Link from "next/link";
import type { Metadata } from "next";
import {
  ArrowLeft,
  ArrowRight,
  Brain,
  MessageSquare,
  BarChart3,
  Target,
  PieChart,
  CheckCircle2,
  Sparkles,
  ShieldCheck,
  Zap,
  User,
} from "lucide-react";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";

export const metadata: Metadata = {
  title: "Your AI Investment Assistant — PivoxQuant",
  description:
    "Ask anything about your portfolio. Get answers in plain language, powered by Claude AI.",
};

/* ── Example conversations ── */
const conversations = [
  {
    icon: MessageSquare,
    question: "Why did my portfolio drop today?",
    answer:
      "Your portfolio dropped 2.3% mainly because your tech stocks (60% of portfolio) reacted to rising interest rate fears. NVDA fell 4.1% and AAPL fell 1.8%.",
    color: "bg-violet-50 text-violet-600",
  },
  {
    icon: BarChart3,
    question: "What do AAPL's quant metrics look like?",
    answer:
      "Current quant score: 72 (Positive). Technical: 68, Fundamental: 85. Strong fundamentals with $95B free cash flow. RSI at 68 suggests it may be slightly overbought short-term.",
    color: "bg-blue-50 text-blue-600",
  },
  {
    icon: PieChart,
    question: "What does my sector allocation look like?",
    answer:
      "Your current sector exposure: Technology 65%. Your risk profile target: 40% max per sector. Healthcare and consumer staples are currently underrepresented relative to your target allocation.",
    color: "bg-pink-50 text-pink-600",
  },
  {
    icon: Target,
    question: "What is my biggest risk right now?",
    answer:
      "Your top risk is sector concentration: 3 of your 5 holdings are in semiconductors. If chip stocks correct, you could see a 12-15% drawdown. Adding uncorrelated assets would help cushion that.",
    color: "bg-emerald-50 text-emerald-600",
  },
];

/* ── What AI Assistant knows ── */
const knowledgeSources = [
  { icon: User, label: "Your actual portfolio and positions" },
  { icon: Zap, label: "Real-time market data and news" },
  { icon: BarChart3, label: "58 quant model outputs" },
  { icon: ShieldCheck, label: "Your personal risk profile" },
  { icon: PieChart, label: "Sector and correlation analysis" },
  { icon: Target, label: "Historical performance patterns" },
];

export default function AiAssistantPage() {
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
          <span className="text-sm font-medium text-slate-700">AI Assistant</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-20">
        {/* ── Disclaimer ── */}
        <div className="mb-8">
          <DisclaimerBanner type="ai-analysis" />
        </div>

        {/* ── Title ── */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-violet-50 mb-6">
            <Brain className="w-7 h-7 text-violet-600" />
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">
            Your AI <span className="gradient-text">Investment Assistant</span>
          </h1>
          <p className="text-lg text-slate-500 max-w-xl mx-auto">
            Ask anything about your portfolio. Get answers in plain language.
          </p>
        </div>

        {/* ── What can AI Assistant do? ── */}
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-6">What can AI Assistant do?</h2>
          <div className="space-y-4">
            {conversations.map((conv) => {
              const Icon = conv.icon;
              return (
                <div key={conv.question} className="sp-card rounded-2xl p-6">
                  <div className="flex items-start gap-4">
                    <div className={`shrink-0 w-10 h-10 rounded-xl flex items-center justify-center ${conv.color.split(" ")[0]}`}>
                      <Icon className={`w-5 h-5 ${conv.color.split(" ")[1]}`} />
                    </div>
                    <div className="min-w-0 flex-1">
                      {/* User question */}
                      <div className="mb-3">
                        <p className="text-sm font-semibold text-slate-900">
                          &ldquo;{conv.question}&rdquo;
                        </p>
                      </div>
                      {/* AI answer */}
                      <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
                        <div className="flex items-center gap-1.5 mb-2">
                          <Sparkles className="w-3.5 h-3.5 text-violet-500" />
                          <span className="text-xs font-semibold text-violet-600">AI Assistant</span>
                        </div>
                        <p className="text-sm text-slate-600 leading-relaxed">{conv.answer}</p>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* ── Powered by Claude AI ── */}
        <section className="mb-16">
          <div className="bg-slate-50 rounded-2xl p-6 sm:p-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
                <Brain className="w-5 h-5 text-violet-600" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-900">Powered by Claude AI</h2>
                <p className="text-sm text-slate-500">Not a generic chatbot. It knows your portfolio.</p>
              </div>
            </div>
            <p className="text-sm text-slate-600 leading-relaxed mb-6">
              Unlike generic AI chatbots that give vague market commentary, our AI Assistant has access to
              your actual data. Every answer is personalized analysis based on your specific situation.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {knowledgeSources.map((source) => {
                return (
                  <div key={source.label} className="flex items-center gap-3 bg-white rounded-xl px-4 py-3 border border-slate-100">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                    <span className="text-sm text-slate-700">{source.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── How it works ── */}
        <section className="mb-16">
          <h2 className="text-xl font-bold text-slate-900 mb-6">How It Works</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { step: "01", title: "Ask a question", desc: "Type anything about your portfolio, a stock, or the market in plain English." },
              { step: "02", title: "AI analyzes your data", desc: "It checks your positions, quant scores, risk metrics, and real-time market data." },
              { step: "03", title: "Get clear answers", desc: "Receive personalized analysis explained simply, with specific numbers and data points." },
            ].map((item) => (
              <div key={item.step} className="sp-card rounded-2xl p-6 text-center">
                <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-violet-50 text-violet-600 text-sm font-bold mb-3">
                  {item.step}
                </div>
                <h3 className="text-sm font-semibold text-slate-900 mb-2">{item.title}</h3>
                <p className="text-sm text-slate-500">{item.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── CTA ── */}
        <section className="text-center py-12 px-6 bg-slate-50 rounded-2xl">
          <h2 className="text-2xl font-bold text-slate-900 mb-3">
            Try AI Assistant for free
          </h2>
          <p className="text-slate-500 mb-6 max-w-md mx-auto">
            Ask your first question today. No credit card required.
            Your assistant is ready when you are.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-all active:scale-[0.97]"
          >
            Try AI Assistant Free
            <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
      </main>
    </div>
  );
}
