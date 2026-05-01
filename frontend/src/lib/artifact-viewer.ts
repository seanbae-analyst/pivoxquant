/**
 * Resolve the right "view this artefact" URL for a given artefact row.
 *
 * Two viewer paths exist in this codebase:
 *
 *   1. PDF artefacts (weekly_memo, earnings_prebrief, brag_card, …)
 *      — backend persists a real PDF on disk and `has_file === true`.
 *        Open `/api/artifacts/<id>/download?inline=1` so the browser's
 *        native PDF viewer handles rendering.
 *
 *   2. HTML / interactive artefacts (dd_checklist, kpi_dashboard,
 *      credit_rating) and any row whose PDF hasn't been rendered yet
 *      — `has_file === false`. The download endpoint would 410. Send
 *        the user to the matching frontend `/reports/preview/<slug>`
 *        page; that shell pulls the persisted `data_preview` JSON via
 *        `useArtifacts` and renders it through the styled template.
 *
 * Type strings come from backend `Artifact.type`. Mapping mirrors
 * `_ARTIFACT_DOWNLOAD_META` in routes/artifacts.py.
 */

import { API } from "./endpoints";

const TYPE_TO_SLUG: Record<string, string> = {
  weekly_memo: "weekly-memo",
  earnings_prebrief: "earnings-prebrief",
  brag_card: "brag-card",
  monthly_brag: "brag-card",
  dd_checklist: "dd-checklist",
  kpi_dashboard: "kpi-dashboard",
  credit_rating: "credit-rating",
  dividend_income: "dividend-income",
  monthly_finance: "monthly-finance",
  risk_board: "risk-board",
  portfolio_segment: "portfolio-segment",
  capital_allocation: "capital-allocation",
  insider_mirror: "insider-mirror",
  year_end_letter: "year-end-letter",
  quarterly_self_report: "quarterly-self-report",
  burn_rate: "burn-rate",
  self_audit: "self-audit",
  sp500_backtest: "sp500-backtest",
};

// HTML-rendered types whose `has_file` is intentionally false on the
// backend — they're shown via the frontend preview shell, never as PDFs.
const HTML_ONLY_TYPES = new Set<string>([
  "dd_checklist",
  "kpi_dashboard",
  "credit_rating",
]);

export interface ArtefactViewable {
  id: number;
  type: string;
  has_file?: boolean;
}

/**
 * Returns the URL the "Open full memo / Open" CTA should point at.
 * Falls back to the type's preview page slug if the type has a known
 * mapping but no rendered PDF; falls back to /reports as a last
 * resort so the link is never broken.
 */
export function getArtifactViewerUrl(a: ArtefactViewable): string {
  const slug = TYPE_TO_SLUG[a.type];
  // HTML-only types: always use the frontend preview shell.
  if (HTML_ONLY_TYPES.has(a.type) && slug) {
    return `/reports/preview/${slug}`;
  }
  // PDF types: prefer the real file when it exists.
  if (a.has_file !== false) {
    return `${API.artifacts.download(a.id)}?inline=1`;
  }
  // PDF type but file not yet rendered → preview shell instead of
  // sending the user to a guaranteed 410.
  if (slug) {
    return `/reports/preview/${slug}`;
  }
  // Truly unknown type: punt to the archive.
  return "/reports";
}
