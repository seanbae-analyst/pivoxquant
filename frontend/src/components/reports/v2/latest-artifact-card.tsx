"use client";

/**
 * <LatestArtifactCard /> — full-width 2-column card for the most recent
 * artifact. Left column: type pill + Playfair pull-quote + body. Right
 * column: "Mentioned" rows w/ 종목명 main pattern (Name on top, ticker
 * code mono dim beneath, +/-X.XX% in KR colors).
 *
 * Source: design-mockups/reports-v2/SPEC.md §2.
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. No banned vocabulary.
 */

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { API } from "@/lib/endpoints";
import { getArtifactViewerUrl } from "@/lib/artifact-viewer";
import type { Artifact, ArtifactType } from "@/lib/types";
import { normalizeTicker } from "@/lib/format";
import { WEEKLY_MEMO_EMPTY_LINE } from "@/lib/cfo/memo-schedule";

const TYPE_LABEL: Record<ArtifactType, string> = {
  weekly_memo: "Weekly Pulse",
  morning_brief: "Today's Memo (legacy)", // type retained for archived artifacts; surface deprecated 2026-04-29
  earnings_prebrief: "Earnings Pre-Brief",
  monthly_brag: "Brag Card",
  quarterly_review: "Quarterly Audit",
  risk_report: "Risk Note",
  custom: "Letter",
  // ── Wave 2 (2026-04-29) labels for the 17 backend artifact types.
  brag_card: "Brag Card",
  self_audit: "Self Audit",
  risk_board: "Risk Board",
  year_end_letter: "Year-End Letter",
  quarterly_self_report: "Quarterly Self-Report",
  kpi_dashboard: "KPI Dashboard",
  dd_checklist: "DD Checklist",
  dividend_income: "Dividend Income",
  monthly_finance: "Monthly Finance",
  burn_rate: "Burn Rate",
  capital_allocation: "Capital Allocation",
  credit_rating: "Credit Rating",
  insider_mirror: "Insider Mirror",
  portfolio_segment: "Portfolio Segment",
  pre_trade_checklist: "Pre-Trade Checklist",
  sp500_backtest: "S&P 500 Backtest",
  living_mirror: "Living Mirror",
};

interface MentionRow {
  ticker: string;
  name: string;
  changePct?: number;
  exchange?: string;
}

function asMentionRows(
  preview: Record<string, unknown> | null | undefined,
): MentionRow[] {
  if (!preview) return [];
  const raw = (preview as { mentioned_tickers?: unknown }).mentioned_tickers;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((x): x is Record<string, unknown> => !!x && typeof x === "object")
    .map((x) => ({
      ticker: typeof x.ticker === "string" ? x.ticker : "",
      name: typeof x.name === "string" ? x.name : "",
      exchange: typeof x.exchange === "string" ? x.exchange : undefined,
      changePct:
        typeof x.change_pct === "number"
          ? x.change_pct
          : typeof x.changePct === "number"
            ? x.changePct
            : undefined,
    }))
    .filter((r) => r.ticker.length > 0);
}

interface Props {
  artifact: Artifact | null;
  loading?: boolean;
  resolveName?: (ticker: string) => string;
}

export function LatestArtifactCard({ artifact, loading, resolveName }: Props) {
  if (loading) {
    return (
      <div
        style={{
          border: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
          borderRadius: 4,
          padding: "clamp(28px, 5vw, 52px) clamp(20px, 5vw, 56px)",
          background: "rgba(255,255,255,0.02)",
          height: 280,
        }}
        className="animate-pulse"
        aria-label="Loading latest artifact"
      />
    );
  }

  if (!artifact) {
    return (
      <div
        style={{
          border: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
          borderRadius: 4,
          padding: "clamp(28px, 5vw, 52px) clamp(20px, 5vw, 56px)",
          background: "rgba(255,255,255,0.02)",
        }}
      >
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "var(--pq-bronze, #B8956A)",
            marginBottom: 12,
          }}
        >
          No artifacts yet
        </div>
        <p
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-lead)",
            lineHeight: 1.65,
            color: "rgba(245,240,232,0.7)",
            margin: 0,
          }}
        >
          The shelf is empty for now. {WEEKLY_MEMO_EMPTY_LINE}
        </p>
      </div>
    );
  }

  const mentions = asMentionRows(artifact.data_preview);
  const typeLabel = TYPE_LABEL[artifact.type] ?? "Artifact";
  // Bug #11 (wave 3b): when sent_at is null but the artifact exists
  // (draft / not yet emailed), fall back to created_at so the card
  // shows a real date instead of "—".
  const dateRaw = artifact.sent_at ?? artifact.created_at ?? null;
  const sentDate = dateRaw
    ? new Date(dateRaw).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "—";

  return (
    <article
      style={{
        border: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
        borderRadius: 4,
        padding: "52px 56px",
        background: "rgba(255,255,255,0.02)",
        position: "relative",
        transition: "border-color 200ms ease",
      }}
      className="hover:border-[var(--pq-bronze)]"
    >
      <div
        className="pq-latest-artifact-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 280px",
          gap: 56,
        }}
      >
        <style jsx>{`
          @media (max-width: 767px) {
            .pq-latest-artifact-grid {
              grid-template-columns: 1fr !important;
              gap: 28px !important;
            }
            .pq-latest-artifact-mentioned {
              border-left: 0 !important;
              border-top: 1px solid var(--pq-hairline, var(--pq-ivory-line)) !important;
              padding-left: 0 !important;
              padding-top: 24px !important;
            }
          }
        `}</style>
        {/* LEFT */}
        <div>
          <span
            className="font-mono uppercase inline-block"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze, #B8956A)",
              border: "1px solid var(--pq-hairline-2, rgba(245,240,232,0.12))",
              borderRadius: 2,
              padding: "4px 9px",
              marginBottom: 18,
            }}
          >
            {typeLabel} · {sentDate}
          </span>

          <h2
            className="font-display"
            style={{
              fontWeight: 500,
              fontSize: "var(--pq-text-h3)",
              lineHeight: 1.15,
              letterSpacing: "-0.01em",
              color: "var(--pq-ivory, #F5F0E8)",
              margin: 0,
            }}
          >
            {artifact.title}
          </h2>

          {artifact.subtitle && (
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-lead)",
                lineHeight: 1.65,
                color: "rgba(245,240,232,0.78)",
                marginTop: 18,
                marginBottom: 0,
                maxWidth: 580,
              }}
            >
              {artifact.subtitle}
            </p>
          )}

          <div
            style={{
              marginTop: 28,
              display: "flex",
              gap: 18,
              alignItems: "center",
              flexWrap: "wrap",
            }}
          >
            <a
              href={getArtifactViewerUrl({
                id: artifact.id,
                type: artifact.type,
                has_file: artifact.has_file,
              })}
              target="_blank"
              rel="noopener noreferrer"
              className="pq-ink-btn-bronze"
              style={{ fontSize: "var(--pq-text-eyebrow)", letterSpacing: "0.18em" }}
            >
              Open full memo ›
            </a>
            {/*
              2026-05-15 (bug-hunter Wave 6 P1 #1): the plain `<a download>`
              tag exposed the user to a raw 410 JSON body on a black
              page when the artifact's PDF file was missing from
              Railway's ephemeral disk (artifact #93 brag card was the
              reported case — `pdf_path: null` / file lost on redeploy).
              Use a fetch-based handler so we can intercept 4xx /5xx and
              surface a toast instead of letting the browser navigate
              to the JSON error page. Backend root cause (persistent
              storage) is a separate CEO/infra action.
            */}
            <button
              type="button"
              onClick={async () => {
                const url = API.artifacts.download(artifact.id);
                try {
                  const resp = await fetch(url, { credentials: "include" });
                  if (!resp.ok) {
                    if (resp.status === 410 || resp.status === 404) {
                      toast.error(
                        "PDF가 아직 준비되지 않았거나 만료됐습니다.",
                        {
                          description:
                            "월간 자동 발송 cron이 다음 1일에 새로 생성합니다. 즉시 필요 시 support@pivoxquant.com",
                          duration: 7000,
                        },
                      );
                      return;
                    }
                    toast.error(
                      `PDF 다운로드 실패 (${resp.status}). 잠시 후 다시 시도해 주세요.`,
                    );
                    return;
                  }
                  const blob = await resp.blob();
                  const blobUrl = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = blobUrl;
                  a.download = `${artifact.type}-${artifact.id}.pdf`;
                  a.click();
                  URL.revokeObjectURL(blobUrl);
                } catch (err) {
                  toast.error(
                    "PDF 다운로드 중 오류 발생. 네트워크 상태를 확인해 주세요.",
                    {
                      description:
                        err instanceof Error ? err.message : undefined,
                    },
                  );
                }
              }}
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.18em",
                color: "var(--pq-bronze, #B8956A)",
                borderBottom: "1px solid var(--pq-bronze-15, rgba(184,149,106,0.15))",
                paddingBottom: 2,
                background: "transparent",
                cursor: "pointer",
                border: "none",
                borderBottomColor: "var(--pq-bronze-15, rgba(184,149,106,0.15))",
                borderBottomWidth: "1px",
                borderBottomStyle: "solid",
              }}
            >
              Download PDF
            </button>
          </div>
        </div>

        {/* RIGHT — Mentioned */}
        <div
          className="pq-latest-artifact-mentioned"
          style={{
            borderLeft: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
            paddingLeft: 36,
          }}
        >
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "rgba(245,240,232,0.45)",
              marginBottom: 16,
            }}
          >
            Mentioned
          </div>

          {mentions.length === 0 ? (
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body)",
                color: "rgba(245,240,232,0.55)",
                margin: 0,
              }}
            >
              No tickers indexed for this issue.
            </p>
          ) : (
            <ul
              style={{
                listStyle: "none",
                padding: 0,
                margin: 0,
                display: "flex",
                flexDirection: "column",
                gap: 14,
              }}
            >
              {mentions.slice(0, 3).map((m) => {
                const displayName =
                  m.name && m.name.length > 0
                    ? m.name
                    : resolveName
                      ? resolveName(m.ticker)
                      : normalizeTicker(m.ticker);
                const pct = m.changePct;
                const isUp = typeof pct === "number" && pct > 0;
                const isDown = typeof pct === "number" && pct < 0;
                const pctColor = isUp
                  ? "var(--up, #D18888)"
                  : isDown
                    ? "var(--down, #7AA0C8)"
                    : "rgba(245,240,232,0.55)";
                const sign = isUp ? "+" : "";
                return (
                  <li
                    key={m.ticker}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr auto",
                      alignItems: "baseline",
                      gap: 12,
                    }}
                  >
                    <div>
                      <div
                        className="font-display"
                        style={{
                          fontWeight: 500,
                          fontSize: "var(--pq-text-h5)",
                          color: "var(--pq-ivory, #F5F0E8)",
                          lineHeight: 1.15,
                        }}
                      >
                        {displayName}
                      </div>
                      <div
                        className="font-mono uppercase"
                        style={{
                          fontSize: "var(--pq-text-eyebrow)",
                          letterSpacing: "0.14em",
                          color: "rgba(245,240,232,0.45)",
                          marginTop: 2,
                        }}
                      >
                        {normalizeTicker(m.ticker)}
                        {m.exchange ? ` · ${m.exchange}` : ""}
                      </div>
                    </div>
                    {typeof pct === "number" && (
                      <div
                        className="font-mono"
                        style={{
                          fontVariantNumeric: "tabular-nums",
                          fontSize: "var(--pq-text-body)",
                          color: pctColor,
                        }}
                      >
                        {sign}
                        {pct.toFixed(2)}%
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      {/* Hidden link wrapper for accessibility — entire card navigates.
          2026-05-02: this overlay was still pointing at the JSON preview
          endpoint and intercepting the visible "Open full memo" button
          (absolute inset-0 catches every click). Route through the same
          helper as the visible CTA so the click target matches. */}
      <Link
        href={getArtifactViewerUrl({
          id: artifact.id,
          type: artifact.type,
          has_file: artifact.has_file,
        })}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`${typeLabel} — open full artifact`}
        className="absolute inset-0"
        style={{ overflow: "hidden", textIndent: "-9999px" }}
      >
        Open
      </Link>
    </article>
  );
}

export default LatestArtifactCard;
