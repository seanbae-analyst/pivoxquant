/**
 * Render synthetic holdings (잔고) screens in the styles of several Korean
 * broker apps for the broker holdings eval
 * (src/lib/fill-ocr/__tests__/broker-eval.test.ts).
 *
 * The styles are approximations of the common layouts, drawn from memory —
 * not copies of the apps: a two-line-header table (키움 영웅문S# style),
 * labelled key-value cards (한국투자 style), a table with two values per cell
 * (미래에셋 M-STOCK style), a card grid (삼성증권 mPOP style), a one-line
 * summary list (NH 나무 style) and a USD holdings list. What varies, from a
 * fixed seed: style, light/dark, phone width, pixel ratio, PNG/JPEG, row
 * count, names (KRX master / US), share counts and prices. No real account
 * data. Ground truth comes from the same numbers the HTML prints.
 *
 *   node scripts/broker-fixtures-render.mjs <out dir> [count=36] [seed=3]
 *   node scripts/ocr-eval-dump.mjs <out dir> <out dir>/ocr
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const [outDir, countArg, seedArg] = process.argv.slice(2);
if (!outDir) {
  console.error("usage: node scripts/broker-fixtures-render.mjs <out dir> [count] [seed]");
  process.exit(2);
}
const COUNT = Number(countArg ?? 36);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const KR = Object.keys(JSON.parse(fs.readFileSync(path.join(root, "tests/fixtures/screenshot_import/kr_names.json"), "utf8")))
  .filter((n) => /^[가-힣A-Za-z0-9&]+$/.test(n) && n.length <= 9);
const US = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "PLTR", "SMR", "JOBY", "IONQ", "SOXL", "TQQQ", "QQQ", "SPY", "SCHD", "O", "KO"];

let seed = Number(seedArg ?? 3) >>> 0;
const rnd = () => {
  seed = (seed + 0x6d2b79f5) >>> 0;
  let t = seed;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const pick = (xs) => xs[Math.floor(rnd() * xs.length)];
const int = (a, b) => a + Math.floor(rnd() * (b - a + 1));
const krw = (n) => Math.round(n).toLocaleString("en-US");
const usd = (n) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function holding(us) {
  const shares = rnd() < 0.35 ? int(1, 9) : rnd() < 0.7 ? int(10, 99) : int(100, 1500);
  if (us) {
    const avg = int(500, 90000) / 100;
    const cur = Math.round(avg * (0.3 + rnd() * 1.6) * 100) / 100;
    const cost = Math.round(shares * avg * 100) / 100, value = Math.round(shares * cur * 100) / 100;
    return { name: pick(US), us, shares, avg, cur, cost, value, pl: Math.round((value - cost) * 100) / 100 };
  }
  const avg = pick([int(10, 999) * 10, int(100, 9999) * 10, int(1000, 99999) * 10]);
  const cur = Math.max(10, Math.round((avg * (0.3 + rnd() * 1.6)) / 5) * 5);
  const cost = shares * avg, value = shares * cur;
  return { name: pick(KR), us, shares, avg, cur, cost, value, pl: value - cost };
}
const money = (h, n, unit = true) => (h.us ? `$${usd(n)}` : `${krw(n)}${unit ? "원" : ""}`);
const signed = (h, n, unit = true) => `${n >= 0 ? "+" : "-"}${money(h, Math.abs(n), unit)}`;
const rate = (h) => `${h.pl >= 0 ? "+" : "-"}${Math.abs((h.pl / h.cost) * 100).toFixed(2)}%`;
const dir = (h) => (h.pl >= 0 ? "up" : "dn");

function theme(dark) {
  return dark
    ? { bg: "#0f1115", fg: "#e9eaec", sub: "#8d939b", line: "#23262d", head: "#191c22", card: "#171a20" }
    : { bg: "#ffffff", fg: "#191f28", sub: "#6b7684", line: "#e5e8eb", head: "#f2f4f6", card: "#f7f8fa" };
}
const css = (t) => `* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: ${t.bg}; color: ${t.fg}; font-family: -apple-system, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; }
h1 { font-size: 19px; padding: 16px 16px 10px; } .sub { color: ${t.sub}; }
.up { color: #e22a2a; } .dn { color: #1f5fd6; }`;

// ── styles ──────────────────────────────────────────────────────────────

const STYLES = {
  /** 키움 style: two header lines, two body lines per stock. */
  kiwoom(hs, t) {
    return `<style>${css(t)} table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
      th { background: ${t.head}; color: ${t.sub}; font-weight: 500; padding: 5px 6px; text-align: right; }
      td { padding: 6px 6px; text-align: right; } th:first-child, td:first-child { text-align: left; }
      tr.b td { border-bottom: 1px solid ${t.line}; padding-bottom: 10px; }</style>
      <h1>계좌잔고</h1><table>
      <tr><th>종목명</th><th>평가손익</th><th>수익률</th></tr>
      <tr><th>보유수량</th><th>매입가</th><th>평가금액</th></tr>
      ${hs.map((h, i) => `<tr><td>${h.name}</td><td class="${dir(h)}">${signed(h, h.pl, false)}</td><td class="${dir(h)}">${rate(h)}</td></tr>
      <tr class="b" data-h="${i}"><td>${h.shares}</td><td>${money(h, h.avg, false)}</td><td>${money(h, h.value, false)}</td></tr>`).join("")}</table>`;
  },
  /** 한국투자 style: one card per stock, one label per line. */
  kis(hs, t) {
    return `<style>${css(t)} .c { background: ${t.card}; margin: 10px 14px; border-radius: 12px; padding: 14px 16px; }
      .n { font-size: 16px; font-weight: 700; margin-bottom: 8px; } .kv { display: flex; justify-content: space-between; font-size: 14px; padding: 3px 0; }
      .kv span:first-child { color: ${t.sub}; }</style><h1>잔고</h1>
      ${hs.map((h, i) => `<div class="c" data-h="${i}"><div class="n">${h.name}</div>
        <div class="kv"><span>평가손익</span><span class="${dir(h)}">${signed(h, h.pl)} (${rate(h)})</span></div>
        <div class="kv"><span>보유수량</span><span>${h.shares}주</span></div>
        <div class="kv"><span>평균단가</span><span>${money(h, h.avg)}</span></div>
        <div class="kv"><span>현재가</span><span>${money(h, h.cur)}</span></div>
        <div class="kv"><span>평가금액</span><span>${money(h, h.value)}</span></div></div>`).join("")}`;
  },
  /** 미래에셋 style: two values stacked in each cell. */
  mirae(hs, t) {
    return `<style>${css(t)} table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
      th { background: ${t.head}; color: ${t.sub}; font-weight: 500; padding: 6px 5px; text-align: right; line-height: 1.5; }
      td { padding: 9px 5px; text-align: right; border-bottom: 1px solid ${t.line}; line-height: 1.6; }
      th:first-child, td:first-child { text-align: left; }</style><h1>주식잔고</h1><table>
      <tr><th>종목명</th><th>평가손익<br>수익률</th><th>잔고수량<br>평균단가</th><th>평가금액<br>현재가</th></tr>
      ${hs.map((h, i) => `<tr data-h="${i}"><td>${h.name}</td><td class="${dir(h)}">${signed(h, h.pl, false)}<br>${rate(h)}</td>
        <td>${h.shares}<br>${money(h, h.avg, false)}</td><td>${money(h, h.value, false)}<br>${money(h, h.cur, false)}</td></tr>`).join("")}</table>`;
  },
  /** 삼성증권 style: 2×2 label grid under the name. */
  samsung(hs, t) {
    return `<style>${css(t)} .c { padding: 14px 16px; border-bottom: 1px solid ${t.line}; }
      .n { display: flex; justify-content: space-between; font-size: 16px; font-weight: 700; }
      .g { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 18px; margin-top: 8px; font-size: 13px; }
      .g div { display: flex; justify-content: space-between; } .g span:first-child { color: ${t.sub}; }</style><h1>보유종목</h1>
      ${hs.map((h, i) => `<div class="c" data-h="${i}"><div class="n"><span>${h.name}</span><span class="${dir(h)}">${rate(h)}</span></div><div class="g">
        <div><span>보유수량</span><span>${h.shares}</span></div><div><span>매입단가</span><span>${money(h, h.avg, false)}</span></div>
        <div><span>매입금액</span><span>${money(h, h.cost, false)}</span></div><div><span>평가금액</span><span>${money(h, h.value, false)}</span></div>
      </div></div>`).join("")}`;
  },
  /** NH 나무 style: name, then one summary line. */
  nh(hs, t) {
    return `<style>${css(t)} .r { padding: 14px 16px; border-bottom: 1px solid ${t.line}; }
      .n { display: flex; justify-content: space-between; font-size: 16px; } .s { margin-top: 6px; font-size: 13px; color: ${t.sub}; }</style>
      <h1>보유주식</h1>
      ${hs.map((h, i) => `<div class="r" data-h="${i}"><div class="n"><span>${h.name}</span><span>${money(h, h.value)}</span></div>
        <div class="s">${h.shares}주 · 평단 ${money(h, h.avg)} · <span class="${dir(h)}">${signed(h, h.pl)} (${rate(h)})</span></div></div>`).join("")}`;
  },
};

fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const truth = {};
const names = Object.keys(STYLES);
for (let k = 0; k < COUNT; k++) {
  const style = names[k % names.length];
  const dark = rnd() < 0.35;
  const width = pick([375, 390, 393, 430]);
  const dpr = pick([2, 3]);
  const jpeg = rnd() < 0.5;
  const us = rnd() < 0.3;
  // One screen never lists the same stock twice.
  const hs = [];
  for (let n = int(3, 7), guard = 0; hs.length < n && guard < 50; guard++) {
    const x = holding(us);
    if (!hs.some((y) => y.name === x.name)) hs.push(x);
  }
  const html = `<!doctype html><html lang="ko"><head><meta charset="utf-8"></head><body>${STYLES[style](hs, theme(dark))}</body></html>`;
  const page = await browser.newPage({ viewport: { width, height: 844 }, deviceScaleFactor: dpr });
  await page.setContent(html);
  const h = await page.evaluate(() => document.body.scrollHeight);
  const clipH = Math.max(480, Math.min(h + 10, 1400));
  // Truth = the holdings whose block is fully inside the capture.
  const visible = await page.evaluate((ch) => [...document.querySelectorAll("[data-h]")]
    .filter((e) => e.getBoundingClientRect().bottom <= ch).map((e) => Number(e.getAttribute("data-h"))), clipH);
  const file = `${style}_${String(k).padStart(2, "0")}.${jpeg ? "jpg" : "png"}`;
  await page.screenshot({
    path: path.join(outDir, file), fullPage: true, clip: { x: 0, y: 0, width, height: clipH },
    ...(jpeg ? { type: "jpeg", quality: pick([70, 80, 90]) } : {}),
  });
  await page.close();
  truth[file] = {
    variant: { style, dark, width, dpr, jpeg, us },
    holdings: hs.filter((_, i) => visible.includes(i))
      .map((x) => ({ name: x.name, shares: x.shares, avg_cost: x.avg, currency: x.us ? "USD" : "KRW" })),
  };
  console.log(file, JSON.stringify(truth[file].variant));
}
await browser.close();
fs.writeFileSync(path.join(outDir, "ground_truth.json"), JSON.stringify(truth, null, 2) + "\n");
