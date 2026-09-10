"use client";

/**
 * PersonasPreview — selected persona cards on the slim landing.
 * ----------------------------------------------------------------
 * Surfaces Growth / Value / Balanced / Beginner — the four the onboarding
 * quiz resolves to most often in the first cohort — and ends with a link
 * into the quiz itself. The per-card "sample report" links and the
 * /features/personas showcase went with the surfaces they pointed at.
 *
 * Palette-safe (Vantablack + Ivory + Bronze). 1-col mobile / 2-col tablet
 * / 4-col desktop. 21st.dev polish: gradient bronze border on hover,
 * itemized micro-ledger numbering.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion";
import { useT } from "@/lib/locale";

type PreviewPersona = {
  code: string;
  en: string;
  kr: string;
  tagline: string;
  italic: string;
};

const FOUR: readonly PreviewPersona[] = [
  {
    code: "GR",
    en: "Growth",
    kr: "성장형",
    tagline: "High-beta compounders. Narrative-led.",
    italic: "미래 현금흐름에 베팅한다.",
  },
  {
    code: "VA",
    en: "Value",
    kr: "가치형",
    tagline: "Margin of safety. Balance-sheet first.",
    italic: "싼 값에 산다. 느리게 부자가 된다.",
  },
  {
    code: "BA",
    en: "Balanced",
    kr: "균형형",
    tagline: "Classic 60/40. Ballast over bravery.",
    italic: "평온한 복리.",
  },
  {
    code: "BE",
    en: "Beginner",
    kr: "입문형",
    tagline: "First year. Learning the ropes.",
    italic: "처음 내 돈을 굴려본다.",
  },
] as const;

export default function PersonasPreview() {
  const t = useT();
  const reduce = useReducedMotion();

  return (
    <section
      id="personas-preview"
      className="relative py-24 md:py-32"
      style={{ backgroundColor: "#050505", color: "var(--pq-ivory)" }}
    >
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        {/* Eyebrow */}
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mb-6 inline-flex items-center gap-2.5"
        >
          <span
            aria-hidden
            className="h-px w-7"
            style={{ backgroundColor: "rgba(184,149,106,0.7)" }}
          />
          <span
            className="font-serif uppercase"
            style={{
              color: "var(--pq-bronze)",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
            }}
          >
            {t("landing.personas.eyebrow")}
          </span>
        </motion.div>

        <motion.h2
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="pq-silver-matte font-serif"
          style={{
            fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
            lineHeight: 1.08,
            letterSpacing: "-0.02em",
            fontWeight: 500,
            marginBottom: 18,
          }}
        >
          {t("landing.personas.heading").split("\n")[0]}
          <br />
          {t("landing.personas.heading").split("\n")[1]}
        </motion.h2>

        <motion.p
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="font-serif max-w-xl"
          style={{
            fontSize: "clamp(15px, 1.3vw, 17px)",
            lineHeight: 1.65,
            color: "rgba(245,240,232,0.65)",
            marginBottom: 56,
          }}
        >
          {t("landing.personas.description")}
        </motion.p>

        {/* Grid */}
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
          className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4"
        >
          {FOUR.map((p, i) => (
            <motion.article
              key={p.code}
              variants={fadeUp}
              className="pq-persona-card-v2 group relative flex flex-col overflow-hidden rounded-sm p-6 md:p-7 transition-all duration-500 hover:-translate-y-1"
              style={{
                minHeight: 240,
                backgroundColor: "var(--pq-card-veil)",
                border: "0.5px solid rgba(184,149,106,0.24)",
              }}
            >
              {/* Gradient bronze corner accent */}
              <span
                aria-hidden
                className="pointer-events-none absolute right-0 top-0 h-16 w-16 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
                style={{
                  background:
                    "radial-gradient(ellipse at top right, rgba(184,149,106,0.22) 0%, transparent 70%)",
                }}
              />

              {/* Numeric index */}
              <div className="mb-4 flex items-baseline justify-between">
                <span
                  className="font-mono tabular-nums"
                  style={{
                    color: "rgba(184,149,106,0.78)",
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.22em",
                  }}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span
                  className="font-serif"
                  style={{
                    color: "rgba(245,240,232,0.50)",
                    fontSize: "var(--pq-text-eyebrow)",
                  }}
                >
                  {p.kr}
                </span>
              </div>

              <span
                className="mb-2 font-mono uppercase"
                style={{
                  color: "var(--pq-bronze)",
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.24em",
                }}
              >
                {p.code}
              </span>

              <h3
                className="font-serif"
                style={{
                  color: "var(--pq-ivory)",
                  fontSize: "var(--pq-text-quote)",
                  fontWeight: 500,
                  letterSpacing: "-0.01em",
                  marginBottom: 10,
                }}
              >
                {p.en}
              </h3>
              <p
                className="font-serif"
                style={{
                  color: "rgba(245,240,232,0.72)",
                  fontSize: "var(--pq-text-body)",
                  lineHeight: 1.55,
                  marginBottom: 8,
                }}
              >
                {p.tagline}
              </p>
              <p
                className="font-serif"
                style={{
                  color: "rgba(184,149,106,0.78)",
                  fontSize: "var(--pq-text-eyebrow)",
                  lineHeight: 1.5,
                  marginBottom: 24,
                }}
              >
                {p.italic}
              </p>

            </motion.article>
          ))}
        </motion.div>

        {/* See all CTA */}
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-40px" }}
          variants={fadeUp}
          className="mt-14 flex flex-col items-start gap-4 md:flex-row md:items-center md:justify-between"
        >
          <p
            className="font-serif"
            style={{
              color: "rgba(245,240,232,0.55)",
              fontSize: "var(--pq-text-body)",
              maxWidth: 480,
            }}
          >
            {t("landing.personas.alsoAvailable")}
          </p>
          <Link
            href="/signup"
            className="group inline-flex items-center gap-2 rounded-sm px-5 py-3 font-serif transition-colors"
            style={{
              backgroundColor: "transparent",
              border: "0.5pt solid rgba(184,149,106,0.5)",
              color: "var(--pq-ivory)",
              fontSize: "var(--pq-text-body)",
              letterSpacing: "0.02em",
            }}
          >
            {t("landing.personas.takeQuiz")}
            <ArrowRight
              className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5"
              style={{ color: "var(--pq-bronze)" }}
              aria-hidden
            />
          </Link>
        </motion.div>
      </div>

      {/* C — hover consistency: bronze border + bronze-08 fill on hover.
          Mirrors home-card.tsx pq-home-card-v2 pattern. */}
      <style jsx global>{`
        .pq-persona-card-v2:hover {
          border-color: var(--pq-bronze) !important;
          background-color: rgba(184, 149, 106, 0.025) !important;
        }
      `}</style>
    </section>
  );
}
