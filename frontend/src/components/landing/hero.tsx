"use client";

/**
 * Hero — landing entry section.
 * -----------------------------------------------------------------------
 * Rebuilt 2026-05-09 (round 2) per CEO follow-up:
 *   "디자인은 뭐 변경 안한거야? 그냥 지우기만 한 마우스 따라다니는 거?"
 *
 * Round 1 only stripped ambient effects (cursor spotlight / aurora /
 * particles / film grain / glyph reveal / ink-bleed). The grid layout
 * with the right-side Today's Gate panel stayed identical to v4 — so
 * structurally the Hero still didn't read like /features/engine,
 * /features/personas, /features/dashboard, etc., which are all
 * single-column editorial pages: eyebrow + big italic Playfair H1 +
 * description paragraph + (downstream visuals appear in subsequent
 * sections, not docked beside the H1).
 *
 * Round 2 mirrors that exact structure. The Hero now:
 *
 *   [MarketTicker]                  ← thin info strip, retained
 *   [eyebrow rule + label]
 *   [BIG italic H1 "Your CFO learns you."]
 *   [description paragraph]
 *   [primary + secondary CTAs]
 *   [disclaimer]
 *
 * No right column. No Today's Gate panel here — that surface lives in
 * the Pre-Trade feature page (/features/pre-trade) which is its
 * canonical home. The Hero now reads as the desk's masthead, exactly
 * like the masthead on every other editorial page on the site.
 *
 * Pure Vantablack background. Zero animation. Zero cursor tracking.
 *
 * Compliance: no BUY/SELL/HOLD/recommend/advice/추천/조언 vocabulary.
 */

import dynamic from "next/dynamic";
import Link from "next/link";
import { ArrowRight, FileText } from "lucide-react";

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

export function Hero() {
  return (
    <section
      aria-labelledby="pq-hero-heading"
      className="relative isolate"
      style={{
        backgroundColor: "#050505",
        color: "var(--pq-ivory)",
      }}
    >
      <MarketTicker />

      {/* Same column geometry the /features pages use:
          mx-auto max-w-7xl + asymmetric vertical padding so the Hero
          reads as the page's masthead, not a centered marketing splash. */}
      <div className="mx-auto max-w-7xl px-5 pb-32 pt-24 sm:px-8 sm:pb-40 sm:pt-32 lg:px-10 lg:pb-48 lg:pt-40">
        <div className="max-w-4xl">
          {/* Eyebrow — bronze rule + uppercase Playfair italic.
              Identical pattern across all /features pages. */}
          <div className="mb-10 inline-flex items-center gap-2.5">
            <span
              aria-hidden
              className="h-px"
              style={{
                backgroundColor: "rgba(139, 111, 71, 0.7)",
                width: 28,
              }}
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
          </div>

          {/* H1 — big italic Playfair, identical sizing to /features/engine,
              /features/personas, /features/explorer.
              Bronze italic on "learns" stays as the only typographic accent. */}
          <h1
            id="pq-hero-heading"
            className="pq-hero-h1 mb-9 font-serif font-normal"
          >
            Your CFO{" "}
            <em
              className="pq-cfo-word"
              style={{ fontStyle: "italic" }}
            >
              learns
            </em>{" "}
            you.
          </h1>

          {/* Description — same width cap + tone as /features pages. */}
          <p
            className="mb-10 max-w-2xl font-serif"
            style={{
              fontSize: "clamp(15px, 1.35vw, 18px)",
              lineHeight: 1.6,
              letterSpacing: "0.005em",
              color: "rgba(245, 240, 232, 0.72)",
            }}
          >
            매일 아침 두 번. 진입 전 일곱 관문. 일요일마다 한 페이지.
            온보딩 20문항이 당신을 8가지 투자자 유형 중 하나로 분류하면, 모든
            artifact가 그 페르소나의 어휘로 다시 쓰입니다. 관측 자료이며 매수·
            매도 권유가 아닙니다.
          </p>

          {/* CTAs — plain bronze pill + ghost outline.
              rounded-[2px] matches the /features pages exactly. */}
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/signup"
              className="group inline-flex items-center gap-2 rounded-[2px] px-6 py-3.5 text-sm font-medium tracking-wide transition-colors"
              style={{
                backgroundColor: "var(--pq-bronze)",
                color: "var(--pq-ink)",
              }}
            >
              Meet your CFO
              <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="/sample-reports/weekly-memo"
              target="_blank"
              rel="noopener"
              className="inline-flex items-center gap-2 rounded-[2px] border px-6 py-3.5 text-sm font-medium tracking-wide transition-colors hover:bg-[var(--pq-ivory-line-faint)]"
              style={{
                borderColor: "rgba(139, 111, 71, 0.5)",
                color: "var(--pq-bronze-light)",
              }}
            >
              <FileText className="h-4 w-4" />
              See a sample
            </Link>
          </div>

          {/* Disclaimer — same italic Playfair micro-copy seen on every
              /features page footer + the disclaimer-banner. */}
          <p
            className="mt-12 max-w-2xl border-t pt-6 font-serif text-[11px] italic leading-relaxed tracking-wide"
            style={{
              borderColor: "var(--pq-border)",
              color: "var(--pq-muted)",
            }}
          >
            <span style={{ color: "rgba(139, 111, 71, 0.9)" }}>— </span>
            Not investment advice. Informational research only. Past
            performance does not guarantee future results.
          </p>
        </div>
      </div>

      {/* Anchor target for in-page navigation. */}
      <div id="pq-hero-anchor" aria-hidden className="h-0 w-0" />
    </section>
  );
}
