"use client";

/**
 * Holdings-screen capture → positions in one reviewed step
 * (docs/product/HOLDINGS_IMPORT_DESIGN.md). Opened from AddPositionModalV2.
 *
 *   captures → [읽기] → Tesseract.js in the browser (lib/fill-ocr/ocr.ts)
 *   → parseHoldingsScreen (only cells the screen proves are filled)
 *   → POST preview (names/codes only) → review: ticker, shares, avg cost,
 *     currency, current holding, per-row mode → consent → POST commit.
 *
 * The capture never leaves the device; the server gets JSON rows only.
 * Existing positions default to "replace" (덮어쓰기): the screen is the
 * broker's own current state, so merging it into an older record would
 * double-count. Rows are never sent until every non-skipped cell is filled.
 */

import * as React from "react";
import { toast } from "sonner";
import { useT } from "@/lib/locale";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { parseHoldingsScreen, type ParsedHolding } from "@/lib/fill-ocr/parse-holdings";
import type { ScreenType } from "@/lib/fill-ocr/parse";
import { OcrInputError, MAX_IMAGE_BYTES, openOcrSession } from "@/lib/fill-ocr/ocr";
import { IMAGE_ACCEPT, MAX_IMAGES_PER_PICK } from "@/components/journal/image-import-panel";
import { TickerSearch, type TickerSearchResult } from "@/components/shared/ticker-search";
import type {
  HoldingsCommitResponse,
  HoldingsExisting,
  HoldingsPreviewRow,
} from "@/lib/types";

export type HoldingMode = "replace" | "add" | "skip";
type Cur = "" | "KRW" | "USD";

export interface HoldingRow {
  key: string;
  fileName: string;
  sourceText: string;
  flags: string[];
  readName: string;
  readCode: string;
  hints: { shares?: string; avgCost?: string; name?: string; code?: string };
  shares: string;
  avgCost: string;
  currency: Cur;
  /** Currency read off the screen ("" = not proven). */
  screenCurrency: Cur;
  ticker: string;
  tickerName: string;
  tickerCurrency: string | null;
  status: "resolved" | "needs_confirm" | "needs_ticker";
  /** needs_confirm rows: the user ticked "same stock as on the capture". */
  confirmed: boolean;
  existing: HoldingsExisting | null;
  mode: HoldingMode;
}

interface FileNote {
  index: number;
  fileName: string;
  kind: "rejected" | "error" | "read";
  screenType?: ScreenType | "empty";
  errorCode?: string;
  rows?: number;
}

const v = (x: string | number | null | undefined) => (x == null ? "" : String(x));
const num = (s: string) => Number(s.replace(/,/g, "").trim());

export function rowFromHolding(h: ParsedHolding, fileName: string, i: number, fileIndex = 0): HoldingRow {
  return {
    key: `${fileIndex}:${fileName}#${i}`,
    fileName,
    sourceText: h.sourceText,
    flags: h.flags,
    readName: v(h.name.value),
    readCode: v(h.code.value),
    hints: {
      shares: h.shares.hint, avgCost: h.avgCost.hint,
      name: h.name.hint, code: h.code.hint,
    },
    shares: v(h.shares.value),
    avgCost: v(h.avgCost.value),
    currency: (h.currency ?? "") as Cur,
    screenCurrency: (h.currency ?? "") as Cur,
    ticker: "",
    tickerName: "",
    tickerCurrency: null,
    status: "needs_ticker",
    confirmed: false,
    existing: null,
    mode: "add",
  };
}

/** Same holding on two overlapping captures: merged only when everything
 * read is identical. Anything else stays as two rows for the user. */
export function mergeIdenticalReads(rows: HoldingRow[]): HoldingRow[] {
  const out: HoldingRow[] = [];
  const sig = (r: HoldingRow) =>
    [r.readCode || r.readName.replace(/\s+/g, ""), r.shares, r.avgCost, r.currency].join("|");
  for (const r of rows) {
    const id = r.readCode || r.readName;
    if (id && r.shares && r.avgCost && out.some((o) => sig(o) === sig(r))) continue;
    out.push(r);
  }
  return out;
}

export function applyPreview(r: HoldingRow, p: HoldingsPreviewRow | undefined): HoldingRow {
  if (!p) return r;
  const tickerCurrency = p.currency ?? null;
  // KRX stocks trade only in won, so a KRX ticker settles an unread
  // currency. A US ticker never does: Korean apps may show US holdings in ₩.
  const currency: Cur = r.currency || (tickerCurrency === "KRW" && p.status === "resolved" ? "KRW" : "");
  return {
    ...r,
    ticker: p.ticker ?? "",
    tickerName: p.name ?? "",
    tickerCurrency,
    status: p.status,
    confirmed: false,
    existing: p.existing,
    mode: p.existing ? "replace" : "add",
    currency,
  };
}

/** Rows whose resolved ticker repeats with different values: auto-merge the
 * identical ones, keep the rest for the user to settle. */
export function dropIdenticalTickerDuplicates(rows: HoldingRow[]): HoldingRow[] {
  const out: HoldingRow[] = [];
  for (const r of rows) {
    if (r.ticker && out.some((o) => o.ticker === r.ticker && o.shares === r.shares &&
        o.avgCost === r.avgCost && o.currency === r.currency && r.shares && r.avgCost)) continue;
    out.push(r);
  }
  return out;
}

export type RowIssue =
  | "ticker" | "confirm" | "shares" | "avgCost" | "currency" | "currencyMismatch" | "duplicate";

export function rowIssues(r: HoldingRow, all: HoldingRow[]): RowIssue[] {
  if (r.mode === "skip") return [];
  const out: RowIssue[] = [];
  if (!r.ticker || r.status === "needs_ticker") out.push("ticker");
  else if (r.status === "needs_confirm" && !r.confirmed) out.push("confirm");
  const s = num(r.shares);
  if (!r.shares.trim() || !(s > 0) || !Number.isFinite(s) || (r.currency === "KRW" && !Number.isInteger(s))) out.push("shares");
  const a = num(r.avgCost);
  if (!r.avgCost.trim() || !(a > 0) || !Number.isFinite(a)) out.push("avgCost");
  if (!r.currency) out.push("currency");
  else if (r.tickerCurrency && r.currency !== r.tickerCurrency) out.push("currencyMismatch");
  if (r.ticker && all.some((o) => o !== r && o.mode !== "skip" && o.ticker === r.ticker)) out.push("duplicate");
  return out;
}

export function commitPayload(rows: HoldingRow[]) {
  return rows
    .filter((r) => r.mode !== "skip")
    .map((r) => ({
      ticker: r.ticker,
      shares: num(r.shares),
      avg_cost: num(r.avgCost),
      currency: r.currency,
      mode: r.mode,
    }));
}

const inputCls =
  "w-full bg-transparent px-2 py-1 font-mono outline-none text-[var(--pq-ivory)] border rounded-[2px] focus:border-[var(--pq-bronze)]";
const small = { fontSize: "var(--pq-text-mono-sm)" } as const;

function fmtQty(n: number) {
  return n.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

export function HoldingsImportPanel({
  onDone,
  onCancel,
  /** Test seam: the OCR session factory (defaults to Tesseract.js). */
  openSession = openOcrSession,
}: {
  onDone: (result: HoldingsCommitResponse) => void;
  onCancel: () => void;
  openSession?: typeof openOcrSession;
}) {
  const t = useT();
  const [files, setFiles] = React.useState<File[]>([]);
  const [progress, setProgress] = React.useState<string | null>(null);
  const [notes, setNotes] = React.useState<FileNote[]>([]);
  const [rows, setRows] = React.useState<HoldingRow[]>([]);
  const [consent, setConsent] = React.useState(false);
  const [sending, setSending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const runId = React.useRef(0);

  const oversized = files.some((f) => f.size > MAX_IMAGE_BYTES);
  const canRead = files.length > 0 && !oversized && progress === null && !sending;
  const active = rows.filter((r) => r.mode !== "skip");
  const allReady = rows.every((r) => rowIssues(r, rows).length === 0);
  const canSend = consent && !sending && active.length > 0 && allReady;

  async function preview(reqRows: { name: string | null; code: string | null; currency: string | null }[]) {
    const res = await apiFetch<{ rows: HoldingsPreviewRow[] }>(API.holdingsImport.preview, {
      method: "POST",
      body: JSON.stringify({ rows: reqRows }),
      timeoutMs: 30_000,
    });
    return Array.isArray(res?.rows) ? res.rows : [];
  }

  async function read() {
    if (!canRead) return;
    const myRun = ++runId.current;
    setError(null);
    setNotes([]);
    setRows([]);
    setProgress(t("journal.import.image.loadingOcr"));
    let session;
    try {
      session = await openSession();
    } catch {
      setProgress(null);
      setError(t("journal.import.image.ocrLoadFailed"));
      return;
    }
    const nextNotes: FileNote[] = [];
    let nextRows: HoldingRow[] = [];
    try {
      for (let i = 0; i < files.length; i++) {
        const f = files[i];
        setProgress(t("journal.import.image.progress").replace("{i}", String(i + 1)).replace("{n}", String(files.length)));
        try {
          const parsed = parseHoldingsScreen(await session.read(f));
          if (parsed.screenType !== "holdings") {
            nextNotes.push({ index: i, fileName: f.name, kind: "rejected", screenType: parsed.screenType });
            continue;
          }
          if (parsed.rows.length === 0) {
            nextNotes.push({ index: i, fileName: f.name, kind: "rejected", screenType: "empty" });
            continue;
          }
          parsed.rows.forEach((h, k) => nextRows.push(rowFromHolding(h, f.name, k, i)));
          nextNotes.push({ index: i, fileName: f.name, kind: "read", rows: parsed.rows.length });
        } catch (err) {
          const code = err instanceof OcrInputError ? err.code : "unreadable";
          nextNotes.push({ index: i, fileName: f.name, kind: "error", errorCode: code });
          if (code === "timeout") break;
        }
      }
    } finally {
      await session.close();
    }
    if (myRun !== runId.current) return;
    nextRows = mergeIdenticalReads(nextRows);
    if (nextRows.length > 0) {
      setProgress(t("dashboard.portfolio.holdingsImport.resolving"));
      try {
        const p = await preview(nextRows.map((r) => ({
          name: r.readName || null, code: r.readCode || null, currency: r.currency || null,
        })));
        nextRows = dropIdenticalTickerDuplicates(nextRows.map((r, i) => applyPreview(r, p.find((x) => x.index === i))));
      } catch (err) {
        setError(err instanceof Error && err.message ? err.message : t("dashboard.portfolio.holdingsImport.previewFailed"));
      }
    }
    if (myRun !== runId.current) return;
    setNotes(nextNotes);
    setRows(nextRows);
    setProgress(null);
  }

  const patch = (key: string, p: Partial<HoldingRow>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...p } : r)));

  async function pickTicker(key: string, s: TickerSearchResult) {
    const bare = s.ticker.trim().toUpperCase().replace(/\.(KS|KQ)$/, "");
    try {
      const [p] = await preview([{ name: s.name ?? null, code: bare, currency: null }]);
      setRows((rs) => rs.map((r) => {
        if (r.key !== key) return r;
        const next = applyPreview({ ...r, currency: r.screenCurrency }, p ? { ...p, index: 0 } : undefined);
        // The user chose this stock — a fuzzy-match confirmation is not needed.
        return { ...next, confirmed: true, status: next.ticker ? (next.status === "needs_ticker" ? "needs_ticker" : "resolved") : "needs_ticker" };
      }));
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : t("dashboard.portfolio.holdingsImport.previewFailed"));
    }
  }

  async function send() {
    if (!canSend) return;
    setSending(true);
    setError(null);
    try {
      const result = await apiFetch<HoldingsCommitResponse>(API.holdingsImport.commit, {
        method: "POST",
        body: JSON.stringify({ consent: true, rows: commitPayload(rows) }),
        timeoutMs: 60_000,
      });
      if (!result || !Array.isArray(result.created)) {
        setError(t("journal.import.image.notSaved"));
        return;
      }
      const skippedByUser = rows.filter((r) => r.mode === "skip").length;
      const tier = result.skipped.filter((s) => s.reason === "TIER_LIMIT");
      const summary = t("dashboard.portfolio.holdingsImport.doneSummary")
        .replace("{created}", String(result.created.length))
        .replace("{replaced}", String(result.replaced.length))
        .replace("{added}", String(result.added.length))
        .replace("{skipped}", String(skippedByUser + result.skipped.filter((s) => s.reason !== "TIER_LIMIT").length));
      toast.success(summary);
      if (tier.length > 0) {
        toast.warning(t("dashboard.portfolio.holdingsImport.tierLimit")
          .replace("{n}", String(tier.length))
          .replace("{tickers}", tier.map((s) => s.ticker).join(", ")));
      }
      onDone(result);
    } catch (err) {
      const msg = err instanceof ApiError || err instanceof Error ? err.message : "";
      setError(msg || t("dashboard.portfolio.holdingsImport.saveFailed"));
    } finally {
      setSending(false);
    }
  }

  const noteText = (n: FileNote) => {
    if (n.kind === "read") return t("dashboard.portfolio.holdingsImport.noteRead").replace("{rows}", String(n.rows ?? 0));
    if (n.kind === "rejected") return t(`dashboard.portfolio.holdingsImport.screen.${n.screenType}`);
    return t(`journal.import.image.inputError.${n.errorCode}`);
  };
  const body = { fontSize: "var(--pq-text-body-sm)", lineHeight: 1.5, color: "var(--pq-ivory-mid)", wordBreak: "keep-all" as const };

  return (
    <div data-testid="holdings-import-panel">
      <p className="font-serif" style={{ ...body, margin: 0 }}>{t("dashboard.portfolio.holdingsImport.intro")}</p>
      <ul className="mt-3 space-y-1 font-serif" style={body}>
        <li>— {t("dashboard.portfolio.holdingsImport.guideScreen")}</li>
        <li>— {t("dashboard.portfolio.holdingsImport.guideColumns")}</li>
        <li>— {t("dashboard.portfolio.holdingsImport.guideReplace")}</li>
        <li>— {t("journal.import.image.guideLocal")}</li>
      </ul>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <input
          id="holdings-images"
          type="file"
          accept={IMAGE_ACCEPT}
          multiple
          disabled={progress !== null}
          onChange={(e) => {
            runId.current += 1;
            setFiles(Array.from(e.target.files ?? []).slice(0, MAX_IMAGES_PER_PICK));
            setRows([]);
            setNotes([]);
          }}
          className="sr-only"
          data-testid="holdings-image-input"
        />
        <label htmlFor="holdings-images" className="pq-ink-btn-ghost cursor-pointer px-4 text-pq-mono-sm uppercase tracking-[0.22em]">
          {t("journal.import.image.choose")}
        </label>
        <span className="font-mono truncate" style={{ ...small, color: "var(--pq-ivory-mid)" }}>
          {files.length === 0 ? t("journal.import.page.fileNone") : t("journal.import.image.chosen").replace("{n}", String(files.length))}
        </span>
        <button
          type="button"
          onClick={read}
          disabled={!canRead}
          aria-disabled={!canRead}
          className="pq-ink-btn-ghost px-4 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
          data-testid="holdings-read"
        >
          {progress ?? t("journal.import.image.read")}
        </button>
      </div>
      <div className="mt-2 font-mono" style={{ ...small, color: "var(--pq-ivory-dim)" }}>{t("journal.import.image.limits")}</div>
      {oversized && <div className="mt-1 font-mono" style={{ ...small, color: "var(--pq-error)" }}>{t("journal.import.image.tooLarge")}</div>}

      {notes.length > 0 && (
        <ul className="mt-3 space-y-1" data-testid="holdings-notes">
          {notes.map((n) => (
            <li key={`${n.index}:${n.fileName}`} className="font-mono [overflow-wrap:anywhere]" style={{ ...small, color: n.kind === "read" ? "var(--pq-ivory-mid)" : "var(--pq-bronze)" }}>
              {n.fileName} — {noteText(n)}
            </li>
          ))}
        </ul>
      )}

      {rows.length > 0 && (
        <>
          <p className="mt-4 font-serif" style={body}>{t("dashboard.portfolio.holdingsImport.reviewDesc")}</p>
          <div className="mt-3 space-y-3" data-testid="holdings-review-table">
            {rows.map((r) => (
              <HoldingReviewRow
                key={r.key}
                row={r}
                issues={rowIssues(r, rows)}
                onPatch={(p) => patch(r.key, p)}
                onPick={(s) => pickTicker(r.key, s)}
              />
            ))}
          </div>

          <label className="mt-5 flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-1 h-4 w-4 shrink-0 accent-[var(--pq-bronze)]"
              aria-label={t("dashboard.portfolio.holdingsImport.consentLabel")}
              data-testid="holdings-consent"
            />
            <span className="font-serif" style={body}>{t("dashboard.portfolio.holdingsImport.consentLabel")}</span>
          </label>
        </>
      )}

      {error && (
        <div className="mt-3 font-mono" style={{ ...small, color: "var(--pq-error)", whiteSpace: "pre-line" }} data-testid="holdings-error">
          {error}
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center justify-end gap-4">
        <button
          type="button"
          onClick={onCancel}
          className="font-mono uppercase"
          style={{ background: "transparent", border: "none", color: "var(--pq-ivory-dim)", fontSize: "var(--pq-text-eyebrow)", letterSpacing: "0.2em", cursor: "pointer", padding: 4 }}
        >
          {t("dashboard.portfolio.holdingsImport.back")}
        </button>
        {rows.length > 0 && (
          <button
            type="button"
            onClick={send}
            disabled={!canSend}
            aria-disabled={!canSend}
            className="pq-ink-btn-bronze inline-flex items-center px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
            data-testid="holdings-send"
          >
            {sending
              ? t("journal.import.page.submitting")
              : t("dashboard.portfolio.holdingsImport.save").replace("{n}", String(active.length))}
          </button>
        )}
      </div>
    </div>
  );
}

function HoldingReviewRow({
  row: r,
  issues,
  onPatch,
  onPick,
}: {
  row: HoldingRow;
  issues: RowIssue[];
  onPatch: (p: Partial<HoldingRow>) => void;
  onPick: (s: TickerSearchResult) => void;
}) {
  const t = useT();
  const [query, setQuery] = React.useState("");
  const [changing, setChanging] = React.useState(false);
  const skip = r.mode === "skip";
  const border = (bad: boolean) => ({ borderColor: bad && !skip ? "var(--pq-bronze)" : "rgba(245,240,232,0.15)" });
  const showSearch = changing || !r.ticker || r.status === "needs_ticker";

  return (
    <div
      className="rounded-[2px] border p-3"
      style={{ borderColor: !skip && issues.length ? "var(--pq-bronze)" : "var(--pq-ivory-line)", opacity: skip ? 0.5 : 1 }}
      data-testid="holdings-review-row"
    >
      <div className="font-mono [overflow-wrap:anywhere]" style={{ ...small, color: "var(--pq-ivory-dim)" }}>
        {r.sourceText.slice(0, 90)}
      </div>

      {/* Stock */}
      <div className="mt-2">
        {r.ticker && !changing && (
          <div className="flex flex-wrap items-center gap-2 font-mono" style={{ ...small, color: "var(--pq-ivory)" }}>
            <span data-testid="holdings-ticker">{r.tickerName ? `${r.tickerName} · ` : ""}{r.ticker}</span>
            <button type="button" onClick={() => { setChanging(true); setQuery(""); }} className="underline" style={{ color: "var(--pq-bronze)", background: "none", border: "none", cursor: "pointer" }}>
              {t("dashboard.portfolio.holdingsImport.changeTicker")}
            </button>
          </div>
        )}
        {r.status === "needs_confirm" && r.ticker && !changing && (
          <label className="mt-1 flex items-start gap-2 cursor-pointer font-mono" style={{ ...small, color: "var(--pq-bronze)" }}>
            <input
              type="checkbox"
              checked={r.confirmed}
              onChange={(e) => onPatch({ confirmed: e.target.checked })}
              className="mt-0.5 h-4 w-4 accent-[var(--pq-bronze)]"
              data-testid="holdings-confirm"
            />
            <span>
              {t("dashboard.portfolio.holdingsImport.confirmMatch").replace("{read}", r.readName || r.readCode || "?")}
            </span>
          </label>
        )}
        {showSearch && (
          <div data-missing={!skip && issues.includes("ticker") ? "true" : undefined}>
            <TickerSearch
              value={query}
              onChange={setQuery}
              onPick={(s) => { setChanging(false); onPick(s); }}
              placeholder={r.readName || r.hints.name || r.readCode || r.hints.code || t("dashboard.portfolio.holdingsImport.tickerPlaceholder")}
              ariaLabel={t("dashboard.portfolio.holdingsImport.col.ticker")}
              limit={6}
              inputClassName={`${inputCls}`}
              inputStyle={border(issues.includes("ticker"))}
            />
          </div>
        )}
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <input
          value={r.shares}
          onChange={(e) => onPatch({ shares: e.target.value })}
          placeholder={r.hints.shares ?? t("dashboard.portfolio.holdingsImport.col.shares")}
          aria-label={t("dashboard.portfolio.holdingsImport.col.shares")}
          inputMode="decimal"
          data-missing={!skip && issues.includes("shares") ? "true" : undefined}
          className={inputCls}
          style={border(issues.includes("shares"))}
        />
        <input
          value={r.avgCost}
          onChange={(e) => onPatch({ avgCost: e.target.value })}
          placeholder={r.hints.avgCost ?? t("dashboard.portfolio.holdingsImport.col.avgCost")}
          aria-label={t("dashboard.portfolio.holdingsImport.col.avgCost")}
          inputMode="decimal"
          data-missing={!skip && issues.includes("avgCost") ? "true" : undefined}
          className={inputCls}
          style={border(issues.includes("avgCost"))}
        />
        <select
          value={r.currency}
          onChange={(e) => onPatch({ currency: e.target.value as Cur })}
          aria-label={t("dashboard.portfolio.holdingsImport.col.currency")}
          data-missing={!skip && (issues.includes("currency") || issues.includes("currencyMismatch")) ? "true" : undefined}
          className={`${inputCls} bg-black`}
          style={border(issues.includes("currency") || issues.includes("currencyMismatch"))}
        >
          <option value="">{t("dashboard.portfolio.holdingsImport.col.currency")}</option>
          <option value="KRW">KRW</option>
          <option value="USD">USD</option>
        </select>
        <select
          value={r.mode}
          onChange={(e) => onPatch({ mode: e.target.value as HoldingMode })}
          aria-label={t("dashboard.portfolio.holdingsImport.col.mode")}
          className={`${inputCls} bg-black`}
          style={border(false)}
          data-testid="holdings-mode"
        >
          {r.existing ? (
            <>
              <option value="replace">{t("dashboard.portfolio.holdingsImport.mode.replace")}</option>
              <option value="add">{t("dashboard.portfolio.holdingsImport.mode.add")}</option>
            </>
          ) : (
            <option value="add">{t("dashboard.portfolio.holdingsImport.mode.new")}</option>
          )}
          <option value="skip">{t("dashboard.portfolio.holdingsImport.mode.skip")}</option>
        </select>
      </div>

      <div className="mt-2 font-mono" style={{ ...small, color: "var(--pq-ivory-mid)" }} data-testid="holdings-existing">
        {r.existing
          ? t("dashboard.portfolio.holdingsImport.current")
            .replace("{shares}", fmtQty(r.existing.shares))
            .replace("{avg}", fmtQty(r.existing.avg_cost))
            .replace("{currency}", r.existing.currency)
          : t("dashboard.portfolio.holdingsImport.notHeld")}
      </div>
      {!skip && issues.length > 0 && (
        <ul className="mt-1 font-mono" style={{ ...small, color: "var(--pq-bronze)" }}>
          {issues.map((i) => <li key={i}>· {t(`dashboard.portfolio.holdingsImport.issue.${i}`)}</li>)}
        </ul>
      )}
      {r.flags.includes("amount_mismatch") && (
        <div className="mt-1 font-mono" style={{ ...small, color: "var(--pq-bronze)" }}>
          {t("dashboard.portfolio.holdingsImport.amountMismatch")}
        </div>
      )}
      {r.flags.includes("foreign_in_krw") && (
        <div className="mt-1 font-mono" style={{ ...small, color: "var(--pq-bronze)" }}>
          {t("dashboard.portfolio.holdingsImport.foreignInKrw")}
        </div>
      )}
    </div>
  );
}
