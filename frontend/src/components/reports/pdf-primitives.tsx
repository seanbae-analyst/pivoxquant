/**
 * PivoxQuant — PDF Report Primitives
 *
 * Reusable building blocks for the 18 print-ready reports defined in
 * /design_handoff_pdf_reports/. Each primitive maps 1:1 to a class in
 * globals.css under the `.pq-report` scope.
 *
 * Design source: design_handoff_pdf_reports/reports/base.css (CEO 2026-04-27).
 *
 * Usage:
 *   <ReportSurface tier="free">
 *     <PdfPage>
 *       <PdfHeader tier="free" title="WEEKLY MEMO" meta="2026-04-26 · WK-23" />
 *       …content blocks…
 *       <PdfDisclaimer cadence="weekly" />
 *     </PdfPage>
 *   </ReportSurface>
 */

"use client";

import { Fragment } from "react";
import type { ReactNode } from "react";
import {
  composeDisclaimer,
  DEFAULT_GOVERNANCE,
  type Cadence,
  type GovernanceMeta,
  type ReportTier,
} from "@/lib/reports/disclaimer";

/* ────────────────────────────────────────────────────────────
   ReportSurface — root wrapper. Forces the .pq-report scope so
   Source Serif 4 + ink palette take effect; isolates the dashboard
   Vantablack theme from leaking in.
   ──────────────────────────────────────────────────────────── */

export function ReportSurface({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`pq-report ${className}`.trim()}>{children}</div>;
}

/* ────────────────────────────────────────────────────────────
   PdfToolbar — preview-only chrome with PDF/print button.
   Hidden on @media print.
   ──────────────────────────────────────────────────────────── */

export function PdfToolbar({
  onPrint,
  extra,
}: {
  onPrint?: () => void;
  extra?: ReactNode;
}) {
  return (
    <div className="pq-pdf-toolbar">
      <button
        type="button"
        className="primary"
        onClick={() => (onPrint ? onPrint() : window.print())}
      >
        PDF로 저장 / 인쇄
      </button>
      {extra}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   PdfPage — single A4 sheet
   ──────────────────────────────────────────────────────────── */

export function PdfPage({
  children,
  compact = false,
}: {
  children: ReactNode;
  compact?: boolean;
}) {
  return (
    <section className={`pq-pdf-page${compact ? " compact" : ""}`}>
      {children}
    </section>
  );
}

/* ────────────────────────────────────────────────────────────
   PdfHeader — brand wordmark + tier chip + meta
   ──────────────────────────────────────────────────────────── */

export function PdfHeader({
  tier,
  title,
  meta,
}: {
  tier: ReportTier;
  title: string;
  meta: string;
}) {
  return (
    <div className="pq-pdf-header">
      <div>
        <span className="pq-pdf-brand-name">
          pivox<span className="accent">quant</span>
        </span>
      </div>
      <div className="pq-pdf-meta">
        <strong>
          <span className={`pq-pdf-tier-chip ${tier}`}>
            {tier.toUpperCase()}
          </span>
          {title}
        </strong>
        <span>{meta}</span>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Eyebrow + section titles
   ──────────────────────────────────────────────────────────── */

export function PdfEyebrow({ children }: { children: ReactNode }) {
  return <div className="pq-pdf-eyebrow">{children}</div>;
}

export function PdfSectionTitle({
  children,
  variant,
}: {
  children: ReactNode;
  variant?: "default" | "sm" | "dry";
}) {
  const cls =
    variant === "sm"
      ? "pq-pdf-section-title sm"
      : variant === "dry"
        ? "pq-pdf-section-title dry"
        : "pq-pdf-section-title";
  return <div className={cls}>{children}</div>;
}

export function PdfColTitle({ children }: { children: ReactNode }) {
  return <div className="pq-pdf-col-title">{children}</div>;
}

/* ────────────────────────────────────────────────────────────
   Cover headline
   ──────────────────────────────────────────────────────────── */

export function PdfCoverEyebrow({ children }: { children: ReactNode }) {
  return <div className="pq-pdf-cover-eyebrow">{children}</div>;
}

export function PdfCoverTitle({
  children,
  size = 64,
}: {
  children: ReactNode;
  size?: number;
}) {
  return (
    <h1 className="pq-pdf-cover-title" style={{ fontSize: size }}>
      {children}
    </h1>
  );
}

export function PdfCoverSub({ children }: { children: ReactNode }) {
  return <p className="pq-pdf-cover-sub">{children}</p>;
}

/* ────────────────────────────────────────────────────────────
   KPI row
   ──────────────────────────────────────────────────────────── */

export interface PdfKpi {
  label: string;
  value: ReactNode;
  delta?: ReactNode;
  deltaTone?: "pos" | "neg" | "warn" | "neutral";
  small?: boolean;
}

export function PdfKpiRow({
  kpis,
  cols,
}: {
  kpis: PdfKpi[];
  cols?: 2 | 3 | 4;
}) {
  const colsCls = cols === 2 ? " cols-2" : cols === 3 ? " cols-3" : "";
  return (
    <div className={`pq-pdf-kpi-row${colsCls}`}>
      {kpis.map((k, i) => (
        <div key={i} className="pq-pdf-kpi">
          <div className="pq-pdf-kpi-lbl">{k.label}</div>
          <div className={`pq-pdf-kpi-val${k.small ? " sm" : ""}`}>
            {k.value}
          </div>
          {k.delta != null && (
            <div
              className={`pq-pdf-kpi-delta${
                k.deltaTone === "pos"
                  ? " pos"
                  : k.deltaTone === "neg"
                    ? " neg"
                    : k.deltaTone === "warn"
                      ? " warn"
                      : ""
              }`}
            >
              {k.delta}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Table — renders an arbitrary HTMLTableElement subtree, but with
   project conventions: ".right" for numeric columns, "tr.total" for
   bold totals, td.pos / td.neg for colored numbers.
   ──────────────────────────────────────────────────────────── */

export function PdfTable({ children }: { children: ReactNode }) {
  return (
    <div className="pq-pdf-table-wrap" style={{ breakInside: "avoid", pageBreakInside: "avoid" }}>
      <table className="pq-pdf-table">{children}</table>
    </div>
  );
}

export function PdfTicker({ children }: { children: ReactNode }) {
  return <span className="pq-pdf-ticker">{children}</span>;
}

/* ────────────────────────────────────────────────────────────
   Allocation row (sector / holding)
   ──────────────────────────────────────────────────────────── */

export interface PdfAllocItem {
  name: ReactNode;
  pct: number; // 0-100
  pctDisplay?: ReactNode; // optional pre-formatted "12.4%" — accepts JSX for color tags
}

export function PdfAllocList({ items }: { items: PdfAllocItem[] }) {
  return (
    <div>
      {items.map((it, i) => {
        const fillWidth = `${Math.max(0, Math.min(100, it.pct))}%`;
        return (
          <div key={i} className="pq-pdf-alloc-row">
            <div>{it.name}</div>
            <div className="pq-pdf-alloc-bar">
              <i style={{ width: fillWidth }} />
            </div>
            <div className="pq-pdf-alloc-pct">
              {it.pctDisplay ?? `${it.pct.toFixed(1)}%`}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Cards / callout / pullquote
   ──────────────────────────────────────────────────────────── */

export function PdfCard({
  children,
  soft = false,
}: {
  children: ReactNode;
  soft?: boolean;
}) {
  return <div className={`pq-pdf-card${soft ? " soft" : ""}`}>{children}</div>;
}

export function PdfCallout({
  children,
  flat = false,
  label,
}: {
  children: ReactNode;
  flat?: boolean;
  label?: ReactNode;
}) {
  return (
    <div className={`pq-pdf-callout${flat ? " flat" : ""}`}>
      {label && (
        <div
          className="pq-pdf-eyebrow"
          style={{ marginBottom: 8, color: "var(--r-ink-3)" }}
        >
          {label}
        </div>
      )}
      <div>{children}</div>
    </div>
  );
}

export function PdfPullquote({ children }: { children: ReactNode }) {
  return <div className="pq-pdf-pullquote">{children}</div>;
}

/* ────────────────────────────────────────────────────────────
   Two / three column grids
   ──────────────────────────────────────────────────────────── */

export function PdfTwoCol({ children }: { children: ReactNode }) {
  return <div className="pq-pdf-two-col">{children}</div>;
}
export function PdfThreeCol({ children }: { children: ReactNode }) {
  return <div className="pq-pdf-three-col">{children}</div>;
}

/* ────────────────────────────────────────────────────────────
   Checklist row
   ──────────────────────────────────────────────────────────── */

export interface PdfCheckItem {
  checked?: boolean;
  body: ReactNode;
  meta?: ReactNode;
}

export function PdfCheckList({ items }: { items: PdfCheckItem[] }) {
  return (
    <div>
      {items.map((it, i) => (
        <div key={i} className="pq-pdf-check-row">
          <div className={`pq-pdf-check-box${it.checked ? " checked" : ""}`} />
          <div>{it.body}</div>
          {it.meta != null && (
            <div className="pq-pdf-check-meta">{it.meta}</div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Notes block (placeholder for free-form copy)
   ──────────────────────────────────────────────────────────── */

export function PdfNotes({
  children,
  tall = false,
}: {
  children: ReactNode;
  tall?: boolean;
}) {
  return (
    <div className={`pq-pdf-notes${tall ? " tall" : ""}`}>{children}</div>
  );
}

/* ────────────────────────────────────────────────────────────
   Page footer (small mono row above the disclaimer)
   ──────────────────────────────────────────────────────────── */

export function PdfPageFooter({
  left,
  right,
}: {
  left?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="pq-pdf-page-footer">
      <span>{left ?? "For information only · pivoxquant.com"}</span>
      <span>{right}</span>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Disclaimer block — required by 자본시장법.
   Full version: KO + EN justified copy. Use ONCE per report on
   the final page (alongside <PdfGovBlock />). Intermediate pages
   should use <PdfDisclaimerMini /> to avoid spilling onto a
   near-empty ghost page.
   ──────────────────────────────────────────────────────────── */

export function PdfDisclaimer({
  cadence,
  withBacktest = false,
}: {
  cadence: Cadence;
  withBacktest?: boolean;
}) {
  const { ko, en } = composeDisclaimer({ cadence, withBacktest });
  return (
    <div className="pq-pdf-disclaimer" data-pq-disclaimer="true">
      <p>
        <strong>면책 고지</strong> · {ko}
      </p>
      <p style={{ marginTop: 6 }}>
        <strong>Disclosure</strong> · {en}
      </p>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   PdfDisclaimerMini — 1-line, 8pt mini disclosure for non-final
   pages. Keeps a visible compliance hint on every page without
   spilling the full KO+EN block (which causes near-empty ghost
   pages). Use on every PdfPage EXCEPT the last. The last page
   should render the full <PdfDisclaimer />.
   ──────────────────────────────────────────────────────────── */

export function PdfDisclaimerMini() {
  return (
    <div
      className="pq-pdf-disclaimer-mini"
      data-pq-disclaimer-mini="true"
      aria-label="Observational research only"
    >
      관찰적 연구 목적 · 투자자문 아님 · OBSERVATIONAL RESEARCH ONLY · NOT INVESTMENT ADVICE
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Governance block — required for Pro / Premium tiers.
   Prepared by · Reviewed by · Methodology · Sources.
   ──────────────────────────────────────────────────────────── */

export function PdfGovBlock({
  meta = DEFAULT_GOVERNANCE,
}: {
  meta?: GovernanceMeta;
}) {
  return (
    <div className="pq-pdf-gov-block">
      <div className="pq-pdf-gov-cell">
        <div className="lbl">Prepared by</div>
        <div className="val">{meta.preparedBy}</div>
      </div>
      <div className="pq-pdf-gov-cell">
        <div className="lbl">Reviewed by</div>
        <div className="val">{meta.reviewedBy}</div>
      </div>
      <div className="pq-pdf-gov-cell">
        <div className="lbl">Methodology</div>
        <div className="val">{meta.methodology}</div>
      </div>
      <div className="pq-pdf-gov-cell">
        <div className="lbl">Sources</div>
        <div className="val">{meta.sources}</div>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Stat block — large display number with mono label
   ──────────────────────────────────────────────────────────── */

export function PdfStat({
  label,
  value,
  delta,
}: {
  label: ReactNode;
  value: ReactNode;
  delta?: ReactNode;
}) {
  return (
    <div className="pq-pdf-stat">
      <div className="pq-pdf-stat-lbl">{label}</div>
      <div className="pq-pdf-stat-val">{value}</div>
      {delta && <div className="pq-pdf-kpi-delta">{delta}</div>}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Heat tag (KPI status pill)
   ──────────────────────────────────────────────────────────── */

export function PdfHeat({
  tone,
  children,
}: {
  tone: "green" | "amber" | "red";
  children: ReactNode;
}) {
  return <span className={`pq-pdf-heat ${tone}`}>{children}</span>;
}

/* ────────────────────────────────────────────────────────────
   Gold rule (Pro/Premium covers)
   ──────────────────────────────────────────────────────────── */

export function PdfGoldRule() {
  return <div className="pq-pdf-gold-rule" />;
}

export function PdfHairline({ strong = false }: { strong?: boolean }) {
  return <div className={`pq-pdf-hairline${strong ? " strong" : ""}`} />;
}

export function PdfDivider() {
  return <div className="pq-pdf-divider" />;
}

export function PdfFlexBetween({
  children,
  className = "",
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div className={`pq-pdf-flex-between ${className}`.trim()} style={style}>
      {children}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Status Badge — IC-pack severity / verdict pill
   Matches base.css `.badge` semantics (severe/high/moderate/low/neutral/info).
   ──────────────────────────────────────────────────────────── */

export type BadgeTone =
  | "severe"
  | "high"
  | "moderate"
  | "low"
  | "neutral"
  | "info";

export function PdfBadge({
  tone = "neutral",
  children,
}: {
  tone?: BadgeTone;
  children: ReactNode;
}) {
  return <span className={`pq-pdf-badge ${tone}`}>{children}</span>;
}

/* ────────────────────────────────────────────────────────────
   Severity Dot
   ──────────────────────────────────────────────────────────── */

export function PdfDot({ tone = "neutral" }: { tone?: BadgeTone }) {
  return <span className={`pq-pdf-dot ${tone}`} />;
}

/* ────────────────────────────────────────────────────────────
   Limit Gauge — risk-board limit row (utilization vs cap)
   ──────────────────────────────────────────────────────────── */

export interface PdfLimitItem {
  name: ReactNode;
  detail?: ReactNode;
  /** 0-100, fill width as % of bar */
  fillPct: number;
  /** 0-100, position of cap marker */
  capPct: number;
  /** Pre-formatted "42% / 35%" */
  valueLabel: ReactNode;
  /** Color class for fill */
  fillState?: "ok" | "warn" | "breach";
  status: ReactNode;
}

export function PdfLimitRow({ item }: { item: PdfLimitItem }) {
  const clampedFill = `${Math.max(0, Math.min(100, item.fillPct))}%`;
  const clampedCap = `${Math.max(0, Math.min(100, item.capPct))}%`;
  const fillCls =
    item.fillState === "warn"
      ? " warn"
      : item.fillState === "breach"
        ? " breach"
        : "";
  return (
    <div className="pq-pdf-lim-row">
      <div className="pq-pdf-lim-name">
        <strong>{item.name}</strong>
        {item.detail != null && <small>{item.detail}</small>}
      </div>
      <div className="pq-pdf-lim-gauge">
        <div className={`fill${fillCls}`} style={{ width: clampedFill }} />
        <div className="cap" style={{ left: clampedCap }} />
      </div>
      <div className="pq-pdf-lim-val">{item.valueLabel}</div>
      <div className="pq-pdf-lim-status">{item.status}</div>
    </div>
  );
}

export function PdfLimitList({ items }: { items: PdfLimitItem[] }) {
  return (
    <div>
      {items.map((it, i) => (
        <PdfLimitRow key={i} item={it} />
      ))}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Waterfall — stress test impact bars (#05 risk-board)
   ──────────────────────────────────────────────────────────── */

export interface PdfWaterfallItem {
  label: ReactNode;
  detail?: ReactNode;
  /** 0-100 — left offset of the bar segment in % */
  leftPct: number;
  /** 0-100 — width of the bar segment in % */
  widthPct: number;
  /** 0-100 — axis line position (typically the worst-case marker) */
  axisPct?: number;
  /** Display tone — neg (loss) is default; pos for gains */
  tone?: "neg" | "pos";
  value: ReactNode;
  valueTone?: "pos" | "neg" | "neutral";
}

export function PdfWaterfall({ items }: { items: PdfWaterfallItem[] }) {
  return (
    <div className="pq-pdf-waterfall">
      {items.map((it, i) => {
        const left = `${Math.max(0, Math.min(100, it.leftPct))}%`;
        const width = `${Math.max(0, Math.min(100, it.widthPct))}%`;
        const axis = it.axisPct != null ? `${Math.max(0, Math.min(100, it.axisPct))}%` : null;
        const valueColor =
          it.valueTone === "pos"
            ? "var(--r-pos)"
            : it.valueTone === "neg"
              ? "var(--r-neg)"
              : undefined;
        return (
          <div key={i} className="pq-pdf-wf-row">
            <div>
              <strong>{it.label}</strong>
              {it.detail != null && (
                <>
                  <br />
                  <small
                    style={{
                      color: "var(--r-ink-3)",
                      fontSize: 9,
                    }}
                  >
                    {it.detail}
                  </small>
                </>
              )}
            </div>
            <div className="pq-pdf-wf-bar">
              {axis && <div className="axis" style={{ left: axis }} />}
              <i
                className={it.tone === "pos" ? "pos" : ""}
                style={{ left, width }}
              />
            </div>
            <div className="pq-pdf-wf-val" style={{ color: valueColor }}>
              {it.value}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Donut Chart — allocation mix (#16 monthly finance balance sheet)
   Implemented as SVG with stroke-dasharray (proportional segments).
   ──────────────────────────────────────────────────────────── */

export interface PdfDonutSegment {
  label: ReactNode;
  /** 0-100, must sum to ≤ 100 */
  pct: number;
  color: string;
  pctDisplay?: ReactNode;
}

export function PdfDonut({
  segments,
  centerLabel,
  size = "lg",
}: {
  segments: PdfDonutSegment[];
  centerLabel?: ReactNode;
  size?: "sm" | "lg";
}) {
  // Compute cumulative offsets for stroke-dasharray
  const RADIUS = 15.915;
  const CIRCUM = 2 * Math.PI * RADIUS; // ≈ 100 (intentional — 1pct = 1 unit)
  // Precompute each segment's stroke-dashoffset so we don't mutate during render.
  const segmentOffsets: number[] = [];
  {
    let cumulative = 25; // start at 12 o'clock
    for (const seg of segments) {
      segmentOffsets.push(-cumulative);
      cumulative += seg.pct;
    }
  }
  return (
    <div className="pq-pdf-donut-wrap">
      <svg
        className={`pq-pdf-donut${size === "sm" ? " sm" : ""}`}
        viewBox="0 0 42 42"
      >
        <circle
          cx="21"
          cy="21"
          r={RADIUS}
          fill="#fff"
          stroke="#f0eee8"
          strokeWidth="6"
        />
        {segments.map((seg, i) => {
          const dash = `${seg.pct} ${CIRCUM - seg.pct}`;
          const offset = segmentOffsets[i];
          return (
            <circle
              key={i}
              cx="21"
              cy="21"
              r={RADIUS}
              fill="transparent"
              stroke={seg.color}
              strokeWidth="6"
              strokeDasharray={dash}
              strokeDashoffset={offset}
            />
          );
        })}
        {centerLabel && (
          <text
            x="21"
            y="21"
            textAnchor="middle"
            dominantBaseline="central"
            style={{
              fontSize: 6,
              fontWeight: 600,
              fill: "var(--r-ink)",
            }}
          className="font-serif" >
            {centerLabel}
          </text>
        )}
      </svg>
      <div className="pq-pdf-donut-legend">
        {segments.map((seg, i) => (
          <div key={i} className="lg-row">
            <span className="sw" style={{ background: seg.color }} />
            <span>{seg.label}</span>
            <span className="lg-pct">
              {seg.pctDisplay ?? `${seg.pct.toFixed(1)}%`}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Executive Summary — IC-pack dl/dt/dd block
   Used in #05 risk-board, #16 monthly-finance, #17 KPI dashboard.
   ──────────────────────────────────────────────────────────── */

export interface PdfExecRow {
  term: ReactNode;
  body: ReactNode;
}

export function PdfExecSum({
  title = "Executive Summary",
  stamp,
  rows,
}: {
  title?: ReactNode;
  stamp?: ReactNode;
  rows: PdfExecRow[];
}) {
  return (
    <div className="pq-pdf-exec-sum">
      <div className="es-head">
        <h2>{title}</h2>
        {stamp != null && <span className="es-stamp">{stamp}</span>}
      </div>
      <dl>
        {rows.map((r, i) => (
          <Fragment key={i}>
            <dt>{r.term}</dt>
            <dd>{r.body}</dd>
          </Fragment>
        ))}
      </dl>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Cover Meta Grid — Premium covers (#13, #14, #16, #18)
   ──────────────────────────────────────────────────────────── */

export interface PdfCoverMetaItem {
  label: ReactNode;
  value: ReactNode;
}

export function PdfCoverMetaGrid({ items }: { items: PdfCoverMetaItem[] }) {
  return (
    <div className="pq-pdf-cover-meta-grid">
      {items.map((it, i) => (
        <div key={i} className="pq-pdf-cover-meta">
          <div className="lbl">{it.label}</div>
          <div className="val">{it.value}</div>
        </div>
      ))}
    </div>
  );
}

export function PdfCoverFoot({
  left,
  right,
}: {
  left?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="pq-pdf-cover-foot">
      <span>{left ?? "pivoxquant.com"}</span>
      {right ?? <span className="pq-pdf-conf-stamp">Personal · Confidential</span>}
    </div>
  );
}

export function PdfConfStamp({ children }: { children: ReactNode }) {
  return <span className="pq-pdf-conf-stamp">{children}</span>;
}

/* ────────────────────────────────────────────────────────────
   Sign Row — analyst / reviewer signature lines
   ──────────────────────────────────────────────────────────── */

export interface PdfSignBox {
  children: ReactNode;
}

export function PdfSignRow({ left, right }: { left: ReactNode; right: ReactNode }) {
  return (
    <div className="pq-pdf-sign-row">
      <div className="pq-pdf-sign-box">{left}</div>
      <div className="pq-pdf-sign-box">{right}</div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Rating Ladder — credit rating visual (#14)
   ──────────────────────────────────────────────────────────── */

export interface PdfRatingRung {
  label: string;
  state?: "now" | "prev" | "default";
}

export function PdfRatingLadder({ rungs }: { rungs: PdfRatingRung[] }) {
  return (
    <div className="pq-pdf-rating-ladder">
      {rungs.map((r, i) => (
        <div
          key={i}
          className={`rung${r.state === "now" ? " now" : r.state === "prev" ? " prev" : ""}`}
        >
          {r.label}
        </div>
      ))}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Sparkline — small inline trend (#17 KPI dashboard)
   ──────────────────────────────────────────────────────────── */

export function PdfSparkline({
  values,
  width = 60,
  height = 14,
}: {
  values: number[];
  width?: number;
  height?: number;
}) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = width / (values.length - 1);
  const path = values
    .map((v, i) => {
      const x = i * step;
      const y = height - ((v - min) / range) * height;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className="pq-pdf-spark" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <path d={path} />
    </svg>
  );
}

/* ────────────────────────────────────────────────────────────
   Gauge — single value within range (#05 correlation)
   ──────────────────────────────────────────────────────────── */

export function PdfGauge({
  fillPct,
  scaleLeft,
  scaleRight,
}: {
  /** 0-100 — marker position */
  fillPct: number;
  scaleLeft?: ReactNode;
  scaleRight?: ReactNode;
}) {
  return (
    <>
      <div className="pq-pdf-gauge">
        <i style={{ left: `${Math.max(0, Math.min(100, fillPct))}%` }} />
      </div>
      {(scaleLeft || scaleRight) && (
        <div className="pq-pdf-gauge-scale">
          <span>{scaleLeft}</span>
          <span>{scaleRight}</span>
        </div>
      )}
    </>
  );
}

/* ────────────────────────────────────────────────────────────
   IC-Pack Dark Cover — #17 KPI Dashboard
   Replaces the standard PdfPage with a dark-mode wrapper.
   ──────────────────────────────────────────────────────────── */

export function PdfIcCoverPage({ children }: { children: ReactNode }) {
  return (
    <section className="pq-pdf-page" style={{ padding: 0, background: "#0e0e0e" }}>
      <div className="pq-pdf-ic-cover">{children}</div>
    </section>
  );
}

export function PdfIcEyebrow({ children }: { children: ReactNode }) {
  return <div className="pq-pdf-ic-eyebrow">{children}</div>;
}

export function PdfIcTitle({ children }: { children: ReactNode }) {
  return <h1 className="pq-pdf-ic-title">{children}</h1>;
}

export function PdfIcSub({ children }: { children: ReactNode }) {
  return <p className="pq-pdf-ic-sub">{children}</p>;
}

export interface PdfIcMarqueeItem {
  label: ReactNode;
  value: ReactNode;
  delta?: ReactNode;
  valueTone?: "pos" | "warn" | "neg";
}

export function PdfIcMarquee({ items }: { items: PdfIcMarqueeItem[] }) {
  return (
    <div className="pq-pdf-ic-marquee">
      {items.map((it, i) => {
        const valStyle: React.CSSProperties =
          it.valueTone === "warn"
            ? { color: "#e8b964" }
            : it.valueTone === "neg"
              ? { color: "#e08278" }
              : {};
        return (
          <div key={i} className="marq">
            <div className="lbl">{it.label}</div>
            <div className={`val${it.valueTone === "pos" ? " pos" : ""}`} style={valStyle}>
              {it.value}
            </div>
            {it.delta != null && <div className="delta">{it.delta}</div>}
          </div>
        );
      })}
    </div>
  );
}

export function PdfIcFoot({
  left,
  middle,
  right,
}: {
  left?: ReactNode;
  middle?: ReactNode;
  right: ReactNode;
}) {
  return (
    <div className="pq-pdf-ic-foot">
      <span>{left ?? "pivoxquant.com"}</span>
      <span>{middle}</span>
      <span className="pq-pdf-conf-stamp">{right}</span>
    </div>
  );
}
