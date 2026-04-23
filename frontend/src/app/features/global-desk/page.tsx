"use client";

import FeaturePageShell from "@/components/landing/feature-page-shell";
import { KoreaUsDesk } from "@/components/landing/korea-us-desk";

export default function GlobalDeskPage() {
  return (
    <FeaturePageShell
      eyebrow="Signature · Korea × US Desk"
      title="One pane. Two currencies. Zero double-booking."
      deck="Alpaca, KIS, and FMP feed a single ledger. KRW and USD sit side by side. The Weekly Memo reads left-to-right across both markets, and the Risk Board deck runs the correlation matrix across the combined book."
      seeAlso={[
        {
          eyebrow: "Signature",
          title: "Pre-Trade Checklist",
          description: "Seven gates before any position change.",
          href: "/features/pre-trade",
        },
        {
          eyebrow: "Catalogue",
          title: "Feature Explorer",
          description: "Browse all seventeen artifacts.",
          href: "/features/explorer",
        },
        {
          eyebrow: "Architecture",
          title: "40-Model Engine",
          description: "FX, coverage, and data-quality models.",
          href: "/features/engine",
        },
      ]}
    >
      <KoreaUsDesk />
    </FeaturePageShell>
  );
}
