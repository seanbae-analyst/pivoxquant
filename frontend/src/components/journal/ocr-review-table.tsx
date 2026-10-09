"use client";

/**
 * Review table for rows read from a fill-screen screenshot.
 *
 * Every cell the parser could not prove (`Cell.value === null`) starts EMPTY,
 * outlined in bronze, with what OCR saw as a placeholder hint. A row cannot
 * be sent until its required cells are filled — nothing is guessed for the
 * user. Cells the parser proved are prefilled and still editable.
 */

import { useT } from "@/lib/locale";
import type { ParsedFill } from "@/lib/fill-ocr/parse";
import { maskSourceText } from "@/lib/fill-ocr/mask";
import { SIDE_BUY, SIDE_SELL } from "@/lib/fill-side";

export type ReviewField = "date" | "time" | "name" | "code" | "side" | "shares" | "price" | "currency";

export interface ReviewRow {
  key: string;
  include: boolean;
  fileName: string;
  values: Record<ReviewField, string>;
  /** Value the parser proved, per field ("" = not proven). */
  proven: Record<ReviewField, string>;
  hints: Partial<Record<ReviewField, string>>;
  tz: "KST" | "ET" | null;
  flags: string[];
  sourceText: string;
}

const REQUIRED: ReviewField[] = ["date", "side", "shares", "price", "currency"];

/** `fileIndex` keeps keys unique when two picks share a name (iOS names every
 * photo "image.jpeg"). */
export function rowFromParsed(f: ParsedFill, fileName: string, i: number, fileIndex = 0): ReviewRow {
  const v = (x: string | number | null | undefined) => (x == null ? "" : String(x));
  const proven: Record<ReviewField, string> = {
    date: v(f.date.value),
    time: f.tz === "ET" ? "" : v(f.time.value),
    name: v(f.name.value),
    code: v(f.code.value),
    side: v(f.side.value),
    shares: v(f.shares.value),
    price: v(f.price.value),
    currency: v(f.currency),
  };
  return {
    key: `${fileIndex}:${fileName}#${i}`,
    include: true,
    fileName,
    values: { ...proven },
    proven,
    hints: {
      date: f.date.hint, time: f.time.hint, name: f.name.hint, code: f.code.hint,
      shares: f.shares.hint, price: f.price.hint,
    },
    tz: f.tz,
    flags: f.flags,
    sourceText: f.sourceText,
  };
}

export function rowComplete(r: ReviewRow): boolean {
  const { values: v } = r;
  if (!REQUIRED.every((k) => v[k].trim() !== "")) return false;
  if (!v.name.trim() && !v.code.trim()) return false;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v.date)) return false;
  if (v.time && !/^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$/.test(v.time)) return false;
  const n = (s: string) => Number(s.replace(/,/g, ""));
  if (!(n(v.shares) > 0 && n(v.price) > 0)) return false;
  if (v.currency === "KRW" && !Number.isInteger(n(v.shares))) return false;
  return currencyConflict(r) === null;
}

/** A US symbol with a won price (Toss can show US fills in ₩) or a KRX code
 * with a dollar price would be recorded at the wrong scale — block it. */
export function currencyConflict(r: ReviewRow): "usd_needed" | "krw_needed" | null {
  const code = r.values.code.trim().toUpperCase();
  // Same shape the server takes as a US symbol (routes/imports.py _US_TICKER_RE),
  // e.g. AAPL, BRK-B, BRK.B. Only the code field: a Latin NAME in won is
  // usually a Korean ETF ("TIGER …") and the server leaves it unresolved.
  if (/^[A-Z]{1,6}(?:[.-][A-Z]{1,2})?$/.test(code) && r.values.currency === "KRW") return "usd_needed";
  if (/^\d{6}$/.test(code) && r.values.currency === "USD") return "krw_needed";
  return null;
}

/** JSON row for POST /api/portfolio/imports/image. */
export function rowPayload(r: ReviewRow) {
  const v = r.values;
  const num = (s: string) => Number(s.replace(/,/g, ""));
  const fieldMap: Record<ReviewField, string> = {
    date: "date", time: "time", name: "name", code: "name", side: "side",
    shares: "shares", price: "price", currency: "currency",
  };
  const userFilled = [...new Set(
    (Object.keys(v) as ReviewField[])
      .filter((k) => v[k].trim() !== "" && v[k] !== r.proven[k])
      .map((k) => fieldMap[k]),
  )];
  return {
    date: v.date,
    time: v.time || null,
    tz: r.tz ?? "KST",
    name: v.name,
    code: v.code,
    action: v.side === SIDE_BUY ? "buy" : "sell",
    shares: num(v.shares),
    price: num(v.price),
    currency: v.currency,
    // Account / customer lines never leave the device (lib/fill-ocr/mask.ts).
    source_text: maskSourceText(r.sourceText),
    user_filled: userFilled,
  };
}

const inputCls =
  "w-full bg-transparent px-2 py-1 font-mono outline-none text-[var(--pq-ivory)] border rounded-[2px] focus:border-[var(--pq-bronze)]";

export function OcrReviewTable({
  rows,
  onChange,
}: {
  rows: ReviewRow[];
  onChange: (next: ReviewRow[]) => void;
}) {
  const t = useT();
  const set = (key: string, patch: Partial<ReviewRow> | ((r: ReviewRow) => ReviewRow)) =>
    onChange(rows.map((r) => (r.key !== key ? r : typeof patch === "function" ? patch(r) : { ...r, ...patch })));
  const setVal = (key: string, field: ReviewField, value: string) =>
    set(key, (r) => ({ ...r, values: { ...r.values, [field]: value } }));

  const cell = (r: ReviewRow, field: ReviewField, width: string, inputMode?: "decimal" | "text") => {
    const missing = r.values[field].trim() === "";
    const needed = REQUIRED.includes(field) || ((field === "name" || field === "code") && !r.values.name && !r.values.code);
    return (
      <input
        value={r.values[field]}
        onChange={(e) => setVal(r.key, field, e.target.value)}
        // No OCR hint → fall back to the column name. There is no header row,
        // so on a 2-column phone grid an empty box was otherwise unlabeled.
        placeholder={r.hints[field] ?? t(`journal.import.image.col.${field}`)}
        inputMode={inputMode}
        aria-label={t(`journal.import.image.col.${field}`)}
        data-missing={missing && needed ? "true" : undefined}
        className={`${inputCls} ${width}`}
        style={{ borderColor: missing && needed ? "var(--pq-bronze)" : "rgba(245,240,232,0.15)" }}
      />
    );
  };

  return (
    <div className="mt-4 space-y-3" data-testid="ocr-review-table">
      {rows.map((r) => {
        const complete = rowComplete(r);
        return (
          <div
            key={r.key}
            className="rounded-[2px] border p-3"
            style={{
              borderColor: r.include && !complete ? "var(--pq-bronze)" : "var(--pq-ivory-line)",
              opacity: r.include ? 1 : 0.45,
            }}
            data-testid="ocr-review-row"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label className="flex min-w-0 items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={r.include}
                  onChange={(e) => set(r.key, { include: e.target.checked })}
                  className="h-4 w-4 accent-[var(--pq-bronze)]"
                  aria-label={t("journal.import.image.includeRow")}
                />
                {/* OCR text can be one long unbroken token — let it wrap anywhere
                    instead of pushing the card past a 390px viewport. */}
                <span className="min-w-0 font-mono [overflow-wrap:anywhere]" style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-ivory-mid)" }}>
                  {r.sourceText.slice(0, 90)}
                </span>
              </label>
              {r.include && !complete && (
                <span className="font-mono" style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-bronze)" }}>
                  {t("journal.import.image.fillBlanks")}
                </span>
              )}
            </div>
            {r.include && currencyConflict(r) && (
              <div className="mt-1 font-mono" style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-bronze)" }}>
                {t(`journal.import.image.${currencyConflict(r)}`)}
              </div>
            )}
            {r.flags.includes("amount_mismatch") && (
              <div className="mt-1 font-mono" style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-bronze)" }}>
                {t("journal.import.image.amountMismatch")}
              </div>
            )}
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {cell(r, "date", "", "text")}
              {cell(r, "time", "", "text")}
              {cell(r, "name", "", "text")}
              {cell(r, "code", "", "text")}
              <select
                value={r.values.side}
                onChange={(e) => setVal(r.key, "side", e.target.value)}
                aria-label={t("journal.import.image.col.side")}
                data-missing={r.values.side ? undefined : "true"}
                className={`${inputCls} bg-black`}
                style={{ borderColor: r.values.side ? "rgba(245,240,232,0.15)" : "var(--pq-bronze)" }}
              >
                <option value="">{t("journal.import.image.sideUnknown")}</option>
                <option value={SIDE_BUY}>{t("journal.import.image.sideBuy")}</option>
                <option value={SIDE_SELL}>{t("journal.import.image.sideSell")}</option>
              </select>
              {cell(r, "shares", "", "decimal")}
              {cell(r, "price", "", "decimal")}
              <select
                value={r.values.currency}
                onChange={(e) => setVal(r.key, "currency", e.target.value)}
                aria-label={t("journal.import.image.col.currency")}
                data-missing={r.values.currency ? undefined : "true"}
                className={`${inputCls} bg-black`}
                style={{ borderColor: r.values.currency ? "rgba(245,240,232,0.15)" : "var(--pq-bronze)" }}
              >
                <option value="">—</option>
                <option value="KRW">KRW</option>
                <option value="USD">USD</option>
              </select>
            </div>
            {r.tz === "ET" && (
              <div className="mt-1 font-mono" style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-ivory-dim)" }}>
                {t("journal.import.image.etNote")}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
