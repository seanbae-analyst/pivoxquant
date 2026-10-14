/**
 * 월급날 배분 — the user's own payday split, kept ON THIS DEVICE ONLY.
 *
 * 2026-10-14. On payday the user writes how they mean to split the money that
 * came in (생활비 · 저축 · 투자 · 기타, optionally the amount itself); the
 * investment part is then set next to what their own recorded fills actually
 * put in over that pay cycle, and at the next payday they say how the other
 * parts went.
 *
 * Why nothing here reaches the server (docs/design/payday-allocation_2026-10-14.md)
 * ---------------------------------------------------------------------------
 * A self-entered income amount is personal information, and income sits in the
 * 신용정보법 list of "신용거래능력 판단 정보"; next to trade records it may be
 * read as 개인신용정보 (금융위 법령해석 2023-04-03). Without a lawyer's opinion
 * the safest design is not to collect it at all: every amount lives in this
 * browser's localStorage, keyed by user id, and is never sent anywhere — no API
 * call, no URL, no analytics, no log. The only network reads are the user's own
 * trades (GET /api/portfolio/trades, already collected) and the USD/KRW rate
 * (GET /api/market/fx), both computed against locally. Same posture as the
 * import masking that never lets account lines leave the device
 * (lib/fill-ocr/mask.ts).
 *
 * Product posture (legal-kr-fintech review 2026-10-14): four fixed parts with
 * amounts only — no free-text labels (a "병원비" label would be health data);
 * no ratios, templates or default amounts (a suggested split reads as advice on
 * how much to invest); the comparison is a fact against the user's own number,
 * never a directive; nothing is said before a trade, only after.
 *
 * Pure functions + a thin storage layer, so every branch is unit-testable.
 */

export const PAYDAY_STORAGE_PREFIX = "pq.payday.v1.u";
/** Pay cycles kept on the device (newest last). Two years of monthly pay. */
export const MAX_CYCLES = 24;
/** GET /api/portfolio/trades caps at 100 rows (routes/portfolio.py). */
export const TRADE_FETCH_LIMIT = 100;

/** The four fixed parts. No free-text labels (see module doc). */
export const PART_KEYS = ["living", "saving", "invest", "other"] as const;
export type PartKey = (typeof PART_KEYS)[number];

export const PART_LABEL: Record<PartKey, string> = {
  living: "생활비",
  saving: "저축",
  invest: "투자",
  other: "기타",
};

/** The parts the user looks back on themselves — 투자 is measured from fills. */
export const REVIEWED_PARTS = ["living", "saving", "other"] as const;
export type ReviewedPart = (typeof REVIEWED_PARTS)[number];

/** How a non-investment part went, in the user's own words. */
export type PartReview = "as_planned" | "less" | "more";
export const REVIEW_LABEL: Record<PartReview, string> = {
  as_planned: "계획대로",
  less: "덜",
  more: "더",
};

/** What a typed actual amount says about the part, against what was set. */
export function reviewFor(planned: number, actual: number): PartReview {
  return actual > planned ? "more" : actual < planned ? "less" : "as_planned";
}

export interface CyclePlan {
  /** KST date the cycle starts (the payday), "YYYY-MM-DD". */
  start: string;
  /** Money that came in this payday (KRW). Optional — null = not written. */
  income: number | null;
  /** KRW per part; null = left blank. */
  parts: Record<PartKey, number | null>;
  /** Self-report for the non-investment parts, written at the next payday. */
  review?: Partial<Record<ReviewedPart, PartReview>>;
  /**
   * What the user says a non-investment part actually came to (KRW), read off
   * their own bank app at the next payday. Optional per part — the quick
   * 계획대로 / 덜 / 더 answer stands without it. Stays in this browser like
   * every other amount here.
   */
  actual?: Partial<Record<ReviewedPart, number>>;
  savedAt: string;
}

export interface PaydayStore {
  v: 1;
  /** Day of month 1–31; 31 also means "the last day" in shorter months. */
  payday: number | null;
  cycles: CyclePlan[];
}

export const EMPTY_STORE: PaydayStore = { v: 1, payday: null, cycles: [] };

/* ── Dates (KST calendar days as "YYYY-MM-DD") ─────────────────────────── */

const KST_MS = 9 * 60 * 60 * 1000;

/** Today's KST calendar date. */
export function kstToday(now: Date = new Date()): string {
  return new Date(now.getTime() + KST_MS).toISOString().slice(0, 10);
}

function daysInMonth(y: number, m: number): number {
  // m is 1-based; day 0 of the next month = last day of this one.
  return new Date(Date.UTC(y, m, 0)).getUTCDate();
}

function ymd(y: number, m: number, d: number): string {
  return `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

/** The payday that falls in month (y, m): the chosen day, or the month's last day. */
export function paydayIn(y: number, m: number, payday: number): string {
  return ymd(y, m, Math.min(payday, daysInMonth(y, m)));
}

/**
 * The pay cycle `today` falls in: [start, end) where start is the most recent
 * payday on or before today and end is the next payday.
 */
export function cycleFor(today: string, payday: number): { start: string; end: string } {
  const [y, m] = today.split("-").map(Number);
  const thisMonth = paydayIn(y, m, payday);
  if (today >= thisMonth) {
    const [ny, nm] = m === 12 ? [y + 1, 1] : [y, m + 1];
    return { start: thisMonth, end: paydayIn(ny, nm, payday) };
  }
  const [py, pm] = m === 1 ? [y - 1, 12] : [y, m - 1];
  return { start: paydayIn(py, pm, payday), end: thisMonth };
}

/** The cycle right before the one starting at `start`. */
export function previousCycle(start: string, payday: number): { start: string; end: string } {
  const [y, m] = start.split("-").map(Number);
  const [py, pm] = m === 1 ? [y - 1, 12] : [y, m - 1];
  return { start: paydayIn(py, pm, payday), end: start };
}

/** "2026-10-25" → "10월 25일". */
export function shortDate(d: string): string {
  const [, m, day] = d.split("-").map(Number);
  return `${m}월 ${day}일`;
}

/* ── Plan arithmetic ───────────────────────────────────────────────────── */

/** Sum of the written parts (blank parts count as 0). */
export function partsTotal(parts: Record<PartKey, number | null>): number {
  return PART_KEYS.reduce((s, k) => s + (parts[k] ?? 0), 0);
}

/** Income minus the written parts, or null when no income was written. */
export function unassigned(plan: Pick<CyclePlan, "income" | "parts">): number | null {
  if (plan.income === null) return null;
  return plan.income - partsTotal(plan.parts);
}

/* ── What the user's own fills put in over a cycle ─────────────────────── */

/** One row of GET /api/portfolio/trades (backend shape) or the demo fixture. */
export interface TradeRowLike {
  date?: string;
  side?: string;
  total?: number;
  amount?: number;
  qty?: number;
  shares?: number;
  price?: number;
  currency?: string;
  source?: string | null;
}

/** Rows a holding-registration path wrote — not fills (models/trade_history.py). */
const REGISTRATION_SOURCES = new Set(["holding_seed", "holding_adjust"]);

function sideOf(row: TradeRowLike): "in" | "out" | null {
  const s = (row.side ?? "").toLowerCase();
  if (s === "bought" || s === "buy") return "in"; // legal-ok — API field value, compared only
  if (s === "sold" || s === "sell") return "out"; // legal-ok — API field value, compared only
  return null;
}

function amountOf(row: TradeRowLike): number {
  const direct = row.total ?? row.amount;
  if (typeof direct === "number" && Number.isFinite(direct)) return Math.abs(direct);
  const qty = row.qty ?? row.shares ?? 0;
  const price = row.price ?? 0;
  return Math.abs(qty * price);
}

export interface CurrencyFlow {
  /** Spent on fills that added to holdings. */
  in: number;
  /** Received from fills that reduced holdings. */
  out: number;
  /** in − out: money the cycle's fills put in. */
  net: number;
}

export interface CycleFlow {
  KRW: CurrencyFlow;
  USD: CurrencyFlow;
  /** Fills counted. */
  fills: number;
  /** KRW + USD × fx, or null when USD fills exist and no rate is known. */
  netKrw: number | null;
  /** The fetch hit its row cap and the oldest row is inside the cycle —
   *  earlier fills of this cycle may be missing. */
  truncated: boolean;
}

/**
 * Money the user's own recorded fills put in over [start, end).
 *
 * Dates come from the API as UTC dates; cycle edges are KST days. A fill in
 * the first nine hours of a KST day lands on the previous date — accepted for
 * a "대략값", and said so on screen.
 */
export function cycleFlow(
  rows: TradeRowLike[],
  start: string,
  end: string,
  usdKrw: number | null,
  fetchLimit: number = TRADE_FETCH_LIMIT,
): CycleFlow {
  const zero = (): CurrencyFlow => ({ in: 0, out: 0, net: 0 });
  const flow: CycleFlow = { KRW: zero(), USD: zero(), fills: 0, netKrw: null, truncated: false };
  let oldest: string | null = null;
  for (const row of rows) {
    const date = (row.date ?? "").slice(0, 10);
    if (date && (oldest === null || date < oldest)) oldest = date;
    if (!date || date < start || date >= end) continue;
    if (REGISTRATION_SOURCES.has(row.source ?? "")) continue;
    const side = sideOf(row);
    if (side === null) continue;
    const cur = (row.currency ?? "USD").toUpperCase() === "KRW" ? "KRW" : "USD";
    flow[cur][side] += amountOf(row);
    flow.fills += 1;
  }
  for (const cur of ["KRW", "USD"] as const) {
    flow[cur].net = flow[cur].in - flow[cur].out;
  }
  const hasUsd = flow.USD.in > 0 || flow.USD.out > 0;
  flow.netKrw = hasUsd
    ? usdKrw && usdKrw > 0
      ? Math.round(flow.KRW.net + flow.USD.net * usdKrw)
      : null
    : Math.round(flow.KRW.net);
  flow.truncated = rows.length >= fetchLimit && oldest !== null && oldest >= start;
  return flow;
}

/* ── Storage: this browser only, one key per user ──────────────────────── */

export function storageKey(userId: number): string {
  return `${PAYDAY_STORAGE_PREFIX}${userId}`;
}

function isAmount(v: unknown): v is number | null {
  return v === null || (typeof v === "number" && Number.isFinite(v) && v >= 0);
}

function sanitizeCycle(raw: unknown): CyclePlan | null {
  if (!raw || typeof raw !== "object") return null;
  const c = raw as Record<string, unknown>;
  if (typeof c.start !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(c.start)) return null;
  const partsRaw = (c.parts ?? {}) as Record<string, unknown>;
  const parts = {} as Record<PartKey, number | null>;
  for (const k of PART_KEYS) parts[k] = isAmount(partsRaw[k]) ? (partsRaw[k] as number | null) : null;
  const income = isAmount(c.income) ? (c.income as number | null) : null;
  const review: CyclePlan["review"] = {};
  const actual: NonNullable<CyclePlan["actual"]> = {};
  const reviewRaw = (c.review ?? {}) as Record<string, unknown>;
  const actualRaw = (c.actual ?? {}) as Record<string, unknown>;
  for (const k of REVIEWED_PARTS) {
    const v = reviewRaw[k];
    if (v === "as_planned" || v === "less" || v === "more") review[k] = v;
    const a = actualRaw[k];
    if (typeof a === "number" && Number.isFinite(a) && a >= 0) actual[k] = a;
  }
  return {
    start: c.start,
    income,
    parts,
    review,
    ...(Object.keys(actual).length > 0 ? { actual } : {}),
    savedAt: typeof c.savedAt === "string" ? c.savedAt : "",
  };
}

/** Parse a stored blob; anything unreadable becomes the empty store. */
export function parseStore(raw: string | null): PaydayStore {
  if (!raw) return { ...EMPTY_STORE, cycles: [] };
  try {
    const data = JSON.parse(raw) as Record<string, unknown>;
    if (!data || data.v !== 1) return { ...EMPTY_STORE, cycles: [] };
    const payday =
      typeof data.payday === "number" && Number.isInteger(data.payday) && data.payday >= 1 && data.payday <= 31
        ? data.payday
        : null;
    const cycles = Array.isArray(data.cycles)
      ? (data.cycles.map(sanitizeCycle).filter(Boolean) as CyclePlan[])
      : [];
    cycles.sort((a, b) => (a.start < b.start ? -1 : a.start > b.start ? 1 : 0));
    return { v: 1, payday, cycles: cycles.slice(-MAX_CYCLES) };
  } catch {
    return { ...EMPTY_STORE, cycles: [] };
  }
}

export function loadStore(userId: number): PaydayStore {
  try {
    return parseStore(window.localStorage.getItem(storageKey(userId)));
  } catch {
    return { ...EMPTY_STORE, cycles: [] };
  }
}

/** Returns false when the browser refused the write (private mode, quota). */
export function saveStore(userId: number, store: PaydayStore): boolean {
  try {
    window.localStorage.setItem(storageKey(userId), JSON.stringify(store));
    return true;
  } catch {
    return false;
  }
}

export function clearStore(userId: number): void {
  try {
    window.localStorage.removeItem(storageKey(userId));
  } catch {
    /* nothing stored, or storage blocked — either way nothing to remove */
  }
}

/** Insert or replace the plan for `plan.start`, keeping the newest MAX_CYCLES. */
export function upsertCycle(store: PaydayStore, plan: CyclePlan): PaydayStore {
  const others = store.cycles.filter((c) => c.start !== plan.start);
  const cycles = [...others, plan].sort((a, b) => (a.start < b.start ? -1 : 1)).slice(-MAX_CYCLES);
  return { ...store, cycles };
}

export function findCycle(store: PaydayStore, start: string): CyclePlan | undefined {
  return store.cycles.find((c) => c.start === start);
}

/** Parse a typed amount ("1,000,000" / "100만" not supported — digits only). */
export function parseAmount(text: string): number | null {
  const digits = text.replace(/[^\d]/g, "");
  if (!digits) return null;
  const n = Number(digits);
  return Number.isFinite(n) ? n : null;
}

/** 1234567 → "1,234,567원". */
export function won(n: number): string {
  return `${Math.round(n).toLocaleString("ko-KR")}원`;
}
