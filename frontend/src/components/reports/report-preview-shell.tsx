"use client";

/**
 * <ReportPreviewShell /> — Wave 2 (2026-04-29) shared shell for the 17
 * /reports/preview/<slug> pages.
 *
 * Responsibilities:
 *   1. Tier gate — block Pro/Premium artifacts for lower-tier users via
 *      <TierGate />, which surfaces an upgrade CTA pointing to /pricing.
 *   2. SWR fetch — `useArtifacts({ type })` returns the user's artifact
 *      archive filtered to this single artifact type. We pick the latest
 *      one (already sorted server-side by `sent_at desc`).
 *   3. Empty state — when no artifact exists yet, render <EmptyState />
 *      with a sensible default `reason` instead of a hardcoded sample.
 *   4. Render — when an artifact is found, the child renderer receives
 *      `data_preview` (cast to the template-specific `*Data` shape).
 *      Templates retain their own `DEFAULT` fallback for prop omission,
 *      but production code paths now hand them real data.
 *
 * The shell is intentionally generic — each preview page passes its own
 * `<Template />` renderer plus type metadata. The template's data shape
 * is opaque to the shell (typed via the generic `TData`).
 */

import * as React from "react";
import { useArtifacts } from "@/lib/hooks";
import type { ArtifactType } from "@/lib/types";
import {
  ReportSurface,
  PdfToolbar,
} from "@/components/reports/pdf-primitives";
import { EmptyState, type EmptyStateReason } from "./empty-state";
import { TierGate } from "@/components/ui/tier-gate";

export interface ReportPreviewShellProps<TData> {
  /** Backend artifact type — must match `_ARTIFACT_DISPATCH` literal. */
  type: ArtifactType;
  /** Tier required to view this preview. */
  tier: "free" | "pro" | "premium";
  /** Default empty-state reason when no artifact exists. */
  emptyReason?: EmptyStateReason;
  /**
   * Renderer for the actual template. Receives:
   *   - `data`: cast `data_preview` payload (or `undefined` if the row
   *     existed but had no preview); when undefined the template falls
   *     back to its own `DEFAULT` props.
   */
  render: (data: TData | undefined) => React.ReactNode;
}

export function ReportPreviewShell<TData>({
  type,
  tier,
  emptyReason = "no_artifact",
  render,
}: ReportPreviewShellProps<TData>) {
  const { artifacts, isLoading } = useArtifacts({ type, limit: 1 });
  const latest = artifacts?.[0];

  const inner = (() => {
    if (isLoading) {
      return (
        <div
          aria-busy="true"
          aria-live="polite"
          style={{
            padding: "96px 56px",
            textAlign: "center",
            color: "rgba(245,240,232,0.55)",
            fontFamily:
              'var(--pq-font-mono,"IBM Plex Mono",ui-monospace,monospace)',
            fontSize: 11,
            letterSpacing: "0.22em",
            textTransform: "uppercase",
          }}
        >
          Loading…
        </div>
      );
    }

    if (!latest) {
      return <EmptyState type={type} reason={emptyReason} />;
    }

    // Backend `data_preview` is `Record<string, unknown> | null` — we
    // hand it to the template renderer as the template-specific data
    // shape. If the preview snapshot is missing/empty, pass `undefined`
    // so the template uses its own DEFAULT (template-level fallback,
    // not a sample-data fallback in user code).
    const preview = latest.data_preview;
    const data =
      preview && Object.keys(preview).length > 0
        ? (preview as unknown as TData)
        : undefined;

    return render(data);
  })();

  // Tier gate wraps the whole rendered surface — TierGate compares
  // `useAuth().user.subscription_tier` against the required tier.
  return (
    <ReportSurface>
      <PdfToolbar />
      {tier === "free" ? (
        inner
      ) : (
        <TierGate tier={tier}>{inner}</TierGate>
      )}
    </ReportSurface>
  );
}

export default ReportPreviewShell;
