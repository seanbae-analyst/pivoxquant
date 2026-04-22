"use client";

/**
 * PdfStackMockup — three PivoxQuant artifact pages fanned out.
 * --------------------------------------------------------------
 * Renders real PivoxQuant sample pages from /public/hero/*.svg (page-1
 * mockups mimicking the actual PDF layouts in samples/pdf/). No Spline,
 * no 3D, no Lottie — just three <img> cards staggered with CSS rotations
 * and a hover lift.
 *
 * Editorial rules:
 *  - No trading action language on the cards (POSITIVE/NEGATIVE/NEUTRAL only).
 *  - Each artifact is a research deliverable, not an advice surface.
 *  - Ivory paper (#FAF8F3) + bronze hairline + deep drop shadow.
 */

import { motion } from "motion/react";
import type { Variants } from "motion/react";

type Artifact = {
  id: string;
  src: string;
  title: string;
  meta: string;
};

// Ordered back → front for correct z-stacking.
const ARTIFACTS: readonly Artifact[] = [
  {
    id: "year-end",
    src: "/hero/year_end_letter_p1.svg",
    title: "Year-End Letter",
    meta: "12 pages · FY 2025",
  },
  {
    id: "risk-board",
    src: "/hero/risk_board_p1.svg",
    title: "Risk Board",
    meta: "7 layers · VaR · Tail",
  },
  {
    id: "weekly-memo",
    src: "/hero/weekly_memo_p1.svg",
    title: "Weekly Investor Memo",
    meta: "5 pages · Week 16",
  },
] as const;

// Fan-out geometry: rotate(-6deg), 0deg, rotate(+6deg) per spec.
const FAN = [
  { rotate: -6, x: -46, y: 40, scale: 0.92 }, // far back, left
  { rotate: 0, x: 0, y: 0, scale: 0.98 }, // middle
  { rotate: 6, x: 46, y: -20, scale: 1.02 }, // front, right
] as const;

const container: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.14, delayChildren: 0.2 } },
};

const card: Variants = {
  hidden: { opacity: 0, y: 24, rotate: 0 },
  visible: (i: number) => ({
    opacity: 1,
    y: FAN[i]?.y ?? 0,
    rotate: FAN[i]?.rotate ?? 0,
    transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] },
  }),
};

export function PdfStackMockup() {
  return (
    <div
      className="relative mx-auto aspect-[4/5] w-full max-w-[460px]"
      role="img"
      aria-label="Three PivoxQuant research artifacts: Year-End Letter, Risk Board, and Weekly Investor Memo"
    >
      {/* Ambient bronze glow behind the stack */}
      <div
        aria-hidden
        className="absolute inset-0 -z-10 opacity-60 blur-3xl"
        style={{
          background:
            "radial-gradient(ellipse at 50% 45%, rgba(139, 111, 71, 0.28) 0%, transparent 60%)",
        }}
      />

      <motion.div
        variants={container}
        initial="hidden"
        animate="visible"
        className="relative h-full w-full"
      >
        {ARTIFACTS.map((a, i) => {
          const pose = FAN[i];
          return (
            <motion.figure
              key={a.id}
              custom={i}
              variants={card}
              style={{
                transformOrigin: "50% 100%",
                left: `${pose.x}px`,
                top: 0,
                zIndex: i + 1,
                scale: pose.scale,
              }}
              whileHover={{ y: (pose.y ?? 0) - 6, transition: { duration: 0.25 } }}
              className="
                group absolute inset-0
                flex flex-col
                overflow-hidden rounded-[6px]
                border border-[color:var(--pq-bronze)]/35
                bg-[#FAF8F3]
                shadow-[0_30px_70px_-20px_rgba(0,0,0,0.78),0_2px_0_0_rgba(139,111,71,0.12)]
                transition-shadow duration-300
                hover:shadow-[0_38px_90px_-20px_rgba(0,0,0,0.85),0_2px_0_0_rgba(139,111,71,0.2)]
                will-change-transform
              "
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={a.src}
                alt=""
                aria-hidden
                className="block h-full w-full select-none object-cover"
                draggable={false}
              />

              {/* Bottom-edge label (artifact name) */}
              <figcaption
                className="
                  pointer-events-none absolute inset-x-0 bottom-0
                  flex items-center justify-between
                  bg-gradient-to-t from-[#0A0A0A]/55 to-transparent
                  px-3 py-2
                  opacity-0 transition-opacity duration-300
                  group-hover:opacity-100
                "
              >
                <span
                  className="font-serif text-[10px] uppercase tracking-[0.22em] text-[color:var(--pq-ivory)]"
                  style={{ fontFeatureSettings: '"tnum", "lnum"' }}
                >
                  {a.title}
                </span>
                <span
                  className="font-mono text-[9px] tabular-nums text-[color:var(--pq-ivory)]/75"
                  style={{ fontFeatureSettings: '"tnum", "lnum"' }}
                >
                  {a.meta}
                </span>
              </figcaption>
            </motion.figure>
          );
        })}
      </motion.div>
    </div>
  );
}

export default PdfStackMockup;
