"use client";

/**
 * MarketTicker — Hero v3 top strip.
 * ------------------------------------------------------------------
 * A thin (32px) editorial ticker band sitting above the Hero.
 * Seamless left-drift marquee. Pure CSS animation (.pq-marquee-track),
 * respects prefers-reduced-motion via globals.css.
 *
 * 2026-05-15 (Bug #1, bug-hunt-live): retired the hand-maintained static
 * snapshot. Every prior value here (SPX/NDX/KOSPI/KOSDAQ/USDKRW/VIX) was a
 * manually-refreshed literal that went stale and — per the long comment
 * history this file used to carry — repeatedly drifted far from reality.
 * The ticker now reads the public, cache-only `GET /api/public/market-
 * snapshot` endpoint (no auth, rate-limited, always HTTP 200) via the
 * `usePublicMarketSnapshot` SWR hook (60s poll). The backend owns the
 * refresh cadence and the staleness flag; the frontend just renders what
 * the cache holds.
 *
 * State handling:
 *   - Loading (no data yet): a minimal placeholder band (no fabricated
 *     numbers, no CLS — same 32px height).
 *   - Error / endpoint down: SWR's `keepPreviousData` holds the last good
 *     payload; if there was never any data we render the placeholder band.
 *     We NEVER render an invented value.
 *   - `is_stale: true` row: rendered normally (the value is the last good
 *     cached close) with a subtle dimmed treatment.
 *   - `value: null` row: rendered as "—" so the row count stays stable.
 *
 * Legal: pure snapshot framing. No BUY/SELL/HOLD. No recommend/advice.
 */

import {
  usePublicMarketSnapshot,
  type PublicMarketSnapshotItem,
} from "@/lib/hooks";

// Korean market convention: ▲ rising = red, ▼ falling = blue.
// CEO directive (2026-04-26) — single KR convention applied to both KR and
// US symbols on PivoxQuant. Tones kept editorial — muted carmine/indigo
// within the bronze family temperature, not pure RGB primaries.
const DIR_COLOR = {
  up: "#D18888",
  down: "#7AA0C8",
  flat: "rgba(245, 240, 232, 0.55)",
} as const;

const DIR_GLYPH = {
  up: "▲",
  down: "▼",
  flat: "·",
} as const;

// Display symbol overrides — the backend emits Yahoo-style symbols
// (^KS11, ^GSPC, …); the ticker shows the desk-floor shorthand.
const SYMBOL_LABEL: Record<string, string> = {
  "^KS11": "KOSPI",
  "^KQ11": "KOSDAQ",
  "^GSPC": "SPX",
  "^IXIC": "NDX",
  "^VIX": "VIX",
  USDKRW: "USDKRW",
};

function dirOf(item: PublicMarketSnapshotItem): "up" | "down" | "flat" {
  if (item.direction === "up" || item.direction === "down") {
    return item.direction;
  }
  return "flat";
}

// Group-3 digit formatting. `null` → "—" so the row count never changes.
// USD/KRW and VIX-style sub-100 values keep 2 decimals; index levels show
// 2 decimals as well to match the prior snapshot's precision.
function fmtLevel(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtChange(pct: number | null): string {
  if (pct == null || !Number.isFinite(pct)) return "—";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function Row({
  ticks,
  ariaHidden,
}: {
  ticks: readonly PublicMarketSnapshotItem[];
  ariaHidden?: boolean;
}) {
  return (
    <div
      className="flex shrink-0 items-center"
      aria-hidden={ariaHidden ? true : undefined}
    >
      {ticks.map((t, i) => {
        const dir = dirOf(t);
        const label = SYMBOL_LABEL[t.symbol] ?? t.symbol;
        return (
          <span
            key={`${t.symbol}-${i}`}
            className="inline-flex items-center whitespace-nowrap px-6"
            style={{ opacity: t.is_stale ? 0.62 : 1 }}
          >
            <span
              className="font-serif text-pq-caption uppercase"
              style={{
                letterSpacing: "0.22em",
                color: "rgba(245, 240, 232, 0.82)",
              }}
            >
              {label}
            </span>
            <span
              className="ml-2 font-mono tabular-nums text-pq-caption"
              style={{
                color: "var(--pq-bronze-light)",
                fontFeatureSettings: '"tnum", "lnum"',
                letterSpacing: "-0.005em",
              }}
            >
              {fmtLevel(t.value)}
            </span>
            <span
              className="ml-2 font-mono tabular-nums text-pq-caption"
              style={{
                color: DIR_COLOR[dir],
                fontFeatureSettings: '"tnum", "lnum"',
              }}
            >
              {DIR_GLYPH[dir]} {fmtChange(t.change_pct)}
            </span>
            <span
              aria-hidden
              className="ml-6 inline-block h-[9px] w-px"
              style={{ backgroundColor: "rgba(184, 149, 106, 0.28)" }}
            />
          </span>
        );
      })}
    </div>
  );
}

// Thin band shell — shared by the loading/empty placeholder and the live
// marquee so there is zero CLS between states.
function TickerShell({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <div
      role="marquee"
      aria-label={label}
      className="relative w-full max-w-full overflow-x-clip overflow-y-hidden border-b box-border"
      style={{
        height: 32,
        borderColor: "rgba(139, 111, 71, 0.22)",
        backgroundColor: "rgba(5, 5, 5, 0.78)",
        backdropFilter: "blur(6px)",
        WebkitBackdropFilter: "blur(6px)",
      }}
    >
      {children}
    </div>
  );
}

export function MarketTicker() {
  const { data } = usePublicMarketSnapshot();

  // `keepPreviousData` means `data` survives across refreshes and through a
  // transient error. When the endpoint has never resolved (cold load or a
  // hard failure on first paint) we render the empty shell — no fabricated
  // numbers, ever.
  const items = data?.items ?? [];

  if (items.length === 0) {
    // Loading / unavailable — render the band silhouette only. No CLS, no
    // invented values. The marquee simply has nothing to drift yet.
    return (
      <TickerShell label="Global market snapshot ticker (loading)">
        <div
          aria-hidden
          className="absolute inset-y-0 left-0 z-30 flex items-center pl-4"
        >
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
              style={{ backgroundColor: "rgba(184, 149, 106, 0.35)" }}
            />
            Market snapshot · loading
          </span>
        </div>
      </TickerShell>
    );
  }

  // Doubled row so the CSS -50% translate wraps seamlessly.
  //
  // Overflow hygiene:
  //   - Outer wrapper uses `w-full max-w-full overflow-x-clip` so the inner
  //     `w-max` track can never push `document.body.scrollWidth` past the
  //     viewport.
  //   - `box-border` pins border-width inside the width budget so the
  //     `border-b` hairline never contributes to scrollWidth.
  return (
    <TickerShell label="Global market snapshot ticker (live, indicative levels)">
      {/* Right edge mask — editorial fade so text dissolves into the void. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 right-0 z-10 w-32"
        style={{
          background:
            "linear-gradient(to left, var(--pq-ink) 0%, transparent 100%)",
        }}
      />

      {/* Kicker — pinned left. Backdrop is a FIXED-WIDTH solid ink block
          followed by a short gradient tail so the marquee text never spills
          over the kicker label. 320px block + 48px gradient tail; the
          marquee track clears 368px (pl-[23rem]). */}
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
          Market snapshot · indicative levels
        </span>
      </div>

      {/* Marquee track — duplicated content for seamless wrap.
          `pl-[23rem]` (368px) clears the 320px opaque kicker block + 48px
          gradient tail. `shrink-0` on each Row prevents flex width
          calculations from shrinking the symbol pills. Track sits at z-0
          so both the kicker zone (z-20) and right fade mask (z-10) render
          above it. */}
      <div className="pq-marquee-track relative z-0 flex h-full w-max items-center pl-[23rem]">
        <Row ticks={items} />
        <Row ticks={items} ariaHidden />
      </div>
    </TickerShell>
  );
}

export default MarketTicker;
