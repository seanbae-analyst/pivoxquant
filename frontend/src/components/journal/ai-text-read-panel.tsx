"use client";

/**
 * Text tab of /journal/import — an AI read of a pasted fill notification the
 * server's text parser cannot read (services/imports/text_parser.py).
 *
 * Lines carrying an account number or customer name are dropped here before
 * anything is sent (lib/fill-ocr/mask.ts); the rows that come back go through
 * the same review table and the same POST /image validation as capture rows,
 * labelled `origin: "text"` so the batch keeps the text source.
 */
import { useState } from "react";
import { useT } from "@/lib/locale";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { Caption } from "@/components/ui/editorial";
import { dropReason } from "@/lib/fill-ocr/mask";
import { fillFromAi, type AiFillRow, type AiReadScreen } from "@/lib/ai-read";
import { AiReadOffer } from "@/components/ui/ai-read-offer";
import { AiContentBadge } from "@/components/ui/ai-content-badge";
import { OcrReviewTable, rowComplete, rowFromParsed, rowPayload, type ReviewRow } from "@/components/journal/ocr-review-table";
import type { ImportCreateResponse } from "@/lib/types";

/** Pasted text → what may be sent: lines that must not leave are dropped. */
export function maskPastedText(text: string): string {
  return text.split(/\r?\n/).filter((l) => l.trim() !== "" && dropReason(l) === null).join("\n");
}

export function AiTextReadPanel({
  text,
  consent,
  onResult,
}: {
  text: string;
  consent: boolean;
  onResult: (result: ImportCreateResponse) => void;
}) {
  const t = useT();
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const included = rows.filter((r) => r.include);
  const canSend = consent && !sending && included.length > 0 && included.every(rowComplete);

  function onScreens(screens: AiReadScreen<AiFillRow>[]) {
    const next = screens.flatMap((s) => s.rows.map((r, j) => rowFromParsed(fillFromAi(r), "text", j)));
    setError(next.length === 0 ? t("aiRead.noRows") : null);
    setRows(next);
  }

  async function send() {
    if (!canSend) return;
    setSending(true);
    setError(null);
    try {
      const result = await apiFetch<ImportCreateResponse>(API.imports.image, {
        method: "POST",
        body: JSON.stringify({ consent: true, origin: "text", rows: included.map(rowPayload) }),
        timeoutMs: 60_000,
      });
      if (!result || !Array.isArray(result.pending)) {
        setError(t("journal.import.image.notSaved"));
        return;
      }
      setRows([]);
      onResult(result);
    } catch (err) {
      const msg = err instanceof ApiError || err instanceof Error ? err.message : "";
      setError(msg || t("journal.page.loadFailure"));
    } finally {
      setSending(false);
    }
  }

  return (
    <div data-testid="ai-text-read-panel">
      <AiReadOffer<AiFillRow>
        kind="fills"
        texts={[maskPastedText(text)]}
        onScreens={onScreens}
        title={t("aiRead.textTitle")}
        body={t("aiRead.textBody")}
      />
      {rows.length > 0 && (
        <>
          <div className="mt-4 flex items-center gap-2">
            <AiContentBadge />
            <Caption>{t("aiRead.applied")}</Caption>
          </div>
          <OcrReviewTable rows={rows} onChange={setRows} />
          <div className="mt-4">
            <button
              type="button"
              onClick={send}
              disabled={!canSend}
              aria-disabled={!canSend}
              className="pq-ink-btn-bronze inline-flex items-center px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
              data-testid="ai-text-send"
            >
              {sending ? t("journal.import.page.submitting") : t("journal.import.image.send")}
            </button>
          </div>
        </>
      )}
      {error && (
        <Caption className="mt-3">
          <span style={{ color: "var(--pq-error)", whiteSpace: "pre-line" }} data-testid="ai-text-error">{error}</span>
        </Caption>
      )}
    </div>
  );
}
