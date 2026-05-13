export function fmtUsd(v: number | null | undefined): string {
  const n = v ?? 0;
  if (!isFinite(n)) return "$\u2014";
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: n >= 1000 ? 0 : 2,
    maximumFractionDigits: n >= 1000 ? 0 : 2,
  });
}

export function fmtKrw(v: number | null | undefined): string {
  const n = v ?? 0;
  if (!isFinite(n)) return "₩\u2014";
  return "₩" + Math.round(n).toLocaleString("ko-KR");
}

/**
 * Format a 52-week range envelope as displayed text.
 *
 * Backend contract (routes/watchlist.py:74-87 — Bug #9 wire-up 2026-05-13):
 * - KRW: `[low_int, high_int]` (zero decimals)
 * - USD: `[low_2dp, high_2dp]`
 * - `null` when either bound is missing (NEVER fabricate "0 ~ 0")
 *
 * KR rows use "₩{lo} ~ ₩{hi}" with comma thousands.
 * US rows use "${lo} – {hi}" with en-dash.
 * Missing / malformed → "—".
 */
export function fmtRange52w(
  range: [number, number] | null | undefined,
  currency: "USD" | "KRW",
): string {
  if (!range || range.length !== 2) return "—";
  const [lo, hi] = range;
  if (
    lo == null || hi == null ||
    !Number.isFinite(lo) || !Number.isFinite(hi) ||
    lo <= 0 || hi <= 0 || hi < lo
  ) {
    return "—";
  }
  if (currency === "KRW") {
    return `₩${Math.round(lo).toLocaleString("ko-KR")} ~ ₩${Math.round(hi).toLocaleString("ko-KR")}`;
  }
  return `$${lo.toFixed(2)} – $${hi.toFixed(2)}`;
}

export function fmtPct(v: number | null | undefined): string {
  const n = v ?? 0;
  if (!isFinite(n)) return "\u2014";
  const s = n >= 0 ? "+" : "";
  return `${s}${n.toFixed(2)}%`;
}

export function pnlColor(v: number): string {
  if (v > 0) return "text-success";
  if (v < 0) return "text-destructive";
  return "text-muted-foreground";
}

/**
 * KR index sanity guards.
 *
 * 2026-04-28 incident: KIS API briefly returned KOSPI = 6,641.02 (~2x the
 * historical max of 3,316). Backend `data_fetcher.get_enhanced_macro` now
 * drops out-of-range readings, but we apply a second guard at the display
 * boundary so a stray value from any path (SSE, alternate endpoint, cached
 * payload) never renders as if live.
 *
 * Bounds intentionally mirror the backend defaults; widen via env only after
 * verifying with KRX/Yahoo (NEXT_PUBLIC_KOSPI_RANGE / _KOSDAQ_RANGE).
 */
function _parsePublicRange(envKey: string, fallback: [number, number]): [number, number] {
  if (typeof process === "undefined") return fallback;
  const raw = (process.env?.[envKey] ?? "").trim();
  if (!raw) return fallback;
  const parts = raw.split(",").map((s) => Number.parseFloat(s.trim()));
  if (parts.length !== 2 || parts.some((n) => !Number.isFinite(n))) return fallback;
  const [lo, hi] = parts as [number, number];
  if (!(lo > 0 && hi > lo)) return fallback;
  return [lo, hi];
}

// Default ranges per CEO directive 2026-04-29: ceiling 50,000 for both.
// Absorbs future re-rates without code change while still catching 100x
// unit-confusion glitches.
export const KOSPI_RANGE: [number, number] = _parsePublicRange(
  "NEXT_PUBLIC_KOSPI_RANGE",
  [1500, 50000],
);
export const KOSDAQ_RANGE: [number, number] = _parsePublicRange(
  "NEXT_PUBLIC_KOSDAQ_RANGE",
  [500, 50000],
);

export function isSaneKospi(level: number | null | undefined): level is number {
  return (
    typeof level === "number" &&
    Number.isFinite(level) &&
    level >= KOSPI_RANGE[0] &&
    level <= KOSPI_RANGE[1]
  );
}

export function isSaneKosdaq(level: number | null | undefined): level is number {
  return (
    typeof level === "number" &&
    Number.isFinite(level) &&
    level >= KOSDAQ_RANGE[0] &&
    level <= KOSDAQ_RANGE[1]
  );
}

/** Drop a KR index level if it falls outside its sanity window. */
export function sanitizeKrIndex(
  symbol: "KOSPI" | "KOSDAQ" | string,
  level: number | null | undefined,
): number | null {
  if (level == null) return null;
  if (symbol === "KOSPI" || symbol === "kospi" || symbol === "^KS11") {
    return isSaneKospi(level) ? level : null;
  }
  if (symbol === "KOSDAQ" || symbol === "kosdaq" || symbol === "^KQ11") {
    return isSaneKosdaq(level) ? level : null;
  }
  return Number.isFinite(level) ? level : null;
}

export function signalColor(signal: string): string {
  switch (signal) {
    case "POSITIVE":
      return "bg-success/15 text-success border-success/30";
    case "NEGATIVE":
      return "bg-destructive/15 text-destructive border-destructive/30";
    default:
      return "bg-warning/15 text-warning border-warning/30";
  }
}

export function scoreColor(score: number): string {
  if (score >= 70) return "bg-success";
  if (score >= 45) return "bg-warning";
  return "bg-destructive";
}

export function scoreTextColor(score: number): string {
  if (score >= 70) return "text-success";
  if (score >= 45) return "text-warning";
  return "text-destructive";
}

/**
 * KR convention price color tokens.
 * ▲ rising  = red  (#D18888 muted carmine)
 * ▼ falling = blue (#7AA0C8 muted indigo)
 * → flat    = ivory soft
 *
 * Single source of truth — every dashboard page uses this so the
 * convention can never split again. CEO directive 2026-04-26.
 */
export type PriceDir = "up" | "down" | "flat";

export function priceDir(value: number | null | undefined): PriceDir {
  if (value === null || value === undefined || Number.isNaN(value)) return "flat";
  if (!Number.isFinite(value)) return "flat";
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}

export const PRICE_COLOR_HEX = {
  up: "#D18888",
  down: "#7AA0C8",
  flat: "rgba(245, 240, 232, 0.55)",
} as const;

/** Returns hex color for a numeric pct/delta. KR convention. */
export function pctColor(value: number | null | undefined): string {
  return PRICE_COLOR_HEX[priceDir(value)];
}

/** Tailwind class variant — useful when style prop isn't ergonomic. */
export const PRICE_COLOR_CLASS = {
  up: "text-[#D18888]",
  down: "text-[#7AA0C8]",
  flat: "text-[rgba(245,240,232,0.55)]",
} as const;

export function pctColorClass(value: number | null | undefined): string {
  return PRICE_COLOR_CLASS[priceDir(value)];
}

export const PRICE_GLYPH = {
  up: "▲",
  down: "▼",
  flat: "·",
} as const;

export function priceGlyph(value: number | null | undefined): string {
  return PRICE_GLYPH[priceDir(value)];
}
