"use client";

/**
 * "AI로 다시 읽기" — the one place a user sends text for an AI read.
 *
 * docs/product/AI_READ_EXPERIMENT_2026-10-07.md §5. What this box guarantees:
 *   - it renders only when NEXT_PUBLIC_AI_READ=1 (lib/ai-read.ts);
 *   - the user sees exactly what will be sent (the masked text, verbatim);
 *   - nothing is sent without the per-use consent tick (국외이전);
 *   - the result is labelled as AI-read (AiContentBadge).
 * The caller turns the returned rows into its own review rows.
 */
import { useState } from "react";
import { useT } from "@/lib/locale";
import { ApiError } from "@/lib/api";
import { Caption, FieldLabel } from "@/components/ui/editorial";
import { AiContentBadge } from "@/components/ui/ai-content-badge";
import { aiReadEnabled, requestAiRead, type AiReadKind, type AiReadScreen } from "@/lib/ai-read";

export function AiReadOffer<R>({
  kind,
  texts,
  onScreens,
  title,
  body,
}: {
  kind: AiReadKind;
  /** Masked text per screen (lib/fill-ocr/mask.ts) — exactly what is sent. */
  texts: string[];
  onScreens: (screens: AiReadScreen<R>[]) => void;
  title?: string;
  body?: string;
}) {
  const t = useT();
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sendable = texts.filter((x) => x.trim() !== "");
  if (!aiReadEnabled() || sendable.length === 0) return null;

  async function run() {
    if (!consent || busy) return;
    setBusy(true);
    setError(null);
    try {
      onScreens(await requestAiRead<R>(kind, sendable));
    } catch (err) {
      const msg = err instanceof ApiError || err instanceof Error ? err.message : "";
      setError(msg || t("aiRead.failed"));
    } finally {
      setBusy(false);
    }
  }

  const textStyle = {
    fontSize: "var(--pq-text-body-sm)",
    lineHeight: 1.5,
    color: "var(--pq-ivory-soft)",
    wordBreak: "keep-all" as const,
  };

  return (
    <div className="mt-5 border-t border-[rgba(245,240,232,0.1)] pt-4" data-testid="ai-read-offer">
      <div className="flex items-center gap-2">
        <AiContentBadge />
        <FieldLabel tone="bronze">{title ?? t("aiRead.title")}</FieldLabel>
      </div>
      <p className="mt-2 font-serif" style={textStyle}>{body ?? t("aiRead.body")}</p>
      <Caption className="mt-1">{t("aiRead.check")}</Caption>
      <details className="mt-2">
        <summary className="cursor-pointer font-mono" style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-ivory-mid)" }}>
          {t("aiRead.preview").replace("{n}", String(sendable.length))}
        </summary>
        <pre
          className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap font-mono p-2 border border-[rgba(245,240,232,0.1)]"
          style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-ivory-mid)" }}
          data-testid="ai-read-preview"
        >
          {sendable.join("\n\n———\n\n")}
        </pre>
      </details>
      <label className="mt-3 flex items-start gap-2 font-serif" style={textStyle}>
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          className="mt-1"
          data-testid="ai-read-consent"
        />
        <span>{t("aiRead.consent")}</span>
      </label>
      <button
        type="button"
        onClick={run}
        disabled={!consent || busy}
        aria-disabled={!consent || busy}
        className="pq-ink-btn-ghost mt-3 px-4 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
        data-testid="ai-read-run"
      >
        {busy ? t("aiRead.reading") : t("aiRead.button")}
      </button>
      {error && (
        <Caption className="mt-2">
          <span style={{ color: "var(--pq-error)" }} data-testid="ai-read-error">{error}</span>
        </Caption>
      )}
    </div>
  );
}
