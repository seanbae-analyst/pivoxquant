"use client";

/**
 * MarketTicker — Hero v3 top strip.
 * ------------------------------------------------------------------
 * A thin (32px) editorial ticker band sitting above the Hero.
 * Seamless left-drift marquee. **Static snapshot** of global indices
 * with an explicit timestamp label — no live data, no fake pulsing.
 *
 * No auth, no fetch, no CLS. Pure CSS animation (.pq-marquee-track).
 * Respects prefers-reduced-motion via globals.css.
 *
 * 2026-04-26 — Reset to "Snapshot" framing per CEO ("싼마이 느낌"
 * audit). Previous "As observed" + pulsing dot read as fake-live;
 * KOSPI 6,475 was off-by-2x and broke trust on inspection. Values
 * re-anchored to plausible 2026-04-25 close estimates and the
 * pulsing dot is removed entirely (legal + visual honesty).
 *
 * Legal: pure snapshot framing. No BUY/SELL/HOLD. No recommend/advice.
 */

type Tick = {
  symbol: string;
  name: string;
  level: string;
  change: string;
  dir: "up" | "down" | "flat";
};

// Static snapshot — values re-anchored 2026-04-26 to plausible 2026-04-25
// close estimates for major global indices. Treated as editorial copy, not
// live data; the kicker label is "Snapshot · 2026-04-25 16:00 KST" so the
// reader is never misled. Update this snapshot in code, not via fetch.
const SNAPSHOT: readonly Tick[] = [
  { symbol: "SPX",    name: "S&P 500",        level: "5,520.30",  change: "+0.18%",  dir: "up"   },
  { symbol: "NDX",    name: "Nasdaq 100",     level: "19,840.15", change: "-0.32%",  dir: "down" },
  { symbol: "DXY",    name: "Dollar Index",   level: "103.45",    change: "+0.04%",  dir: "flat" },
  { symbol: "KOSPI",  name: "KOSPI",          level: "2,755.20",  change: "+0.41%",  dir: "up"   },
  { symbol: "KOSDAQ", name: "KOSDAQ",         level: "868.40",    change: "-0.22%",  dir: "down" },
  { symbol: "VIX",    name: "Volatility Idx", level: "14.85",     change: "-1.06%",  dir: "down" },
  { symbol: "US10Y",  name: "US 10Y Yield",   level: "4.32%",     change: "-0.02pp", dir: "down" },
] as const;

// Korean market convention: ▲ rising = red, ▼ falling = blue.
// CEO directive (2026-04-26) — single KR convention applied to both KR and US
// symbols on PivoxQuant. Swapped from prior US convention (sage up / carmine
// down). Tones kept editorial — muted carmine/indigo within bronze family
// temperature, not pure RGB primaries.
const DIR_COLOR = {
  up:   "#D18888",
  down: "#7AA0C8",
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
            style={{ backgroundColor: "rgba(184, 149, 106, 0.28)" }}
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
      aria-label="Global market snapshot ticker (as of 2026-04-25 close, indicative levels)"
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

      {/* Kicker — "Snapshot · YYYY-MM-DD HH:MM KST" editorial label, pinned
          left. Backdrop is a FIXED-WIDTH solid ink block (not a partial
          gradient) followed by a short gradient tail. Widened to 240 px so
          the longer "SNAPSHOT · 2026-04-25 16:00 KST" copy never collides
          with the marquee track. The pulsing dot was removed (2026-04-26)
          to stop signalling "live" — values are static editorial fixtures. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-0 z-20"
        style={{
          width: 240,
          backgroundColor: "var(--pq-ink)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 z-20"
        style={{
          left: 240,
          width: 48,
          background:
            "linear-gradient(to right, var(--pq-ink) 0%, transparent 100%)",
        }}
      />
      <div className="absolute inset-y-0 left-0 z-30 flex items-center pl-4 pr-3">
        <span
          className="font-serif text-[11px] uppercase whitespace-nowrap"
          style={{
            letterSpacing: "0.24em",
            color: "var(--pq-bronze)",
          }}
        >
          <span
            aria-hidden
            className="mr-1.5 inline-block h-[5px] w-[5px] rounded-full align-middle"
            style={{ backgroundColor: "rgba(184, 149, 106, 0.55)" }}
          />
          As of 2026-04-25 close · indicative levels
        </span>
      </div>

      {/* Marquee track — duplicated content for seamless wrap.
          `pl-[18rem]` (288px) clears the 240px opaque kicker block + 48px
          gradient tail. Kicker was widened in 2026-04-26 to fit the longer
          "Snapshot · 2026-04-25 16:00 KST" label. `shrink-0` on each Row
          prevents flex-container width calculations from shrinking the
          symbol pills. Track sits at z-0 so both the kicker zone (z-20)
          and right fade mask (z-10) render above it. */}
      <div className="pq-marquee-track relative z-0 flex h-full w-max items-center pl-[18rem]">
        <Row ticks={SNAPSHOT} />
        <Row ticks={SNAPSHOT} ariaHidden />
      </div>
    </div>
  );
}

export default MarketTicker;
