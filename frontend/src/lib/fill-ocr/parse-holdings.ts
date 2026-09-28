/**
 * Holdings-screen (보유종목 / 잔고) OCR words → positions, by rules only.
 *
 * docs/product/HOLDINGS_IMPORT_DESIGN.md. Same input and the same rule as the
 * fill parser (parse.ts):
 *
 *   A cell is filled ONLY when the screen proves it. Otherwise it is left
 *   empty (`value: null`) with the OCR reading as a hint, and the user types
 *   it. Guessing is never the fallback.
 *
 * What a holdings screen adds is a second price that is NOT the cost basis:
 * 현재가 (current price) sits right next to 평균단가 (average cost). Putting
 * the current price into the average-cost cell is the main way this parser
 * could be confidently wrong, so a number becomes the average cost only when
 *   - it carries its own label (평균 / 평균단가 / 평단 / 매입가 …) — cards and
 *     key-value lists — or sits under such a column header (tables), and
 *   - both OCR readings agree, or exactly one reading combination satisfies
 *     shares × avg ≈ 매입금액 (±0.5%), where 매입금액 is printed, or is
 *     평가금액 − 평가손익 when both are printed.
 * Unlabelled numbers are never an average cost. 현재가 / 평가금액 / 수익률 are
 * read only as evidence for the check above and never leave this file.
 *
 * Pure and synchronous (evaluated offline: __tests__/holdings-eval.test.ts).
 */
import {
  classifyScreen, close, digitsOf, groupLines, headerSegments, isCode, median,
  nameDigitAt, nameFrom, parseAmount, readNumber, tossPlLine,
  type Cell, type Line, type NumRead, type OcrWord, type ScreenType,
} from "./parse";

export interface ParsedHolding {
  name: Cell<string>;
  /** 6-digit KRX code or US ticker, as printed (same proven-only rules as fills). */
  code: Cell<string>;
  shares: Cell<number>;
  avgCost: Cell<number>;
  currency: "KRW" | "USD" | null;
  /** cross_checked · derived_avg · derived_shares · amount_mismatch · merged_record · foreign_in_krw */
  flags: string[];
  sourceText: string;
}

export interface HoldingsParse {
  screenType: ScreenType;
  rows: ParsedHolding[];
}

// ── labels ──────────────────────────────────────────────────────────────

type Field = "qty" | "avg" | "cost" | "value" | "pl" | "cur" | "rate" | "name" | "ignore" | "unknown";

// Order matters: the first list whose label the text contains wins, so the
// longer / more specific labels come first (평가손익 before 평가, 매입금액
// before 매입가).
const LABELS: [Field, string[]][] = [
  ["ignore", ["계좌번호", "주문번호", "매도가능", "주문가능", "대출"]],
  ["pl", ["평가손익", "손익"]],
  ["rate", ["수익률", "손익률"]],
  ["cost", ["매입금액", "매입액", "매입총액", "투자원금", "원금"]],
  ["avg", ["평균단가", "평균매입가", "매수평균가", "평균가", "평단가", "평단", "매입단가", "매입가", "평균"]],
  ["value", ["평가금액", "평가액", "평가"]],
  ["cur", ["현재가", "현재", "시세"]],
  ["qty", ["보유수량", "잔고수량", "보유량", "수량"]],
  ["name", ["종목명", "종목"]],
];

function labelOf(text: string, opts: { suffix: boolean }): Field | null {
  const c = text.replace(/[^가-힣A-Za-z]/g, "");
  if (!c) return null;
  for (const [f, ls] of LABELS) {
    if (ls.some((l) => (opts.suffix ? c.endsWith(l) : c.includes(l)))) return f;
  }
  return null;
}

/** Table header labels. A garbled "보유수량" ("보유숭") still starts with 보유. */
function headerField(text: string): Field {
  const f = labelOf(text, { suffix: false });
  if (f) return f;
  if (/^보유/.test(text) && !/종목|주식/.test(text)) return "qty";
  return "unknown";
}

const LABEL_WORDS = new Set(LABELS.flatMap(([, ls]) => ls).concat(["주", "원", "총", "매입", "보유", "잔고"]));

// ── signed amounts (평가손익 "+100,750", "-$58.62") ────────────────────────

function signedCandidates(w: OcrWord): number[] {
  const m = w.t.match(/^([+\-−▲▼]?)(.*)$/)!;
  const sign = m[1] === "-" || m[1] === "−" || m[1] === "▼" ? -1 : m[1] ? 1 : 0;
  const vals = new Set<number>();
  const prim = parseAmount(m[2]);
  if (prim !== null) vals.add(prim);
  // The digits-only re-read drops the sign and may read "+" as a 4.
  const alt = w.alt ? parseAmount(w.alt) : null;
  if (alt !== null) vals.add(alt);
  const out: number[] = [];
  for (const v of vals) {
    if (sign >= 0) out.push(v);
    if (sign <= 0) out.push(-v);
  }
  return out;
}

// ── extraction within one record ─────────────────────────────────────────

interface Reads {
  qty: NumRead[];
  avg: NumRead[];
  cost: NumRead[];
  value: NumRead[];
  /** Unlabelled amount on the name line: 평가금액 or 매입금액, unknown which. */
  unl: NumRead[];
  pl: number[][];
  qtyHasUnit: boolean;
}

const emptyReads = (): Reads => ({ qty: [], avg: [], cost: [], value: [], unl: [], pl: [], qtyHasUnit: false });

const SEP = /^[·ㆍ•|,:;\-–—/()（）]+$/;

/** Cards / key-value lists: each number is typed by the label right before it
 * on the same line ("평균 70,850원", "보유수량 6주") or by a 주 unit after it. */
function readLabelled(lines: Line[], nameLine: Line | null, reads: Reads) {
  for (const line of lines) {
    let between: string[] = [];
    const ws = line.words;
    for (let i = 0; i < ws.length; i++) {
      const w = ws[i];
      const t = w.t;
      if (!/\d/.test(t)) {
        if (!SEP.test(t)) between.push(t);
        continue;
      }
      const label = labelOf(between.filter((x) => x !== "원" && x !== "주" && !/^\$$/.test(x)).join(""), { suffix: true });
      between = [];
      const next = ws[i + 1]?.t ?? "";
      if (t.includes("%")) {
        // "65%" is how OCR reads "65주" — never a number; a percentage is 수익률.
        continue;
      }
      if (/^[+\-−▲▼]/.test(t) && (label === null || label === "pl")) {
        reads.pl.push(signedCandidates(w));
        continue;
      }
      const unitNext = /^주/.test(next) && next !== "주당";
      if ((unitNext || /주$/.test(t)) && label !== "avg" && label !== "cur" && label !== "cost" && label !== "value") {
        reads.qty.push(readNumber({ ...w, t: t.replace(/주$/, "") }));
        reads.qtyHasUnit = true;
        continue;
      }
      switch (label) {
        case "qty": reads.qty.push(readNumber({ ...w, t: t.replace(/주$/, "") })); break;
        case "avg": reads.avg.push(readNumber(w)); break;
        case "cost": reads.cost.push(readNumber(w)); break;
        case "value": reads.value.push(readNumber(w)); break;
        case "pl": reads.pl.push(signedCandidates(w)); break;
        case null:
          // Unlabelled money on the stock's own name line ("삼성전자 4,706,000원").
          if (line === nameLine && !isCode(t) &&
              (/원$/.test(t) || next.startsWith("원") || /^\$/.test(t) || /^\d{1,3}(,\d{3})+(\.\d{2})?$/.test(t))) {
            reads.unl.push(readNumber(w));
          }
          break;
        default: break; // cur / rate / ignore / name — evidence we do not use
      }
    }
  }
}

// ── the proof ────────────────────────────────────────────────────────────

const one = (xs: NumRead[]): NumRead | null => (xs.length === 1 ? xs[0] : null);

function prove(reads: Reads, usd: boolean, flags: string[], opts: { requireUnit: boolean }) {
  const hint = (r: NumRead | null | undefined) => r?.hint;
  // The same label twice in one record: it swallowed a neighbour's line.
  const dup = reads.qty.length > 1 || reads.avg.length > 1 || reads.cost.length > 1;
  if (dup) flags.push("merged_record");
  const q = one(reads.qty), p = one(reads.avg), c = one(reads.cost);
  const v = one(reads.value), u = one(reads.unl);
  const pl = reads.pl.length === 1 ? reads.pl[0] : [];

  // What shares × avg must equal, when the screen prints enough to say.
  const targets: number[] = [];
  if (c) targets.push(...c.candidates);
  if (v && pl.length) for (const a of v.candidates) for (const b of pl) targets.push(a - b);
  if (u && pl.length) {
    // An unlabelled name-line amount is either 매입금액 or 평가금액.
    for (const a of u.candidates) { targets.push(a); for (const b of pl) targets.push(a - b); }
  }

  let shares: Cell<number> = q ? { value: q.value, hint: q.value === null ? q.hint : undefined } : { value: null, hint: hint(reads.qty[0]) };
  let avg: Cell<number> = p ? { value: p.value, hint: p.value === null ? p.hint : undefined } : { value: null, hint: hint(reads.avg[0]) };
  if (dup) {
    return {
      shares: { value: null, hint: shares.value != null ? String(shares.value) : shares.hint },
      avg: { value: null, hint: avg.value != null ? String(avg.value) : avg.hint },
    };
  }

  const matches = (a: number, b: number) => targets.some((t) => close(a * b, t, usd));
  if (q && p && targets.length) {
    const provenPair = shares.value !== null && avg.value !== null;
    if (provenPair && matches(shares.value!, avg.value!)) flags.push("cross_checked");
    else {
      const combos = new Set<string>();
      for (const qv of q.candidates) for (const pv of p.candidates) if (matches(qv, pv)) combos.add(`${qv}|${pv}`);
      if (combos.size === 1) {
        const [qv, pv] = [...combos][0].split("|").map(Number);
        shares = { value: qv };
        avg = { value: pv };
        flags.push("cross_checked");
      } else if (combos.size === 0) {
        // HARD gate: the screen prints the cost (or value − P/L) and no
        // reading of shares × avg produces it — a misread or a misassigned
        // column. Neither cell is kept, even a shares value both readings
        // agree on: both come from one box, so a digit the box missed
        // ("117" → "17") is missed twice.
        flags.push("amount_mismatch");
        return { shares: { value: null, hint: q.hint }, avg: { value: null, hint: p.hint } };
      }
    }
  } else if (!p && q && c && q.value !== null && c.value !== null && q.value > 0 && reads.avg.length === 0) {
    // No average-cost reading at all, but 수량 and 매입금액 are both proven:
    // avg = 매입금액 ÷ 수량 by definition. Only when it divides to a printable
    // price (whole won / whole cent) — a rounded quotient is not on screen.
    const d = c.value / q.value;
    const printable = usd ? Math.abs(d * 100 - Math.round(d * 100)) < 1e-6 : Math.abs(d - Math.round(d)) < 1e-9;
    if (printable) {
      avg = { value: usd ? Math.round(d * 100) / 100 : Math.round(d) };
      flags.push("derived_avg");
    }
  }

  // Plausibility where nothing else checked the numbers.
  const checked = flags.includes("cross_checked") || flags.includes("derived_avg");
  if (!checked) {
    if (!usd && avg.value !== null && avg.value < 100) avg = { value: null, hint: String(avg.value) };
    if (opts.requireUnit && shares.value !== null && !reads.qtyHasUnit) shares = { value: null, hint: String(shares.value) };
  }
  if (shares.value !== null && (shares.value <= 0 || shares.value > 1e7)) shares = { value: null, hint: String(shares.value) };
  if (!usd && shares.value !== null && !Number.isInteger(shares.value)) shares = { value: null, hint: String(shares.value) };
  if (avg.value !== null && avg.value <= 0) avg = { value: null, hint: String(avg.value) };
  return { shares, avg };
}

// ── name / code ──────────────────────────────────────────────────────────

function nameAndCode(nameWords: OcrWord[], codeWords: OcrWord[], usd: boolean, dollarLine: boolean) {
  const lead = nameWords.filter((w) => !LABEL_WORDS.has(w.t.replace(/[^가-힣A-Za-z]/g, "")));
  // A US ticker only from a line that carries the $ amount (fills rule —
  // a symbol inside a fund description must never become the ticker).
  const nm = nameFrom(lead, usd && dollarLine);
  const name = nm.name.replace(/^[(（[{<]+|[)）\]}>]+$/g, "").trim();
  const out: { name: Cell<string>; code: Cell<string> } = {
    name: name ? { value: name } : { value: null },
    code: { value: null },
  };
  const cw = codeWords.find((w) => isCode(w.t));
  if (cw) {
    out.code = cw.alt != null && digitsOf(cw.alt) === cw.t ? { value: cw.t } : { value: null, hint: cw.t };
  } else if (nm.code && !isCode(nm.code)) {
    out.code = { value: nm.code };
  } else {
    const garbled = codeWords[0];
    if (garbled) out.code = { value: null, hint: garbled.alt ?? garbled.t };
  }
  return out;
}

function screenCurrency(lines: Line[]): "KRW" | "USD" | null {
  const all = lines.map((l) => l.compact).join("|");
  const won = /\d원|원\||₩/.test(all) || /\d\s*원/.test(lines.map((l) => l.text).join("|"));
  const dollar = /\$\s*\d/.test(all);
  if (won && !dollar) return "KRW";
  if (dollar && !won) return "USD";
  return null;
}

function recordCurrency(compact: string, screen: "KRW" | "USD" | null): "KRW" | "USD" | null {
  const dollar = /\$\s*\d/.test(compact);
  const won = /\d원|₩/.test(compact);
  if (dollar && !won) return "USD";
  if (won && !dollar) return "KRW";
  if (dollar && won) return null;
  return screen;
}

// ── tables ──────────────────────────────────────────────────────────────

interface HCol { f: Field; cx: number }

function holdingsHeader(line: Line): HCol[] | null {
  const cols = headerSegments(line).map(({ text, cx }) => ({ f: headerField(text), cx }));
  const known = new Set(cols.map((c) => c.f).filter((f) => f !== "unknown"));
  if (known.size < 3 || !known.has("qty") || !(known.has("avg") || known.has("cost"))) return null;
  return cols;
}

const NUMERIC_FIELDS: Field[] = ["qty", "avg", "cost", "value", "pl", "cur", "rate"];

function tableHoldings(lines: Line[], hi: number, cols: HCol[], screenCur: "KRW" | "USD" | null): ParsedHolding[] {
  const body = lines.slice(hi + 1);
  const footer = body.findIndex((l) => /합계|총계/.test(l.compact));
  const rows = footer >= 0 ? body.slice(0, footer) : body;
  // A code under / beside the name does not make a line a row; a comma-less
  // 6-digit price in a numeric column ("812000") does.
  const numericCount = (l: Line) => l.words.filter((w) => /\d/.test(w.t) && !(codeLike(w) && nearNameColumn(w, cols))).length;
  const data = rows.filter((l) => numericCount(l) >= 2);
  const aux = rows.filter((l) => numericCount(l) < 2);
  const pitch = data.length > 1 ? median(data.slice(1).map((l, i) => l.y - data[i].y)) : 40;
  const attached = new Map<Line, Line[]>(data.map((l) => [l, []]));
  for (const l of aux) {
    const byDist = [...data].sort((x, y) => Math.abs(x.y - l.y) - Math.abs(y.y - l.y));
    const [best, second] = byDist;
    if (!best || Math.abs(best.y - l.y) >= pitch * 0.75) continue;
    if (second && Math.abs(second.y - l.y) < Math.abs(best.y - l.y) * 1.5) continue;
    attached.get(best)!.push(l);
  }
  const nearest = (w: OcrWord): Field => {
    const cx = (w.x0 + w.x1) / 2;
    const [best, second] = [...cols].sort((x, y) => Math.abs(x.cx - cx) - Math.abs(y.cx - cx));
    // About as close to two numeric columns (e.g. 평균단가 | 현재가) → neither.
    if (/\d/.test(w.t) && second && NUMERIC_FIELDS.includes(best.f) && NUMERIC_FIELDS.includes(second.f) &&
        Math.abs(second.cx - cx) < Math.abs(best.cx - cx) * 1.3) return "unknown";
    return best.f;
  };
  const hasName = cols.some((c) => c.f === "name");
  return data.map((line) => {
    const all = [line, ...(attached.get(line) ?? [])].sort((a, b) => a.y - b.y);
    const compact = all.map((l) => l.compact).join("");
    const currency = recordCurrency(compact, screenCur);
    const usd = currency === "USD";
    const reads = emptyReads();
    const nameWords: OcrWord[] = [];
    const codeWords: OcrWord[] = [];
    for (const w of all.flatMap((l) => l.words)) {
      const f = nearest(w);
      if (f === "ignore") continue;
      if (/\d/.test(w.t)) {
        // A 6-digit code only in (or right beside) the name column — never a
        // comma-less price in a numeric column.
        if (codeLike(w) && (f === "name" || nearNameColumn(w, cols))) { codeWords.push(w); continue; }
        if (w.t.includes("%")) continue;
        switch (f) {
          case "qty": reads.qty.push(readNumber(w)); break;
          case "avg": reads.avg.push(readNumber(w)); break;
          case "cost": reads.cost.push(readNumber(w)); break;
          case "value": reads.value.push(readNumber(w)); break;
          case "pl": reads.pl.push(signedCandidates(w)); break;
          case "name": if (/[가-힣A-Za-z]/.test(w.t)) nameWords.push(w); break;
          default: break;
        }
        continue;
      }
      if (f === "name" || (!hasName && f === "unknown")) nameWords.push(w);
    }
    const flags: string[] = [];
    const { shares, avg } = prove(reads, usd, flags, { requireUnit: false });
    const nc = nameAndCode(nameWords, codeWords, usd, /\$\s*\d/.test(line.compact));
    return {
      name: nc.name, code: nc.code, shares, avgCost: avg, currency, flags,
      sourceText: all.map((l) => l.text).join(" / "),
    };
  });
}

function nearNameColumn(w: OcrWord, cols: HCol[]): boolean {
  const nameCol = cols.find((c) => c.f === "name");
  if (!nameCol) return false;
  const cx = (w.x0 + w.x1) / 2;
  const [best] = [...cols].sort((x, y) => Math.abs(x.cx - cx) - Math.abs(y.cx - cx));
  return best === nameCol || w.x0 < nameCol.cx;
}

// ── stacked-header tables (two values per cell) ─────────────────────────────
//
//   종목명 | 평가손익 | 잔고수량 | 평가금액        ← header line 1
//          | 수익률   | 평균단가 | 현재가          ← header line 2
//   삼성전자 +1,000   10        711,000          ← body top line
//            +0.14%   71,000    71,100          ← body bottom line
//
// Each column carries a top and a bottom field; a stock is two body lines,
// with its name on either line or centred between them.

interface SCol { cx: number; top: Field; bot: Field }

function stackedHeader(lines: Line[], hMed: number): { at: number; cols: SCol[] } | null {
  // Header lines carry labels — "보유수량 817 · 매입단가 77,620" (two numbers)
  // is data; one stray number is OCR junk ("2008 평균단가 현재가").
  const numbered = (l: Line) => l.words.filter((w) => /\d{2,}/.test(w.t)).length >= 2;
  const known = (xs: { f: Field }[]) => xs.filter((x) => x.f !== "unknown");
  const fields = (l: Line) => headerSegments(l).map(({ text, cx }) => ({ f: headerField(text), cx }));
  for (let i = 0; i + 1 < lines.length; i++) {
    const a = lines[i];
    if (numbered(a)) continue;
    const top = fields(a);
    if (known(top).length < 2) continue;
    // The second header line, allowing one OCR junk line in between.
    const j = [i + 1, i + 2].find((k) => k < lines.length && lines[k].y - a.y < hMed * 4 &&
      !numbered(lines[k]) && known(fields(lines[k])).length >= 2);
    if (j === undefined) continue;
    const b = lines[j];
    const bot = fields(b);
    const all = new Set([...known(top), ...known(bot)].map((x) => x.f));
    if (!all.has("qty") || !(all.has("avg") || all.has("cost"))) continue;
    const cols: SCol[] = top.map((t) => {
      const near = [...bot].sort((x, y) => Math.abs(x.cx - t.cx) - Math.abs(y.cx - t.cx))[0];
      return { cx: t.cx, top: t.f, bot: near && Math.abs(near.cx - t.cx) < hMed * 3 ? near.f : "unknown" };
    });
    return { at: j, cols };
  }
  return null;
}

function stackedHoldings(lines: Line[], at: number, cols: SCol[], screenCur: "KRW" | "USD" | null, hMed: number): ParsedHolding[] {
  const body = lines.slice(at + 1);
  const numeric = body.filter((l) => l.words.filter((w) => /\d/.test(w.t)).length >= 2);
  const nameLines = body.filter((l) => !numeric.includes(l) && /[가-힣A-Za-z]{2,}/.test(l.compact.replace(/[^가-힣A-Za-z]/g, "")));
  const pairs: [Line, Line][] = [];
  for (let k = 0; k + 1 < numeric.length; k++) {
    if (numeric[k + 1].y - numeric[k].y < hMed * 3.2) { pairs.push([numeric[k], numeric[k + 1]]); k++; }
  }
  const nameCol = cols.find((c) => c.top === "name");
  const colOf = (w: OcrWord) => [...cols].sort((x, y) => Math.abs(x.cx - (w.x0 + w.x1) / 2) - Math.abs(y.cx - (w.x0 + w.x1) / 2))[0];
  return pairs.map(([top, bot]) => {
    const mid = (top.y + bot.y) / 2;
    const reads = emptyReads();
    const nameWords: OcrWord[] = [];
    const codeWords: OcrWord[] = [];
    const put = (w: OcrWord, f: Field) => {
      if (w.t.includes("%")) return;
      switch (f) {
        case "qty": reads.qty.push(readNumber({ ...w, t: w.t.replace(/주$/, "") })); break;
        case "avg": reads.avg.push(readNumber(w)); break;
        case "cost": reads.cost.push(readNumber(w)); break;
        case "value": reads.value.push(readNumber(w)); break;
        case "pl": reads.pl.push(signedCandidates(w)); break;
        default: break;
      }
    };
    for (const [line, which] of [[top, "top"], [bot, "bot"]] as const) {
      for (const w of line.words) {
        const c = colOf(w);
        if (!/\d/.test(w.t) || (nameCol && c === nameCol)) {
          if (isCode(w.t)) codeWords.push(w);
          else if (/[가-힣A-Za-z]/.test(w.t) && (!nameCol || c === nameCol)) nameWords.push(w);
          continue;
        }
        put(w, which === "top" ? c.top : c.bot);
      }
    }
    // A name centred between the two lines.
    if (!nameWords.length) {
      const nl = nameLines.find((l) => Math.abs(l.y - mid) < hMed * 1.2);
      if (nl) nameWords.push(...nl.words.filter((w) => /[가-힣A-Za-z]/.test(w.t)));
    }
    const compact = top.compact + bot.compact;
    const currency = recordCurrency(compact, screenCur);
    const usd = currency === "USD";
    const flags: string[] = [];
    const { shares, avg } = prove(reads, usd, flags, { requireUnit: false });
    const nc = nameAndCode(nameWords, codeWords, usd, /\$\s*\d/.test(compact));
    return {
      name: nc.name, code: nc.code, shares, avgCost: avg, currency, flags,
      sourceText: [top.text, bot.text].join(" / "),
    };
  });
}

// ── cards / key-value lists ────────────────────────────────────────────────

/** A word that is a printed number ("1,040,000", "+$677.00", "42주"), as
 * opposed to a name glyph misread with a digit in it ("Ｌ6" for LG). */
const numberish = (w: OcrWord) => /^[+\-−▲▼~≈(]?[$₩&]?\d/.test(w.t);

/** A 6-digit stock code as printed: 6 digits, or a 6-glyph token whose
 * digits-only re-read is 6 digits ("0Ｌ35790" → 086790) — never an amount. */
const codeLike = (w: OcrWord) =>
  isCode(w.t) || (/^[0-9A-Za-zＬＩＯ]{6}$/.test(w.t) && /\d/.test(w.t) && isCode(w.alt ?? ""));

/** Words before the first number, minus labels and separators — a stock name? */
function leadName(l: Line): boolean {
  const firstNum = l.words.findIndex((w) => numberish(w) || codeLike(w));
  const lead = (firstNum < 0 ? l.words : l.words.slice(0, firstNum)).map((w) => w.t).join("");
  if (!/[가-힣A-Za-z]{2,}/.test(lead.replace(/[^가-힣A-Za-z]/g, ""))) return false;
  if (labelOf(lead, { suffix: false })) return false;
  const nm = nameFrom(firstNum < 0 ? l.words : l.words.slice(0, firstNum), false);
  return nm.name.replace(/[^가-힣A-Za-z]/g, "").length >= 2;
}

// A quantity label anywhere on the line counts — "보유수량 817 · 매입단가 77,620"
// is a quantity line even though its whole text reads as 매입단가 first.
const QTY_LABEL = /보유수량|잔고수량|보유량|수량/;
const isAnchor = (l: Line) =>
  /\d\s*주(?!당)/.test(l.text) || (QTY_LABEL.test(l.compact.replace(/[\d,.]/g, "")) && /\d/.test(l.text));

function cardHoldings(lines: Line[], screenCur: "KRW" | "USD" | null): ParsedHolding[] {
  const anchors = lines.map((l, i) => (isAnchor(l) ? i : -1)).filter((i) => i >= 0);
  if (anchors.length === 0) return [];
  const names = lines.map((l, i) => (!isAnchor(l) && leadName(l) ? i : -1)).filter((i) => i >= 0);
  const hMed = median(lines.map((l) => l.h)) || 20;

  // Record starts: for each anchor, the nearest name line above it that lies
  // after the previous anchor (so a name is never shared by two records).
  const starts: { start: number; anchor: number | null; nameIdx: number | null }[] = [];
  anchors.forEach((a, k) => {
    const prev = k > 0 ? anchors[k - 1] : -1;
    const between = names.filter((n) => n < a && n > prev);
    const last = between[between.length - 1];
    const n = last !== undefined && lines[a].y - lines[last].y < hMed * 8 ? last : null;
    starts.push({ start: n ?? a, anchor: a, nameIdx: n });
    // Other name lines between two anchors: a record whose quantity line was
    // not recognised ("2.5%" for 2.5주, "ax" for 4주). It becomes a row of
    // its own — never silently dropped, never merged into its neighbour.
    if (k === 0) return; // above the first record: screen title / tabs
    for (const o of between) if (o !== n) starts.push({ start: o, anchor: null, nameIdx: o });
  });
  // Name lines after the last anchor with numbers under them (cut or unread qty).
  const last = anchors[anchors.length - 1];
  for (const n of names.filter((x) => x > last)) {
    const upto = names.find((x) => x > n) ?? lines.length;
    if (lines.slice(n, upto).some((l) => /\d/.test(l.text)) && lines[n].y - lines[last].y < hMed * 30) {
      starts.push({ start: n, anchor: null, nameIdx: n });
    }
  }
  starts.sort((a, b) => a.start - b.start);

  const out: ParsedHolding[] = [];
  starts.forEach((s, k) => {
    const end = k + 1 < starts.length ? starts[k + 1].start : lines.length;
    // Records end where the next begins; trailing lines far below (bottom tab
    // bar, disclaimers) are not part of the last record.
    const recIdx: number[] = [];
    for (let i = s.start; i < end; i++) {
      if (i > s.start && lines[i].y - lines[i - 1].y > hMed * 5) break;
      recIdx.push(i);
    }
    const rec = recIdx.map((i) => lines[i]);
    const compact = rec.map((l) => l.compact).join("");
    const currency = recordCurrency(compact, screenCur);
    const usd = currency === "USD";
    const nameLine = s.nameIdx !== null ? lines[s.nameIdx] : null;
    const reads = emptyReads();
    readLabelled(rec, nameLine, reads);
    const flags: string[] = [];
    const { shares, avg } = prove(reads, usd, flags, { requireUnit: true });
    let nc = { name: { value: null } as Cell<string>, code: { value: null } as Cell<string> };
    if (nameLine) {
      const codeWords = nameLine.words.filter(codeLike);
      const firstNum = nameLine.words.findIndex((w, i) => numberish(w) && !codeWords.includes(w) && !nameDigitAt(nameLine.words, i));
      const lead = firstNum < 0 ? nameLine.words : nameLine.words.slice(0, firstNum);
      nc = nameAndCode(lead.filter((w) => !codeWords.includes(w)), codeWords, usd, /\$\s*\d/.test(nameLine.compact));
    }
    if (s.anchor === null && !nc.name.value && !nc.code.value) return;
    out.push({
      name: nc.name, code: nc.code, shares, avgCost: avg, currency, flags,
      sourceText: rec.map((l) => l.text).join(" / "),
    });
  });
  return out;
}

// ── Toss 내 투자 (two lines per stock, no labels) ─────────────────────────
//
//   [logo] 아이티센글로벌            859,449원     ← name + 평가금
//          29주          -982,051 (53.3%)          ← shares, 평가손익, 수익률
//
// Nothing is labelled and no average cost is printed, but the layout is fixed:
//   - the first token of the second line IS the share count, so a misread 주
//     glyph ("19%", "3F", "248 수") still reads as shares when both OCR
//     readings of the digits agree;
//   - 수익률 = 손익 ÷ (평가금 − 손익), truncated to 0.1%. When the printed rate reproduces from the
//     printed amount and P/L, (평가금 − 손익) is proven to be the cost basis, and
//     avg = cost ÷ shares. Exactly one reading combination must pass; otherwise
//     the quotient is only a hint.
//   - the name starts where the second line starts; anything left of it is the
//     round logo that OCR reads as "©", "(vs)", "MA", "이 <".

const TOSS_AMOUNT = /^[$]?\d{1,3}(,\d{3})*(\.\d{2})?원?$/;
/** "29주" "29 주" and the glyph misreads OCR makes of 주 ("19%", "3F", "39=",
 * "94+", "248 수"): digits, then at most two non-digit glyphs. */
const TOSS_QTY = /^(\d[\d,.]*?)[.:]?([^\d\s]{0,2})$/;
const TOSS_PL = /^[+\-−][$]?[\d,]+(\.\d+)?원?$/;
const TOSS_RATE = /^\((\d+(\.\d+)?)%\)$/;

export const tossQtyLine = tossPlLine;

/** The amount as printed, or as the digit pass re-read it ("1.062,711",
 * "3,231.920%" → 3,231,920). A sign makes it a P/L, not an amount. */
const tossAmountWord = (w: OcrWord | undefined) =>
  Boolean(w) && !/^[+\-−]/.test(w!.t) &&
  [w!.t.replace(/[,.]$/, ""), (w!.alt ?? "").trim()].some((t) =>
    TOSS_AMOUNT.test(t) && (t.includes(",") || /^\$\d+\.\d{2}$/.test(t))); // "$184.32" has no comma

/** "이름 … 금액" — the first amount after at least one name word. Whatever
 * follows it ("원", or "원" misread as "839%") is ignored. Names may carry
 * digits ("교보15호스팩"). A bare number right before a printed "원" is an
 * amount too ("832원", comma dropped "17164,157원"). */
function tossNameLine(l: Line): { nameWords: OcrWord[]; amount: OcrWord } | null {
  // ≥3 digits: the 현재가 · 평가금 · $ · 원 toggle reads "$ 원" as "6 원".
  const beforeWon = new Set(l.words.filter((w, k) => l.words[k + 1]?.t === "원" && /^\d[\d,.]{2,}$/.test(w.t)));
  const ws = l.words.filter((w) => w.t !== "원");
  const i = ws.findIndex((w, k) => k > 0 && (tossAmountWord(w) || beforeWon.has(w)));
  if (i < 0) return null;
  const nameWords = ws.slice(0, i);
  const letters = nameWords.map((w) => w.t).join("").replace(/[^가-힣A-Za-z]/g, "");
  if (letters.length < 2) return null;
  if (/내투자|주식$/.test(letters)) return null;
  return { nameWords, amount: ws[i] };
}

/** Both readings of a digit token, with the trailing punctuation the digit
 * pass adds ("2" / "2." / "2:") dropped. */
function tossRead(t: string, alt: string | null | undefined): NumRead {
  return readNumber({ t: t.replace(/[.:/]$/, ""), alt: alt?.trim().replace(/[.:/]$/, ""), c: 0, x0: 0, y0: 0, x1: 0, y1: 0 });
}

/** The share token is the one digit word before the P/L; logo glyphs read
 * as letters ("자 248 주") may sit in front of it. */
function tossShares(ws: OcrWord[], plIdx: number): Cell<number> {
  const before = ws.slice(0, plIdx < 0 ? ws.length : plIdx).filter((w) => /\d/.test(w.t));
  if (before.length !== 1) return { value: null };
  const w = before[0];
  const m = w.t.match(TOSS_QTY);
  if (!m) return { value: null };
  const r = tossRead(m[1], w.alt);
  const n = r.value;
  // Nothing on this screen checks the count (the rate check covers amount and
  // P/L only), so a 주 glyph must be seen after the digits — in the token
  // ("19%", "3F") or as the next word ("29 주", "248 수"). Without one the 주
  // may have been read as a digit ("7주" → "73").
  const next = ws[ws.indexOf(w) + 1]?.t ?? "";
  const unit = m[2] !== "" || /^[주수추%=+F]/.test(next);
  return unit && n !== null && Number.isInteger(n) && n > 0 && n <= 1e7 ? { value: n } : { value: null, hint: m[1] };
}

function tossAvg(amount: NumRead, plw: OcrWord, ratew: OcrWord | undefined, shares: number, usd: boolean): Cell<number> {
  const neg = /^[\-−]/.test(plw.t);
  const pl = tossRead(plw.t.replace(/^[+\-−]/, ""), plw.alt);
  // Toss prints the rate with one decimal; a reading with more ("53.39" for
  // 53.3) is a misread, so either reading with exactly one decimal is used.
  // With no such reading, both are cut to one decimal (an extra trailing digit).
  const read = ratew ? [ratew.t.match(TOSS_RATE)?.[1] ?? "", (ratew.alt ?? "").trim()] : [];
  const one = read.filter((r) => /^\d+\.\d$/.test(r)).map(Number);
  const rates = one.length ? one
    : read.filter((r) => /^\d+\.\d+$/.test(r)).map((r) => Math.floor(Number(r) * 10) / 10);
  const avgOf = (a: number, p: number) => {
    const d = (a - (neg ? -p : p)) / shares;
    return usd ? Math.round(d * 100) / 100 : Math.round(d);
  };
  for (const rate of [...new Set(rates)]) {
    const ok = new Set<number>();
    for (const a of amount.candidates) {
      for (const p of pl.candidates) {
        const cost = a - (neg ? -p : p);
        if (cost <= 0) continue;
        // Toss truncates the rate (37.667% → "37.6%"); rounding is accepted too.
        const r = (p / cost) * 100;
        if (r >= rate - 0.051 && r < rate + 0.1) ok.add(avgOf(a, p));
      }
    }
    if (ok.size === 1) return { value: [...ok][0] };
  }
  const a = amount.candidates[0], p = pl.candidates[0];
  if (a === undefined || p === undefined) return { value: null };
  const d = avgOf(a, p);
  return d > 0 ? { value: null, hint: String(d) } : { value: null };
}

function tossHoldings(lines: Line[]): ParsedHolding[] {
  const out: ParsedHolding[] = [];
  const hMed = median(lines.map((l) => l.h)) || 20;
  // The name column starts where the quantity lines start — one x for the
  // whole screen, so a row whose quantity line is cut off still has it.
  const qx = lines.filter((l) => tossQtyLine(l.compact))
    .map((l) => l.words.find((w) => /\d/.test(w.t))?.x0).filter((x): x is number => x !== undefined);
  const nameLeft = qx.length ? median(qx) - hMed : -Infinity;
  let foreign = false;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (/해외주식/.test(l.compact)) foreign = true;
    if (/국내주식/.test(l.compact)) foreign = false;
    const nm = tossNameLine(l);
    if (!nm) continue;
    // The quantity line is the first "…±손익(수익률%)" line below, before the
    // next stock's name line; logo glyphs in between ("©", "5", "(vs)") are
    // skipped. Too far below → cut off at the edge.
    let ql: Line | null = null;
    for (let k = i + 1; k < lines.length && lines[k].y - l.y < hMed * 5; k++) {
      if (tossQtyLine(lines[k].compact)) { ql = lines[k]; break; }
      if (tossNameLine(lines[k])) break;
    }
    // The page pass often reads "$" as "%" ("%38,285.00"); the digit pass keeps it.
    const usd = [nm.amount.t, nm.amount.alt ?? ""].some((t) => t.trim().startsWith("$"));
    const currency: ParsedHolding["currency"] = usd ? "USD" : foreign ? null : "KRW";
    const flags: string[] = [];
    if (foreign && !usd) flags.push("foreign_in_krw");

    let shares: Cell<number> = { value: null };
    let avgCost: Cell<number> = { value: null };
    let nameWords = nm.nameWords;
    if (ql) {
      const ws = ql.words;
      const plIdx = ws.findIndex((w) => TOSS_PL.test(w.t));
      shares = tossShares(ws, plIdx);
      const plw = plIdx >= 0 ? ws[plIdx] : undefined;
      const ratew = ws.find((w) => TOSS_RATE.test(w.t));
      const n = shares.value ?? (shares.hint ? Number(shares.hint) : NaN);
      if (plw && Number.isInteger(n) && n > 0 && !(foreign && !usd)) {
        const amount = tossRead(nm.amount.t.replace(/원$/, "").replace(/^%(?=\d)/, usd ? "$" : "%"), nm.amount.alt);
        // Malformed grouping ("17164,157") parses to nothing; its digits are
        // still a candidate — the rate check decides.
        if (amount.candidates.length === 0 && digitsOf(nm.amount.t)) amount.candidates.push(Number(digitsOf(nm.amount.t)));
        avgCost = tossAvg(amount, plw, ratew, n, usd);
        // A proven average needs proven shares too.
        if (avgCost.value !== null && shares.value === null) avgCost = { value: null, hint: String(avgCost.value) };
        if (avgCost.value !== null) flags.push("derived_avg");
      }
    }
    const kept = nameWords.filter((w) => w.x1 > nameLeft);
    if (kept.length) nameWords = kept;
    nameWords = nameWords.filter((w) => /[가-힣A-Za-z]/.test(w.t) || /^\d+$/.test(w.t));
    const nc = nameAndCode(nameWords, [], usd, usd);
    out.push({
      name: nc.name, code: nc.code, shares, avgCost, currency, flags,
      sourceText: [l, ql].filter(Boolean).map((x) => x!.text).join(" / "),
    });
  }
  return out;
}

// ── Toss 자세히 보기 table ───────────────────────────────────────────────────
//
//   종목명      | 총 수익 | 1주 평균 금액     | 총 금액
//   삼성전자      -0.7%     272,000원           4,048,149원     ← top line
//   15주          -31,851원 현재가 270,500원    원금 4,080,000원 ← bottom line
//
// The average cost is printed, and so is 원금 (cost). Columns come from the
// header's x positions; inside a column the upper amount is the average /
// 평가금 and the lower one 현재가 / 원금 — by position, so a misread label
// ("원금" → "HZ") does not matter. A stock ends at the line carrying
// 현재가 / 원금 (its share count may sit one line lower, under a wrapped
// name). shares × avg must reproduce 원금, as in every other layout.

const DETAIL_HEADER = (l: Line) => /평균금액/.test(l.compact) && /총금액/.test(l.compact) && /종목/.test(l.compact);

interface DetailCols { nameRight: number; avg: [number, number]; total: [number, number]; pl: number | null }

function detailCols(h: Line): DetailCols | null {
  const ws = h.words;
  const iAvg = ws.findIndex((w) => /평균/.test(w.t));
  const iTot = ws.findIndex((w, k) => k > iAvg && /^총/.test(w.t));
  if (iAvg < 0 || iTot < 0) return null;
  const avgStart = ws.slice(0, iAvg).reverse().find((w) => /^[1주]$/.test(w.t)) ?? ws[iAvg];
  const avgEnd = ws.slice(iAvg).find((w) => /금액/.test(w.t)) ?? ws[iAvg];
  const totEnd = ws.slice(iTot).find((w) => /금액/.test(w.t)) ?? ws[iTot];
  const iName = ws.findIndex((w) => /명/.test(w.t));
  const nextAfterName = iName >= 0 ? ws.slice(iName + 1).find((w) => !/^[<>|^ㆍ·:;,.]$/.test(w.t) || w.x0 > ws[iName].x1 + 60) : undefined;
  const nameRight = Math.min(nextAfterName ? nextAfterName.x0 - 5 : Infinity, avgStart.x0 - 60);
  // 총 수익 (left of the average), when the header shows it.
  const plW = ws.slice(0, iAvg).find((w, k) => k > iName && /수|익/.test(w.t));
  return { nameRight, avg: [avgStart.x0, avgEnd.x1], total: [ws[iTot].x0, totEnd.x1], pl: plW ? plW.x0 + 40 : null };
}

const cxOf = (w: OcrWord) => (w.x0 + w.x1) / 2;
const MARK = /현재가|원금/;

function detailHoldings(lines: Line[], hMed: number): ParsedHolding[] {
  const out: ParsedHolding[] = [];
  const heads = lines.map((l, i) => (DETAIL_HEADER(l) ? i : -1)).filter((i) => i >= 0);
  heads.forEach((hi, t) => {
    const cols = detailCols(lines[hi]);
    if (!cols) return;
    const end = t + 1 < heads.length ? heads[t + 1] : lines.length;
    const body = lines.slice(hi + 1, end);
    // Each word goes to the nearest column centre — on a narrow phone the
    // right-aligned average and total cells come close enough to overlap.
    const centres: [string, number][] = [
      ["avg", (cols.avg[0] + cols.avg[1]) / 2], ["total", (cols.total[0] + cols.total[1]) / 2],
      ...(cols.pl !== null ? [["pl", cols.pl] as [string, number]] : []),
    ];
    const colOf = (w: OcrWord) => [...centres].sort((a, b) => Math.abs(a[1] - cxOf(w)) - Math.abs(b[1] - cxOf(w)))[0][0];
    const inAvg = (w: OcrWord) => cxOf(w) >= cols.avg[0] - 100 && cxOf(w) <= cols.avg[1] + 40 && colOf(w) === "avg";
    const inTot = (w: OcrWord) => cxOf(w) >= cols.total[0] - 150 && cxOf(w) <= cols.total[1] + 40 && colOf(w) === "total";
    const inName = (w: OcrWord) => w.x1 <= cols.nameRight + 40 && w.x0 < cols.nameRight;
    // No rates live in these two columns: a trailing "%" is "원" misread ("554,666%").
    const amount = (w: OcrWord) => /\d/.test(w.t) && digitsOf(w.alt ?? w.t).length >= 1;
    // A stock ends at its 현재가 / 원금 line; the share count may follow it.
    // A wrapped cell puts 현재가 and 원금 on two lines: one stock, one mark (the last).
    const marks = body.filter((l) => MARK.test(l.compact) || l.words.some((w) => inTot(w) && w.x0 < cols.total[0] - 40 && !/\d/.test(w.t)))
      .filter((l, k, xs) => !(xs[k + 1] && xs[k + 1].y - l.y < hMed * 2.5));
    let from = -Infinity;
    for (const m of marks) {
      const to = m.y + hMed * 1.8;
      const band = body.filter((l) => l.y > from && l.y <= to);
      from = to;
      const words = band.flatMap((l) => l.words.map((w) => ({ w, l })));
      const nameWs = words.filter(({ w }) => inName(w));
      const qtyW = nameWs.find(({ w }) => /^\d/.test(w.t))?.w;
      // The name sits above the 현재가 / 원금 line; what is on or below it in
      // the name column is the share count and its misread 주 ("19 수").
      const letters = nameWs.filter(({ l }) => l.y < m.y - hMed * 0.5).map(({ w }) => w)
        .filter((w) => /[가-힣A-Za-z]/.test(w.t) && !/^[A-Za-z]{1,2}$/.test(w.t) && !/^\d/.test(w.t));
      // Upper amount in a column first; a word right after 현재가 / 원금 is the lower one.
      const colAmounts = (inCol: (w: OcrWord) => boolean) => words
        .filter(({ w }) => inCol(w) && amount(w))
        .map(({ w, l }) => ({ w, labelled: MARK.test(l.words[l.words.indexOf(w) - 1]?.t ?? ""), y: l.y }))
        .sort((a, b) => a.y - b.y || a.w.x0 - b.w.x0);
      const avgs = colAmounts(inAvg), tots = colAmounts(inTot);
      const upper = (xs: typeof avgs) => xs.find((x) => !x.labelled && x !== xs[xs.length - 1]) ?? (xs.length === 1 && !xs[0].labelled ? xs[0] : undefined);
      const lower = (xs: typeof avgs) => xs.find((x) => x.labelled) ?? (xs.length >= 2 ? xs[xs.length - 1] : undefined);
      const avgW = upper(avgs)?.w, costW = lower(tots)?.w, valueW = upper(tots)?.w;
      const reads = emptyReads();
      if (qtyW) {
        const m2 = qtyW.t.match(TOSS_QTY);
        if (m2) reads.qty.push(tossRead(m2[1], qtyW.alt));
      }
      const money = (w: OcrWord) => tossRead(w.t.replace(/[원%]$/, "").replace(/^[_~]+/, "").replace(/^%(?=\d)/, "$"), w.alt);
      if (avgW) reads.avg.push(money(avgW));
      if (costW) reads.cost.push(money(costW));
      if (valueW) reads.value.push(money(valueW));
      const usd = [avgW, costW, valueW].some((w) => w && [w.t, w.alt ?? ""].some((x) => /^[_~]*\$/.test(x.trim())));
      const flags: string[] = [];
      // Share count unread ("29주" → "on"): 원금 ÷ 평균 is it when that lands
      // on a whole number and gives 원금 back within the usual tolerance.
      if (reads.qty.every((q) => q.candidates.length === 0) && reads.avg.length === 1 && reads.cost.length === 1) {
        const ns = new Set<number>();
        for (const p of reads.avg[0].candidates) for (const c of reads.cost[0].candidates) {
          const n = Math.round(c / p);
          if (n >= 1 && Math.abs(c / p - n) < 0.02 && close(n * p, c, usd)) ns.add(n);
        }
        if (ns.size === 1) {
          const n = [...ns][0];
          reads.qty = [{ value: n, candidates: [n], hint: String(n) }];
          flags.push("derived_shares");
        }
      }
      let { shares, avg } = prove(reads, usd, flags, { requireUnit: false });
      // 원금 is always printed here, so a value that did not pass shares × avg
      // ≈ 원금 is only a hint — a garbled avg lets 현재가 take its slot.
      if (!flags.includes("cross_checked")) {
        const h = (c: Cell<number>) => (c.value !== null ? { value: null, hint: String(c.value) } : c);
        shares = h(shares); avg = h(avg);
      }
      const nc = nameAndCode(letters, [], usd, false);
      if (!nc.name.value && shares.value === null && avg.value === null) continue;
      out.push({
        name: nc.name, code: nc.code, shares, avgCost: avg, currency: usd ? "USD" : "KRW", flags,
        sourceText: band.map((l) => l.text).join(" / "),
      });
    }
  });
  return out;
}

// ── entry point ──────────────────────────────────────────────────────────

export function parseHoldingsScreen(words: OcrWord[]): HoldingsParse {
  const lines = groupLines(words);
  const screenType = classifyScreen(lines);
  if (screenType !== "holdings") return { screenType, rows: [] };
  const cur = screenCurrency(lines);
  const hi = lines.findIndex((l) => holdingsHeader(l) !== null);
  const hMed = median(lines.map((l) => l.h)) || 20;
  const stacked = hi < 0 ? stackedHeader(lines, hMed) : null;
  const toss = lines.filter((l) => tossQtyLine(l.compact)).length >= 2;
  const detail = lines.some(DETAIL_HEADER);
  const rows = detail ? detailHoldings(lines, hMed)
    : hi >= 0 ? tableHoldings(lines, hi, holdingsHeader(lines[hi])!, cur)
    : stacked ? stackedHoldings(lines, stacked.at, stacked.cols, cur, hMed)
    : toss ? tossHoldings(lines) : cardHoldings(lines, cur);
  // A row with no quantity, cost, name or code reading is not a holding.
  const some = (c: Cell<unknown>) => c.value !== null || Boolean(c.hint);
  return { screenType, rows: rows.filter((r) => some(r.shares) || some(r.avgCost) || some(r.name) || some(r.code)) };
}
