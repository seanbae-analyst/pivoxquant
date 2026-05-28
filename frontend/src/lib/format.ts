export function fmtUsd(v: number | null | undefined): string {
  const n = v ?? 0;
  if (!isFinite(n)) return "USD \u2014";
  // currencyDisplay:"code" emits the ISO code ("USD") but separates it from the
  // amount with a non-breaking / narrow-NBSP space \u2014 normalise to a plain space
  // so output is byte-consistent with the manual "KRW " / "USD " prefixes used
  // by the other formatters and asserted by tests.
  return n
    .toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      currencyDisplay: "code",
      minimumFractionDigits: n >= 1000 ? 0 : 2,
      maximumFractionDigits: n >= 1000 ? 0 : 2,
    })
    .replace(/[\u00a0\u202f]/g, " ");
}

export function fmtKrw(v: number | null | undefined): string {
  const n = v ?? 0;
  if (!isFinite(n)) return "KRW \u2014";
  return "KRW " + Math.round(n).toLocaleString("ko-KR");
}

/**
 * Format a 52-week range envelope as displayed text.
 *
 * Backend contract (routes/watchlist.py:74-87 — Bug #9 wire-up 2026-05-13):
 * - KRW: `[low_int, high_int]` (zero decimals)
 * - USD: `[low_2dp, high_2dp]`
 * - `null` when either bound is missing (NEVER fabricate "0 ~ 0")
 *
 * KR rows use "KRW {lo} ~ KRW {hi}" with comma thousands.
 * US rows use "USD {lo} – {hi}" with en-dash.
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
    return `KRW ${Math.round(lo).toLocaleString("ko-KR")} ~ KRW ${Math.round(hi).toLocaleString("ko-KR")}`;
  }
  return `USD ${lo.toFixed(2)} – USD ${hi.toFixed(2)}`;
}

export function fmtPct(v: number | null | undefined): string {
  // Data-honesty guard (\uc790\ubcf8\uc2dc\uc7a5\ubc95 \u00a7101): a missing value must NEVER be
  // fabricated as "+0.00%" (which reads as a real "no change" datapoint).
  // null/undefined \u2192 "\u2014". A genuine numeric 0 stays "+0.00%" (valid 0% move).
  if (v == null) return "\u2014";
  const n = v;
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

/* ──────────────────────────────────────────────────────────────────────────
 * Wave 2 additive helpers (2026-05-19 — Phase 1A infra).
 * Net-new functions only; existing signatures are frozen because 28+138
 * use sites depend on them. Anything that needs a different shape MUST
 * be a new name (e.g. fmtMoneySigned, not "fmtUsd with sign opt-in").
 * ────────────────────────────────────────────────────────────────────── */

/**
 * Money with an explicit sign prefix.
 *   +KRW 123,456   (positive KRW)
 *   −USD 1,234.56  (negative USD — U+2212 minus, NOT ASCII hyphen)
 *   ±USD 0         (zero — bronze "flat")
 * Used by P&L deltas, brag-card swing displays, weekly memo callouts where
 * the reader has to clock direction at a glance. fmtUsd / fmtKrw stay
 * sign-implicit so they remain safe inside formulas like "Total: KRW X".
 */
export function fmtMoneySigned(
  v: number | null | undefined,
  currency: "USD" | "KRW",
): string {
  const n = v ?? 0;
  if (!Number.isFinite(n)) return currency === "KRW" ? "KRW —" : "USD —";
  if (n === 0) {
    return currency === "KRW" ? "KRW 0" : "USD 0.00";
  }
  // U+2212 MINUS for negatives (typographic; matches KR convention rendering
  // in Pretendard/Playfair which would otherwise show a hyphen-minus).
  const sign = n > 0 ? "+" : "−";
  const abs = Math.abs(n);
  if (currency === "KRW") {
    return `${sign}KRW ${Math.round(abs).toLocaleString("ko-KR")}`;
  }
  return `${sign}${abs
    .toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      currencyDisplay: "code",
      minimumFractionDigits: abs >= 1000 ? 0 : 2,
      maximumFractionDigits: abs >= 1000 ? 0 : 2,
    })
    .replace(/[  ]/g, " ")}`;
}

/**
 * Compact money for tight surfaces (chart tooltips, KPI tiles, sparklines).
 *   USD: USD 1.2M / USD 3.4B / USD 1,234 (under 1M stays full)
 *   KRW: KRW 1.2억 / KRW 3,400만 / KRW 12,345 (KR myriad system: 만 / 억 / 조)
 * Returns the same "—" sentinels as fmtUsd/fmtKrw for non-finite inputs.
 */
export function fmtMoneyCompact(
  v: number | null | undefined,
  currency: "USD" | "KRW",
): string {
  const n = v ?? 0;
  if (!Number.isFinite(n)) return currency === "KRW" ? "KRW —" : "USD —";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (currency === "USD") {
    if (abs >= 1e12) return `${sign}USD ${(abs / 1e12).toFixed(1)}T`;
    if (abs >= 1e9)  return `${sign}USD ${(abs / 1e9 ).toFixed(1)}B`;
    if (abs >= 1e6)  return `${sign}USD ${(abs / 1e6 ).toFixed(1)}M`;
    if (abs >= 1e3)  return `${sign}USD ${(abs / 1e3 ).toFixed(1)}K`;
    return fmtUsd(n);
  }
  // KRW myriad scale (한국 만/억/조 표기).
  if (abs >= 1e12) return `${sign}KRW ${(abs / 1e12).toFixed(1)}조`;
  if (abs >= 1e8)  return `${sign}KRW ${(abs / 1e8 ).toFixed(1)}억`;
  if (abs >= 1e4)  return `${sign}KRW ${(abs / 1e4 ).toFixed(1)}만`;
  return fmtKrw(n);
}

/* ──────────────────────────────────────────────────────────────────────────
 * Wave 3 additive helpers (2026-05-19 — precision migration infra).
 *
 * Filling the gaps that Wave 2 sweep agents documented as the reason 17+
 * files kept their local `fmtPct`/`fmtMoney`/`fmtKrw` redefinitions. Each
 * helper here corresponds to a previously-inlined pattern with a precise,
 * named contract so the call sites can finally drop their local copies.
 *
 * Net-new functions only; existing fmt* signatures stay frozen.
 * ────────────────────────────────────────────────────────────────────── */

/**
 * Percent with FORCED sign and configurable precision (default 1dp).
 *   fmtPct1(12.3)   →  "+12.3%"
 *   fmtPct1(-5)     →  "-5.0%"
 *   fmtPct1(0)      →  "+0.0%"      (sign always present for non-NaN)
 *   fmtPct1(null)   →  "—"          (lib/fmtPct uses "+0.00%" for null)
 *
 * Differs from fmtPct in TWO ways:
 *   1. Default precision 1dp (was 2dp).  Hero/share-card headlines.
 *   2. null/undefined → "—", NOT "+0.00%".  Matches what every local
 *      fmtPct copy in components/* already does, so migrating away from
 *      those copies is now a 1-line swap with no visible change.
 *
 * Use for: portfolio-hero, what-if-result share card, equity-curve %,
 * positions-table P&L %, watchlist mover %.
 */
export function fmtPct1(
  v: number | null | undefined,
  dp: number = 1,
): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(dp)}%`;
}

/**
 * Percent without a sign prefix (magnitude only).
 *   fmtPctUnsigned(23.4)        →  "23.4%"
 *   fmtPctUnsigned(-5, 2)       →  "-5.00%"   (negative kept; only "+" is suppressed)
 *   fmtPctUnsigned(0)           →  "0.0%"
 *   fmtPctUnsigned(null)        →  "—"
 *
 * For columns where direction is conveyed by colour/arrow elsewhere
 * (donut tooltips, weight breakdowns, allocation pies).
 */
export function fmtPctUnsigned(
  v: number | null | undefined,
  dp: number = 1,
): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${v.toFixed(dp)}%`;
}

/**
 * KR myriad (만 / 억 / 조) money with TUNABLE precision per scale band.
 * Differs from fmtMoneyCompact's KRW branch by giving callers control over
 * decimal density:
 *   fmtKrwAbbrev(120_000_000)              →  "KRW 1.2억"     (default 1dp 억)
 *   fmtKrwAbbrev(120_000_000, {dpEok: 2})  →  "KRW 1.20억"
 *   fmtKrwAbbrev(34_000_000, {dpMan: 0})   →  "KRW 3,400만"   (default)
 *   fmtKrwAbbrev(-120_000_000)             →  "-KRW 1.2억"
 *   fmtKrwAbbrev(NaN)                      →  "KRW —"
 *
 * This is the helper the Wave 2 sweep was waiting for — the donut tooltip
 * wants `{dpEok: 2, dpMan: 0}`, the what-if hero wants `{dpEok: 2, dpMan: 0}`,
 * the chart tick wants `{dpEok: 1, dpMan: 0}`. All previously inlined.
 */
export interface KrwAbbrevOpts {
  /** decimals when value lands in 조 (≥ 1e12). default 1 */
  dpJo?: number;
  /** decimals when value lands in 억 (≥ 1e8).  default 1 */
  dpEok?: number;
  /** decimals when value lands in 만 (≥ 1e4).  default 0 */
  dpMan?: number;
  /**
   * Strip trailing zeros after the decimal point (Wave 4-B 2026-05-20).
   *   fmtKrwAbbrev(150_000_000, {dpEok: 2})                  → "KRW 1.50억"
   *   fmtKrwAbbrev(150_000_000, {dpEok: 2, trimTrailing:true})→ "KRW 1.5억"
   *   fmtKrwAbbrev(100_000_000, {dpEok: 2, trimTrailing:true})→ "KRW 1억"
   * Lets the what-if hero / share-card display compact magnitudes without
   * "1.00억" noise while still allowing other callers (DD report, ledger)
   * to lock a fixed precision.
   */
  trimTrailing?: boolean;
}

export function fmtKrwAbbrev(
  v: number | null | undefined,
  opts: KrwAbbrevOpts = {},
): string {
  if (v == null || !Number.isFinite(v)) return "KRW —";
  const { dpJo = 1, dpEok = 1, dpMan = 0, trimTrailing = false } = opts;
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  // Each band: divide, fix to N dp, then re-localise so thousand-group
  // separators come back ("KRW 3,400만" not "KRW 3400만"). Negative dp is treated
  // as 0. The toFixed() rounds half-away-from-zero; that matches both the
  // donut tooltip and the what-if hero contract from Wave 2 sweep notes.
  const fmtBand = (scaled: number, dp: number, suffix: string): string => {
    const d = Math.max(0, dp);
    // toFixed first to lock decimals, then split + localise the integer half.
    const fixed = scaled.toFixed(d);
    const [intPart, fracPartRaw] = fixed.split(".");
    let fracPart = fracPartRaw;
    if (trimTrailing && fracPart) {
      // Drop trailing zeros: "50" → "5", "00" → "". Keeps intentional rounding
      // (toFixed already happened) so "1.234" with dp=2 reads "1.23" still.
      fracPart = fracPart.replace(/0+$/, "");
    }
    const grouped = Number(intPart).toLocaleString("ko-KR");
    return `${sign}KRW ${fracPart ? `${grouped}.${fracPart}` : grouped}${suffix}`;
  };
  if (abs >= 1e12) return fmtBand(abs / 1e12, dpJo, "조");
  if (abs >= 1e8)  return fmtBand(abs / 1e8,  dpEok, "억");
  if (abs >= 1e4)  return fmtBand(abs / 1e4,  dpMan, "만");
  return `${sign}KRW ${Math.round(abs).toLocaleString("ko-KR")}`;
}

/**
 * USD with NO automatic decimal-switching and NO sign prefix.
 *   fmtUsdPlain(1234)         →  "USD 1,234"           (default dp = 0)
 *   fmtUsdPlain(1234.56, 2)   →  "USD 1,234.56"
 *   fmtUsdPlain(-1234)        →  "-USD 1,234"
 *   fmtUsdPlain(NaN)          →  "USD —"
 *
 * fmtUsd has an implicit precision switch at 1000 (2dp under, 0dp over).
 * Hero numbers, transaction rows, and table cells often want a single
 * deterministic precision — that's this helper.
 */
export function fmtUsdPlain(
  v: number | null | undefined,
  dp: number = 0,
): string {
  if (v == null || !Number.isFinite(v)) return "USD —";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  return `${sign}USD ${abs.toLocaleString("en-US", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  })}`;
}

/**
 * Display-ready ticker label.
 *   displayTicker("005930.KS", "삼성전자")  →  "삼성전자"
 *   displayTicker("005930.KS")              →  "삼성전자"   (seed lookup)
 *   displayTicker("999999.KS")              →  "999999"     (suffix stripped)
 *   displayTicker("AAPL", "Apple Inc.")     →  "Apple Inc." (backend wins)
 *   displayTicker("AAPL")                   →  "Apple"      (seed)
 *   displayTicker(null)                     →  ""
 *
 * Differs from displayName() in that the suffix is ALWAYS stripped when the
 * fallback is the raw ticker (we never want "005930.KS" surfacing). Use this
 * for table cells, badges, anywhere the ticker is the visible label.
 *
 * CEO directive feedback_ticker_display: a naked 6-digit code is illegible —
 * always prefer name, only fall back to the bare code when seed misses.
 */
export function displayTicker(
  symbol: string | null | undefined,
  name?: string | null,
): string {
  if (!symbol) return (name ?? "").trim();
  // 1. Explicit backend name wins (when it's actually a name, not a ticker echo).
  const trimmedName = (name ?? "").trim();
  if (
    trimmedName &&
    normalizeTicker(trimmedName) !== normalizeTicker(symbol) &&
    trimmedName.toUpperCase() !== symbol.trim().toUpperCase()
  ) {
    return trimmedName;
  }
  // 2. Static seed (covers KOSPI/KOSDAQ majors + US seed names).
  const seeded = tickerToName(symbol);
  if (seeded) return seeded;
  // 3. Bare ticker with KS/KQ/KRX/KR suffix stripped.
  return normalizeTicker(symbol) || symbol.trim();
}

/* ──────────────────────────────────────────────────────────────────────────
 * Wave 4-B additive helpers (2026-05-20 — Wave 3 follow-up).
 *
 * Closing the gaps that Wave 3 sweep documented as the reason positions /
 * watchlist / ledger / recent-transactions kept their local fmt copies.
 * Net-new functions only; existing fmt* signatures stay frozen.
 * ────────────────────────────────────────────────────────────────────── */

/**
 * Percent with FORCED sign using U+2212 MINUS (not ASCII hyphen) and
 * magnitude via Math.abs(). Mirrors positions-table-v2 / watchlist-mini /
 * ledger-book-paper local pattern so callers can migrate 1:1.
 *
 *   fmtPctSignedMinus(12.3)         →  "+12.30%"
 *   fmtPctSignedMinus(-5)           →  "−5.00%"        (U+2212, not "-")
 *   fmtPctSignedMinus(0)            →  "0.00%"         (no sign at zero)
 *   fmtPctSignedMinus(null)         →  "—"
 *   fmtPctSignedMinus(12.345, 1)    →  "+12.3%"
 *
 * Differs from `fmtPct`:
 *   - U+2212 vs ASCII "-" for negatives (typographic minus matches
 *     Pretendard/Playfair render across KR/Latin glyph runs).
 *   - n === 0 emits NO sign ("0.00%") instead of "+0.00%".
 *   - n == null / non-finite → "—" instead of "+0.00%".
 *   - Configurable precision (default 2dp matches fmtPct).
 *
 * Differs from `fmtPct1`:
 *   - Uses U+2212; fmtPct1 uses ASCII "-".
 *   - n === 0 emits NO sign; fmtPct1 emits "+0.0%".
 *
 * Use for: positions P&L %, watchlist mover %, ledger row % columns.
 */
export function fmtPctSignedMinus(
  v: number | null | undefined,
  dp: number = 2,
): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  return `${sign}${Math.abs(v).toFixed(dp)}%`;
}

/**
 * Money with deterministic precision and NO automatic scale switching.
 *   fmtMoneyPlain(1234.56, "USD")      →  "USD 1,234.56"  (default dp=0 -> "USD 1,235", caller passes 2 here)
 *   fmtMoneyPlain(1234.56, "USD", 2)   →  "USD 1,234.56"
 *   fmtMoneyPlain(1234.56, "USD", 0)   →  "USD 1,235"
 *   fmtMoneyPlain(-1234, "USD", 2)     →  "-USD 1,234.00" (ASCII "-")
 *   fmtMoneyPlain(1234567, "KRW")      →  "KRW 1,234,567"
 *   fmtMoneyPlain(null, "USD")         →  "—"          (single em-dash, currency-agnostic)
 *   fmtMoneyPlain(NaN, "KRW")          →  "—"
 *
 * Differs from fmtUsd / fmtKrw:
 *   - Caller chooses precision; no n>=1000 switch.
 *   - Non-finite returns "—" (not "USD —" / "KRW —") to match the
 *     positions-table / watchlist / recent-transactions local pattern
 *     where "—" sits in a typographic ivory cell with no leading glyph.
 *   - ASCII "-" for negatives (matches all 4 local sites; fmtMoneySigned
 *     uses U+2212 which would be a visible shift).
 *
 * KRW always rounds (whole-won is the only valid display).
 *
 * Use for: positions-table-v2 fmtMoney, watchlist-mini fmtMoney,
 * recent-transactions-block fmtMoney/fmtSignedAmount, positions-top-card.
 */
export function fmtMoneyPlain(
  v: number | null | undefined,
  currency: "USD" | "KRW",
  dp: number = 0,
): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  const glyph = currency === "KRW" ? "KRW " : "USD ";
  if (currency === "KRW") {
    return `${sign}${glyph}${Math.round(abs).toLocaleString("ko-KR")}`;
  }
  const body = abs.toLocaleString("en-US", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  });
  return `${sign}${glyph}${body}`;
}

/**
 * Like fmtMoneyPlain but with an EXPLICIT +/- sign for non-zero values.
 *   fmtMoneyPlainSigned(1234, "USD", 2)  →  "+USD 1,234.00"
 *   fmtMoneyPlainSigned(-1234, "USD", 2) →  "−USD 1,234.00" (U+2212)
 *   fmtMoneyPlainSigned(0, "USD", 2)     →  "—"          (zero -> no row)
 *   fmtMoneyPlainSigned(null, "USD")     →  "—"
 *
 * Matches the recent-transactions-block fmtSignedAmount contract:
 * zero/null collapse to "—" so the column stays uncluttered on no-op rows.
 */
export function fmtMoneyPlainSigned(
  v: number | null | undefined,
  currency: "USD" | "KRW",
  dp: number = 0,
): string {
  if (v == null || !Number.isFinite(v) || v === 0) return "—";
  const sign = v > 0 ? "+" : "−";
  const abs = Math.abs(v);
  const glyph = currency === "KRW" ? "KRW " : "USD ";
  if (currency === "KRW") {
    return `${sign}${glyph}${Math.round(abs).toLocaleString("ko-KR")}`;
  }
  const body = abs.toLocaleString("en-US", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  });
  return `${sign}${glyph}${body}`;
}

/* ──────────────────────────────────────────────────────────────────────────
 * Wave B i18n — locale-aware compact number helper (2026-05-28).
 *
 * fmtCompactLocale(n, locale) renders abbreviated large numbers:
 *   ko: 만/억/조 scale  (1_200_000 → "120만",  150_000_000 → "1.5억")
 *   en: K/M/B/T scale   (1_200_000 → "1.2M",   150_000_000 → "150M")
 *
 * Pure function — no React dependency. Callers in client components should
 * obtain locale from useLocale() and pass it here.
 * ────────────────────────────────────────────────────────────────────────── */

export type FormatLocale = "ko" | "en";

/**
 * Compact large number abbreviation, locale-aware.
 *   ko: Korean myriad (만/억/조)
 *   en: SI prefix (K/M/B/T)
 * Returns raw number string (no currency prefix) — wrap with currency symbol
 * at the call site if needed.
 */
export function fmtCompactLocale(
  v: number | null | undefined,
  locale: FormatLocale = "ko",
): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";

  if (locale === "ko") {
    if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(1)}조`;
    if (abs >= 1e8)  return `${sign}${(abs / 1e8).toFixed(1)}억`;
    if (abs >= 1e4)  return `${sign}${(abs / 1e4).toFixed(0)}만`;
    return `${sign}${Math.round(abs).toLocaleString("ko-KR")}`;
  }
  // en: SI prefix
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(1)}T`;
  if (abs >= 1e9)  return `${sign}${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6)  return `${sign}${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3)  return `${sign}${(abs / 1e3).toFixed(1)}K`;
  return `${sign}${Math.round(abs).toLocaleString("en-US")}`;
}

/**
 * Locale-aware compact KRW/USD money string.
 *   ko + KRW → "KRW 1.5억" (myriad)
 *   en + KRW → "KRW 150M"  (SI prefix, KRW still labeled for clarity)
 *   any + USD → "USD 1.5M" (SI prefix always for USD)
 */
export function fmtMoneyCompactLocale(
  v: number | null | undefined,
  currency: "USD" | "KRW",
  locale: FormatLocale = "ko",
): string {
  if (v == null || !Number.isFinite(v))
    return currency === "KRW" ? "KRW —" : "USD —";
  const prefix = currency === "KRW" ? "KRW " : "USD ";
  if (currency === "KRW" && locale === "ko") {
    // Use native Korean myriad scale.
    return `${prefix}${fmtCompactLocale(v, "ko")}`;
  }
  // USD or en+KRW: use SI prefix.
  return `${prefix}${fmtCompactLocale(v, "en")}`;
}
