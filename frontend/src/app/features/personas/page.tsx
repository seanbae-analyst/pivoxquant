"use client";

import FeaturePageShell from "@/components/landing/feature-page-shell";
import { SectionCurtain } from "@/components/landing/section-curtain";
import { PersonaShowcase } from "@/components/landing/persona-showcase";

export default function PersonasPage() {
  return (
    <FeaturePageShell
      eyebrow="Identity Layer · Eight Personas"
      title="A desk that speaks your investor language."
      deck="Twenty onboarding questions resolve you into one of eight personas. Every artifact — from the Weekly Memo to the Year-End Letter — is re-voiced around the persona you tested into. When you drift, the desk proposes a reclassification; you accept or decline."
      seeAlso={[
        {
          eyebrow: "Quiz",
          title: "Archetype Quiz",
          description: "Twenty questions. One honest portrait of how you invest.",
          href: "/features/personas#archetype",
        },
        {
          eyebrow: "Research",
          title: "Sample Reports",
          description: "Read a report rendered in each of the eight voices.",
          href: "/features/reports",
        },
        {
          eyebrow: "Architecture",
          title: "40-Model Engine",
          description: "The quant, risk, and AI stack feeding every artifact.",
          href: "/features/engine",
        },
      ]}
    >
      <SectionCurtain divider={false}>
        <PersonaShowcase />
      </SectionCurtain>

      <SectionCurtain>
      <section
        id="archetype"
        className="py-24 md:py-32"
        style={{ backgroundColor: "#080808" }}
      >
        <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <div className="mb-6 inline-flex items-center gap-2.5">
            <span
              aria-hidden
              className="h-px w-7"
              style={{ backgroundColor: "rgba(184,149,106,0.7)" }}
            />
            <span
              className="font-serif uppercase"
              style={{
                color: "var(--pq-bronze)",
                fontSize: "11px",
                letterSpacing: "0.22em",
              }}
            >
              Archetype Quiz
            </span>
          </div>
          <h2
            className="font-serif"
            style={{
              color: "var(--pq-ivory)",
              fontSize: "clamp(1.75rem, 3.6vw, 2.5rem)",
              lineHeight: 1.1,
              letterSpacing: "-0.02em",
              fontWeight: 500,
              marginBottom: 18,
            }}
          >
            Twenty questions. No scoring shame.
          </h2>
          <p
            className="font-serif"
            style={{
              color: "rgba(245,240,232,0.7)",
              fontSize: "15.5px",
              lineHeight: 1.65,
              maxWidth: "60ch",
              marginBottom: 28,
            }}
          >
            The quiz lives inside the onboarding flow. It classifies you without
            scoring you: there is no “good” persona, only the one your past
            decisions actually look like. You can retake it quarterly — or the
            desk will ask first if drift appears.
          </p>
          <a
            href="/signup"
            className="inline-flex items-center gap-2 rounded-sm px-6 py-3 font-serif transition-transform active:scale-[0.98]"
            style={{
              backgroundColor: "var(--pq-bronze)",
              color: "var(--pq-ink)",
              fontSize: "13.5px",
              letterSpacing: "0.02em",
            }}
          >
            Take the archetype quiz
          </a>
        </div>
      </section>
      </SectionCurtain>
    </FeaturePageShell>
  );
}
