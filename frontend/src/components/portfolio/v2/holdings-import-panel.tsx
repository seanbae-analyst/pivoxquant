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
import Link from "next/link";
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
  /** The user set `currency` by hand — a later ticker pick keeps it. */
  currencyByUser?: boolean;
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

/** Same holding on two overlapping captures (same name/code and currency):
 * merged when no cell contradicts — equal values, or one side empty with no
 * reading (or a hint equal to the other side's proven value). A capture that
 * read "2" for sure and one that only hinted "2" become one row with 2.
 * Anything that disagrees stays as two rows for the user. */
export function mergeIdenticalReads(rows: HoldingRow[]): HoldingRow[] {
  const out: HoldingRow[] = [];
  const id = (r: HoldingRow) => r.readCode || r.readName.replace(/\s+/g, "");
  const fits = (a: HoldingRow, b: HoldingRow, k: "shares" | "avgCost") => {
    if (a[k] && b[k]) return a[k] === b[k];
    if (!a[k] && !b[k]) return (a.hints[k] ?? "") === (b.hints[k] ?? "") || !a.hints[k] || !b.hints[k];
    const [filled, empty] = a[k] ? [a, b] : [b, a];
    return !empty.hints[k] || empty.hints[k] === filled[k];
  };
  for (const r of rows) {
    const i = id(r) ? out.findIndex((o) => id(o) === id(r) && o.currency === r.currency &&
      fits(o, r, "shares") && fits(o, r, "avgCost")) : -1;
    if (i < 0) { out.push(r); continue; }
    const o = out[i];
    out[i] = {
      ...o,
      shares: o.shares || r.shares,
      avgCost: o.avgCost || r.avgCost,
      // Per key: rowFromHolding sets every key, often to undefined, so a
      // spread would let an empty key wipe the other capture's reading.
      hints: {
        shares: o.hints.shares ?? r.hints.shares, avgCost: o.hints.avgCost ?? r.hints.avgCost,
        name: o.hints.name ?? r.hints.name, code: o.hints.code ?? r.hints.code,
      },
      flags: [...new Set([...o.flags, ...r.flags])],
    };
  }
  return out;
}

export function applyPreview(r: HoldingRow, p: HoldingsPreviewRow | undefined): HoldingRow {
  if (!p) return r;
  const tickerCurrency = p.currency ?? null;
  // KRX stocks trade only in won, so a KRX ticker settles an unread
  // currency. A US ticker never does: Korean apps may show US holdings in ₩.
  const currency: Cur = r.currency || (tickerCurrency === "KRW" && p.status === "resolved" ? "KRW" : "");
  // A US stock shown in won (Toss 내 투자 / 자세히 보기 cropped above its
  // 해외주식 header): a won average — worked out or printed, cross-checked
  // against won 원금 or not — is not the dollar cost basis.
  // (A currency the user set by hand is theirs to settle — currencyMismatch.)
  if (tickerCurrency === "USD" && r.currency === "KRW" && !r.currencyByUser && (r.avgCost || r.hints.avgCost)) {
    return {
      ...applyPreview({ ...r, currency: "", avgCost: "", hints: { ...r.hints, avgCost: undefined },
        flags: [...r.flags.filter((f) => f !== "derived_avg" && f !== "cross_checked" && f !== "foreign_in_krw"), "foreign_in_krw"] }, p),
    };
  }
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

/** The user changes a row's currency. An average read in the other currency
 * is not a price in the new one, so it is cleared (with its reading);
 * choosing a currency for a row that had none keeps what is there. */
export function currencyPatch(r: HoldingRow, currency: Cur): Partial<HoldingRow> {
  if (r.currency && currency !== r.currency) {
    return { currency, avgCost: "", hints: { ...r.hints, avgCost: undefined }, currencyByUser: true };
  }
  return { currency, currencyByUser: true };
}

/** The user picked a ticker for a row. The row is re-resolved against it,
 * but what the user decided stays: a skipped row stays skipped, and a
 * currency they chose is not reset to the screen's. */
export function pickedTicker(r: HoldingRow, p: HoldingsPreviewRow | undefined): HoldingRow {
  const next = applyPreview({ ...r, currency: r.currencyByUser ? r.currency : r.screenCurrency }, p);
  return {
    ...next,
    mode: r.mode === "skip" ? "skip" : next.mode,
    // The user chose this stock — a fuzzy-match confirmation is not needed.
    confirmed: true,
    status: next.ticker ? (next.status === "needs_ticker" ? "needs_ticker" : "resolved") : "needs_ticker",
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

/** A usable average cost. No stock trades under 100원, and a won figure with
 * three or more decimals ("170.850") is "170,850" misread (comma as dot). */
export function avgCostOk(s: string, currency: Cur): boolean {
  const a = num(s);
  if (!s.trim() || !(a > 0) || !Number.isFinite(a)) return false;
  // 70,850.33원처럼 평단을 소수 둘째 자리까지 찍는 증권사가 있어 1,000원 이상의 소수는 받는다.
  // 1,000원 미만의 소수("170.85")나 소수 셋째 자리("170.850")는 쉼표를 점으로 잘못 읽은 것이다.
  if (currency !== "KRW") return true;
  if (a < 100 || /\.\d{3,}\s*$/.test(s.trim())) return false;
  return Number.isInteger(a) || a >= 1000;
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
  if (!avgCostOk(r.avgCost, r.currency)) out.push("avgCost");
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
  /** Omit to hide the back button (onboarding has nowhere to go back to). */
  onCancel?: () => void;
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
      setRows((rs) => rs.map((r) => (r.key === key ? pickedTicker(r, p ? { ...p, index: 0 } : undefined) : r)));
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

  const hasExisting = rows.some((r) => r.existing && r.mode !== "skip");

  return (
    <div data-testid="holdings-import-panel">
      <p className="font-serif" style={{ ...body, margin: 0 }}>{t("dashboard.portfolio.holdingsImport.intro")}</p>

      {/* 1 · which screen */}
      <StepHead n={1} label={t("dashboard.portfolio.holdingsImport.step1")} />
      <p className="font-serif" style={{ ...body, margin: 0, color: "var(--pq-ivory)" }}>
        {t("dashboard.portfolio.holdingsImport.step1Body")}
      </p>
      <CaptureGuide />

      {/* 2 · upload */}
      <StepHead n={2} label={t("dashboard.portfolio.holdingsImport.step2")} />
      <div className="flex flex-wrap items-center gap-3">
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
      <div className="mt-2 font-mono" style={{ ...small, color: "var(--pq-ivory-dim)" }}>
        {t("journal.import.image.limits")}
        <br />
        {t("dashboard.portfolio.holdingsImport.localNote")}
      </div>
      {oversized && <div className="mt-1 font-mono" style={{ ...small, color: "var(--pq-error)" }}>{t("journal.import.image.tooLarge")}</div>}

      {notes.length > 0 && (
        <ul className="mt-3 space-y-1" data-testid="holdings-notes">
          {notes.map((n) => (
            <li key={`${n.index}:${n.fileName}`} className="font-mono [overflow-wrap:anywhere]" style={{ ...small, color: n.kind === "read" ? "var(--pq-ivory-mid)" : "var(--pq-bronze)" }}>
              {n.fileName} — {noteText(n)}
            </li>
          ))}
          {/* A fill screen belongs to the journal's image import — say where,
              as a link (the journal side already links back here). */}
          {notes.some((n) => n.kind === "rejected" && n.screenType === "fills") && (
            <li>
              <Link
                href="/journal/import?tab=image"
                data-testid="holdings-fills-link"
                className="font-mono"
                style={{ ...small, color: "var(--pq-bronze)", textDecoration: "underline", textUnderlineOffset: 3 }}
              >
                {t("dashboard.portfolio.holdingsImport.fillsLink")}
              </Link>
            </li>
          )}
        </ul>
      )}

      {rows.length > 0 && (
        <>
          {/* 3 · review and save */}
          <StepHead n={3} label={t("dashboard.portfolio.holdingsImport.step3")} />
          <p className="font-serif" style={{ ...body, margin: 0 }}>{t("dashboard.portfolio.holdingsImport.reviewDesc")}</p>
          {hasExisting && (
            <p className="mt-1 font-serif" style={{ ...body, margin: 0 }} data-testid="holdings-replace-note">
              {t("dashboard.portfolio.holdingsImport.guideReplace")}
            </p>
          )}
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
        {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="font-mono uppercase"
          style={{ background: "transparent", border: "none", color: "var(--pq-ivory-dim)", fontSize: "var(--pq-text-eyebrow)", letterSpacing: "0.2em", cursor: "pointer", padding: 4 }}
        >
          {t("dashboard.portfolio.holdingsImport.back")}
        </button>
        )}
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

/** Numbered step heading — the panel reads top to bottom as 1 · 2 · 3. */
function StepHead({ n, label }: { n: number; label: string }) {
  return (
    <div
      className="mt-5 mb-2 font-mono uppercase tracking-[0.18em]"
      style={{ ...small, color: "var(--pq-bronze)" }}
    >
      {n} · {label}
    </div>
  );
}

/** Broker-specific tips, folded away — the one line above is all most
 * users need. Toss 자세히 보기 carries a small drawn example of the table. */
function CaptureGuide() {
  const t = useT();
  const k = (s: string) => t(`dashboard.portfolio.holdingsImport.shot.${s}`);
  const text = { fontSize: "var(--pq-text-body-sm)", lineHeight: 1.5, color: "var(--pq-ivory-mid)", wordBreak: "keep-all" as const };
  const cell = { padding: "4px 5px", textAlign: "right" as const, whiteSpace: "nowrap" as const };
  const hl = { outline: "1.5px solid var(--pq-bronze)", outlineOffset: -2 };
  const dim = { color: "var(--pq-ivory-dim)", fontSize: "var(--pq-text-eyebrow-sm)" };
  const box = { borderColor: "var(--pq-ivory-line)" };
  const summary = { ...small, color: "var(--pq-ivory-mid)", cursor: "pointer" };
  return (
    <div className="mt-2 space-y-2" data-testid="holdings-capture-guide">
      <details className="rounded-[2px] border px-3 py-2" style={box}>
        <summary className="font-mono" style={summary}>{k("tossToggle")}</summary>
        <p className="mt-2 font-serif" style={{ ...text, margin: 0, color: "var(--pq-ivory)" }}>{k("toss")}</p>
        <figure className="mt-2" style={{ margin: 0 }}>
          <div className="overflow-x-auto">
            <table className="font-mono" style={{ fontSize: "var(--pq-text-mono-xs)", lineHeight: 1.45, borderCollapse: "collapse", color: "var(--pq-ivory)" }} aria-hidden="true">
              <thead>
                <tr style={{ color: "var(--pq-ivory-dim)" }}>
                  <td style={{ ...cell, textAlign: "left" }}>{k("colName")}</td>
                  <td style={cell}>{k("colAvg")}</td>
                  <td style={cell}>{k("colTotal")}</td>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderTop: "1px solid var(--pq-ivory-line)" }}>
                  <td style={{ ...cell, textAlign: "left" }}>삼성전자<div style={dim}>15주</div></td>
                  <td style={{ ...cell, ...hl }}>272,000<div style={dim}>{k("cur")} 270,500</div></td>
                  <td style={cell}>4,048,149<div style={{ ...dim, ...hl, color: "var(--pq-ivory)" }}>{k("cost")} 4,080,000</div></td>
                </tr>
              </tbody>
            </table>
          </div>
          <figcaption className="mt-1 font-mono" style={{ ...small, color: "var(--pq-ivory-dim)" }}>{k("exampleCaption")}</figcaption>
        </figure>
        <p className="mt-2 font-serif" style={{ ...text, margin: 0 }}>{k("tossAlt")}</p>
      </details>
      <details className="rounded-[2px] border px-3 py-2" style={box}>
        <summary className="font-mono" style={summary}>{k("foreignToggle")}</summary>
        <p className="mt-2 font-serif" style={{ ...text, margin: 0 }}>{t("dashboard.portfolio.holdingsImport.guideForeign")}</p>
      </details>
    </div>
  );
}

/** A labelled field with its example, and — when OCR read a value it could
 * not prove — a one-tap button to use that reading. */
function Field({ help, hint, empty, onUse, valid, children }: {
  help: string; hint?: string; empty: boolean; onUse: (v: string) => void;
  /** The same check the row applies — a reading that fails it is not offered. */
  valid?: (v: string) => boolean;
  children: React.ReactNode;
}) {
  const t = useT();
  const clean = hint?.replace(/[^\d.,$]/g, "").replace(/^\$/, "").replace(/,/g, "");
  return (
    <label className="block">
      <span className="block font-mono" style={{ ...small, color: "var(--pq-ivory-dim)", wordBreak: "keep-all" }}>{help}</span>
      {children}
      {empty && clean && /^\d+(\.\d+)?$/.test(clean) && (valid?.(clean) ?? true) && (
        <button
          type="button"
          onClick={(e) => { e.preventDefault(); onUse(clean); }}
          className="mt-1 underline font-mono"
          style={{ ...small, color: "var(--pq-bronze)", background: "none", border: "none", cursor: "pointer", padding: 0 }}
          data-testid="holdings-use-read"
        >
          {t("dashboard.portfolio.holdingsImport.help.useRead").replace("{v}", clean)}
        </button>
      )}
    </label>
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
            <span className="block font-mono" style={{ ...small, color: "var(--pq-ivory-dim)", wordBreak: "keep-all" }}>
              {t("dashboard.portfolio.holdingsImport.help.ticker")}
            </span>
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

      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4 items-end">
        <Field help={t("dashboard.portfolio.holdingsImport.help.shares")} hint={r.hints.shares} empty={!r.shares} onUse={(v) => onPatch({ shares: v })}>
          <input
            value={r.shares}
            onChange={(e) => onPatch({ shares: e.target.value })}
            placeholder={t("dashboard.portfolio.holdingsImport.col.shares")}
            aria-label={t("dashboard.portfolio.holdingsImport.col.shares")}
            inputMode="decimal"
            data-missing={!skip && issues.includes("shares") ? "true" : undefined}
            className={inputCls}
            style={border(issues.includes("shares"))}
          />
        </Field>
        <Field help={t("dashboard.portfolio.holdingsImport.help.avgCost")} hint={r.hints.avgCost} empty={!r.avgCost} onUse={(v) => onPatch({ avgCost: v })} valid={(v) => avgCostOk(v, r.currency)}>
          <input
            value={r.avgCost}
            onChange={(e) => onPatch({ avgCost: e.target.value })}
            placeholder={t("dashboard.portfolio.holdingsImport.col.avgCost")}
            aria-label={t("dashboard.portfolio.holdingsImport.col.avgCost")}
            inputMode="decimal"
            data-missing={!skip && issues.includes("avgCost") ? "true" : undefined}
            className={inputCls}
            style={border(issues.includes("avgCost"))}
          />
        </Field>
        <select
          value={r.currency}
          onChange={(e) => onPatch(currencyPatch(r, e.target.value as Cur))}
          aria-label={t("dashboard.portfolio.holdingsImport.help.currency")}
          title={t("dashboard.portfolio.holdingsImport.help.currency")}
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
