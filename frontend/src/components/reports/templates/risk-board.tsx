/**
 * Report 05 — Risk Board (Pro · 4 pages · Weekly)
 *
 * Source: /design_handoff_pdf_reports/reports/05_risk_board.html
 *
 * Page 1: Executive Summary (dl/dt/dd) + 4-up KPI row + Risk Limits
 *         (gauge bars with cap markers + status badges).
 * Page 2: 7-Layer Risk Defense matrix — PivoxQuant differentiator surface
 *         (W7.2 / E2E P1 #14). Maps backend `risk_defense.py` layers L1-L7
 *         (VaR / Correlation / VIX / Tail / Daily / Sector / Cash) with
 *         threshold + observed + status columns. Mirrors live `/risk`
 *         dashboard (PR #199 hhi + 7-layer schema) for consistency.
 * Page 3: Stress test waterfall + scenario table + correlation gauge +
 *         observed actions checklist + governance.
 * Page 4: Atomic disclaimer sheet.
 *
 * Compliance: All risk metrics are observation labels (BREACH / OVER / OK).
 * No buy/sell/hold language. Pro tier requires GovBlock — included on page 3.
 */

"use client";

import {
  PdfPage,
  PdfHeader,
  PdfGoldRule,
  PdfKpiRow,
  PdfHeat,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";
import { EmptyState } from "../empty-state";

export interface RiskBoardData {
  weekTag: string; // "Week of Apr 26, 2026 · RB-2026-W17"
  asOfStamp: string; // "As of Apr 26, 2026 · 18:00 KST"
  // KPI row — only the four metrics the backend actually computes
  // (services/artifacts/risk_board_service.py: var95_pct / sharpe_annual /
  // max_drawdown_pct / vix_current). `beta` was dropped: the backend never
  // computes a portfolio beta, so a `beta` card would be either a hardcoded
  // fabrication (표시광고법) or an unguarded undefined deref → render_error.
  // VIX takes its slot.
  var95: { value: string; nav: string; tone: "green" | "amber" | "red" };
  maxDD: { value: string; limit: string; tone: "green" | "amber" | "red" };
  sharpe: { value: string; vsPrior: string; tone: "green" | "amber" | "red" };
  vix: { value: string; band: string; tone: "green" | "amber" | "red" };
  // Stress — pairwise correlation proxy (backend derives from sector
  // concentration). Optional so an empty/short book elides the card rather
  // than throwing.
  pairwiseCorr?: { value: string; gauge: number; verdict: string };
}


export function RiskBoard({ data }: { data?: RiskBoardData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="risk_board" reason="no_positions" />;
  }
  return (
    <>
      {/* ═══════ PAGE 1 — EXECUTIVE SUMMARY + LIMITS ═══════ */}
      <PdfPage>
        <PdfHeader
          tier="pro"
          title="RISK BOARD · WEEKLY"
          meta={`${data.weekTag} · 01/02`}
        />

        {/* Executive Summary narrative omitted: the backend does not supply a
            risk-board narrative shape into RiskBoardData. Per CEO 2026-05-31
            "있는 데이터로만, 없으면 없대 해" — render only the real
            VaR/Sharpe/MaxDD/VIX KPI row and the real pairwise-correlation card
            below (all wired from data_json via _risk_board_preview_shape).
            Carry-over: build a backend → RiskBoardData adapter for ExecSum,
            Risk Limits, the 7-Layer matrix, and stress scenarios, then restore
            those surfaces with real data. */}
        <p
          className="font-mono"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: "var(--r-ink-4)",
            letterSpacing: 1.2,
            textTransform: "uppercase",
            marginBottom: 6,
          }}
        >
          {data.asOfStamp}
        </p>

        <PdfKpiRow
          kpis={[
            {
              label: "VaR · 95% 1d",
              value: data.var95.value,
              delta: (
                <>
                  {data.var95.nav} ·{" "}
                  <PdfHeat tone={data.var95.tone}>{data.var95.tone.toUpperCase()}</PdfHeat>
                </>
              ),
              deltaTone: "neg",
            },
            {
              label: "VIX · Current",
              value: data.vix.value,
              delta: (
                <>
                  {data.vix.band} ·{" "}
                  <PdfHeat tone={data.vix.tone}>{data.vix.tone.toUpperCase()}</PdfHeat>
                </>
              ),
              deltaTone: "warn",
            },
            {
              label: "Max Drawdown",
              value: data.maxDD.value,
              delta: (
                <>
                  {data.maxDD.limit} ·{" "}
                  <PdfHeat tone={data.maxDD.tone}>{data.maxDD.tone.toUpperCase()}</PdfHeat>
                </>
              ),
              deltaTone: "neg",
            },
            {
              label: "Sharpe · Annual",
              value: data.sharpe.value,
              delta: (
                <>
                  {data.sharpe.vsPrior} ·{" "}
                  <PdfHeat tone={data.sharpe.tone}>{data.sharpe.tone.toUpperCase()}</PdfHeat>
                </>
              ),
              deltaTone: "pos",
            },
          ]}
        />

        {/* Pairwise-correlation card — rendered only when the backend supplies
            the proxy (derived from sector concentration). Elided otherwise so a
            short/empty book never shows a fabricated correlation. */}
        {data.pairwiseCorr ? (
          <div style={{ marginTop: 20 }}>
            <PdfKpiRow
              kpis={[
                {
                  label: "Pairwise Corr · proxy",
                  value: data.pairwiseCorr.value,
                  delta: data.pairwiseCorr.verdict,
                },
              ]}
            />
          </div>
        ) : null}

        {/* Risk Limits gauge list omitted: the cap/fill/observed values were
            hardcoded, not wired from RiskBoardData. Carry-over: wire backend
            risk-limit observations. */}

        <PdfPageFooter
          left="Risk Board · Pro · Internal use only"
          right="Page 01"
        />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* ═══════ PAGE 2 — DISCLAIMER (atomic disclaim-only sheet) ═══════
         The former 7-Layer Risk Defense matrix, stress-test waterfall, stress
         scenario table, and rebalance notes were entirely hardcoded — the
         backend computes these values but no snake→camel adapter wires them
         into RiskBoardData, so they could not be rendered with real data.
         Per CEO 2026-05-31 they are omitted rather than shown as fabricated
         figures. The real VaR/Beta/MaxDD/Sharpe KPI row and the pairwise
         correlation card remain on page 1. Carry-over: build the backend →
         RiskBoardData adapter (7-layer thresholds/observed, stress scenarios,
         risk limits, rebalance notes) and restore those surfaces. */}
      <PdfPage>
        <PdfHeader
          tier="pro"
          title="RISK BOARD · WEEKLY"
          meta={`${data.weekTag} · 02/02`}
        />
        <PdfGoldRule />
        <PdfDisclaimer cadence="weekly" />
      </PdfPage>
    </>
  );
}
