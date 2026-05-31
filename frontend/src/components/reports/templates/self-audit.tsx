/**
 * Report 07 — Self Audit (Pro · 2 pages · On Demand)
 *
 * Source: /design_handoff_pdf_reports/reports/07_self_audit.html
 *
 * Page 1: Cover headline + 4-up KPI (audit grade) + 8-rule compliance checklist
 *         + "what you said vs what you did" consistency table.
 * Page 2: Bias heatmap (alloc bars) + top-flag card + 3 audit findings cards
 *         + auditor's note + sign row + governance + disclaimer.
 *
 * Compliance: All findings are process audits, not investment advice.
 * No buy/sell/hold language. Cadence: ondemand (one-off).
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
  PdfCheckList,
  PdfTable,
  PdfTwoCol,
  PdfCard,
  PdfCallout,
  PdfFlexBetween,
  PdfDivider,
  PdfSignRow,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";
import { EmptyState } from "../empty-state";

export interface SelfAuditData {
  asOf: string; // "Apr 26, 2026 · SA-2026-04"
  intro: string;
  kpis: {
    score: { value: string; prev: string };
    rulesFollowed: { value: string; pct: string };
    decisionsLogged: { value: string; pct: string };
    biasFlags: { value: string; target: string };
  };
  rules: { num: string; text: string; status: string; statusTone: "pos" | "neg" | "warn" }[];
  consistency: { said: string; did: string; match: "✓" | "✗" }[];
  biasHeat: { name: string; pct: number; pctDisplay: string; tone: "pos" | "neg" | "neutral"; flat?: boolean }[];
  topFlag: { tag: string; title: string; body: string; counterRule: string };
  findings: {
    code: string;
    severity: "MAJOR" | "MINOR" | "OBSERVATION";
    due: string;
    dueTone?: "neg" | "neutral";
    title: string;
    body: string;
  }[];
  auditorNote: string;
}


const TONE_STYLE: Record<"pos" | "neg" | "warn" | "neutral", string | undefined> = {
  pos: "var(--r-pos)",
  neg: "var(--r-neg)",
  warn: "var(--r-warn)",
  neutral: undefined,
};

export function SelfAudit({ data }: { data?: SelfAuditData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="self_audit" reason="no_trades" />;
  }
  return (
    <>
      {/* ═══════ PAGE 1 ═══════ */}
      <PdfPage>
        <PdfHeader tier="pro" title="SELF AUDIT" meta={data.asOf} />
        <PdfGoldRule />


        <PdfEyebrow>Self Audit · On Demand</PdfEyebrow>
        <PdfCoverTitle size={42}>
          Are your decisions <em>consistent</em>?—<br />
          you, seen by the auditor.
        </PdfCoverTitle>
        <p
          style={{
            color: "var(--r-ink-3)",
            marginTop: 12,
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.55,
          }}
        className="font-serif" >
          {data.intro}
        </p>

        <div style={{ marginTop: 24 }}>
          <PdfKpiRow
            kpis={[
              { label: "Audit Score", value: data.kpis.score.value, delta: data.kpis.score.prev },
              { label: "Rules Followed", value: data.kpis.rulesFollowed.value, delta: data.kpis.rulesFollowed.pct, deltaTone: "warn" },
              { label: "Decisions Logged", value: data.kpis.decisionsLogged.value, delta: data.kpis.decisionsLogged.pct, deltaTone: "pos" },
              { label: "Bias Flags", value: data.kpis.biasFlags.value, delta: data.kpis.biasFlags.target, deltaTone: "neg" },
            ]}
          />
        </div>

        <PdfSectionTitle variant="sm">Rule Compliance · 룰 준수 점검</PdfSectionTitle>
        <PdfCheckList
          items={data.rules.map((r) => ({
            checked: r.statusTone === "pos",
            body: (
              <>
                <strong>{r.num} · {r.text.split(" — ")[0]}</strong>
                {r.text.includes(" — ") && <> — {r.text.split(" — ").slice(1).join(" — ")}</>}
              </>
            ),
            meta: <span style={{ color: TONE_STYLE[r.statusTone] }}>{r.status}</span>,
          }))}
        />

        <PdfSectionTitle variant="sm">Consistency Check · 말과 행동</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>What You Said</th>
              <th>What You Did</th>
              <th className="right">Match</th>
            </tr>
          </thead>
          <tbody>
            {data.consistency.map((c, i) => (
              <tr key={i}>
                <td>{c.said}</td>
                <td>{c.did}</td>
                <td className={`right ${c.match === "✓" ? "pos" : "neg"}`}>{c.match}</td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfPageFooter left="Self Audit · Pro" right="Page 01" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* ═══════ PAGE 2 ═══════ */}
      <PdfPage>
        <PdfHeader tier="pro" title="SELF AUDIT" meta={`${data.asOf} · 02/03`} />
        <PdfGoldRule />

        <PdfSectionTitle variant="sm">Bias Heatmap · 편향 분포</PdfSectionTitle>

        <PdfTwoCol>
          <div>
            {data.biasHeat.map((b, i) => {
              const pctClamped = Math.max(0, Math.min(100, b.pct));
              return (
                <div key={i} className="pq-pdf-alloc-row">
                  <div><strong>{b.name}</strong></div>
                  <div className={`pq-pdf-alloc-bar${b.flat ? " flat" : ""}`}>
                    <i style={{ width: `${pctClamped}%` }} />
                  </div>
                  <div className="pq-pdf-alloc-pct" style={{ color: TONE_STYLE[b.tone] }}>
                    {b.pctDisplay}
                  </div>
                </div>
              );
            })}
          </div>
          <div>
            <div className="pq-pdf-col-title">Top Flag · 가장 큰 패턴</div>
            <PdfCard soft>
              <div
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  color: "var(--r-ink-3)",
                  letterSpacing: "1.5px",
                  textTransform: "uppercase",
                }}
              className="font-mono" >
                {data.topFlag.tag}
              </div>
              <h3
                style={{
                  fontSize: "var(--pq-text-quote)",
                  margin: "8px 0",
                  fontWeight: 500,
                }}
              className="font-serif" >
                {data.topFlag.title}
              </h3>
              <p
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  lineHeight: 1.6,
                  color: "var(--r-ink-2)",
                }}
              >
                {data.topFlag.body}
              </p>
              <PdfDivider />
              <div style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--r-ink-3)" }}>
                <strong>{data.topFlag.counterRule}</strong>
              </div>
            </PdfCard>
          </div>
        </PdfTwoCol>

        <PdfSectionTitle variant="sm">Audit Findings · 시정 사항</PdfSectionTitle>

        {data.findings.map((f, i) => (
          <PdfCard key={i}>
            <PdfFlexBetween>
              <div className="pq-pdf-kpi-lbl">
                {f.code} · {f.severity}
              </div>
              <div
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  color:
                    f.dueTone === "neg"
                      ? "var(--r-neg)"
                      : f.dueTone === "neutral"
                        ? "var(--r-ink-4)"
                        : undefined,
                }}
              className="font-mono" >
                {f.due}
              </div>
            </PdfFlexBetween>
            <h3
              style={{
                fontSize: "var(--pq-text-h5)",
                margin: "8px 0 6px",
                fontWeight: 500,
              }}
            className="font-serif" >
              {f.title}
            </h3>
            <p
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                lineHeight: 1.6,
                color: "var(--r-ink-3)",
              }}
            >
              {f.body}
            </p>
          </PdfCard>
        ))}

        <div style={{ marginTop: 18 }}>
          <PdfCallout flat label="Auditor's Note">
            {data.auditorNote}
          </PdfCallout>
        </div>

        <PdfSignRow
          left="감사관 (Self) · _____________"
          right="감사 일자 · _____________"
        />

        <PdfGovBlock />

        <PdfPageFooter
          left="Self Audit · Pro · Not investment advice"
          right="Page 02"
        />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* ═══════ PAGE 3 — DISCLAIMER (atomic disclaim-only sheet) ═══════ */}
      <PdfPage>
        <PdfHeader tier="pro" title="SELF AUDIT" meta={`${data.asOf} · 03/03`} />
        <PdfGoldRule />
        <PdfDisclaimer cadence="ondemand" />
      </PdfPage>
    </>
  );
}
