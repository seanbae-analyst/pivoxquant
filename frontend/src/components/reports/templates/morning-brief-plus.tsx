/**
 * Report — Morning Brief Plus (Pro · 1 page · Daily · Pre-market)
 *
 * Source: frontend/public/samples/morning_brief_plus.pdf
 *
 * The pre-market briefing. Cover headline + 4-up macro KPI row (S&P FUTURES,
 * 10Y YIELD, DXY, VIX), top moves checklist, and the one observation for the
 * open. Lives outside the dashboard auth layout so the design can be reviewed
 * without logging in.
 *
 * Compliance: POSITIVE / NEGATIVE / NEUTRAL labels only. No buy/sell/hold.
 * Cadence is "daily" — disclaimer reflects pre-market timing.
 */

"use client";

import {
  PdfPage,
  PdfHeader,
  PdfEyebrow,
  PdfCoverTitle,
  PdfKpiRow,
  PdfTwoCol,
  PdfColTitle,
  PdfCheckList,
  PdfCard,
  PdfCallout,
  PdfNotes,
  PdfPageFooter,
  PdfDisclaimerMini,
  PdfSectionTitle,
} from "../pdf-primitives";
import { EmptyState } from "../empty-state";

export interface MorningBriefPlusData {
  asOf: string;            // "2026-04-28"
  briefTag: string;        // "MB-2026-04-28"
  /** S&P 500 futures level + delta */
  spFutures: string;       // "5,842.25"
  spFuturesDelta: string;  // "▲ 0.42%"
  /** US 10Y yield */
  tenYieldPct: string;     // "4.18%"
  tenYieldDelta: string;   // "▼ 2bps"
  /** US Dollar Index */
  dxy: string;             // "104.32"
  dxyDelta: string;        // "▲ 0.18%"
  /** CBOE VIX */
  vix: string;             // "14.22"
  vixDelta: string;        // "▼ 0.31"
  /** Three pre-market moves to observe */
  topMoves: { body: string; meta: string; checked: boolean }[];
  /** The one observation for the open */
  observation: string;
  /** Pre-market memo — what the user is watching today */
  memoToSelf: string;
}


export function MorningBriefPlus({ data }: { data?: MorningBriefPlusData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="morning_brief" reason="no_artifact" />;
  }
  return (
    <PdfPage>
      <PdfHeader
        tier="pro"
        title="MORNING BRIEF PLUS"
        meta={`${data.asOf} · ${data.briefTag}`}
      />


      <PdfEyebrow>Morning Brief · Before The Bell</PdfEyebrow>
      <PdfCoverTitle size={42}>
        Opens in <em>3 hours</em>—<br />
        today, in <em>five lines</em>.
      </PdfCoverTitle>
      <p
        style={{
          color: "var(--r-ink-3)",
          marginTop: 12,
          fontSize: "var(--pq-text-body)",
          lineHeight: 1.55,
        }}
      className="font-serif" >
        Pre-market macro snapshot, three moves that matter, one observation
        for the open. Read it with coffee.
      </p>

      <div style={{ marginTop: 24 }}>
        <PdfKpiRow
          cols={4}
          kpis={[
            {
              label: "S&P Futures",
              value: data.spFutures,
              delta: data.spFuturesDelta,
              deltaTone: "pos",
            },
            {
              label: "10Y Yield",
              value: data.tenYieldPct,
              delta: data.tenYieldDelta,
              deltaTone: "neg",
            },
            {
              label: "DXY",
              value: data.dxy,
              delta: data.dxyDelta,
            },
            {
              label: "VIX",
              value: data.vix,
              delta: data.vixDelta,
              deltaTone: "neg",
            },
          ]}
        />
      </div>

      <PdfTwoCol>
        <div>
          <PdfColTitle>Top Moves · 프리마켓</PdfColTitle>
          <PdfCheckList
            items={data.topMoves.map((m) => ({
              checked: m.checked,
              body: m.body,
              meta: m.meta,
            }))}
          />
        </div>
        <div>
          <PdfColTitle>Macro Snapshot</PdfColTitle>
          <PdfCard>
            <div className="pq-pdf-kpi-lbl">Tape Tone</div>
            <div
              style={{
                fontSize: "var(--pq-text-avatar)",
                marginTop: 4,
              }}
            className="font-serif" >
              POSITIVE
            </div>
            <div
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                color: "var(--r-ink-3)",
                marginTop: 8,
                lineHeight: 1.55,
              }}
            >
              Futures bid · yields easing · vol compressed.
              Risk-on tilt into the open.
            </div>
          </PdfCard>
        </div>
      </PdfTwoCol>

      <div style={{ marginTop: 18 }}>
        <PdfCallout flat label="At The Open · The One Observation">
          {data.observation}
        </PdfCallout>
      </div>

      <div style={{ marginTop: 18 }}>
        <PdfSectionTitle variant="sm">Memo to Self · Today</PdfSectionTitle>
        <PdfNotes>{data.memoToSelf}</PdfNotes>
      </div>

      <PdfPageFooter
        left="For information only · pivoxquant.com"
        right={`Morning Brief Plus · ${data.briefTag}`}
      />

      <PdfDisclaimerMini />
    </PdfPage>
  );
}
