"use client";

/**
 * HeroArtifactPreview — Hero right-column visual (replaces ReportFlipDeck +
 * HeroDataStream). Shows a vertically stacked "living artifact" preview that
 * cycles through three product states (Weekly Memo / Earnings Pre-Brief /
 * Risk Board) with a smooth crossfade every ~5s.
 *
 * Design intent (CEO direction): a research-terminal panel rendered in
 * editorial typography on Vantablack — NOT a 3D card, NOT gold-on-gold.
 * Every text/background pair is contrast-checked:
 *   • Ivory (#F5F0E8 ~ 95% L) on Vantablack (#0A0A0A) → ~17:1 (AAA)
 *   • Bronze (#B8956A ~ 65% L) on Vantablack             → ~6.4:1 (AA body)
 *   • Bronze on bronze tint (rgba(184,149,106,0.08))     → ~5.9:1
 *   • No bronze fill behind bronze text anywhere.
 *
 * Palette guardrail: Vantablack / Bronze / Ivory only.
 * Legal: never uses BUY/SELL/HOLD/recommend/advice/추천/조언.
 * Motion: respects prefers-reduced-motion (cycle stops, first state shown).
 */

import { useEffect, useState } from "react";
import { useReducedMotion } from "motion/react";
import { FileText, ShieldHalf, CalendarClock } from "lucide-react";

type ArtifactState = {
  kicker: string;
  cadence: string;
  title: string;
  lede: string;
  rows: ReadonlyArray<{ label: string; value: string; tone?: "pos" | "neu" }>;
  footer: string;
  Icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
};

const STATES: readonly ArtifactState[] = [
  {
    kicker: "WEEKLY MEMO · WEEK 17",
    cadence: "Monday 06:00 KST",
    title: "Seven days on the page.",
    lede:
      "A reading of the example portfolio: what compounded, what drifted, the calendar that matters next.",
    rows: [
      { label: "Realized P&L", value: "+1.84%", tone: "pos" },
      { label: "Drift log", value: "2 names" },
      { label: "Earnings on book", value: "3 prints" },
      { label: "Memo length", value: "5 pages" },
    ],
    footer: "Observation only. No allocation instructions.",
    Icon: FileText,
  },
  {
    kicker: "EARNINGS PRE-BRIEF",
    cadence: "Eve of print · 19:30",
    title: "What the Street expects tomorrow.",
    lede:
      "Consensus bands, four-quarter guidance cadence, and the reaction pattern from the last eight prints.",
    rows: [
      { label: "Consensus EPS", value: "$2.10 ± 0.07" },
      { label: "Guidance trail", value: "+3.2pp avg" },
      { label: "Post-print drift", value: "±4.1% σ" },
      { label: "Brief length", value: "6 pages" },
    ],
    footer: "A reading of expectations — not a directional call.",
    Icon: CalendarClock,
  },
  {
    kicker: "RISK BOARD · Q2 CUT",
    cadence: "Quarterly · Board grade",
    title: "The deck a committee reads.",
    lede:
      "Seven defensive layers rendered as a board cut: concentration, tail, correlation, regime, drawdown.",
    rows: [
      { label: "Position Herfindahl", value: "0.18" },
      { label: "VaR (95, 1d)", value: "−1.6%" },
      { label: "Tail correlation", value: "0.32" },
      { label: "Deck length", value: "12 slides" },
    ],
    footer: "Formatted to open on a boardroom screen.",
    Icon: ShieldHalf,
  },
];

const CYCLE_MS = 5000;

export function HeroArtifactPreview() {
  const reduce = useReducedMotion();
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    if (reduce) return;
    const id = window.setInterval(() => {
      setIdx((i) => (i + 1) % STATES.length);
    }, CYCLE_MS);
    return () => window.clearInterval(id);
  }, [reduce]);

  const s = STATES[idx];

  return (
    <div
      className="relative mx-auto w-full max-w-[460px]"
      style={{ aspectRatio: "4/5" }}
      aria-label="PivoxQuant artifact preview — cycles through Weekly Memo, Earnings Pre-Brief, and Risk Board"
    >
      {/* Outer bronze hairline frame + ink fill */}
      <div
        className="absolute inset-0 overflow-hidden rounded-sm"
        style={{
          backgroundColor: "#0A0A0A",
          border: "0.5px solid rgba(184,149,106,0.32)",
          boxShadow:
            "0 1px 0 rgba(245,240,232,0.04) inset, 0 30px 80px -40px rgba(0,0,0,0.85)",
        }}
      >
        {/* Top status bar — always visible */}
        <div
          className="flex items-center justify-between px-5 py-3"
          style={{
            borderBottom: "0.5px solid rgba(184,149,106,0.18)",
            backgroundColor: "rgba(245,240,232,0.015)",
          }}
        >
          <div className="flex items-center gap-2">
            <span
              aria-hidden
              className="inline-block h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: "#B8956A" }}
            />
            <span
              className="font-serif uppercase"
              style={{
                fontSize: "9.5px",
                letterSpacing: "0.24em",
                color: "rgba(184,149,106,0.85)",
              }}
            >
              PivoxQuant · Desk
            </span>
          </div>
          <span
            className="font-mono"
            style={{
              fontSize: "9.5px",
              letterSpacing: "0.06em",
              color: "rgba(245,240,232,0.42)",
            }}
          >
            LIVE · {String(idx + 1).padStart(2, "0")} / {STATES.length}
          </span>
        </div>

        {/* Page grain overlay (very subtle) */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              "repeating-linear-gradient(0deg, rgba(245,240,232,0.018) 0px, rgba(245,240,232,0.018) 1px, transparent 1px, transparent 4px)",
            mixBlendMode: "screen",
          }}
        />

        {/* Cycling content — content swaps via state, transition handled by
            CSS opacity on inner elements. Outer container stays static so the
            outer pq-reveal hero entrance animation isn't fighting with us. */}
        <div className="relative h-[calc(100%-44px)] px-6 py-7">
            <div
              className="flex h-full flex-col"
              style={{ opacity: 1 }}
            >
              {/* Kicker row */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <s.Icon
                    className="h-3.5 w-3.5"
                    aria-hidden
                    /* lucide takes color from CSS color */
                  />
                  <span
                    className="font-serif uppercase"
                    style={{
                      fontSize: "10px",
                      letterSpacing: "0.22em",
                      color: "var(--pq-bronze, #B8956A)",
                    }}
                  >
                    {s.kicker}
                  </span>
                </div>
                <span
                  className="font-serif italic"
                  style={{
                    fontSize: "10.5px",
                    color: "rgba(245,240,232,0.55)",
                  }}
                >
                  {s.cadence}
                </span>
              </div>

              {/* Title — ivory on ink (~17:1 contrast) */}
              <h3
                className="mt-5 font-serif"
                style={{
                  fontSize: "22px",
                  lineHeight: 1.18,
                  letterSpacing: "-0.015em",
                  fontWeight: 500,
                  color: "var(--pq-ivory, #F5F0E8)",
                }}
              >
                {s.title}
              </h3>

              {/* Lede — slightly dimmed ivory on ink (~10:1) */}
              <p
                className="mt-3 font-serif"
                style={{
                  fontSize: "13px",
                  lineHeight: 1.6,
                  color: "rgba(245,240,232,0.72)",
                }}
              >
                {s.lede}
              </p>

              {/* Hairline divider */}
              <div
                aria-hidden
                className="my-5 h-px w-full"
                style={{ backgroundColor: "rgba(184,149,106,0.22)" }}
              />

              {/* Editorial rows — label / value */}
              <ul className="flex flex-col gap-2.5">
                {s.rows.map((r) => (
                  <li
                    key={r.label}
                    className="flex items-baseline justify-between gap-3"
                  >
                    <span
                      className="font-serif uppercase"
                      style={{
                        fontSize: "9.5px",
                        letterSpacing: "0.2em",
                        color: "rgba(245,240,232,0.5)",
                      }}
                    >
                      {r.label}
                    </span>
                    <span
                      aria-hidden
                      className="mx-2 flex-1"
                      style={{
                        borderBottom:
                          "0.5px dotted rgba(245,240,232,0.18)",
                        transform: "translateY(-3px)",
                      }}
                    />
                    <span
                      className="font-mono"
                      style={{
                        fontSize: "12.5px",
                        letterSpacing: "0.01em",
                        color:
                          r.tone === "pos"
                            ? "#7FB088"
                            : "var(--pq-ivory, #F5F0E8)",
                      }}
                    >
                      {r.value}
                    </span>
                  </li>
                ))}
              </ul>

              {/* Footer line */}
              <p
                className="mt-auto font-serif italic"
                style={{
                  fontSize: "11px",
                  lineHeight: 1.5,
                  color: "rgba(184,149,106,0.78)",
                  paddingTop: 18,
                  borderTop: "0.5px solid rgba(184,149,106,0.18)",
                }}
              >
                {s.footer}
              </p>
            </div>
        </div>

        {/* Cycle indicator bars (bottom edge) */}
        <div
          className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-center gap-1.5 pb-2.5"
          aria-hidden
        >
          {STATES.map((_, i) => (
            <span
              key={i}
              className="block h-px"
              style={{
                width: 22,
                backgroundColor:
                  i === idx
                    ? "rgba(184,149,106,0.85)"
                    : "rgba(184,149,106,0.22)",
                transition: "background-color 400ms ease",
              }}
            />
          ))}
        </div>
      </div>

      {/* Soft bronze halo (background only — never sits behind text) */}
      <div
        aria-hidden
        className="pointer-events-none absolute -inset-12 -z-10"
        style={{
          background:
            "radial-gradient(ellipse at 60% 40%, rgba(184,149,106,0.12) 0%, transparent 60%)",
        }}
      />
    </div>
  );
}

export default HeroArtifactPreview;
