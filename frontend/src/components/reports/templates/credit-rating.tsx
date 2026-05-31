/**
 * Report 14 — Credit Rating (Premium · 3 pages · Quarterly)
 *
 * Source: /design_handoff_pdf_reports/reports/14_credit_rating.html
 *
 * Page 1: Cover (eyebrow + title + sub + 4-up cover meta).
 * Page 2: Pullquote + Rating Distribution alloc + Quarter Changes table (upgrades/downgrades).
 * Page 3: Watchlist cards (Negative outlook + downgrade notes) + CDS Spread Watch table
 *         + CFO's Note + sign row + governance + disclaimer.
 *
 * Compliance: Credit watch is descriptive; "ON WATCH" / "DOWNGRADE BIAS" are
 * agency-style classifications, not buy/sell/hold. POSITIVE / NEGATIVE / NEUTRAL only.
 */

"use client";

import {
  PdfPage,
  PdfHeader,
  PdfGoldRule,
  PdfCoverEyebrow,
  PdfCoverTitle,
  PdfCoverSub,
  PdfCoverMetaGrid,
  PdfCoverFoot,
  PdfPullquote,
  PdfSectionTitle,
  PdfAllocList,
  PdfTable,
  PdfTicker,
  PdfFlexBetween,
  PdfCallout,
  PdfSignRow,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";
import { EmptyState } from "../empty-state";

interface RatingChange {
  ticker: string;
  name: string;
  agency: string;
  prev: string;
  now: string;
  nowTone: "pos" | "neg" | "neutral";
  outlook: string;
  outlookTone: "pos" | "neg" | "warn";
  action: string;
  actionTone: "pos" | "neg" | "warn" | "neutral";
}
interface CdsRow {
  ticker: string;
  name: string;
  cds: string;
  delta: string;
  deltaTone: "pos" | "neg";
  vsImplied: string;
  vsImpliedTone: "pos" | "neg" | "neutral";
  signal: string;
  signalTone: "pos" | "neg" | "warn";
}

export interface CreditRatingData {
  doc: string;
  /** Period label for the cover headline (a quarter name). Optional —
   *  omitted rather than hardcoded when the backend does not supply it. */
  coverPeriod?: string;
  reviewed: string;
  upgrades: string;
  downgrades: string;
  onWatch: string;
  pullquote: string;
  distribution: { name: string; pct: number; pctDisplay: string; warn?: boolean; flat?: boolean }[];
  changes: RatingChange[];
  watchPrimary: { lbl: string; title: string; ticker: string; name: string; body: string };
  watchSecondary: { lbl: string; body: string }[];
  cds: CdsRow[];
  cfoNote: string;
}


export function CreditRating({ data }: { data?: CreditRatingData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="credit_rating" reason="no_positions" />;
  }
  return (
    <>
      {/* PAGE 1 — COVER */}
      <PdfPage>
        <PdfHeader tier="premium" title="CREDIT RATING" meta={data.doc} />


        <div style={{ marginTop: "30mm" }}>
          <PdfCoverEyebrow>Credit Rating Review · Quarterly</PdfCoverEyebrow>
          <PdfCoverTitle>
            {data.coverPeriod ? <>{data.coverPeriod}<br /></> : null}
            <em>Credit Watch.</em>
          </PdfCoverTitle>
          <PdfCoverSub>
            Rating moves across holdings this quarter — upgrades, watch, downgrades. Bond-market signals the equity tape won&rsquo;t show you.
          </PdfCoverSub>
        </div>

        <div style={{ marginTop: "auto", paddingTop: "30mm" }}>
          <PdfCoverMetaGrid
            items={[
              { label: "Holdings Reviewed", value: data.reviewed },
              { label: "Upgrades", value: data.upgrades },
              { label: "Downgrades", value: data.downgrades },
              { label: "On Watch", value: data.onWatch },
            ]}
          />
        </div>

        <PdfCoverFoot />
      </PdfPage>

      {/* PAGE 2 */}
      <PdfPage>
        <PdfHeader tier="premium" title="CREDIT RATING" meta={`${data.doc} · 02/04`} />
        <PdfGoldRule />

        <PdfPullquote>{data.pullquote}</PdfPullquote>

        <PdfSectionTitle>Rating Distribution · 분포</PdfSectionTitle>
        <PdfAllocList
          items={data.distribution.map((d) => ({
            name: <strong>{d.name}</strong>,
            pct: d.pct,
            pctDisplay: (
              <span style={{ color: d.warn ? "var(--r-warn)" : undefined }}>{d.pctDisplay}</span>
            ),
          }))}
        />

        <PdfSectionTitle variant="sm">Quarter Changes · 변동</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Agency</th>
              <th className="right">Prev</th>
              <th className="right">Now</th>
              <th className="right">Outlook</th>
              <th className="right">Action</th>
            </tr>
          </thead>
          <tbody>
            {data.changes.map((c) => (
              <tr key={c.ticker}>
                <td>
                  <PdfTicker>{c.ticker}</PdfTicker>{" "}
                  <span style={{ color: "var(--r-ink-3)" }}>{c.name}</span>
                </td>
                <td>{c.agency}</td>
                <td className="right">{c.prev}</td>
                <td className={`right ${c.nowTone === "neutral" ? "" : c.nowTone}`}>{c.now}</td>
                <td className="right" style={{ color: c.outlookTone === "pos" ? "var(--r-pos)" : c.outlookTone === "neg" ? "var(--r-neg)" : "var(--r-warn)" }}>
                  {c.outlook}
                </td>
                <td className="right" style={{ color: c.actionTone === "pos" ? "var(--r-pos)" : c.actionTone === "neg" ? "var(--r-neg)" : c.actionTone === "warn" ? "var(--r-warn)" : "var(--r-ink-3)" }}>
                  {c.action}
                </td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfPageFooter left="Credit Rating · Premium" right="Page 02" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 3 — 2026-05-06 Strategy B Option 2: explicit disclaim-only PdfPage so
          chromium print engine never pushes the disclaimer onto a ghost sheet. */}
      <PdfPage>
        <PdfHeader tier="premium" title="CREDIT RATING" meta={`${data.doc} · 03/04`} />
        <PdfGoldRule />

        <PdfSectionTitle>Watchlist · 끊어질 위험</PdfSectionTitle>

        <div style={{ border: "1.5px solid var(--r-neg)", padding: 22, borderRadius: 6, marginBottom: 14 }}>
          <PdfFlexBetween>
            <div>
              <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }} className="font-mono" >
                {data.watchPrimary.lbl}
              </div>
              <h3 style={{ fontSize: "var(--pq-text-quote)", margin: "6px 0", fontWeight: 500 }} className="font-serif" >
                {data.watchPrimary.title}
              </h3>
            </div>
            <PdfTicker>{data.watchPrimary.ticker}</PdfTicker>
          </PdfFlexBetween>
          <p style={{ fontSize: "var(--pq-text-body)", lineHeight: 1.65, color: "var(--r-ink-2)", marginTop: 12 }}>
            {data.watchPrimary.body}
          </p>
        </div>

        {data.watchSecondary.map((w, i) => (
          <div
            key={i}
            style={{ borderLeft: "3px solid var(--r-warn)", padding: 18, background: "var(--r-bg-soft)", marginBottom: 14, borderRadius: 4 }}
          >
            <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }} className="font-mono" >
              {w.lbl}
            </div>
            <p style={{ fontSize: "var(--pq-text-eyebrow)", lineHeight: 1.6, color: "var(--r-ink-2)", marginTop: 6 }}>{w.body}</p>
          </div>
        ))}

        <PdfSectionTitle variant="sm">CDS Spread Watch · 시장이 매기는 가격</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Ticker</th>
              <th className="right">5y CDS</th>
              <th className="right">3m Δ</th>
              <th className="right">vs Rating Implied</th>
              <th className="right">Signal</th>
            </tr>
          </thead>
          <tbody>
            {data.cds.map((c) => (
              <tr key={c.ticker}>
                <td>
                  <PdfTicker>{c.ticker}</PdfTicker>{" "}
                  <span style={{ color: "var(--r-ink-3)" }}>{c.name}</span>
                </td>
                <td className="right">{c.cds}</td>
                <td className={`right ${c.deltaTone}`}>{c.delta}</td>
                <td className="right" style={{ color: c.vsImpliedTone === "pos" ? "var(--r-pos)" : c.vsImpliedTone === "neg" ? "var(--r-neg)" : undefined }}>
                  {c.vsImplied}
                </td>
                <td className="right" style={{ color: c.signalTone === "pos" ? "var(--r-pos)" : c.signalTone === "neg" ? "var(--r-neg)" : "var(--r-warn)" }}>
                  {c.signal}
                </td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <div style={{ marginTop: 18 }}>
          <PdfCallout flat label="CFO's Note">{data.cfoNote}</PdfCallout>
        </div>

        <PdfSignRow left="분석자 · _____________" right={`검토 일자 · ${data.reviewed}`} />

        <PdfGovBlock />
        <PdfPageFooter left="Credit Rating · Premium · Not investment advice" right="Page 03" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 4 — DISCLAIMER (atomic disclaim-only sheet) */}
      <PdfPage>
        <PdfHeader tier="premium" title="CREDIT RATING" meta={`${data.doc} · 04/04`} />
        <PdfGoldRule />
        <PdfDisclaimer cadence="quarterly" />
      </PdfPage>
    </>
  );
}
