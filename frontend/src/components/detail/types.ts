/**
 * Shared types + helpers for the /detail/[ticker] redesign.
 *
 * Extracted verbatim (logic-preserving) from the former 1792-line monolithic
 * page.tsx during the 2026-05-20 "Terminal Above, Editorial Below" redesign.
 * The page now owns data orchestration only; presentation lives in the
 * sibling component files which all import from here.
 *
 * Signals: POSITIVE / NEGATIVE / NEUTRAL only — BUY/SELL banned by law.
 */

import { fmtUsd, fmtKrw } from "@/lib/format";

/* ── Backend response shapes ── */

export interface Snapshot {
  pe_ratio?: number | null;
  eps?: number | null;
  beta?: number | null;
  market_cap?: number | null;
  avg_volume?: number | null;
  week52_high?: number | null;
  week52_low?: number | null;
  industry?: string;
  profit_margin?: number | null;
  revenue_growth?: number | null;
  debt_equity?: number | null;
}

export interface SignalDetail {
  ticker: string;
  name: string;
  signal: string;
  score: number;
  price: number;
  change_pct: number;
  sector: string;
  currency: "USD" | "KRW";
  is_korean: boolean;
  tp_pct: number;
  sl_pct: number;
  tech_score?: number;
  fund_score?: number;
  news_score?: number;
  quant_score?: number;
  snapshot?: Snapshot;
  observed_at?: string | null;
}

export interface ChartPoint {
  date: string;
  close: number;
}
export interface ChartResponse {
  data: ChartPoint[];
}

export interface NewsItem {
  title: string;
  link: string;
  source: string;
  published: string;
}
export interface NewsResponse {
  news: NewsItem[];
}

// Insider Form 4 — SEC EDGAR, US tickers only.
export interface InsiderFiling {
  insider?: string;
  relationship?: string;
  transaction_date?: string;
  transaction_code?: string;
  shares?: number;
  price?: number;
  value_usd?: number;
  acquired?: boolean;
}
export interface InsiderResponse {
  ticker?: string;
  data?: InsiderFiling[];
  source?: string;
}

export interface ProfileData {
  ticker?: string;
  name?: string;
  summary?: string;
  sector?: string;
  industry?: string;
  website?: string;
  employees?: number | null;
  country?: string;
  market_cap?: number | null;
  currency?: "USD" | "KRW";
}

// AI SWOT — POST /api/ai/swot
export interface SwotResponse {
  swot?: string;
  swot_kr?: string;
}

// Earnings calendar — GET /api/earnings (filtered by ticker client-side).
// Backend (routes/market.py:440) returns:
//   { earnings: [{ ticker, name, date, signal, score }] }
// `signal` is POSITIVE/NEGATIVE/NEUTRAL/—. eps_*/revenue_* fields are
// kept optional for forward-compat if backend ever extends the schema.
export interface EarningsItem {
  ticker?: string;
  symbol?: string; // alias compat — not currently emitted
  name?: string;
  date?: string;
  signal?: "POSITIVE" | "NEGATIVE" | "NEUTRAL" | "—" | string;
  score?: number;
  eps_estimate?: number | null; // forward-compat (unused today)
  eps_actual?: number | null;
  revenue_estimate?: number | null;
  revenue_actual?: number | null;
}
export interface EarningsResponse {
  earnings?: EarningsItem[];
  data?: EarningsItem[];
}

/* ── Chart periods ── */

// Backend accepts 1mo/3mo/6mo/1y/2y (routes/market.py L295). 2Y is server max.
export const PERIODS = ["1M", "3M", "6M", "1Y", "2Y"] as const;
export type Period = (typeof PERIODS)[number];
export const PERIOD_MAP: Record<Period, string> = {
  "1M": "1mo",
  "3M": "3mo",
  "6M": "6mo",
  "1Y": "1y",
  "2Y": "2y",
};

/* ── SWR fetcher (shared) ── */

export const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

/* ── Currency / number helpers ── */

export function isKrw(signal: SignalDetail | undefined, ticker: string): boolean {
  if (signal?.currency === "KRW") return true;
  if (signal?.is_korean === true) return true;
  return /^\d{6}\.(KS|KQ)$/i.test(ticker);
}

export function fmtPrice(value: number | undefined | null, krw: boolean): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return krw ? fmtKrw(value) : fmtUsd(value);
}

export function fmtMcap(value: number | null | undefined, krw: boolean): string {
  if (value == null || value <= 0) return "—";
  if (krw) {
    if (value >= 1e12) return `${(value / 1e12).toFixed(1)}조`;
    if (value >= 1e8) return `${(value / 1e8).toFixed(0)}억`;
    return `${value.toLocaleString()}`;
  }
  if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(0)}M`;
  return `$${value.toLocaleString()}`;
}

/**
 * Split a formatted market cap into { number, suffix } so the unit modifier
 * (조 / 억 / T / B / M) can render visually subordinate to the digits
 * (audit FINDING-035). The suffix is the trailing run of non-digit, non-dot,
 * non-comma characters; "$" prefixes stay with the number.
 */
export function splitMcap(formatted: string): { num: string; suffix: string } {
  if (formatted === "—") return { num: "—", suffix: "" };
  const m = formatted.match(/^([$]?[\d.,]+)([^\d.,]*)$/);
  if (!m) return { num: formatted, suffix: "" };
  return { num: m[1], suffix: m[2] };
}

export function pillarToken(label: string): "POSITIVE" | "NEGATIVE" | "NEUTRAL" {
  return label === "POSITIVE"
    ? "POSITIVE"
    : label === "NEGATIVE"
      ? "NEGATIVE"
      : "NEUTRAL";
}

/** Short relative time — "3d ago", "2w ago", "—". Observation tone only. */
export function formatRelative(iso: string | undefined): string {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (isNaN(parsed.getTime())) return "—";
  const diffMs = Date.now() - parsed.getTime();
  if (diffMs < 0) return "—";
  const days = Math.floor(diffMs / 86_400_000);
  if (days < 1) return "today";
  if (days === 1) return "1d ago";
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return weeks === 1 ? "1w ago" : `${weeks}w ago`;
  const months = Math.floor(days / 30);
  return months === 1 ? "1mo ago" : `${months}mo ago`;
}

/** Lightweight keyword-based news sentiment — editorial classifier, observation-only. */
export function classifyNewsSentiment(title: string): "pos" | "neg" | "neu" {
  const t = title.toLowerCase();
  const pos = [
    "beat", "beats", "surge", "surges", "rally", "rallies", "record high",
    "upgrade", "raised", "strong", "growth", "profit", "buyback",
    "partnership", "approval", "wins", "boost", "breakthrough",
    "outperform", "exceeds", "milestone", "expands",
  ];
  const neg = [
    "miss", "misses", "plunge", "plunges", "drop", "drops", "decline",
    "downgrade", "cut", "weak", "lawsuit", "probe", "investigation",
    "recall", "loss", "fraud", "bankruptcy", "warns", "warning",
    "layoffs", "halt", "suspends", "scandal", "subpoena", "underperform",
  ];
  for (const w of pos) if (t.includes(w)) return "pos";
  for (const w of neg) if (t.includes(w)) return "neg";
  return "neu";
}

/** Bucket news items by human day label ("Today", "Yesterday", "Apr 18"). */
export function bucketNewsByDay(
  items: NewsItem[],
): Array<{ label: string; items: NewsItem[] }> {
  const buckets = new Map<string, NewsItem[]>();
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const dayMs = 86_400_000;

  for (const n of items) {
    const dt = new Date(n.published);
    const ts = isNaN(dt.getTime()) ? NaN : dt.getTime();
    let label: string;
    if (!Number.isFinite(ts)) {
      label = "Undated";
    } else {
      const local = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()).getTime();
      const delta = today - local;
      if (delta <= 0) label = "Today";
      else if (delta < dayMs * 1.5) label = "Yesterday";
      else if (delta < dayMs * 7) {
        label = dt.toLocaleDateString("en-US", { weekday: "long" });
      } else {
        label = dt.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      }
    }
    const arr = buckets.get(label) ?? [];
    arr.push(n);
    buckets.set(label, arr);
  }
  return Array.from(buckets.entries()).map(([label, items]) => ({ label, items }));
}

/** Currency-aware price formatter pair for the chart. */
export function priceFormatter(currency: "USD" | "KRW") {
  return currency === "KRW" ? fmtKrw : fmtUsd;
}
