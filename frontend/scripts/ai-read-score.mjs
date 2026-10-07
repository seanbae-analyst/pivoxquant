/**
 * AI-read experiment, step 3: score a reader's JSON against ground_truth.json
 * (docs/product/AI_READ_EXPERIMENT_2026-10-07.md §results).
 *
 * Per holding field (stock / shares / avg_cost / currency):
 *   auto      filled as read|derived and right
 *   confirm   filled as guessed and right   (user taps "맞아요")
 *   unknown   left blank                    (user types it)
 *   wrong_g   filled as guessed and wrong   (shown as a question — user fixes)
 *   WRONG     filled as read|derived and wrong — the number that must stay 0
 * Plus: screen classification (has-position vs not), invented rows
 * (rows the screen does not hold, incl. any row on fills/order/watchlist/…),
 * and truncated stocks that got numbers.
 *
 *   node scripts/ai-read-score.mjs <fixture dir> <reader.json>
 */
import fs from "node:fs";
import path from "node:path";

const [dir, readerPath] = process.argv.slice(2);
const truth = JSON.parse(fs.readFileSync(path.join(dir, "ground_truth.json"), "utf8"));
const names = Object.fromEntries(
  Object.entries(JSON.parse(fs.readFileSync(path.join(dir, "..", "kr_names.json"), "utf8"))).map(([n, c]) => [n.replace(/\s+/g, ""), c]),
);
const reader = JSON.parse(fs.readFileSync(readerPath, "utf8")).screens;

const norm = (s) => String(s ?? "").replace(/\s+/g, "").toUpperCase();
const stockKey = (v) => { const n = norm(v); return names[String(v ?? "").replace(/\s+/g, "")] ?? n; };
const POSITIVE = new Set(["holdings", "position_detail"]);
const FIELDS = ["stock", "shares", "avg_cost", "currency"];
const tally = Object.fromEntries(FIELDS.map((f) => [f, { auto: 0, confirm: 0, unknown: 0, wrong_g: 0, WRONG: 0 }]));
const out = { screens_right: 0, screens: 0, invented_rows: [], truncated_with_numbers: [], wrong: [], rows_complete_auto: 0, rows_all_right: 0, rows: 0 };

for (const [file, g] of Object.entries(truth)) {
  const r = reader[file] ?? { screen_type: "missing", rows: [] };
  out.screens++;
  if (POSITIVE.has(r.screen_type) === POSITIVE.has(g.screen_type)) out.screens_right++;
  else out.wrong.push(`${file}: screen ${r.screen_type} (truth ${g.screen_type})`);
  const rows = (r.rows ?? []).filter((x) => !x.truncated);
  for (const t of (r.rows ?? []).filter((x) => x.truncated)) {
    if (t.shares?.v || t.avg_cost?.v) out.truncated_with_numbers.push(`${file}: ${t.stock?.v}`);
  }
  const used = new Set();
  const want = (t, f) => (f === "stock" ? norm(t.ticker) : f === "currency" ? t.currency : t[f]);
  const got = (x, f) => (f === "stock" ? norm(stockKey(x.stock?.v)) : x[f]?.v);
  const same = (a, b) => (typeof b === "number" ? Math.abs(Number(a) - b) < 1e-6 : a === b);
  for (const t of g.holdings) {
    out.rows++;
    // match by stock, else by numbers (a misread stock still lands on its row)
    let i = rows.findIndex((x, k) => !used.has(k) && got(x, "stock") === norm(t.ticker));
    if (i < 0) i = rows.findIndex((x, k) => !used.has(k) && (same(got(x, "shares"), t.shares) || same(got(x, "avg_cost"), t.avg_cost)));
    const x = i >= 0 ? rows[i] : null;
    if (i >= 0) used.add(i);
    let allAuto = true, allRight = true;
    for (const f of FIELDS) {
      const st = x?.[f]?.s ?? "blank", v = x ? got(x, f) : null;
      const empty = !x || st === "blank" || v === null || v === undefined || v === "";
      let k;
      if (empty) k = "unknown";
      else if (same(v, want(t, f))) k = st === "guessed" ? "confirm" : "auto";
      else { k = st === "guessed" ? "wrong_g" : "WRONG"; out.wrong.push(`${file}: ${t.name} ${f} got ${x[f]?.v} (${st}) want ${want(t, f)}`); }
      tally[f][k]++;
      if (k !== "auto") allAuto = false;
      if (k !== "auto" && k !== "confirm") allRight = false;
    }
    if (allAuto) out.rows_complete_auto++;
    if (allRight) out.rows_all_right++;
  }
  rows.forEach((x, k) => { if (!used.has(k)) out.invented_rows.push(`${file}: ${x.stock?.v}`); });
}
console.log(JSON.stringify({ fields: tally, ...out }, null, 2));
