/**
 * Render synthetic Toss 내 투자 screens for the Toss holdings eval
 * (src/lib/fill-ocr/__tests__/toss-eval.test.ts).
 *
 * The layout copies the real screen (two unlabelled lines per stock, round
 * logo left, 평가금 right, "N주" under the name, "±손익 (수익률%)" under the
 * amount, rate truncated to 0.1%). What varies, from a fixed seed: light /
 * dark, phone width, pixel ratio, PNG / JPEG quality, header present or rows
 * only, rows cut at the edges, row count, names (KRX master + Korean US
 * names), share counts (many single digits) and prices. No real account data.
 * Ground truth is computed from the same numbers the HTML prints.
 *
 *   node scripts/toss-fixtures-render.mjs <out dir> [count=30] [seed=7]
 *   node scripts/ocr-eval-dump.mjs <out dir> <out dir>/ocr
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const [outDir, countArg, seedArg, modeArg] = process.argv.slice(2);
// "usd": every screen has 해외주식 rows shown with the app's $ toggle on.
const USD_MODE = modeArg === "usd";
if (!outDir) {
  console.error("usage: node scripts/toss-fixtures-render.mjs <out dir> [count] [seed]");
  process.exit(2);
}
const COUNT = Number(countArg ?? 30);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const KR = Object.keys(JSON.parse(fs.readFileSync(path.join(root, "tests/fixtures/screenshot_import/kr_names.json"), "utf8")))
  .filter((n) => /^[가-힣A-Za-z0-9&]+$/.test(n) && n.length <= 10);
const US = Object.entries(JSON.parse(fs.readFileSync(path.join(root, "services/us_kr_names.json"), "utf8")))
  .filter(([n]) => /[가-힣]/.test(n));

// mulberry32 — deterministic
let seed = Number(seedArg ?? 7) >>> 0;
const rnd = () => {
  seed = (seed + 0x6d2b79f5) >>> 0;
  let t = seed;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const pick = (xs) => xs[Math.floor(rnd() * xs.length)];
const int = (a, b) => a + Math.floor(rnd() * (b - a + 1));
const won = (n) => Math.round(n).toLocaleString("en-US");

function holding(foreign) {
  const [name, ticker] = foreign ? pick(US) : [pick(KR), null];
  const shares = rnd() < 0.4 ? int(1, 9) : rnd() < 0.7 ? int(10, 99) : int(100, 999);
  if (foreign && USD_MODE) {
    const avg = int(100, 90000) / 100;
    const cost = Math.round(shares * avg * 100) / 100;
    const value = Math.max(0.01, Math.round(cost * (0.1 + rnd() * 1.8) * 100) / 100);
    const pl = Math.round((value - cost) * 100) / 100;
    const rate = Math.floor((Math.abs(pl) / cost) * 1000) / 10;
    return { name, ticker, shares, avg, cost, value, pl, rate, foreign, usd: true };
  }
  const avg = foreign ? int(3, 900) * 1000 + int(0, 999) : pick([int(1, 99) * 100, int(100, 999) * 100, int(1000, 9999) * 100, int(1, 9) * 100000]);
  const cost = shares * avg;
  const value = Math.max(1, Math.round(cost * (0.1 + rnd() * 1.8)));
  const pl = value - cost;
  const rate = Math.floor((Math.abs(pl) / cost) * 1000) / 10; // Toss truncates
  return { name, ticker, shares, avg, cost, value, pl, rate, foreign };
}

const LOGO = ["#1b3a8c", "#e2762f", "#c8262f", "#17325e", "#2d9d8f", "#6b4bd6", "#0a1f7a", "#d7e8f3"];
const GLYPH = ["cen", "SK", "TFO", "SAMSUNG", "◎", "⊕", "H", "LG", "", "N"];

function css(dark, fontScale) {
  const fg = dark ? "#e8e8ea" : "#191f28", sub = dark ? "#8b8f97" : "#8b95a1", bg = dark ? "#101013" : "#ffffff";
  return `* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: ${bg}; color: ${fg}; font-family: -apple-system, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; font-size: ${16 * fontScale}px; }
.hdr { padding: 20px 20px 8px; } .hdr .t { font-size: 1.2em; font-weight: 700; } .hdr .v { font-size: 2.1em; font-weight: 800; margin-top: 6px; }
.sec { display: flex; justify-content: space-between; padding: 22px 20px 10px; font-size: 1.05em; } .sec .r { color: #3182f6; }
.row { display: flex; align-items: center; padding: 14px 20px; }
.logo { width: 3em; height: 3em; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-size: .7em; font-weight: 800; flex: none; margin-right: 1.1em; }
.mid { flex: 1; } .nm { font-size: 1.12em; } .sh { color: ${sub}; margin-top: 4px; font-size: .95em; }
.rt { text-align: right; } .amt { font-size: 1.12em; font-weight: 700; } .pl { margin-top: 4px; font-size: .95em; }
.neg { color: #3182f6; } .pos { color: #f04452; }`;
}

function row(h, i) {
  const cls = h.pl < 0 ? "neg" : "pos";
  const m = (n) => (h.usd ? `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : won(n));
  const pl = `${h.pl < 0 ? "-" : "+"}${m(Math.abs(h.pl))} (${h.rate.toFixed(1)}%)`;
  return `<div class="row" data-h="${i}"><div class="logo" style="background:${pick(LOGO)}">${pick(GLYPH)}</div>
<div class="mid"><div class="nm">${h.name}</div><div class="sh">${h.shares}주</div></div>
<div class="rt"><div class="amt">${h.usd ? m(h.value) : `${won(h.value)}원`}</div><div class="pl ${cls}">${pl}</div></div></div>`;
}

fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const truth = {};
for (let k = 0; k < COUNT; k++) {
  const dark = rnd() < 0.4;
  const width = pick([375, 390, 393, 430]);
  const dpr = pick([2, 3]);
  const fontScale = pick([0.95, 1, 1, 1.08]);
  const jpeg = rnd() < 0.5;
  const header = rnd() < 0.5;
  const kr = Array.from({ length: int(2, 6) }, () => holding(false));
  const us = USD_MODE || rnd() < 0.5 ? Array.from({ length: int(1, 3) }, () => holding(true)) : [];
  const all = [...kr, ...us];
  const total = all.reduce((s, h) => s + (h.usd ? h.value * 1400 : h.value), 0);
  const totalPl = all.reduce((s, h) => s + (h.usd ? h.pl * 1400 : h.pl), 0);
  const html = `<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>${css(dark, fontScale)}</style></head><body>
${header ? `<div class="hdr"><div class="t">내 투자</div><div class="v">${won(total)}원 ›</div><div class="neg">${totalPl < 0 ? "-" : "+"}${won(Math.abs(totalPl))}원</div></div>` : ""}
${header ? `<div class="sec"><span>국내주식 <span class="r">-20.4%</span></span><span>⌃</span></div>` : ""}
${kr.map(row).join("")}
${us.length ? `<div class="sec"><span>해외주식 <span class="r">-59.1%</span></span><span>⌃</span></div>${us.map((h, i) => row(h, kr.length + i)).join("")}` : ""}
</body></html>`;
  const page = await browser.newPage({ viewport: { width, height: 844 }, deviceScaleFactor: dpr });
  await page.setContent(html);
  const h = await page.evaluate(() => document.body.scrollHeight);
  const clipH = Math.min(h, 1400);
  // Truth = the holdings whose row is fully inside the capture.
  const visible = await page.evaluate((ch) => [...document.querySelectorAll("[data-h]")]
    .filter((e) => e.getBoundingClientRect().bottom <= ch).map((e) => Number(e.getAttribute("data-h"))), clipH);
  const file = `toss_${String(k).padStart(2, "0")}.${jpeg ? "jpg" : "png"}`;
  await page.screenshot({
    path: path.join(outDir, file), fullPage: true, clip: { x: 0, y: 0, width, height: clipH },
    ...(jpeg ? { type: "jpeg", quality: pick([70, 80, 90]) } : {}),
  });
  await page.close();
  truth[file] = {
    variant: { dark, width, dpr, fontScale, jpeg, header },
    holdings: all.filter((_, i) => visible.includes(i)).map((x) => ({ name: x.name, ticker: x.ticker, shares: x.shares, avg_cost: x.foreign && !x.usd ? null : x.avg, foreign: x.foreign })),
  };
  console.log(file, JSON.stringify(truth[file].variant));
}
await browser.close();
fs.writeFileSync(path.join(outDir, "ground_truth.json"), JSON.stringify(truth, null, 2) + "\n");
