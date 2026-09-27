/**
 * Render the synthetic holdings (보유종목/잔고) screens the holdings parser
 * eval runs on (src/lib/fill-ocr/__tests__/holdings-eval.test.ts).
 *
 * Every screen is plain HTML rendered by headless Chromium at a phone
 * viewport (390×844 @2x → 780×1688, the size of the fill-screen fixtures).
 * No real account data — names are listed stocks, numbers are made up.
 * Ground truth is computed from the same data the HTML prints, so it cannot
 * drift from the picture.
 *
 *   node scripts/holdings-fixtures-render.mjs <tune|heldout> <out dir>
 *   node scripts/ocr-eval-dump.mjs <out dir> <out dir>/ocr
 *
 * docs/product/HOLDINGS_IMPORT_DESIGN.md §accuracy.
 */
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const [setName, outDir] = process.argv.slice(2);
if (!setName || !outDir) {
  console.error("usage: node scripts/holdings-fixtures-render.mjs <tune|heldout> <out dir>");
  process.exit(2);
}

const krw = (n) => Math.round(n).toLocaleString("en-US");
const usd = (n) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const signed = (n, f) => (n >= 0 ? `+${f(n)}` : `-${f(-n)}`);
const pct = (pl, cost) => `${pl >= 0 ? "+" : "-"}${Math.abs((pl / cost) * 100).toFixed(2)}%`;

/** h = {name, code?, ticker?, shares, avg, cur, currency} → derived money. */
function money(h) {
  const cost = h.currency === "USD" ? Math.round(h.shares * h.avg * 100) / 100 : Math.round(h.shares * h.avg);
  const value = h.currency === "USD" ? Math.round(h.shares * h.cur * 100) / 100 : Math.round(h.shares * h.cur);
  const pl = h.currency === "USD" ? Math.round((value - cost) * 100) / 100 : value - cost;
  return { cost, value, pl };
}

const BASE_CSS = `
* { box-sizing: border-box; margin: 0; padding: 0; }
body { width: 390px; min-height: 844px; font-family: "Apple SD Gothic Neo", "Noto Sans CJK KR", sans-serif; }
.status { height: 44px; display: flex; justify-content: space-between; align-items: center; padding: 0 24px; font-size: 14px; font-weight: 600; }
`;

// ── layouts ─────────────────────────────────────────────────────────────

/** Dark card list: name + 평가금액 on one line, "N주 · 평균 · 현재 · 손익" below. */
function darkCards({ title, holdings, sep = "·", avgLabel = "평균", curLabel = "현재" }) {
  const cards = holdings.map((h) => {
    const m = money(h);
    const f = h.currency === "USD" ? (n) => `$${usd(n)}` : (n) => `${krw(n)}원`;
    const fp = h.currency === "USD" ? (n) => usd(n) : (n) => krw(n);
    return `<div class="card"><div class="r1"><span class="nm">${h.label ?? h.name}</span><span class="val">${f(m.value)}</span></div>
      <div class="r2">${h.shares}주 ${sep} ${avgLabel} ${f(h.avg)} ${sep} ${curLabel} ${f(h.cur)} <span class="${m.pl >= 0 ? "up" : "dn"}">${signed(m.pl, fp)} (${pct(m.pl, m.cost)})</span></div></div>`;
  }).join("");
  return `<style>${BASE_CSS}
    body { background: #111317; color: #e8e8ea; }
    h1 { font-size: 20px; padding: 16px 20px; }
    .card { padding: 18px 20px; border-bottom: 1px solid #22252b; }
    .r1 { display: flex; justify-content: space-between; font-size: 17px; font-weight: 600; }
    .r2 { margin-top: 8px; font-size: 13px; color: #9aa0a6; }
    .up { color: #f04452; } .dn { color: #3182f6; }
  </style><div class="status"><span>9:41</span><span>LTE</span></div>
  <h1>${title}</h1><div style="padding:0 20px 8px;font-size:13px;color:#9aa0a6">보유종목 ${holdings.length}</div>${cards}`;
}

/** Light HTS-like table with a header row. `cols` picks and orders columns. */
function lightTable({ title, holdings, cols, codeUnder = false, summary = true, headerLabels = {} }) {
  const L = {
    name: "종목명", shares: "보유수량", avg: "평균단가", cur: "현재가", value: "평가금액",
    cost: "매입금액", pl: "평가손익", rate: "수익률", ...headerLabels,
  };
  const cell = (h, c) => {
    const m = money(h);
    const f = h.currency === "USD" ? (n) => `$${usd(n)}` : (n) => krw(n);
    switch (c) {
      case "name": return `<td class="nm">${h.label ?? h.name}${codeUnder && h.code ? `<div class="code">${h.code}</div>` : ""}</td>`;
      case "shares": return `<td>${h.shares}</td>`;
      case "avg": return `<td>${f(h.avg)}</td>`;
      case "cur": return `<td>${f(h.cur)}</td>`;
      case "value": return `<td>${f(m.value)}</td>`;
      case "cost": return `<td>${f(m.cost)}</td>`;
      case "pl": return `<td class="${m.pl >= 0 ? "up" : "dn"}">${signed(m.pl, h.currency === "USD" ? usd : krw)}</td>`;
      case "rate": return `<td class="${m.pl >= 0 ? "up" : "dn"}">${pct(m.pl, m.cost)}</td>`;
      default: return "<td></td>";
    }
  };
  const tot = holdings.reduce((a, h) => { const m = money(h); return { cost: a.cost + m.cost, value: a.value + m.value }; }, { cost: 0, value: 0 });
  return `<style>${BASE_CSS}
    body { background: #fff; color: #191f28; }
    h1 { font-size: 18px; padding: 12px 12px 6px; }
    .sum { padding: 4px 12px 12px; font-size: 13px; color: #4e5968; line-height: 1.7; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th { background: #f2f4f6; color: #4e5968; font-weight: 600; padding: 8px 3px; text-align: right; }
    th:first-child, td.nm { text-align: left; padding-left: 8px; }
    td { padding: 12px 3px; border-bottom: 1px solid #e5e8eb; text-align: right; vertical-align: top; }
    .code { color: #8b95a1; font-size: 11px; margin-top: 3px; }
    .up { color: #e22a2a; } .dn { color: #1f5fd6; }
  </style><div class="status"><span>9:41</span><span>5G</span></div>
  <h1>${title}</h1>
  ${summary ? `<div class="sum">총 매입 ${krw(tot.cost)}원<br>총 평가 ${krw(tot.value)}원</div>` : ""}
  <table><tr>${cols.map((c) => `<th>${L[c]}</th>`).join("")}</tr>
  ${holdings.map((h) => `<tr>${cols.map((c) => cell(h, c)).join("")}</tr>`).join("")}</table>`;
}

/** Key-value detail cards (one block per stock, one label per line). */
function kvCards({ title, holdings, keys }) {
  const L = { shares: "보유수량", avg: "평균단가", cost: "매입금액", value: "평가금액", cur: "현재가", pl: "평가손익" };
  const blocks = holdings.map((h) => {
    const m = money(h);
    const f = h.currency === "USD" ? (n) => `$${usd(n)}` : (n) => `${krw(n)}원`;
    const v = { shares: `${h.shares}주`, avg: f(h.avg), cost: f(m.cost), value: f(m.value), cur: f(h.cur), pl: signed(m.pl, h.currency === "USD" ? (n) => `$${usd(n)}` : (n) => `${krw(n)}원`) };
    return `<div class="blk"><div class="hd">${h.label ?? h.name}${h.code ? ` <span class="code">${h.code}</span>` : ""}${h.ticker && h.showTicker ? ` <span class="code">${h.ticker}</span>` : ""}</div>
      ${keys.map((k) => `<div class="kv"><span>${L[k]}</span><span>${v[k]}</span></div>`).join("")}</div>`;
  }).join("");
  return `<style>${BASE_CSS}
    body { background: #f7f8fa; color: #191f28; }
    h1 { font-size: 20px; padding: 14px 20px; }
    .blk { background: #fff; margin: 10px 14px; border-radius: 14px; padding: 14px 16px; }
    .hd { font-size: 16px; font-weight: 700; margin-bottom: 8px; }
    .code { font-size: 12px; color: #8b95a1; font-weight: 400; }
    .kv { display: flex; justify-content: space-between; font-size: 14px; padding: 4px 0; color: #333d4b; }
  </style><div class="status"><span>9:41</span><span>LTE</span></div><h1>${title}</h1>${blocks}`;
}

/** US card list: "Apple AAPL  $2,501.00" / "10주 · 평균 $182.40 · 현재 $250.10". */
function usCards({ title, holdings }) {
  const cards = holdings.map((h) => {
    const m = money(h);
    return `<div class="card"><div class="r1"><span><b>${h.name}</b> <span class="tk">${h.ticker}</span></span><span>$${usd(m.value)}</span></div>
      <div class="r2">${h.shares}주 · 평균 $${usd(h.avg)} · 현재 $${usd(h.cur)}</div>
      <div class="r3 ${m.pl >= 0 ? "up" : "dn"}">${signed(m.pl, (n) => `$${usd(n)}`)} (${pct(m.pl, m.cost)})</div></div>`;
  }).join("");
  return `<style>${BASE_CSS}
    body { background: #fff; color: #191f28; }
    h1 { font-size: 20px; padding: 14px 20px 4px; }
    .card { padding: 16px 20px; border-bottom: 1px solid #eef0f3; }
    .r1 { display: flex; justify-content: space-between; font-size: 16px; }
    .tk { color: #8b95a1; font-size: 13px; }
    .r2 { margin-top: 6px; font-size: 13px; color: #6b7684; }
    .r3 { margin-top: 3px; font-size: 13px; } .up { color: #e22a2a; } .dn { color: #1f5fd6; }
  </style><div class="status"><span>9:41</span><span>5G</span></div><h1>${title}</h1>
  <div style="padding:0 20px 10px;font-size:13px;color:#6b7684">해외주식 보유종목 · 평가금액 기준</div>${cards}`;
}

// ── data ────────────────────────────────────────────────────────────────

const K = (name, code, shares, avg, cur, label) => ({ name, code, shares, avg, cur, currency: "KRW", label });
const U = (name, ticker, shares, avg, cur) => ({ name, ticker, shares, avg, cur, currency: "USD" });

const SETS = {
  tune: {
    "t01_dark_cards.png": { layout: darkCards, title: "OO증권 · 내 주식", holdings: [
      K("삼성전자", "005930", 42, 68200, 71500), K("LG에너지솔루션", "373220", 3, 412000, 385500),
      K("기아", "000270", 15, 96400, 101200), K("신한지주", "055550", 30, 45150, 52300),
      K("한국전력", "015760", 50, 21350, 20800) ] },
    "t02_table_codes.png": { layout: lightTable, title: "주식잔고", codeUnder: true,
      cols: ["name", "shares", "avg", "cur", "value", "pl"], holdings: [
      K("삼성전자", "005930", 120, 61300, 72400), K("SK하이닉스", "000660", 7, 131500, 198500),
      K("NAVER", "035420", 12, 214000, 187300), K("카카오", "035720", 25, 58400, 41850),
      K("셀트리온", "068270", 9, 176400, 184300), K("KB금융", "105560", 20, 61800, 87600) ] },
    "t03_us_cards.png": { layout: usCards, title: "해외주식 잔고", holdings: [
      U("Apple", "AAPL", 10, 182.4, 250.1), U("Microsoft", "MSFT", 4, 402.15, 438.2),
      U("Tesla", "TSLA", 2.5, 244.8, 221.35), U("NVIDIA", "NVDA", 30, 96.4, 132.1) ] },
    "t04_kv_cost.png": { layout: kvCards, title: "보유종목 상세", keys: ["shares", "avg", "cost", "value"], holdings: [
      K("현대차", "005380", 6, 251000, 245000), K("POSCO홀딩스", "005490", 4, 389500, 402000),
      K("하나금융지주", "086790", 18, 57300, 63100) ] },
    "t05_table_cost_only.png": { layout: lightTable, title: "계좌잔고", summary: true,
      cols: ["name", "shares", "cost", "cur", "pl"], headerLabels: { name: "종목", shares: "잔고수량" }, holdings: [
      K("LG화학", "051910", 5, 364200, 331000), K("삼성SDI", "006400", 3, 287500, 301000),
      K("크래프톤", "259960", 8, 244750, 262500), K("LG전자", "066570", 11, 98600, 94100) ] },
    "t06_table_avg_rate.png": { layout: lightTable, title: "잔고/평가", summary: false,
      cols: ["name", "shares", "avg", "cur", "rate"], headerLabels: { avg: "매입가" }, holdings: [
      K("카카오뱅크", "323410", 40, 24150, 21900), K("엔씨소프트", "036570", 2, 231000, 198700),
      K("삼성바이오로직스", "207940", 1, 812000, 945000), K("기아", "000270", 13, 88900, 101200) ] },
  },
  heldout: {
    "v01_dark_cards_pyeongdan.png": { layout: darkCards, title: "MY 보유주식", avgLabel: "평단", curLabel: "현재가", sep: "|", holdings: [
      K("하나금융지주", "086790", 22, 58950, 63100), K("삼성전자", "005930", 7, 74100, 71500),
      K("LG전자", "066570", 9, 103200, 94100), K("KB금융", "105560", 5, 79800, 87600) ] },
    "v02_table_all_cols.png": { layout: lightTable, title: "보유종목", codeUnder: false, summary: true,
      cols: ["name", "shares", "avg", "cost", "cur", "value"], headerLabels: { shares: "수량", avg: "평균가" }, holdings: [
      K("POSCO홀딩스", "005490", 3, 371000, 402000), K("셀트리온", "068270", 14, 169800, 184300),
      K("한국전력", "015760", 100, 19870, 20800), K("신한지주", "055550", 16, 48200, 52300),
      K("카카오", "035720", 33, 44900, 41850) ] },
    "v03_kv_us.png": { layout: kvCards, title: "해외 보유종목", keys: ["shares", "avg", "cur", "value", "pl"], holdings: [
      { ...U("Apple", "AAPL", 12, 171.25, 250.1), showTicker: true },
      { ...U("Amazon", "AMZN", 6, 188.4, 201.7), showTicker: true },
      { ...U("Alphabet", "GOOGL", 1.75, 152.3, 171.9), showTicker: true } ] },
    "v04_table_us.png": { layout: lightTable, title: "해외잔고", summary: false,
      cols: ["name", "shares", "avg", "cur", "pl"], holdings: [
      U("TSLA", "TSLA", 8, 212.5, 221.35), U("NVDA", "NVDA", 15, 118.2, 132.1),
      U("MSFT", "MSFT", 2, 415.6, 438.2), U("QQQ", "QQQ", 5, 468.9, 489.3) ] },
  },
};

const spec = SETS[setName];
if (!spec) { console.error(`unknown set ${setName}`); process.exit(2); }
fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
const truth = {};
for (const [file, s] of Object.entries(spec)) {
  await page.setContent(`<!doctype html><html lang="ko"><head><meta charset="utf-8"></head><body>${s.layout(s)}</body></html>`);
  await page.screenshot({ path: path.join(outDir, file), clip: { x: 0, y: 0, width: 390, height: 844 } });
  truth[file] = {
    screen_type: "holdings",
    holdings: s.holdings.map((h) => ({
      name: h.name, ticker: h.currency === "USD" ? h.ticker : (h.code ?? null), shares: h.shares,
      avg_cost: h.avg, currency: h.currency, cost: money(h).cost,
    })),
  };
  console.log(file);
}
await browser.close();
fs.writeFileSync(path.join(outDir, "ground_truth.json"), JSON.stringify(truth, null, 2) + "\n");
