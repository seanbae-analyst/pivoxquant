"use client";

/**
 * ReportFlipDeck — Hero v3 right column.
 * ------------------------------------------------------------------
 * A single tilted report cover that flips through the three flagship
 * PivoxQuant artifacts on a 6-second loop:
 *   Weekly Memo → Risk Board → Year-End Letter → …
 *
 * Desktop (lg+): true 3D Y-axis flip with perspective.
 * Mobile: simple cross-fade (perf + UX).
 *
 * Pauses on hover. Respects prefers-reduced-motion. Uses motion/react
 * only — no Three.js / GSAP / Lottie.
 *
 * Legal: editorial tone only. No advice / recommend language.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";

type Cover = {
  id: string;
  kicker: string;     // Editorial kicker (Q3 2025 · Equity Research)
  title: string;      // Serif display title
  subtitle: string;   // Deck line (italic)
  meta: string;       // Page count / cadence
  seal: string;       // Roman numeral / monogram
};

const COVERS: readonly Cover[] = [
  {
    id: "weekly-memo",
    kicker: "Week 16 · 2026 · Investor Memo",
    title: "Weekly Investor\nMemo",
    subtitle: "Five-page editorial dossier, drawn from your holdings.",
    meta: "5 pages · Delivered Mondays, 07:00 KST",
    seal: "I",
  },
  {
    id: "risk-board",
    kicker: "Q2 2026 · Risk & Compliance",
    title: "Risk Board",
    subtitle: "Seven-layer defensive posture, updated as markets move.",
    meta: "7 layers · VaR · Tail · Correlation",
    seal: "II",
  },
  {
    id: "year-end",
    kicker: "FY 2025 · Annual Letter",
    title: "Year-End\nInvestor Letter",
    subtitle: "A reflective accounting — what the portfolio did, and why.",
    meta: "12 pages · Delivered January 15",
    seal: "III",
  },
] as const;

const CYCLE_MS = 6000;
const FLIP_MS = 1200;

function CoverFace({ cover }: { cover: Cover }) {
  return (
    <div
      className="pq-flip-surface absolute inset-0 flex flex-col overflow-hidden rounded-[6px]"
      style={{
        border: "1px solid rgba(139, 111, 71, 0.38)",
        boxShadow:
          "0 34px 80px -20px rgba(0,0,0,0.82), 0 2px 0 0 rgba(139,111,71,0.18), inset 0 0 0 1px rgba(255,255,255,0.35)",
      }}
    >
      {/* Bronze hairline inner frame */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-[10px] rounded-[3px]"
        style={{ border: "0.5px solid rgba(139, 111, 71, 0.32)" }}
      />

      {/* Top kicker */}
      <div className="relative z-10 flex items-start justify-between px-8 pt-8">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className="inline-block h-px w-6"
            style={{ backgroundColor: "rgba(111, 86, 54, 0.7)" }}
          />
          <span
            className="font-serif text-[9.5px] uppercase"
            style={{
              letterSpacing: "0.24em",
              color: "rgba(111, 86, 54, 0.95)",
            }}
          >
            PivoxQuant · Research Desk
          </span>
        </div>
        <span
          className="font-serif text-[10px]"
          style={{
            letterSpacing: "0.18em",
            color: "rgba(111, 86, 54, 0.7)",
          }}
        >
          {cover.seal}
        </span>
      </div>

      {/* Title + subtitle block, vertically anchored ~40% down */}
      <div className="relative z-10 mt-auto flex flex-col px-8 pb-10">
        <span
          className="mb-4 font-serif text-[10px] uppercase"
          style={{
            letterSpacing: "0.22em",
            color: "rgba(111, 86, 54, 0.85)",
          }}
        >
          {cover.kicker}
        </span>
        <h3
          className="mb-3 whitespace-pre-line font-serif"
          style={{
            fontSize: "clamp(22px, 2.4vw, 30px)",
            lineHeight: 1.08,
            letterSpacing: "-0.015em",
            color: "#2A1F13",
            fontStyle: "italic",
            fontWeight: 400,
          }}
        >
          {cover.title}
        </h3>
        <p
          className="mb-6 max-w-[280px] font-serif italic"
          style={{
            fontSize: "12.5px",
            lineHeight: 1.55,
            color: "rgba(42, 31, 19, 0.72)",
          }}
        >
          {cover.subtitle}
        </p>
        <div
          aria-hidden
          className="mb-3 h-px w-10"
          style={{ backgroundColor: "rgba(111, 86, 54, 0.55)" }}
        />
        <span
          className="font-mono text-[9.5px] uppercase tabular-nums"
          style={{
            letterSpacing: "0.18em",
            color: "rgba(111, 86, 54, 0.85)",
            fontFeatureSettings: '"tnum", "lnum"',
          }}
        >
          {cover.meta}
        </span>
      </div>

      {/* Bronze seal monogram, lower-right */}
      <div
        aria-hidden
        className="absolute bottom-7 right-7 flex h-11 w-11 items-center justify-center rounded-full"
        style={{
          border: "0.5px solid rgba(111, 86, 54, 0.55)",
          color: "rgba(111, 86, 54, 0.85)",
        }}
      >
        <span
          className="font-serif text-[13px]"
          style={{ letterSpacing: "0.08em", fontStyle: "italic" }}
        >
          PQ
        </span>
      </div>
    </div>
  );
}

export function ReportFlipDeck() {
  const reduceMotion = useReducedMotion();
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState<"front" | "flipping">("front");
  const [paused, setPaused] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const timerRef = useRef<number | null>(null);

  // Mobile detection — 2D cross-fade below lg (1024px).
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1023px)");
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  // Cycle loop. Skipped entirely when reduceMotion.
  useEffect(() => {
    if (reduceMotion) return;
    if (paused) return;

    timerRef.current = window.setTimeout(() => {
      setPhase("flipping");
      // Midway swap + return
      window.setTimeout(() => {
        setIdx((n) => (n + 1) % COVERS.length);
      }, FLIP_MS / 2);
      window.setTimeout(() => {
        setPhase("front");
      }, FLIP_MS);
    }, CYCLE_MS);

    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [idx, paused, reduceMotion]);

  const current = useMemo(() => COVERS[idx], [idx]);

  // ──────────────────────────────────────────────────────────────
  // Mobile: simple cross-fade, no perspective. Still cycles.
  // ──────────────────────────────────────────────────────────────
  if (isMobile) {
    return (
      <div
        className="relative mx-auto aspect-[4/5] w-full max-w-[400px]"
        aria-hidden="true"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
      >
        {/* Ambient bronze glow */}
        <div
          aria-hidden
          className="absolute inset-0 -z-10 opacity-55 blur-3xl"
          style={{
            background:
              "radial-gradient(ellipse at 50% 45%, rgba(139, 111, 71, 0.32) 0%, transparent 60%)",
          }}
        />
        <motion.div
          key={current.id}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="relative h-full w-full"
        >
          <CoverFace cover={current} />
        </motion.div>
      </div>
    );
  }

  // ──────────────────────────────────────────────────────────────
  // Desktop: 3D tilt + Y-axis flip.
  // Tilt pose: rotateY: -12, rotateX: 4 (back to this on "front").
  // ──────────────────────────────────────────────────────────────
  const restRotateY = -12;
  const restRotateX = 4;
  const midRotateY = 90; // 90 = edge-on, invisible

  const rotateY = phase === "flipping" ? midRotateY : restRotateY;

  return (
    <div
      className="relative mx-auto aspect-[4/5] w-full max-w-[460px]"
      style={{ perspective: "1400px" }}
      aria-hidden="true"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      {/* Ambient bronze glow behind the cover */}
      <div
        aria-hidden
        className="absolute inset-0 -z-10 opacity-60 blur-3xl"
        style={{
          background:
            "radial-gradient(ellipse at 50% 45%, rgba(139, 111, 71, 0.3) 0%, transparent 60%)",
        }}
      />

      {/* Tilted stage */}
      <motion.div
        initial={{ opacity: 0, rotateY: restRotateY, rotateX: restRotateX, y: 22 }}
        animate={{
          opacity: 1,
          rotateY,
          rotateX: restRotateX,
          y: 0,
        }}
        transition={{
          rotateY: {
            duration: FLIP_MS / 2000,
            ease: [0.65, 0, 0.35, 1],
          },
          opacity: { duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.15 },
          y: { duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.15 },
        }}
        className="relative h-full w-full"
        style={{
          transformStyle: "preserve-3d",
          transformOrigin: "50% 50%",
        }}
      >
        <CoverFace cover={current} />
      </motion.div>

      {/* Floor shadow — anchors the card in space */}
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-6 left-1/2 h-8 w-3/4 -translate-x-1/2 rounded-full blur-2xl"
        style={{
          background: "rgba(0, 0, 0, 0.55)",
          opacity: 0.55,
        }}
      />
    </div>
  );
}

export default ReportFlipDeck;
