"use client";

/**
 * feature-cards-grid.tsx — client subtree extracted from page.tsx so
 * the page can be a Server Component + export metadata. The motion +
 * useReducedMotion bits live here; everything that doesn't need a
 * client runtime stays static on the parent.
 *
 * 2026-05-17 wave 12 frontend P1 (PR #432). See parent page.tsx for
 * the rationale.
 *
 * 2026-05-17 wave 13 PR #446 — RSC serialisation fix. React Server
 * Components cannot pass component types (LucideIcon function objects)
 * as props across the RSC → client boundary. The parent page now sends
 * an `iconKey: string` and this client component maps that key to the
 * actual icon. Avoids the prerender error:
 *   "Functions cannot be passed directly to Client Components unless
 *    you explicitly expose it by marking it with 'use server'."
 */

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import {
  ArrowRight,
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
  type LucideIcon,
} from "lucide-react";

import { Eyebrow } from "@/components/landing/eyebrow";
import { fadeUp, PQ_EASE, PQ_DUR_BASE } from "@/lib/motion";

/**
 * iconKey → LucideIcon registry. Keys are stable strings the parent
 * Server Component sends across the wire. If a key is unknown we
 * silently fall back to Compass so a missing entry never breaks the
 * grid.
 */
const ICONS: Record<string, LucideIcon> = {
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
};

export type FeatureIconKey = keyof typeof ICONS;

export interface FeatureCard {
  href: string;
  eyebrow: string;
  title: string;
  description: string;
  /**
   * String key into the ICONS registry above. Strings serialise
   * cleanly across the RSC boundary (component types do not).
   */
  iconKey: FeatureIconKey;
}

export function FeatureCardsGrid({ cards }: { cards: readonly FeatureCard[] }) {
  const reduce = useReducedMotion();

  return (
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
          {cards.map((card, i) => {
            const Icon = ICONS[card.iconKey] ?? Compass;
            return (
              <motion.div
                key={card.href}
                initial={reduce ? undefined : { opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{
                  duration: PQ_DUR_BASE,
                  delay: Math.min(i * 0.04, 0.24),
                  ease: PQ_EASE,
                }}
              >
                <Link
                  href={card.href}
                  data-testid={`feature-card-${card.href.replace("/features/", "")}`}
                  className="group relative flex h-full flex-col gap-3 overflow-hidden rounded-sm p-6 transition-all hover:-translate-y-0.5"
                  style={{
                    backgroundColor: "var(--pq-card-veil)",
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
                    <Icon className="h-4 w-4" aria-hidden />
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
                    className="mt-auto inline-flex items-center gap-1.5 pt-3 font-serif"
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
            );
          })}
        </div>
      </div>
    </section>
  );
}
