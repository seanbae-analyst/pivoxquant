"use client";

/**
 * /features — Feature index page.
 * -------------------------------------------------------------
 *  • Wave 7 Task 4 (E2E P2 #4): /features was a 404 dead route.
 *    Subpaths (/features/engine, /features/personas, …) existed
 *    but the index did not — breaking nav fallbacks and SEO
 *    crawl discovery for the 13 feature surfaces.
 *  • Reuses FeaturePageShell so the chrome (TopNav, hero, see-also,
 *    CTA, disclaimer footer) is identical to /features/* descendants.
 *  • Body renders all 13 feature cards in a responsive grid so this
 *    page doubles as a sitemap-grade discovery index.
 *  • Design v3 lock-in: Vantablack ink, bronze accent, Playfair serif.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, type LucideIcon } from "lucide-react";
import {
  Layers,
  CircuitBoard,
  Compass,
  Users,
  FileText,
  LineChart,
  Shield,
  Globe2,
  Brain,
  Target,
  Sparkles,
  BarChart3,
  Gavel,
} from "lucide-react";

import FeaturePageShell from "@/components/landing/feature-page-shell";
import { Eyebrow } from "@/components/landing/eyebrow";
import { fadeUp } from "@/lib/motion";

type FeatureCard = {
  href: string;
  eyebrow: string;
  title: string;
  description: string;
  icon: LucideIcon;
};

// Mirrors top-nav.tsx NAV_GROUPS taxonomy + extends to cover the
// directories that don't appear in the mega-dropdown but ship as
// real /features/* routes (canslim, paper-trading, profiles,
// quant-scoring, risk-defense, ai-assistant).
const FEATURE_CARDS: readonly FeatureCard[] = [
  {
    href: "/features/engine",
    eyebrow: "Architecture",
    title: "40-Model Engine",
    description:
      "Identity, learning, and artifact — three strata that turn holdings into a research desk.",
    icon: Brain,
  },
  {
    href: "/features/personas",
    eyebrow: "Identity",
    title: "8 CFO Personas",
    description:
      "Growth, Value, Balanced, Income, Quant, and more — eight investor archetypes.",
    icon: Users,
  },
  {
    href: "/features/dashboard",
    eyebrow: "Preview",
    title: "Dashboard Preview",
    description:
      "The research terminal — equity curve, signals, ledger, and risk board.",
    icon: LineChart,
  },
  {
    href: "/features/explorer",
    eyebrow: "Catalogue",
    title: "Feature Explorer",
    description:
      "Browse the seventeen research artifacts, one at a time.",
    icon: Compass,
  },
  {
    href: "/features/reports",
    eyebrow: "Research",
    title: "Sample Reports",
    description:
      "Weekly Memo, Earnings Pre-Brief, Risk Board deck — sample PDFs.",
    icon: FileText,
  },
  {
    href: "/features/pre-trade",
    eyebrow: "Signature",
    title: "Pre-Trade Checklist",
    description:
      "Seven gates before any position change — friction by design.",
    icon: Shield,
  },
  {
    href: "/features/global-desk",
    eyebrow: "Signature",
    title: "Korea × US Desk",
    description:
      "One pane. KRW and USD. Unified market feed for global portfolios.",
    icon: Globe2,
  },
  {
    href: "/features/risk-defense",
    eyebrow: "Risk",
    title: "7-Layer Risk Defense",
    description:
      "VaR, correlation, VIX, tail, daily, sector, and cash gates.",
    icon: Layers,
  },
  {
    href: "/features/quant-scoring",
    eyebrow: "Quant",
    title: "Quant Scoring",
    description:
      "Four-pillar composite — momentum, value, quality, and low-volatility.",
    icon: BarChart3,
  },
  {
    href: "/features/canslim",
    eyebrow: "Screener",
    title: "CAN SLIM",
    description:
      "Seven-factor growth screener after William O'Neil's framework.",
    icon: Target,
  },
  {
    href: "/features/profiles",
    eyebrow: "Onboarding",
    title: "Investor Profiles",
    description:
      "Twenty-question questionnaire that maps you to a persona.",
    icon: Gavel,
  },
  {
    href: "/features/paper-trading",
    eyebrow: "Practice",
    title: "Paper Trading",
    description:
      "Rehearse decisions on a sandbox account. No real capital at risk.",
    icon: CircuitBoard,
  },
  {
    href: "/features/ai-assistant",
    eyebrow: "AI Assistant",
    title: "AI Assistant",
    description:
      "Claude-powered research notes. Observational, never directive.",
    icon: Sparkles,
  },
];

export default function FeaturesIndexPage() {
  const reduce = useReducedMotion();

  return (
    <FeaturePageShell
      eyebrow="Features · 13 Surfaces"
      title="Every page of the research desk."
      deck="Thirteen surfaces, one engine. Browse the artifacts your Living CFO can produce — from the 40-model engine to the seven-gate pre-trade checklist — and open any one to read it in full."
      seeAlso={[
        {
          eyebrow: "Architecture",
          title: "40-Model Engine",
          description:
            "Quant, risk, and AI models feeding every artifact.",
          href: "/features/engine",
        },
        {
          eyebrow: "Identity",
          title: "8 CFO Personas",
          description:
            "Eight investor identities. One desk that speaks them all.",
          href: "/features/personas",
        },
        {
          eyebrow: "Catalogue",
          title: "Feature Explorer",
          description:
            "All seventeen research artifacts, opened one at a time.",
          href: "/features/explorer",
        },
      ]}
    >
      <section
        className="py-20 md:py-28"
        style={{ backgroundColor: "var(--pq-ink)" }}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={reduce ? undefined : "hidden"}
            whileInView="visible"
            viewport={{ once: true, margin: "-80px" }}
            variants={fadeUp}
            className="mb-10 flex"
          >
            <Eyebrow>The catalogue</Eyebrow>
          </motion.div>

          <div
            data-testid="features-index-grid"
            className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3"
          >
            {FEATURE_CARDS.map((card, i) => (
              <motion.div
                key={card.href}
                initial={reduce ? undefined : { opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{
                  duration: 0.42,
                  delay: Math.min(i * 0.04, 0.24),
                  ease: [0.16, 1, 0.3, 1],
                }}
              >
                <Link
                  href={card.href}
                  data-testid={`feature-card-${card.href.replace("/features/", "")}`}
                  className="group relative flex h-full flex-col gap-3 overflow-hidden rounded-sm p-6 transition-all hover:-translate-y-0.5"
                  style={{
                    backgroundColor: "#0D0D0D",
                    border: "0.5px solid rgba(184,149,106,0.22)",
                  }}
                >
                  <span
                    aria-hidden
                    className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-0 transition-opacity duration-500 group-hover:opacity-100"
                    style={{
                      background:
                        "linear-gradient(90deg, transparent 0%, rgba(184,149,106,0.5) 50%, transparent 100%)",
                    }}
                  />

                  <span
                    className="inline-flex h-10 w-10 items-center justify-center rounded-sm"
                    style={{
                      backgroundColor: "rgba(184,149,106,0.1)",
                      border: "0.5px solid rgba(184,149,106,0.26)",
                      color: "var(--pq-bronze)",
                    }}
                  >
                    <card.icon className="h-4 w-4" aria-hidden />
                  </span>

                  <span
                    className="font-serif uppercase"
                    style={{
                      color: "var(--pq-bronze)",
                      fontSize: "var(--pq-text-eyebrow)",
                      letterSpacing: "0.22em",
                    }}
                  >
                    {card.eyebrow}
                  </span>

                  <h3
                    className="font-serif"
                    style={{
                      color: "var(--pq-ivory)",
                      fontSize: "var(--pq-text-h4)",
                      fontWeight: 500,
                      letterSpacing: "-0.01em",
                    }}
                  >
                    {card.title}
                  </h3>

                  <p
                    className="font-serif"
                    style={{
                      color: "rgba(245,240,232,0.6)",
                      fontSize: "var(--pq-text-body)",
                      lineHeight: 1.55,
                    }}
                  >
                    {card.description}
                  </p>

                  <span
                    className="mt-auto inline-flex items-center gap-1.5 pt-3 font-serif italic"
                    style={{
                      color: "var(--pq-bronze)",
                      fontSize: "var(--pq-text-body)",
                    }}
                  >
                    Open
                    <ArrowRight
                      className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-0.5"
                      aria-hidden
                    />
                  </span>
                </Link>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </FeaturePageShell>
  );
}
