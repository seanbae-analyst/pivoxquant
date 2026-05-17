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
 *
 *  2026-05-17 wave 12 frontend P1 (PR #432) — page is now a Server
 *  Component so it can `export const metadata` (Next.js disallows it
 *  in "use client" modules). useReducedMotion + motion.div live in
 *  the FeatureCardsGrid child client component.
 *
 *  2026-05-17 wave 13 (PR #446) — `iconKey` string instead of `icon`
 *  component. React Server Components cannot serialise component
 *  types across the RSC → client boundary (caught by `npm run build`
 *  prerender of /features after PR #432: "Functions cannot be passed
 *  directly to Client Components..."). The child component maps the
 *  key to the actual LucideIcon at render time.
 */

import type { Metadata } from "next";

import FeaturePageShell from "@/components/landing/feature-page-shell";
import {
  FeatureCardsGrid,
  type FeatureCard,
} from "./feature-cards-grid";

export const metadata: Metadata = {
  title: "기능 · Features",
  description:
    "PivoxQuant의 13개 기능 surface를 한눈에. 40-Model Engine, 8 CFO Personas, 7-Layer Risk Defense 등 리서치 데스크 전체 카탈로그.",
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
    iconKey: "Brain",
  },
  {
    href: "/features/personas",
    eyebrow: "Identity",
    title: "8 CFO Personas",
    description:
      "Growth, Value, Balanced, Income, Quant, and more — eight investor archetypes.",
    iconKey: "Users",
  },
  {
    href: "/features/dashboard",
    eyebrow: "Preview",
    title: "Dashboard Preview",
    description:
      "The research terminal — equity curve, signals, ledger, and risk board.",
    iconKey: "LineChart",
  },
  {
    href: "/features/explorer",
    eyebrow: "Catalogue",
    title: "Feature Explorer",
    description:
      "Browse the seventeen research artifacts, one at a time.",
    iconKey: "Compass",
  },
  {
    href: "/features/reports",
    eyebrow: "Research",
    title: "Sample Reports",
    description:
      "Weekly Memo, Earnings Pre-Brief, Risk Board deck — sample PDFs.",
    iconKey: "FileText",
  },
  {
    href: "/features/pre-trade",
    eyebrow: "Signature",
    title: "Pre-Trade Checklist",
    description:
      "Seven gates before any position change — friction by design.",
    iconKey: "Shield",
  },
  {
    href: "/features/global-desk",
    eyebrow: "Signature",
    title: "Korea × US Desk",
    description:
      "One pane. KRW and USD. Unified market feed for global portfolios.",
    iconKey: "Globe2",
  },
  {
    href: "/features/risk-defense",
    eyebrow: "Risk",
    title: "7-Layer Risk Defense",
    description:
      "VaR, correlation, VIX, tail, daily, sector, and cash gates.",
    iconKey: "Layers",
  },
  {
    href: "/features/quant-scoring",
    eyebrow: "Quant",
    title: "Quant Scoring",
    description:
      "Four-pillar composite — momentum, value, quality, and low-volatility.",
    iconKey: "BarChart3",
  },
  {
    href: "/features/canslim",
    eyebrow: "Screener",
    title: "CAN SLIM",
    description:
      "Seven-factor growth screener after William O'Neil's framework.",
    iconKey: "Target",
  },
  {
    href: "/features/profiles",
    eyebrow: "Onboarding",
    title: "Investor Profiles",
    description:
      "Twenty-question questionnaire that maps you to a persona.",
    iconKey: "Gavel",
  },
  {
    href: "/features/paper-trading",
    eyebrow: "Practice",
    title: "Paper Trading",
    description:
      "Rehearse decisions on a sandbox account. No real capital at risk.",
    iconKey: "CircuitBoard",
  },
  {
    href: "/features/ai-assistant",
    eyebrow: "AI Assistant",
    title: "AI Assistant",
    description:
      "Claude-powered research notes. Observational, never directive.",
    iconKey: "Sparkles",
  },
];

export default function FeaturesIndexPage() {
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
      <FeatureCardsGrid cards={FEATURE_CARDS} />
    </FeaturePageShell>
  );
}
