/**
 * 리서치 양식 — labels and caps shared by /journal/research and /pre-trade.
 *
 * Caps mirror models/research_note.py one-for-one (the server re-checks every
 * one; these only keep the form from offering what it would refuse).
 * docs/design/research-notes_2026-10-15.md.
 */
import type {
  ResearchInfoSource,
  ResearchNote,
  ResearchOutcome,
  ResearchVerdict,
  StockRecordEvent,
} from "@/lib/types";

export const RESEARCH_MAX_THESES = 3;
export const RESEARCH_MAX_BUSINESS = 300;
export const RESEARCH_MAX_THESIS = 300;
export const RESEARCH_MAX_INVALIDATION = 500;
export const RESEARCH_MAX_RISK = 500;
export const RESEARCH_MAX_NUMBERS = 1000;
export const RESEARCH_MAX_REVIEW_NOTE = 500;

export const REVIEW_MONTH_OPTIONS = [1, 3, 6] as const;
export type ReviewMonths = (typeof REVIEW_MONTH_OPTIONS)[number];

export const INFO_SOURCE_ORDER: ResearchInfoSource[] = ["report", "youtube", "social", "ai", "self"];

export const INFO_SOURCE_LABEL: Record<ResearchInfoSource | "none", string> = {
  report: "리포트",
  youtube: "유튜브",
  social: "지인·SNS",
  ai: "AI",
  self: "직접 분석",
  none: "적지 않음",
};

export const VERDICT_ORDER: ResearchVerdict[] = ["right", "wrong", "unknown"];
export const VERDICT_LABEL: Record<ResearchVerdict, string> = {
  right: "맞음",
  wrong: "틀림",
  unknown: "모름",
};

/** The user's own fills on that stock since the note — a fact, not a grade. */
export const OUTCOME_LABEL: Record<ResearchOutcome, string> = {
  gain: "판 뒤 이익",
  loss: "판 뒤 손실",
  flat: "판 뒤 본전",
  open: "아직 안 팖",
};

/** "2026-01-15" → "1월 15일" (KST calendar date as written by the server). */
export function researchDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return "";
  return `${Number(m[2])}월 ${Number(m[3])}일`;
}

/** A UTC timestamp's KST calendar date, "YYYY-MM-DD". */
export function kstDateOf(isoUtc: string | null | undefined): string {
  if (!isoUtc) return "";
  const t = Date.parse(/Z|[+-]\d\d:?\d\d$/.test(isoUtc) ? isoUtc : `${isoUtc}Z`);
  if (Number.isNaN(t)) return "";
  return new Date(t + 9 * 3600_000).toISOString().slice(0, 10);
}

/** A ticker symbol, not a typed name — the server's ``services.imports.TICKER_RE``
 *  (``^[A-Z0-9][A-Z0-9.-]{0,19}$``) on the upper-cased value. */
export function looksLikeTicker(value: string | null | undefined): boolean {
  return /^[A-Z0-9][A-Z0-9.-]{0,19}$/.test((value ?? "").trim().toUpperCase());
}

/* ── 다시 찾기 (2026-10-27) ──────────────────────────────────────────────
 * The filters `GET /api/research-notes/list` takes on top of the cursor
 * (services/research_notes/service.py::list_research). Narrative fields are
 * encrypted at rest, so the server matches `q` after decrypting the user's
 * own rows; the rest are plain SQL filters. */

export type ResearchStatusFilter = "due" | "waiting" | "scored";
export const RESEARCH_STATUS_ORDER: ResearchStatusFilter[] = ["due", "waiting", "scored"];
export const RESEARCH_STATUS_LABEL: Record<ResearchStatusFilter, string> = {
  due: "다시 볼 날 됨",
  waiting: "기다리는 중",
  scored: "채점함",
};

export type ResearchPeriod = "all" | "1m" | "3m" | "1y";
export const RESEARCH_PERIOD_ORDER: ResearchPeriod[] = ["all", "1m", "3m", "1y"];
export const RESEARCH_PERIOD_LABEL: Record<ResearchPeriod, string> = {
  all: "전체 기간",
  "1m": "최근 1개월",
  "3m": "최근 3개월",
  "1y": "최근 1년",
};
const PERIOD_MONTHS: Record<Exclude<ResearchPeriod, "all">, number> = { "1m": 1, "3m": 3, "1y": 12 };

export interface ResearchFilters {
  q: string;
  source: ResearchInfoSource | "none" | null;
  status: ResearchStatusFilter | null;
  period: ResearchPeriod;
}

export const EMPTY_RESEARCH_FILTERS: ResearchFilters = { q: "", source: null, status: null, period: "all" };

/** The server caps `q` at 100 characters; the input does the same. */
export const RESEARCH_MAX_QUERY = 100;

export function researchFiltersActive(f: ResearchFilters): boolean {
  return f.q.trim() !== "" || f.source !== null || f.status !== null || f.period !== "all";
}

/** Today's KST calendar date `months` back, "YYYY-MM-DD" (clamped to the month's end). */
export function kstMonthsAgo(months: number, now: number = Date.now()): string {
  const kst = new Date(now + 9 * 3600_000);
  const y = kst.getUTCFullYear();
  const m = kst.getUTCMonth() - months;
  const last = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
  return new Date(Date.UTC(y, m, Math.min(kst.getUTCDate(), last))).toISOString().slice(0, 10);
}

/** `&q=…&source=…` for the list URL — "" when no filter is on. */
export function researchFilterQuery(f: ResearchFilters, now: number = Date.now()): string {
  const p = new URLSearchParams();
  const q = f.q.trim().slice(0, RESEARCH_MAX_QUERY);
  if (q) p.set("q", q);
  if (f.source) p.set("source", f.source);
  if (f.status) p.set("status", f.status);
  if (f.period !== "all") p.set("since", kstMonthsAgo(PERIOD_MONTHS[f.period], now));
  const s = p.toString();
  return s ? `&${s}` : "";
}

/* ── 적은 뒤 (2026-10-27) ────────────────────────────────────────────────
 * The research detail screen (/journal/research/[id]) lays one note next to
 * what the user did on the same stock after writing it — read from the
 * stock record (GET /api/stock-record/<ticker>), no new endpoint. Facts and
 * counts only: nothing here says the reason caused the trade. */

/** A stored value with no time of day — `services.imports.is_date_only`:
 *  the date itself (a KST date for fills, the official date for filings). */
function isDateOnly(at: string): boolean {
  return /T00:00:00(\.0+)?$/.test(at);
}

/** Did `at` happen at or after the note was written? A date-only value
 *  counts from the note's KST day on — the server's `_sold_after` rule. */
export function atOrAfterNote(at: string | null, noteCreatedAt: string | null): boolean {
  if (!at || !noteCreatedAt) return false;
  if (isDateOnly(at)) return at.slice(0, 10) >= kstDateOf(noteCreatedAt);
  const t = Date.parse(/Z|[+-]\d\d:?\d\d$/.test(at) ? at : `${at}Z`);
  const n = Date.parse(/Z|[+-]\d\d:?\d\d$/.test(noteCreatedAt) ? noteCreatedAt : `${noteCreatedAt}Z`);
  return !Number.isNaN(t) && !Number.isNaN(n) && t >= n;
}

/** One line on the 적은 뒤 timeline: a stock-record event, or one of the
 *  note's own days (다시 볼 날 · 채점). */
export type AfterItem =
  | { kind: "event"; at: string; event: StockRecordEvent }
  | { kind: "review_day"; at: string; upcoming: boolean }
  | { kind: "scored"; at: string };

export interface AfterNote {
  /** Oldest first — the story from the day it was written. */
  items: AfterItem[];
  counts: { buys: number; sells: number; pauses: number; notTaken: number; notes: number; research: number; filings: number };
}

function sortKey(at: string): string {
  // Date-only values sort as the start of their day; timed ones by instant.
  return isDateOnly(at) ? `${at.slice(0, 10)}T00:00:00` : at;
}

/**
 * What happened on the note's stock after it was written. `events` is the
 * stock record's list (any order); the note itself is left out. `today` is
 * the KST date, "YYYY-MM-DD" — a review day still ahead is marked upcoming.
 */
export function afterNote(note: ResearchNote, events: StockRecordEvent[], today: string): AfterNote {
  const counts = { buys: 0, sells: 0, pauses: 0, notTaken: 0, notes: 0, research: 0, filings: 0 };
  const items: AfterItem[] = [];
  for (const e of events) {
    if (!e.at) continue;
    if (e.kind === "research" && e.id === note.id) continue;
    if (e.kind === "registered") continue; // an import of what was held, not an act
    if (!atOrAfterNote(e.at, note.created_at)) continue;
    items.push({ kind: "event", at: e.at, event: e });
    if (e.kind === "fill") {
      if (e.side === "buy") counts.buys++;
      else counts.sells++;
    } else if (e.kind === "pause") {
      counts.pauses++;
      if (e.bought_after === false) counts.notTaken++;
    } else if (e.kind === "note") counts.notes++;
    else if (e.kind === "research") counts.research++;
    else if (e.kind === "filing") counts.filings++;
  }
  if (note.review_on) {
    items.push({ kind: "review_day", at: `${note.review_on}T00:00:00`, upcoming: note.review_on > today });
  }
  if (note.reviewed_at) items.push({ kind: "scored", at: note.reviewed_at });
  items.sort((a, b) => (sortKey(a.at) < sortKey(b.at) ? -1 : sortKey(a.at) > sortKey(b.at) ? 1 : 0));
  return { items, counts };
}

/** Today's KST calendar date, "YYYY-MM-DD". */
export function kstToday(now: number = Date.now()): string {
  return new Date(now + 9 * 3600_000).toISOString().slice(0, 10);
}
