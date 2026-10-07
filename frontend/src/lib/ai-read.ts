/**
 * AI read of a capture's / a pasted message's masked text — the client half.
 *
 * docs/product/AI_READ_EXPERIMENT_2026-10-07.md · services/ai_read.py.
 * Only text that passed lib/fill-ocr/mask.ts leaves the device; the server
 * masks again, reads, and checks every number against the printed text before
 * it fills a cell. Rows come back in the rule parser's own shape (Cell values
 * and hints), so the existing review tables, preview and commit validation
 * apply unchanged — an AI-read row is saved exactly like a rule-read one.
 *
 * Off unless `NEXT_PUBLIC_AI_READ=1`. The backend has its own
 * `AI_READ_ENABLED` and answers 503 when off; either alone keeps it off.
 */
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import type { Cell, ParsedFill } from "@/lib/fill-ocr/parse";
import type { ParsedHolding } from "@/lib/fill-ocr/parse-holdings";

export function aiReadEnabled(): boolean {
  return process.env.NEXT_PUBLIC_AI_READ === "1";
}

export type AiReadKind = "holdings" | "fills";

/** Stamped on the source_text of every AI-read row, so the stored snippet
 * says how the row was read. */
export const AI_SOURCE_TAG = "[AI 판독]";

type Money = "KRW" | "USD" | null;

export interface AiHoldingRow {
  name: Cell<string>;
  code: Cell<string>;
  shares: Cell<number>;
  avg_cost: Cell<number>;
  currency: Money;
  truncated: boolean;
  flags: string[];
}

export interface AiFillRow {
  name: Cell<string>;
  code: Cell<string>;
  action: Cell<"buy" | "sell">;
  shares: Cell<number>;
  price: Cell<number>;
  amount: Cell<number>;
  date: Cell<string>;
  time: Cell<string>;
  currency: Money;
  flags: string[];
}

export interface AiReadScreen<R> {
  screen_type: string;
  reason: string;
  rows: R[];
}

export async function requestAiRead<R>(kind: AiReadKind, screens: string[]): Promise<AiReadScreen<R>[]> {
  const res = await apiFetch<{ screens: AiReadScreen<R>[] }>(API.imports.aiRead, {
    method: "POST",
    body: JSON.stringify({ kind, screens, consent: true }),
    timeoutMs: 120_000,
  });
  return Array.isArray(res?.screens) ? res.screens : [];
}

const cell = <T,>(c: Cell<T> | undefined): Cell<T> => (c ? { value: c.value ?? null, ...(c.hint ? { hint: c.hint } : {}) } : { value: null });

export function holdingFromAi(r: AiHoldingRow): ParsedHolding {
  return {
    name: cell(r.name),
    code: cell(r.code),
    shares: cell(r.shares),
    avgCost: cell(r.avg_cost),
    currency: r.currency ?? null,
    flags: r.flags ?? ["ai_read"],
    sourceText: AI_SOURCE_TAG,
  };
}

export function fillFromAi(r: AiFillRow): ParsedFill {
  const a = r.action?.value;
  return {
    date: cell(r.date),
    time: cell(r.time),
    tz: r.currency === "USD" ? null : "KST",
    name: cell(r.name),
    code: cell(r.code),
    side: { value: a === "buy" ? "BUY" : a === "sell" ? "SELL" : null },
    shares: cell(r.shares),
    price: cell(r.price),
    amount: cell(r.amount),
    currency: r.currency ?? null,
    flags: r.flags ?? ["ai_read"],
    sourceText: AI_SOURCE_TAG,
  };
}
