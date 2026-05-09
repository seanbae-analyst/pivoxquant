"use client";

/**
 * Hero — landing entry section, static editorial.
 * -----------------------------------------------------------------------
 * Rebuilt 2026-05-09 per CEO direction:
 *   "이상한 마우스 옮겨다니면 금색 따라오는 그거 지우고 아예 삭다 새로 만들어"
 *
 * The previous v4 layered HeroAurora (cursor-tracked bronze sunrise),
 * HeroSpotlight (cursor radial gradient), HeroParticles (drifting motes),
 * FilmGrain, a dot mask, an inner glow, a glyph-by-glyph H1 reveal, and
 * an SVG ink-bleed CTA. Each was independently tasteful but the stack
 * read as overproduced — the hero felt different from every other
 * editorial page on the site (/features/* / /pricing / /login / /signup
 * / /terms / /privacy), all of which are static, calm, and Vantablack.
 *
 * This rebuild matches the rest of the site exactly:
 *   - eyebrow + italic Playfair H1 + sub copy + CTAs + disclaimer (left)
 *   - 7-Layer Today's Gate panel (right, lg+, kept — the one element
 *     that makes the hero feel like a research desk, not just text)
 *   - MarketTicker strip at the very top (informational, retained)
 *   - Pure Vantablack background, zero ambient effects
 *   - Static everything: no entrance animations, no cursor tracking,
 *     no ink-bleed, no glyph cross-fade. The H1 paints once and stays.
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

/* 7-Layer Pre-Trade Gate — static editorial preview of risk_defense.py.
   Not interactive, no API. Source-of-truth labels mirror the live engine. */
const GATE_ROWS: { label: string; state: "ok" | "watch" }[] = [
  { label: "VaR (95%)", state: "ok" },
  { label: "Correlation drift", state: "ok" },
  { label: "VIX regime", state: "watch" },
  { label: "Tail risk", state: "ok" },
  { label: "Daily P & L", state: "ok" },
  { label: "Sector cap", state: "ok" },
  { label: "Cash buffer", state: "ok" },
];

export function Hero() {
  return (
    <section
      aria-labelledby="pq-hero-heading"
      className="relative isolate overflow-hidden"
      style={{
        backgroundColor: "#050505",
        color: "var(--pq-ivory)",
      }}
    >
      {/* ─── Ticker — thin strip at very top ─── */}
      <MarketTicker />

      <div className="relative mx-auto max-w-7xl px-5 pb-24 pt-24 sm:px-8 sm:pb-32 sm:pt-28 lg:px-10 lg:pb-36 lg:pt-32">
        <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_auto] lg:gap-16">
          {/* ─── Editorial copy column ─── */}
          <div className="max-w-3xl">
            {/* Eyebrow */}
            <div className="mb-8 inline-flex items-center gap-2.5">
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

            {/* H1 — static italic Playfair, bronze italic on "learns".
                No glyph reveal, no cross-fade, no animation. */}
            <h1
              id="pq-hero-heading"
              className="pq-hero-h1 mb-7 font-serif font-normal"
            >
              Your CFO{" "}
              <em
                className="pq-cfo-word"
                style={{ fontStyle: "italic" }}
              >
                learns
              </em>
              <br />
              you.
            </h1>

            {/* Sub copy */}
            <p
              className="mb-9 max-w-xl font-serif"
              style={{
                fontSize: "clamp(15px, 1.35vw, 18px)",
                lineHeight: 1.55,
                letterSpacing: "0.005em",
                color: "rgba(245, 240, 232, 0.72)",
              }}
            >
              Morning memos. Pre-trade gates. A letter every Friday.
            </p>

            {/* CTAs — plain bronze pill + ghost outline.
                No SVG ink-bleed; rounded-[2px] matches /features pages. */}
            <div className="flex flex-wrap items-center gap-3">
              <Link
                href="/signup"
                className="group inline-flex items-center gap-2 rounded-[2px] px-5 py-3 text-sm font-medium tracking-wide transition-colors"
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
                className="inline-flex items-center gap-2 rounded-[2px] border px-5 py-3 text-sm font-medium tracking-wide transition-colors hover:bg-[rgba(245,240,232,0.04)]"
                style={{
                  borderColor: "rgba(139, 111, 71, 0.5)",
                  color: "var(--pq-bronze-light)",
                }}
              >
                <FileText className="h-4 w-4" />
                See a sample
              </Link>
            </div>

            {/* Disclaimer */}
            <p
              className="mt-10 border-t pt-6 font-serif text-[11px] italic leading-relaxed tracking-wide"
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

          {/* ─── Right column: 7-Layer Today's Gate (lg+ only) ───
              Kept from the previous Hero — the one element that makes
              the section read as a research-desk surface rather than a
              plain marketing hero. Pure CSS panel, static, no API, no
              live ticking. */}
          <aside
            aria-hidden
            className="pq-gate-card hidden lg:block"
          >
            <div className="pq-gate-card-frame">
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

              <div className="pq-gate-card-time">
                <span className="pq-gate-card-time-mono">09:14:22</span>
                <span className="pq-gate-card-time-tz">KST</span>
              </div>

              <ul className="pq-gate-card-list">
                {GATE_ROWS.map((row) => (
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

      {/* Anchor target for in-page navigation. */}
      <div id="pq-hero-anchor" aria-hidden className="h-0 w-0" />
    </section>
  );
}
