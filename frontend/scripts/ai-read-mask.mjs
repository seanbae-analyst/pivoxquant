/**
 * AI-read experiment, step 2: OCR word dump → the masked text an AI reader
 * would receive (docs/product/AI_READ_EXPERIMENT_2026-10-07.md §masking).
 *
 * Runs on the dumps ocr-eval-dump.mjs writes. Prototype of what the browser
 * would do before anything leaves the device:
 *   1. words → lines (by vertical centre, left to right)
 *   2. DROP identity lines: 계좌·위탁·고객·…님 (account / customer headers)
 *   3. DROP lines nobody needs for holdings: 예수금·주문가능·출금가능
 *   4. DROP any line holding something shaped like an account number
 *      (≥8 digits joined by hyphens, or 8+ digits in a row — OCR look-alikes
 *      O/o/l/I/| count as digits) or an account-type tag like [종합_주식] —
 *      the holder's name sits on that line in real apps, so masking only the
 *      digits leaked it (2026-10-07, App Store screenshots of 3 brokers)
 * Then measures leaks against ground_truth.json `pii`.
 *
 *   node scripts/ai-read-mask.mjs <fixture dir> <out dir>
 */
import fs from "node:fs";
import path from "node:path";

const [dir, outDir] = process.argv.slice(2);
if (!dir || !outDir) {
  console.error("usage: node scripts/ai-read-mask.mjs <fixture dir> <out dir>");
  process.exit(2);
}

const DROP_IDENTITY = /계좌|위탁|고객|님/;
const DROP_UNNEEDED = /예수금|주문\s*가능|출금\s*가능/;
const ACCOUNT_TAG = /\[[^\]]*(종합|위탁|주식|CMA|ISA|연금|비대면|저축)[^\]]*\]/;
const D = "[0-9OolI|]";
const ACCOUNT = new RegExp(`${D}{2,}(?:\\s?[-–]\\s?${D}{2,}){1,3}|${D}{8,}`, "g");
const digitsOf = (s) => s.replace(/[Oo]/g, "0").replace(/[lI|]/g, "1").replace(/\D/g, "");
const looksLikeAccount = (m) => {
  const d = digitsOf(m);
  // 8+ digits overall, but not a money amount ("1,234,567" uses commas, never hyphens)
  return d.length >= 8 && !/,/.test(m);
};

function toLines(words) {
  const ws = [...words].sort((a, b) => (a.y0 + a.y1) / 2 - (b.y0 + b.y1) / 2 || a.x0 - b.x0);
  const lines = [];
  let cur = [], cy = null;
  for (const w of ws) {
    const y = (w.y0 + w.y1) / 2;
    if (cy !== null && Math.abs(y - cy) > 14) { lines.push(cur); cur = []; cy = null; }
    if (cy === null) cy = y;
    cur.push(w);
  }
  if (cur.length) lines.push(cur);
  return lines.map((l) => l.sort((a, b) => a.x0 - b.x0).map((w) => w.t).join(" "));
}

const truth = JSON.parse(fs.readFileSync(path.join(dir, "ground_truth.json"), "utf8"));
fs.mkdirSync(outDir, { recursive: true });
const report = { dropped_identity: 0, dropped_unneeded: 0, dropped_account: 0, leaks: [] };
for (const file of Object.keys(truth).sort()) {
  const dump = JSON.parse(fs.readFileSync(path.join(dir, "ocr", `${file}.json`), "utf8"));
  if (!Array.isArray(dump)) { fs.writeFileSync(path.join(outDir, `${file}.txt`), `[OCR 거절: ${dump.error}]\n`); continue; }
  const kept = [];
  for (const line of toLines(dump)) {
    // OCR splits Hangul into spaced syllables ("주 문 가 능") — match keywords without spaces
    const squashed = line.replace(/\s+/g, "");
    if (DROP_IDENTITY.test(squashed)) { report.dropped_identity++; continue; }
    if (DROP_UNNEEDED.test(squashed)) { report.dropped_unneeded++; continue; }
    if (ACCOUNT_TAG.test(squashed) || (line.match(ACCOUNT) ?? []).some(looksLikeAccount)) { report.dropped_account++; continue; }
    kept.push(line);
  }
  const text = kept.join("\n");
  fs.writeFileSync(path.join(outDir, `${file}.txt`), text + "\n");
  // leak = a PII string, or any 4+ digit run of an account number, still in the text
  const flat = text.replace(/\s+/g, "");
  for (const p of truth[file].pii ?? []) {
    const parts = /\d/.test(p) ? p.split(/\D+/).filter((x) => x.length >= 4) : [p];
    for (const part of parts) if (flat.includes(part)) report.leaks.push({ file, pii_part: part.replace(/\d/g, "#") });
  }
}
console.log(JSON.stringify(report, null, 2));
