"use client";

/**
 * Hero — PivoxQuant landing Hero v4 (Cinematic).
 * -----------------------------------------------------------------------
 * v4 layers onto v3's CEO-approved copy:
 *   1. HeroAurora       — bronze "sunrise" that tracks the cursor
 *   2. HeroParticles    — slow ivory/bronze drifting motes (Canvas 2D)
 *   3. HeroTypography   — glyph-by-glyph H1 reveal (LCP-safe)
 *   4. HeroDataStream   — paper reports flowing behind the flip deck
 *   5. CtaInkBleed      — SVG ink-bleed on the primary CTA
 *   6. Scroll cue       — slim bronze pulse line (replaces chevron hint)
 *   7. Animated counters on the STATS strip (scroll-triggered)
 *   8. Cinematic entrance timeline (ticker → eyebrow → H1 → … → CTAs)
 *
 * CEO-customized copy (preserved verbatim):
 *   Eyebrow : "PivoxQuant · Living CFO"
 *   H1      : "Your CFO learns you." (italic + bronze glow on "learns")
 *   KR sub  : 매일 아침 두 번. 진입 전 일곱 관문. …
 *   CTAs    : "Meet your CFO" / "See a sample"
 *
 * LCP discipline: the <h1> is rendered statically on the server with the
 * full phrase; only after hydration + viewport entry does the glyph split
 * take over (HeroTypography handles the cross-fade).
 *
 * Legal safe: no BUY/SELL/HOLD/recommend/advice/추천/조언 copy in any of
 * the ambient text (aurora/particles/data stream).
 */

import dynamic from "next/dynamic";
import { useRef } from "react";
import { useReducedMotion } from "motion/react";
import { ArrowRight, FileText } from "lucide-react";

import { HeroSpotlight } from "./hero-spotlight";
import { HeroAurora } from "./hero-aurora";
import { HeroTypography } from "./hero-typography";
import { CtaInkBleed } from "./cta-ink-bleed";
import { FilmGrain } from "./film-grain";

/* ────────────────────────────────────────────────
   Dynamic imports — defer heavy, below-LCP UI.
   ──────────────────────────────────────────────── */
const MarketTicker = dynamic(
  () => import("./market-ticker").then((m) => m.MarketTicker),
  {
    ssr: false,
    loading: () => (
      <div
        aria-hidden
        style={{
          height: 32,
          borderBottom: "1px solid rgba(139, 111, 71, 0.22)",
          backgroundColor: "rgba(5, 5, 5, 0.78)",
        }}
      />
    ),
  },
);

const HeroParticles = dynamic(
  () => import("./hero-particles").then((m) => m.HeroParticles),
  { ssr: false, loading: () => null },
);

/* ══════════════════════════════════════════════════
   HERO v4
   ══════════════════════════════════════════════════ */
export function Hero() {
  const reduceMotion = useReducedMotion();
  const animate = !reduceMotion;
  const heroRef = useRef<HTMLElement>(null);

  const smoothScroll = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    const target = document.getElementById("pq-hero-anchor");
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Cinematic entrance delays (ms). Client-only via inline style so SSR
  // emits a static Hero; CSS animation kicks in after hydration.
  const d = (ms: number): React.CSSProperties =>
    animate ? { animationDelay: `${ms}ms` } : {};

  return (
    <section
      ref={heroRef}
      aria-labelledby="pq-hero-heading"
      className="relative isolate overflow-hidden"
      style={{
        backgroundColor: "#050505",
        color: "var(--pq-ivory)",
      }}
    >
      {/* ─── Ticker — thin strip at very top ─── */}
      <div className={animate ? "pq-reveal" : ""} style={d(200)}>
        <MarketTicker />
      </div>

      {/* ─── L0: Aurora — bronze radial, pointer-tracked ─── */}
      <HeroAurora trackTarget={heroRef} />

      {/* ─── L1: Dot pattern ─── */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-[1]"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(245, 240, 232, 0.05) 1px, transparent 1px)",
          backgroundSize: "16px 16px",
          maskImage:
            "radial-gradient(ellipse at center, black 40%, transparent 100%)",
          WebkitMaskImage:
            "radial-gradient(ellipse at center, black 40%, transparent 100%)",
        }}
      />

      {/* ─── L2: Drifting particles (Canvas 2D, off-screen pausable) ─── */}
      <HeroParticles />

      {/* ─── L3: Film grain — filmier (0.05 → 0.07) ─── */}
      <FilmGrain opacity={0.07} blendMode="overlay" />

      {/* ─── L4: Bottom fade into ink ─── */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-56 z-[2]"
        style={{
          background:
            "linear-gradient(to bottom, transparent 0%, #030303 92%)",
        }}
      />

      {/* ─── L5: Inner warm glow below the H1 ─── */}
      <div aria-hidden className="pq-inner-glow" />

      {/* ─── Spotlight wrapper ─── */}
      <HeroSpotlight className="relative">
        <div className="relative mx-auto max-w-7xl px-5 pb-24 pt-24 sm:px-8 sm:pb-32 sm:pt-28 lg:px-10 lg:pb-36 lg:pt-32">
          {/* 2026-04-26: right-column persona spotlight removed per CEO.
              2026-05-03: right column re-introduced as a static "Friday
              memo · sealed" mockup card to balance the H1 column on lg+
              screens (CEO note: "오른쪽이 너무 텅 비는데"). Mobile keeps
              the single editorial column for clean LCP. The card is
              non-interactive eye-candy — pure CSS, no API, no images. */}
          <div className="relative grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_auto] lg:gap-16">
            {/* ─── Editorial copy column (single, max-width capped) ─── */}
            <div className="relative z-[3] max-w-3xl">
              {/* Masthead eyebrow */}
              <div
                className={`mb-8 inline-flex items-center gap-2.5 ${animate ? "pq-reveal" : ""}`}
                style={d(350)}
              >
                <span
                  aria-hidden
                  className={`h-px ${animate ? "pq-eyebrow-grow" : "w-7"}`}
                  style={{
                    backgroundColor: "rgba(139, 111, 71, 0.7)",
                    width: animate ? "28px" : undefined,
                  }}
                />
                <span
                  className={`font-serif text-[11px] uppercase ${animate ? "pq-reveal" : ""}`}
                  style={{
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                    ...d(500),
                  }}
                >
                  PivoxQuant · Living CFO
                </span>
              </div>

              {/* H1 — LCP element. HeroTypography renders a plain span
                  statically, then swaps to a glyph layer after hydration. */}
              {/* 2026-05-03: pq-silver-matte removed from H1.
                  The class set `-webkit-text-fill-color: transparent` and
                  relied on `background: linear-gradient + background-clip: text`
                  for the visible color. When the gradient failed to paint
                  (Chrome on certain GPU stacks; observed live at pivoxquant.com)
                  the entire H1 rendered as transparent \u2192 invisible. The CEO
                  direction was Playfair + bronze accent on "learns"; the
                  silver-gradient effect was over-engineering. Solid ivory
                  via .pq-hero-h1 color is guaranteed to render. */}
              <HeroTypography
                id="pq-hero-heading"
                className="pq-hero-h1 mb-7 font-serif font-normal"
                startDelayMs={700}
                segments={[
                  { text: "Your CFO\u00A0" },
                  { text: "learns", cfo: true, br: true },
                  { text: "you." },
                ]}
              />

              {/* English deck line — primary subtitle (Korean removed per CEO,
                  2026-04-26: "Hero 영어로 하라고"). */}
              <p
                className={`mb-9 max-w-xl font-serif ${animate ? "pq-reveal-left" : ""}`}
                style={{
                  fontSize: "clamp(15px, 1.35vw, 18px)",
                  lineHeight: 1.55,
                  letterSpacing: "0.005em",
                  color: "rgba(245, 240, 232, 0.72)",
                  ...d(1400),
                }}
              >
                Morning memos. Pre-trade gates. A letter every Friday.
              </p>

              {/* Stat strip removed from Hero per CEO direction (2026-04-26).
                  Backtest numbers live on /features/engine and pricing pages.
                  Hero is now persona-focused — CFO learns you, that's it. */}

              {/* ─── CTAs — ink-bleed primary + ghost secondary ─── */}
              <div
                className={`flex flex-wrap items-center gap-3 ${animate ? "pq-reveal" : ""}`}
                style={d(1800)}
              >
                <CtaInkBleed href="/signup" variant="bronze">
                  Meet your CFO
                  <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
                </CtaInkBleed>

                <CtaInkBleed
                  href="/sample-reports/weekly-memo"
                  as="anchor"
                  variant="ghost"
                  target="_blank"
                  rel="noopener"
                  className="px-5"
                >
                  <FileText className="h-4 w-4" />
                  See a sample
                </CtaInkBleed>
              </div>

              {/* ─── Disclaimer footer ─── */}
              <p
                className={`mt-10 border-t pt-6 font-serif text-[11px] italic leading-relaxed tracking-wide ${animate ? "pq-reveal" : ""}`}
                style={{
                  borderColor: "var(--pq-border)",
                  color: "var(--pq-muted)",
                  ...d(1950),
                }}
              >
                <span style={{ color: "rgba(139, 111, 71, 0.9)" }}>— </span>
                Not investment advice. Informational research only. Past
                performance does not guarantee future results.
              </p>
            </div>

            {/* ─── Right column: 7-Layer Pre-Trade Gate (lg+ only) ───
                2026-05-03: previous Friday-memo card felt too decorative.
                Replaced with a static panel that previews the 7-Layer Risk
                Defense product surface (risk_defense.py) — the actual gate
                a user passes through before submitting any order. Bloomberg-
                terminal monospace + bronze status dots; italic labels keep
                editorial warmth. Compliance-safe: shows GATE STATUS, never
                advice or directional words. */}
            <aside
              aria-hidden
              className={`pq-gate-card hidden lg:block ${animate ? "pq-reveal-left" : ""}`}
              style={d(1100)}
            >
              <div className="pq-gate-card-frame">
                {/* Eyebrow + live ping */}
                <div className="pq-gate-card-head">
                  <span className="pq-gate-card-eyebrow">
                    <span aria-hidden className="pq-gate-card-rule" />
                    PivoxQuant · Today&rsquo;s Gate
                  </span>
                  <span aria-hidden className="pq-gate-card-ping">
                    <span className="pq-gate-card-ping-dot" />
                    <span className="pq-gate-card-ping-ring" />
                  </span>
                </div>

                {/* Time stamp */}
                <div className="pq-gate-card-time">
                  <span className="pq-gate-card-time-mono">09:14:22</span>
                  <span className="pq-gate-card-time-tz">KST</span>
                </div>

                {/* 7 layers */}
                <ul className="pq-gate-card-list">
                  {[
                    { label: "VaR (95%)", state: "ok" as const },
                    { label: "Correlation drift", state: "ok" as const },
                    { label: "VIX regime", state: "watch" as const },
                    { label: "Tail risk", state: "ok" as const },
                    { label: "Daily P & L", state: "ok" as const },
                    { label: "Sector cap", state: "ok" as const },
                    { label: "Cash buffer", state: "ok" as const },
                  ].map((row) => (
                    <li
                      key={row.label}
                      className={`pq-gate-row pq-gate-row--${row.state}`}
                    >
                      <span aria-hidden className="pq-gate-row-dot" />
                      <span className="pq-gate-row-label">{row.label}</span>
                      <span
                        aria-hidden
                        className="pq-gate-row-status"
                        data-state={row.state}
                      >
                        {row.state === "ok" ? "✓" : "⚠"}
                      </span>
                    </li>
                  ))}
                </ul>

                {/* Foot — aggregate + recheck */}
                <div className="pq-gate-card-foot">
                  <span className="pq-gate-card-foot-count">
                    <strong>6</strong> of 7 cleared
                  </span>
                  <span aria-hidden className="pq-gate-card-foot-dot">
                    &middot;
                  </span>
                  <span className="pq-gate-card-foot-recheck">
                    re-check 17:30
                  </span>
                </div>
              </div>
            </aside>

          </div>
        </div>

        {/* ─── Scroll cue — slim bronze pulse line, replaces v3 chevron. */}
        <a
          href="#pq-hero-anchor"
          onClick={smoothScroll}
          aria-label="Continue to next section"
          className="absolute bottom-8 left-1/2 z-[3] -translate-x-1/2 flex flex-col items-center gap-2"
          style={d(2500)}
        >
          <span
            className="font-serif italic"
            style={{
              fontSize: "12px",
              letterSpacing: "0.05em",
              color: "rgba(139, 111, 71, 0.65)",
            }}
          >
            Continue dossier
          </span>
          <span
            aria-hidden
            className={animate ? "pq-scroll-cue-line" : ""}
            style={
              animate
                ? undefined
                : {
                    width: 1,
                    height: 40,
                    background:
                      "linear-gradient(to bottom, transparent 0%, var(--pq-bronze) 50%, transparent 100%)",
                  }
            }
          />
        </a>
      </HeroSpotlight>

      {/* Anchor for smooth scroll target — reserves no layout space */}
      <div id="pq-hero-anchor" aria-hidden className="h-0 w-0" />
    </section>
  );
}

export default Hero;
