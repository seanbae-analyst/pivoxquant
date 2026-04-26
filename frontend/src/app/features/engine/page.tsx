"use client";

import FeaturePageShell from "@/components/landing/feature-page-shell";
import { SectionCurtain } from "@/components/landing/section-curtain";
import { ThreeLayers } from "@/components/landing/three-layers";
import { LivingCfoLoop } from "@/components/landing/living-cfo-loop";
import EngineModelsDrawer from "@/components/landing/engine-models-drawer";

export default function EnginePage() {
  return (
    <FeaturePageShell
      eyebrow="Architecture · 40 Models"
      title="The engine behind every artifact."
      deck="Identity, learning, and artifact — three strata that turn your holdings into the kind of research desks produce at dawn. Forty quant, risk, and AI models run underneath, cited by name in every page of every PDF."
      seeAlso={[
        {
          eyebrow: "Catalogue",
          title: "Feature Explorer",
          description: "Browse all seventeen artifacts, one at a time.",
          href: "/features/explorer",
        },
        {
          eyebrow: "Research",
          title: "Sample Reports",
          description: "Weekly Memo, Earnings Pre-Brief, Risk Board deck.",
          href: "/features/reports",
        },
        {
          eyebrow: "Preview",
          title: "Dashboard Preview",
          description: "The research terminal — equity, signals, ledger.",
          href: "/features/dashboard",
        },
      ]}
    >
      <SectionCurtain divider={false} id="three-layers">
        <ThreeLayers />
      </SectionCurtain>
      <SectionCurtain id="loop">
        <LivingCfoLoop />
      </SectionCurtain>
      <SectionCurtain id="inventory">
        <EngineModelsDrawer />
      </SectionCurtain>
    </FeaturePageShell>
  );
}
