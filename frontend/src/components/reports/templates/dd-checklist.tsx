/**
 * Report 08 — DD Checklist (Pro · On Demand)
 *
 * Source: /design_handoff_pdf_reports/reports/08_dd_checklist.html
 *
 * The live backend payload (services/artifacts/dd_checklist_service.py) is a
 * T+3 self-review of the user's *actual* pending positions — rendered by
 * <BackendDdChecklistView />. When there is no real artifact data we show the
 * honest empty state; we never fabricate a sample checklist.
 *
 * Compliance: Process audit / pre-entry checklist. No buy/sell/hold language.
 * Cadence: ondemand (one-off pre-entry diligence).
 */

"use client";

import {
  PdfPage,
  PdfHeader,
  PdfGoldRule,
  PdfEyebrow,
  PdfCoverTitle,
  PdfDisclaimerMini,
} from "../pdf-primitives";
import { EmptyState } from "../empty-state";

type Tone = "pos" | "neg" | "warn";

interface DdItem {
  num: string;
  text: string;
  detail?: string;
  status: string;
  tone: Tone;
  checked?: boolean;
}

/**
 * Static IC-pack shape. Retained as an exported type because the auth-gated
 * preview page parametrises <ReportPreviewShell<DdChecklistData>>. The live
 * backend never emits this shape (it emits the T+3 pending-review shape
 * below); no fabricated fixture of this shape is shipped.
 */
export interface DdChecklistData {
  asOf: string;
  ticker: string;
  company: string;
  price: { value: string; delta: string };
  targetSize: { value: string; detail: string };
  ddScore: { value: string; verdict: string };
  sectionA: DdItem[];
  sectionB: DdItem[];
  sectionC: DdItem[];
  sectionD: DdItem[];
  sectionE: DdItem[];
  thesis: string;
  decisionScore: string;
  promise: string;
}

/**
 * Backend dd_checklist payload shape (from services/artifacts/dd_checklist_service.py).
 * 2026-05-02: backend produces a T+3 multi-position review.
 */
interface BackendPendingRow {
  ticker: string;
  /**
   * PR #212 follow-up — when the backend enriches pending rows with the
   * company display name we render it as the row hero (with ticker as a
   * small subline). Optional today; safely falls back to ticker.
   */
  companyName?: string;
  shares: number;
  avg_cost: number;
  added_at?: string;
  days_since?: number;
}

interface BackendDdChecklistData {
  as_of?: string;
  user_name?: string;
  pending?: BackendPendingRow[];
  disclaimer?: string;
}

function isBackendShape(data: unknown): data is BackendDdChecklistData {
  return !!data
    && typeof data === "object"
    && "pending" in (data as Record<string, unknown>)
    && Array.isArray((data as { pending?: unknown }).pending);
}

function fmtMoney(n: number, korean: boolean): string {
  if (!isFinite(n)) return "—";
  if (korean) return `KRW ${Math.round(n).toLocaleString()}`;
  return `USD ${n.toFixed(2)}`;
}

/** Render the real backend payload — the user's actual pending positions. */
function BackendDdChecklistView({ data }: { data: BackendDdChecklistData }) {
  const pending = data.pending ?? [];
  const asOf = data.as_of || "";
  const name = data.user_name || "";
  return (
    <PdfPage>
      <PdfHeader tier="pro" title="DD CHECKLIST" meta={asOf ? `${asOf}` : ""} />
      <PdfGoldRule />
      <PdfEyebrow>Due Diligence · T+3 Self-Review</PdfEyebrow>
      <PdfCoverTitle size={36}>
        {name ? `${name}, ` : ""}
        오늘 점검할 <em>{pending.length}개</em> 종목.
      </PdfCoverTitle>
      <div style={{ marginTop: 28, }} className="font-serif" >
        <p style={{ fontSize: "var(--pq-text-body)", color: "var(--r-ink-2, #555)", margin: 0, lineHeight: 1.65 }}>
          3일 전에 추가하신 포지션. 메모를 다시 한 번 점검해 보세요.
        </p>
      </div>
      <div style={{ marginTop: 32, borderTop: "1px solid var(--r-rule, #e5e0d6)" }}>
        {pending.map((p, i) => {
          const krw = (p.ticker || "").toUpperCase().endsWith(".KS")
            || (p.ticker || "").toUpperCase().endsWith(".KQ");
          // PR #212 follow-up — when companyName is present, use it as the
          // row hero (serif). Ticker becomes a small mono subline. Falls
          // back to ticker-only when name is missing.
          const heroName = p.companyName && p.companyName.trim() ? p.companyName : p.ticker;
          const showTickerSubline = !!(p.companyName && p.companyName.trim());
          return (
            <div
              key={`${p.ticker}-${i}`}
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(140px, 1.2fr) 1fr 1fr auto",
                gap: 16,
                padding: "16px 0",
                borderBottom: "1px solid var(--r-rule, #efeae0)",
                alignItems: "baseline",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div
                  className="font-serif"
                  style={{
                    fontSize: "var(--pq-text-body)",
                    fontWeight: 500,
                    color: "var(--r-ink-1, #1a1a1a)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {heroName}
                </div>
                {showTickerSubline && (
                  <div
                    className="font-mono"
                    style={{
                      fontSize: "var(--pq-text-micro)",
                      color: "var(--r-gold-deep, #8b6f47)",
                      letterSpacing: "0.04em",
                      marginTop: 2,
                    }}
                  >
                    {p.ticker}
                  </div>
                )}
              </div>
              <span className="font-mono" style={{ fontSize: "var(--pq-text-body)", color: "var(--r-ink-2)" }}>
                {p.shares} shares
              </span>
              <span className="font-mono" style={{ fontSize: "var(--pq-text-body)", color: "var(--r-ink-3)" }}>
                avg {fmtMoney(p.avg_cost, krw)}
              </span>
              <span className="font-mono" style={{ fontSize: "var(--pq-text-eyebrow)", letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--r-ink-4)" }}>
                +{p.days_since ?? "—"}d
              </span>
            </div>
          );
        })}
      </div>
      <PdfDisclaimerMini />
    </PdfPage>
  );
}

export function DdChecklist({ data: dataInput }: { data?: DdChecklistData | unknown }) {
  // Real data only: the live backend hands us the T+3 pending-review payload.
  if (isBackendShape(dataInput)) {
    return <BackendDdChecklistView data={dataInput} />;
  }
  // No fabricated fixture — when there is no real artifact data, render the
  // honest empty state instead of a fabricated sample checklist.
  return <EmptyState type="dd_checklist" reason="no_trades" />;
}
