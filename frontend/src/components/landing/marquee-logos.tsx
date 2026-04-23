"use client";

/**
 * MarqueeLogos — benchmark-wordmark strip below hero.
 * ----------------------------------------------------
 *  • "Research cadence modeled after:" eyebrow.
 *  • Continuous left-scrolling wordmark row — SVG text only (no brand
 *    logos; we set tone via typographic wordmarks, legally safe).
 *  • Pauses on hover. Dims in reduced-motion.
 *  • Vantablack bg, ivory @ 0.36 opacity, bronze divider dots.
 */

import { useReducedMotion } from "motion/react";

const WORDMARKS = [
  "GOLDMAN RESEARCH",
  "McKINSEY QUARTERLY",
  "FINANCIAL TIMES",
  "MORGAN STANLEY DESK",
  "BLACKROCK SYSTEMATIC",
  "J.P. MORGAN EYE",
  "BRIDGEWATER DAILY",
  "ALLIANCEBERNSTEIN LEDGER",
];

export function MarqueeLogos() {
  const reduce = useReducedMotion();
  // Duplicate for seamless loop
  const track = [...WORDMARKS, ...WORDMARKS];

  return (
    <section
      aria-label="Research cadence benchmarks"
      className="relative overflow-hidden border-y"
      style={{
        backgroundColor: "#060606",
        borderColor: "rgba(184,149,106,0.16)",
      }}
    >
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-5 flex items-center justify-center gap-2.5">
          <span
            aria-hidden
            className="h-px w-8"
            style={{ backgroundColor: "rgba(184,149,106,0.7)" }}
          />
          <span
            className="font-serif uppercase"
            style={{
              color: "var(--pq-bronze)",
              fontSize: "10.5px",
              letterSpacing: "0.24em",
            }}
          >
            Research cadence modeled after
          </span>
          <span
            aria-hidden
            className="h-px w-8"
            style={{ backgroundColor: "rgba(184,149,106,0.7)" }}
          />
        </div>

        {/* Mask gradient edges */}
        <div
          className="relative overflow-hidden"
          style={{
            maskImage:
              "linear-gradient(90deg, transparent 0%, black 10%, black 90%, transparent 100%)",
            WebkitMaskImage:
              "linear-gradient(90deg, transparent 0%, black 10%, black 90%, transparent 100%)",
          }}
        >
          <div
            className="flex min-w-max items-center gap-14 will-change-transform"
            style={{
              animation: reduce ? "none" : "pq-marquee 42s linear infinite",
            }}
          >
            {track.map((name, i) => (
              <span
                key={`${name}-${i}`}
                className="inline-flex items-center gap-14 font-serif"
                style={{
                  color: "rgba(245,240,232,0.36)",
                  fontSize: "13.5px",
                  letterSpacing: "0.24em",
                  textTransform: "uppercase",
                  whiteSpace: "nowrap",
                }}
              >
                {name}
                <span
                  aria-hidden
                  className="inline-block h-1 w-1 rounded-full"
                  style={{ backgroundColor: "rgba(184,149,106,0.5)" }}
                />
              </span>
            ))}
          </div>
        </div>
      </div>

      <style jsx>{`
        @keyframes pq-marquee {
          0% {
            transform: translate3d(0, 0, 0);
          }
          100% {
            transform: translate3d(-50%, 0, 0);
          }
        }
      `}</style>
    </section>
  );
}

export default MarqueeLogos;
