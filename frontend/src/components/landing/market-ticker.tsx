"use client";

/**
 * MarketTicker — Hero v3 top strip.
 * ------------------------------------------------------------------
 * A thin (32px) editorial ticker band sitting above the Hero.
 * Seamless left-drift marquee. Static snapshot of 5 symbols with a
 * "Last observed" timestamp label — editorial, not real-time.
 *
 * No auth, no fetch, no CLS. Pure CSS animation (.pq-marquee-track).
 * Respects prefers-reduced-motion via globals.css.
 *
 * Legal: "observation" framing. No BUY/SELL/HOLD. No recommend/advice.
 */

type Tick = {
  symbol: string;
  name: string;
  level: string;
  change: string;
  dir: "up" | "down" | "flat";
};

// Static observation snapshot. Matches "as observed" editorial label.
// Fixed 2026-04-24: previous snapshot had SPY ETF price ($708) labeled
// as "S&P 500" (actual index ~7108) — misleading by an order of magnitude.
// Re-anchored to actual index levels as of the observation timestamp.
const SNAPSHOT: readonly Tick[] = [
  { symbol: "SPX",     name: "S&P 500",        level: "7,108.40", change: "+0.12%", dir: "up" },
  { symbol: "NDX",     name: "Nasdaq 100",     level: "24,438.50",change: "-0.38%", dir: "down" },
  { symbol: "KOSPI",   name: "KOSPI",          level: "6,475.63", change: "+0.46%", dir: "up" },
  { symbol: "USDKRW",  name: "USD/KRW",        level: "1,483.08", change: "+0.04%", dir: "flat" },
  { symbol: "VIX",     name: "Volatility Idx", level: "27.98",    change: "+1.83%", dir: "up" },
  { symbol: "US10Y",   name: "US 10Y Yield",   level: "4.42%",    change: "-0.03pp", dir: "down" },
  { symbol: "GOLD",    name: "XAU/USD",        level: "3,112.40", change: "+0.22%", dir: "up" },
] as const;

// Editorial up/down tones — muted sage/carmine, within bronze family temperature.
const DIR_COLOR = {
  up:   "#7DB487",
  down: "#D18888",
  flat: "rgba(245, 240, 232, 0.55)",
} as const;

const DIR_GLYPH = {
  up:   "▲",
  down: "▼",
  flat: "·",
} as const;

function Row({ ticks, ariaHidden }: { ticks: readonly Tick[]; ariaHidden?: boolean }) {
  return (
    <div
      className="flex shrink-0 items-center"
      aria-hidden={ariaHidden ? true : undefined}
    >
      {ticks.map((t, i) => (
        <span
          key={`${t.symbol}-${i}`}
          className="inline-flex items-center whitespace-nowrap px-6"
        >
          <span
            className="font-serif text-[10.5px] uppercase"
            style={{
              letterSpacing: "0.22em",
              color: "rgba(245, 240, 232, 0.82)",
            }}
          >
            {t.symbol}
          </span>
          <span
            className="ml-2 font-mono tabular-nums text-[11.5px]"
            style={{
              color: "var(--pq-bronze-light)",
              fontFeatureSettings: '"tnum", "lnum"',
              letterSpacing: "-0.005em",
            }}
          >
            {t.level}
          </span>
          <span
            className="ml-2 font-mono tabular-nums text-[10.5px]"
            style={{
              color: DIR_COLOR[t.dir],
              fontFeatureSettings: '"tnum", "lnum"',
            }}
          >
            {DIR_GLYPH[t.dir]} {t.change}
          </span>
          <span
            aria-hidden
            className="ml-6 inline-block h-[9px] w-px"
            style={{ backgroundColor: "rgba(139, 111, 71, 0.28)" }}
          />
        </span>
      ))}
    </div>
  );
}

export function MarketTicker() {
  // Doubled row so the CSS -50% translate wraps seamlessly.
  //
  // Overflow hygiene:
  //   - Outer wrapper uses `w-full max-w-full overflow-x-clip` so the inner
  //     `w-max` track can never push `document.body.scrollWidth` past the
  //     viewport. `overflow-x-clip` (Tailwind 4) is stricter than
  //     `overflow-hidden` in border-box math and prevents 1–2px border
  //     leaks that produced the +14px horizontal scroll on 614px.
  //   - `box-border` pins border-width inside the width budget so the
  //     `border-b` hairline never contributes to scrollWidth.
  return (
    <div
      role="marquee"
      aria-label="Global market observation ticker"
      className="relative w-full max-w-full overflow-x-clip overflow-y-hidden border-b box-border"
      style={{
        height: 32,
        borderColor: "rgba(139, 111, 71, 0.22)",
        backgroundColor: "rgba(5, 5, 5, 0.78)",
        backdropFilter: "blur(6px)",
        WebkitBackdropFilter: "blur(6px)",
      }}
    >
      {/* Edge masks — editorial fade at both ends so text dissolves into the void.
          Left edge mask is intentionally smaller than the kicker zone below so
          it does not compete with the kicker's opaque backdrop. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 right-0 z-10 w-32"
        style={{
          background:
            "linear-gradient(to left, var(--pq-ink) 0%, transparent 100%)",
        }}
      />

      {/* Kicker — "Live observation" editorial label, pinned left.
          Backdrop is a FIXED-WIDTH solid ink block (not a partial gradient)
          followed by a short gradient tail. This guarantees no ticker glyph
          bleeds through behind the "As observed" text on any viewport —
          previously the 60% gradient-stop left the right half of the kicker
          transparent, so tickers were visible behind "OBSERVED". */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-0 z-20"
        style={{
          width: 180,
          backgroundColor: "var(--pq-ink)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 z-20"
        style={{
          left: 180,
          width: 48,
          background:
            "linear-gradient(to right, var(--pq-ink) 0%, transparent 100%)",
        }}
      />
      <div className="absolute inset-y-0 left-0 z-30 flex items-center pl-4 pr-3">
        <span
          className="font-serif text-[9.5px] uppercase whitespace-nowrap"
          style={{
            letterSpacing: "0.24em",
            color: "var(--pq-bronze)",
          }}
        >
          <span
            className="pq-live-dot mr-1.5 inline-block h-[5px] w-[5px] rounded-full align-middle"
            style={{ backgroundColor: "var(--pq-bronze-light)" }}
          />
          As observed
        </span>
      </div>

      {/* Marquee track — duplicated content for seamless wrap.
          `pl-[15rem]` (240px) clears the 180px opaque kicker block + 48px
          gradient tail + breathing room. `shrink-0` on each Row prevents
          flex-container width calculations from shrinking the symbol pills.
          Track sits at z-0 so both the kicker zone (z-20) and right fade
          mask (z-10) render above it. */}
      <div className="pq-marquee-track relative z-0 flex h-full w-max items-center pl-[15rem]">
        <Row ticks={SNAPSHOT} />
        <Row ticks={SNAPSHOT} ariaHidden />
      </div>
    </div>
  );
}

export default MarketTicker;
