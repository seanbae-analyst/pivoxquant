/**
 * Offline accuracy eval of the holdings parser on synthetic screens in the
 * styles of several broker apps (키움 · 한국투자 · 미래에셋 · 삼성 · NH, KRW and USD).
 *
 * Inputs (committed, OCR dumps + truth only — images are regenerable):
 *   tests/fixtures/screenshot_import/broker_tune/     seed 3, rules were tuned on it
 *   tests/fixtures/screenshot_import/broker_heldout/  seed 23, measured once after tuning
 *   `node scripts/broker-fixtures-render.mjs <dir> 36 <seed>` then
 *   `node scripts/ocr-eval-dump.mjs <dir> <dir>/ocr`.
 * The styles are approximations drawn from memory, not the apps themselves.
 *
 * Fails on ANY wrongly filled shares / average cost, or the auto rate
 * dropping below the floor measured on 2026-09-28 (minus slack).
 * `OCR_EVAL_PRINT=1 npx vitest run src/lib/fill-ocr/__tests__/broker-eval.test.ts --disable-console-intercept`
 */
import fs from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";
import type { OcrWord } from "@/lib/fill-ocr/parse";
import { parseHoldingsScreen, type ParsedHolding } from "@/lib/fill-ocr/parse-holdings";

const FIXTURES = path.resolve(__dirname, "../../../../../tests/fixtures/screenshot_import");

interface Truth { name: string; shares: number; avg_cost: number; currency: string }
interface Screen { variant: { style: string; us: boolean }; holdings: Truth[] }
const bare = (s: string) => s.replace(/\s+/g, "").toUpperCase();

function score(set: string) {
  const dir = path.join(FIXTURES, set);
  const gt = JSON.parse(fs.readFileSync(path.join(dir, "ground_truth.json"), "utf8")) as Record<string, Screen>;
  const s = { rows: 0, shares: 0, avg: 0, wrong: [] as string[], byStyle: {} as Record<string, [number, number, number]> };
  for (const [file, t] of Object.entries(gt)) {
    const style = t.variant.style + (t.variant.us ? "-us" : "");
    const st = (s.byStyle[style] ??= [0, 0, 0]);
    s.rows += t.holdings.length;
    st[0] += t.holdings.length;
    const raw = JSON.parse(fs.readFileSync(path.join(dir, "ocr", `${file}.json`), "utf8")) as OcrWord[] | { error: string };
    if (!Array.isArray(raw)) continue;
    const rows = parseHoldingsScreen(raw).rows;
    // Pair rows with holdings: exact names first, then — among rows whose
    // name is no holding's — the same share reading.
    const used = new Set<ParsedHolding>();
    const match = new Map<Truth, ParsedHolding>();
    for (const h of t.holdings) {
      const r = rows.find((x) => !used.has(x) && bare(x.name.value ?? x.code.value ?? "") === bare(h.name));
      if (r) { used.add(r); match.set(h, r); }
    }
    for (const h of t.holdings) {
      if (match.has(h)) continue;
      const r = rows.find((x) => !used.has(x) && x.shares.value === h.shares &&
        !t.holdings.some((o) => bare(o.name) === bare(x.name.value ?? "")));
      if (r) { used.add(r); match.set(h, r); }
    }
    for (const h of t.holdings) {
      const r = match.get(h);
      if (!r) continue;
      if (r.shares.value === h.shares) { s.shares++; st[1]++; }
      else if (r.shares.value !== null) s.wrong.push(`${file} ${h.name} shares ${r.shares.value}≠${h.shares}`);
      if (r.avgCost.value === h.avg_cost) { s.avg++; st[2]++; }
      else if (r.avgCost.value !== null) s.wrong.push(`${file} ${h.name} avg ${r.avgCost.value}≠${h.avg_cost}`);
    }
  }
  if (process.env.OCR_EVAL_PRINT) {
    const pc = (a: number, b: number) => `${Math.round((a / b) * 100)}%`;
    console.log(`### ${set}: ${s.rows} rows · shares auto ${pc(s.shares, s.rows)} · avg auto ${pc(s.avg, s.rows)} · wrong ${s.wrong.length}`);
    console.log("| style | rows | shares auto | avg auto |\n|---|---|---|---|");
    for (const [k, [n, a, b]] of Object.entries(s.byStyle).sort()) console.log(`| ${k} | ${n} | ${pc(a, n)} | ${pc(b, n)} |`);
  }
  return s;
}

// Measured 2026-09-28 (tune / heldout): shares auto 81% · 79%, avg auto
// 79% · 81% of 173 · 179 rows. Floors leave slack for OCR drift.
const FLOORS: Record<string, { shares: number; avg: number }> = {
  broker_tune: { shares: 0.75, avg: 0.72 },
  broker_heldout: { shares: 0.75, avg: 0.72 },
};

describe.each(Object.keys(FLOORS))("broker-style holdings eval (%s)", (set) => {
  const s = score(set);
  it("never fills a cell wrongly", () => {
    expect(s.wrong).toEqual([]);
  });
  it("keeps the auto-fill rate", () => {
    expect(s.shares / s.rows).toBeGreaterThanOrEqual(FLOORS[set].shares);
    expect(s.avg / s.rows).toBeGreaterThanOrEqual(FLOORS[set].avg);
  });
});
