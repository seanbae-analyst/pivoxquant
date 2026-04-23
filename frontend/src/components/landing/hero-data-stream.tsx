"use client";

/**
 * HeroDataStream — sheets of paper flowing down behind the flip deck.
 * -----------------------------------------------------------------------
 * Five translucent ivory "reports" ride a 30 s vertical loop, each with
 * its own phase offset so they never bunch. Each sheet shows blurred
 * serif lines (legal-safe copy only — no buy/sell/recommend language)
 * and a mock monospace ticker block.
 *
 * Layering (lowest → highest):
 *   • aurora / dot pattern / film grain / this stream / flip deck
 *
 * This component sits *behind* ReportFlipDeck at z-[1]. It is
 * `aria-hidden`, decorative, does not capture pointer events.
 *
 * Reduced motion
 *   • Sheets render at their resting positions (no vertical flow).
 *
 * Performance
 *   • Single CSS keyframe drives the flow (GPU composited transform).
 *   • `content-visibility: auto` on each sheet so offscreen sheets
 *     skip rendering work.
 */

import { useReducedMotion } from "motion/react";

type Sheet = {
  id: string;
  title: string;
  subtitle: string;
  ticker: string;
  /** 0–1 horizontal position within the right column. */
  lane: number;
  /** rotation in deg */
  tilt: number;
  /** animation-delay in s (negative => already in motion on mount) */
  delay: number;
  /** animation-duration in s */
  duration: number;
  /** sheet scale (depth cue) */
  scale: number;
  /** opacity max */
  alpha: number;
};

/* Legal-safe titles only. No buy/sell/recommend/advice/추천/조언. */
const SHEETS: Sheet[] = [
  {
    id: "morning-brief",
    title: "Morning Brief",
    subtitle: "April 22 · Pre-market research packet",
    ticker: "SPY  AAPL  NVDA  MSFT  GOOGL",
    lane: 0.18,
    tilt: -3.2,
    delay: -4,
    duration: 32,
    scale: 0.88,
    alpha: 0.5,
  },
  {
    id: "weekly-memo",
    title: "Weekly Memo",
    subtitle: "Portfolio posture · 4 holdings reviewed",
    ticker: "COST  UNH  LLY  V",
    lane: 0.56,
    tilt: 2.1,
    delay: -12,
    duration: 34,
    scale: 0.96,
    alpha: 0.62,
  },
  {
    id: "capital-review",
    title: "Capital Review",
    subtitle: "Risk budget · 7-gate pre-trade check",
    ticker: "VAR  CVaR  BETA  CORR",
    lane: 0.82,
    tilt: -1.4,
    delay: -22,
    duration: 30,
    scale: 0.82,
    alpha: 0.42,
  },
  {
    id: "portfolio-journal",
    title: "Portfolio Journal",
    subtitle: "Entries logged · 12 of 12 rationales",
    ticker: "JOURNAL · JNL · 2026Q2",
    lane: 0.32,
    tilt: 1.8,
    delay: -8,
    duration: 36,
    scale: 0.78,
    alpha: 0.38,
  },
  {
    id: "pulse-check",
    title: "Pulse Check",
    subtitle: "Behavioral tilt · disposition signal flat",
    ticker: "PULSE · NEUTRAL · 0.12σ",
    lane: 0.68,
    tilt: -2.6,
    delay: -18,
    duration: 28,
    scale: 0.86,
    alpha: 0.48,
  },
];

function SheetCard({ sheet, reduced }: { sheet: Sheet; reduced: boolean }) {
  const style: React.CSSProperties = {
    position: "absolute",
    top: 0,
    left: `${sheet.lane * 100}%`,
    width: "clamp(170px, 22vw, 240px)",
    transform: `translateX(-50%) rotate(${sheet.tilt}deg) scale(${sheet.scale})`,
    transformOrigin: "center",
    opacity: reduced ? sheet.alpha * 0.7 : sheet.alpha,
    contentVisibility: "auto",
    containIntrinsicSize: "300px 220px",
    animation: reduced
      ? undefined
      : `pq-paper-flow ${sheet.duration}s linear ${sheet.delay}s infinite`,
  };

  return (
    <div aria-hidden="true" className="pq-paper-sheet" style={style}>
      <div className="pq-paper-inner">
        <div className="pq-paper-head">
          <span className="pq-paper-mark" aria-hidden />
          <span className="pq-paper-title">{sheet.title}</span>
        </div>
        <div className="pq-paper-sub">{sheet.subtitle}</div>
        <div className="pq-paper-rule" aria-hidden />
        {/* Blurred "body copy" — 4 hairline rows */}
        <div className="pq-paper-lines">
          <span />
          <span style={{ width: "88%" }} />
          <span style={{ width: "72%" }} />
          <span style={{ width: "92%" }} />
          <span style={{ width: "64%" }} />
        </div>
        <div className="pq-paper-ticker">{sheet.ticker}</div>
        <div className="pq-paper-foot">
          <span>— Research note</span>
          <span>PQ · {sheet.id.slice(0, 3).toUpperCase()}</span>
        </div>
      </div>
    </div>
  );
}

export function HeroDataStream({ className }: { className?: string }) {
  const reduceMotion = useReducedMotion() ?? false;

  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 z-[1] overflow-hidden ${className ?? ""}`}
      style={{
        maskImage:
          "linear-gradient(to bottom, transparent 0%, black 14%, black 78%, transparent 100%)",
        WebkitMaskImage:
          "linear-gradient(to bottom, transparent 0%, black 14%, black 78%, transparent 100%)",
      }}
    >
      {SHEETS.map((s) => (
        <SheetCard key={s.id} sheet={s} reduced={reduceMotion} />
      ))}
    </div>
  );
}

export default HeroDataStream;
