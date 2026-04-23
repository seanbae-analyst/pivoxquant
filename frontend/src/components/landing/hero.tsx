"use client";

/**
 * Hero — PivoxQuant landing Hero v3 (Cinematic).
 * -----------------------------------------------------------------------
 * v3 upgrades on top of v2:
 *   1. MarketTicker (top strip, seamless marquee)
 *   2. CFO word — ivory → bronze glow via CSS keyframe (.pq-cfo-word)
 *   3. ReportFlipDeck (right column) — 3D Y-axis flip through 3 artifacts
 *   4. Scroll hint (bottom-center, "Continue dossier")
 *   5. Tighter Vantablack — narrower spotlight, deeper bottom fade,
 *      stronger film grain.
 *
 * Palette: Vantablack #050505/#0A0A0A · Ivory #F5F0E8 · Bronze #B8956A.
 * Type:    Source Serif 4 (masthead, H1, body) · JetBrains Mono (data).
 * Copy:    English, research-framed. NO BUY/SELL/HOLD/recommend/advice.
 * Disclaimer: inline (Bronze italic) per legal requirement.
 * A11y:    <h1> static for SEO; ticker/deck/hint are aria-hidden.
 * Perf:    CLS reserved (ticker 32px, H1 clamped, deck aspect 4:5).
 */

import Link from "next/link";
import dynamic from "next/dynamic";
import { motion, useReducedMotion } from "motion/react";
import type { Variants } from "motion/react";
import { ArrowRight, FileText, ChevronDown } from "lucide-react";

import { HeroSpotlight } from "./hero-spotlight";
import { FilmGrain } from "./film-grain";

/* ────────────────────────────────────────────────
   Dynamic imports — defer heavy, below-the-initial-paint UI.
   ------------------------------------------------
   MarketTicker and ReportFlipDeck together pull in motion/react runtime,
   matchMedia listeners, and large inline styles (~72 KB chunk per
   Lighthouse trace: _next/static/chunks/0nfangqn4qoja.js). They are NOT
   needed for the Largest Contentful Paint (the H1 "Your portfolio,
   briefed like a CFO's." is the LCP element).
   Splitting them out:
     - trims ~40-50 KB from the hero's critical JS path,
     - removes forced reflow during hydration (measured +200-400 ms
       Render Delay on mobile),
     - preserves visuals (fixed-height skeletons keep CLS = 0).
   `ssr: false` because both components read window.matchMedia inside
   useEffect and the content is decorative/aria-hidden. A fixed-size
   placeholder holds the layout until the chunk lands.
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

/* ────────────────────────────────────────────────
   Motion
   ──────────────────────────────────────────────── */
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

/* ────────────────────────────────────────────────
   Stats (backtest figures, tabular-nums)
   ──────────────────────────────────────────────── */
const STATS: readonly { label: string; value: string; tone?: "pos" }[] = [
  { label: "CAGR", value: "21.19%" },
  { label: "Sharpe", value: "0.94" },
  { label: "2022 Bear", value: "+23.2pp", tone: "pos" },
  { label: "Alpha", value: "+9.66%", tone: "pos" },
] as const;

/* ══════════════════════════════════════════════════
   HERO v3
   ══════════════════════════════════════════════════ */
export function Hero() {
  const reduceMotion = useReducedMotion();

  const smoothScroll = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    const target = document.getElementById("pq-hero-anchor");
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <section
      aria-labelledby="pq-hero-heading"
      className="relative isolate overflow-hidden"
      style={{
        backgroundColor: "#050505",
        color: "var(--pq-ivory)",
      }}
    >
      {/* ─── Ticker (v3) ─── thin strip at very top */}
      <MarketTicker />

      {/* ─── L2: Dot pattern ─── tighter mask (55% → 40%) */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
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

      {/* ─── L3: Film grain ─── slightly filmier */}
      <FilmGrain opacity={0.05} blendMode="overlay" />

      {/* ─── L4: Bottom fade into ink ─── deeper (h-40 → h-56) */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-56 z-[2]"
        style={{
          background:
            "linear-gradient(to bottom, transparent 0%, #050505 92%)",
        }}
      />

      {/* ─── Spotlight wrapper ─── content inside ─── */}
      <HeroSpotlight className="relative">
        <div className="relative mx-auto max-w-7xl px-5 pb-24 pt-24 sm:px-8 sm:pb-32 sm:pt-28 lg:px-10 lg:pb-36 lg:pt-32">
          <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1.22fr)_minmax(0,1fr)] lg:gap-16">
            {/* ─── LEFT: Copy column ─── */}
            <motion.div
              variants={stagger}
              initial="hidden"
              animate="visible"
              className="max-w-2xl"
            >
              {/* Masthead eyebrow */}
              <motion.div
                variants={fadeUp}
                className="mb-8 inline-flex items-center gap-2.5"
              >
                <span
                  aria-hidden
                  className="h-px w-7"
                  style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }}
                />
                <span
                  className="font-serif text-[11px] uppercase"
                  style={{
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                  }}
                >
                  PivoxQuant · Living CFO
                </span>
              </motion.div>

              {/* H1 — LCP element, rendered static (no fade-in) so Lighthouse
                  counts first paint as contentful. Motion wrappers on the LCP
                  element defer contentfulness until the animation settles. */}
              <h1
                id="pq-hero-heading"
                className="pq-silver-matte mb-7 font-serif font-normal"
                style={{
                  fontSize: "clamp(2.5rem, 6vw, 4.75rem)",
                  lineHeight: 1.02,
                  letterSpacing: "-0.02em",
                }}
              >
                Your CFO&nbsp;
                <span
                  className={reduceMotion ? "" : "pq-cfo-word"}
                  style={{
                    fontStyle: "italic",
                    ...(reduceMotion
                      ? { color: "var(--pq-bronze-light)" }
                      : {}),
                  }}
                >
                  learns
                </span>
                <br />
                you.
              </h1>

              {/* Subcopy — Living CFO */}
              <motion.p
                variants={fadeUp}
                className="mb-3 max-w-xl font-serif"
                style={{
                  fontSize: "clamp(15px, 1.35vw, 17px)",
                  lineHeight: 1.65,
                  color: "rgba(245, 240, 232, 0.72)",
                }}
              >
                매일 아침 두 번. 매수 전 일곱 관문. 매주 금요일 한 장의 편지.
                2년 뒤 당신은 알게 된다. 이 앱이 당신의 투자 철학을 당신보다
                먼저 기억한다는 것을.
              </motion.p>

              {/* Italic deck line */}
              <motion.p
                variants={fadeUp}
                className="mb-9 max-w-xl font-serif italic"
                style={{
                  fontSize: "clamp(13.5px, 1.15vw, 15px)",
                  lineHeight: 1.5,
                  letterSpacing: "0.005em",
                  color: "rgba(139, 111, 71, 0.85)",
                }}
              >
                Twice each morning. Seven gates before every trade. One letter
                each Friday. A personal CFO that studies you.
              </motion.p>

              {/* ─── Stat strip ─── */}
              <motion.div variants={fadeUp} className="mb-10">
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
                      <span
                        className="font-mono tabular-nums text-[17px] leading-none sm:text-[19px]"
                        style={{
                          color:
                            s.tone === "pos" ? "#3C7A52" : "var(--pq-ivory)",
                          fontFeatureSettings: '"tnum", "lnum"',
                          letterSpacing: "-0.01em",
                        }}
                      >
                        {s.value}
                      </span>
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
              </motion.div>

              {/* ─── CTAs ─── */}
              <motion.div
                variants={fadeUp}
                className="flex flex-wrap items-center gap-3"
              >
                <Link
                  href="/signup"
                  className="
                    group inline-flex h-12 items-center gap-2 rounded-sm px-6
                    text-[13.5px] font-medium tracking-wide
                    transition-transform duration-200
                    hover:-translate-y-px active:translate-y-0 active:scale-[0.99]
                  "
                  style={{
                    backgroundColor: "var(--pq-ivory)",
                    color: "var(--pq-ink)",
                    boxShadow:
                      "0 1px 0 0 rgba(245,240,232,0.3) inset, 0 8px 24px -8px rgba(245,240,232,0.25)",
                  }}
                >
                  Meet your CFO
                  <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
                </Link>

                <a
                  href="/samples/weekly_memo.pdf"
                  target="_blank"
                  rel="noopener"
                  className="
                    inline-flex h-12 items-center gap-2 rounded-sm border bg-transparent px-5
                    text-[13.5px] font-medium tracking-wide transition-colors duration-200
                  "
                  style={{
                    borderColor: "rgba(139, 111, 71, 0.5)",
                    color: "rgba(245, 240, 232, 0.88)",
                  }}
                >
                  <FileText className="h-4 w-4" />
                  See a sample
                </a>
              </motion.div>

              {/* ─── Disclaimer footer ─── */}
              <motion.p
                variants={fadeUp}
                className="mt-10 border-t pt-6 font-serif text-[11px] italic leading-relaxed tracking-wide"
                style={{
                  borderColor: "var(--pq-border)",
                  color: "var(--pq-muted)",
                }}
              >
                <span style={{ color: "rgba(139, 111, 71, 0.9)" }}>— </span>
                Not investment advice. Informational research only. Past
                performance does not guarantee future results.
              </motion.p>
            </motion.div>

            {/* ─── RIGHT: 3D Flip Deck ─── */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{
                duration: 0.9,
                ease: [0.16, 1, 0.3, 1],
                delay: 0.1,
              }}
              className="relative order-first flex w-full items-center justify-center lg:order-none"
            >
              <ReportFlipDeck />
            </motion.div>
          </div>
        </div>

        {/* ─── Scroll hint (v3) ─── bottom-center, editorial ─── */}
        <a
          href="#pq-hero-anchor"
          onClick={smoothScroll}
          aria-label="Continue to next section"
          className="
            absolute bottom-8 left-1/2 z-[3] -translate-x-1/2
            flex flex-col items-center gap-2
            group
          "
        >
          <span
            className={`${reduceMotion ? "" : "pq-scroll-hint"} flex flex-col items-center gap-1.5`}
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
            <ChevronDown
              className="h-3.5 w-3.5"
              style={{ color: "rgba(139, 111, 71, 0.7)" }}
              aria-hidden
            />
          </span>
        </a>
      </HeroSpotlight>

      {/* Anchor for smooth scroll target — reserves no layout space */}
      <div id="pq-hero-anchor" aria-hidden className="h-0 w-0" />
    </section>
  );
}

export default Hero;
