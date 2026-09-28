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
  /** Further digit readings (other crops) when they disagreed — candidates
   * only, never a proof on their own. */
  alts?: string[];
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

export interface Line {
  words: OcrWord[];
  y: number;
  h: number;
  compact: string; // text with every space removed
  text: string;
}

export function median(xs: number[]): number {
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
// 잔고수량 / 매입금액 / 계좌잔고 / 주식잔고 / 평단 name balance screens that avoid the
// words above (heldout n1: 계좌잔고 · 잔고수량 · 매입금액 · 현재가 · 손익).
const HOLD_KW = ["보유종목", "보유주식", "평가금액", "평가손익", "평균단가", "매입가", "평균", "수익률",
  "잔고수량", "보유수량", "매입금액", "계좌잔고", "주식잔고", "평단"];
const ORDER_KW = ["주문유형", "지정가", "시장가", "호가", "주문가능", "주문수량", "주문금액", "매수하기", "매도하기", "정정"];

function countKw(compact: string, kws: string[]): number {
  return kws.reduce((n, k) => n + (compact.includes(k) ? 1 : 0), 0);
}

/** Toss 내 투자 second line: "…-982,051(53.3%)" — signed P/L then its rate. */
export const tossPlLine = (compact: string) =>
  /[+\-−]\$?\d[\d,.]*원?\(\d+(\.\d+)?%\)$/.test(compact) && !/^[+\-−]/.test(compact);

export function classifyScreen(lines: Line[]): ScreenType {
  const all = lines.map((l) => l.compact).join("|");
  let fills = countKw(all, FILL_KW);
  if (all.includes("거래") && all.includes("내역")) fills += 1;
  // Fill-shaped detail lines: "체결 10주", "10주 구매", "12.5주 x $13.42".
  const detail = lines.filter((l) =>
    /체결\d[\d.,]*주|\d[\d.,]*주(구매|판매|매수|매도)|\d주?x\$\d/.test(l.compact)).length;
  fills += Math.min(3, detail);
  let holds = countKw(all, HOLD_KW);
  // Toss 내 투자 prints no label at all: "이름 859,449원" over "29주 -982,051 (53.3%)".
  // Two lines ending in a signed P/L and its rate are a holdings list — the
  // 주 glyph itself is often misread ("110%", "(JES"), so it is not required.
  if (lines.filter((l) => tossPlLine(l.compact)).length >= 2) holds += 2;
  // Toss 자세히 보기 table header: "종목명 · 1주 평균 금액 · 총 금액".
  if (lines.some((l) => /평균금액/.test(l.compact) && /총금액/.test(l.compact))) holds += 2;
  // "39주 · 평단 87,880원" summary lines (no other holdings word on screen).
  if (lines.filter((l) => /\d주.{0,4}(평단|평균|매입가)/.test(l.compact)).length >= 2) holds += 2;
  const orders = countKw(all, ORDER_KW);
  if (holds >= 2 && holds > fills) return "holdings";
  if (orders >= 2 && fills < 2) return "orders";
  if (fills >= 1) return "fills";
  return "other";
}

// ── numbers: two readings must agree ───────────────────────────────────

export const digitsOf = (s: string) => s.replace(/[^\d]/g, "");

/** Parse one printed number. Rejects malformed thousands grouping ("1448,000"). */
export function parseAmount(raw: string): number | null {
  // "%" is never part of a price or quantity here — it is how OCR misreads
  // the "주" glyph ("8%" for 8주), so such a token proves nothing.
  if (raw.includes("%")) return null;
  let s = raw.replace(/[원₩$\s]/g, "").replace(/^[~≈]/, "");
  s = s.replace(/[)(]+$/, "");
  if (!/^\d[\d,]*(\.\d+)?$/.test(s)) return null;
  const [intPart, frac] = s.split(".");
  if (intPart.includes(",") && !/^\d{1,3}(,\d{3})+$/.test(intPart)) return null;
  const v = Number(intPart.replace(/,/g, "") + (frac !== undefined ? `.${frac}` : ""));
  return Number.isFinite(v) ? v : null;
}

export interface NumRead {
  /** Proven value (both readings agree) or null. */
  value: number | null;
  /** Every distinct parseable reading — used by the cross-check. */
  candidates: number[];
  hint: string;
}

export function readNumber(w: OcrWord): NumRead {
  const primary = parseAmount(w.t);
  const altRaw = (w.alt ?? "").trim();
  const alt = altRaw ? parseAmount(altRaw) : null;
  const more = (w.alts ?? []).map((a) => parseAmount(a.trim()));
  const candidates = [...new Set([primary, alt, ...more].filter((v): v is number => v !== null))];
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

export const TIME_RE = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/;

function readTime(w: OcrWord): Cell<string> {
  const m = w.t.match(TIME_RE);
  if (!m) return { value: null };
  const [hh, mm, ss] = [+m[1], +m[2], m[3] !== undefined ? +m[3] : null];
  const ok =
    m[1].length === 2 && hh < 24 && mm < 60 && (ss === null || ss < 60) &&
    w.alt != null && digitsOf(w.alt) === digitsOf(w.t);
  return ok ? { value: w.t } : { value: null, hint: w.t };
}

export const isNumericWord = (t: string) => /^[~≈]?[$₩]?\d[\d,.]*(원|%|\))?$/.test(t);
export const isCode = (t: string) => /^\d{6}$/.test(t);
const STATUS_WORDS = ["체결", "완료", "구매완료", "판매완료", "원", "주", "주당", "당", "단가", "체결가", "금액", "체결금액"];

// ── cross-check ────────────────────────────────────────────────────────

export function close(a: number, b: number, usd: boolean): boolean {
  const tol = usd ? Math.max(0.011, b * 0.005) : Math.max(1, b * 0.005);
  return Math.abs(a - b) <= tol;
}

function reconcile(
  q: NumRead | null, p: NumRead | null, a: NumRead | null, usd: boolean, flags: string[],
): [Cell<number>, Cell<number>, Cell<number>] {
  const cell = (r: NumRead | null): Cell<number> =>
    r ? { value: r.value, hint: r.value === null ? r.hint : undefined } : { value: null };
  const out: [Cell<number>, Cell<number>, Cell<number>] = [cell(q), cell(p), cell(a)];
  const blankAll = (): [Cell<number>, Cell<number>, Cell<number>] => [
    { value: null, hint: q?.hint }, { value: null, hint: p?.hint }, { value: null, hint: a?.hint },
  ];
  // Plausibility when nothing else can check the pair (no amount on screen).
  if (!usd && out[1].value !== null && out[1].value < 100) out[1] = { value: null, hint: p?.hint };
  if (out[0].value !== null && out[0].value > 1e6) out[0] = { value: null, hint: q?.hint };
  if (!q || !p || !a) return out;
  // HARD gate: an amount is on screen, so quantity × price must match one of
  // its readings. If no reading does, the three cells may belong to
  // different trades (misaligned rows / columns) — prove nothing.
  if (a.candidates.length > 0 && out[0].value !== null && out[1].value !== null &&
      !a.candidates.some((av) => close(out[0].value! * out[1].value!, av, usd))) {
    const combosAny = q.candidates.some((qv) => p.candidates.some((pv) =>
      a.candidates.some((av) => close(qv * pv, av, usd))));
    if (!combosAny) {
      flags.push("amount_mismatch");
      return blankAll();
    }
  }
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
  /** Month-only headers span December and January: which year each belongs
   * to is not printed, so month-day headers are not dated at all. */
  yearAmbiguous?: boolean;
  date: string | null;
}

/** A 1–2 digit token between Hangul words is part of the name — "현대차 3 우 B"
 * is 현대차3우B; dropping it would turn the name into another listed stock
 * (현대차 / 현대차우). */
export const nameDigitAt = (ws: OcrWord[], i: number) =>
  /^\d{1,2}$/.test(ws[i].t) && i > 0 && /[가-힣]$/.test(ws[i - 1].t) && /^[가-힣]/.test(ws[i + 1]?.t ?? "");

export function nameFrom(words: OcrWord[], usd: boolean): { name: string; code: string | null } {
  let code: string | null = null;
  const parts: string[] = [];
  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    const t = w.t.replace(/[[\]|]/g, "");
    if (!t) continue;
    if (isCode(t)) { code = t; continue; }
    if (nameDigitAt(words, i)) { parts.push(t); continue; }
    if (isNumericWord(t) || /\d/.test(t)) continue;
    if (sideFromText(t) || STATUS_WORDS.includes(t) || /^[·ㆍ,.\-_=~≈:;'"、|x×*]+$/.test(t)) continue;
    if (usd && !code && /^[A-Z]{1,5}$/.test(t)) { code = t; continue; }
    parts.push(t);
  }
  // Korean names come back split per syllable ("삼 성 전 자"): join Hangul runs.
  const joined = parts.reduce((acc, p) => {
    const prevHangul = /[가-힣\d]$/.test(acc);
    const curHangul = /^[가-힣\d]/.test(p);
    return acc && !(prevHangul && curHangul) ? `${acc} ${p}` : acc + p;
  }, "");
  // A date header split into tokens ("2026 년 9 월 22 일 (화)") leaves only
  // date words once the digits are dropped — that is not a stock name.
  const name = joined.trim();
  const dateOnly = /^[\s()（）]*((년|월|일|[월화수목금토일]요일|\(?[월화수목금토일]\)?)[\s()（）]*)+$/.test(name);
  return { name: dateOnly ? "" : name, code };
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
      /주$/.test(own) || /^[x×]$/i.test(next);
    if (isQty && !/주문$/.test(prev)) {
      if (!q || /체결$/.test(prev)) {
        q = readNumber({ ...w, t: own.replace(/주$/, "") });
        qtyHasUnit = /^주/.test(next) || /주$/.test(own);
      }
      continue;
    }
    // "x" / "×" (quantity × price) counts only as a word of its own — "AMEX"
    // ends in x too, and the amount after it is not a price.
    const times = /^[x×]$/i.test(seq[i - 1]?.t ?? "");
    if (/(단가|주당|당|체결가|가)$/.test(prev) || times || /^[x×]\$/.test(own)) {
      if (!p) p = readNumber({ ...w, t: own.replace(/^[x×]/, "") });
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
  // No separate name line → the anchor itself names the stock
  // ("하나금융지주 매수 5주 x 68,900").
  const anchorLine = recLines[detailIdx];
  const anchorAsName = before.length === 0 && anchorLeadName(anchorLine);
  const nameLineObj = usd
    ? before.find((l) => /\$\s*\d/.test(l.text)) ?? (anchorAsName ? anchorLine : undefined)
    : before[0] ?? (anchorAsName ? anchorLine : undefined);
  // From the anchor line only the words before its first number are the name.
  const nameLine = !nameLineObj
    ? []
    : nameLineObj === anchorLine
      ? anchorLine.words.slice(0, Math.max(0, anchorLine.words.findIndex((w) => /\d/.test(w.t))))
      : nameLineObj.words;
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
  const rowDates = new Set(words.map((w) => fullDate(w.t)).filter(Boolean));
  const rowDate = [...rowDates][0] ?? null;
  f.date = { value: rowDate ?? ctx.date };

  // Merged-record guard: two clocks, two dates, or amounts on two lines mean
  // this record swallowed a neighbouring trade's line. Keep only what the
  // anchor (detail) line itself proves; everything else goes back to the user.
  const times = new Set(words.filter((w) => TIME_RE.test(w.t)).map((w) => w.t));
  // (the anchor line itself may carry a per-share price in 원 — not counted)
  const amountLines = recLines.filter((l, k) =>
    k !== detailIdx && /\d{1,3}(,\d{3})+\s*(원|₩)|\$\s*\d/.test(l.text)).length;
  if (times.size > 1 || rowDates.size > 1 || amountLines > 1) {
    f.flags.push("merged_record");
    const anchor = recLines[detailIdx];
    f.time = { value: null, hint: f.time.value ?? f.time.hint };
    if (rowDates.size > 1) f.date = { value: null };
    f.amount = { value: null, hint: f.amount.value != null ? String(f.amount.value) : f.amount.hint };
    const anchorSide = sideFromText(anchor.compact);
    f.side = { value: anchorSide };
    if (!anchor.words.some((w) => nameLine.includes(w))) f.name = { value: null, hint: f.name.value ?? undefined };
    if (!anchor.words.some((w) => w === codeWord)) f.code = { value: null, hint: f.code.value ?? f.code.hint };
  }
  return f;
}

// ── tables ─────────────────────────────────────────────────────────────

type Col = "date" | "time" | "name" | "side" | "qty" | "price" | "amount" | "fee" | "tax" | "ignore" | "unknown";
const COL_LABELS: [Col, string[]][] = [
  // Order / fill / account numbers are 6+ digit ids that look like stock
  // codes — recognised only so they are never read as anything.
  ["ignore", ["원주문번호", "주문번호", "체결번호", "접수번호", "계좌번호"]],
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

/** A header line split into labels: words closer than ~one glyph belong to
 * the same label ("보 유 수량" → 보유수량). `text` keeps letters only. */
export function headerSegments(line: Line): { text: string; cx: number }[] {
  const segs: { words: OcrWord[] }[] = [];
  for (const w of line.words) {
    const last = segs[segs.length - 1];
    const prev = last?.words[last.words.length - 1];
    if (prev && w.x0 - prev.x1 < line.h * 0.9) last.words.push(w);
    else segs.push({ words: [w] });
  }
  return segs.map((s) => ({
    text: s.words.map((w) => w.t).join("").replace(/[^가-힣A-Za-z]/g, ""),
    cx: (s.words[0].x0 + s.words[s.words.length - 1].x1) / 2,
  }));
}

function headerColumns(line: Line): Column[] | null {
  const cols: Column[] = headerSegments(line).map(({ text: c, cx }) => {
    const hit = COL_LABELS.find(([, ls]) => ls.some((l) => c.includes(l)));
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
  // Dates, times and codes do not make a line a trade row ("09.22 14:21:07"
  // printed under each name is a detail of the row above, not a row).
  const numericCount = (l: Line) =>
    l.words.filter((w) => /\d/.test(w.t) && !isCode(w.t) && !TIME_RE.test(w.t) &&
      !fullDate(w.t) && !/^\d{1,2}[./]\d{1,2}$/.test(w.t)).length;
  const data = rows.filter((l) => numericCount(l) >= 2);
  const aux = rows.filter((l) => numericCount(l) < 2);
  const pitch = data.length > 1 ? median(data.slice(1).map((l, i) => l.y - data[i].y)) : 40;
  const attached = new Map<Line, Line[]>(data.map((l) => [l, []]));
  for (const l of aux) {
    const byDist = [...data].sort((x, y) => Math.abs(x.y - l.y) - Math.abs(y.y - l.y));
    const [best, second] = byDist;
    if (!best || Math.abs(best.y - l.y) >= pitch * 0.75) continue;
    // Roughly between two rows → it could belong to either; attach to none.
    if (second && Math.abs(second.y - l.y) < Math.abs(best.y - l.y) * 1.5) continue;
    attached.get(best)!.push(l);
  }
  const NUMERIC_COLS: Col[] = ["qty", "price", "amount", "fee", "tax"];
  const nearestCol = (w: OcrWord): Col => {
    const cx = (w.x0 + w.x1) / 2;
    const byDist = [...cols].sort((x, y) => Math.abs(x.cx - cx) - Math.abs(y.cx - cx));
    const [best, second] = byDist;
    // A number about as close to two numeric columns is not assigned to either.
    if (/\d/.test(w.t) && second && NUMERIC_COLS.includes(best.col) && NUMERIC_COLS.includes(second.col) &&
        Math.abs(second.cx - cx) < Math.abs(best.cx - cx) * 1.3) return "unknown";
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
    const codeWords: { w: OcrWord; col: Col }[] = [];
    for (const w of all.flatMap((l) => l.words)) {
      const d = fullDate(w.t);
      if (d) {
        f.date = w.alt != null && digitsOf(w.alt) === digitsOf(w.t) ? { value: d } : { value: null, hint: w.t };
        continue;
      }
      if (TIME_RE.test(w.t)) { f.time = readTime(w); continue; }
      const col = nearestCol(w);
      if (col === "ignore") continue;
      if (isCode(w.t) && col !== "qty" && col !== "price" && col !== "amount" && col !== "fee" && col !== "tax") {
        // Decided after the name words are known: a code must sit in the
        // name column or right under / beside the name — never in an
        // arbitrary column (체결번호 000240 is also a real listing).
        // (A 6-digit number in a numeric column is a price/amount.)
        codeWords.push({ w, col });
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
    const hangulName = nameWords.filter((w) => /[가-힣A-Za-z]/.test(w.t));
    const nearName = (w: OcrWord) => hangulName.some((n) => {
      const gapX = Math.max(0, Math.max(n.x0, w.x0) - Math.min(n.x1, w.x1));
      const gapY = Math.abs((n.y0 + n.y1) / 2 - (w.y0 + w.y1) / 2);
      return gapX <= (n.y1 - n.y0) * 1.5 && gapY <= (n.y1 - n.y0) * 2.2;
    });
    const code = codeWords.find(({ w, col }) => col === "name" || nearName(w));
    if (code) {
      f.code = code.w.alt != null && digitsOf(code.w.alt) === code.w.t
        ? { value: code.w.t } : { value: null, hint: code.w.t };
    }
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
  const ymd = line.compact.match(/(20\d{2})년(\d{1,2})월(\d{1,2})일/);
  if (ymd) return validYmd(+ymd[1], +ymd[2], +ymd[3]);
  const md = monthDay(line.compact);
  if (md && ctx.year && !ctx.yearAmbiguous) return validYmd(ctx.year, md[0], md[1]);
  return null;
}

// "10주", "체결 10주", "12.5주 x $13.42", "5 x 68,900". The x-form is a
// lowercase x / × / * followed by a price — ETF names like "Bull 2X" / "3X"
// (uppercase X) are not quantities.
const isDetail = (l: Line) =>
  /\d\s*주/.test(l.text) || /\d\s*[x×*]\s*\$?\s*\d/.test(l.text.replace(/,/g, ""));

/** Does the anchor line itself start with a stock name ("하나금융지주 매수
 * 5주 x 68,900")? Only words before the first number count — trailing OCR
 * debris ("… 42,050원 제설") is not a name. */
function anchorLeadName(l: Line): boolean {
  const firstNum = l.words.findIndex((w) => /\d/.test(w.t));
  const lead = firstNum < 0 ? l.words : l.words.slice(0, firstNum);
  const nm = nameFrom(lead, /\$/.test(l.compact));
  return Boolean(nm.name || nm.code);
}

/** A row with neither a quantity nor a price reading is not a trade row (a
 * stray date/time line, a footer) — never emit it. A missing name is fine:
 * the user fills it. */
function hasTradeShape(f: ParsedFill): boolean {
  const has = (c: Cell<unknown>) => c.value !== null || Boolean(c.hint);
  return has(f.shares) || has(f.price);
}

export function parseFillScreen(words: OcrWord[]): ScreenParse {
  const lines = groupLines(words);
  const screenType = classifyScreen(lines);
  const result: ScreenParse = { screenType, rows: [], excluded: [] };
  if (screenType !== "fills") return result;

  // Every month-day header counts, with or without its own year: a year-less
  // "1월 2일" next to "2026년 12월 30일" is 2027 (or unknowable) — never the
  // header's year. Headers that print their year are still dated (headerDate).
  const months = new Set(lines.map((l) => monthDay(l.compact)?.[0]).filter((m) => m !== undefined));
  const ctx: Ctx = { year: yearContext(lines), yearAmbiguous: months.has(12) && months.has(1), date: null };

  // Table layout?
  const hi = lines.findIndex((l) => headerColumns(l) !== null);
  if (hi >= 0) {
    for (const l of lines.slice(0, hi)) ctx.date = headerDate(l, ctx) ?? ctx.date;
    result.rows = tableFills(lines, hi, headerColumns(lines[hi])!, ctx).filter(hasTradeShape);
    return result;
  }

  // Card / list layout: records anchored on detail lines ("N주", "N x $P").
  const detailIdx = lines.map((l, i) => (isDetail(l) ? i : -1)).filter((i) => i >= 0);
  const dateAt = new Map<number, string | null>();
  const headerLines = new Set<number>();
  // A section date header carries only the date (+ weekday / notes in
  // parentheses). A line that also has a time or an amount is a trade's own
  // "date time amount" line — using it as a header would date the next trade.
  const onlyDate = (l: Line) => {
    const rest = l.compact
      .replace(/(20\d{2})[./-]\d{1,2}[./-]\d{1,2}/, "")
      .replace(/(20\d{2}년)?\d{1,2}월\d{1,2}일/, "")
      .replace(/\([^)]*\)?/g, "");
    return !/\d/.test(rest);
  };
  lines.forEach((l, i) => {
    const d = headerDate(l, ctx);
    if (d && !isDetail(l) && onlyDate(l)) {
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
    if (best < 0 || Math.abs(lines[best].y - l.y) >= lines[best].h * 6) return;
    // Between two trade lines at similar distance → belongs to neither.
    const others = detailIdx.filter((d) => d !== best &&
      ![...headerLines].some((h) => h > Math.min(i, d) && h < Math.max(i, d)));
    const second = others.reduce((m, d) => Math.min(m, Math.abs(lines[d].y - l.y)), Infinity);
    if (second < Math.abs(lines[best].y - l.y) * 1.25) return;
    owner.set(i, best);
  });
  // Layout orientation: when almost every trade keeps its extra lines on one
  // side of its anchor (e.g. "name 5주 x 68,900" over "date time amount"), a
  // line on the other side belongs to a neighbouring trade whose anchor was
  // not recognised — attaching it would give this trade that one's values.
  if (detailIdx.length >= 3) {
    const withAbove = new Set([...owner.entries()].filter(([i, d]) => i < d).map(([, d]) => d)).size;
    const withBelow = new Set([...owner.entries()].filter(([i, d]) => i > d).map(([, d]) => d)).size;
    const n = detailIdx.length;
    for (const [i, d] of [...owner.entries()]) {
      if (i < d && withAbove <= n * 0.3 && withBelow > n * 0.5) owner.delete(i);
      else if (i > d && withBelow <= n * 0.3 && withAbove > n * 0.5) owner.delete(i);
    }
  }
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
    // Cut at the top edge: only the first record on screen can be, and only
    // if neither a line above nor its own anchor line names a stock.
    const noNameLine = before.length === 0;
    const aboveHeaders = [...headerLines].some((h) => h < d);
    const anchorNamed = anchorLeadName(lines[d]);
    if (noNameLine && !anchorNamed && d === detailIdx[0] && (!aboveHeaders || d <= firstContent)) {
      result.excluded.push({ text, reason: "partial" });
      continue;
    }
    const fill = cardFill(recLines, recIdx.indexOf(d), { ...ctx, date });
    if (hasTradeShape(fill)) result.rows.push(fill);
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
