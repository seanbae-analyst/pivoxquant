/**
 * Mock fallback data for the Discover page.
 * Rendered when SWR hook returns error or empty results,
 * so the editorial page never appears visually broken
 * (FMP 402 / upstream failures are absorbed silently).
 */

export interface IndexCard {
  name: string;
  level: string;
  changePct: number;
}

export interface MoverRow {
  ticker: string;
  name: string;
  price: string;
  changePct: number;
}

export interface SectorRow {
  sector: string;
  d1: number;
  d5: number;
  m1: number;
}

export interface ThematicItem {
  ticker: string;
  name: string;
  metric: string;
  metricValue: string;
}

/* ── Market overview (5 indices) ── */
export const MOCK_INDICES: IndexCard[] = [
  { name: "S&P 500", level: "5,218.42", changePct: 0.31 },
  { name: "Nasdaq", level: "16,342.18", changePct: 0.58 },
  { name: "Dow", level: "38,912.55", changePct: -0.12 },
  { name: "KOSPI", level: "2,612.34", changePct: 0.42 },
  { name: "KOSDAQ", level: "847.91", changePct: -0.18 },
];

/* ── US Top Movers ── */
export const MOCK_US_GAINERS: MoverRow[] = [
  { ticker: "NVDA", name: "NVIDIA", price: "$918.42", changePct: 4.62 },
  { ticker: "AVGO", name: "Broadcom", price: "$1,312.10", changePct: 3.84 },
  { ticker: "AMD", name: "AMD", price: "$162.35", changePct: 3.15 },
  { ticker: "MU", name: "Micron", price: "$118.70", changePct: 2.91 },
  { ticker: "ASML", name: "ASML", price: "$1,024.50", changePct: 2.76 },
  { ticker: "TSM", name: "TSMC", price: "$142.85", changePct: 2.41 },
  { ticker: "SMCI", name: "Super Micro", price: "$842.10", changePct: 2.18 },
  { ticker: "ARM", name: "Arm Holdings", price: "$108.24", changePct: 2.04 },
  { ticker: "PLTR", name: "Palantir", price: "$24.80", changePct: 1.92 },
  { ticker: "CRWD", name: "CrowdStrike", price: "$312.40", changePct: 1.81 },
];

export const MOCK_US_LOSERS: MoverRow[] = [
  { ticker: "BA", name: "Boeing", price: "$184.20", changePct: -3.84 },
  { ticker: "LUV", name: "Southwest Air", price: "$28.14", changePct: -2.92 },
  { ticker: "F", name: "Ford", price: "$12.48", changePct: -2.64 },
  { ticker: "GM", name: "GM", price: "$42.30", changePct: -2.41 },
  { ticker: "WBA", name: "Walgreens", price: "$18.92", changePct: -2.18 },
  { ticker: "TGT", name: "Target", price: "$162.40", changePct: -1.95 },
  { ticker: "INTC", name: "Intel", price: "$34.20", changePct: -1.82 },
  { ticker: "PFE", name: "Pfizer", price: "$26.18", changePct: -1.74 },
  { ticker: "VZ", name: "Verizon", price: "$40.12", changePct: -1.62 },
  { ticker: "T", name: "AT&T", price: "$17.48", changePct: -1.41 },
];

/* ── KR Top Movers (영문 ticker format .KS / .KQ) ── */
export const MOCK_KR_GAINERS: MoverRow[] = [
  { ticker: "005930.KS", name: "Samsung Electronics", price: "₩78,400", changePct: 2.35 },
  { ticker: "000660.KS", name: "SK Hynix", price: "₩184,500", changePct: 1.92 },
  { ticker: "035420.KS", name: "NAVER", price: "₩218,000", changePct: 1.64 },
  { ticker: "207940.KS", name: "Samsung Biologics", price: "₩812,000", changePct: 1.28 },
  { ticker: "051910.KS", name: "LG Chem", price: "₩382,500", changePct: 1.04 },
];

export const MOCK_KR_LOSERS: MoverRow[] = [
  { ticker: "373220.KS", name: "LG Energy Solution", price: "₩342,500", changePct: -2.18 },
  { ticker: "005380.KS", name: "Hyundai Motor", price: "₩248,000", changePct: -1.84 },
  { ticker: "068270.KS", name: "Celltrion", price: "₩186,500", changePct: -1.42 },
  { ticker: "028260.KS", name: "Samsung C&T", price: "₩142,000", changePct: -1.18 },
  { ticker: "105560.KS", name: "KB Financial", price: "₩74,200", changePct: -0.92 },
];

/* ── Sector rotation (11 GICS) ── */
export const MOCK_SECTORS: SectorRow[] = [
  { sector: "Information Technology", d1: 0.84, d5: 2.41, m1: 4.62 },
  { sector: "Communication Services", d1: 0.62, d5: 1.82, m1: 3.14 },
  { sector: "Consumer Discretionary", d1: 0.38, d5: 1.24, m1: 2.18 },
  { sector: "Financials", d1: 0.21, d5: 0.84, m1: 1.62 },
  { sector: "Industrials", d1: 0.14, d5: 0.42, m1: 0.94 },
  { sector: "Health Care", d1: -0.08, d5: -0.12, m1: 0.32 },
  { sector: "Consumer Staples", d1: -0.12, d5: -0.34, m1: -0.18 },
  { sector: "Materials", d1: -0.24, d5: -0.62, m1: -0.84 },
  { sector: "Real Estate", d1: -0.38, d5: -0.92, m1: -1.42 },
  { sector: "Utilities", d1: -0.42, d5: -1.14, m1: -1.82 },
  { sector: "Energy", d1: -0.62, d5: -1.84, m1: -2.41 },
];

/* ── Thematic screeners ── */
export const MOCK_OVERSOLD: ThematicItem[] = [
  { ticker: "PFE", name: "Pfizer", metric: "RSI", metricValue: "27.4" },
  { ticker: "T", name: "AT&T", metric: "RSI", metricValue: "28.8" },
  { ticker: "VZ", name: "Verizon", metric: "RSI", metricValue: "29.1" },
  { ticker: "WBA", name: "Walgreens", metric: "RSI", metricValue: "29.6" },
  { ticker: "INTC", name: "Intel", metric: "RSI", metricValue: "30.2" },
  { ticker: "NKE", name: "Nike", metric: "RSI", metricValue: "30.8" },
  { ticker: "MMM", name: "3M", metric: "RSI", metricValue: "31.4" },
  { ticker: "TGT", name: "Target", metric: "RSI", metricValue: "31.9" },
];

export const MOCK_HIGHS_52W: ThematicItem[] = [
  { ticker: "NVDA", name: "NVIDIA", metric: "52W High", metricValue: "$918.42" },
  { ticker: "MSFT", name: "Microsoft", metric: "52W High", metricValue: "$428.15" },
  { ticker: "META", name: "Meta", metric: "52W High", metricValue: "$512.80" },
  { ticker: "AVGO", name: "Broadcom", metric: "52W High", metricValue: "$1,312.10" },
  { ticker: "GOOG", name: "Alphabet", metric: "52W High", metricValue: "$172.40" },
  { ticker: "LLY", name: "Eli Lilly", metric: "52W High", metricValue: "$784.20" },
  { ticker: "JPM", name: "JPMorgan", metric: "52W High", metricValue: "$201.34" },
  { ticker: "V", name: "Visa", metric: "52W High", metricValue: "$284.60" },
];

export const MOCK_EARNINGS_BEAT: ThematicItem[] = [
  { ticker: "NFLX", name: "Netflix", metric: "EPS surprise", metricValue: "+14.2%" },
  { ticker: "UNH", name: "UnitedHealth", metric: "EPS surprise", metricValue: "+8.4%" },
  { ticker: "BAC", name: "Bank of America", metric: "EPS surprise", metricValue: "+6.8%" },
  { ticker: "JNJ", name: "Johnson & Johnson", metric: "EPS surprise", metricValue: "+5.2%" },
  { ticker: "UAL", name: "United Airlines", metric: "EPS surprise", metricValue: "+4.6%" },
  { ticker: "MS", name: "Morgan Stanley", metric: "EPS surprise", metricValue: "+3.8%" },
];
