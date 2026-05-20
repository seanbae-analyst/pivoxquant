"use client";

/**
 * Zone3 DOSSIER — AI SWOT (on-demand).
 *
 * Claude is rate-limited, so generation is user-triggered (the page owns the
 * fetch + 503/429-graceful error copy and passes the result down). AI content
 * disclosure badge is mandatory (regulatory ③ 2026-01). Observation framing
 * only — no advice / recommendation language.
 */

import { Sparkles } from "lucide-react";
import { FieldLabel } from "@/components/ui/editorial";
import { AiContentBadge } from "@/components/ui/ai-content-badge";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { SectionHeading } from "./shared";
import type { SwotResponse } from "./types";

export function SwotPanel({
  ticker,
  displayName,
  swot,
  loading,
  error,
  onGenerate,
}: {
  ticker: string;
  /** Human-readable name (e.g. "삼성전자") for user-facing copy. ticker is
   * reserved for the API gate / POST body — never shown raw (feedback_ticker_display). */
  displayName?: string;
  swot: SwotResponse | null;
  loading: boolean;
  error: string | null;
  onGenerate: () => void;
}) {
  const hasContent = swot && (swot.swot_kr || swot.swot);

  return (
    <section>
      <div className="mb-5">
        <SectionHeading
          eyebrow="AI assistant · observation"
          title="AI analysis"
          icon={
            <Sparkles className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.4} />
          }
        />
        <div className="mt-3">
          <AiContentBadge variant="inline" />
        </div>
      </div>

      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] rounded-sm p-5">
        {hasContent ? (
          <div className="space-y-4">
            {swot!.swot_kr ? (
              <div>
                <FieldLabel>한국어</FieldLabel>
                <p className="mt-2 whitespace-pre-line font-sans text-pq-body leading-[1.6] text-[var(--pq-ivory)]/85">
                  {swot!.swot_kr}
                </p>
              </div>
            ) : null}
            {swot!.swot ? (
              <div className="pt-3 border-t border-[var(--pq-ivory-line-soft)]">
                <FieldLabel>English</FieldLabel>
                <p className="mt-2 whitespace-pre-line font-serif text-pq-body leading-[1.65] text-[var(--pq-ivory)]/75">
                  {swot!.swot}
                </p>
              </div>
            ) : null}
            <div className="pt-3 mt-3 border-t border-[var(--pq-ivory-line-soft)]">
              <DisclaimerBanner type="signal" />
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-start gap-3">
            <p className="pq-detail-caption">
              AI analysis is being prepared. Trigger an observation summary for{" "}
              {displayName || "this stock"} below.
            </p>
            <button
              type="button"
              onClick={onGenerate}
              disabled={loading || !ticker}
              className="inline-flex items-center gap-2 px-4 py-2 text-pq-mono-xs uppercase tracking-[0.18em] border border-[var(--pq-bronze)] text-[var(--pq-bronze)] hover:bg-[rgba(184,149,106,0.08)] hover:text-[var(--pq-bronze-light)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors rounded-sm"
            >
              <Sparkles className="h-3 w-3" strokeWidth={1.6} />
              {loading ? "Generating…" : "Generate AI summary"}
            </button>
            {error ? (
              <p className="text-pq-mono-xs text-[var(--pq-ivory-dim)]">
                Unable to generate right now ({error}). Try again later.
              </p>
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
}
