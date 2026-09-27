/**
 * Offline accuracy eval of the holdings-screen parser (parse-holdings.ts).
 *
 * Inputs (committed): tests/fixtures/screenshot_import/holdings/
 *   *.png, ocr/*.png.json, ground_truth.json — rendered by
 *     `node scripts/holdings-fixtures-render.mjs tune <dir>` and dumped with the
 *     production OCR path (`node scripts/ocr-eval-dump.mjs <dir> <dir>/ocr`)
 *   ground_truth_shared.json — the two holdings screens PR #594 already had
 *     (synthetic/j_holdings, heldout/n1), read in place.
 * tests/fixtures/screenshot_import/holdings_heldout/ — rendered the same way
 * AFTER the rules were written and not used to change them.
 *
 * Per field: auto (filled and right), unknown (left blank for the user), wrong
 * (filled and wrong). The test fails if any field is filled wrongly, if a
 * holdings row is invented, or if ANY fill / order / other screen of the
 * fill-parser sets yields a holdings row.
 * `OCR_EVAL_PRINT=1 npx vitest run src/lib/fill-ocr/__tests__/holdings-eval.test.ts --disable-console-intercept`
 */
import fs from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";
import type { OcrWord } from "@/lib/fill-ocr/parse";
import { parseHoldingsScreen, type ParsedHolding } from "@/lib/fill-ocr/parse-holdings";

const FIXTURES = path.resolve(__dirname, "../../../../../tests/fixtures/screenshot_import");

interface GtHolding { name: string; ticker: string | null; shares: number; avg_cost: number; currency: string }
interface GtScreen { screen_type: string; holdings?: GtHolding[] }

const FIELDS = ["name", "shares", "avgCost", "currency"] as const;
type Field = (typeof FIELDS)[number];

const KR_NAMES = JSON.parse(fs.readFileSync(path.join(FIXTURES, "kr_names.json"), "utf8")) as Record<string, string>;
const KR_CODES = new Set(Object.values(KR_NAMES));

/** Same rule as the server (services/imports/ocr_rows.py resolution): a KR code
 * counts only if it is in the master, an exact name counts, a conflict → none. */
function resolvedStock(h: ParsedHolding): string | null {
  const raw = (h.code.value ?? "").toUpperCase();
  const code = /^\d{6}$/.test(raw) ? (KR_CODES.has(raw) ? raw : null) : raw || null;
  const byName = KR_NAMES[(h.name.value ?? "").replace(/\s+/g, "")] ?? null;
  if (code && byName && code !== byName) return null;
  return code ?? byName;
}

function got(h: ParsedHolding, k: Field): unknown {
  if (k === "name") return resolvedStock(h);
  if (k === "currency") return h.currency;
  return h[k].value;
}

function want(t: GtHolding, k: Field): unknown {
  if (k === "name") return (t.ticker ?? KR_NAMES[t.name.replace(/\s+/g, "")] ?? t.name).toUpperCase();
  if (k === "avgCost") return t.avg_cost;
  return t[k];
}

function score(h: ParsedHolding, t: GtHolding): number {
  let s = 0;
  for (const k of FIELDS) if (k !== "currency" && got(h, k) != null && got(h, k) === want(t, k)) s += 3;
  const hints = [h.shares.hint, h.avgCost.hint].map((x) => (x ?? "").replace(/[^\d.]/g, "")).filter(Boolean);
  for (const v of [t.shares, t.avg_cost]) if (hints.includes(String(v))) s += 1;
  const nm = (h.name.value ?? h.name.hint ?? "").replace(/\s+/g, "");
  if (nm && (t.name.includes(nm) || nm.includes(t.name))) s += 2;
  return s;
}

type Tally = Record<Field, { auto: number; unknown: number; wrong: number; total: number }>;

function evaluate(entries: [string, GtScreen][], dir: string) {
  const tally = Object.fromEntries(FIELDS.map((k) => [k, { auto: 0, unknown: 0, wrong: 0, total: 0 }])) as Tally;
  const wrongs: string[] = [];
  const screens: string[] = [];
  for (const [file, g] of entries) {
    const dumpPath = path.join(dir, path.dirname(file), "ocr", `${path.basename(file)}.json`);
    const dump = JSON.parse(fs.readFileSync(dumpPath, "utf8")) as OcrWord[] | { error: string };
    const res = Array.isArray(dump) ? parseHoldingsScreen(dump) : { screenType: "rejected", rows: [] };
    const truth = g.holdings ?? [];
    const used = new Set<number>();
    const matchOf = new Map<number, ParsedHolding>();
    let extra = 0;
    for (const h of res.rows) {
      let best = -1, bestS = 0;
      truth.forEach((t, i) => {
        if (used.has(i)) return;
        const s = score(h, t);
        if (s > bestS) { best = i; bestS = s; }
      });
      if (best >= 0) { used.add(best); matchOf.set(best, h); continue; }
      extra += 1;
      for (const k of FIELDS) if (k !== "currency" && got(h, k) != null) {
        tally[k].wrong += 1;
        wrongs.push(`${file} extra row ${k}=${String(got(h, k))}`);
      }
    }
    truth.forEach((t, i) => {
      const h = matchOf.get(i);
      for (const k of FIELDS) {
        tally[k].total += 1;
        const v = h ? got(h, k) : null;
        if (v == null) tally[k].unknown += 1;
        else if (v === want(t, k)) tally[k].auto += 1;
        else { tally[k].wrong += 1; wrongs.push(`${file} #${i} ${k}: got ${String(v)} want ${String(want(t, k))}`); }
      }
    });
    screens.push(`| ${file} | ${res.screenType} | ${res.rows.length}/${truth.length} | ${extra} |`);
  }
  return { tally, wrongs, screens };
}

function load(dir: string, file: string): [string, GtScreen][] {
  const p = path.join(dir, file);
  return fs.existsSync(p) ? Object.entries(JSON.parse(fs.readFileSync(p, "utf8")) as Record<string, GtScreen>) : [];
}

const SETS: [string, [string, GtScreen][]][] = [
  ["holdings", [
    ...load(path.join(FIXTURES, "holdings"), "ground_truth.json"),
    ...load(path.join(FIXTURES, "holdings"), "ground_truth_shared.json"),
  ]],
  ["holdings_heldout", load(path.join(FIXTURES, "holdings_heldout"), "ground_truth.json")],
];

describe.each(SETS.filter(([, e]) => e.length > 0))("holdings-screen OCR eval (%s set)", (set, entries) => {
  const { tally, wrongs, screens } = evaluate(entries, path.join(FIXTURES, set));

  if (process.env.OCR_EVAL_PRINT) {
    const pct = (n: number, d: number) => (d ? `${Math.round((n / d) * 100)}%` : "-");
    const out = [`### ${set}`, "| 칸 | 자동 인식 | 판별불가(사용자 입력) | 틀리게 확신 | n |", "|---|---|---|---|---|"];
    for (const k of FIELDS) {
      const t = tally[k];
      out.push(`| ${k} | ${pct(t.auto, t.total)} (${t.auto}) | ${pct(t.unknown, t.total)} (${t.unknown}) | ${t.wrong} | ${t.total} |`);
    }
    out.push("", "| 화면 | 판정 | 행(추출/정답) | 없는 행 |", "|---|---|---|---|", ...screens);
    console.log(out.join("\n"));
    if (wrongs.length) console.log("WRONG:\n" + wrongs.join("\n"));
  }

  it("never fills a cell wrongly (wrong-confident == 0)", () => {
    expect(wrongs).toEqual([]);
  });

  // Pinned on the set the rules were written for. On the held-out set a
  // holdings screen read as "other" only costs recall (no rows, nothing saved).
  it.runIf(set === "holdings")("classifies every holdings screen as holdings", () => {
    for (const s of screens) expect(s).toMatch(/\| holdings \|/);
  });
});

describe("holdings parser rejects every non-holdings screen", () => {
  for (const set of ["synthetic", "heldout", "regression"]) {
    const gt = JSON.parse(fs.readFileSync(path.join(FIXTURES, set, "ground_truth.json"), "utf8")) as Record<string, GtScreen>;
    for (const [file, g] of Object.entries(gt)) {
      if (g.screen_type === "holdings") continue;
      it(`${set}/${file} (${g.screen_type}) → no holdings rows`, () => {
        const dump = JSON.parse(fs.readFileSync(path.join(FIXTURES, set, "ocr", `${file}.json`), "utf8")) as OcrWord[] | { error: string };
        if (!Array.isArray(dump)) return; // rejected before reading
        const res = parseHoldingsScreen(dump);
        expect(res.screenType).not.toBe("holdings");
        expect(res.rows).toEqual([]);
      });
    }
  }
});
