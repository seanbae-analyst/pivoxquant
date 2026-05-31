/**
 * Report 03 — Brag Card (Free · 1 page · Monthly)
 *
 * Source: /design_handoff_pdf_reports/reports/03_brag_card.html
 *
 * The month's "best decision" highlight. Hero card with the One trade,
 * two-column "why it worked" + "lesson for next month", pullquote at bottom.
 *
 * Compliance: All decision labels use neutral framing. No buy/sell/hold.
 * Disclaimer rendered automatically at the bottom.
 */

"use client";

import {
  PdfPage,
  PdfHeader,
  PdfGoldRule,
  PdfEyebrow,
  PdfCoverTitle,
  PdfKpiRow,
  PdfTwoCol,
  PdfColTitle,
  PdfCheckList,
  PdfCard,
  PdfPullquote,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
  PdfTicker,
} from "../pdf-primitives";
import { fmtPct } from "@/lib/format";
import { EmptyState } from "../empty-state";

export interface BragCardData {
  monthLabel: string;     // "April 2026"
  reportTag: string;      // "BC-2026-04"
  bestDecisionPct: string;// "+12.8%"
  contribution: string;   // "contributed +1.84%p to NAV"
  hitRate: string;        // "7 / 9"
  hitRateDetail: string;  // "78% · best month YTD"
  monthReturn: string;    // "+4.2%"
  benchmark: string;      // "vs S&P +1.6%"
  hero: {
    ticker: string;
    name: string;
    title: string;
    body: string;
    entry: string;
    mark: string;
    pnl: string;
  };
  whyItWorked: { body: string; meta: string }[];
  lessonForNext: { body: string; meta: string }[];
  pullquote: string;
}

/**
 * Backend artifact `data_json` (from `BragCardService.generate_for_user`)
 * is a flat snake_case shape — *not* the `BragCardData` shape this
 * template expects. Without normalisation, `data.hero.ticker` throws
 * `Cannot read properties of undefined (reading 'ticker')` and the
 * `<ReportPreviewShell>` boundary catches it into a "리포트를 다시
 * 준비하고 있어요" empty state — the user never sees their card.
 *
 * 2026-05-13 root-cause fix: accept either shape. The flat backend
 * payload is mapped to the `BragCardData` shape here (mirror of
 * `BragCardService._to_v3_shape` on the Python side). When `data` is
 * undefined or genuinely empty, `normalizeBragCardData` returns `null` and
 * the component renders the honest empty state — never a fabricated sample.
 */
type BackendBragPayload = {
  month_label?: string;
  month_label_long?: string;
  month_start?: string;
  return_pct?: number | null;
  trade_count?: number | null;
  best_ticker?: string | null;
  best_return_pct?: number | null;
};

/**
 * Reshape either the `BragCardData` template shape OR the flat backend
 * `data_json` payload into `BragCardData`. Returns `null` when there is no
 * real artifact data — the component then renders the honest empty state.
 *
 * No fabricated fixture: narrative sections (`whyItWorked` / `lessonForNext`
 * / `pullquote`) are sourced ONLY from real data. For the numeric-only
 * backend payload they stay empty rather than borrowing a fabricated story.
 */
function normalizeBragCardData(
  raw: BragCardData | BackendBragPayload | undefined | null,
): BragCardData | null {
  if (!raw || typeof raw !== "object") return null;
  // Already in the template shape — trust it but still defend `hero`.
  const candidate = raw as Partial<BragCardData>;
  if (
    candidate.hero &&
    typeof candidate.hero === "object" &&
    typeof candidate.hero.ticker === "string"
  ) {
    return {
      monthLabel: candidate.monthLabel ?? "",
      reportTag: candidate.reportTag ?? "",
      bestDecisionPct: candidate.bestDecisionPct ?? "—",
      contribution: candidate.contribution ?? "",
      hitRate: candidate.hitRate ?? "—",
      hitRateDetail: candidate.hitRateDetail ?? "",
      monthReturn: candidate.monthReturn ?? "—",
      benchmark: candidate.benchmark ?? "",
      hero: {
        ticker: candidate.hero.ticker,
        name: candidate.hero.name ?? "",
        title: candidate.hero.title ?? "",
        body: candidate.hero.body ?? "",
        entry: candidate.hero.entry ?? "—",
        mark: candidate.hero.mark ?? "—",
        pnl: candidate.hero.pnl ?? "—",
      },
      whyItWorked: candidate.whyItWorked ?? [],
      lessonForNext: candidate.lessonForNext ?? [],
      pullquote: candidate.pullquote ?? "",
    };
  }

  // Backend flat snake_case payload — map onto BragCardData.
  const flat = raw as BackendBragPayload;
  const hasAnyBackendField =
    "best_ticker" in flat ||
    "return_pct" in flat ||
    "month_label" in flat ||
    "month_label_long" in flat;
  if (!hasAnyBackendField) return null;

  const monthLabel = flat.month_label_long || flat.month_label || "";
  const monthStart = (flat.month_start || "").slice(0, 7);
  const reportTag = monthStart ? `BC-${monthStart}` : "";

  const bestRet = flat.best_return_pct;
  const bestDecisionPct = bestRet == null ? "—" : fmtPct(bestRet);
  const monthReturn = flat.return_pct == null ? "—" : fmtPct(flat.return_pct);
  const tradeCount = flat.trade_count ?? 0;

  const hitRate = tradeCount > 0 ? `${tradeCount} 건` : "—";
  const hitRateDetail = tradeCount > 0 ? `${tradeCount} closed lot(s)` : "";

  const ticker = flat.best_ticker || "—";
  const heroBody =
    bestRet == null
      ? "이번 달 단일 의사결정 기록을 준비하고 있어요."
      : `${ticker} 종목에서 단일 의사결정을 관찰했습니다. ` +
        `실현 수익률은 ${bestDecisionPct}로 기록되었습니다.`;

  return {
    monthLabel,
    reportTag,
    bestDecisionPct,
    contribution: "",
    hitRate,
    hitRateDetail,
    monthReturn,
    benchmark: "",
    hero: {
      ticker,
      name: "",
      title: "이번 달 단일 의사결정 기록",
      body: heroBody,
      entry: "—",
      mark: "—",
      pnl: bestDecisionPct,
    },
    // No fabricated narrative — the numeric backend payload carries none.
    whyItWorked: [],
    lessonForNext: [],
    pullquote: "",
  };
}

/** Renders inline `**bold**` segments inside body strings. */
function renderInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? (
      <strong key={i}>{p.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}

/**
 * Renders pullquote text with whitelisted `<em>...</em>` emphasis.
 * Avoids `dangerouslySetInnerHTML` — only `<em>` tags are recognized,
 * everything else is rendered as plain text. Defends against XSS even
 * if backend copy ever flows from untrusted input.
 */
function renderPullquote(text: string) {
  const parts = text.split(/(<em>[^<]*<\/em>)/g);
  return parts.map((p, i) =>
    p.startsWith("<em>") && p.endsWith("</em>") ? (
      <em key={i}>{p.slice(4, -5)}</em>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}

export function BragCard({
  data: rawData,
}: {
  /**
   * Accepts either the `BragCardData` template shape OR the raw backend
   * `data_json` payload (snake_case from `BragCardService.generate_for_user`).
   * `normalizeBragCardData` reshapes both into `BragCardData` so the
   * template never crashes on `data.hero.ticker` when the boundary
   * shell hands it a flat backend payload (2026-05-13 root-cause fix).
   */
  data?: BragCardData | BackendBragPayload;
}) {
  const data = normalizeBragCardData(rawData ?? null);
  // No fabricated fixture — render the honest empty state when there is no
  // real artifact data instead of a fabricated sample.
  if (!data) {
    return <EmptyState type="brag_card" reason="no_trades" />;
  }
  return (
    <>
    <PdfPage>
      <PdfHeader tier="free" title="BRAG CARD" meta={`${data.monthLabel} · ${data.reportTag} · 01/02`} />

      <PdfEyebrow>Brag Card · Monthly</PdfEyebrow>
      <PdfCoverTitle size={42}>
        The month&apos;s <em>best call</em>—<br />
        one page worth bragging about.
      </PdfCoverTitle>
      <p
        style={{
          color: "var(--r-ink-3)",
          marginTop: 12,
          fontSize: "var(--pq-text-body)",
          lineHeight: 1.55,
        }}
      className="font-serif" >
        One decision that wasn&apos;t luck — proven on paper, kept for next month&apos;s self.
      </p>

      <div style={{ marginTop: 24 }}>
        <PdfKpiRow
          cols={3}
          kpis={[
            {
              label: "Best Decision",
              value: data.bestDecisionPct,
              delta: data.contribution,
              deltaTone: "pos",
            },
            {
              label: "Hit Rate · MTD",
              value: data.hitRate,
              delta: data.hitRateDetail,
            },
            {
              label: "Month Return",
              value: data.monthReturn,
              delta: data.benchmark,
              deltaTone: "pos",
            },
          ]}
        />
      </div>

      {/* Hero — the one decision */}
      <div style={{ marginTop: 18 }}>
        <PdfCard>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 12,
            }}
          >
            <div
              style={{
                fontSize: "var(--pq-text-kicker)",
                letterSpacing: "1.5px",
                textTransform: "uppercase",
                color: "var(--r-ink-4)",
              }}
            className="font-mono" >
              ★ The One · 이 달의 결정
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <PdfTicker>{data.hero.ticker}</PdfTicker>
              <span
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  color: "var(--r-ink-3)",
                }}
                className="font-serif"
              >
                {data.hero.name}
              </span>
            </div>
          </div>
          <div
            style={{
              fontSize: "var(--pq-text-quote)",
              fontWeight: 500,
              letterSpacing: "-0.012em",
              marginBottom: 8,
            }}
          className="font-serif" >
            {data.hero.title}
          </div>
          <p
            style={{
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.6,
              color: "var(--r-ink-2)",
              marginBottom: 14,
            }}
          className="font-serif" >
            {data.hero.body}
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: 14,
              fontSize: "var(--pq-text-eyebrow)",
            }}
          >
            <div>
              <div
                className="pq-pdf-kpi-lbl"
                style={{ marginBottom: 6 }}
              >
                Entry
              </div>
              <div
                style={{
                  fontVariantNumeric: "tabular-nums",
                }}
              className="font-mono" >
                {data.hero.entry}
              </div>
            </div>
            <div>
              <div
                className="pq-pdf-kpi-lbl"
                style={{ marginBottom: 6 }}
              >
                Mark
              </div>
              <div
                style={{
                  fontVariantNumeric: "tabular-nums",
                }}
              className="font-mono" >
                {data.hero.mark}
              </div>
            </div>
            <div>
              <div
                className="pq-pdf-kpi-lbl"
                style={{ marginBottom: 6 }}
              >
                P&amp;L
              </div>
              <div
                style={{
                  fontVariantNumeric: "tabular-nums",
                  color: "var(--r-pos)",
                }}
              className="font-mono" >
                {data.hero.pnl}
              </div>
            </div>
          </div>
        </PdfCard>
      </div>

      {(data.whyItWorked.length > 0 || data.lessonForNext.length > 0) && (
        <div style={{ marginTop: 18 }}>
          <PdfTwoCol>
            <div>
              <PdfColTitle>Why It Worked · 운이 아닌 이유</PdfColTitle>
              <PdfCheckList
                items={data.whyItWorked.map((i) => ({
                  checked: true,
                  body: renderInline(i.body),
                  meta: i.meta,
                }))}
              />
            </div>
            <div>
              <PdfColTitle>Lesson for Next Month · 다음 달까지 유지</PdfColTitle>
              <PdfCheckList
                items={data.lessonForNext.map((i) => ({
                  checked: false,
                  body: renderInline(i.body),
                  meta: i.meta,
                }))}
              />
            </div>
          </PdfTwoCol>
        </div>
      )}

      {data.pullquote ? (
        <div style={{ marginTop: 18 }}>
          <PdfPullquote>
            <span>{renderPullquote(data.pullquote)}</span>
          </PdfPullquote>
        </div>
      ) : null}

      <PdfPageFooter
        left="For information only · pivoxquant.com"
        right={`Brag Card · ${data.reportTag}`}
      />

      <PdfDisclaimerMini />
    </PdfPage>

    <PdfPage>
      <PdfHeader tier="free" title="BRAG CARD" meta={`${data.monthLabel} · ${data.reportTag} · 02/02`} />
      <PdfGoldRule />
      <PdfDisclaimer cadence="monthly" />
    </PdfPage>
    </>
  );
}
