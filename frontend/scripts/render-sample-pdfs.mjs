#!/usr/bin/env node
// Sample PDF renderer using Playwright headless.
// Usage:
//   node scripts/render-sample-pdfs.mjs --slug=morning-brief-plus
//   node scripts/render-sample-pdfs.mjs --all
//   node scripts/render-sample-pdfs.mjs --slug=morning-brief-plus --baseUrl=http://localhost:3000

import { chromium } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const SLUGS = [
  "weekly-memo", "brag-card", "morning-brief-plus",
  "earnings-prebrief", "dd-checklist", "risk-board",
  "sp500-backtest", "portfolio-segment", "dividend-income",
  "insider-mirror", "quarterly-self-report", "self-audit",
  "monthly-finance", "kpi-dashboard", "capital-allocation",
  "credit-rating", "year-end-letter", "burn-rate",
];

// React slug -> public/samples/<filename>.pdf mapping
const SLUG_TO_FILENAME = {
  "weekly-memo":           "weekly_memo.pdf",
  "brag-card":             "brag_card.pdf",
  "morning-brief-plus":    "morning_brief_plus.pdf",
  "earnings-prebrief":     "earnings_prebrief.pdf",
  "dd-checklist":          "dd_checklist.pdf",
  "risk-board":            "risk_board.pdf",
  "sp500-backtest":        "sp500_backtest.pdf",
  "portfolio-segment":     "portfolio_segment.pdf",
  "dividend-income":       "dividend_income.pdf",
  "insider-mirror":        "insider_mirror.pdf",
  "quarterly-self-report": "quarterly_self_report.pdf",
  "self-audit":            "self_audit.pdf",
  "monthly-finance":       "monthly_finance.pdf",
  "kpi-dashboard":         "kpi_dashboard.pdf",
  "capital-allocation":    "capital_allocation.pdf",
  "credit-rating":         "credit_rating.pdf",
  "year-end-letter":       "year_end_letter.pdf",
  "burn-rate":             "burn_rate.pdf",
};

/* Reference-folder mapping. The repo-internal `frontend/public/samples/`
   serves the marketing pages; the sibling `../../pivoxquant_pdfs/` is the
   numbered reference set the lint tool (`pivoxquant_pdfs/lint_pdfs.py`)
   reads. They MUST stay in sync — without this, source fixes never reach
   the lint scope and CI/manual scans show stale 41-finding state.
   2026-05-06 audit-driven addition. */
const SLUG_TO_REFERENCE = {
  "weekly-memo":           "01_weekly_memo.pdf",
  "morning-brief-plus":    "02_morning_brief_plus.pdf",
  "brag-card":             "03_brag_card.pdf",
  "earnings-prebrief":     "04_earnings_prebrief.pdf",
  "risk-board":            "05_risk_board.pdf",
  "quarterly-self-report": "06_quarterly_self_report.pdf",
  "self-audit":            "07_self_audit.pdf",
  "dd-checklist":          "08_dd_checklist.pdf",
  "dividend-income":       "09_dividend_income.pdf",
  "insider-mirror":        "10_insider_mirror.pdf",
  "sp500-backtest":        "11_sp500_backtest.pdf",
  "portfolio-segment":     "12_portfolio_segment.pdf",
  "capital-allocation":    "13_capital_allocation.pdf",
  "credit-rating":         "14_credit_rating.pdf",
  "burn-rate":             "15_burn_rate.pdf",
  "monthly-finance":       "16_monthly_finance.pdf",
  "kpi-dashboard":         "17_kpi_dashboard.pdf",
  "year-end-letter":       "18_year_end_letter.pdf",
};

function parseArgs(argv) {
  const args = { slug: null, all: false, baseUrl: "http://localhost:3000", sync: true };
  for (const a of argv) {
    if (a === "--all") args.all = true;
    else if (a === "--no-sync") args.sync = false;
    else if (a.startsWith("--slug=")) args.slug = a.split("=")[1];
    else if (a.startsWith("--baseUrl=")) args.baseUrl = a.split("=")[1];
  }
  return args;
}

/* Mirror rendered PDFs to the sibling reference folder used by lint_pdfs.py.
   Path: <repo>/frontend/scripts -> ../.. = <repo-parent> = /Users/seanbae/Desktop/취준
   Sibling: <repo-parent>/pivoxquant_pdfs/<NN>_<slug>.pdf
   Returns { synced, failed } counts. */
function syncToReference(renderedSlugs, outDir) {
  const refDir = path.resolve(__dirname, "..", "..", "..", "pivoxquant_pdfs");
  if (!fs.existsSync(refDir)) {
    console.error(`[sync] reference dir missing: ${refDir}`);
    return { synced: 0, failed: renderedSlugs.length };
  }
  let synced = 0, failed = 0;
  for (const slug of renderedSlugs) {
    const srcName = SLUG_TO_FILENAME[slug] ?? `${slug.replace(/-/g, "_")}.pdf`;
    const refName = SLUG_TO_REFERENCE[slug];
    if (!refName) {
      console.error(`[sync] no reference mapping for ${slug}`);
      failed++;
      continue;
    }
    const srcPath = path.join(outDir, srcName);
    const dstPath = path.join(refDir, refName);
    try {
      if (!fs.existsSync(srcPath)) {
        throw new Error(`source missing: ${srcPath}`);
      }
      fs.copyFileSync(srcPath, dstPath);
      const now = new Date();
      fs.utimesSync(dstPath, now, now);
      const stat = fs.statSync(dstPath);
      if (stat.size < 30_000) {
        throw new Error(`copied PDF too small (${stat.size} bytes)`);
      }
      synced++;
      console.log(
        `[sync] ${srcName} -> ../pivoxquant_pdfs/${refName} (${(stat.size / 1024).toFixed(1)}KB)`,
      );
    } catch (err) {
      failed++;
      console.error(`[sync-fail] ${slug}: ${err.message}`);
    }
  }
  return { synced, failed };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const targets = args.all ? SLUGS : (args.slug ? [args.slug] : []);
  if (!targets.length) {
    console.error("Usage: --slug=<slug> | --all  [--baseUrl=URL]");
    process.exit(1);
  }
  const outDir = path.resolve(__dirname, "..", "public", "samples");
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1024, height: 1366 } });
  const page = await context.newPage();
  // 2026-05-06: emulate "screen" media so all `@media print` rules in
  // globals.css don't hide our content during PDF capture. The PDF
  // engine in Playwright defaults to "print" media which triggered a
  // simulator-only `body * { visibility: hidden !important; }` rule
  // that turned the entire viewport invisible. We render in screen
  // mode and let printBackground:true + the PDF page geometry
  // produce print-quality output.
  await page.emulateMedia({ media: "screen" });

  let ok = 0, fail = 0;
  for (const slug of targets) {
    const url = `${args.baseUrl}/sample-reports/${slug}`;
    const filename = SLUG_TO_FILENAME[slug] ?? `${slug.replace(/-/g, "_")}.pdf`;
    const outPath = path.join(outDir, filename);
    try {
      console.log(`[render] ${slug} -> ${filename}`);
      await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });

      // 2026-05-06 audit fix: wait for the actual report DOM, not just
      // network idle. Networkidle can resolve before client-side React
      // hydration finishes, producing blank-shell PDFs.
      await page.waitForSelector(".pq-pdf-page, .pq-report", { timeout: 15000 });

      // Quality gate: assert the rendered page has non-trivial text
      // before writing the PDF, so a blank-page regression cannot pass
      // CI silently.
      const textLen = await page.evaluate(
        () => (document.body?.innerText || "").length,
      );
      if (textLen < 200) {
        throw new Error(
          `rendered text too short (${textLen} chars) — likely blank page`,
        );
      }

      await page.pdf({
        path: outPath,
        format: "Letter",
        printBackground: true,
        margin: { top: "0.5in", bottom: "0.5in", left: "0.5in", right: "0.5in" },
      });

      // Post-write size check — the empty-shell regression produced
      // 1.5-3.5KB blanks; real samples are 200KB+.
      const stat = fs.statSync(outPath);
      if (stat.size < 30_000) {
        throw new Error(
          `saved PDF too small (${stat.size} bytes) — likely empty shell`,
        );
      }

      ok++;
      console.log(`[saved] ${outPath} (${(stat.size / 1024).toFixed(1)}KB)`);
    } catch (err) {
      fail++;
      console.error(`[fail] ${slug}:`, err.message);
    }
  }
  await browser.close();
  console.log(`\nDone -- ok: ${ok}, fail: ${fail}`);

  // Sync rendered PDFs to sibling reference folder used by lint_pdfs.py.
  // Without this, source-side fixes never reach the lint scope and the
  // 41-finding scan stays stale. Skip with --no-sync.
  let syncFailed = 0;
  if (args.sync && ok > 0) {
    const renderedSlugs = targets.filter(slug => {
      const fname = SLUG_TO_FILENAME[slug] ?? `${slug.replace(/-/g, "_")}.pdf`;
      try {
        return fs.statSync(path.join(outDir, fname)).size >= 30_000;
      } catch { return false; }
    });
    const { synced, failed } = syncToReference(renderedSlugs, outDir);
    syncFailed = failed;
    console.log(`[sync] done -- synced: ${synced}, failed: ${failed}`);
  } else if (!args.sync) {
    console.log("[sync] skipped (--no-sync)");
  }

  process.exit(fail > 0 || syncFailed > 0 ? 1 : 0);
}

main().catch(err => { console.error(err); process.exit(1); });
