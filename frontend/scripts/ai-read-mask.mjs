/**
 * AI-read experiment, step 2: OCR word dump → the masked text an AI reader
 * would receive (docs/product/AI_READ_EXPERIMENT_2026-10-07.md §masking),
 * using the app's own rules (src/lib/fill-ocr/mask.ts — one copy), then
 * measures leaks against ground_truth.json `pii`.
 *
 *   node scripts/ai-read-mask.mjs <fixture dir> <out dir>
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createJiti } from "jiti";

const [dir, outDir] = process.argv.slice(2);
if (!dir || !outDir) {
  console.error("usage: node scripts/ai-read-mask.mjs <fixture dir> <out dir>");
  process.exit(2);
}

// The rules live in src/lib/fill-ocr/mask.ts (the app's copy); load it as-is.
const jiti = createJiti(import.meta.url, { alias: { "@": path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src") } });
const { maskScreen } = await jiti.import("../src/lib/fill-ocr/mask.ts");

const truth = JSON.parse(fs.readFileSync(path.join(dir, "ground_truth.json"), "utf8"));
fs.mkdirSync(outDir, { recursive: true });
const report = { dropped_identity: 0, dropped_unneeded: 0, dropped_account: 0, leaks: [] };
for (const file of Object.keys(truth).sort()) {
  const dump = JSON.parse(fs.readFileSync(path.join(dir, "ocr", `${file}.json`), "utf8"));
  if (!Array.isArray(dump)) { fs.writeFileSync(path.join(outDir, `${file}.txt`), `[OCR 거절: ${dump.error}]\n`); continue; }
  const { text, dropped } = maskScreen(dump);
  report.dropped_identity += dropped.identity;
  report.dropped_unneeded += dropped.unneeded;
  report.dropped_account += dropped.account;
  fs.writeFileSync(path.join(outDir, `${file}.txt`), text + "\n");
  // leak = a PII string, or any 4+ digit run of an account number, still in the text
  const flat = text.replace(/\s+/g, "");
  for (const p of truth[file].pii ?? []) {
    const parts = /\d/.test(p) ? p.split(/\D+/).filter((x) => x.length >= 4) : [p];
    for (const part of parts) if (flat.includes(part)) report.leaks.push({ file, pii_part: part.replace(/\d/g, "#") });
  }
}
console.log(JSON.stringify(report, null, 2));
