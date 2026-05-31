/**
 * Report 15 — Burn Rate (Premium · 2 pages · Monthly)
 *
 * Source: /design_handoff_pdf_reports/reports/15_burn_rate.html
 *
 * Page 1: 3-up KPI (holdings tracked / avg runway / combined cash)
 *         + Runway Ranking table (8 holdings).
 * Page 2: Critical cards (RIVN 7mo / LCID 5mo) + Watch card (RBLX) + CFO's Note
 *         + governance + disclaimer.
 *
 * Compliance: Cash runway tracking. "PROFITABLE / SAFE / WATCH / CRITICAL" are
 * descriptive cash status, not buy/sell/hold. Action lines describe portfolio
 * sizing rules, not investment recommendations.
 */

"use client";

import {
  PdfPage,
  PdfHeader,
  PdfGoldRule,
  PdfEyebrow,
  PdfCoverTitle,
  PdfKpiRow,
  PdfSectionTitle,
  PdfTable,
  PdfTicker,
  PdfCard,
  PdfFlexBetween,
  PdfCheckList,
  PdfCallout,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";
import { displayTicker, normalizeTicker } from "@/lib/format";
import { EmptyState } from "../empty-state";

type BurnStatus = "PROFITABLE" | "SAFE" | "WATCH" | "CRITICAL";

interface BurnRow {
  ticker: string;
  name: string;
  cash: string;
  qBurn: string;
  qBurnTone: "pos" | "neg";
  runway: string;
  runwayTone?: "pos" | "warn" | "neg";
  status: BurnStatus;
  position: string;
}

export interface BurnRateData {
  asOf: string;
  /** Report id shown in the page header (a BR-prefixed tag). Optional —
   *  omitted rather than hardcoded when the backend does not supply it. */
  reportTag?: string;
  tracked: { value: string; detail: string };
  avgRunway: { value: string; detail: string };
  combinedCash: { value: string; detail: string };
  rows: BurnRow[];
  critical: {
    ticker: string;
    name: string;
    runwayMonths: number;
    runwayLabel: string;
    runwayLabelTone: "warn" | "neg";
    cashBurnLine: string;
    note: string;
    action: string;
  }[];
  watch: {
    ticker: string;
    name: string;
    runway: string;
    cashBurnLine: string;
    note: string;
  };
  cfoNote: string;
}

const STATUS_TONE: Record<BurnStatus, string | undefined> = {
  PROFITABLE: "var(--r-pos)",
  SAFE: undefined,
  WATCH: "var(--r-warn)",
  CRITICAL: "var(--r-neg)",
};


export function BurnRate({ data }: { data?: BurnRateData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="burn_rate" reason="insufficient_history" />;
  }
  return (
    <>
      {/* PAGE 1 */}
      <PdfPage>
        <PdfHeader tier="premium" title="BURN RATE" meta={`${data.asOf}${data.reportTag ? ` · ${data.reportTag}` : ""} · 01/03`} />
        <PdfGoldRule />


        <PdfEyebrow>Burn Rate · For Growth Holdings</PdfEyebrow>
        <PdfCoverTitle size={42}>
          How long until
          <br />
          <em>they run out</em>?
        </PdfCoverTitle>
        <p style={{ color: "var(--r-ink-3)", fontSize: "var(--pq-text-body)", lineHeight: 1.55, marginTop: 12, maxWidth: "140mm" }}>
          Cash burn and runway across growth names. Who survives the next round, who doesn&rsquo;t.
        </p>

        <div style={{ marginTop: 24 }}>
          <PdfKpiRow
            cols={3}
            kpis={[
              { label: "Holdings Tracked", value: data.tracked.value, delta: data.tracked.detail },
              { label: "Avg Runway", value: data.avgRunway.value, delta: data.avgRunway.detail, deltaTone: "warn" },
              { label: "Combined Cash", value: data.combinedCash.value, delta: data.combinedCash.detail, deltaTone: "pos" },
            ]}
          />
        </div>

        <PdfSectionTitle variant="sm">Runway Ranking · 활주로 순위</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Holding</th>
              <th className="right">Cash</th>
              <th className="right">Q Burn</th>
              <th className="right">Runway</th>
              <th>Status</th>
              <th className="right">Position</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.ticker}>
                <td>
                  <PdfTicker>{r.ticker}</PdfTicker>
                  {r.name}
                </td>
                <td className="right">{r.cash}</td>
                <td className={`right ${r.qBurnTone}`}>{r.qBurn}</td>
                <td className="right" style={{ color: r.runwayTone === "warn" ? "var(--r-warn)" : r.runwayTone === "neg" ? "var(--r-neg)" : r.runwayTone === "pos" ? "var(--r-pos)" : undefined }}>
                  {r.runway}
                </td>
                <td>
                  <span style={{ color: STATUS_TONE[r.status] }}>{r.status}</span>
                </td>
                <td className="right">{r.position}</td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfPageFooter left="Burn Rate · Premium" right="Page 01" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 2 — 2026-05-06 Strategy B Option 2: explicit disclaim-only PdfPage so
          chromium print engine never pushes the disclaimer onto a ghost sheet. */}
      <PdfPage>
        <PdfHeader tier="premium" title="BURN RATE" meta={`${data.asOf}${data.reportTag ? ` · ${data.reportTag}` : ""} · 02/03`} />
        <PdfGoldRule />

        <PdfEyebrow>02 — Critical Watch</PdfEyebrow>
        <PdfSectionTitle>Critical · 12개월 미만 활주로</PdfSectionTitle>

        {data.critical.map((c) => {
          const fillPct = Math.max(8, Math.min(40, (c.runwayMonths / 24) * 100));
          return (
            <PdfCard key={c.ticker}>
              <PdfFlexBetween style={{ marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }} className="font-mono" >
                    {c.name && c.name !== c.ticker ? `${c.name} · ${normalizeTicker(c.ticker)}` : displayTicker(c.ticker, c.name)}
                  </div>
                  <h3 style={{ fontSize: "var(--pq-text-quote)", margin: 0, fontWeight: 500 }} className="font-serif" >
                    Runway:{" "}
                    <span style={{ color: c.runwayLabelTone === "warn" ? "var(--r-gold)" : "var(--r-neg)" }}>
                      {c.runwayLabel}
                    </span>
                  </h3>
                </div>
                <div style={{ fontSize: "var(--pq-text-eyebrow)" }} className="font-mono" >{c.cashBurnLine}</div>
              </PdfFlexBetween>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "30mm 1fr 18mm",
                  alignItems: "center",
                  gap: 12,
                  padding: "9px 0",
                }}
              >
                <div style={{ fontSize: "var(--pq-text-eyebrow)" }} className="font-mono" >Runway gauge</div>
                <div style={{ height: 8, background: "var(--r-bg-soft)", borderRadius: 2, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${fillPct}%`,
                      height: "100%",
                      background: c.runwayLabelTone === "warn"
                        ? "linear-gradient(90deg, var(--r-neg), var(--r-warn))"
                        : "var(--r-neg)",
                      borderRadius: 2,
                    }}
                  />
                </div>
                <div style={{ textAlign: "right", fontSize: "var(--pq-text-eyebrow)" }} className="font-mono" >
                  {c.runwayMonths} / 24 mo
                </div>
              </div>
              <p style={{ color: "var(--r-ink-3)", marginTop: 12, fontSize: "var(--pq-text-eyebrow)", lineHeight: 1.6 }}>{c.note}</p>
              <div style={{ paddingTop: 8 }}>
                <PdfCheckList items={[{ checked: false, body: <><strong>Action</strong> — {c.action}</>, meta: "P1" }]} />
              </div>
            </PdfCard>
          );
        })}

        <PdfSectionTitle variant="sm">Watch · 12–18개월</PdfSectionTitle>
        <div style={{ background: "var(--r-bg-soft)", borderRadius: 6, padding: 16, marginBottom: 14 }}>
          <PdfFlexBetween>
            <div>
              <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }} className="font-mono" >
                {data.watch.name && data.watch.name !== data.watch.ticker
                  ? `${data.watch.name} · ${normalizeTicker(data.watch.ticker)}`
                  : displayTicker(data.watch.ticker, data.watch.name)}
              </div>
              <strong>{data.watch.runway}</strong>
            </div>
            <div style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--r-ink-3)" }} className="font-mono" >{data.watch.cashBurnLine}</div>
          </PdfFlexBetween>
          <p style={{ color: "var(--r-ink-3)", marginTop: 8, fontSize: "var(--pq-text-eyebrow)", lineHeight: 1.55 }}>{data.watch.note}</p>
        </div>

        <div style={{ marginTop: 18 }}>
          <PdfCallout label="CFO's Note">{data.cfoNote}</PdfCallout>
        </div>

        <PdfGovBlock />
        <PdfPageFooter left="Burn Rate · Premium · Not investment advice" right="Page 02" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 3 — DISCLAIMER (atomic disclaim-only sheet) */}
      <PdfPage>
        <PdfHeader tier="premium" title="BURN RATE" meta={`${data.asOf}${data.reportTag ? ` · ${data.reportTag}` : ""} · 03/03`} />
        <PdfGoldRule />
        <PdfDisclaimer cadence="monthly" />
      </PdfPage>
    </>
  );
}
