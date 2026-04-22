"use client";

/**
 * StatStrip — dense numeric strip under Hero headline
 * ----------------------------------------------------
 * Editorial tone: no hype, no gradient. JetBrains Mono tabular figures.
 * Values are past-backtest metrics — NOT forward projections.
 * A disclaimer line ("past performance != future results") renders below.
 */

import { motion } from "motion/react";
import type { Variants } from "motion/react";

type Stat = {
  label: string;
  value: string;
  tone?: "pos" | "neg" | "neutral";
};

const DEFAULT_STATS: readonly Stat[] = [
  { label: "CAGR", value: "15–21%", tone: "neutral" },
  { label: "Sharpe", value: "0.94", tone: "neutral" },
  { label: "2022 Bear", value: "+2%", tone: "pos" },
  { label: "Alpha", value: "+9.66%", tone: "pos" },
] as const;

const strip: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.3 } },
};

const cell: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] },
  },
};

export function StatStrip({ stats = DEFAULT_STATS }: { stats?: readonly Stat[] }) {
  return (
    <div className="w-full">
      <motion.ul
        variants={strip}
        initial="hidden"
        animate="visible"
        className="
          grid grid-cols-2 sm:grid-cols-4
          divide-y divide-x divide-[#1A1A1A]
          sm:divide-y-0
          border border-[#1A1A1A]
          rounded-sm
          bg-black/20
          backdrop-blur-[1px]
        "
      >
        {stats.map((s) => (
          <motion.li
            key={s.label}
            variants={cell}
            className="px-4 py-3 sm:py-3.5 flex flex-col gap-1"
          >
            <span
              className="
                text-[10px] leading-none uppercase
                tracking-[0.22em]
                text-[#6B6B6B]
                font-sans
              "
            >
              {s.label}
            </span>
            <span
              className="
                font-mono tabular-nums
                text-[15px] sm:text-[17px] leading-none
                tracking-tight
              "
              style={{
                color:
                  s.tone === "pos"
                    ? "#3C7A52"
                    : s.tone === "neg"
                    ? "#8A2B1E"
                    : "#F5F0E8",
                fontFeatureSettings: '"tnum", "lnum"',
              }}
            >
              {s.value}
            </span>
          </motion.li>
        ))}
      </motion.ul>
      <p className="mt-2 text-[10.5px] leading-relaxed text-[#6B6B6B] tracking-wide">
        Backtest figures, 2015–2024 S&amp;P 500 universe. Past performance is
        not indicative of future results.
      </p>
    </div>
  );
}

export default StatStrip;
