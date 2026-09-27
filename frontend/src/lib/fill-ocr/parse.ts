/**
 * Fill-screen OCR words → trade rows, by rules only (no model).
 *
 * docs/product/SCREENSHOT_IMPORT_DESIGN.md §5. Input is what `ocr.ts` (the
 * browser, Tesseract.js) returns: words with boxes, a confidence and — for
 * every word containing a digit — `alt`, a second digits-only reading of the
 * same box. The rule this file lives by:
 *
 *   A cell is filled ONLY when the screen proves it. Otherwise it is left
 *   empty (`value: null`) with the OCR reading as a hint, and the user types
 *   it. Guessing is never the fallback.
 *
 * "Proves" means: a number's two readings agree, or exactly one combination
 * of the candidate readings satisfies quantity × price = amount; a side is
 * written as a word (매수/매도/구매/판매/Buy/Sell — colour alone is not read);
 * a date is printed on the row or in a section header with a known year.
 *
 * Pure and synchronous so it can be evaluated offline against OCR dumps
 * (__tests__/eval.test.ts).
 */

export interface OcrWord {
  /** Text as read by the page pass (kor+eng). */
  t: string;
  /** Tesseract confidence 0–100. */
  c: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  /** Digits-only re-read of the same box (only for words containing a digit). */
  alt?: string | null;
}

export type ScreenType = "fills" | "holdings" | "orders" | "other";
export type Side = "BUY" | "SELL";

export interface Cell<T> {
  value: T | null;
  /** What was read when the value could not be proven — shown as a hint only. */
  hint?: string;
}

export interface ParsedFill {
  date: Cell<string>; // YYYY-MM-DD
  time: Cell<string>; // HH:MM[:SS], wall clock of `tz`
  tz: "KST" | "ET" | null;
  name: Cell<string>;
  code: Cell<string>; // 6-digit KRX code or US ticker, as printed
  side: Cell<Side>;
  shares: Cell<number>;
  price: Cell<number>;
  amount: Cell<number>;
  currency: "KRW" | "USD" | null;
  /** amount_mismatch · cross_checked · partial */
  flags: string[];
  sourceText: string;
}

export interface ExcludedRow {
  text: string;
  reason: "unfilled" | "cancelled" | "partial";
}

export interface ScreenParse {
  screenType: ScreenType;
  rows: ParsedFill[];
  excluded: ExcludedRow[];
}

// ── lines ──────────────────────────────────────────────────────────────

interface Line {
  words: OcrWord[];
  y: number;
  h: number;
  compact: string; // text with every space removed
  text: string;
}

function median(xs: number[]): number {
  if (xs.length === 0) return 0;
  const s = [...xs].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)];
}

export function groupLines(words: OcrWord[]): Line[] {
  const ws = words.filter((w) => w.t && w.t.trim());
  const hMed = median(ws.map((w) => w.y1 - w.y0)) || 10;
  const sorted = [...ws].sort((a, b) => (a.y0 + a.y1) / 2 - (b.y0 + b.y1) / 2);
  const lines: { cy: number; words: OcrWord[] }[] = [];
  for (const w of sorted) {
    const cy = (w.y0 + w.y1) / 2;
    const hit = lines.find((l) => Math.abs(l.cy - cy) < Math.max(4, hMed * 0.55));
    if (hit) {
      hit.words.push(w);
      hit.cy = (hit.cy * (hit.words.length - 1) + cy) / hit.words.length;
    } else lines.push({ cy, words: [w] });
  }
  return lines
    .map((l) => {
      const words = l.words.sort((a, b) => a.x0 - b.x0);
      const text = words.map((w) => w.t).join(" ");
      return {
        words,
        y: l.cy,
        h: median(words.map((w) => w.y1 - w.y0)),
        text,
        compact: text.replace(/\s+/g, ""),
      };
    })
    .sort((a, b) => a.y - b.y);
}

// ── screen type ────────────────────────────────────────────────────────

const FILL_KW = ["체결내역", "거래내역", "체결일자", "체결단가", "체결수량", "체결금액", "체결가", "구매완료", "판매완료", "주문체결"];
// "잔고" / "현재가" are left out on purpose: they are bottom-tab labels on
// most broker apps and show up on fill screens too.
const HOLD_KW = ["보유종목", "보유주식", "평가금액", "평가손익", "평균단가", "매입가", "평균", "수익률"];
const ORDER_KW = ["주문유형", "지정가", "시장가", "호가", "주문가능", "주문수량", "주문금액", "매수하기", "매도하기", "정정"];

function countKw(compact: string, kws: string[]): number {
  return kws.reduce((n, k) => n + (compact.includes(k) ? 1 : 0), 0);
}

export function classifyScreen(lines: Line[]): ScreenType {
  const all = lines.map((l) => l.compact).join("|");
  let fills = countKw(all, FILL_KW);
  if (all.includes("거래") && all.includes("내역")) fills += 1;
  // Fill-shaped detail lines: "체결 10주", "10주 구매", "12.5주 x $13.42".
  const detail = lines.filter((l) =>
    /체결\d[\d.,]*주|\d[\d.,]*주(구매|판매|매수|매도)|\d주?x\$\d/.test(l.compact)).length;
  fills += Math.min(3, detail);
  const holds = countKw(all, HOLD_KW);
  const orders = countKw(all, ORDER_KW);
  if (holds >= 2 && holds > fills) return "holdings";
  if (orders >= 2 && fills < 2) return "orders";
  if (fills >= 1) return "fills";
  return "other";
}

// ── numbers: two readings must agree ───────────────────────────────────

const digitsOf = (s: string) => s.replace(/[^\d]/g, "");

/** Parse one printed number. Rejects malformed thousands grouping ("1448,000"). */
export function parseAmount(raw: string): number | null {
  let s = raw.replace(/[원₩$\s]/g, "").replace(/^[~≈]/, "");
  s = s.replace(/[)(%]+$/, "");
  if (!/^\d[\d,]*(\.\d+)?$/.test(s)) return null;
  const [intPart, frac] = s.split(".");
  if (intPart.includes(",") && !/^\d{1,3}(,\d{3})+$/.test(intPart)) return null;
  const v = Number(intPart.replace(/,/g, "") + (frac !== undefined ? `.${frac}` : ""));
  return Number.isFinite(v) ? v : null;
}

interface NumRead {
  /** Proven value (both readings agree) or null. */
  value: number | null;
  /** Every distinct parseable reading — used by the cross-check. */
  candidates: number[];
  hint: string;
}

function readNumber(w: OcrWord): NumRead {
  const primary = parseAmount(w.t);
  const altRaw = (w.alt ?? "").trim();
  const alt = altRaw ? parseAmount(altRaw) : null;
  const candidates = [...new Set([primary, alt].filter((v): v is number => v !== null))];
  const agree =
    primary !== null &&
    alt !== null &&
    digitsOf(w.t) === digitsOf(altRaw) &&
    primary === alt;
  return { value: agree ? primary : null, candidates, hint: w.t };
}

// ── side / status / dates ─────────────────────────────────────────────

const BUY_WORDS = ["매수", "구매", "Buy", "Bought", "BUY"];
const SELL_WORDS = ["매도", "판매", "Sell", "Sold", "SELL"];

export function sideFromText(compact: string): Side | null {
  const buy = BUY_WORDS.some((k) => compact.includes(k));
  const sell = SELL_WORDS.some((k) => compact.includes(k));
  if (buy === sell) return null; // none, or both → not provable
  return buy ? "BUY" : "SELL";
}

const pad2 = (n: number) => String(n).padStart(2, "0");

function validYmd(y: number, m: number, d: number): string | null {
  if (y < 1990 || y > 2100 || m < 1 || m > 12 || d < 1 || d > 31) return null;
  const dt = new Date(Date.UTC(y, m - 1, d));
  if (dt.getUTCMonth() !== m - 1) return null;
  return `${y}-${pad2(m)}-${pad2(d)}`;
}

/** Full date in a word/line, with both readings agreeing when a word is given. */
function fullDate(text: string): string | null {
  const m = text.match(/(20\d{2})[./-](\d{1,2})[./-](\d{1,2})/);
  return m ? validYmd(+m[1], +m[2], +m[3]) : null;
}

function monthDay(compact: string): [number, number] | null {
  const m = compact.match(/(\d{1,2})월(\d{1,2})일/);
  return m ? [+m[1], +m[2]] : null;
}

const TIME_RE = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/;

function readTime(w: OcrWord): Cell<string> {
  const m = w.t.match(TIME_RE);
  if (!m) return { value: null };
  const [hh, mm, ss] = [+m[1], +m[2], m[3] !== undefined ? +m[3] : null];
  const ok =
    m[1].length === 2 && hh < 24 && mm < 60 && (ss === null || ss < 60) &&
    w.alt != null && digitsOf(w.alt) === digitsOf(w.t);
  return ok ? { value: w.t } : { value: null, hint: w.t };
}

const isNumericWord = (t: string) => /^[~≈]?[$₩]?\d[\d,.]*(원|%|\))?$/.test(t);
const isCode = (t: string) => /^\d{6}$/.test(t);
const STATUS_WORDS = ["체결", "완료", "구매완료", "판매완료", "원", "주", "주당", "당", "단가", "체결가", "금액", "체결금액"];

// ── cross-check ────────────────────────────────────────────────────────

function close(a: number, b: number, usd: boolean): boolean {
  const tol = usd ? Math.max(0.011, b * 0.005) : Math.max(1, b * 0.005);
  return Math.abs(a - b) <= tol;
}

function reconcile(
  q: NumRead | null, p: NumRead | null, a: NumRead | null, usd: boolean, flags: string[],
): [Cell<number>, Cell<number>, Cell<number>] {
  const cell = (r: NumRead | null): Cell<number> =>
    r ? { value: r.value, hint: r.value === null ? r.hint : undefined } : { value: null };
  const out: [Cell<number>, Cell<number>, Cell<number>] = [cell(q), cell(p), cell(a)];
  if (!q || !p || !a) return out;
  if (q.value !== null && p.value !== null && a.value !== null) {
    if (close(q.value * p.value, a.value, usd)) return out;
    // Every reading agrees but the printed arithmetic does not: the screen
    // itself is inconsistent — let the user decide which cell is right.
    flags.push("amount_mismatch");
    return [
      { value: null, hint: q.hint }, { value: null, hint: p.hint }, { value: null, hint: a.hint },
    ];
  }
  const combos: [number, number, number][] = [];
  for (const qv of q.candidates) for (const pv of p.candidates) for (const av of a.candidates)
    if (close(qv * pv, av, usd)) combos.push([qv, pv, av]);
  const uniq = new Set(combos.map((c) => c.join("|")));
  if (uniq.size === 1) {
    flags.push("cross_checked");
    const [qv, pv, av] = combos[0];
    return [{ value: qv }, { value: pv }, { value: av }];
  }
  return out;
}

// ── record → fill ──────────────────────────────────────────────────────

interface Ctx {
  year: number | null;
  date: string | null;
}

function nameFrom(words: OcrWord[], usd: boolean): { name: string; code: string | null } {
  let code: string | null = null;
  const parts: string[] = [];
  for (const w of words) {
    const t = w.t.replace(/[[\]|]/g, "");
    if (!t) continue;
    if (isCode(t)) { code = t; continue; }
    if (isNumericWord(t) || /\d/.test(t)) continue;
    if (sideFromText(t) || STATUS_WORDS.includes(t) || /^[·ㆍ,.\-_=~≈:;'"、|]+$/.test(t)) continue;
    if (usd && !code && /^[A-Z]{1,5}$/.test(t)) { code = t; continue; }
    parts.push(t);
  }
  // Korean names come back split per syllable ("삼 성 전 자"): join Hangul runs.
  const joined = parts.reduce((acc, p) => {
    const prevHangul = /[가-힣]$/.test(acc);
    const curHangul = /^[가-힣]/.test(p);
    return acc && !(prevHangul && curHangul) ? `${acc} ${p}` : acc + p;
  }, "");
  return { name: joined.trim(), code };
}

function emptyFill(sourceText: string): ParsedFill {
  return {
    date: { value: null }, time: { value: null }, tz: null, name: { value: null },
    code: { value: null }, side: { value: null }, shares: { value: null },
    price: { value: null }, amount: { value: null }, currency: null, flags: [], sourceText,
  };
}

/** Card / list layouts: name line + detail line ("10주 · 단가 72,400원") + time. */
function cardFill(recLines: Line[], detailIdx: number, ctx: Ctx): ParsedFill {
  const words = recLines.flatMap((l) => l.words);
  const compact = recLines.map((l) => l.compact).join("");
  const text = recLines.map((l) => l.text).join(" / ");
  const f = emptyFill(text);
  const usd = /\$/.test(compact);
  f.currency = usd ? "USD" : /원|₩/.test(compact) ? "KRW" : null;
  f.tz = /\bET\b|미국동부/.test(text + compact) ? "ET" : "KST";

  // quantity / price / amount by neighbouring words
  let q: NumRead | null = null, p: NumRead | null = null, a: NumRead | null = null;
  // Whether the quantity was followed by its own "주" token. Without it the
  // unit glyph may have been swallowed into the number ("12.5주" → "12.53"),
  // so such a quantity is trusted only if the amount cross-check confirms it.
  let qtyHasUnit = false;
  const seq = words;
  for (let i = 0; i < seq.length; i++) {
    const w = seq[i];
    if (!/\d/.test(w.t) || isCode(w.t) || TIME_RE.test(w.t)) continue;
    const prev = seq.slice(Math.max(0, i - 2), i).map((x) => x.t).join("");
    const next = seq[i + 1]?.t ?? "";
    const next2 = seq[i + 2]?.t ?? "";
    const own = w.t;
    if (/^[~≈]/.test(own) || /[~≈]$/.test(prev)) continue; // "≈ 233,424원" conversion
    const isQty =
      (/^주/.test(next) && next !== "주당" && !(next === "주" && next2.startsWith("당"))) ||
      /주$/.test(own) || /^x$/i.test(next);
    if (isQty && !/주문$/.test(prev)) {
      if (!q || /체결$/.test(prev)) {
        q = readNumber({ ...w, t: own.replace(/주$/, "") });
        qtyHasUnit = /^주/.test(next) || /주$/.test(own);
      }
      continue;
    }
    if (/(단가|주당|당|체결가|가|x)$/i.test(prev) || /^x\$/.test(own) || (usd && /x$/i.test(prev))) {
      if (!p) p = readNumber({ ...w, t: own.replace(/^x/, "") });
      continue;
    }
    const onNameLine = detailIdx > 0 && (usd
      ? recLines.slice(0, detailIdx).some((l) => /\$\s*\d/.test(l.text) && l.words.includes(w))
      : recLines[0].words.includes(w));
    if (/금액$/.test(prev) || (onNameLine && (/원$/.test(own) || next.startsWith("원") || (usd && own.startsWith("$"))))) {
      if (!a) a = readNumber(w);
    }
  }
  // US detail line "12.5주 x $13.42": quantity may be followed by x directly
  [f.shares, f.price, f.amount] = reconcile(q, p, a, usd, f.flags);
  const amountConfirmed =
    f.amount.value !== null && f.shares.value !== null && f.price.value !== null && !f.flags.includes("amount_mismatch");
  if (!qtyHasUnit && f.shares.value !== null && !amountConfirmed) {
    f.shares = { value: null, hint: String(f.shares.value) };
  }
  if (!usd && f.shares.value !== null && !Number.isInteger(f.shares.value)) {
    f.shares = { value: null, hint: String(f.shares.value) };
  }

  // US cards stack "TSLL 매수 $167.75" over a fund description ("Direxion
  // Daily TSLA Bull 2X") — only the line carrying the $ amount names the
  // ticker; a symbol inside the description must never be taken for it.
  const before = recLines.slice(0, detailIdx);
  const nameLineObj = usd ? before.find((l) => /\$\s*\d/.test(l.text)) : before[0];
  const nameLine = nameLineObj ? nameLineObj.words : [];
  const nm = nameFrom(nameLine, usd);
  // A code is only read from the name line — a 6-digit price or amount
  // printed without commas ("201000") must never become a stock code.
  const codeWord = nameLine.find((w) => isCode(w.t));
  f.name = nm.name ? { value: nm.name } : { value: null };
  const code = codeWord?.t ?? nm.code;
  if (code) {
    const ok = !isCode(code) || (codeWord?.alt != null && digitsOf(codeWord.alt) === code);
    f.code = ok ? { value: code } : { value: null, hint: code };
  }
  f.side = { value: sideFromText(compact) };
  const tw = words.find((w) => TIME_RE.test(w.t));
  if (tw) f.time = readTime(tw);
  const rowDate = words.map((w) => fullDate(w.t)).find(Boolean) ?? null;
  f.date = { value: rowDate ?? ctx.date };
  return f;
}

// ── tables ─────────────────────────────────────────────────────────────

type Col = "date" | "time" | "name" | "side" | "qty" | "price" | "amount" | "fee" | "tax" | "unknown";
const COL_LABELS: [Col, string[]][] = [
  ["amount", ["체결금액", "거래금액", "금액"]],
  ["price", ["체결단가", "단가", "체결가"]],
  ["qty", ["체결수량", "수량"]],
  ["date", ["체결일자", "거래일자", "일자", "체결일"]],
  ["time", ["체결시간", "시간", "시각"]],
  ["name", ["종목명", "종목"]],
  ["side", ["매매구분", "구분"]],
  ["fee", ["수수료"]],
  ["tax", ["제세금", "세금"]],
];

interface Column { col: Col; cx: number }

function headerColumns(line: Line): Column[] | null {
  const segs: { words: OcrWord[] }[] = [];
  for (const w of line.words) {
    const last = segs[segs.length - 1];
    const prev = last?.words[last.words.length - 1];
    if (prev && w.x0 - prev.x1 < line.h * 0.9) last.words.push(w);
    else segs.push({ words: [w] });
  }
  const cols: Column[] = segs.map((s) => {
    const c = s.words.map((w) => w.t).join("").replace(/[^가-힣A-Za-z]/g, "");
    const hit = COL_LABELS.find(([, ls]) => ls.some((l) => c.includes(l)));
    const cx = (s.words[0].x0 + s.words[s.words.length - 1].x1) / 2;
    return { col: hit ? hit[0] : "unknown", cx };
  });
  const known = new Set(cols.map((c) => c.col).filter((c) => c !== "unknown"));
  if (known.size < 3 || !(known.has("qty") || known.has("price"))) return null;
  // A garbled last header right of the price column is the amount column.
  if (!known.has("amount")) {
    const pi = cols.findIndex((c) => c.col === "price");
    const last = cols[cols.length - 1];
    if (pi >= 0 && last.col === "unknown" && cols.indexOf(last) > pi) last.col = "amount";
  }
  return cols;
}

function tableFills(lines: Line[], hi: number, cols: Column[], ctx: Ctx): ParsedFill[] {
  const body = lines.slice(hi + 1);
  const footer = body.findIndex((l) => /합계|총계/.test(l.compact));
  const rows = footer >= 0 ? body.slice(0, footer) : body;
  const numericCount = (l: Line) =>
    l.words.filter((w) => /\d/.test(w.t) && !isCode(w.t)).length;
  const data = rows.filter((l) => numericCount(l) >= 2);
  const aux = rows.filter((l) => numericCount(l) < 2);
  const pitch = data.length > 1 ? median(data.slice(1).map((l, i) => l.y - data[i].y)) : 40;
  const attached = new Map<Line, Line[]>(data.map((l) => [l, []]));
  for (const l of aux) {
    let best: Line | null = null;
    for (const d of data) if (!best || Math.abs(d.y - l.y) < Math.abs(best.y - l.y)) best = d;
    if (best && Math.abs(best.y - l.y) < pitch * 0.75) attached.get(best)!.push(l);
  }
  const nearestCol = (w: OcrWord): Col => {
    const cx = (w.x0 + w.x1) / 2;
    let best = cols[0];
    for (const c of cols) if (Math.abs(c.cx - cx) < Math.abs(best.cx - cx)) best = c;
    return best.col;
  };
  return data.map((line) => {
    const extra = attached.get(line) ?? [];
    const all = [line, ...extra].sort((a, b) => a.y - b.y);
    const f = emptyFill(all.map((l) => l.text).join(" / "));
    const compact = all.map((l) => l.compact).join("");
    f.currency = /\$/.test(compact) ? "USD" : "KRW";
    f.tz = "KST";
    let q: NumRead | null = null, p: NumRead | null = null, a: NumRead | null = null;
    const nameWords: OcrWord[] = [];
    for (const w of all.flatMap((l) => l.words)) {
      const d = fullDate(w.t);
      if (d) {
        f.date = w.alt != null && digitsOf(w.alt) === digitsOf(w.t) ? { value: d } : { value: null, hint: w.t };
        continue;
      }
      if (TIME_RE.test(w.t)) { f.time = readTime(w); continue; }
      const col = nearestCol(w);
      if (isCode(w.t) && (col === "name" || col === "unknown" || col === "time")) {
        f.code = w.alt != null && digitsOf(w.alt) === w.t ? { value: w.t } : { value: null, hint: w.t };
        continue;
      }
      if (/\d/.test(w.t)) {
        if (col === "qty" && !q) q = readNumber(w);
        else if (col === "price" && !p) p = readNumber(w);
        else if (col === "amount" && !a) a = readNumber(w);
        else if (col === "date" && !f.date.value) f.date = { value: null, hint: w.t };
        continue;
      }
      if (col === "name" || col === "unknown" || col === "time") nameWords.push(w);
    }
    if (!cols.some((c) => c.col === "name")) {
      // name column header missing (multi-line cells): Hangul/Latin words anywhere
      for (const w of all.flatMap((l) => l.words)) if (!nameWords.includes(w) && !/\d/.test(w.t)) nameWords.push(w);
    }
    [f.shares, f.price, f.amount] = reconcile(q, p, a, false, f.flags);
    const nm = nameFrom(nameWords, false);
    f.name = nm.name ? { value: nm.name } : { value: null };
    f.side = { value: sideFromText(compact) };
    if (!f.date.value && !f.date.hint) f.date = { value: ctx.date };
    return f;
  });
}

// ── entry point ────────────────────────────────────────────────────────

function yearContext(lines: Line[]): number | null {
  const years = lines.flatMap((l) => [...l.compact.matchAll(/(20\d{2})(?:년|[./-]\d)/g)].map((m) => +m[1]));
  return years.length ? Math.max(...years) : null;
}

function headerDate(line: Line, ctx: Ctx): string | null {
  const d = fullDate(line.compact);
  if (d) return d;
  const md = monthDay(line.compact);
  if (md && ctx.year) return validYmd(ctx.year, md[0], md[1]);
  return null;
}

// "10주", "체결 10주", "12.5주 x $13.42", "12.5 x $13.42". The x-form must be
// followed by a $ price — ETF names like "Bull 2X" / "3X" are not quantities.
const isDetail = (l: Line) =>
  /\d\s*주/.test(l.text) || /\d\s*[x×]\s*\$\s*\d/i.test(l.text.replace(/,/g, ""));

export function parseFillScreen(words: OcrWord[]): ScreenParse {
  const lines = groupLines(words);
  const screenType = classifyScreen(lines);
  const result: ScreenParse = { screenType, rows: [], excluded: [] };
  if (screenType !== "fills") return result;

  const ctx: Ctx = { year: yearContext(lines), date: null };

  // Table layout?
  const hi = lines.findIndex((l) => headerColumns(l) !== null);
  if (hi >= 0) {
    for (const l of lines.slice(0, hi)) ctx.date = headerDate(l, ctx) ?? ctx.date;
    result.rows = tableFills(lines, hi, headerColumns(lines[hi])!, ctx);
    return result;
  }

  // Card / list layout: records anchored on detail lines ("N주", "N x $P").
  const detailIdx = lines.map((l, i) => (isDetail(l) ? i : -1)).filter((i) => i >= 0);
  const dateAt = new Map<number, string | null>();
  const headerLines = new Set<number>();
  lines.forEach((l, i) => {
    const d = headerDate(l, ctx);
    if (d && !isDetail(l) && !/\d{1,3}(,\d{3})+/.test(l.compact.replace(/20\d{2}/, ""))) {
      headerLines.add(i);
      dateAt.set(i, d);
    }
  });
  const owner = new Map<number, number>(); // line index → detail index
  // Screen titles / filters ("OO증권 체결내역", "국내주식 해외주식") are never a card's name line.
  const isChrome = (l: Line) =>
    /체결내역|거래내역|주문내역|국내주식|해외주식|~/.test(l.compact) || TIME_RE.test(l.words[0]?.t ?? "") && l.y < (lines[0]?.y ?? 0) + 5;
  lines.forEach((l, i) => {
    if (headerLines.has(i) || detailIdx.includes(i) || isChrome(l)) return;
    let best = -1;
    for (const d of detailIdx) {
      // never cross a date header
      const lo = Math.min(i, d), hiI = Math.max(i, d);
      if ([...headerLines].some((h) => h > lo && h < hiI)) continue;
      if (best < 0 || Math.abs(lines[d].y - l.y) < Math.abs(lines[best].y - l.y)) best = d;
    }
    if (best >= 0 && Math.abs(lines[best].y - l.y) < lines[best].h * 6) owner.set(i, best);
  });
  const firstContent = Math.min(...[...headerLines, ...detailIdx, lines.length]);
  for (const d of detailIdx) {
    const before = [...owner.entries()].filter(([i, o]) => o === d && i < d).map(([i]) => i);
    const after = [...owner.entries()].filter(([i, o]) => o === d && i > d).map(([i]) => i);
    const recIdx = [...before, d, ...after].sort((a, b) => a - b);
    const recLines = recIdx.map((i) => lines[i]);
    const compact = recLines.map((l) => l.compact).join("");
    const text = recLines.map((l) => l.text).join(" / ");
    // date context = last header above this record
    let date: string | null = null;
    for (const [i, v] of dateAt) if (i < d) date = v;
    if (/미체결/.test(compact) || /체결0주/.test(compact)) {
      result.excluded.push({ text, reason: "unfilled" });
      continue;
    }
    if (/취소|정정/.test(compact)) {
      result.excluded.push({ text, reason: "cancelled" });
      continue;
    }
    // Cut at the top edge: no name line and nothing above it on screen.
    const noNameLine = before.length === 0;
    const aboveHeaders = [...headerLines].some((h) => h < d);
    if (noNameLine && (!aboveHeaders || d <= firstContent)) {
      result.excluded.push({ text, reason: "partial" });
      continue;
    }
    const fill = cardFill(recLines, recIdx.indexOf(d), { ...ctx, date });
    result.rows.push(fill);
  }
  // A name line after the last detail line (cut at the bottom edge).
  const lastD = detailIdx[detailIdx.length - 1];
  if (lastD !== undefined) {
    const tail = lines.slice(lastD + 1).filter((l, k) => !owner.has(lastD + 1 + k));
    const cut = tail.find((l) => /\d{1,3}(,\d{3})+\s*원/.test(l.text) || isCode(l.compact.slice(-6)));
    if (cut) result.excluded.push({ text: cut.text, reason: "partial" });
  }
  return result;
}
