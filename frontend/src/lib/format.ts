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
