"use client";

/**
 * ArtifactStackMockup — Fan-out of 3 PDF artifact thumbnails.
 * -----------------------------------------------------------
 * Drop-in visual for the Hero right column. Pure CSS + framer-motion —
 * renders synthetic ivory PDF pages until `public/artifacts/*.png` thumbnails
 * are provided (generate via Chrome headless from /Pivoxquant report/*.pdf
 * and place as weekly_memo.png / risk_board.png / quarterly.png).
 *
 * Editorial rules (Vantablack + Ivory + Bronze):
 *  - No purple/violet/blue gradients.
 *  - No trading action language (BUY/SELL/HOLD). Shows neutral research labels.
 *  - Each card is a research artifact, not an advice surface.
 */

import { motion } from "motion/react";
import type { Variants } from "motion/react";

type Artifact = {
  id: string;
  title: string;
  subtitle: string;
  issued: string;
  meta: string;
  accent?: "plain" | "bronze";
  thumb?: string; // optional /artifacts/*.png override
};

const ARTIFACTS: readonly Artifact[] = [
  {
    id: "weekly-memo",
    title: "Weekly Investor Memo",
    subtitle: "Week 16 · Portfolio Review",
    issued: "ISSUED 2026-04-19",
    meta: "5 pages · PDF",
    accent: "bronze",
    thumb: "/artifacts/weekly_memo.png",
  },
  {
    id: "risk-board",
    title: "Risk Board",
    subtitle: "VaR · Correlation · Tail",
    issued: "ISSUED 2026-04-19",
    meta: "7 layers · PDF",
    accent: "plain",
    thumb: "/artifacts/risk_board.png",
  },
  {
    id: "quarterly",
    title: "Quarterly Self-Report",
    subtitle: "Q1 2026 · Your Holdings",
    issued: "ISSUED 2026-03-31",
    meta: "12 pages · PDF",
    accent: "plain",
    thumb: "/artifacts/quarterly.png",
  },
] as const;

// Fan-out geometry (desktop). Order bottom-up for correct z-stacking.
// Index 0 renders furthest back, index 2 closest to camera.
const FAN = [
  { rotate: -7, x: -28, y: 28, z: 0, scale: 0.92 },
  { rotate: 3, x: 0, y: 0, z: 1, scale: 0.98 },
  { rotate: -2, x: 24, y: -22, z: 2, scale: 1.02 },
] as const;

const container: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.14, delayChildren: 0.2 } },
};

const card: Variants = {
  hidden: { opacity: 0, y: 24, rotate: 0 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    rotate: FAN[i]?.rotate ?? 0,
    transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] },
  }),
};

function PdfPreviewBody({ a }: { a: Artifact }) {
  // Synthetic ivory-paper preview. Replaced by <img /> when a thumb PNG exists.
  return (
    <div className="relative flex-1 px-4 pb-4 pt-3">
      {/* header row */}
      <div className="flex items-center justify-between border-b border-[#D9D4C7] pb-2">
        <span className="font-serif text-[10px] tracking-[0.18em] uppercase text-[#1A1A1A]/70">
          PIVOXQUANT
        </span>
        <span className="font-mono text-[9px] tabular-nums text-[#1A1A1A]/50">
          {a.issued}
        </span>
      </div>

      {/* title */}
      <h4 className="font-serif text-[14px] leading-tight text-[#1A1A1A] mt-3 mb-1">
        {a.title}
      </h4>
      <p className="font-serif text-[10.5px] leading-snug text-[#1A1A1A]/60 mb-3">
        {a.subtitle}
      </p>

      {/* body placeholder lines */}
      <div className="space-y-1.5">
        {[96, 88, 92, 70, 82, 64].map((w, i) => (
          <div
            key={i}
            className="h-[3px] rounded-full bg-[#1A1A1A]/15"
            style={{ width: `${w}%` }}
          />
        ))}
      </div>

      {/* footnote */}
      <div className="flex items-center justify-between mt-4 pt-2 border-t border-[#D9D4C7]">
        <span className="font-mono text-[9px] tabular-nums text-[#1A1A1A]/55">
          {a.meta}
        </span>
        {a.accent === "bronze" ? (
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#B8956A]" />
        ) : (
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#1A1A1A]/25" />
        )}
      </div>
    </div>
  );
}

export function ArtifactStackMockup() {
  return (
    <div className="relative w-full max-w-[440px] aspect-[4/5] mx-auto">
      {/* ambient bronze glow behind the stack */}
      <div
        aria-hidden
        className="absolute inset-0 -z-10 blur-3xl opacity-60"
        style={{
          background:
            "radial-gradient(ellipse at 50% 45%, rgba(139,111,71,0.28) 0%, transparent 60%)",
        }}
      />

      <motion.div
        variants={container}
        initial="hidden"
        animate="visible"
        className="relative w-full h-full"
      >
        {ARTIFACTS.map((a, i) => {
          const pose = FAN[i];
          return (
            <motion.article
              key={a.id}
              custom={i}
              variants={card}
              style={{
                transformOrigin: "50% 100%",
                left: `${pose.x}px`,
                top: `${pose.y}px`,
                zIndex: pose.z,
                scale: pose.scale,
              }}
              className="
                absolute inset-0
                rounded-[6px]
                bg-[#FAF8F3]
                border border-[#B8956A]/35
                shadow-[0_24px_60px_-16px_rgba(0,0,0,0.7),0_2px_0_0_rgba(139,111,71,0.12)]
                overflow-hidden
                flex flex-col
                will-change-transform
              "
            >
              {/* optional real thumbnail fallback */}
              {a.thumb ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={a.thumb}
                  alt=""
                  aria-hidden
                  onError={(e) => {
                    // hide if asset absent — synthetic body renders instead
                    (e.currentTarget as HTMLImageElement).style.display = "none";
                  }}
                  className="absolute inset-0 w-full h-full object-cover opacity-0 data-[loaded=true]:opacity-100 transition-opacity duration-500"
                  onLoad={(e) => {
                    e.currentTarget.setAttribute("data-loaded", "true");
                    e.currentTarget.style.opacity = "1";
                    const body = e.currentTarget
                      .nextElementSibling as HTMLElement | null;
                    if (body) body.style.display = "none";
                  }}
                />
              ) : null}

              <PdfPreviewBody a={a} />
            </motion.article>
          );
        })}
      </motion.div>
    </div>
  );
}

export default ArtifactStackMockup;
