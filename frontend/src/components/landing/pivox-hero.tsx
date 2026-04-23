"use client";

/**
 * PivoxHero — Vantablack + Ivory + Bronze Hero Section.
 * -----------------------------------------------------
 * Composition of:
 *  - aceternity/hero-highlight style: dot pattern + mouse-follow bronze spotlight
 *  - easemize/cinematic-landing-hero style: silver-matte headline gradient
 *
 * Rules (enforced):
 *  - Language: English only, research-framed. No BUY/SELL/HOLD/recommend/advice.
 *  - Palette: Vantablack (#0A0A0A), Ivory (#F5F0E8), Bronze (#B8956A).
 *  - No GSAP / no 3D / no purple-violet-blue gradient.
 *  - Disclaimer footer rendered inside the section.
 */

import Link from "next/link";
import { useCallback } from "react";
import {
  motion,
  useMotionTemplate,
  useMotionValue,
  useReducedMotion,
} from "motion/react";
import type { Variants } from "motion/react";
import { ArrowRight, FileText } from "lucide-react";

import { ArtifactStackMockup } from "./artifact-stack-mockup";
import { StatStrip } from "./stat-strip";

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

export function PivoxHero() {
  const reduceMotion = useReducedMotion();

  // Bronze spotlight follows the cursor (aceternity pattern).
  const mouseX = useMotionValue(-1000);
  const mouseY = useMotionValue(-1000);
  const spotlight = useMotionTemplate`radial-gradient(480px circle at ${mouseX}px ${mouseY}px, rgba(139,111,71,0.22), transparent 72%)`;

  const onMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (reduceMotion) return;
      const { left, top } = e.currentTarget.getBoundingClientRect();
      mouseX.set(e.clientX - left);
      mouseY.set(e.clientY - top);
    },
    [mouseX, mouseY, reduceMotion]
  );

  return (
    <section
      aria-labelledby="pivox-hero-heading"
      onMouseMove={onMouseMove}
      className="relative isolate overflow-hidden bg-[#0A0A0A] text-[#F5F0E8]"
    >
      {/* ─── Background layer 1: dot pattern ─── */}
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(80,76,70,0.55) 1px, transparent 1px)",
          backgroundSize: "18px 18px",
          opacity: 0.28,
          maskImage:
            "radial-gradient(ellipse at center, black 55%, transparent 100%)",
          WebkitMaskImage:
            "radial-gradient(ellipse at center, black 55%, transparent 100%)",
        }}
      />

      {/* ─── Background layer 2: bronze mouse spotlight ─── */}
      <motion.div
        aria-hidden
        className="absolute inset-0 pointer-events-none transition-opacity duration-500"
        style={{ background: spotlight }}
      />

      {/* ─── Background layer 3: subtle film grain ─── */}
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none mix-blend-overlay opacity-[0.04]"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.96  0 0 0 0 0.94  0 0 0 0 0.91  0 0 0 0.6 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")",
        }}
      />

      {/* ─── Background layer 4: bottom fade ─── */}
      <div
        aria-hidden
        className="absolute inset-x-0 bottom-0 h-40 pointer-events-none"
        style={{
          background:
            "linear-gradient(to bottom, transparent 0%, #0A0A0A 90%)",
        }}
      />

      {/* ─── Content ─── */}
      <div className="relative mx-auto max-w-7xl px-5 sm:px-8 lg:px-10 pt-28 pb-20 sm:pt-32 sm:pb-28 lg:pt-36 lg:pb-32">
        <div className="grid lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] gap-12 lg:gap-16 items-center">
          {/* ─ LEFT: Copy ─ */}
          <motion.div
            variants={stagger}
            initial="hidden"
            animate="visible"
            className="max-w-2xl"
          >
            {/* Eyebrow */}
            <motion.div
              variants={fadeUp}
              className="inline-flex items-center gap-2.5 mb-8"
            >
              <span
                aria-hidden
                className="h-px w-7 bg-[#B8956A]/70"
              />
              <span
                className="
                  font-sans text-[11px] uppercase
                  tracking-[0.22em]
                  text-[#B8956A]
                "
              >
                PivoxQuant · Research Desk
              </span>
            </motion.div>

            {/* Headline — silver-matte gradient */}
            <motion.h1
              id="pivox-hero-heading"
              variants={fadeUp}
              className="
                font-serif
                text-[2.5rem] sm:text-5xl lg:text-[4.25rem] xl:text-[4.75rem]
                leading-[1.02]
                tracking-[-0.02em]
                font-normal
                pivox-silver-matte
                mb-7
              "
            >
              Your portfolio,
              <br />
              briefed like a&nbsp;CFO&rsquo;s.
            </motion.h1>

            {/* Subcopy */}
            <motion.p
              variants={fadeUp}
              className="
                font-serif
                text-[17px] sm:text-[18px]
                leading-[1.55]
                text-[#F5F0E8]/70
                max-w-xl
                mb-10
              "
            >
              17 institutional-grade research artifacts. Weekly memos, risk
              boards, year-end letters — drawn from your own holdings.
            </motion.p>

            {/* Stat strip */}
            <motion.div variants={fadeUp} className="mb-10">
              <StatStrip />
            </motion.div>

            {/* CTAs */}
            <motion.div
              variants={fadeUp}
              className="flex flex-wrap items-center gap-3"
            >
              <Link
                href="/signup"
                className="
                  group inline-flex items-center gap-2
                  h-12 px-6
                  rounded-sm
                  bg-[#F5F0E8] text-[#0A0A0A]
                  text-[13.5px] font-medium tracking-wide
                  transition-transform duration-200
                  hover:translate-y-[-1px]
                  active:translate-y-0 active:scale-[0.99]
                  shadow-[0_1px_0_0_rgba(245,240,232,0.3)_inset,0_8px_24px_-8px_rgba(245,240,232,0.25)]
                "
              >
                Start 7-day trial
                <ArrowRight className="w-4 h-4 transition-transform duration-200 group-hover:translate-x-0.5" />
              </Link>

              <a
                href="#sample-report"
                className="
                  group inline-flex items-center gap-2
                  h-12 px-5
                  rounded-sm
                  bg-transparent
                  text-[#F5F0E8]/85
                  border border-[#B8956A]/50
                  text-[13.5px] font-medium tracking-wide
                  transition-colors duration-200
                  hover:text-[#F5F0E8] hover:border-[#B8956A]
                "
              >
                <FileText className="w-4 h-4" />
                View backtest PDF
              </a>
            </motion.div>

            {/* Disclaimer — prominent, below the fold but readable */}
            <motion.p
              variants={fadeUp}
              className="
                mt-10 pt-6
                border-t border-[#F5F0E8]/8
                text-[11px] leading-relaxed
                text-[#6B6B6B]
                tracking-wide
              "
            >
              <span className="text-[#B8956A]/80">— </span>
              Not investment advice. Past performance &ne; future results.
              Research tool only. PivoxQuant is not a licensed advisor.
            </motion.p>
          </motion.div>

          {/* ─ RIGHT: Artifact Stack ─ */}
          <motion.div
            initial={{ opacity: 0, y: 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
            className="relative w-full flex items-center justify-center order-first lg:order-none mb-4 lg:mb-0"
          >
            <ArtifactStackMockup />
          </motion.div>
        </div>
      </div>
    </section>
  );
}

export default PivoxHero;
