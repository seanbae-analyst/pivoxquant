"use client";

/**
 * Image tab of /journal/import — broker fill-screen captures → pending fills.
 *
 * docs/product/SCREENSHOT_IMPORT_DESIGN.md. The capture NEVER leaves the
 * device: Tesseract.js reads it in the browser (lib/fill-ocr/ocr.ts), the
 * rule parser (lib/fill-ocr/parse.ts) fills only the cells it can prove, and
 * the user types the rest in <OcrReviewTable />. Only the finished rows are
 * sent (JSON) and they land in the pending inbox like any other import.
 *
 *   - Several captures can be picked; they are read one after another in one
 *     OCR session. Overlapping rows fall out as `duplicate` server-side.
 *   - Holdings / open-order / other screens are named and skipped.
 *   - The broker picker only labels the batch; parsing is the same for all.
 *   - Menu paths per broker are NOT listed: they have not been checked on real
 *     devices (TODO: verify with real captures, then add them to the guide).
 */

import { useRef, useState } from "react";
import { useT } from "@/lib/locale";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { Caption, FieldLabel } from "@/components/ui/editorial";
import { parseFillScreen, type ScreenType } from "@/lib/fill-ocr/parse";
import { OcrInputError, MAX_IMAGE_BYTES, openOcrSession } from "@/lib/fill-ocr/ocr";
import {
  OcrReviewTable,
  rowComplete,
  rowFromParsed,
  rowPayload,
  type ReviewRow,
} from "@/components/journal/ocr-review-table";
import type { ImportCreateResponse } from "@/lib/types";

export const IMAGE_ACCEPT = "image/png,image/jpeg,image/webp";
export const MAX_IMAGES_PER_PICK = 10;

const BROKERS = ["unknown", "kis", "kiwoom", "toss", "mirae", "samsung", "nh", "overseas"] as const;
type Broker = (typeof BROKERS)[number];

interface FileNote {
  index: number;
  fileName: string;
  kind: "rejected" | "error" | "read";
  screenType?: ScreenType | "empty";
  errorCode?: string;
  rows?: number;
  excluded?: number;
}

export function ImageImportPanel({
  consent,
  onResult,
  /** Test seam: the OCR session factory (defaults to Tesseract.js). */
  openSession = openOcrSession,
}: {
  consent: boolean;
  onResult: (result: ImportCreateResponse) => void;
  openSession?: typeof openOcrSession;
}) {
  const t = useT();
  const [broker, setBroker] = useState<Broker>("unknown");
  const [files, setFiles] = useState<File[]>([]);
  const [progress, setProgress] = useState<string | null>(null);
  const [notes, setNotes] = useState<FileNote[]>([]);
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // A newer pick or read makes an in-flight run stale: its results are dropped.
  const runId = useRef(0);

  const oversized = files.some((f) => f.size > MAX_IMAGE_BYTES);
  const canRead = files.length > 0 && !oversized && progress === null && !sending;
  const included = rows.filter((r) => r.include);
  const canSend = consent && !sending && included.length > 0 && included.every(rowComplete);

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
    const nextRows: ReviewRow[] = [];
    try {
      for (let i = 0; i < files.length; i++) {
        const f = files[i];
        setProgress(
          t("journal.import.image.progress").replace("{i}", String(i + 1)).replace("{n}", String(files.length)),
        );
        try {
          const words = await session.read(f);
          const parsed = parseFillScreen(words);
          if (parsed.screenType !== "fills") {
            nextNotes.push({ index: i, fileName: f.name, kind: "rejected", screenType: parsed.screenType });
            continue;
          }
          if (parsed.rows.length === 0) {
            nextNotes.push({ index: i, fileName: f.name, kind: "rejected", screenType: "empty" });
            continue;
          }
          parsed.rows.forEach((row, k) => nextRows.push(rowFromParsed(row, f.name, k, i)));
          nextNotes.push({ index: i, fileName: f.name, kind: "read", rows: parsed.rows.length, excluded: parsed.excluded.length });
        } catch (err) {
          const code = err instanceof OcrInputError ? err.code : "unreadable";
          nextNotes.push({ index: i, fileName: f.name, kind: "error", errorCode: code });
          if (code === "timeout") break; // the workers were terminated
        }
      }
    } finally {
      await session.close();
    }
    if (myRun !== runId.current) return;
    setNotes(nextNotes);
    setRows(nextRows);
    setProgress(null);
  }

  async function send() {
    if (!canSend) return;
    setSending(true);
    setError(null);
    try {
      const result = await apiFetch<ImportCreateResponse>(API.imports.image, {
        method: "POST",
        body: JSON.stringify({ consent: true, broker, rows: included.map(rowPayload) }),
        timeoutMs: 60_000,
      });
      // Demo mode answers {ok:true} with no batch — keep the reviewed rows.
      if (!result || !Array.isArray(result.pending)) {
        setError(t("journal.import.image.notSaved"));
        return;
      }
      setRows([]);
      setNotes([]);
      setFiles([]);
      onResult(result);
    } catch (err) {
      const msg = err instanceof ApiError || err instanceof Error ? err.message : "";
      // Every row skipped (e.g. currency mismatch) → the reasons are in the body.
      const skipped = err instanceof ApiError && Array.isArray(err.body?.skipped)
        ? (err.body.skipped as { reason?: string; snippet?: string }[])
        : [];
      const reasons = skipped.map((x) => `· ${x.reason ?? ""}${x.snippet ? ` — ${x.snippet}` : ""}`);
      setError([msg || t("journal.page.loadFailure"), ...reasons].join("\n"));
    } finally {
      setSending(false);
    }
  }

  const bodyStyle = {
    fontSize: "var(--pq-text-body-sm)",
    lineHeight: 1.5,
    color: "var(--pq-ivory-soft)",
    wordBreak: "keep-all" as const,
  };
  const noteText = (n: FileNote) => {
    if (n.kind === "read")
      return t("journal.import.image.noteRead")
        .replace("{rows}", String(n.rows ?? 0))
        .replace("{excluded}", String(n.excluded ?? 0));
    if (n.kind === "rejected") return t(`journal.import.image.screen.${n.screenType}`);
    return t(`journal.import.image.inputError.${n.errorCode}`);
  };

  return (
    <div className="mt-5" data-testid="image-import-panel">
      {/* Capture guide — which screen, which columns, what a good capture looks like. */}
      <FieldLabel tone="bronze">{t("journal.import.image.guideTitle")}</FieldLabel>
      <Caption className="mt-1">{t("journal.import.image.guideScreen")}</Caption>
      <ul className="mt-2 space-y-1 font-serif" style={bodyStyle}>
        <li>— {t("journal.import.image.guideRequired")}</li>
        <li>— {t("journal.import.image.guideOptional")}</li>
        <li>— {t("journal.import.image.guideWhole")}</li>
        <li>— {t("journal.import.image.guideSharp")}</li>
        <li>— {t("journal.import.image.guideFilter")}</li>
        <li>— {t("journal.import.image.guideMulti")}</li>
        <li>— {t("journal.import.image.guideLocal")}</li>
      </ul>

      <div className="mt-4">
        <label htmlFor="image-broker">
          <FieldLabel tone="bronze">{t("journal.import.image.brokerLabel")}</FieldLabel>
        </label>
        <select
          id="image-broker"
          value={broker}
          onChange={(e) => setBroker(e.target.value as Broker)}
          className="mt-2 block bg-transparent px-3 py-2 font-mono outline-none text-[var(--pq-ivory)] border border-[rgba(245,240,232,0.15)] rounded-[2px] focus:border-[var(--pq-bronze)]"
          style={{ fontSize: "var(--pq-text-mono-sm)" }}
        >
          {BROKERS.map((b) => (
            <option key={b} value={b} className="bg-black">
              {t(`journal.import.image.brokers.${b}`)}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <input
          id="import-images"
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
          data-testid="image-input"
        />
        <label
          htmlFor="import-images"
          className="pq-ink-btn-ghost cursor-pointer px-4 text-pq-mono-sm uppercase tracking-[0.22em]"
        >
          {t("journal.import.image.choose")}
        </label>
        <span className="font-mono truncate" style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-ivory-mid)" }}>
          {files.length === 0
            ? t("journal.import.page.fileNone")
            : t("journal.import.image.chosen").replace("{n}", String(files.length))}
        </span>
        <button
          type="button"
          onClick={read}
          disabled={!canRead}
          aria-disabled={!canRead}
          className="pq-ink-btn-ghost px-4 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
          data-testid="image-read"
        >
          {progress ?? t("journal.import.image.read")}
        </button>
      </div>
      <Caption className="mt-2">{t("journal.import.image.limits")}</Caption>
      {oversized && (
        <Caption className="mt-1">
          <span style={{ color: "var(--pq-error)" }}>{t("journal.import.image.tooLarge")}</span>
        </Caption>
      )}

      {notes.length > 0 && (
        <ul className="mt-3 space-y-1" data-testid="image-notes">
          {notes.map((n) => (
            <li key={`${n.index}:${n.fileName}`} className="font-mono" style={{ fontSize: "var(--pq-text-mono-sm)", color: n.kind === "read" ? "var(--pq-ivory-mid)" : "var(--pq-bronze)" }}>
              {n.fileName} — {noteText(n)}
            </li>
          ))}
        </ul>
      )}

      {rows.length > 0 && (
        <>
          <Caption className="mt-4">{t("journal.import.image.reviewDesc")}</Caption>
          <OcrReviewTable rows={rows} onChange={setRows} />
          <div className="mt-5 flex items-center gap-3">
            <button
              type="button"
              onClick={send}
              disabled={!canSend}
              aria-disabled={!canSend}
              className="pq-ink-btn-bronze inline-flex items-center px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
              data-testid="image-send"
            >
              {sending ? t("journal.import.page.submitting") : t("journal.import.image.send")}
            </button>
          </div>
        </>
      )}
      {error && (
        <Caption className="mt-3">
          <span style={{ color: "var(--pq-error)", whiteSpace: "pre-line" }} data-testid="image-error">{error}</span>
        </Caption>
      )}
    </div>
  );
}
