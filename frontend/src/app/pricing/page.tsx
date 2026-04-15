"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { cn } from "@/lib/utils";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  Check,
  X,
  Crown,
  Zap,
  BarChart3,
  ChevronDown,
  ShieldAlert,
  ArrowLeft,
} from "lucide-react";

/* ── Tier data ── */

interface PlanFeature {
  label: string;
  free: string | boolean;
  pro: string | boolean;
  premium: string | boolean;
}

const PLAN_FEATURES: PlanFeature[] = [
  { label: "Stock tracking", free: "3 stocks", pro: "Unlimited", premium: "Unlimited" },
  { label: "Technical indicators", free: "5 basic", pro: "25+ advanced", premium: "58 full models" },
  { label: "AI Assistant queries", free: false, pro: "10/day", premium: "100/day" },
  { label: "Signal analysis", free: "Basic score", pro: "Full 4-pillar analysis", premium: "Full + historical" },
  { label: "Risk dashboard", free: false, pro: true, premium: true },
  { label: "Portfolio analytics", free: "Basic", pro: "Advanced", premium: "Advanced + benchmark" },
  { label: "Watchlist", free: "5 stocks", pro: "Unlimited", premium: "Unlimited" },
  { label: "AutoTrade", free: false, pro: false, premium: true },
  { label: "Portfolio optimization", free: false, pro: false, premium: true },
  { label: "Real-time alerts", free: false, pro: true, premium: true },
  { label: "Broker sync", free: false, pro: true, premium: true },
  { label: "Priority processing", free: false, pro: true, premium: true },
];

/* ── FAQ data ── */

interface FaqItem {
  q: string;
  a: string;
}

const FAQ_ITEMS: FaqItem[] = [
  {
    q: "Can I cancel my subscription anytime?",
    a: "Yes, you can cancel your subscription at any time. You will continue to have access to your paid features until the end of your current billing period. No questions asked.",
  },
  {
    q: "Is my financial data safe?",
    a: "Absolutely. We use bank-level encryption (AES-256) for all data at rest, and TLS 1.3 for data in transit. We never store your brokerage credentials directly. All broker connections use OAuth or API key-based authentication.",
  },
  {
    q: "What is included in the free plan?",
    a: "The free plan includes tracking up to 3 stocks with basic signal scores, 5 technical indicators, and basic portfolio analytics. It is a great way to experience PivoxQuant before committing to a paid plan.",
  },
  {
    q: "How does AutoTrade work?",
    a: "AutoTrade executes trades automatically based on your configured rules and signal thresholds. It requires a connected broker account and is available on the Premium plan. Please test with paper trading first.",
  },
  {
    q: "Do prices include VAT?",
    a: "Yes, all displayed prices include VAT. There are no hidden fees or additional charges. What you see is what you pay.",
  },
];

/* ── FAQ Accordion Item ── */

function FaqAccordion({ item }: { item: FaqItem }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-b border-slate-100 last:border-0">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center justify-between py-4 text-left"
        aria-expanded={open}
      >
        <span className="text-sm font-semibold text-slate-900 pr-4">
          {item.q}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </button>
      {open && (
        <p className="pb-4 text-sm text-slate-600 leading-relaxed">
          {item.a}
        </p>
      )}
    </div>
  );
}

/* ── Feature check/cross ── */

function FeatureValue({ value }: { value: string | boolean }) {
  if (value === true)
    return <Check className="h-4 w-4 text-emerald-500 mx-auto" />;
  if (value === false)
    return <X className="h-4 w-4 text-slate-300 mx-auto" />;
  return (
    <span className="text-xs font-medium text-slate-700 text-center block">
      {value}
    </span>
  );
}

/* ── Plan Card ── */

function PlanCard({
  name,
  price,
  originalPrice,
  period,
  description,
  features,
  cta,
  ctaHref,
  onCtaClick,
  highlighted,
  badge,
  icon,
}: {
  name: string;
  price: string;
  originalPrice?: string;
  period: string;
  description: string;
  features: string[];
  cta: string;
  ctaHref?: string;
  onCtaClick?: () => void;
  highlighted?: boolean;
  badge?: string;
  icon: React.ReactNode;
}) {
  const buttonClass = highlighted
    ? "w-full rounded-full bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition-all hover:bg-slate-800 active:scale-[0.97]"
    : "w-full rounded-full border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97]";

  return (
    <div
      className={cn(
        "sp-card relative flex flex-col p-6",
        highlighted && "ring-2 ring-purple-500/20 border-purple-200",
      )}
    >
      {badge && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="inline-flex items-center rounded-full bg-primary-gradient px-3 py-1 text-[11px] font-bold text-white">
            {badge}
          </span>
        </div>
      )}

      <div className="flex items-center gap-3 mb-4">
        <div
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-xl",
            highlighted ? "bg-primary-gradient" : "bg-slate-100",
          )}
        >
          <span className={highlighted ? "text-white" : "text-slate-400"}>
            {icon}
          </span>
        </div>
        <div>
          <p className="text-base font-bold text-slate-900">{name}</p>
          <p className="text-xs text-slate-500">{description}</p>
        </div>
      </div>

      <div className="mb-5">
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold text-slate-900">{price}</span>
          <span className="text-sm text-slate-500">{period}</span>
        </div>
        {originalPrice && (
          <p className="text-xs text-slate-400 mt-1">
            <span className="line-through">{originalPrice}</span>{" "}
            <span className="text-purple-600 font-semibold">
              Introductory price
            </span>
          </p>
        )}
      </div>

      <ul className="flex-1 space-y-2.5 mb-6">
        {features.map((feat) => (
          <li key={feat} className="flex items-start gap-2 text-sm text-slate-600">
            <Check className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
            <span>{feat}</span>
          </li>
        ))}
      </ul>

      {ctaHref ? (
        <Link href={ctaHref} className={buttonClass}>
          {cta}
        </Link>
      ) : (
        <button type="button" onClick={onCtaClick} className={buttonClass}>
          {cta}
        </button>
      )}
    </div>
  );
}

/* ── Page ── */

export default function PricingPage() {
  const [loadingCheckout, setLoadingCheckout] = useState<string | null>(null);

  const handleCheckout = useCallback(async (plan: string) => {
    setLoadingCheckout(plan);
    try {
      const result = await apiFetch<{ url: string }>(API.billing.createCheckout, {
        method: "POST",
        body: JSON.stringify({ plan }),
      });
      if (result.url) {
        window.location.href = result.url;
      }
    } catch {
      // If user is not authenticated, redirect to signup
      window.location.href = "/signup";
    } finally {
      setLoadingCheckout(null);
    }
  }, []);

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-[#fafafa]">
        {/* ── Top navigation ── */}
        <div className="mx-auto max-w-5xl px-4 py-4">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to home
          </Link>
        </div>

        <div className="mx-auto max-w-5xl px-4 pb-20">
          {/* ── Hero ── */}
          <div className="text-center mb-12">
            <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-3">
              Simple, transparent pricing.
            </h1>
            <p className="text-lg text-slate-500 max-w-md mx-auto">
              Start free. Upgrade when you are ready.
            </p>
          </div>

          {/* ── Plan Cards ── */}
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3 mb-16">
            <PlanCard
              name="Free"
              price="₩0"
              period="/mo"
              description="Get started with basics"
              icon={<BarChart3 className="h-5 w-5" />}
              features={[
                "Track up to 3 stocks",
                "5 basic technical indicators",
                "Basic signal scores",
                "Portfolio overview",
                "Community access",
              ]}
              cta="Get Started"
              ctaHref="/signup"
            />

            <PlanCard
              name="Pro"
              price="₩9,900"
              originalPrice="₩14,900/mo"
              period="/mo"
              description="For active investors"
              icon={<Crown className="h-5 w-5" />}
              highlighted
              badge="Most Popular"
              features={[
                "Unlimited stock tracking",
                "25+ advanced indicators",
                "AI Assistant (10 queries/day)",
                "Full 4-pillar signal analysis",
                "Risk dashboard & alerts",
                "Broker sync",
              ]}
              cta={loadingCheckout === "pro" ? "Loading..." : "Upgrade to Pro"}
              onCtaClick={() => handleCheckout("pro")}
            />

            <PlanCard
              name="Premium"
              price="₩19,900"
              period="/mo"
              description="Maximum performance"
              icon={<Zap className="h-5 w-5" />}
              features={[
                "Everything in Pro",
                "58 quantitative models",
                "AI Assistant (100 queries/day)",
                "AutoTrade with paper trading",
                "Portfolio optimization (HRP, MDP)",
                "Priority signal processing",
              ]}
              cta={
                loadingCheckout === "premium" ? "Loading..." : "Upgrade to Premium"
              }
              onCtaClick={() => handleCheckout("premium")}
            />
          </div>

          {/* ── Feature Comparison Table ── */}
          <div className="sp-card overflow-hidden mb-16">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="text-base font-bold text-slate-900">
                Feature Comparison
              </h2>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/50">
                    <th className="px-6 py-3 text-left font-semibold text-slate-500 text-xs uppercase tracking-wider">
                      Feature
                    </th>
                    <th className="px-4 py-3 text-center font-semibold text-slate-500 text-xs uppercase tracking-wider w-28">
                      Free
                    </th>
                    <th className="px-4 py-3 text-center font-semibold text-purple-600 text-xs uppercase tracking-wider w-28">
                      Pro
                    </th>
                    <th className="px-4 py-3 text-center font-semibold text-slate-500 text-xs uppercase tracking-wider w-28">
                      Premium
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {PLAN_FEATURES.map((feat, idx) => (
                    <tr
                      key={feat.label}
                      className={cn(
                        "border-b border-slate-50",
                        idx % 2 === 1 && "bg-slate-50/30",
                      )}
                    >
                      <td className="px-6 py-3 text-sm font-medium text-slate-700">
                        {feat.label}
                      </td>
                      <td className="px-4 py-3">
                        <FeatureValue value={feat.free} />
                      </td>
                      <td className="px-4 py-3 bg-purple-50/30">
                        <FeatureValue value={feat.pro} />
                      </td>
                      <td className="px-4 py-3">
                        <FeatureValue value={feat.premium} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── FAQ ── */}
          <div className="max-w-2xl mx-auto mb-16">
            <h2 className="text-xl font-bold text-slate-900 text-center mb-8">
              Frequently Asked Questions
            </h2>
            <div className="sp-card px-6">
              {FAQ_ITEMS.map((item) => (
                <FaqAccordion key={item.q} item={item} />
              ))}
            </div>
          </div>

          {/* ── VAT & Disclaimer ── */}
          <div className="text-center space-y-3">
            <p className="text-xs text-slate-500">
              All prices in KRW. VAT included. Cancel anytime.
            </p>
            <div className="mx-auto max-w-xl rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-start gap-2">
                <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-slate-400 mt-0.5" />
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Past performance does not guarantee future results. PivoxQuant
                  provides data-driven analysis tools, not investment advice. All
                  investment decisions are the sole responsibility of the user.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ErrorBoundary>
  );
}
