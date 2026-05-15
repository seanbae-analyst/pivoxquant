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

/* ──────────────────────────────────────────────────────────────────────────
 * Ticker → company name (audit FINDING-011/012/013/017/026).
 *
 * CEO directive [feedback_ticker_display] (repeated 3+ times): a naked
 * 6-digit code ("005930") is illegible to a KR retail user — always prefer
 * the company name ("삼성전자"), with the ticker demoted to a subtitle.
 *
 * Resolution order at every callsite should be:
 *   backend payload `name`  →  resolveTickerName(positions/watchlist)
 *   →  tickerToName() static seed  →  raw ticker (last resort)
 *
 * This static seed only needs to cover the seed dataset + KOSPI/KOSDAQ
 * majors so that even an unauthenticated / cold-cache surface never leaks a
 * bare code. The backend resolve_stock_name() remains the source of truth
 * for the long tail.
 * ────────────────────────────────────────────────────────────────────────── */

/** Strip exchange suffix and uppercase: "005930.KS" → "005930". */
export function normalizeTicker(raw: string | null | undefined): string {
  if (!raw) return "";
  return raw
    .trim()
    .toUpperCase()
    .replace(/\.(KS|KQ|KRX|KR)$/i, "");
}

// Curated seed — KR majors keyed by bare 6-digit code, US seed names by symbol.
// Keep small and high-confidence; the backend covers the long tail.
const TICKER_NAME_SEED: Readonly<Record<string, string>> = {
  // KOSPI majors
  "005930": "삼성전자",
  "000660": "SK하이닉스",
  "207940": "삼성바이오로직스",
  "005380": "현대차",
  "051910": "LG화학",
  "006400": "삼성SDI",
  "035420": "NAVER",
  "035720": "카카오",
  "005490": "POSCO홀딩스",
  "000270": "기아",
  "068270": "셀트리온",
  "105560": "KB금융",
  "055550": "신한지주",
  "012330": "현대모비스",
  "066570": "LG전자",
  "003670": "포스코퓨처엠",
  "028260": "삼성물산",
  "096770": "SK이노베이션",
  "017670": "SK텔레콤",
  "015760": "한국전력",
  // KOSDAQ majors
  "247540": "에코프로비엠",
  "086520": "에코프로",
  "091990": "셀트리온헬스케어",
  "196170": "알테오젠",
  "263750": "펄어비스",
  // US seed names
  AAPL: "Apple",
  MSFT: "Microsoft",
  GOOGL: "Alphabet",
  AMZN: "Amazon",
  NVDA: "NVIDIA",
  META: "Meta",
  TSLA: "Tesla",
  BRK: "Berkshire Hathaway",
  JPM: "JPMorgan Chase",
  V: "Visa",
};

/**
 * Resolve a ticker to its display name from the static seed.
 * Returns `null` when unknown — callers should fall back to the raw ticker
 * (or, better, a backend-supplied name) themselves.
 */
export function tickerToName(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const bare = normalizeTicker(raw);
  if (bare in TICKER_NAME_SEED) return TICKER_NAME_SEED[bare];
  const upper = (raw ?? "").trim().toUpperCase();
  if (upper in TICKER_NAME_SEED) return TICKER_NAME_SEED[upper];
  return null;
}

/**
 * Best-effort display name: prefer an explicit backend name, else the static
 * seed, else the raw ticker. Never returns an empty string for a real input.
 */
export function displayName(
  ticker: string | null | undefined,
  backendName?: string | null,
): string {
  const trimmed = (backendName ?? "").trim();
  // Reject a backend "name" that is just the ticker echoed back.
  if (
    trimmed &&
    normalizeTicker(trimmed) !== normalizeTicker(ticker) &&
    trimmed.toUpperCase() !== (ticker ?? "").trim().toUpperCase()
  ) {
    return trimmed;
  }
  return tickerToName(ticker) ?? (ticker ?? "").trim();
}

/** True when a string looks like a bare exchange ticker (no company name). */
export function isNakedTicker(s: string | null | undefined): boolean {
  if (!s) return false;
  const t = s.trim();
  // 6-digit KR code (optionally suffixed) or 1-5 char all-caps US symbol.
  return /^\d{6}(\.\w{1,4})?$/.test(t) || /^[A-Z]{1,5}(\.\w{1,4})?$/.test(t);
}

/** Is this ticker a KR-listed (KRW-quoted) symbol? */
export function isKrTicker(raw: string | null | undefined): boolean {
  if (!raw) return false;
  const t = raw.trim().toUpperCase();
  if (/\.(KS|KQ|KRX|KR)$/.test(t)) return true;
  // Bare 6-digit numeric code with no suffix — KR convention.
  return /^\d{6}$/.test(t);
}

/** Currency-aware money format chosen from the ticker, not a hardcoded "$". */
export function fmtMoneyForTicker(
  value: number | null | undefined,
  ticker: string | null | undefined,
): string {
  return isKrTicker(ticker) ? fmtKrw(value) : fmtUsd(value);
}
