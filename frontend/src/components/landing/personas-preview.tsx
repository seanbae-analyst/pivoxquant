"use client";

/**
 * PersonasPreview — the three names the mirror uses, on the slim landing.
 * ----------------------------------------------------------------
 * 2026-09-13 rewrite. This section used to show four engine personas
 * with two-letter engine codes, named four more to make "eight in all", and
 * promised the mirror would speak "in the language of the one you picked".
 * All of that was wrong for the product that ships:
 *
 *   • The 8 engine persona codes must never appear in UI. Only the 3 disclosed
 *     buckets may — 성장형 / 균형형 / 수익형 (lib/cfo/hooks.ts
 *     PERSONA_TO_SURFACE, mirroring backend persona_analytics).
 *   • Onboarding v3 (2026-09-06) creates no type label. It records the user's
 *     five answers, and /mirror compares them with observed trades. Nobody
 *     "picks" a type.
 *
 * So the section now says exactly that: your answers stay in your words, and
 * when the mirror names a trading pattern it uses only the three buckets. The
 * one-line descriptions are the product's own SURFACE_TAGLINES wording.
 *
 * Palette-safe (Vantablack + Ivory + Bronze). 1-col mobile / 3-col desktop.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion";
import { useT } from "@/lib/locale";
import { useAuth } from "@/lib/auth";

const BUCKETS = ["growth", "balanced", "income"] as const;

export default function PersonasPreview() {
  const t = useT();
  const { user } = useAuth();
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
            color: "var(--pq-ivory-mid)",
            marginBottom: 56,
          }}
        >
          {t("landing.personas.description")}
        </motion.p>

        {/* Grid — the three disclosed buckets, nothing finer */}
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
          className="grid grid-cols-1 gap-6 md:grid-cols-3"
        >
          {BUCKETS.map((bucket, i) => (
            <motion.article
              key={bucket}
              variants={fadeUp}
              className="pq-persona-card-v2 group relative flex flex-col overflow-hidden rounded-sm p-6 md:p-7 transition-all duration-500 hover:-translate-y-1"
              style={{
                minHeight: 180,
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
              <span
                className="mb-4 font-mono tabular-nums"
                style={{
                  color: "rgba(184,149,106,0.78)",
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.22em",
                }}
              >
                {String(i + 1).padStart(2, "0")}
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
                {t(`landing.personas.buckets.${bucket}.name`)}
              </h3>
              <p
                className="font-serif"
                style={{
                  color: "var(--pq-ivory-muted)",
                  fontSize: "var(--pq-text-body)",
                  lineHeight: 1.55,
                }}
              >
                {t(`landing.personas.buckets.${bucket}.line`)}
              </p>
            </motion.article>
          ))}
        </motion.div>

        {/* Note + CTA */}
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
              color: "var(--pq-ivory-dim)",
              fontSize: "var(--pq-text-body)",
              maxWidth: 480,
            }}
          >
            {t("landing.personas.bucketsNote")}
          </p>
          {/* Same login split as hero.tsx — a signed-in user has already
              answered the five questions; send them to the mirror instead.
              Signed-out visitors go to /login, the unified auth entry. */}
          <Link
            href={user ? "/mirror" : "/login"}
            className="group inline-flex items-center gap-2 rounded-sm px-5 py-3 font-serif transition-colors"
            style={{
              backgroundColor: "transparent",
              border: "0.5pt solid rgba(184,149,106,0.5)",
              color: "var(--pq-ivory)",
              fontSize: "var(--pq-text-body)",
              letterSpacing: "0.02em",
            }}
          >
            {user ? t("landing.hero.ctaOpenMirror") : t("landing.personas.takeQuiz")}
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
