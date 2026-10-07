/**
 * Render the synthetic screens for the AI-read experiment
 * (docs/product/AI_READ_EXPERIMENT_2026-10-07.md).
 *
 * Unlike holdings-fixtures-render.mjs, every number and most stock picks come
 * from a seeded RNG, so whoever writes this file does not know the answers —
 * the reader under test only ever sees the masked OCR text.
 *
 * Screens span broker-style layouts (light/dark cards, two-row grids,
 * key-value blocks, detail pages, mixed KRW/USD) and pages that hold NO
 * position (fills, order ticket, watchlist, account summary, quote page).
 * Most carry fake personal data (account numbers, customer names) so the
 * masking step can be measured; ground_truth.json lists it under `pii`.
 * Layouts are generic — no broker logos, names or brand colours.
 *
 *   node scripts/ai-read-fixtures-render.mjs <seed> <out dir>
 *   node scripts/ocr-eval-dump.mjs <out dir> <out dir>/ocr
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const [seedArg, outDir] = process.argv.slice(2);
if (!seedArg || !outDir) {
  console.error("usage: node scripts/ai-read-fixtures-render.mjs <seed> <out dir>");
  process.exit(2);
}

// ── rng ─────────────────────────────────────────────────────────────────
let s = Number(seedArg) >>> 0;
const rnd = () => {
  s = (s + 0x6d2b79f5) >>> 0;
  let t = s;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const int = (a, b) => a + Math.floor(rnd() * (b - a + 1));
const pick = (arr) => arr[int(0, arr.length - 1)];

// ── data ────────────────────────────────────────────────────────────────
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const KR = Object.entries(JSON.parse(fs.readFileSync(path.join(root, "tests/fixtures/screenshot_import/kr_names.json"), "utf8")))
  .slice(0, 400)
  .filter(([n]) => !/우$|우B$|스팩/.test(n));
const US = [
  ["Apple", "AAPL"], ["Microsoft", "MSFT"], ["NVIDIA", "NVDA"], ["Amazon", "AMZN"], ["Alphabet A", "GOOGL"],
  ["Meta Platforms", "META"], ["Tesla", "TSLA"], ["Broadcom", "AVGO"], ["Netflix", "NFLX"], ["Palantir", "PLTR"],
  ["Coca-Cola", "KO"], ["Costco", "COST"], ["Invesco QQQ", "QQQ"], ["SPDR S&P 500", "SPY"], ["Realty Income", "O"],
  ["Advanced Micro Devices", "AMD"], ["Visa", "V"], ["JPMorgan Chase", "JPM"], ["SCHD", "SCHD"], ["Intel", "INTC"],
];
const PEOPLE = ["김민준", "이서연", "박지호", "최수아", "정우진", "강하은", "조현우", "윤지민"];

/** KRW: avg 1,000~400,000 (10원 단위), cur within ±25%. USD: avg 10~600, 2dp. */
function krStock() {
  const [name, code] = pick(KR);
  const avg = int(100, 40000) * 10;
  const cur = Math.max(10, Math.round((avg * (0.75 + rnd() * 0.5)) / 10) * 10);
  return { name, code, ticker: null, shares: int(1, 300), avg, cur, currency: "KRW" };
}
function usStock() {
  const [name, ticker] = pick(US);
  const avg = int(1000, 60000) / 100;
  const cur = Math.round(avg * (0.75 + rnd() * 0.5) * 100) / 100;
  const shares = rnd() < 0.2 ? int(1, 400) / 100 : int(1, 120);
  return { name, code: null, ticker, shares, avg, cur, currency: "USD" };
}
const uniq = (gen, n) => {
  const out = [], seen = new Set();
  while (out.length < n) { const h = gen(); const k = h.code ?? h.ticker; if (!seen.has(k)) { seen.add(k); out.push(h); } }
  return out;
};
const money = (h) => {
  const r = (x) => (h.currency === "USD" ? Math.round(x * 100) / 100 : Math.round(x));
  const cost = r(h.shares * h.avg), value = r(h.shares * h.cur);
  return { cost, value, pl: r(value - cost) };
};
const krw = (n) => Math.round(n).toLocaleString("en-US");
const usd = (n) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const amt = (h, n) => (h.currency === "USD" ? `$${usd(n)}` : `${krw(n)}원`);
const sgn = (h, n) => (n >= 0 ? "+" : "-") + (h.currency === "USD" ? `$${usd(Math.abs(n))}` : `${krw(Math.abs(n))}원`);
const pct = (m) => `${m.pl >= 0 ? "+" : "-"}${Math.abs((m.pl / m.cost) * 100).toFixed(2)}%`;
const acct = () => pick([
  () => `${int(100, 999)}-${int(10, 99)}-${int(100000, 999999)}`,
  () => `${int(1000, 9999)}-${int(1000, 9999)}-${int(10, 99)}`,
  () => `${int(10000000, 99999999)}-${int(10, 99)}`,
])();

const CSS = `* { box-sizing: border-box; margin: 0; padding: 0; }
body { width: 390px; min-height: 844px; font-family: "Noto Sans CJK KR", "WenQuanYi Zen Hei", sans-serif; }
.st { height: 44px; display: flex; justify-content: space-between; align-items: center; padding: 0 24px; font-size: 14px; font-weight: 600; }
.up { color: #e5484d; } .dn { color: #3b82f6; } .mut { color: #8b95a1; }`;
const status = () => `<div class="st"><span>${int(8, 11)}:${String(int(0, 59)).padStart(2, "0")}</span><span>LTE</span></div>`;
const page = (body, css, dark = false) =>
  `<style>${CSS} body { background: ${dark ? "#101215" : "#fff"}; color: ${dark ? "#e8e8ea" : "#191f28"}; } ${css}</style>${status()}${body}`;

// ── layouts: holdings ───────────────────────────────────────────────────

/** Light rounded list: name / 평가금액 / 손익 + "N주". No 평균단가 on screen. */
function cardsNoAvg(hs, pii) {
  const who = pick(PEOPLE), a = acct(); pii.push(who, a);
  const rows = hs.map((h) => { const m = money(h); return `<div class="row"><div><div class="nm">${h.name}</div><div class="mut sm">${h.shares}주</div></div>
    <div class="r"><div class="v">${amt(h, m.value)}</div><div class="${m.pl >= 0 ? "up" : "dn"} sm">${sgn(h, m.pl)} (${pct(m)})</div></div></div>`; }).join("");
  return page(`<div class="hd">${who}님의 계좌 <span class="mut">${a}</span></div><div class="tot">내 투자</div>${rows}`,
    `.hd { padding: 12px 20px; font-size: 14px; } .tot { padding: 8px 20px 4px; font-size: 22px; font-weight: 700; }
     .row { display: flex; justify-content: space-between; padding: 16px 20px; } .nm { font-size: 17px; font-weight: 600; }
     .sm { font-size: 13px; margin-top: 4px; } .r { text-align: right; } .v { font-size: 17px; font-weight: 600; }`);
}

/** Dark cards with labelled 평균/현재 on the second line. */
function darkCards(hs, pii) {
  const a = acct(); pii.push(a);
  const rows = hs.map((h) => { const m = money(h); return `<div class="c"><div class="r1"><span>${h.name}</span><span>${amt(h, m.value)}</span></div>
    <div class="r2">${h.shares}주 · 평균 ${amt(h, h.avg)} · 현재 ${amt(h, h.cur)} <span class="${m.pl >= 0 ? "up" : "dn"}">${sgn(h, m.pl)}</span></div></div>`; }).join("");
  return page(`<div class="hd">위탁 ${a}</div><h1>보유 ${hs.length}</h1>${rows}`,
    `.hd { padding: 8px 20px; font-size: 13px; color: #9aa0a6; } h1 { font-size: 20px; padding: 10px 20px; }
     .c { padding: 16px 20px; border-bottom: 1px solid #23262c; } .r1 { display: flex; justify-content: space-between; font-size: 16px; font-weight: 600; }
     .r2 { font-size: 13px; color: #a5aab3; margin-top: 6px; }`, true);
}

/** Dense two-row grid: (종목명 | 평가손익 | 수익률) over (보유수량 | 매입가 | 현재가). */
function twoRowGrid(hs, pii) {
  const who = pick(PEOPLE), a = acct(); pii.push(who, a);
  const rows = hs.map((h) => { const m = money(h); return `<tr class="a"><td>${h.name}</td><td class="${m.pl >= 0 ? "up" : "dn"}">${h.currency === "USD" ? usd(m.pl) : krw(m.pl)}</td><td class="${m.pl >= 0 ? "up" : "dn"}">${pct(m)}</td></tr>
    <tr class="b"><td>${h.shares}</td><td>${h.currency === "USD" ? usd(h.avg) : krw(h.avg)}</td><td>${h.currency === "USD" ? usd(h.cur) : krw(h.cur)}</td></tr>`; }).join("");
  return page(`<div class="hd">계좌 ${a} ${who}</div><div class="tt">잔고</div>
    <table><tr class="h"><th>종목명</th><th>평가손익</th><th>수익률</th></tr><tr class="h"><th>보유수량</th><th>매입가</th><th>현재가</th></tr>${rows}</table>`,
    `.hd { padding: 8px 12px; font-size: 13px; background: #f2f4f6; } .tt { padding: 10px 12px; font-size: 18px; font-weight: 700; }
     table { width: 100%; border-collapse: collapse; font-size: 13px; } th { background: #e9edf2; font-weight: 500; padding: 4px 8px; text-align: right; }
     th:first-child, td:first-child { text-align: left; } td { padding: 4px 8px; text-align: right; } tr.b td { border-bottom: 1px solid #dde1e6; color: #4e5968; }`);
}

/** Key-value blocks, one label per line, code next to the name. */
function kvBlocks(hs, pii) {
  const a = acct(); pii.push(a);
  const rows = hs.map((h) => { const m = money(h); return `<div class="b"><div class="n">${h.name} <span class="mut">${h.code ?? h.ticker}</span></div>
    <div class="kv"><span>보유수량</span><span>${h.shares}주</span></div><div class="kv"><span>매입단가</span><span>${amt(h, h.avg)}</span></div>
    <div class="kv"><span>매입금액</span><span>${amt(h, m.cost)}</span></div><div class="kv"><span>평가손익</span><span class="${m.pl >= 0 ? "up" : "dn"}">${sgn(h, m.pl)}</span></div></div>`; }).join("");
  return page(`<div class="hd">종합 ${a}</div>${rows}`,
    `.hd { padding: 10px 20px; font-size: 13px; color: #6b7684; } .b { margin: 10px 16px; padding: 14px; border: 1px solid #e5e8eb; border-radius: 12px; }
     .n { font-size: 16px; font-weight: 700; margin-bottom: 8px; } .kv { display: flex; justify-content: space-between; font-size: 14px; padding: 3px 0; }`);
}

/** Overseas list: 평균단가 shown in USD with a KRW conversion beside it. */
function usWithKrw(hs, pii) {
  const who = pick(PEOPLE); pii.push(who);
  const fx = int(1300, 1450);
  const rows = hs.map((h) => { const m = money(h); return `<div class="c"><div class="r1"><b>${h.ticker}</b> <span class="mut">${h.name}</span></div>
    <div class="g"><span>수량 ${h.shares}</span><span>평균 $${usd(h.avg)} <span class="mut">(${krw(h.avg * fx)}원)</span></span></div>
    <div class="g"><span>현재 $${usd(h.cur)}</span><span class="${m.pl >= 0 ? "up" : "dn"}">${sgn(h, m.pl)} ${pct(m)}</span></div></div>`; }).join("");
  return page(`<div class="hd">${who} 고객님 · 해외주식</div><div class="fx">적용환율 ${krw(fx)}.${int(10, 99)}</div>${rows}`,
    `.hd { padding: 10px 20px; font-size: 15px; font-weight: 600; } .fx { padding: 0 20px 8px; font-size: 12px; color: #8b95a1; }
     .c { padding: 14px 20px; border-top: 1px solid #eef0f2; } .r1 { font-size: 16px; } .g { display: flex; justify-content: space-between; font-size: 14px; margin-top: 4px; }`);
}

/** Mixed KRW + USD list in one account; currency only from the amount format. */
function mixedList(hs, pii) {
  const a = acct(); pii.push(a);
  const rows = hs.map((h) => { const m = money(h); return `<div class="row"><div class="nm">${h.name}</div>
    <div class="ln"><span>${h.shares}주 · 평단 ${amt(h, h.avg)}</span><span>${amt(h, m.value)}</span></div></div>`; }).join("");
  return page(`<div class="hd">통합계좌 ${a}</div><div class="tt">국내·해외 보유</div>${rows}`,
    `.hd { padding: 8px 20px; font-size: 13px; color: #6b7684; } .tt { padding: 6px 20px 10px; font-size: 20px; font-weight: 700; }
     .row { padding: 12px 20px; border-bottom: 1px solid #f0f1f3; } .nm { font-size: 16px; font-weight: 600; } .ln { display: flex; justify-content: space-between; font-size: 14px; color: #4e5968; margin-top: 4px; }`);
}

/** Single-stock page with a "내 주식" block (1주 평균금액 · 보유 수량). */
function detailWithPosition(h) {
  const m = money(h);
  return page(`<div class="nm">${h.name}</div><div class="px">${amt(h, h.cur)}</div><div class="chart"></div>
    <div class="tab">차트 · 호가 · <b>내 주식</b> · 뉴스</div>
    <div class="kv"><span>1주 평균금액</span><span>${amt(h, h.avg)}</span></div><div class="kv"><span>보유 수량</span><span>${h.shares}주</span></div>
    <div class="kv"><span>총 금액</span><span>${amt(h, m.value)}</span></div><div class="kv"><span>투자 원금</span><span>${amt(h, m.cost)}</span></div>
    <div class="kv"><span>총 수익</span><span class="${m.pl >= 0 ? "up" : "dn"}">${sgn(h, m.pl)} (${pct(m)})</span></div>`,
    `.nm { padding: 8px 20px 0; font-size: 15px; color: #6b7684; } .px { padding: 2px 20px; font-size: 28px; font-weight: 700; }
     .chart { margin: 12px 20px; height: 150px; background: linear-gradient(180deg,#fdecec,#fff); border-radius: 8px; }
     .tab { padding: 10px 20px; font-size: 14px; color: #8b95a1; } .kv { display: flex; justify-content: space-between; padding: 9px 20px; font-size: 15px; }`);
}

/** Card list whose last card is cut by the bottom edge (only the name line shows). */
function truncatedCards(hs, pii) {
  const a = acct(); pii.push(a);
  const rows = hs.map((h) => { const m = money(h); return `<div class="c"><div class="r1"><span>${h.name}</span><span>${amt(h, m.value)}</span></div>
    <div class="r2">보유 ${h.shares}주 · 평균단가 ${amt(h, h.avg)}</div><div class="r2">수익 <span class="${m.pl >= 0 ? "up" : "dn"}">${sgn(h, m.pl)} (${pct(m)})</span></div></div>`; }).join("");
  return page(`<div class="hd">${a}</div><div class="sp"></div>${rows}`,
    `.hd { padding: 8px 20px; font-size: 13px; color: #6b7684; } .sp { height: 262px; background: #f7f8fa; margin: 8px 16px; border-radius: 12px; }
     .c { padding: 18px 20px; border-bottom: 1px solid #eef0f2; } .r1 { display: flex; justify-content: space-between; font-size: 17px; font-weight: 600; } .r2 { font-size: 14px; color: #6b7684; margin-top: 6px; }`);
}

// ── layouts: no position on screen ──────────────────────────────────────

function fillsList(hs, pii) {
  const a = acct(); pii.push(a);
  const rows = hs.map((h) => `<div class="row"><div><div class="nm">${h.name}</div><div class="mut">${int(1, 28)}일 ${int(9, 15)}:${String(int(0, 59)).padStart(2, "0")}</div></div>
    <div class="r"><div class="${rnd() < 0.5 ? "up" : "dn"}">${rnd() < 0.5 ? "매수" : "매도"} ${int(1, 50)}주</div><div>체결가 ${amt(h, h.cur)}</div></div></div>`).join("");
  return page(`<div class="hd">${a}</div><div class="tt">체결내역</div>${rows}`,
    `.hd { padding: 8px 20px; font-size: 13px; color: #6b7684; } .tt { padding: 6px 20px; font-size: 20px; font-weight: 700; }
     .row { display: flex; justify-content: space-between; padding: 14px 20px; font-size: 14px; } .nm { font-size: 16px; font-weight: 600; } .r { text-align: right; }`);
}

function orderTicket(h, pii) {
  const who = pick(PEOPLE); pii.push(who);
  return page(`<div class="nm">${h.name} 매수</div><div class="px">${amt(h, h.cur)}</div>
    <div class="kv"><span>주문 가격</span><span>${amt(h, h.cur)}</span></div><div class="kv"><span>주문 수량</span><span>${int(1, 40)}주</span></div>
    <div class="kv"><span>주문 가능 금액</span><span>${krw(int(100, 9000) * 1000)}원</span></div><div class="kv mut"><span>${who}님 · 지정가</span><span></span></div>
    <div class="btn">매수하기</div>`,
    `.nm { padding: 14px 20px 0; font-size: 20px; font-weight: 700; } .px { padding: 4px 20px 16px; font-size: 16px; color: #6b7684; }
     .kv { display: flex; justify-content: space-between; padding: 12px 20px; font-size: 16px; } .btn { margin: 40px 20px; padding: 16px; text-align: center; background: #e5484d; color: #fff; border-radius: 12px; }`);
}

function watchlist(hs) {
  const rows = hs.map((h) => { const ch = (rnd() * 8 - 4).toFixed(2); return `<div class="row"><span class="nm">${h.name}</span>
    <span class="r"><span>${amt(h, h.cur)}</span><span class="${ch >= 0 ? "up" : "dn"}">${ch >= 0 ? "+" : ""}${ch}%</span></span></div>`; }).join("");
  return page(`<div class="tt">관심 종목</div>${rows}`,
    `.tt { padding: 12px 20px; font-size: 20px; font-weight: 700; } .row { display: flex; justify-content: space-between; padding: 14px 20px; font-size: 16px; }
     .r { display: flex; gap: 14px; }`);
}

function accountSummary(pii) {
  const who = pick(PEOPLE), a = acct(); pii.push(who, a);
  const tot = int(500, 90000) * 1000, pl = int(-3000, 9000) * 1000;
  return page(`<div class="hd">${who}님</div><div class="ac">${a}</div><div class="big">${krw(tot)}원</div>
    <div class="kv"><span>평가손익</span><span class="${pl >= 0 ? "up" : "dn"}">${pl >= 0 ? "+" : "-"}${krw(Math.abs(pl))}원</span></div>
    <div class="kv"><span>예수금</span><span>${krw(int(0, 9000) * 1000)}원</span></div><div class="kv"><span>주문가능금액</span><span>${krw(int(0, 9000) * 1000)}원</span></div>`,
    `.hd { padding: 12px 20px 0; font-size: 16px; font-weight: 600; } .ac { padding: 2px 20px; font-size: 13px; color: #8b95a1; }
     .big { padding: 16px 20px; font-size: 30px; font-weight: 700; } .kv { display: flex; justify-content: space-between; padding: 10px 20px; font-size: 15px; }`);
}

function quotePage(h) {
  return page(`<div class="nm">${h.name}</div><div class="px">${amt(h, h.cur)}</div><div class="chart"></div>
    <div class="kv"><span>시가</span><span>${amt(h, h.avg)}</span></div><div class="kv"><span>거래량</span><span>${krw(int(1000, 9000000))}</span></div>
    <div class="kv"><span>52주 최고</span><span>${amt(h, h.cur * 1.3)}</span></div><div class="btn">구매하기</div>`,
    `.nm { padding: 8px 20px 0; font-size: 15px; color: #6b7684; } .px { padding: 2px 20px; font-size: 28px; font-weight: 700; }
     .chart { margin: 12px 20px; height: 180px; background: #f7f8fa; border-radius: 8px; } .kv { display: flex; justify-content: space-between; padding: 9px 20px; font-size: 15px; }
     .btn { margin: 30px 20px; padding: 16px; text-align: center; background: #3182f6; color: #fff; border-radius: 12px; }`);
}

// ── screens ─────────────────────────────────────────────────────────────
// [file, screen_type, build(pii) → {html, holdings}]
const SCREENS = [
  ["a01_cards_no_avg.png", "holdings", (p) => { const hs = uniq(krStock, 5); return { html: cardsNoAvg(hs, p), holdings: hs }; }],
  ["a02_dark_cards.png", "holdings", (p) => { const hs = uniq(krStock, 5); return { html: darkCards(hs, p), holdings: hs }; }],
  ["a03_two_row_grid.png", "holdings", (p) => { const hs = uniq(krStock, 6); return { html: twoRowGrid(hs, p), holdings: hs }; }],
  ["a04_kv_blocks.png", "holdings", (p) => { const hs = uniq(krStock, 3); return { html: kvBlocks(hs, p), holdings: hs }; }],
  ["a05_us_with_krw.png", "holdings", (p) => { const hs = uniq(usStock, 4); return { html: usWithKrw(hs, p), holdings: hs }; }],
  ["a06_mixed_krw_usd.png", "holdings", (p) => { const hs = [...uniq(krStock, 3), ...uniq(usStock, 3)]; return { html: mixedList(hs, p), holdings: hs }; }],
  ["a07_detail_kr.png", "holdings", () => { const h = krStock(); return { html: detailWithPosition(h), holdings: [h] }; }],
  ["a08_detail_us.png", "holdings", () => { const h = usStock(); return { html: detailWithPosition(h), holdings: [h] }; }],
  // 5 cards fit in 844px only partially: the 5th shows its name line at most.
  ["a09_truncated.png", "holdings", (p) => { const hs = uniq(krStock, 5); return { html: truncatedCards(hs, p), holdings: hs.slice(0, 4), truncated: hs[4] }; }],
  ["a10_dark_cards_us.png", "holdings", (p) => { const hs = uniq(usStock, 5); return { html: darkCards(hs, p), holdings: hs }; }],
  ["b01_fills.png", "fills", (p) => ({ html: fillsList(uniq(krStock, 6), p), holdings: [] })],
  ["b02_order_ticket.png", "order", (p) => ({ html: orderTicket(krStock(), p), holdings: [] })],
  ["b03_watchlist.png", "watchlist", () => ({ html: watchlist([...uniq(krStock, 5), ...uniq(usStock, 3)]), holdings: [] })],
  ["b04_account_summary.png", "account_summary", (p) => ({ html: accountSummary(p), holdings: [] })],
  ["b05_quote_page.png", "quote", () => ({ html: quotePage(krStock()), holdings: [] })],
];

fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const pg = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
const truth = {};
for (const [file, type, build] of SCREENS) {
  const pii = [];
  const { html, holdings, truncated } = build(pii);
  await pg.setContent(`<!doctype html><html lang="ko"><head><meta charset="utf-8"></head><body>${html}</body></html>`);
  await pg.screenshot({ path: path.join(outDir, file), clip: { x: 0, y: 0, width: 390, height: 844 } });
  truth[file] = {
    screen_type: type,
    holdings: holdings.map((h) => ({ name: h.name, ticker: h.ticker ?? h.code, shares: h.shares, avg_cost: h.avg, currency: h.currency })),
    ...(truncated ? { truncated: { name: truncated.name, ticker: truncated.ticker ?? truncated.code } } : {}),
    pii,
  };
  console.log(file);
}
await browser.close();
fs.writeFileSync(path.join(outDir, "ground_truth.json"), JSON.stringify(truth, null, 2) + "\n");
