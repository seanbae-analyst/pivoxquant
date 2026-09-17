"use client";

/**
 * Hero — landing masthead.
 * -----------------------------------------------------------------------
 * Single column, same geometry the rest of the landing uses:
 *
 *   [eyebrow rule + label]
 *   [H1  "부자로 만들어 준다고 / 약속하지 않습니다."]
 *   [description paragraph]
 *   [primary CTA → /signup]
 *   [disclaimer]
 *
 * Pure Vantablack. Zero animation. Zero cursor tracking. No italic
 * (CEO 2026-06-15). Copy lives in messages/{ko,en}.json under `landing.hero`.
 *
 * 2026-09-02: the previous header described a "[MarketTicker] ← retained"
 * strip, an H1 reading "Your CFO learns you.", and pointed at /features/engine,
 * /features/personas, /features/explorer and /features/pre-trade as the pages
 * this layout mirrors. The ticker is gone (see the note below), the CFO copy
 * was replaced when the artifact pipeline was deleted, and every /features/*
 * route 308s to "/". Header rewritten to describe what the component renders.
 *
 * Compliance: no BUY/SELL/HOLD/recommend/advice/추천/조언 vocabulary.
 */

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/locale";

/*
 * ⚠️ 2026-09-02 — <MarketTicker/> removed from the public Hero.
 *
 * The strip read GET /api/public/market-snapshot (no auth) and rendered KOSPI,
 * KOSDAQ, USD/KRW, S&P 500, Nasdaq 100 and VIX to anyone who opened the site.
 * Three reasons it had to go, in order of weight:
 *
 * 1. FMP terms §2.2.2 forbid displaying their data to users without a separate
 *    Data Display Agreement, and the clause says "complimentary or paid" — a
 *    free beta is covered. The US rows here are FMP-derived (SPY/QQQ/VIXY
 *    proxies, see routes/market.py::public_market_snapshot). An unauthenticated,
 *    crawlable page was the widest possible surface for that exposure.
 * 2. It contradicted the product. CLAUDE.md: the three screens that matter
 *    (/pre-trade, /journal, /mirror) never call a price feed at all — quotes
 *    exist only for /portfolio valuation. A macro ticker above the hero framed
 *    the product as a market terminal, which is the thing it deliberately is not.
 * 3. It was dead on prod anyway. The backend is unreachable (api/health → 404
 *    measured 2026-09-02), so the component's honest no-fabricated-values
 *    fallback rendered an empty 32px band on every visit.
 *
 * market-ticker.tsx is KEPT, but not for the reason this comment used to give.
 * It said "the dashboard-side usage ... are still wanted" — measured
 * 2026-09-10, there is no dashboard-side usage: the component has ZERO
 * importers anywhere in src/. It is retained solely because its
 * proxy-disclosure logic is the work that would have to be redone if the FMP
 * Data Display Agreement (terms §2.2.2, still unresolved) is ever obtained.
 * Until then it renders nowhere. 2026-09-10: the CEO decided to pursue that
 * agreement rather than drop the surface, so the file is retained on a live
 * plan and not on a maybe — tracked as SHIP_BLOCKERS R8. If R8 is ever closed
 * as abandoned, delete this component; git holds the history either way.
 */

export function Hero() {
  const t = useT();
  const { user } = useAuth();
  return (
    <section
      // app/layout.tsx renders a "Skip to main content" link to #main-content.
      // The dashboard shell owns that id on its <main>; the landing had no
      // target at all (measured 2026-09-17: getElementById → null), so the
      // skip link was a dead jump. The hero is the first content after the
      // full-viewport splash, so it is the right landing spot.
      id="main-content"
      aria-labelledby="pq-hero-heading"
      className="relative isolate"
      style={{
        backgroundColor: "#050505",
        color: "var(--pq-ivory)",
      }}
    >
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
                backgroundColor: "rgba(var(--pq-bronze-wash-rgb), 0.7)",
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
              {t("landing.hero.eyebrow")}
            </span>
          </div>

          {/* H1 — Playfair. The second clause is the bronze accent and the
              whole point of the sentence: it names what we will not do. */}
          <h1
            id="pq-hero-heading"
            className="pq-hero-h1 mb-9 font-serif font-normal"
          >
            {t("landing.hero.h1Part1")}{" "}
            {/* Accent word: bronze, upright. Decorative italic removed
                globally per CEO 2026-06-15 ("이탤릭 이상한거 다 빼라"). */}
            <em
              className="pq-cfo-word"
              style={{ fontStyle: "normal" }}
            >
              {t("landing.hero.h1Italic")}
            </em>
          </h1>

          {/* Description — same width cap + tone as /features pages. */}
          <p
            className="mb-10 max-w-2xl font-serif"
            style={{
              // v3 token: --pq-text-deck = 17px (deck/body paragraph scale).
              fontSize: "var(--pq-text-deck)",
              lineHeight: 1.6,
              letterSpacing: "0.005em",
              color: "var(--pq-ivory-muted)",
            }}
          >
            {t("landing.hero.description")}
          </p>

          {/* CTAs — plain bronze pill + ghost outline.
              rounded-[2px] matches the /features pages exactly.
              Signed-out visitors go to sign-up, signed-in users to their
              mirror — same split as the top nav (top-nav.tsx). */}
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href={user ? "/mirror" : "/signup"}
              className="group inline-flex items-center gap-2 rounded-[2px] px-6 py-3.5 text-sm font-medium tracking-wide transition-colors"
              style={{
                backgroundColor: "var(--pq-bronze)",
                color: "var(--pq-ink)",
              }}
            >
              {user ? t("landing.hero.ctaOpenMirror") : t("landing.hero.ctaPrimary")}
              <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
            </Link>
          </div>

          {/* Disclaimer — same italic Playfair micro-copy seen on every
              /features page footer + the disclaimer-banner. */}
          <p
            className="mt-12 max-w-2xl border-t pt-6 font-serif text-[11px] leading-relaxed tracking-wide"
            style={{
              borderColor: "var(--pq-border)",
              color: "var(--pq-muted)",
            }}
          >
            <span style={{ color: "rgba(var(--pq-bronze-wash-rgb), 0.9)" }}>— </span>
            {t("landing.hero.disclaimer")}
          </p>
        </div>
      </div>

      {/* Anchor target for in-page navigation. */}
      <div id="pq-hero-anchor" aria-hidden className="h-0 w-0" />
    </section>
  );
}
