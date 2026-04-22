"use client";

/**
 * Hero — PivoxQuant landing Hero v2 (Goldman IC / Linear / Stripe tier).
 * -----------------------------------------------------------------------
 * Composition:
 *   - HeroSpotlight: bronze cursor-follow radial (aceternity pattern, motion v12)
 *   - FilmGrain: SVG fractalNoise overlay
 *   - Silver-matte headline (CSS, no GSAP)
 *   - PdfStackMockup: three real PivoxQuant artifact pages fanned out
 *
 * Palette: Vantablack #0A0A0A · Ivory #F5F0E8 · Bronze #8B6F47 (single accent).
 * Type:    Source Serif 4 (masthead, H1, body) · JetBrains Mono (stat numbers).
 * Copy:    English, research-framed. NO BUY/SELL/HOLD/recommend/advice.
 * Disclaimer: rendered inline (Bronze italic) per legal requirement.
 */

import Link from "next/link";
import { motion } from "motion/react";
import type { Variants } from "motion/react";
import { ArrowRight, FileText } from "lucide-react";

import { HeroSpotlight } from "./hero-spotlight";
import { FilmGrain } from "./film-grain";
import { PdfStackMockup } from "./pdf-stack-mockup";

/* ────────────────────────────────────────────────
   Motion
   ──────────────────────────────────────────────── */
const fadeUp: Variants = {
  hidden: { opacity: 0, y: 18 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.7, ease: [0.16, 1, 0.3, 1] },
  },
};
const stagger: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.09 } },
};

/* ────────────────────────────────────────────────
   Stats (backtest figures, tabular-nums)
   ──────────────────────────────────────────────── */
const STATS: readonly { label: string; value: string; tone?: "pos" }[] = [
  { label: "CAGR", value: "21.19%" },
  { label: "Sharpe", value: "0.94" },
  { label: "2022 Bear", value: "+23.2pp", tone: "pos" },
  { label: "Alpha", value: "+9.66%", tone: "pos" },
] as const;

/* ══════════════════════════════════════════════════
   HERO
   ══════════════════════════════════════════════════ */
export function Hero() {
  return (
    <section
      aria-labelledby="pq-hero-heading"
      className="relative isolate overflow-hidden"
      style={{
        backgroundColor: "var(--pq-ink)",
        color: "var(--pq-ivory)",
      }}
    >
      {/* ─── L1: Vantablack fill ─── already via inline style ─── */}

      {/* ─── L2: Dot pattern (16px, ivory @ 4%) ─── */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(245, 240, 232, 0.045) 1px, transparent 1px)",
          backgroundSize: "16px 16px",
          maskImage:
            "radial-gradient(ellipse at center, black 55%, transparent 100%)",
          WebkitMaskImage:
            "radial-gradient(ellipse at center, black 55%, transparent 100%)",
        }}
      />

      {/* ─── L3: Film grain ─── */}
      <FilmGrain opacity={0.035} blendMode="overlay" />

      {/* ─── L4: Bottom fade into ink ─── */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-40"
        style={{
          background:
            "linear-gradient(to bottom, transparent 0%, var(--pq-ink) 92%)",
        }}
      />

      {/* ─── Spotlight wrapper ─── content inside ─── */}
      <HeroSpotlight className="relative">
        <div className="relative mx-auto max-w-7xl px-5 pb-20 pt-28 sm:px-8 sm:pb-28 sm:pt-32 lg:px-10 lg:pb-32 lg:pt-36">
          <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1.22fr)_minmax(0,1fr)] lg:gap-16">
            {/* ─── LEFT: Copy column (55%) ─── */}
            <motion.div
              variants={stagger}
              initial="hidden"
              animate="visible"
              className="max-w-2xl"
            >
              {/* Masthead eyebrow */}
              <motion.div
                variants={fadeUp}
                className="mb-8 inline-flex items-center gap-2.5"
              >
                <span
                  aria-hidden
                  className="h-px w-7"
                  style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }}
                />
                <span
                  className="font-serif text-[11px] uppercase"
                  style={{
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                  }}
                >
                  PivoxQuant · Research Desk
                </span>
              </motion.div>

              {/* H1 — silver-matte */}
              <motion.h1
                id="pq-hero-heading"
                variants={fadeUp}
                className="pq-silver-matte mb-7 font-serif font-normal"
                style={{
                  fontSize: "clamp(2.5rem, 6vw, 4.75rem)",
                  lineHeight: 1.02,
                  letterSpacing: "-0.02em",
                }}
              >
                Your portfolio,
                <br />
                briefed like a&nbsp;CFO&rsquo;s.
              </motion.h1>

              {/* Subcopy */}
              <motion.p
                variants={fadeUp}
                className="mb-3 max-w-xl font-serif"
                style={{
                  fontSize: "clamp(16px, 1.45vw, 18px)",
                  lineHeight: 1.6,
                  color: "rgba(245, 240, 232, 0.72)",
                }}
              >
                17 institutional-grade research artifacts. Monthly memos, risk
                boards, year-end letters — drawn from your own holdings.
              </motion.p>

              {/* Italic deck line — sits under the subcopy like an IC masthead. */}
              <motion.p
                variants={fadeUp}
                className="mb-9 max-w-xl font-serif italic"
                style={{
                  fontSize: "clamp(13.5px, 1.15vw, 15px)",
                  lineHeight: 1.5,
                  letterSpacing: "0.005em",
                  color: "rgba(139, 111, 71, 0.85)",
                }}
              >
                A quiet operating system for private capital.
              </motion.p>

              {/* ─── Stat strip ─── */}
              <motion.div
                variants={fadeUp}
                className="mb-10"
              >
                <div
                  aria-hidden
                  className="mb-4 h-px w-full"
                  style={{ backgroundColor: "var(--pq-border)" }}
                />
                <ul className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
                  {STATS.map((s) => (
                    <li key={s.label} className="flex flex-col gap-1.5">
                      <span
                        className="font-serif text-[9.5px] uppercase leading-none"
                        style={{
                          letterSpacing: "0.22em",
                          color: "var(--pq-muted)",
                        }}
                      >
                        {s.label}
                      </span>
                      <span
                        className="font-mono tabular-nums text-[17px] leading-none sm:text-[19px]"
                        style={{
                          color:
                            s.tone === "pos" ? "#3C7A52" : "var(--pq-ivory)",
                          fontFeatureSettings: '"tnum", "lnum"',
                          letterSpacing: "-0.01em",
                        }}
                      >
                        {s.value}
                      </span>
                    </li>
                  ))}
                </ul>
                <p
                  className="mt-3 font-serif text-[10.5px] italic leading-relaxed"
                  style={{ color: "var(--pq-muted)" }}
                >
                  Backtest, 2014–2024 US equity universe. Past performance does
                  not guarantee future results.
                </p>
              </motion.div>

              {/* ─── CTAs ─── */}
              <motion.div
                variants={fadeUp}
                className="flex flex-wrap items-center gap-3"
              >
                <Link
                  href="/signup"
                  className="
                    group inline-flex h-12 items-center gap-2 rounded-sm px-6
                    text-[13.5px] font-medium tracking-wide
                    transition-transform duration-200
                    hover:-translate-y-px active:translate-y-0 active:scale-[0.99]
                  "
                  style={{
                    backgroundColor: "var(--pq-ivory)",
                    color: "var(--pq-ink)",
                    boxShadow:
                      "0 1px 0 0 rgba(245,240,232,0.3) inset, 0 8px 24px -8px rgba(245,240,232,0.25)",
                  }}
                >
                  Start 7-day trial
                  <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
                </Link>

                <a
                  href="/samples/sp500_backtest.pdf"
                  target="_blank"
                  rel="noopener"
                  className="
                    inline-flex h-12 items-center gap-2 rounded-sm border bg-transparent px-5
                    text-[13.5px] font-medium tracking-wide transition-colors duration-200
                  "
                  style={{
                    borderColor: "rgba(139, 111, 71, 0.5)",
                    color: "rgba(245, 240, 232, 0.88)",
                  }}
                >
                  <FileText className="h-4 w-4" />
                  View backtest PDF
                </a>
              </motion.div>

              {/* ─── Disclaimer footer (Bronze italic 10pt) ─── */}
              <motion.p
                variants={fadeUp}
                className="mt-10 border-t pt-6 font-serif text-[11px] italic leading-relaxed tracking-wide"
                style={{
                  borderColor: "var(--pq-border)",
                  color: "var(--pq-muted)",
                }}
              >
                <span style={{ color: "rgba(139, 111, 71, 0.9)" }}>— </span>
                Not investment advice. Informational research only. Past
                performance does not guarantee future results.
              </motion.p>
            </motion.div>

            {/* ─── RIGHT: PDF stack (45%) ─── */}
            <motion.div
              initial={{ opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.9,
                ease: [0.16, 1, 0.3, 1],
                delay: 0.15,
              }}
              className="relative order-first flex w-full items-center justify-center lg:order-none"
            >
              <PdfStackMockup />
            </motion.div>
          </div>
        </div>
      </HeroSpotlight>
    </section>
  );
}

export default Hero;
