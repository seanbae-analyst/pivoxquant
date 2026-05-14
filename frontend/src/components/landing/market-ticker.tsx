"use client";

/**
 * MarketTicker — Hero v3 top strip.
 * ------------------------------------------------------------------
 * A thin (32px) editorial ticker band sitting above the Hero.
 * Seamless left-drift marquee. Manually refreshed snapshot of major
 * indices. Kicker label is explicit so visitors never read these as
 * live; we update in code and surface the refresh date.
 *
 * No auth, no fetch, no CLS. Pure CSS animation (.pq-marquee-track).
 * Respects prefers-reduced-motion via globals.css.
 *
 * Refresh history (Bug C, observed 2026-05-12):
 *   - 2026-04-26: re-anchored to 2026-04-25 close per CEO "싼마이 느낌"
 *     audit; pulsing dot removed for legal/visual honesty.
 *   - 2026-05-13: KOSPI/KOSDAQ/USDKRW re-anchored from the KIS feed
 *     (KOSPI 7,643 / KOSDAQ 1,179 / USDKRW 1,487). NOTE: the KOSPI value
 *     here was WRONG — see the 2026-05-14 entry below.
 *   - 2026-05-14 (Bug #1, bug-hunt-live): the KOSPI row (7,643.15) was
 *     ~3x the real index level. Root cause is the KIS "0001" current-level
 *     endpoint returning an inflated value (Bug #2, owned by backend-dev).
 *     KOSPI row REMOVED rather than shipping a wrong number to
 *     unauthenticated visitors. Re-add once backend-dev confirms a
 *     KRX-cross-validated level. Next step remains a public
 *     Server-Component fetch to retire the manual snapshot ritual.
 *   - 2026-05-13 (second pass): SPX / NDX / VIX re-anchored against
 *     official-licensed feeds. SPX & VIX from FMP $29 stable
 *     `historical-price-eod/full` (2026-05-12 close). NDX from FRED
 *     `NASDAQ100` series (Fed-published, T+1 lag — 2026-05-11 close,
 *     latest available at refresh time). Prior values (SPX 5,520 /
 *     NDX 19,840 / VIX 14.85) were pre-pandemic-era levels off by
 *     30-48% from reality — active misrepresentation, not just stale.
 *   - 2026-05-13 (PR #343 audit, option B): USD-IDX row dropped.
 *     DXY removed pending ICE direct license (FMP premium gated).
 *     DTWEXBGS swap rejected due to product mismatch — see PR #343
 *     audit. DXY (ICE, 6-country, ~100) and DTWEXBGS (Fed, 26-country,
 *     ~118) are different products; the ~12% absolute-level scale gap
 *     is itself a capital-markets-law misrepresentation risk even with
 *     a distinct label. Remaining 6 rows (SPX/NDX/KOSPI/KOSDAQ/USDKRW/
 *     VIX) carry the ticker without forcing a mislabeled proxy.
 *   - 2026-05-13 (FMP paid-plan retry): CEO confirmed FMP $29 plan
 *     billed. Re-tested `^NDX` and `^DXY` on the active key — both
 *     STILL return 402 Premium Query Parameter ("not available under
 *     your current subscription"). Caret-prefixed index symbols are
 *     gated to an Enterprise tier above the $29 Starter. Plain `NDX`
 *     (no caret) returns stale 2023-05-23 data; plain `DXY` returns
 *     `[]`. Conclusion: FMP cannot license `^NDX`/`^DXY` at our price
 *     point — FRED stays as the official NDX source, DXY row stays
 *     omitted. NDX value refreshed to FRED's newly-published 2026-05-12
 *     close (29,064.80, posted overnight) — was the missing T+1 print
 *     PR #343 anticipated.
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

// Static snapshot. All values from official-licensed feeds verified at refresh
// time (2026-05-13 KST). Source-per-row:
//   - SPX  : FMP stable `historical-price-eod/light` symbol=^GSPC, 2026-05-12 close = 7,400.97 (prev 7,412.85 → -0.16%).
//   - NDX  : FRED series=NASDAQ100, 2026-05-12 close = 29,064.80 (prev 29,320.66 → -0.87%). FMP $29 plan cannot license `^NDX` (still 402 after paid-plan retry on 2026-05-13); FRED's overnight T+1 publish is the latest official US value.
//   - KOSDAQ / USDKRW: KIS API 2026-05-12 close (verified via routes/market.py /api/market/indices?region=kr live probe — unchanged from PR #335).
//   - KOSPI: ROW REMOVED 2026-05-14 (Bug #1) — KIS "0001" current-level endpoint returns an inflated (~3x) value. Awaiting backend-dev Bug #2 fix before re-adding.
//   - VIX  : FMP stable `historical-price-eod/light` symbol=^VIX, 2026-05-12 close = 17.99 (prev 18.38 → -2.12%).
//
// DXY remains omitted. Re-verified 2026-05-13 on the paid FMP key — `^DXY`
// still returns 402 Premium Query Parameter, plain `DXY` returns `[]`. ICE
// direct license still the only honest path; DTWEXBGS swap remains rejected
// (product mismatch, see PR #343 audit). Six rows is enough surface area
// without forcing a misleading proxy.
//
// The kicker label is explicit so visitors read this as reference, not live.
//
// SNAPSHOT_DATE is exported for the kicker text and the pre-commit stale-guard
// referenced in earlier comments. NOTE: the current .githooks/pre-commit does
// not actually contain a SNAPSHOT_DATE >14d check; treat that earlier comment
// as aspirational. A real value-vs-FMP regression gate is the right next step
// (see PR body).
export const SNAPSHOT_DATE = "2026-05-12";
// Bug #1 (2026-05-14, bug-hunt-live): the KOSPI row was hardcoded at
// 7,643.15 — real KOSPI trades in the ~2,500–3,200 range, i.e. the value
// was ~3x reality. Per bug-hunt-live.md the snapshot was taken from the
// KIS "0001" current-level endpoint, which itself returns an anomalous
// inflated value (Bug #2 — same root cause, owned by backend-dev). The
// landing ticker is unauthenticated by design (no auth, no fetch, no CLS),
// so it cannot connect to /api/market/indices at runtime — and we must NOT
// substitute a guessed real KOSPI level here.
//
// Honest interim fix: REMOVE the KOSPI row entirely rather than ship a
// factually-wrong number to unauthenticated visitors (active
// capital-markets-law misrepresentation risk). KOSDAQ/USDKRW are sourced
// from different KIS codes than the inflated "0001" KOSPI endpoint and
// bug-hunt-live only flagged KOSPI with 100% confidence — they stay.
//
// RE-ADD path (blocked on backend-dev Bug #2 / Phase 0): once backend-dev
// confirms a correct, KRX/KIS-cross-validated KOSPI level, re-insert the
// row here with that value (and ideally move the whole strip to a public
// Server-Component fetch to retire the manual snapshot ritual).
const SNAPSHOT: readonly Tick[] = [
  { symbol: "SPX",     name: "S&P 500",           level: "7,400.97",  change: "-0.16%",  dir: "down" },
  { symbol: "NDX",     name: "Nasdaq 100",        level: "29,064.80", change: "-0.87%",  dir: "down" },
  { symbol: "KOSDAQ",  name: "KOSDAQ",            level: "1,179.29",  change: "-2.32%",  dir: "down" },
  { symbol: "USDKRW",  name: "USD / KRW",         level: "1,487.48",  change: "+0.82%",  dir: "up"   },
  { symbol: "VIX",     name: "Volatility Idx",    level: "17.99",     change: "-2.12%",  dir: "down" },
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
            className="font-serif text-pq-caption uppercase"
            style={{
              letterSpacing: "0.22em",
              color: "rgba(245, 240, 232, 0.82)",
            }}
          >
            {t.symbol}
          </span>
          <span
            className="ml-2 font-mono tabular-nums text-pq-caption"
            style={{
              color: "var(--pq-bronze-light)",
              fontFeatureSettings: '"tnum", "lnum"',
              letterSpacing: "-0.005em",
            }}
          >
            {t.level}
          </span>
          <span
            className="ml-2 font-mono tabular-nums text-pq-caption"
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
      aria-label={`Global market snapshot ticker (refreshed ${SNAPSHOT_DATE}, indicative levels)`}
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

      {/* Kicker — "As of 2026-04-25 close · indicative levels" editorial label,
          pinned left. Backdrop is a FIXED-WIDTH solid ink block (not a partial
          gradient) followed by a short gradient tail.

          2026-05-07: widened from 240→320 + marquee padding 288→368 because the
          older 240+48 budget was tight (~296px text width @ 11px serif + 0.24em
          tracking + pl-4) and "INDICATIVE LEVELS" trailing word could spill over
          the marquee text at certain scroll positions, producing "INDICATIVE
          IKEO/VSEIS" garbled overlap. Fixed by giving the kicker text 8% more
          horizontal slack. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-0 z-20"
        style={{
          width: 320,
          backgroundColor: "var(--pq-ink)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 z-20"
        style={{
          left: 320,
          width: 48,
          background:
            "linear-gradient(to right, var(--pq-ink) 0%, transparent 100%)",
        }}
      />
      <div className="absolute inset-y-0 left-0 z-30 flex items-center pl-4 pr-3">
        <span
          className="font-serif text-pq-mono-sm uppercase whitespace-nowrap"
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
          Snapshot · {SNAPSHOT_DATE} · indicative levels
        </span>
      </div>

      {/* Marquee track — duplicated content for seamless wrap.
          `pl-[23rem]` (368px) clears the 320px opaque kicker block + 48px
          gradient tail (2026-05-07: widened from 18rem/288 to 23rem/368 to
          eliminate "INDICATIVE LEVELS" spillover seen in bug-hunter audit).
          `shrink-0` on each Row prevents flex-container width calculations
          from shrinking the symbol pills. Track sits at z-0 so both the
          kicker zone (z-20) and right fade mask (z-10) render above it. */}
      <div className="pq-marquee-track relative z-0 flex h-full w-max items-center pl-[23rem]">
        <Row ticks={SNAPSHOT} />
        <Row ticks={SNAPSHOT} ariaHidden />
      </div>
    </div>
  );
}

export default MarketTicker;
