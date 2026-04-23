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
 *   KR sub  : 매일 아침 두 번. 매수 전 일곱 관문. …
 *   CTAs    : "Meet your CFO" / "See a sample"
 *
 * LCP discipline: the <h1> is rendered statically on the server with the
 * full phrase; only after hydration + viewport entry does the glyph split
 * take over (HeroTypography handles the cross-fade).
 *
 * Legal safe: no BUY/SELL/HOLD/recommend/advice/추천/조언 copy in any of
 * the ambient text (aurora/particles/data stream).
 */

import Link from "next/link";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
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

const ReportFlipDeck = dynamic(
  () => import("./report-flip-deck").then((m) => m.ReportFlipDeck),
  {
    ssr: false,
    loading: () => (
      <div
        aria-hidden
        className="relative mx-auto aspect-[4/5] w-full max-w-[460px]"
      />
    ),
  },
);

const HeroParticles = dynamic(
  () => import("./hero-particles").then((m) => m.HeroParticles),
  { ssr: false, loading: () => null },
);

const HeroDataStream = dynamic(
  () => import("./hero-data-stream").then((m) => m.HeroDataStream),
  { ssr: false, loading: () => null },
);

/* ────────────────────────────────────────────────
   Stats — count-up targets. `toRender` preserves the
   original text (e.g. "+23.2pp") so the visual width
   doesn't jump between the 0 state and the final state.
   ──────────────────────────────────────────────── */
type Stat = {
  label: string;
  value: string;
  /** Numeric target (null → don't animate, use `value` as-is). */
  target?: number;
  /** Formatter for the animated number. */
  format?: (n: number) => string;
  tone?: "pos";
};

const STATS: readonly Stat[] = [
  {
    label: "CAGR",
    value: "21.19%",
    target: 21.19,
    format: (n) => `${n.toFixed(2)}%`,
  },
  {
    label: "Sharpe",
    value: "0.94",
    target: 0.94,
    format: (n) => n.toFixed(2),
  },
  {
    label: "2022 Bear",
    value: "+23.2pp",
    target: 23.2,
    format: (n) => `+${n.toFixed(1)}pp`,
    tone: "pos",
  },
  {
    label: "Alpha",
    value: "+9.66%",
    target: 9.66,
    format: (n) => `+${n.toFixed(2)}%`,
    tone: "pos",
  },
] as const;

/** Scroll-triggered count-up. Honors prefers-reduced-motion. */
function useCountUp(target: number | undefined, enabled: boolean) {
  const [value, setValue] = useState(target ?? 0);
  const ref = useRef<HTMLSpanElement>(null);
  const firedRef = useRef(false);

  useEffect(() => {
    if (!enabled || target === undefined) return;
    setValue(0);
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting && !firedRef.current) {
            firedRef.current = true;
            const duration = 1400;
            const start = performance.now();
            const tick = (now: number) => {
              const t = Math.min(1, (now - start) / duration);
              // ease-out cubic
              const eased = 1 - Math.pow(1 - t, 3);
              setValue(target * eased);
              if (t < 1) requestAnimationFrame(tick);
              else setValue(target);
            };
            requestAnimationFrame(tick);
            io.disconnect();
          }
        }
      },
      { threshold: 0.3 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [target, enabled]);

  return { value, ref };
}

function StatValue({ stat, animate }: { stat: Stat; animate: boolean }) {
  const { value, ref } = useCountUp(stat.target, animate);
  const display =
    animate && stat.target !== undefined && stat.format
      ? stat.format(value)
      : stat.value;

  return (
    <span
      ref={ref}
      className="pq-stat-count font-mono text-[17px] leading-none sm:text-[19px]"
      style={{
        color: stat.tone === "pos" ? "#3C7A52" : "var(--pq-ivory)",
        letterSpacing: "-0.01em",
      }}
    >
      {display}
    </span>
  );
}

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
          <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1.22fr)_minmax(0,1fr)] lg:gap-16">
            {/* ─── LEFT: Copy column ─── */}
            <div className="relative z-[3] max-w-2xl">
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
              <HeroTypography
                id="pq-hero-heading"
                className="pq-hero-h1 pq-silver-matte mb-7 font-serif font-normal"
                startDelayMs={700}
                segments={[
                  { text: "Your CFO\u00A0" },
                  { text: "learns", cfo: true, br: true },
                  { text: "you." },
                ]}
              />

              {/* Subcopy — Korean (Living CFO voice) */}
              <p
                className={`mb-3 max-w-xl font-serif ${animate ? "pq-reveal" : ""}`}
                style={{
                  fontSize: "clamp(15px, 1.35vw, 17px)",
                  lineHeight: 1.65,
                  color: "rgba(245, 240, 232, 0.72)",
                  ...d(1400),
                }}
              >
                매일 아침 두 번. 매수 전 일곱 관문. 매주 금요일 한 장의 편지.
                2년 뒤 당신은 알게 된다. 이 앱이 당신의 투자 철학을 당신보다
                먼저 기억한다는 것을.
              </p>

              {/* Italic deck line — English */}
              <p
                className={`mb-9 max-w-xl font-serif italic ${animate ? "pq-reveal" : ""}`}
                style={{
                  fontSize: "clamp(13.5px, 1.15vw, 15px)",
                  lineHeight: 1.5,
                  letterSpacing: "0.005em",
                  color: "rgba(139, 111, 71, 0.85)",
                  ...d(1550),
                }}
              >
                Twice each morning. Seven gates before every trade. One letter
                each Friday. A personal CFO that studies you.
              </p>

              {/* ─── Stat strip ─── */}
              <div
                className={`mb-10 ${animate ? "pq-reveal" : ""}`}
                style={d(1700)}
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
                      <StatValue stat={s} animate={animate ?? false} />
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
              </div>

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
                  href="/samples/weekly_memo.pdf"
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

            {/* ─── RIGHT: Flip deck, over the paper-flow stream ─── */}
            <div
              className={`relative order-first flex w-full items-center justify-center lg:order-none ${animate ? "pq-reveal" : ""}`}
              style={d(2000)}
            >
              {/* Paper-flow stream — behind the deck */}
              <HeroDataStream />
              {/* The deck itself — 3D flip, visible in front */}
              <div className="relative z-[2] w-full">
                <ReportFlipDeck />
              </div>
            </div>
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
              fontSize: "10.5px",
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
