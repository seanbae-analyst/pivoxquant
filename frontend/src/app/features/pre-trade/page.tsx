"use client";

import FeaturePageShell from "@/components/landing/feature-page-shell";
import { DepositionTeaser } from "@/components/landing/deposition-teaser";

export default function PreTradePage() {
  return (
    <FeaturePageShell
      eyebrow="Signature · Pre-Trade Checklist"
      title="Seven gates before any position change."
      deck="The Pre-Trade Checklist asks you — before you click — what you would say about this trade under oath. Seven gates: thesis, size, risk ceiling, correlation, catalyst, exit, and counter-thesis. The Deposition files your answers."
      seeAlso={[
        {
          eyebrow: "Signature",
          title: "Korea × US Desk",
          description: "One pane. KRW and USD. KIS, Alpaca, FMP.",
          href: "/features/global-desk",
        },
        {
          eyebrow: "Architecture",
          title: "40-Model Engine",
          description: "The risk and behavioral models feeding each gate.",
          href: "/features/engine",
        },
        {
          eyebrow: "Signature",
          title: "Journal Companion",
          description: "A private thinking partner. Closed beta.",
          href: "/companion",
        },
      ]}
    >
      <div id="deposition">
        <DepositionTeaser />
      </div>
    </FeaturePageShell>
  );
}
