/**
 * Offline accuracy eval of the Toss 내 투자 path of the holdings parser.
 *
 * Inputs (committed, OCR dumps + truth only — images are regenerable):
 *   tests/fixtures/screenshot_import/toss_tune/     seed 7, rules were tuned on it
 *   tests/fixtures/screenshot_import/toss_heldout/  seed 11, measured after tuning
 *   tests/fixtures/screenshot_import/toss_usd/      seed 31, 해외주식 with the $ toggle on
 *     (`… toss-fixtures-render.mjs <dir> 30 31 usd`) — the dollar average is expected
 *   tests/fixtures/screenshot_import/toss_detail/   seed 41, the 자세히 보기 table (`… 30 41 detail`)
 *   `node scripts/toss-fixtures-render.mjs <dir> 30 <seed>` then
 *   `node scripts/ocr-eval-dump.mjs <dir> <dir>/ocr`.
 *
 * Per row: shares / avgCost are auto (filled and right), unknown (left for
 * the user) or wrong (filled and wrong). Fails on ANY wrong cell, any screen
 * not classified as holdings, any won average filled for an overseas row, or
 * the auto rate dropping below the floor measured on 2026-09-28 (minus slack).
 * `OCR_EVAL_PRINT=1 npx vitest run src/lib/fill-ocr/__tests__/toss-eval.test.ts --disable-console-intercept`
 */
import fs from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";
import type { OcrWord } from "@/lib/fill-ocr/parse";
import { parseHoldingsScreen, type ParsedHolding } from "@/lib/fill-ocr/parse-holdings";

const FIXTURES = path.resolve(__dirname, "../../../../../tests/fixtures/screenshot_import");

interface Truth { name: string; shares: number; avg_cost: number | null; foreign: boolean }
const bare = (s: string) => s.replace(/\s+/g, "");

function score(set: string) {
  const dir = path.join(FIXTURES, set);
  const gt = JSON.parse(fs.readFileSync(path.join(dir, "ground_truth.json"), "utf8")) as Record<string, { holdings: Truth[] }>;
  const s = {
    screens: 0, inputRejected: 0, notHoldings: [] as string[], rows: 0, found: 0,
    shares: { auto: 0, unknown: 0, wrong: [] as string[] },
    avg: { n: 0, auto: 0, unknown: 0, wrong: [] as string[] },
    foreignAvgFilled: [] as string[],
  };
  for (const [file, t] of Object.entries(gt)) {
    s.screens++;
    const raw = JSON.parse(fs.readFileSync(path.join(dir, "ocr", `${file}.json`), "utf8")) as OcrWord[] | { error: string };
    s.rows += t.holdings.length;
    if (!Array.isArray(raw)) { s.inputRejected++; continue; }
    const p = parseHoldingsScreen(raw);
    if (p.screenType !== "holdings") s.notHoldings.push(file);
    const used = new Set<ParsedHolding>();
    for (const h of t.holdings) {
      // The row for this holding: same name, else the same share reading.
      const r = p.rows.find((x) => !used.has(x) && bare(x.name.value ?? "") === bare(h.name))
        ?? p.rows.find((x) => !used.has(x) && (x.shares.value === h.shares || x.shares.hint === String(h.shares)));
      if (!r) continue;
      used.add(r);
      s.found++;
      if (r.shares.value === null) s.shares.unknown++;
      else if (r.shares.value === h.shares) s.shares.auto++;
      else s.shares.wrong.push(`${file} ${h.name} ${r.shares.value}≠${h.shares}`);
      if (h.foreign && h.avg_cost === null) {
        // Shown in won: the dollar cost basis is not on screen.
        if (r.avgCost.value !== null) s.foreignAvgFilled.push(`${file} ${h.name}`);
        continue;
      }
      s.avg.n++;
      if (r.avgCost.value === null) s.avg.unknown++;
      else if (r.avgCost.value === h.avg_cost) s.avg.auto++;
      else s.avg.wrong.push(`${file} ${h.name} ${r.avgCost.value}≠${h.avg_cost}`);
    }
  }
  if (process.env.OCR_EVAL_PRINT) {
    const pc = (a: number, b: number) => `${Math.round((a / b) * 100)}% (${a}/${b})`;
    console.log(`### ${set}: ${s.screens} screens, ${s.rows} rows, input rejected ${s.inputRejected}`);
    console.log(`rows found ${pc(s.found, s.rows)} · shares auto ${pc(s.shares.auto, s.rows)} · ` +
      `avg auto ${pc(s.avg.auto, s.avg.n)} · wrong ${s.shares.wrong.length + s.avg.wrong.length}`);
  }
  return s;
}

// Measured 2026-09-28 (tune / heldout): shares auto 122/142 · 126/145,
// avg auto 95/115 · 91/107. Floors leave a few rows of slack for OCR drift.
const FLOORS: Record<string, { shares: number; avg: number }> = {
  toss_tune: { shares: 0.8, avg: 0.75 },
  toss_heldout: { shares: 0.8, avg: 0.75 },
  // 2026-09-28: shares 153/187, avg 144/171 (overseas rows 38/58).
  toss_usd: { shares: 0.78, avg: 0.78 },
  // Synthetic 자세히 보기 is harsher than the real captures (dark, small type,
  // wrapped cells: OCR often garbles the header line, so the table path cannot
  // start). Measured 2026-09-28: rows 62/174, shares 45/174. It gates wrong = 0;
  // the two real captures of this screen read 11 of 15 stocks fully.
  toss_detail: { shares: 0.2, avg: 0.5 },
};

describe.each(Object.keys(FLOORS))("Toss 내 투자 eval (%s)", (set) => {
  const s = score(set);
  it("never fills a cell wrongly", () => {
    expect(s.shares.wrong).toEqual([]);
    expect(s.avg.wrong).toEqual([]);
  });
  it("never fills a won average for an overseas stock", () => {
    expect(s.foreignAvgFilled).toEqual([]);
  });
  it("classifies every readable screen as holdings", () => {
    if (set === "toss_detail") return; // header line garbled on some — see FLOORS
    expect(s.notHoldings).toEqual([]);
  });
  it("keeps the auto-fill rate", () => {
    expect(s.shares.auto / s.rows).toBeGreaterThanOrEqual(FLOORS[set].shares);
    expect(s.avg.auto / s.avg.n).toBeGreaterThanOrEqual(FLOORS[set].avg);
  });
});
